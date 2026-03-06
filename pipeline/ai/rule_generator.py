"""
Rule Generator — analyzes transactions and proposes category rules.

Two approaches:
1. Pattern-based: finds merchants with consistent categorization across existing data
2. AI-based: sends uncategorized merchant names to Claude for suggestions

Used by the "Generate Rules" feature on the Rules page.
"""
import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.ai.categories import EXPENSE_CATEGORIES, TAX_CATEGORIES
from pipeline.ai.category_rules import apply_rules, normalize_merchant
from pipeline.db.schema import (
    BusinessEntity,
    CategoryRule,
    HouseholdProfile,
    Transaction,
)
from pipeline.utils import CLAUDE_MODEL, call_claude_with_retry, get_claude_client, strip_json_fences

logger = logging.getLogger(__name__)


async def generate_rules_from_patterns(session: AsyncSession) -> list[dict[str, Any]]:
    """Analyze categorized transactions and propose rules for consistent merchants.

    Groups transactions by normalized merchant name. For merchants with ≥2
    transactions and ≥80% category consistency, proposes a rule.
    Skips merchants that already have a CategoryRule.
    """
    # Load existing rule patterns to skip
    existing_result = await session.execute(
        select(CategoryRule.merchant_pattern).where(CategoryRule.is_active.is_(True))
    )
    existing_patterns = {row[0] for row in existing_result}

    # Load entity names for enrichment
    entity_result = await session.execute(select(BusinessEntity.id, BusinessEntity.name))
    entity_names = {row[0]: row[1] for row in entity_result}

    # Get all categorized, non-excluded transactions
    result = await session.execute(
        select(Transaction).where(
            Transaction.effective_category.isnot(None),
            Transaction.is_excluded.is_(False),
            Transaction.is_manually_reviewed.is_(False),
            Transaction.effective_category != "Uncategorized",
            Transaction.effective_category != "Transfer",
        )
    )
    transactions = list(result.scalars().all())

    # Group by normalized merchant
    merchant_groups: dict[str, list[Transaction]] = {}
    for tx in transactions:
        merchant = normalize_merchant(tx.description)
        if not merchant or len(merchant) < 3:
            continue
        if merchant in existing_patterns:
            continue
        merchant_groups.setdefault(merchant, []).append(tx)

    # Find consistent patterns
    proposals: list[dict[str, Any]] = []
    for merchant, txns in merchant_groups.items():
        if len(txns) < 2:
            continue

        # Count category occurrences
        cat_counts: dict[tuple, int] = {}
        for tx in txns:
            key = (
                tx.effective_category,
                tx.effective_tax_category,
                tx.effective_segment,
                tx.business_entity_id,
            )
            cat_counts[key] = cat_counts.get(key, 0) + 1

        best_key, best_count = max(cat_counts.items(), key=lambda x: x[1])
        total = len(txns)
        consistency = best_count / total

        if consistency >= 0.8:
            cat, tax_cat, seg, entity_id = best_key
            proposals.append({
                "merchant": merchant,
                "category": cat,
                "tax_category": tax_cat,
                "segment": seg,
                "entity_id": entity_id,
                "entity_name": entity_names.get(entity_id) if entity_id else None,
                "transaction_count": total,
                "confidence": round(consistency, 2),
                "source": "pattern",
            })

    proposals.sort(key=lambda r: r["transaction_count"], reverse=True)
    return proposals


