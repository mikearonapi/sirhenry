"""
CSV parser for credit card statements and Monarch Money exports.
Auto-detects card issuer (or Monarch) from column headers and normalizes
to a common schema.  Returns a list of dicts ready for bulk_create_transactions.
"""
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

from pipeline.utils import to_float as _to_float

logger = logging.getLogger(__name__)


@dataclass
class MonarchTransaction:
    """One row from a Monarch Money CSV export."""
    date: datetime
    merchant: str
    category: str
    account_name: str
    original_statement: str
    notes: str
    amount: float
    owner: str = ""
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Issuer profiles — map issuer name → column aliases
# ---------------------------------------------------------------------------

ISSUER_PROFILES: dict[str, dict] = {
    "chase": {
        "detect_cols": {"Transaction Date", "Post Date", "Description", "Amount"},
        "date_col": "Transaction Date",
        "description_col": "Description",
        "amount_col": "Amount",
        "amount_sign": "native",  # Chase: negative = debit, positive = credit
    },
    "amex": {
        "detect_cols": {"Date", "Description", "Amount"},
        "max_cols": 4,
        "date_col": "Date",
        "description_col": "Description",
        "amount_col": "Amount",
        "amount_sign": "flip",   # Amex: positive = debit, negative = credit
    },
    "capital_one": {
        "detect_cols": {"Transaction Date", "Posted Date", "Card No.", "Description", "Debit", "Credit"},
        "date_col": "Transaction Date",
        "description_col": "Description",
        "debit_col": "Debit",
        "credit_col": "Credit",
        "amount_sign": "debit_credit",
    },
    "citi": {
        "detect_cols": {"Date", "Description", "Debit", "Credit"},
        "date_col": "Date",
        "description_col": "Description",
        "debit_col": "Debit",
        "credit_col": "Credit",
        "amount_sign": "debit_credit",
    },
    "bank_of_america": {
        "detect_cols": {"Posted Date", "Reference Number", "Payee", "Address", "Amount"},
        "date_col": "Posted Date",
        "description_col": "Payee",
        "amount_col": "Amount",
        "amount_sign": "flip",
    },
    "discover": {
        "detect_cols": {"Trans. Date", "Post Date", "Description", "Amount", "Category"},
        "date_col": "Trans. Date",
        "description_col": "Description",
        "amount_col": "Amount",
        "amount_sign": "flip",
    },
}


def _detect_issuer(columns: set[str]) -> Optional[str]:
    """Return issuer name whose detect_cols are a subset of the CSV columns."""
    for issuer, profile in ISSUER_PROFILES.items():
        if not profile["detect_cols"].issubset(columns):
            continue
        if "max_cols" in profile and len(columns) > profile["max_cols"]:
            continue
        return issuer
    return None


def _parse_amount(row: pd.Series, profile: dict) -> float:
    sign_mode = profile["amount_sign"]
    if sign_mode == "debit_credit":
        debit = row.get(profile.get("debit_col", ""), "")
        credit = row.get(profile.get("credit_col", ""), "")
        debit_val = _to_float(debit)
        credit_val = _to_float(credit)
        # debit = money out (negative), credit = money in (positive)
        return credit_val - debit_val
    else:
        raw = row[profile["amount_col"]]
        val = _to_float(raw)
        if sign_mode == "flip":
            return -val
        return val  # native


def _transaction_hash(date: datetime, description: str, amount: float, seq: int = 0) -> str:
    key = f"{date.date()}|{description.strip().lower()}|{amount:.2f}|{seq}"
    return hashlib.sha256(key.encode()).hexdigest()


