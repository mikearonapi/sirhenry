"""
Import endpoint — accepts a multipart file upload or a file path reference,
runs the appropriate pipeline importer, and optionally triggers AI categorization.
"""
import logging
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import AsyncSessionLocal, get_session
from api.models.schemas import ImportResultOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/import", tags=["import"])

IMPORT_DIRS = {
    "credit_card": Path("data/imports/credit-cards"),
    "tax_document": Path("data/imports/tax-documents"),
    "investment": Path("data/imports/investments"),
    "amazon": Path("data/imports/amazon"),
    "monarch": Path("data/imports/monarch"),
}


async def _run_post_import_background(tax_year: Optional[int]) -> None:
    """
    Background task: runs AI categorization, Amazon order matching, and
    period recompute after a successful synchronous import.
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            try:
                from pipeline.ai.categorizer import categorize_transactions
                cat_result = await categorize_transactions(session)
                logger.info(f"Background categorization: {cat_result}")
            except Exception as e:
                logger.warning(f"Auto-categorization failed: {e}")

            try:
                from pipeline.importers.amazon import auto_match_amazon_orders
                match_result = await auto_match_amazon_orders(session)
                logger.info(f"Amazon auto-match: {match_result}")
            except Exception as e:
                logger.warning(f"Amazon auto-match failed: {e}")

            try:
                from pipeline.ai.report_gen import recompute_all_periods
                year = tax_year or datetime.now(timezone.utc).year
                await recompute_all_periods(session, year)
            except Exception as e:
                logger.warning(f"Period recompute failed: {e}")


@router.post("/upload", response_model=ImportResultOut)
async def upload_and_import(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: Literal["credit_card", "tax_document", "investment", "amazon", "monarch"] = Form(...),
    account_name: str = Form(""),
    institution: str = Form(""),
    segment: Literal["personal", "business", "investment", "reimbursable"] = Form("personal"),
    tax_year: Optional[int] = Form(None),
    run_categorize: bool = Form(True),
    account_id: Optional[int] = Form(None, description="Import into existing account (skip account creation)"),
    session: AsyncSession = Depends(get_session),
):
    """
    Accept a file upload, save it to the appropriate imports folder,
    then process it via the pipeline.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    suffix = Path(file.filename).suffix.lower()
    allowed = {".csv", ".pdf", ".jpg", ".jpeg", ".png"}
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail=f"File type {suffix} not supported. Use .csv, .pdf, .jpg, or .png")

    dest_dir = IMPORT_DIRS.get(document_type)
    if not dest_dir:
        raise HTTPException(status_code=400, detail=f"Unknown document type: {document_type}")

    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = PurePosixPath(file.filename).name
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    dest_path = dest_dir / safe_name

    # Enforce max upload size (50 MB)
    content = await file.read(50_000_001)  # Read max + 1 byte
    if len(content) > 50_000_000:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")
    with open(dest_path, "wb") as f:
        f.write(content)

    # Run import synchronously for the response (gives immediate feedback)
    result: dict = {}

    if document_type == "credit_card":
        from pipeline.importers.credit_card import import_csv_file
        result = await import_csv_file(
            session, str(dest_path),
            account_name=account_name or file.filename,
            institution=institution,
            default_segment=segment,
            account_id=account_id,
        )
    elif document_type == "tax_document":
        if suffix in (".jpg", ".jpeg", ".png"):
            from pipeline.importers.tax_doc import import_image_file
            result = await import_image_file(session, str(dest_path), tax_year=tax_year)
        else:
            from pipeline.importers.tax_doc import import_pdf_file
            result = await import_pdf_file(session, str(dest_path), tax_year=tax_year)
    elif document_type == "investment":
        from pipeline.importers.investment import import_investment_file
        result = await import_investment_file(
            session, str(dest_path),
            tax_year=tax_year,
            account_name=account_name or "Investment Account",
        )
    elif document_type == "amazon":
        from pipeline.importers.amazon import import_amazon_csv
        result = await import_amazon_csv(
            session, str(dest_path),
            run_categorize=run_categorize,
        )
    elif document_type == "monarch":
        from pipeline.importers.monarch import import_monarch_csv
        result = await import_monarch_csv(
            session, str(dest_path),
            default_segment=segment,
        )

    if result.get("status") == "error":
        raise HTTPException(status_code=422, detail=result.get("message", "Import failed"))

    # Kick off background AI categorization + period recompute
    if run_categorize and result.get("status") == "completed":
        background_tasks.add_task(_run_post_import_background, tax_year)

    return ImportResultOut(
        document_id=result.get("document_id", 0),
        filename=file.filename,
        status=result.get("status", "unknown"),
        transactions_imported=result.get("transactions_imported", 0),
        transactions_skipped=result.get("transactions_skipped", 0),
        message=result.get("message", ""),
    )


