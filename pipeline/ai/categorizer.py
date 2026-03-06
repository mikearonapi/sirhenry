"""
Claude-powered transaction categorizer and tax document field extractor.

Two main functions:
1. categorize_transactions() — batch categorize credit card transactions
2. extract_tax_fields_with_claude() — extract fields from complex PDFs

Claude is called with structured prompts that return JSON.
Results are written back to the transactions table (effective_* fields).
"""
import json
import logging
import os
from typing import Any

import anthropic
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from pipeline.ai.categories import EXPENSE_CATEGORIES, TAX_CATEGORIES
from pipeline.ai.privacy import PIISanitizer, sanitize_entity_list, log_ai_privacy_audit
from pipeline.db import get_transactions
from pipeline.db.schema import HouseholdProfile
from pipeline.utils import CLAUDE_MODEL, strip_json_fences, get_claude_client, call_claude_with_retry

load_dotenv(override=True)
logger = logging.getLogger(__name__)


def _build_categorization_prompt(
    transactions: list[dict],
    context: str = "",
    entities: list[dict] | None = None,
    household_context: str = "",
) -> str:
    tx_list = json.dumps(
        [{"id": t["id"], "date": str(t["date"])[:10], "description": t["description"],
          "amount": t["amount"], "current_segment": t.get("segment", "personal"),
          "current_entity": t.get("business_entity_name")}
         for t in transactions],
        indent=2,
    )

    entity_context = ""
    if entities:
        entity_lines = []
        for e in entities:
            status = "active" if e.get("is_active") else "inactive"
            prov = " (provisional)" if e.get("is_provisional") else ""
            line = (
                f"  - {e['name']} | type={e['entity_type']} | tax={e['tax_treatment']} "
                f"| owner={e.get('owner', 'unknown')} | {status}{prov}"
            )
            if e.get("description"):
                line += f"\n    What it does: {e['description']}"
            if e.get("expected_expenses"):
                line += f"\n    Typical expenses: {e['expected_expenses']}"
            if e.get("assigned_accounts"):
                line += f"\n    Assigned accounts: {', '.join(e['assigned_accounts'])}"
            if e.get("vendor_patterns"):
                patterns = e["vendor_patterns"][:10]  # Limit to avoid prompt bloat
                line += f"\n    Known vendors: {', '.join(patterns)}"
            entity_lines.append(line)
        entity_context = "\nBusiness entities in this household:\n" + "\n".join(entity_lines)

    # household_context is built dynamically from DB — no hardcoded names here
    household_section = f"\nContext about this household:\n{household_context}" if household_context else ""

    return f"""You are a professional financial categorizer and CPA assistant.
{household_section}{entity_context}
{context}

For each transaction below, return a JSON array with one object per transaction.
Each object must have:
- "id": the transaction id (integer, unchanged)
- "category": pick the BEST match from the category list
- "tax_category": pick the BEST match from the tax category list (or null if not applicable)
- "segment": one of "personal", "business", "investment", "reimbursable"
- "business_entity": name of the business entity this expense belongs to (or null if personal/investment)
- "confidence": float 0.0–1.0

Category options: {json.dumps(EXPENSE_CATEGORIES)}

Tax category options: {json.dumps(TAX_CATEGORIES)}

Rules:
1. Positive amounts are income/credits; negative amounts are expenses/debits.
2. Business expenses: meals with clients/colleagues → "Business — Meals (50% deductible)".
3. Airline/hotel on a work trip → "Business — Travel & Transportation".
4. Software subscriptions used for work → "Business — Software & Subscriptions".
5. Personal meals, groceries, personal shopping → "personal" segment.
6. Credit card payments, transfers between accounts → "Transfer", segment "personal".
7. If ambiguous between personal and business, default to "personal" with lower confidence.
8. If a transaction is already tagged "reimbursable", keep it reimbursable.
9. Use the business entity list above to assign transactions to the correct entity.
10. Return ONLY the JSON array, no other text.

Transactions:
{tx_list}"""


async def _build_household_context(session: AsyncSession) -> str:
    """Build a minimal household context for categorization — no names or employers.

    The categorizer only needs filing status to make segment/category decisions.
    Names and employers are PII that Claude doesn't need for transaction categorization.
    """
    result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    household = result.scalar_one_or_none()

    lines: list[str] = []
    if household:
        filing = household.filing_status or "unknown"
        lines.append(f"- Filing status: {filing.upper()}")
        if household.spouse_a_income:
            lines.append("- Primary earner: W-2 employee")
        if household.spouse_b_income:
            lines.append("- Secondary earner: has income")

    return "\n".join(lines) if lines else "- No household profile configured"


