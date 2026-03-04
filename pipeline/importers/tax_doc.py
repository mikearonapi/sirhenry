"""
Tax document PDF/image importer.
Sends documents to Claude AI for form type detection and field extraction.

Usage:
    python -m pipeline.importers.tax_doc --file "data/imports/tax-documents/w2_accenture_2025.pdf"
    python -m pipeline.importers.tax_doc --dir "data/imports/tax-documents/"
"""
import argparse
import asyncio
import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select as sa_select

from pipeline.db import (
    create_document,
    create_tax_item,
    get_document_by_hash,
    update_document_status,
)
from pipeline.db.schema import TaxItem
from pipeline.parsers.pdf_parser import extract_pdf, extract_pdf_page_images, is_text_sparse
from pipeline.utils import file_hash, create_engine_and_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DIR = Path("data/processed/tax-documents")

# Valid TaxItem column names — used to filter Claude output
_TAXITEM_COLUMNS = {
    "source_document_id", "tax_year", "form_type",
    "payer_name", "payer_ein",
    # W-2
    "w2_wages", "w2_federal_tax_withheld", "w2_ss_wages", "w2_ss_tax_withheld",
    "w2_medicare_wages", "w2_medicare_tax_withheld", "w2_state", "w2_state_wages",
    "w2_state_income_tax", "w2_state_allocations",
    # 1099-NEC
    "nec_nonemployee_compensation", "nec_federal_tax_withheld",
    # 1099-DIV
    "div_total_ordinary", "div_qualified", "div_total_capital_gain", "div_federal_tax_withheld",
    # 1099-B
    "b_proceeds", "b_cost_basis", "b_gain_loss", "b_term", "b_wash_sale_loss",
    # 1099-INT
    "int_interest", "int_federal_tax_withheld",
    # K-1
    "k1_ordinary_income", "k1_rental_income", "k1_other_rental_income",
    "k1_guaranteed_payments", "k1_interest_income", "k1_dividends",
    "k1_qualified_dividends", "k1_short_term_capital_gain", "k1_long_term_capital_gain",
    "k1_section_179", "k1_distributions",
    # 1099-R
    "r_gross_distribution", "r_taxable_amount", "r_federal_tax_withheld",
    "r_distribution_code", "r_state_tax_withheld", "r_state",
    # 1099-G
    "g_unemployment_compensation", "g_state_tax_refund",
    "g_federal_tax_withheld", "g_state",
    # 1099-K
    "k_gross_amount", "k_federal_tax_withheld", "k_state",
    # 1098
    "m_mortgage_interest", "m_points_paid", "m_property_tax",
    # raw catch-all
    "raw_fields",
}


def _infer_tax_year(filepath: str, text: str) -> int:
    """Try to extract tax year from filename or document text."""
    # Check filename first
    year_match = re.search(r"(20\d{2})", Path(filepath).name)
    if year_match:
        return int(year_match.group(1))
    # Check document text
    text_match = re.search(r"tax\s+year\s+(20\d{2})|for\s+calendar\s+year\s+(20\d{2})|(20\d{2})\s+w-2", text, re.IGNORECASE)
    if text_match:
        year_str = next(g for g in text_match.groups() if g)
        return int(year_str)
    # Default to previous year (most documents are for prior year)
    return datetime.now(timezone.utc).year - 1


