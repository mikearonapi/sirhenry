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
from pipeline.db import get_transactions
from pipeline.db.schema import HouseholdProfile
from pipeline.utils import CLAUDE_MODEL, strip_json_fences, get_claude_client, call_claude_with_retry

load_dotenv()
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
            entity_lines.append(
                f"  - {e['name']} | type={e['entity_type']} | tax={e['tax_treatment']} "
                f"| owner={e.get('owner', 'unknown')} | {status}{prov}"
            )
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
    """Build a household context string from DB data — no hardcoded names."""
    result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    household = result.scalar_one_or_none()

    lines: list[str] = []
    if household:
        filing = household.filing_status or "unknown"
        lines.append(f"- Filing status: {filing.upper()}")
        if household.spouse_a_name and household.spouse_a_employer:
            lines.append(
                f"- {household.spouse_a_name}: W-2 income from {household.spouse_a_employer}"
            )
        elif household.spouse_a_name:
            lines.append(f"- Primary earner: {household.spouse_a_name}")
        if household.spouse_b_name and household.spouse_b_employer:
            lines.append(
                f"- {household.spouse_b_name}: income from {household.spouse_b_employer}"
            )
        elif household.spouse_b_name:
            lines.append(f"- Spouse/partner: {household.spouse_b_name}")

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

    entities = await get_all_business_entities(session, include_inactive=True)
    entity_dicts = [
        {
            "name": e.name,
            "entity_type": e.entity_type,
            "tax_treatment": e.tax_treatment,
            "owner": e.owner,
            "is_active": e.is_active,
            "is_provisional": e.is_provisional,
        }
        for e in entities
    ]
    entity_name_to_id = {e.name.lower(): e.id for e in entities}

    household_context = await _build_household_context(session)

    page_size = 500
    max_iterations = 20
    total_categorized = 0
    total_errors = 0
    total_skipped = 0

    for iteration in range(max_iterations):
        transactions = await get_transactions(
            session,
            year=year,
            month=month,
            limit=page_size,
            offset=0,
        )

        uncategorized = [
            t for t in transactions
            if t.effective_category is None and not t.is_manually_reviewed
        ]

        if not uncategorized:
            if iteration == 0:
                logger.info("No uncategorized transactions found.")
            break

        total_skipped += len(transactions) - len(uncategorized)
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
                            eid = entity_name_to_id.get(entity_name.lower())
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

    return {
        "categorized": total_categorized,
        "skipped": total_skipped,
        "errors": total_errors,
    }


async def extract_tax_fields_with_claude(
    form_type: str,
    text: str,
    tax_year: int,
) -> dict[str, Any]:
    """
    Use Claude to extract structured fields from a tax document's text.
    Returns a dict of field name → value.
    Used as fallback when heuristic extraction misses key fields.
    """
    client = get_claude_client()

    field_schema = {
        "w2": {
            "payer_name": "string — employer name",
            "payer_ein": "string — XX-XXXXXXX format",
            "w2_wages": "float — Box 1",
            "w2_federal_tax_withheld": "float — Box 2",
            "w2_ss_wages": "float — Box 3",
            "w2_ss_tax_withheld": "float — Box 4",
            "w2_medicare_wages": "float — Box 5",
            "w2_medicare_tax_withheld": "float — Box 6",
            "w2_state_allocations": "JSON array of {state, wages, tax} for each state in boxes 15-17",
        },
        "1099_nec": {
            "payer_name": "string",
            "payer_ein": "string — XX-XXXXXXX format",
            "nec_nonemployee_compensation": "float — Box 1",
            "nec_federal_tax_withheld": "float — Box 4 (or 0 if blank)",
        },
        "1099_div": {
            "payer_name": "string",
            "div_total_ordinary": "float — Box 1a",
            "div_qualified": "float — Box 1b",
            "div_total_capital_gain": "float — Box 2a",
            "div_federal_tax_withheld": "float — Box 4",
        },
        "1099_b": {
            "payer_name": "string — brokerage name",
            "entries": "array of {description, proceeds, cost_basis, gain_loss, term: short|long}",
        },
        "brokerage_statement": {
            "payer_name": "string — brokerage name",
            "total_dividends": "float",
            "total_interest": "float",
            "realized_gains_short": "float",
            "realized_gains_long": "float",
        },
        "other": {
            "summary": "string — brief description of document contents",
            "amounts": "array of {label, amount}",
        },
    }

    schema = field_schema.get(form_type, field_schema["other"])

    prompt = f"""You are a professional CPA and tax document reader.

Extract the following fields from this {form_type.upper()} tax document for tax year {tax_year}.

Required fields:
{json.dumps(schema, indent=2)}

Return ONLY a JSON object with the field names as keys. Use null for missing fields.
Do NOT include any explanatory text outside the JSON.

Document text:
---
{text[:6000]}
---"""

    response = call_claude_with_retry(
        client,
        model=CLAUDE_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = strip_json_fences(response.content[0].text)

    return json.loads(raw)
