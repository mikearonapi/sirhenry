"""
Investment statement importer (brokerage PDFs and CSVs).
Handles: Fidelity, Schwab, Vanguard, E*Trade, TD Ameritrade statement formats.
Extracts 1099-B capital gains, dividend summaries, and income transactions.

Usage:
    python -m pipeline.importers.investment --file "data/imports/investments/fidelity_2025.pdf"
    python -m pipeline.importers.investment --dir "data/imports/investments/"
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

from pipeline.db import (
    bulk_create_transactions,
    create_document,
    create_tax_item,
    create_transaction,
    get_document_by_hash,
    upsert_account,
    update_document_status,
)
from pipeline.parsers.pdf_parser import extract_pdf
from pipeline.utils import file_hash, create_engine_and_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DIR = Path("data/processed/investments")


def _detect_brokerage(text: str) -> str:
    text_lower = text.lower()
    if "fidelity" in text_lower:
        return "Fidelity"
    if "schwab" in text_lower:
        return "Schwab"
    if "vanguard" in text_lower:
        return "Vanguard"
    if "e*trade" in text_lower or "etrade" in text_lower:
        return "E*Trade"
    if "td ameritrade" in text_lower or "tda" in text_lower:
        return "TD Ameritrade"
    if "merrill" in text_lower:
        return "Merrill Lynch"
    return "Unknown Brokerage"


def _extract_1099b_entries(text: str) -> list[dict]:
    """
    Extract capital gain/loss entries from 1099-B text.
    Returns list of {description, proceeds, cost_basis, gain_loss, term}.
    """
    entries = []
    # Pattern: security description, proceeds, cost, gain/loss
    pattern = re.finditer(
        r"([A-Z][A-Z\s/&]{3,40})\s+"
        r"([\d,]+\.\d{2})\s+"
        r"([\d,]+\.\d{2})\s+"
        r"(-?[\d,]+\.\d{2})\s+"
        r"(short|long)",
        text, re.IGNORECASE,
    )
    for m in pattern:
        try:
            entries.append({
                "description": m.group(1).strip(),
                "proceeds": float(m.group(2).replace(",", "")),
                "cost_basis": float(m.group(3).replace(",", "")),
                "gain_loss": float(m.group(4).replace(",", "")),
                "term": m.group(5).lower(),
            })
        except ValueError:
            pass
    return entries


def _extract_dividend_income(text: str) -> float:
    match = re.search(
        r"(?:total\s+dividends?|total\s+ordinary\s+dividends?)[^\n$]*?\$?([\d,]+\.?\d*)",
        text, re.IGNORECASE,
    )
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            pass
    return 0.0


async def import_investment_file(
    session: AsyncSession,
    filepath: str,
    tax_year: int | None = None,
    account_name: str = "Investment Account",
) -> dict:
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

    suffix = path.suffix.lower()
    form_type = "brokerage_statement"

    if suffix == ".pdf":
        try:
            pdf_doc = extract_pdf(filepath)
        except Exception as e:
            return {"status": "error", "message": f"PDF extraction failed: {e}"}
        text = pdf_doc.full_text
        brokerage = _detect_brokerage(text)
    elif suffix == ".csv":
        text = ""
        brokerage = account_name
    else:
        return {"status": "error", "message": f"Unsupported file type: {suffix}"}

    resolved_year = tax_year or (datetime.now(timezone.utc).year - 1)

    # Ensure account
    account = await upsert_account(session, {
        "name": account_name or brokerage,
        "account_type": "investment",
        "subtype": "brokerage",
        "institution": brokerage if suffix == ".pdf" else account_name,
    })

    doc = await create_document(session, {
        "filename": path.name,
        "original_path": str(path.resolve()),
        "file_type": suffix.lstrip("."),
        "document_type": form_type,
        "status": "processing",
        "file_hash": fhash,
        "file_size_bytes": path.stat().st_size,
        "tax_year": resolved_year,
        "account_id": account.id,
        "raw_text": text[:50000] if text else None,
    })

    items_created = 0

    if suffix == ".pdf" and text:
        # Try to extract 1099-B entries
        entries_1099b = _extract_1099b_entries(text)
        for entry in entries_1099b:
            await create_tax_item(session, {
                "source_document_id": doc.id,
                "tax_year": resolved_year,
                "form_type": "1099_b",
                "payer_name": brokerage,
                "b_proceeds": entry["proceeds"],
                "b_cost_basis": entry["cost_basis"],
                "b_gain_loss": entry["gain_loss"],
                "b_term": entry["term"],
                "raw_fields": json.dumps(entry),
            })
            items_created += 1

        # Extract dividend income as a transaction
        total_div = _extract_dividend_income(text)
        if total_div > 0:
            await create_transaction(session, {
                "account_id": account.id,
                "source_document_id": doc.id,
                "date": datetime(resolved_year, 12, 31),
                "description": f"Total Dividends — {brokerage} ({resolved_year})",
                "amount": total_div,
                "segment": "investment",
                "category": "Dividend Income",
                "tax_category": "1099-DIV Box 1a — Total Ordinary Dividends",
                "effective_category": "Dividend Income",
                "effective_segment": "investment",
                "effective_tax_category": "1099-DIV Box 1a — Total Ordinary Dividends",
                "period_year": resolved_year,
                "period_month": 12,
            })
            items_created += 1

        # Claude-assisted extraction for complex statements
        if items_created == 0:
            try:
                from pipeline.ai.categorizer import extract_tax_fields_with_claude
                claude_fields = await extract_tax_fields_with_claude(
                    form_type="brokerage_statement",
                    text=text[:8000],
                    tax_year=resolved_year,
                )
                if claude_fields:
                    await create_tax_item(session, {
                        "source_document_id": doc.id,
                        "tax_year": resolved_year,
                        "form_type": "brokerage_statement",
                        "payer_name": brokerage,
                        "raw_fields": json.dumps(claude_fields),
                    })
                    items_created += 1
            except Exception as e:
                logger.warning(f"Claude extraction failed: {e}")

    elif suffix == ".csv":
        from pipeline.parsers.csv_parser import parse_investment_csv
        try:
            rows = parse_investment_csv(filepath, account.id, doc.id, "investment")
            inserted = await bulk_create_transactions(session, rows)
            items_created = inserted
        except ValueError as e:
            logger.warning(f"CSV parse failed, file may be a summary: {e}")

    # Compute archive path (actual copy deferred until after transaction commits)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dest = PROCESSED_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{path.name}"

    await update_document_status(session, doc.id, "completed", processed_path=str(dest))

    return {
        "status": "completed",
        "document_id": doc.id,
        "filename": path.name,
        "brokerage": brokerage if suffix == ".pdf" else account_name,
        "items_created": items_created,
        "message": f"Imported {items_created} items from {path.name}.",
        "_archive_src": str(filepath),
        "_archive_dest": str(dest),
    }


async def import_directory(session: AsyncSession, directory: str, **kwargs) -> list[dict]:
    results = []
    for f in sorted(Path(directory).iterdir()):
        if f.suffix.lower() in (".pdf", ".csv"):
            result = await import_investment_file(session, str(f), **kwargs)
            results.append(result)
    return results


async def _main():
    parser = argparse.ArgumentParser(description="Import investment statements")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to a single file")
    group.add_argument("--dir", help="Directory of files to import")
    parser.add_argument("--year", type=int, help="Override tax year")
    parser.add_argument("--account-name", default="Investment Account")
    args = parser.parse_args()

    engine, Session = create_engine_and_session()
    from pipeline.db import init_db
    await init_db(engine)

    async with Session() as session:
        async with session.begin():
            if args.file:
                all_results = [await import_investment_file(
                    session, args.file,
                    tax_year=args.year,
                    account_name=args.account_name,
                )]
            else:
                all_results = await import_directory(
                    session, args.dir,
                    tax_year=args.year,
                    account_name=args.account_name,
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