async def import_pdf_file(
    session: AsyncSession,
    filepath: str,
    tax_year: int | None = None,
    claude_fallback: bool = True,
) -> dict:
    """
    Import a single tax document PDF.
    Claude auto-detects form type and extracts all fields.
    """
    path = Path(filepath)
    if not path.exists():
        return {"status": "error", "message": f"File not found: {filepath}"}

    fhash = file_hash(filepath)
    existing = await get_document_by_hash(session, fhash)
    if existing:
        return {
            "status": "duplicate",
            "message": f"Already imported as document #{existing.id}",
            "document_id": existing.id,
        }

    # Extract PDF text
    try:
        pdf_doc = extract_pdf(filepath)
    except Exception as e:
        return {"status": "error", "message": f"PDF extraction failed: {e}"}

    resolved_year = tax_year or _infer_tax_year(filepath, pdf_doc.full_text)

    doc = await create_document(session, {
        "filename": path.name,
        "original_path": str(path.resolve()),
        "file_type": "pdf",
        "document_type": "processing",
        "status": "processing",
        "file_hash": fhash,
        "file_size_bytes": path.stat().st_size,
        "tax_year": resolved_year,
        "raw_text": pdf_doc.full_text[:50000],
    })

    # Send to Claude for form type detection + field extraction
    extracted: dict = {}
    form_type = "other"

    if claude_fallback:
        try:
            from pipeline.ai.categorizer import extract_tax_fields_with_claude
            # Use vision for scanned/image PDFs with sparse text
            page_images = None
            if is_text_sparse(pdf_doc):
                try:
                    page_images = extract_pdf_page_images(filepath, max_pages=3)
                    logger.info(f"Vision mode for {path.name} (scanned PDF)")
                except Exception as img_err:
                    logger.warning(f"Image render failed for {path.name}: {img_err}")

            extracted = await extract_tax_fields_with_claude(
                text=pdf_doc.full_text[:8000],
                tax_year=resolved_year,
                images=page_images,
            )

            # Use Claude's detected form type
            form_type = extracted.pop("_form_type", "other")
            _VALID_FORM_TYPES = {"w2", "1099_nec", "1099_div", "1099_b", "1099_int",
                                 "1099_r", "1099_g", "1099_k", "k1", "1098", "schedule_h", "other"}
            if form_type not in _VALID_FORM_TYPES:
                form_type = "other"

        except Exception as e:
            logger.warning(f"Claude extraction failed for {path.name}: {e}")

    # JSON-serialize any list/dict values (e.g. w2_state_allocations)
    for k, v in list(extracted.items()):
        if isinstance(v, (list, dict)):
            extracted[k] = json.dumps(v)

    # Dedup: skip if a TaxItem already exists with same form_type + tax_year + payer
    dedup_q = sa_select(TaxItem.id).where(
        TaxItem.form_type == form_type,
        TaxItem.tax_year == resolved_year,
    )
    payer_ein = extracted.get("payer_ein")
    payer_name = extracted.get("payer_name")
    if payer_ein:
        dedup_q = dedup_q.where(TaxItem.payer_ein == payer_ein)
    elif payer_name:
        dedup_q = dedup_q.where(TaxItem.payer_name == payer_name)
    existing_item = (await session.execute(dedup_q.limit(1))).scalar_one_or_none()
    if existing_item:
        logger.info(f"Dedup skip: {form_type} {resolved_year} payer={payer_ein or payer_name}")
    else:
        await create_tax_item(session, {
            "source_document_id": doc.id,
            "tax_year": resolved_year,
            "form_type": form_type,
            "raw_fields": json.dumps(extracted),
            **{k: v for k, v in extracted.items() if k in _TAXITEM_COLUMNS},
        })

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dest = PROCESSED_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{path.name}"
    await update_document_status(session, doc.id, "completed", processed_path=str(dest), document_type=form_type)

    # Clear raw_text after successful extraction — data is now in TaxItem fields
    from pipeline.security.file_cleanup import clear_document_raw_text
    await clear_document_raw_text(session, doc.id)

    # Audit log
    try:
        from pipeline.security.audit import log_audit
        fields_count = len([v for v in extracted.values() if v is not None])
        await log_audit(session, "data_import", "tax_document", f"type={form_type},year={resolved_year},fields={fields_count}")
    except Exception:
        pass

    logger.info(f"Imported {form_type} ({resolved_year}) from {path.name}")
    return {
        "status": "completed",
        "document_id": doc.id,
        "filename": path.name,
        "form_type": form_type,
        "tax_year": resolved_year,
        "fields_extracted": len([v for v in extracted.values() if v is not None]),
        "message": f"Imported {form_type} for tax year {resolved_year}.",
        "_archive_src": str(filepath),
        "_archive_dest": str(dest),
    }