async def generate_rules_from_ai(
    session: AsyncSession,
    max_merchants: int = 150,
) -> list[dict[str, Any]]:
    """Use Claude to suggest categories for uncategorized merchants.

    Groups uncategorized transactions by normalized merchant name,
    sends unique merchant names (not individual transactions) to Claude.
    Much cheaper than per-transaction categorization.
    """
    # Load existing rule patterns to skip
    existing_result = await session.execute(
        select(CategoryRule.merchant_pattern).where(CategoryRule.is_active.is_(True))
    )
    existing_patterns = {row[0] for row in existing_result}

    # Get uncategorized transactions
    result = await session.execute(
        select(Transaction).where(
            Transaction.effective_category.is_(None),
            Transaction.is_excluded.is_(False),
            Transaction.is_manually_reviewed.is_(False),
        )
    )
    transactions = list(result.scalars().all())

    # Group by normalized merchant
    merchant_groups: dict[str, list[Transaction]] = {}
    for tx in transactions:
        merchant = normalize_merchant(tx.description)
        if not merchant or len(merchant) < 3:
            continue
        if merchant in existing_patterns:
            continue
        merchant_groups.setdefault(merchant, []).append(tx)

    # Filter to merchants with ≥2 transactions, limit total
    merchants_to_categorize = [
        {
            "merchant": merchant,
            "sample_descriptions": list({tx.description for tx in txns[:3]}),
            "avg_amount": round(sum(tx.amount for tx in txns) / len(txns), 2),
            "count": len(txns),
        }
        for merchant, txns in merchant_groups.items()
        if len(txns) >= 2
    ]
    merchants_to_categorize.sort(key=lambda m: m["count"], reverse=True)
    merchants_to_categorize = merchants_to_categorize[:max_merchants]

    if not merchants_to_categorize:
        return []

    # Build entity context
    entities = await session.execute(
        select(BusinessEntity).where(BusinessEntity.is_active.is_(True))
    )
    entity_list = list(entities.scalars().all())
    entity_names = {e.id: e.name for e in entity_list}

    entity_context = ""
    if entity_list:
        lines = []
        for e in entity_list:
            line = f"  - {e.name} (type={e.entity_type}, tax={e.tax_treatment})"
            if e.description:
                line += f" — {e.description}"
            lines.append(line)
        entity_context = "\nBusiness entities:\n" + "\n".join(lines)

    # Build household context
    hh_result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary.is_(True)).limit(1)
    )
    hh = hh_result.scalar_one_or_none()
    household_context = ""
    if hh:
        filing = hh.filing_status or "unknown"
        household_context = f"\nHousehold: {filing.upper()} filing"

    # Build prompt
    merchant_json = json.dumps(
        [{"merchant": m["merchant"], "samples": m["sample_descriptions"],
          "avg_amount": m["avg_amount"], "count": m["count"]}
         for m in merchants_to_categorize],
        indent=2,
    )

    prompt = f"""You are a professional financial categorizer. For each merchant below, suggest the best category and segment.
{household_context}{entity_context}

For each merchant, return a JSON array with one object per merchant:
- "merchant": the merchant name (unchanged)
- "category": best match from category list
- "tax_category": best match from tax category list (or null)
- "segment": "personal", "business", "investment", or "reimbursable"
- "business_entity": name of the business entity (or null if personal)
- "confidence": float 0.0-1.0

Category options: {json.dumps(EXPENSE_CATEGORIES)}
Tax category options: {json.dumps(TAX_CATEGORIES)}

Rules:
1. Negative avg_amount = expense, positive = income/credit
2. Credit card payments and transfers → "Credit Card Payment" / "Transfer", personal
3. Business software/tools → "Business — Software & Subscriptions"
4. If ambiguous, default to personal with lower confidence
5. Return ONLY the JSON array

Merchants:
{merchant_json}"""

    client = get_claude_client()
    try:
        response = call_claude_with_retry(
            client,
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = strip_json_fences(response.content[0].text)
        results: list[dict] = json.loads(raw)
    except Exception as e:
        logger.error(f"AI rule generation failed: {e}")
        return []

    # Map results back
    proposals: list[dict[str, Any]] = []
    merchant_count_map = {m["merchant"]: m["count"] for m in merchants_to_categorize}

    for r in results:
        merchant = r.get("merchant", "")
        if not merchant or merchant not in merchant_count_map:
            continue

        entity_id = None
        entity_name_str = r.get("business_entity")
        if entity_name_str:
            for eid, ename in entity_names.items():
                if ename.lower() == entity_name_str.lower():
                    entity_id = eid
                    break

        proposals.append({
            "merchant": merchant,
            "category": r.get("category"),
            "tax_category": r.get("tax_category"),
            "segment": r.get("segment", "personal"),
            "entity_id": entity_id,
            "entity_name": entity_names.get(entity_id) if entity_id else None,
            "transaction_count": merchant_count_map[merchant],
            "confidence": r.get("confidence", 0.7),
            "source": "ai",
        })

    proposals.sort(key=lambda r: r["transaction_count"], reverse=True)
    return proposals


async def create_rules_from_proposals(
    session: AsyncSession,
    proposals: list[dict[str, Any]],
) -> dict[str, int]:
    """Create CategoryRule records from approved proposals and apply retroactively.

    For merchants with an existing active rule, skips them.
    For merchants with an inactive rule, re-activates and updates them.
    For new merchants, creates a fresh rule.
    Returns counts: rules_created, duplicates_skipped, transactions_categorized.
    """
    # Load ALL existing rules (active and inactive) — unique constraint on merchant_pattern
    existing_result = await session.execute(
        select(CategoryRule).where(
            CategoryRule.merchant_pattern.in_([p.get("merchant", "") for p in proposals])
        )
    )
    existing_rules = {r.merchant_pattern: r for r in existing_result.scalars().all()}

    created = 0
    skipped = 0
    reactivated = 0

    for p in proposals:
        merchant = p.get("merchant", "")
        if not merchant:
            skipped += 1
            continue

        existing = existing_rules.get(merchant)
        if existing and existing.is_active:
            skipped += 1
            continue

        if existing and not existing.is_active:
            # Re-activate and update the existing rule
            existing.is_active = True
            existing.category = p.get("category") or existing.category
            existing.tax_category = p.get("tax_category") or existing.tax_category
            existing.segment = p.get("segment") or existing.segment
            existing.business_entity_id = p.get("entity_id") or existing.business_entity_id
            reactivated += 1
            created += 1
            continue

        rule = CategoryRule(
            merchant_pattern=merchant,
            category=p.get("category"),
            tax_category=p.get("tax_category"),
            segment=p.get("segment"),
            business_entity_id=p.get("entity_id"),
            source="generated",
            match_count=0,
            is_active=True,
        )
        session.add(rule)
        created += 1

    await session.flush()

    # Apply all rules retroactively
    apply_result = await apply_rules(session)
    categorized = apply_result.get("applied", 0)

    return {
        "rules_created": created,
        "duplicates_skipped": skipped,
        "transactions_categorized": categorized,
    }
