"""
Tax document PDF importer (W-2, 1099-NEC, 1099-DIV, 1099-B, 1099-INT).
Extracts structured fields via heuristics + Claude fallback, writes to tax_items.

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
from pipeline.parsers.pdf_parser import (
    detect_form_type,
    extract_1099_div_fields,
    extract_1099_int_fields,
    extract_1099_nec_fields,
    extract_pdf,
    extract_w2_fields,
)
from pipeline.utils import file_hash, create_engine_and_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DIR = Path("data/processed/tax-documents")


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
    Returns a result summary dict.
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

    form_type = detect_form_type(pdf_doc)
    resolved_year = tax_year or _infer_tax_year(filepath, pdf_doc.full_text)

    doc = await create_document(session, {
        "filename": path.name,
        "original_path": str(path.resolve()),
        "file_type": "pdf",
        "document_type": form_type,
        "status": "processing",
        "file_hash": fhash,
        "file_size_bytes": path.stat().st_size,
        "tax_year": resolved_year,
        "raw_text": pdf_doc.full_text[:50000],  # store first 50k chars
    })

    # Extract form fields
    extracted: dict = {}
    try:
        if form_type == "w2":
            extracted = extract_w2_fields(pdf_doc)
        elif form_type == "1099_nec":
            extracted = extract_1099_nec_fields(pdf_doc)
        elif form_type == "1099_div":
            extracted = extract_1099_div_fields(pdf_doc)
        elif form_type == "1099_int":
            extracted = extract_1099_int_fields(pdf_doc)
        # For 1099_b and brokerage_statement, Claude handles extraction
    except Exception as e:
        logger.warning(f"Heuristic extraction failed for {path.name}: {e}")

    # Claude fallback for complex/missing fields
    if claude_fallback and _needs_claude_fallback(form_type, extracted):
        try:
            from pipeline.ai.categorizer import extract_tax_fields_with_claude
            claude_fields = await extract_tax_fields_with_claude(
                form_type=form_type,
                text=pdf_doc.full_text[:8000],
                tax_year=resolved_year,
            )
            # Merge: only fill missing fields from Claude
            for k, v in claude_fields.items():
                if k not in extracted or extracted[k] is None:
                    extracted[k] = v
        except Exception as e:
            logger.warning(f"Claude fallback failed for {path.name}: {e}")

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
        logger.warning(
            f"Duplicate tax item skipped: {form_type} {resolved_year} "
            f"payer={payer_ein or payer_name} (existing id={existing_item})"
        )
    else:
        await create_tax_item(session, {
            "source_document_id": doc.id,
            "tax_year": resolved_year,
            "form_type": form_type,
            "raw_fields": json.dumps(extracted),
            **{k: v for k, v in extracted.items() if not k.startswith("_")},
        })

    # Compute archive path (actual copy deferred until after transaction commits)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dest = PROCESSED_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{path.name}"

    await update_document_status(session, doc.id, "completed", processed_path=str(dest))

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


def _needs_claude_fallback(form_type: str, extracted: dict) -> bool:
    """Return True if key fields are missing and Claude should try."""
    if form_type == "w2":
        return extracted.get("w2_wages") is None
    if form_type == "1099_nec":
        return extracted.get("nec_nonemployee_compensation") is None
    if form_type == "1099_div":
        return extracted.get("div_total_ordinary") is None
    if form_type == "1099_int":
        return extracted.get("int_interest") is None
    if form_type in ("1099_b", "brokerage_statement", "other"):
        return True
    return False


async def import_directory(session: AsyncSession, directory: str, **kwargs) -> list[dict]:
    results = []
    for pdf_file in sorted(Path(directory).glob("*.pdf")):
        result = await import_pdf_file(session, str(pdf_file), **kwargs)
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

        # Archive files after successful commit
        for r in all_results:
            src, dst = r.pop("_archive_src", None), r.pop("_archive_dest", None)
            if src and dst:
                shutil.copy2(src, dst)

        if args.file:
            print(json.dumps(all_results[0], indent=2))
        else:
            print(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