async def import_image_file(
    session: AsyncSession,
    filepath: str,
    tax_year: int | None = None,
) -> dict:
    """
    Import a tax document from an image file (JPG/PNG — e.g. phone photo of W-2).
    Uses Claude vision exclusively for extraction.
    """
    path = Path(filepath)
    if not path.exists():
        return {"status": "error", "message": f"File not found: {filepath}"}

    fhash = file_hash(filepath)
    existing = await get_document_by_hash(session, fhash)
    if existing:
        return {
            "status": "duplicate",
            "message": f"Already imported as document #{existing.id}",
            "document_id": existing.id,
        }

    img_bytes = path.read_bytes()
    suffix = path.suffix.lower()
    media_type = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
    resolved_year = tax_year or _infer_tax_year(filepath, "")

    doc = await create_document(session, {
        "filename": path.name,
        "original_path": str(path.resolve()),
        "file_type": "image",
        "document_type": "other",
        "status": "processing",
        "file_hash": fhash,
        "file_size_bytes": path.stat().st_size,
        "tax_year": resolved_year,
    })

    try:
        from pipeline.ai.categorizer import extract_tax_fields_with_claude
        claude_fields = await extract_tax_fields_with_claude(
            text="[Image-only document]",
            tax_year=resolved_year,
            images=[img_bytes],
        )
    except Exception as e:
        await update_document_status(session, doc.id, "failed", error_message=str(e))
        return {"status": "error", "message": f"Vision extraction failed: {e}", "document_id": doc.id}

    # Detect form type from Claude's response
    form_type = claude_fields.pop("_form_type", "other")
    _VALID = {"w2", "1099_nec", "1099_div", "1099_b", "1099_int", "1099_r", "1099_g", "1099_k", "k1", "1098", "schedule_h", "other"}
    if form_type not in _VALID:
        form_type = "other"

    # JSON-serialize any list/dict values
    for k, v in claude_fields.items():
        if isinstance(v, (list, dict)):
            claude_fields[k] = json.dumps(v)

    await create_tax_item(session, {
        "source_document_id": doc.id,
        "tax_year": resolved_year,
        "form_type": form_type,
        "raw_fields": json.dumps(claude_fields),
        **{k: v for k, v in claude_fields.items() if k in _TAXITEM_COLUMNS},
    })

    await update_document_status(session, doc.id, "completed", document_type=form_type)
    logger.info(f"Imported image {form_type} ({resolved_year}) from {path.name}")
    return {
        "status": "completed",
        "document_id": doc.id,
        "filename": path.name,
        "form_type": form_type,
        "tax_year": resolved_year,
        "fields_extracted": len([v for v in claude_fields.values() if v is not None]),
        "message": f"Imported {form_type} for tax year {resolved_year} (via vision).",
    }


async def import_directory(session: AsyncSession, directory: str, **kwargs) -> list[dict]:
    results = []
    dir_path = Path(directory)
    # Process PDFs
    for pdf_file in sorted(dir_path.glob("*.pdf")):
        result = await import_pdf_file(session, str(pdf_file), **kwargs)
        results.append(result)
    # Process images (phone photos of tax docs)
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        for img_file in sorted(dir_path.glob(ext)):
            result = await import_image_file(session, str(img_file), tax_year=kwargs.get("tax_year"))
            results.append(result)
    return results


async def _main():
    parser = argparse.ArgumentParser(description="Import tax document PDFs")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to a single PDF file")
    group.add_argument("--dir", help="Directory of PDF files to import")
    parser.add_argument("--year", type=int, help="Override tax year")
    parser.add_argument("--no-claude", action="store_true", help="Disable Claude fallback")
    args = parser.parse_args()

    engine, Session = create_engine_and_session()
    from pipeline.db import init_db
    await init_db(engine)

    async with Session() as session:
        async with session.begin():
            if args.file:
                all_results = [await import_pdf_file(
                    session, args.file,
                    tax_year=args.year,
                    claude_fallback=not args.no_claude,
                )]
            else:
                all_results = await import_directory(
                    session, args.dir,
                    tax_year=args.year,
                    claude_fallback=not args.no_claude,
                )

        # Archive files after successful commit, then securely delete source
        from pipeline.security.file_cleanup import secure_delete_file
        for r in all_results:
            src, dst = r.pop("_archive_src", None), r.pop("_archive_dest", None)
            if src and dst:
                shutil.copy2(src, dst)
                secure_delete_file(src)

        if args.file:
            print(json.dumps(all_results[0], indent=2))
        else:
            print(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