@router.post("/batch-tax-docs")
async def batch_import_tax_docs(
    background_tasks: BackgroundTasks,
    tax_year: Optional[int] = None,
    claude_fallback: bool = True,
    session: AsyncSession = Depends(get_session),
):
    """Batch-import all PDFs from data/imports/tax-documents/."""
    from pipeline.importers.tax_doc import import_directory
    directory = str(IMPORT_DIRS["tax_document"])
    results = await import_directory(
        session, directory,
        tax_year=tax_year,
        claude_fallback=claude_fallback,
    )
    # Kick off background recompute
    if any(r.get("status") == "completed" for r in results):
        background_tasks.add_task(_run_post_import_background, tax_year)
    return {
        "total": len(results),
        "completed": sum(1 for r in results if r.get("status") == "completed"),
        "duplicate": sum(1 for r in results if r.get("status") == "duplicate"),
        "error": sum(1 for r in results if r.get("status") == "error"),
        "results": results,
    }


@router.post("/categorize", tags=["import"])
async def run_categorization(
    year: Optional[int] = None,
    month: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
):
    """Manually trigger AI categorization for uncategorized transactions."""
    from pipeline.ai.categorizer import categorize_transactions
    result = await categorize_transactions(session, year=year, month=month)
    return result


@router.get("/amazon-reconcile/status")
async def amazon_reconcile_status(
    year: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
):
    """Get Amazon order/transaction match rates and unmatched counts."""
    from sqlalchemy import func, select
    from pipeline.db.schema import Transaction
    from pipeline.db.schema_extended import AmazonOrder
    from pipeline.importers.amazon import _amazon_description_filter

    filters = [AmazonOrder.is_refund.is_(False)]
    tx_filters: list = []
    if year:
        from datetime import datetime as dt
        y_start, y_end = dt(year, 1, 1), dt(year + 1, 1, 1)
        filters.append(AmazonOrder.order_date >= y_start)
        filters.append(AmazonOrder.order_date < y_end)
        tx_filters.append(Transaction.date >= y_start)
        tx_filters.append(Transaction.date < y_end)

    total_orders = (await session.execute(
        select(func.count(AmazonOrder.id)).where(*filters)
    )).scalar() or 0

    matched_orders = (await session.execute(
        select(func.count(AmazonOrder.id)).where(
            AmazonOrder.matched_transaction_id.isnot(None), *filters
        )
    )).scalar() or 0

    total_amazon_txns = (await session.execute(
        select(func.count(Transaction.id)).where(
            _amazon_description_filter(), *tx_filters
        )
    )).scalar() or 0

    matched_tx_ids = select(AmazonOrder.matched_transaction_id).where(
        AmazonOrder.matched_transaction_id.isnot(None)
    ).subquery()
    unmatched_txns = (await session.execute(
        select(func.count(Transaction.id)).where(
            _amazon_description_filter(),
            Transaction.id.notin_(matched_tx_ids),
            *tx_filters,
        )
    )).scalar() or 0

    match_rate = round(matched_orders / total_orders * 100, 1) if total_orders > 0 else 0

    return {
        "total_amazon_orders": total_orders,
        "matched_orders": matched_orders,
        "unmatched_orders": total_orders - matched_orders,
        "total_amazon_transactions": total_amazon_txns,
        "unmatched_transactions": unmatched_txns,
        "match_rate_pct": match_rate,
        "quality": "good" if match_rate >= 90 else "needs_attention" if match_rate >= 70 else "poor",
    }


@router.post("/amazon-reconcile")
async def amazon_reconcile(
    fix_categories: bool = False,
    year: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
):
    """Run Amazon order ↔ CC transaction matching, optionally push categories."""
    from pipeline.importers.amazon import auto_match_amazon_orders
    match_result = await auto_match_amazon_orders(session, propagate_categories=fix_categories)
    logger.info(f"Amazon reconciliation: {match_result}")
    return match_result