def parse_credit_card_csv(
    filepath: str,
    account_id: int,
    document_id: int,
    default_segment: str = "personal",
) -> list[dict]:
    """
    Parse a credit card CSV file and return a list of transaction dicts
    ready to be passed to bulk_create_transactions.

    Raises ValueError if the CSV format cannot be detected.
    """
    try:
        df = pd.read_csv(filepath, dtype=str, skip_blank_lines=True)
    except Exception as e:
        raise ValueError(f"Cannot read CSV file: {e}") from e

    # Normalize column names: strip whitespace
    df.columns = [c.strip() for c in df.columns]
    col_set = set(df.columns)

    issuer = _detect_issuer(col_set)
    if issuer is None:
        raise ValueError(
            f"Unknown CSV format. Columns found: {sorted(col_set)}. "
            "Supported issuers: Chase, Amex, Capital One, Citi, Bank of America, Discover."
        )

    logger.info(f"Detected issuer: {issuer} in {filepath}")
    profile = ISSUER_PROFILES[issuer]

    rows: list[dict] = []
    seen_hashes: dict[str, int] = {}
    skipped = 0
    for _, row in df.iterrows():
        raw_date = row.get(profile["date_col"], "")
        raw_desc = row.get(profile["description_col"], "")
        if pd.isna(raw_date) or pd.isna(raw_desc) or str(raw_date).strip() == "":
            skipped += 1
            continue

        try:
            tx_date = pd.to_datetime(str(raw_date).strip(), format="mixed").to_pydatetime()
        except Exception:
            skipped += 1
            logger.warning(f"Could not parse date '{raw_date}', skipping row.")
            continue

        description = str(raw_desc).strip()
        amount = _parse_amount(row, profile)

        # Handle duplicate hashes (e.g. two identical Starbucks charges on same day)
        base_hash = _transaction_hash(tx_date, description, amount, seq=0)
        seq = seen_hashes.get(base_hash, 0)
        tx_hash = _transaction_hash(tx_date, description, amount, seq=seq)
        seen_hashes[base_hash] = seq + 1

        rows.append({
            "account_id": account_id,
            "source_document_id": document_id,
            "date": tx_date,
            "description": description,
            "amount": amount,
            "currency": "USD",
            "segment": default_segment,
            "period_month": tx_date.month,
            "period_year": tx_date.year,
            "transaction_hash": tx_hash,
            "effective_segment": default_segment,
            "data_source": "csv",
        })

    logger.info(f"Parsed {len(rows)} transactions, skipped {skipped} rows.")
    return rows


# ---------------------------------------------------------------------------
# Monarch Money CSV
# ---------------------------------------------------------------------------

MONARCH_REQUIRED_COLS = {"Date", "Merchant", "Category", "Account", "Amount"}


def is_monarch_csv(filepath: str) -> bool:
    """Return True if the CSV has Monarch Money column headers."""
    try:
        df = pd.read_csv(filepath, dtype=str, nrows=0, skip_blank_lines=True)
        cols = {c.strip() for c in df.columns}
        return MONARCH_REQUIRED_COLS.issubset(cols)
    except Exception:
        return False


def parse_monarch_csv(filepath: str) -> list[MonarchTransaction]:
    """
    Parse a Monarch Money export CSV into MonarchTransaction objects.
    Does NOT assign account_id or document_id — the importer handles that
    because a single Monarch file spans multiple accounts.
    """
    try:
        df = pd.read_csv(filepath, dtype=str, skip_blank_lines=True)
    except Exception as e:
        raise ValueError(f"Cannot read Monarch CSV: {e}") from e

    df.columns = [c.strip() for c in df.columns]

    transactions: list[MonarchTransaction] = []
    skipped = 0

    for _, row in df.iterrows():
        raw_date = row.get("Date", "")
        merchant = str(row.get("Merchant", "")).strip()

        if pd.isna(raw_date) or str(raw_date).strip() == "":
            skipped += 1
            continue

        try:
            tx_date = pd.to_datetime(str(raw_date).strip(), format="mixed").to_pydatetime()
        except Exception:
            skipped += 1
            logger.warning(f"Could not parse Monarch date '{raw_date}', skipping row.")
            continue

        amount = _to_float(row.get("Amount", "0"))
        category = str(row.get("Category", "")).strip()
        account_name = str(row.get("Account", "")).strip()
        original_statement = str(row.get("Original Statement", "")).strip()
        notes = str(row.get("Notes", "")).strip()
        if notes.lower() == "nan":
            notes = ""
        if original_statement.lower() == "nan":
            original_statement = ""
        if category.lower() == "nan":
            category = ""

        raw_tags = str(row.get("Tags", "")).strip()
        tags = [t.strip() for t in raw_tags.split(",") if t.strip() and t.strip().lower() != "nan"]

        owner = str(row.get("Owner", "")).strip()
        if owner.lower() == "nan":
            owner = ""

        transactions.append(MonarchTransaction(
            date=tx_date,
            merchant=merchant,
            category=category,
            account_name=account_name,
            original_statement=original_statement,
            notes=notes,
            amount=amount,
            owner=owner,
            tags=tags,
        ))

    logger.info(f"Parsed {len(transactions)} Monarch transactions, skipped {skipped} rows.")
    return transactions


# ---------------------------------------------------------------------------
# Investment / Brokerage CSV
# ---------------------------------------------------------------------------

BROKERAGE_PROFILES: dict[str, dict] = {
    "fidelity": {
        "detect_cols": {"Run Date", "Action", "Symbol", "Quantity", "Price", "Amount"},
        "date_col": "Run Date",
        "action_col": "Action",
        "symbol_col": "Symbol",
        "quantity_col": "Quantity",
        "price_col": "Price",
        "amount_col": "Amount",
    },
    "schwab": {
        "detect_cols": {"Date", "Action", "Symbol", "Quantity", "Price", "Amount"},
        "date_col": "Date",
        "action_col": "Action",
        "symbol_col": "Symbol",
        "quantity_col": "Quantity",
        "price_col": "Price",
        "amount_col": "Amount",
    },
}

