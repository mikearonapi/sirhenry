"""
Transaction flow type classifier.

Classifies every transaction as one of:
  - expense:  Money out for goods/services
  - income:   Money in (paycheck, dividends, interest, etc.)
  - transfer: Internal money movement (CC payments, account transfers, savings)
  - refund:   Money back from a purchase (positive amount on an expense category)

Used by the migration to backfill, and by the Plaid sync to classify new transactions.
"""

# ---------------------------------------------------------------------------
# Category-based classification
# ---------------------------------------------------------------------------

# Categories that are always transfers (internal money movement)
TRANSFER_CATEGORIES = frozenset({
    "Transfer",
    "Credit Card Payment",
    "Savings",
    "Check",
    "Payment / Refund",
})

# Categories that are always income
INCOME_CATEGORIES = frozenset({
    "Dividend Income",
    "Interest Income",
    "Capital Gain",
    "Board / Director Income",
    "W-2 Wages",
    "1099-NEC / Consulting Income",
    "K-1 / Partnership Income",
    "Rental Income",
    "Trust Income",
})

# Description patterns that indicate income (case-insensitive)
_INCOME_DESC_PATTERNS = (
    "payroll", "paycheck", "des:payroll", "des:payments",
    "direct dep", "ach credit", "irs", "tax refund",
    "dividend", "interest paid",
)

# Description patterns that indicate transfers (case-insensitive)
_TRANSFER_DESC_PATTERNS = (
    "transfer to", "transfer from", "online transfer",
    "ach transfer", "wire transfer", "zelle",
    "venmo", "paypal",  # peer-to-peer are treated as transfers by default
)

# Categories that contain the word "Paycheck" are always income
# regardless of whether they're in INCOME_CATEGORIES
# (handles "Accenture Paycheck", "Vivant Paycheck", etc.)


def classify_flow_type(
    amount: float,
    category: str | None,
    description: str | None = None,
) -> str:
    """Determine the flow type for a transaction.

    Args:
        amount: Transaction amount (negative=debit, positive=credit)
        category: The effective category (or raw category)
        description: Transaction description for pattern matching

    Returns:
        One of: "expense", "income", "transfer", "refund"
    """
    cat = category or ""
    desc = (description or "").lower()

    # 1. Transfer categories — always transfers regardless of amount sign
    if cat in TRANSFER_CATEGORIES:
        return "transfer"

    # 2. Known income categories
    if cat in INCOME_CATEGORIES:
        return "income"

    # 3. Category name contains "Paycheck" or "Trust" → income
    cat_lower = cat.lower()
    if "paycheck" in cat_lower or "trust" in cat_lower:
        return "income"

    # 4. Category is "Other Income" — usually income (tax refunds, rewards, etc.)
    if cat_lower == "other income":
        return "income"

    # 5. Category contains "Discretionary" — inter-account allocation (transfer)
    if "discretionary" in cat_lower:
        return "transfer"

    # 6. Category contains savings/goal keywords — transfer to savings
    savings_keywords = ("fund", "college", "wedding", "investment", "savings", "529")
    if any(kw in cat_lower for kw in savings_keywords):
        return "transfer"

    # 7. Category is explicitly an expense reimbursement
    if "expenses" in cat_lower or "reimburs" in cat_lower:
        return "income"  # money coming back in

    # 8. Amount-based classification for remaining categories
    if amount > 0:
        # Positive amount on a non-income category = refund
        # (e.g., Amazon refund, grocery store return)
        #
        # Check description patterns for income first
        for pattern in _INCOME_DESC_PATTERNS:
            if pattern in desc:
                return "income"
        # Check description patterns for transfers
        for pattern in _TRANSFER_DESC_PATTERNS:
            if pattern in desc:
                return "transfer"
        return "refund"

    # 9. Negative amount on a non-transfer, non-income category = expense
    # But check for transfer descriptions (e.g., "Transfer to Ally Bank")
    for pattern in _TRANSFER_DESC_PATTERNS:
        if pattern in desc:
            return "transfer"

    return "expense"