async def categorize_transactions(
    session: AsyncSession,
    year: int | None = None,
    month: int | None = None,
    batch_size: int = 50,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Fetch uncategorized (no effective_category) transactions and run Claude categorization.
    Updates effective_category, effective_tax_category, effective_segment, ai_confidence,
    and business_entity_id when Claude identifies one.
    Returns a summary dict.
    """
    client = get_claude_client()

    from pipeline.db import get_all_business_entities, get_business_entity_by_name
    from pipeline.db.schema import Account, VendorEntityRule

    entities = await get_all_business_entities(session, include_inactive=True)

    # Build sanitizer to anonymize entity names for Claude
    sanitizer = PIISanitizer()
    # Load household just for sanitizer registration (names/employers)
    hh_result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    hh = hh_result.scalar_one_or_none()
    sanitizer.register_household(hh, entities)

    # Build enrichment maps for richer categorization context
    acct_result = await session.execute(
        select(Account).where(
            Account.is_active == True,
            Account.default_business_entity_id.isnot(None),
        )
    )
    accounts_map: dict[int, list[str]] = {}
    for acct in acct_result.scalars().all():
        accounts_map.setdefault(acct.default_business_entity_id, []).append(acct.name)

    rules_result = await session.execute(
        select(VendorEntityRule).where(VendorEntityRule.is_active == True)
    )
    rules_map: dict[int, list[str]] = {}
    for rule in rules_result.scalars().all():
        rules_map.setdefault(rule.business_entity_id, []).append(rule.vendor_pattern)

    # Build sanitized entity list for the prompt (with enrichment)
    entity_dicts = sanitize_entity_list(
        entities, sanitizer, accounts_map=accounts_map, rules_map=rules_map,
    )
    # Map: sanitized_name -> entity ID (for mapping Claude's response back)
    sanitized_name_to_id = {
        sanitizer.sanitize_text(e.name).lower(): e.id for e in entities
    }
    # Also keep original name mapping for fallback
    entity_name_to_id = {e.name.lower(): e.id for e in entities}

    household_context = await _build_household_context(session)
    log_ai_privacy_audit("categorize", ["transactions", "entities"], sanitized=True)

    page_size = 500
    max_iterations = 20
    total_categorized = 0
    total_errors = 0
    total_skipped = 0

    from pipeline.db.schema import Transaction as TxModel

    for iteration in range(max_iterations):
        # Query uncategorized transactions directly instead of fetching all
        q = select(TxModel).where(
            TxModel.effective_category.is_(None),
            TxModel.is_manually_reviewed.is_(False),
            TxModel.is_excluded.is_(False),
        )
        if year:
            q = q.where(TxModel.period_year == year)
        if month:
            q = q.where(TxModel.period_month == month)
        q = q.order_by(TxModel.date.desc()).limit(page_size)

        result = await session.execute(q)
        uncategorized = list(result.scalars().all())

        if not uncategorized:
            if iteration == 0:
                logger.info("No uncategorized transactions found.")
            break
        logger.info(
            f"Iteration {iteration + 1}: categorizing {len(uncategorized)} "
            f"transactions in batches of {batch_size}..."
        )

        for i in range(0, len(uncategorized), batch_size):
            batch = uncategorized[i : i + batch_size]
            batch_dicts = [
                {
                    "id": t.id,
                    "date": t.date,
                    "description": t.description,
                    "amount": t.amount,
                    "segment": t.effective_segment or t.segment,
                    "business_entity_name": None,
                }
                for t in batch
            ]

            prompt = _build_categorization_prompt(batch_dicts, entities=entity_dicts, household_context=household_context)

            try:
                response = call_claude_with_retry(
                    client,
                    model=CLAUDE_MODEL,
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = strip_json_fences(response.content[0].text)

                results: list[dict] = json.loads(raw)

                if not dry_run:
                    from sqlalchemy import update as sa_update
                    from pipeline.db.schema import Transaction
                    for r in results:
                        values = {
                            "category": r.get("category"),
                            "tax_category": r.get("tax_category"),
                            "segment": r.get("segment", "personal"),
                            "ai_confidence": r.get("confidence", 0.8),
                            "effective_category": r.get("category"),
                            "effective_tax_category": r.get("tax_category"),
                            "effective_segment": r.get("segment", "personal"),
                        }

                        entity_name = r.get("business_entity")
                        if entity_name:
                            # Try sanitized name first (Claude may return labels), then original
                            eid = sanitized_name_to_id.get(entity_name.lower()) or entity_name_to_id.get(entity_name.lower())
                            if eid:
                                values["business_entity_id"] = eid
                                values["effective_business_entity_id"] = eid

                        await session.execute(
                            sa_update(Transaction)
                            .where(Transaction.id == r["id"])
                            .values(**values)
                        )
                        total_categorized += 1

                logger.info(f"Batch {i // batch_size + 1}: categorized {len(results)} transactions.")

            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error in batch {i // batch_size + 1}: {e}")
                total_errors += len(batch)
            except anthropic.APIError as e:
                logger.error(f"Anthropic API error: {e}")
                total_errors += len(batch)

    # Audit log
    try:
        from pipeline.security.audit import log_audit
        await log_audit(session, "ai_categorize", "transactions", f"count={total_categorized},errors={total_errors}")
    except Exception:
        pass

    return {
        "categorized": total_categorized,
        "skipped": total_skipped,
        "errors": total_errors,
    }


async def extract_tax_fields_with_claude(
    text: str,
    tax_year: int,
    images: list[bytes] | None = None,
    form_type: str | None = None,
) -> dict[str, Any]:
    """
    Use Claude to auto-detect form type AND extract all fields from a tax document.
    Returns a dict with '_form_type' plus all extracted field values.
    Accepts text, images (vision), or both.
    """
    import base64

    client = get_claude_client()

    prompt = f"""You are a professional CPA extracting data from a tax document (tax year {tax_year}).

STEP 1: Identify the document type. Set "_form_type" to one of:
  w2, 1099_nec, 1099_div, 1099_b, 1099_int, 1099_r, 1099_g, 1099_k, k1, 1098, schedule_h, other

STEP 2: Extract ALL relevant fields based on the form type.

For W-2: payer_name, payer_ein, w2_wages (Box 1), w2_federal_tax_withheld (Box 2),
  w2_ss_wages (Box 3), w2_ss_tax_withheld (Box 4), w2_medicare_wages (Box 5),
  w2_medicare_tax_withheld (Box 6), w2_state_allocations (array of {{state, wages, tax}} for EACH state in boxes 15-17)

For 1099-NEC: payer_name, payer_ein, nec_nonemployee_compensation (Box 1), nec_federal_tax_withheld (Box 4)

For 1099-DIV: payer_name, div_total_ordinary (1a), div_qualified (1b), div_total_capital_gain (2a), div_federal_tax_withheld (4)

For 1099-B: payer_name, b_proceeds, b_cost_basis, b_gain_loss, b_term (short or long), b_wash_sale_loss

For 1099-INT: payer_name, int_interest (Box 1), int_federal_tax_withheld (Box 4)

For 1099-R (retirement distributions — pensions, IRAs, 401k):
  payer_name, payer_ein,
  r_gross_distribution (Box 1), r_taxable_amount (Box 2a),
  r_federal_tax_withheld (Box 4), r_distribution_code (Box 7 — e.g. "1","7","G"),
  r_state_tax_withheld (Box 12), r_state (Box 13)

For 1099-G (government payments — unemployment, state tax refunds):
  payer_name, payer_ein,
  g_unemployment_compensation (Box 1), g_state_tax_refund (Box 2),
  g_federal_tax_withheld (Box 4), g_state (Box 10a)

For 1099-K (payment card/third-party network — Stripe, PayPal, Square):
  payer_name, payer_ein,
  k_gross_amount (Box 1a), k_federal_tax_withheld (Box 4), k_state (Box 7)

For 1098 (mortgage interest statement):
  payer_name, payer_ein,
  m_mortgage_interest (Box 1), m_points_paid (Box 6), m_property_tax (Box 10)

For K-1 (Schedule K-1 — partnerships, S-corps, trusts/estates):
  payer_name, payer_ein,
  k1_ordinary_income (Box 1 — ordinary business income or loss),
  k1_rental_income (Box 2 — net rental real estate income/loss),
  k1_other_rental_income (Box 3 — other net rental income/loss),
  k1_guaranteed_payments (Box 4 — guaranteed payments),
  k1_interest_income (Box 5 — interest income),
  k1_dividends (Box 6a — ordinary dividends),
  k1_qualified_dividends (Box 6b — qualified dividends),
  k1_short_term_capital_gain (Box 8 — net short-term capital gain/loss),
  k1_long_term_capital_gain (Box 9a — net long-term capital gain/loss),
  k1_section_179 (Box 12 — section 179 deduction),
  k1_distributions (Box 19 — distributions)

For Schedule H (household employment taxes): payer_name, payer_ein

For all others: payer_name

IMPORTANT:
- Multi-state W-2s: include ALL states in w2_state_allocations array
- Use numeric values (no $ or commas). Use null for missing fields.
- payer_ein format: XX-XXXXXXX
- If a composite statement contains multiple form types (e.g. 1099-DIV + 1099-INT + 1099-B), extract ALL fields from ALL sections

Return ONLY a JSON object. No explanatory text.

Document text:
---
{text[:8000]}
---"""

    content: list[dict[str, Any]] = []
    if images:
        for img_bytes in images:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.b64encode(img_bytes).decode(),
                },
            })
    content.append({"type": "text", "text": prompt})

    response = call_claude_with_retry(
        client,
        model=CLAUDE_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": content}],
    )

    raw = strip_json_fences(response.content[0].text)

    return json.loads(raw)


# ═══════════════════════════════════════════════════════════════════════════
# Document type auto-detection (no AI call — rule-based for speed)
# ═══════════════════════════════════════════════════════════════════════════

def detect_document_type(text: str, filename: str) -> dict:
    """Auto-detect document type from file content and filename.

    Uses pattern matching (no AI call) for instant results.
    Returns {detected_type, confidence, suggested_fields}.
    """
    text_lower = (text or "").lower()
    fname_lower = (filename or "").lower()

    # CSV detection from content
    if fname_lower.endswith(".csv"):
        if any(k in text_lower for k in ["order id", "order date", "items ordered", "shipping address"]):
            return {"detected_type": "amazon", "confidence": 0.95, "suggested_fields": {}}
        if any(k in text_lower for k in ["account", "balance", "original description", "net worth", "monarch"]):
            return {"detected_type": "monarch", "confidence": 0.90, "suggested_fields": {}}
        if any(k in text_lower for k in ["1099-b", "proceeds", "cost basis", "gain/loss", "wash sale"]):
            return {"detected_type": "investment", "confidence": 0.90, "suggested_fields": {}}
        # Default CSV → credit card
        if any(k in text_lower for k in ["transaction", "date", "amount", "description", "debit", "credit", "merchant"]):
            return {"detected_type": "credit_card", "confidence": 0.80, "suggested_fields": {}}

    # PDF/image detection from text content
    if fname_lower.endswith((".pdf", ".jpg", ".jpeg", ".png")):
        # Tax documents
        if any(k in text_lower for k in ["w-2", "wage and tax statement", "w2"]):
            return {"detected_type": "tax_document", "confidence": 0.95, "suggested_fields": {"form_type": "w2"}}
        if any(k in text_lower for k in ["1099-nec", "nonemployee compensation"]):
            return {"detected_type": "tax_document", "confidence": 0.95, "suggested_fields": {"form_type": "1099_nec"}}
        if any(k in text_lower for k in ["1099-div", "dividends and distributions"]):
            return {"detected_type": "tax_document", "confidence": 0.95, "suggested_fields": {"form_type": "1099_div"}}
        if any(k in text_lower for k in ["1099-b", "proceeds from broker"]):
            return {"detected_type": "tax_document", "confidence": 0.95, "suggested_fields": {"form_type": "1099_b"}}
        if any(k in text_lower for k in ["1099-int", "interest income"]):
            return {"detected_type": "tax_document", "confidence": 0.95, "suggested_fields": {"form_type": "1099_int"}}
        if any(k in text_lower for k in ["schedule k-1", "partner's share", "k-1"]):
            return {"detected_type": "tax_document", "confidence": 0.95, "suggested_fields": {"form_type": "k1"}}

        # Insurance
        if any(k in text_lower for k in ["declaration", "policy number", "insurance", "premium", "coverage", "deductible", "underwritten by"]):
            if any(k in text_lower for k in ["auto", "vehicle", "home", "umbrella", "life insurance", "disability", "health plan"]):
                return {"detected_type": "insurance", "confidence": 0.85, "suggested_fields": {}}

        # Pay stub
        if any(k in text_lower for k in ["pay stub", "earnings statement", "pay period", "gross pay", "net pay", "ytd", "federal withholding"]):
            return {"detected_type": "pay_stub", "confidence": 0.90, "suggested_fields": {}}

        # Investment statement
        if any(k in text_lower for k in ["brokerage", "portfolio", "holdings", "account statement", "dividend summary"]):
            return {"detected_type": "investment", "confidence": 0.80, "suggested_fields": {}}

    # Filename-based fallbacks
    if any(k in fname_lower for k in ["w2", "w-2"]):
        return {"detected_type": "tax_document", "confidence": 0.80, "suggested_fields": {"form_type": "w2"}}
    if any(k in fname_lower for k in ["1099"]):
        return {"detected_type": "tax_document", "confidence": 0.80, "suggested_fields": {}}
    if any(k in fname_lower for k in ["paystub", "pay_stub", "earnings", "paycheck"]):
        return {"detected_type": "pay_stub", "confidence": 0.80, "suggested_fields": {}}
    if any(k in fname_lower for k in ["insurance", "policy", "declaration"]):
        return {"detected_type": "insurance", "confidence": 0.75, "suggested_fields": {}}
    if any(k in fname_lower for k in ["amazon", "order"]):
        return {"detected_type": "amazon", "confidence": 0.75, "suggested_fields": {}}

    return {"detected_type": "credit_card", "confidence": 0.50, "suggested_fields": {}}