_INVESTMENT_ACTION_MAP: dict[str, str] = {
    "buy": "Buy",
    "bought": "Buy",
    "purchase": "Buy",
    "sell": "Sell",
    "sold": "Sell",
    "dividend": "Dividend",
    "div": "Dividend",
    "reinvest dividend": "Dividend",
    "interest": "Interest",
    "transfer": "Transfer",
    "journal": "Transfer",
    "contribution": "Transfer",
    "distribution": "Transfer",
}


def _detect_brokerage(columns: set[str]) -> tuple[str | None, dict | None]:
    for name, profile in BROKERAGE_PROFILES.items():
        if profile["detect_cols"].issubset(columns):
            return name, profile
    # Generic fallback: needs at least Date and (Amount or Value)
    if "Date" in columns and (columns & {"Amount", "Value"}):
        amount_col = "Amount" if "Amount" in columns else "Value"
        return "generic", {
            "date_col": "Date",
            "action_col": next((c for c in ("Action", "Type", "Transaction Type") if c in columns), None),
            "symbol_col": next((c for c in ("Symbol", "Security", "Ticker") if c in columns), None),
            "quantity_col": next((c for c in ("Quantity", "Shares", "Qty") if c in columns), None),
            "price_col": next((c for c in ("Price",) if c in columns), None),
            "amount_col": amount_col,
        }
    return None, None


def _normalize_action(raw: str) -> str:
    return _INVESTMENT_ACTION_MAP.get(raw.strip().lower(), raw.strip())


def parse_investment_csv(
    filepath: str,
    account_id: int,
    document_id: int,
    default_segment: str = "investment",
) -> list[dict]:
    """
    Parse a brokerage / investment CSV file and return a list of transaction
    dicts ready to be passed to bulk_create_transactions.

    Raises ValueError if the CSV format cannot be detected.
    """
    try:
        df = pd.read_csv(filepath, dtype=str, skip_blank_lines=True)
    except Exception as e:
        raise ValueError(f"Cannot read CSV file: {e}") from e

    df.columns = [c.strip() for c in df.columns]
    col_set = set(df.columns)

    broker, profile = _detect_brokerage(col_set)
    if broker is None or profile is None:
        raise ValueError(
            f"Unknown investment CSV format. Columns found: {sorted(col_set)}. "
            "Supported brokerage formats: Fidelity, Schwab, Vanguard, E*Trade (or generic with Date + Amount/Value)."
        )

    logger.info(f"Detected brokerage format: {broker} in {filepath}")

    rows: list[dict] = []
    seen_hashes: dict[str, int] = {}
    skipped = 0

    for _, row in df.iterrows():
        raw_date = row.get(profile["date_col"], "")
        if pd.isna(raw_date) or str(raw_date).strip() == "":
            skipped += 1
            continue

        try:
            tx_date = pd.to_datetime(str(raw_date).strip(), format="mixed").to_pydatetime()
        except Exception:
            skipped += 1
            logger.warning(f"Could not parse date '{raw_date}', skipping row.")
            continue

        raw_amount = row.get(profile["amount_col"], "0")
        amount = _to_float(raw_amount) if not pd.isna(raw_amount) else 0.0

        action_col = profile.get("action_col")
        raw_action = str(row.get(action_col, "")) if action_col else ""
        action = _normalize_action(raw_action) if raw_action and raw_action.lower() != "nan" else ""

        symbol_col = profile.get("symbol_col")
        symbol = str(row.get(symbol_col, "")).strip() if symbol_col else ""
        if symbol.lower() == "nan":
            symbol = ""

        description = f"{action} {symbol}".strip() if (action or symbol) else "Investment transaction"

        base_hash = _transaction_hash(tx_date, description, amount, seq=0)
        seq = seen_hashes.get(base_hash, 0)
        tx_hash = _transaction_hash(tx_date, description, amount, seq=seq)
        seen_hashes[base_hash] = seq + 1

        rows.append({
            "account_id": account_id,
            "source_document_id": document_id,
            "date": tx_date,
            "description": description,
            "amount": amount,
            "currency": "USD",
            "segment": default_segment,
            "period_month": tx_date.month,
            "period_year": tx_date.year,
            "transaction_hash": tx_hash,
            "effective_segment": default_segment,
            "data_source": "csv",
        })

    logger.info(f"Parsed {len(rows)} investment transactions, skipped {skipped} rows.")
    return rows


def monarch_tx_hash(tx: MonarchTransaction, seq: int = 0) -> str:
    """
    Compute transaction hash for a Monarch row.
    Uses Original Statement (the raw card description) when available so that the
    hash matches what a direct credit-card CSV import would produce.  Falls back
    to Merchant if Original Statement is empty.
    """
    desc = tx.original_statement or tx.merchant
    return _transaction_hash(tx.date, desc, tx.amount, seq=seq)
