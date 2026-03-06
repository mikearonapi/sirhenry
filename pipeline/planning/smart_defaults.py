"""
Smart Defaults Engine — aggregates data from all domain tables into a
unified object that any page can use to auto-fill forms.

Single entry point: compute_smart_defaults(session) -> dict
"""
import json
import logging
from datetime import date, datetime, timezone
from statistics import median

from sqlalchemy import Float as SAFloat
from sqlalchemy import and_, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import (
    Account,
    BenefitPackage,
    Budget,
    BusinessEntity,
    EquityGrant,
    FamilyMember,
    Goal,
    HouseholdProfile,
    InsurancePolicy,
    ManualAsset,
    NetWorthSnapshot,
    PlaidAccount,
    RecurringTransaction,
    TaxItem,
    Transaction,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------

async def compute_smart_defaults(session: AsyncSession) -> dict:
    """Aggregate data from every domain table into a single defaults dict."""
    results = {}

    # Run independent queries in sequence (async sqlite doesn't benefit from gather)
    results["household"] = await _household_defaults(session)
    results["age"] = await _age_defaults(session)
    results["income"] = await _income_defaults(session)
    results["retirement"] = await _retirement_defaults(session)
    results["expenses"] = await _expense_defaults(session)
    results["debts"] = await _debt_defaults(session)
    results["assets"] = await _asset_defaults(session)
    results["net_worth"] = await _net_worth_defaults(session)
    results["recurring"] = await _recurring_defaults(session)
    results["equity"] = await _equity_defaults(session)
    results["tax"] = await _tax_defaults(session)
    results["benefits"] = await _benefits_defaults(session)
    results["goals"] = await _goals_defaults(session)
    results["businesses"] = await _business_defaults(session)
    results["data_sources"] = await _data_source_flags(session)

    return results


# ---------------------------------------------------------------------------
# Household
# ---------------------------------------------------------------------------

async def _household_defaults(session: AsyncSession) -> dict:
    result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary.is_(True)).limit(1)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        result = await session.execute(select(HouseholdProfile).limit(1))
        profile = result.scalar_one_or_none()

    if not profile:
        return {}

    return {
        "id": profile.id,
        "filing_status": profile.filing_status,
        "state": profile.state,
        "spouse_a_name": profile.spouse_a_name,
        "spouse_a_income": profile.spouse_a_income or 0,
        "spouse_a_employer": profile.spouse_a_employer,
        "spouse_b_name": profile.spouse_b_name,
        "spouse_b_income": profile.spouse_b_income or 0,
        "spouse_b_employer": profile.spouse_b_employer,
        "combined_income": profile.combined_income or 0,
        "other_income_annual": profile.other_income_annual or 0,
        "dependents": json.loads(profile.dependents_json) if profile.dependents_json else [],
    }


# ---------------------------------------------------------------------------
# Age (from FamilyMember DOB)
# ---------------------------------------------------------------------------

async def _age_defaults(session: AsyncSession) -> dict:
    result = await session.execute(
        select(FamilyMember)
        .where(FamilyMember.relationship == "self")
        .limit(1)
    )
    member = result.scalar_one_or_none()
    if not member or not member.date_of_birth:
        return {"current_age": None, "date_of_birth": None}

    dob = member.date_of_birth
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return {
        "current_age": age,
        "date_of_birth": dob.isoformat(),
    }


# ---------------------------------------------------------------------------
# Income (from W-2s, household, transactions)
# ---------------------------------------------------------------------------

async def _income_defaults(session: AsyncSession) -> dict:
    current_year = datetime.now(timezone.utc).year

    # W-2 totals for current or most recent year
    for year in [current_year, current_year - 1]:
        w2_result = await session.execute(
            select(
                func.sum(TaxItem.w2_wages),
                func.sum(TaxItem.w2_federal_tax_withheld),
                func.sum(TaxItem.w2_state_income_tax),
            ).where(TaxItem.form_type == "w2", TaxItem.tax_year == year)
        )
        row = w2_result.one()
        if row[0]:
            w2_total = row[0] or 0
            w2_fed_withheld = row[1] or 0
            w2_state_withheld = row[2] or 0
            w2_year = year
            break
    else:
        w2_total = 0
        w2_fed_withheld = 0
        w2_state_withheld = 0
        w2_year = None

    # 1099-NEC totals
    nec_result = await session.execute(
        select(func.sum(TaxItem.nec_nonemployee_compensation))
        .where(TaxItem.form_type == "1099_nec", TaxItem.tax_year == (w2_year or current_year))
    )
    nec_total = nec_result.scalar() or 0

    # Individual W-2 breakdown by employer
    w2_items = await session.execute(
        select(TaxItem.payer_name, TaxItem.w2_wages, TaxItem.w2_federal_tax_withheld)
        .where(TaxItem.form_type == "w2", TaxItem.tax_year == (w2_year or current_year))
        .order_by(TaxItem.w2_wages.desc())
    )
    by_source = [
        {"employer": r[0], "wages": r[1] or 0, "withheld": r[2] or 0}
        for r in w2_items
    ]

    # Household combined income is user-curated base salary — prefer it over
    # W-2 totals which may be inflated by one-time bonuses / retention / RSU
    household = await _household_defaults(session)
    combined = household.get("combined_income", 0) or 0
    # Use household if set, W-2 as fallback
    best_income = combined if combined > 0 else w2_total

    return {
        "w2_total": w2_total,
        "w2_fed_withheld": w2_fed_withheld,
        "w2_state_withheld": w2_state_withheld,
        "w2_year": w2_year,
        "nec_total": nec_total,
        "combined": best_income + nec_total,
        "by_source": by_source,
    }


# ---------------------------------------------------------------------------
# Retirement (from ManualAssets tagged as retirement + BenefitPackage)
# ---------------------------------------------------------------------------

async def _retirement_defaults(session: AsyncSession) -> dict:
    # Retirement account balances
    result = await session.execute(
        select(
            func.sum(ManualAsset.current_value),
            func.max(ManualAsset.employer_match_pct),
            func.max(ManualAsset.contribution_rate_pct),
            func.sum(ManualAsset.employee_contribution_ytd),
        ).where(
            ManualAsset.is_retirement_account.is_(True),
            ManualAsset.is_liability.is_(False),
            ManualAsset.is_active.is_(True),
        )
    )
    row = result.one()
    total_savings = row[0] or 0
    best_match = row[1] or 0
    contribution_rate = row[2] or 0
    ytd_contributions = row[3] or 0

    # Monthly contribution estimate from YTD
    today = date.today()
    months_elapsed = max(today.month, 1)
    monthly_contribution = round(ytd_contributions / months_elapsed, 2) if ytd_contributions else 0

    # W-2 Box 12 Code D (401k) from most recent W-2
    current_year = datetime.now(timezone.utc).year
    w2_401k = 0
    for year in [current_year, current_year - 1]:
        # Check raw_fields for box 12 codes
        w2_result = await session.execute(
            select(TaxItem.raw_fields)
            .where(TaxItem.form_type == "w2", TaxItem.tax_year == year)
        )
        for (raw,) in w2_result:
            if raw:
                try:
                    fields = json.loads(raw) if isinstance(raw, str) else raw
                    box12 = fields.get("box_12", {})
                    if isinstance(box12, dict):
                        w2_401k += box12.get("D", 0) or box12.get("d", 0) or 0
                except (json.JSONDecodeError, AttributeError):
                    pass
        if w2_401k > 0:
            monthly_contribution = round(w2_401k / 12, 2)
            break

    # Benefits package match % as fallback
    benefit_result = await session.execute(
        select(func.max(BenefitPackage.employer_match_pct))
    )
    benefit_match = benefit_result.scalar() or 0
    if benefit_match > best_match:
        best_match = benefit_match

    return {
        "total_savings": total_savings,
        "monthly_contribution": monthly_contribution,
        "annual_contribution": w2_401k if w2_401k else monthly_contribution * 12,
        "employer_match_pct": best_match,
        "contribution_rate_pct": contribution_rate,
    }


# ---------------------------------------------------------------------------
# Expenses (from recent transactions)
# ---------------------------------------------------------------------------

async def _expense_defaults(session: AsyncSession) -> dict:
    today = date.today()
    current_year = today.year
    current_month = today.month

    # Get last 6 months of expense data (all segments + personal-only)
    months_data: list[float] = []
    personal_months_data: list[float] = []
    category_totals: dict[str, list[float]] = {}

    for offset in range(1, 7):
        m = current_month - offset
        y = current_year
        if m <= 0:
            m += 12
            y -= 1

        result = await session.execute(
            select(
                func.sum(case(
                    (Transaction.amount < 0, Transaction.amount * -1),
                    else_=0,
                )).label("expenses"),
            ).where(
                Transaction.period_year == y,
                Transaction.period_month == m,
                Transaction.effective_segment.in_(["personal", "business"]),
                Transaction.is_excluded.is_(False),
            )
        )
        month_total = result.scalar() or 0
        if month_total > 0:
            months_data.append(month_total)

        # Personal-only expenses (for retirement planning)
        personal_result = await session.execute(
            select(
                func.sum(case(
                    (Transaction.amount < 0, Transaction.amount * -1),
                    else_=0,
                )).label("expenses"),
            ).where(
                Transaction.period_year == y,
                Transaction.period_month == m,
                Transaction.effective_segment == "personal",
                Transaction.is_excluded.is_(False),
            )
        )
        personal_total = personal_result.scalar() or 0
        if personal_total > 0:
            personal_months_data.append(personal_total)

        # Category breakdown
        cat_result = await session.execute(
            select(
                Transaction.effective_category,
                func.sum(case(
                    (Transaction.amount < 0, Transaction.amount * -1),
                    else_=0,
                )),
            ).where(
                Transaction.period_year == y,
                Transaction.period_month == m,
                Transaction.effective_segment.in_(["personal", "business"]),
                Transaction.is_excluded.is_(False),
                Transaction.effective_category.isnot(None),
            ).group_by(Transaction.effective_category)
        )
        for cat, amt in cat_result:
            if cat and amt:
                category_totals.setdefault(cat, []).append(amt)

    avg_monthly = round(sum(months_data) / len(months_data), 2) if months_data else 0
    median_monthly = round(median(months_data), 2) if months_data else 0
    personal_avg_monthly = round(sum(personal_months_data) / len(personal_months_data), 2) if personal_months_data else 0

    # Category medians
    by_category = {}
    for cat, amounts in category_totals.items():
        by_category[cat] = round(median(amounts), 2)
    # Sort by value descending
    by_category = dict(sorted(by_category.items(), key=lambda x: x[1], reverse=True))

    return {
        "avg_monthly": avg_monthly,
        "median_monthly": median_monthly,
        "annual_total": round(avg_monthly * 12, 2),
        "personal_annual_total": round(personal_avg_monthly * 12, 2),
        "months_of_data": len(months_data),
        "by_category": by_category,
    }


# ---------------------------------------------------------------------------
# Debts (liabilities from ManualAsset + Plaid)
# ---------------------------------------------------------------------------

async def _debt_defaults(session: AsyncSession) -> list:
    # Retirement-relevant debt types (not revolving credit cards)
    _RETIREMENT_DEBT_TYPES = {"loan", "mortgage", "auto_loan", "student_loan"}

    result = await session.execute(
        select(ManualAsset).where(
            ManualAsset.is_liability.is_(True),
            ManualAsset.is_active.is_(True),
        ).order_by(ManualAsset.current_value.desc())
    )
    debts = []
    for asset in result.scalars():
        atype = (asset.asset_type or "").lower()
        debts.append({
            "name": asset.name,
            "type": asset.asset_type,
            "balance": asset.current_value or 0,
            "institution": asset.institution,
            "retirement_relevant": atype in _RETIREMENT_DEBT_TYPES,
            "monthly_payment": 0,
        })

    # Add Plaid credit card / loan balances
    plaid_result = await session.execute(
        select(PlaidAccount).where(
            PlaidAccount.type.in_(["credit", "loan"])
        )
    )
    for pa in plaid_result.scalars():
        ptype = (pa.subtype or pa.type or "").lower()
        debts.append({
            "name": pa.name or pa.official_name or "Account",
            "type": pa.subtype or pa.type,
            "balance": abs(pa.current_balance or 0),
            "institution": None,
            "retirement_relevant": ptype not in ("credit card", "credit"),
            "monthly_payment": 0,
        })

    # Enrich with monthly payments from transaction history
    # Aggregate by month first (handles biweekly payments), then take median
    today = date.today()
    payment_cats: list[tuple[str, list[str]]] = [
        ("mortgage", ["mortgage", "home loan", "home"]),
        ("vehicle purchase", ["vehicle", "auto loan", "car loan"]),
    ]
    for cat_pattern, keywords in payment_cats:
        cat_result = await session.execute(
            select(
                Transaction.period_year,
                Transaction.period_month,
                func.sum(func.abs(Transaction.amount)),
            ).where(
                func.lower(Transaction.effective_category) == cat_pattern,
                Transaction.flow_type == "expense",
                Transaction.is_excluded.is_(False),
                Transaction.date >= today.replace(year=today.year - 1),
            ).group_by(Transaction.period_year, Transaction.period_month)
        )
        monthly_totals = [r[2] for r in cat_result if r[2] and r[2] > 100]
        if monthly_totals:
            monthly_est = round(median(monthly_totals), 2)
            for d in debts:
                if d["monthly_payment"] > 0:
                    continue
                name_low = (d["name"] or "").lower()
                type_low = (d["type"] or "").lower()
                if any(kw in name_low or kw in type_low for kw in keywords):
                    d["monthly_payment"] = monthly_est

    return debts


# ---------------------------------------------------------------------------
# Assets summary
# ---------------------------------------------------------------------------

async def _asset_defaults(session: AsyncSession) -> dict:
    # Split investments by retirement flag to avoid double-counting
    result = await session.execute(
        select(
            ManualAsset.asset_type,
            ManualAsset.is_retirement_account,
            func.sum(ManualAsset.current_value),
        ).where(
            ManualAsset.is_liability.is_(False),
            ManualAsset.is_active.is_(True),
        ).group_by(ManualAsset.asset_type, ManualAsset.is_retirement_account)
    )
    retirement_total = 0
    non_retirement_investment = 0
    real_estate = 0
    vehicle = 0
    other = 0
    grand_total = 0

    for asset_type, is_ret, val in result:
        val = val or 0
        grand_total += val
        if is_ret:
            retirement_total += val
        elif asset_type in ("investment", "brokerage"):
            non_retirement_investment += val
        elif asset_type == "real_estate":
            real_estate += val
        elif asset_type == "vehicle":
            vehicle += val
        else:
            other += val

    return {
        "real_estate_total": real_estate,
        "vehicle_total": vehicle,
        "investment_total": non_retirement_investment,
        "retirement_total": retirement_total,
        "other_total": other,
        "total": grand_total,
    }


# ---------------------------------------------------------------------------
# Net worth (latest snapshot or computed)
# ---------------------------------------------------------------------------

async def _net_worth_defaults(session: AsyncSession) -> dict:
    result = await session.execute(
        select(NetWorthSnapshot)
        .order_by(NetWorthSnapshot.year.desc(), NetWorthSnapshot.month.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()
    if snap:
        return {
            "total_assets": snap.total_assets,
            "total_liabilities": snap.total_liabilities,
            "net_worth": snap.net_worth,
            "as_of": f"{snap.year}-{snap.month:02d}",
        }
    return {"total_assets": 0, "total_liabilities": 0, "net_worth": 0, "as_of": None}


# ---------------------------------------------------------------------------
# Recurring subscriptions
# ---------------------------------------------------------------------------

async def _recurring_defaults(session: AsyncSession) -> list:
    result = await session.execute(
        select(RecurringTransaction)
        .where(RecurringTransaction.status == "active")
        .order_by(RecurringTransaction.amount.desc())
        .limit(50)
    )
    return [
        {
            "id": r.id,
            "name": r.name,
            "amount": abs(r.amount),
            "frequency": r.frequency,
            "category": r.category,
            "segment": r.segment,
        }
        for r in result.scalars()
    ]


# ---------------------------------------------------------------------------
# Equity compensation
# ---------------------------------------------------------------------------

async def _equity_defaults(session: AsyncSession) -> dict:
    result = await session.execute(
        select(
            func.sum(EquityGrant.vested_shares * EquityGrant.current_fmv),
            func.sum(EquityGrant.unvested_shares * EquityGrant.current_fmv),
        ).where(EquityGrant.is_active.is_(True))
    )
    row = result.one()
    vested_value = row[0] or 0
    unvested_value = row[1] or 0

    return {
        "total_value": vested_value + unvested_value,
        "vested_value": vested_value,
        "unvested_value": unvested_value,
    }


# ---------------------------------------------------------------------------
# Tax defaults (withholding, effective rate from most recent year)
# ---------------------------------------------------------------------------

async def _tax_defaults(session: AsyncSession) -> dict:
    current_year = datetime.now(timezone.utc).year

    for year in [current_year, current_year - 1]:
        result = await session.execute(
            select(
                func.sum(TaxItem.w2_federal_tax_withheld),
                func.sum(TaxItem.w2_state_income_tax),
                func.sum(TaxItem.w2_wages),
            ).where(TaxItem.tax_year == year)
        )
        row = result.one()
        if row[2] and row[2] > 0:
            fed = row[0] or 0
            state = row[1] or 0
            wages = row[2]
            return {
                "total_withholding": fed + state,
                "federal_withholding": fed,
                "state_withholding": state,
                "effective_rate": round((fed + state) / wages * 100, 1) if wages else 0,
                "tax_year": year,
            }

    return {"total_withholding": 0, "federal_withholding": 0, "state_withholding": 0, "effective_rate": 0, "tax_year": None}


# ---------------------------------------------------------------------------
# Benefits
# ---------------------------------------------------------------------------

async def _benefits_defaults(session: AsyncSession) -> dict:
    result = await session.execute(select(BenefitPackage).limit(2))
    packages = list(result.scalars())
    if not packages:
        return {
            "has_401k": False, "match_pct": 0, "match_limit_pct": 0,
            "has_hsa": False, "has_espp": False, "has_mega_backdoor": False,
            "health_premium_monthly": 0,
        }

    # Combine across both spouses
    has_401k = any(p.has_401k for p in packages)
    match_pct = max((p.employer_match_pct or 0) for p in packages)
    match_limit = max((p.employer_match_limit_pct or 0) for p in packages)
    has_hsa = any(p.has_hsa for p in packages)
    has_espp = any(p.has_espp for p in packages)
    has_mega = any(p.has_mega_backdoor for p in packages)
    health_premium = sum((p.health_premium_monthly or 0) for p in packages)

    return {
        "has_401k": has_401k,
        "match_pct": match_pct,
        "match_limit_pct": match_limit,
        "has_hsa": has_hsa,
        "has_espp": has_espp,
        "has_mega_backdoor": has_mega,
        "health_premium_monthly": health_premium,
    }


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------

async def _goals_defaults(session: AsyncSession) -> list:
    result = await session.execute(
        select(Goal)
        .where(Goal.status == "active")
        .order_by(Goal.target_amount.desc())
    )
    return [
        {
            "id": g.id,
            "name": g.name,
            "target": g.target_amount,
            "current": g.current_amount,
            "monthly_contribution": g.monthly_contribution or 0,
            "progress_pct": round(g.current_amount / g.target_amount * 100, 1) if g.target_amount else 0,
            "account_id": g.account_id,
        }
        for g in result.scalars()
    ]


# ---------------------------------------------------------------------------
# Business entities
# ---------------------------------------------------------------------------

async def _business_defaults(session: AsyncSession) -> list:
    result = await session.execute(
        select(BusinessEntity)
        .where(BusinessEntity.is_active.is_(True))
        .order_by(BusinessEntity.name)
    )
    return [
        {"id": e.id, "name": e.name, "entity_type": e.entity_type, "tax_treatment": e.tax_treatment}
        for e in result.scalars()
    ]


# ---------------------------------------------------------------------------
# Data source flags (tells UI what's available for auto-fill)
# ---------------------------------------------------------------------------

async def _data_source_flags(session: AsyncSession) -> dict:
    current_year = datetime.now(timezone.utc).year

    w2_count = (await session.execute(
        select(func.count(TaxItem.id)).where(TaxItem.form_type == "w2")
    )).scalar() or 0

    plaid_count = (await session.execute(
        select(func.count(PlaidAccount.id))
    )).scalar() or 0

    household_count = (await session.execute(
        select(func.count(HouseholdProfile.id))
    )).scalar() or 0

    benefit_count = (await session.execute(
        select(func.count(BenefitPackage.id))
    )).scalar() or 0

    asset_count = (await session.execute(
        select(func.count(ManualAsset.id)).where(ManualAsset.is_active.is_(True))
    )).scalar() or 0

    recurring_count = (await session.execute(
        select(func.count(RecurringTransaction.id)).where(RecurringTransaction.status == "active")
    )).scalar() or 0

    equity_count = (await session.execute(
        select(func.count(EquityGrant.id)).where(EquityGrant.is_active.is_(True))
    )).scalar() or 0

    budget_count = (await session.execute(
        select(func.count(Budget.id))
    )).scalar() or 0

    return {
        "has_w2": w2_count > 0,
        "has_plaid": plaid_count > 0,
        "has_household": household_count > 0,
        "has_benefits": benefit_count > 0,
        "has_assets": asset_count > 0,
        "has_recurring": recurring_count > 0,
        "has_equity": equity_count > 0,
        "has_budget": budget_count > 0,
        "w2_count": w2_count,
        "plaid_accounts": plaid_count,
    }


# ═══════════════════════════════════════════════════════════════════════════
# W-2 → Household sync detection
# ═══════════════════════════════════════════════════════════════════════════

async def detect_household_updates(session: AsyncSession) -> list[dict]:
    """Compare W-2 data against HouseholdProfile and return suggested updates."""
    result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary.is_(True)).limit(1)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        result = await session.execute(select(HouseholdProfile).limit(1))
        profile = result.scalar_one_or_none()
    if not profile:
        return []

    current_year = datetime.now(timezone.utc).year
    suggestions: list[dict] = []

    # Get all W-2s for the most recent year
    for year in [current_year, current_year - 1]:
        w2_result = await session.execute(
            select(TaxItem)
            .where(TaxItem.form_type == "w2", TaxItem.tax_year == year)
            .order_by(TaxItem.w2_wages.desc())
        )
        w2s = list(w2_result.scalars())
        if w2s:
            break
    else:
        return []

    # Match W-2s to spouse A/B by employer name
    for w2 in w2s:
        if not w2.w2_wages:
            continue

        # Try to match to spouse A
        if profile.spouse_a_employer and w2.payer_name:
            if _employer_match(profile.spouse_a_employer, w2.payer_name):
                if abs((profile.spouse_a_income or 0) - w2.w2_wages) > 100:
                    suggestions.append({
                        "field": "spouse_a_income",
                        "label": f"{profile.spouse_a_name or 'Spouse A'} Income",
                        "current": profile.spouse_a_income or 0,
                        "suggested": w2.w2_wages,
                        "source": f"W-2 from {w2.payer_name} ({year})",
                    })
                continue

        # Try to match to spouse B
        if profile.spouse_b_employer and w2.payer_name:
            if _employer_match(profile.spouse_b_employer, w2.payer_name):
                if abs((profile.spouse_b_income or 0) - w2.w2_wages) > 100:
                    suggestions.append({
                        "field": "spouse_b_income",
                        "label": f"{profile.spouse_b_name or 'Spouse B'} Income",
                        "current": profile.spouse_b_income or 0,
                        "suggested": w2.w2_wages,
                        "source": f"W-2 from {w2.payer_name} ({year})",
                    })
                continue

        # If no employer match and spouse A has no income, suggest as spouse A
        if (profile.spouse_a_income or 0) == 0 and not profile.spouse_a_employer:
            suggestions.append({
                "field": "spouse_a_income",
                "label": f"{profile.spouse_a_name or 'Spouse A'} Income",
                "current": 0,
                "suggested": w2.w2_wages,
                "source": f"W-2 from {w2.payer_name} ({year})",
            })
            # Also suggest employer name
            suggestions.append({
                "field": "spouse_a_employer",
                "label": f"{profile.spouse_a_name or 'Spouse A'} Employer",
                "current": profile.spouse_a_employer or "",
                "suggested": w2.payer_name,
                "source": f"W-2 ({year})",
            })

    return suggestions


async def apply_household_updates(session: AsyncSession, updates: list[dict]) -> dict:
    """Apply selected household updates from W-2 data."""
    result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary.is_(True)).limit(1)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        result = await session.execute(select(HouseholdProfile).limit(1))
        profile = result.scalar_one_or_none()
    if not profile:
        return {"applied": 0, "error": "No household profile found"}

    applied = 0
    allowed_fields = {
        "spouse_a_income", "spouse_a_employer", "spouse_a_work_state",
        "spouse_b_income", "spouse_b_employer", "spouse_b_work_state",
        "filing_status", "state",
    }

    for update in updates:
        field = update.get("field")
        value = update.get("suggested")
        if field in allowed_fields and value is not None:
            setattr(profile, field, value)
            applied += 1

    # Recompute combined income
    profile.combined_income = (profile.spouse_a_income or 0) + (profile.spouse_b_income or 0)
    profile.updated_at = datetime.utcnow()

    return {"applied": applied}


# ═══════════════════════════════════════════════════════════════════════════
# Smart Budget Generation
# ═══════════════════════════════════════════════════════════════════════════

async def generate_smart_budget(
    session: AsyncSession, year: int, month: int,
) -> list[dict]:
    """Generate a smart budget based on recent spending patterns."""
    today = date.today()
    lines: list[dict] = []
    seen_categories: set[str] = set()

    # 1. Recurring subscriptions → fixed budget lines
    recurring_result = await session.execute(
        select(RecurringTransaction).where(RecurringTransaction.status == "active")
    )
    for r in recurring_result.scalars():
        # Normalize to monthly amount
        if r.frequency == "weekly":
            monthly = abs(r.amount) * 4.33
        elif r.frequency == "biweekly":
            monthly = abs(r.amount) * 2.17
        elif r.frequency == "quarterly":
            monthly = abs(r.amount) / 3
        elif r.frequency == "annual":
            monthly = abs(r.amount) / 12
        else:
            monthly = abs(r.amount)

        cat = r.category or "Subscriptions"
        if cat not in seen_categories:
            lines.append({
                "category": cat,
                "segment": r.segment or "personal",
                "budget_amount": round(monthly, 2),
                "source": "recurring",
                "detail": r.name,
            })
            seen_categories.add(cat)

    # 2. Spending history (3-6 month median by category)
    category_months: dict[str, list[float]] = {}
    for offset in range(1, 7):
        m = month - offset
        y = year
        if m <= 0:
            m += 12
            y -= 1

        cat_result = await session.execute(
            select(
                Transaction.effective_category,
                Transaction.effective_segment,
                func.sum(case(
                    (Transaction.amount < 0, Transaction.amount * -1),
                    else_=0,
                )),
            ).where(
                Transaction.period_year == y,
                Transaction.period_month == m,
                Transaction.is_excluded.is_(False),
                Transaction.effective_category.isnot(None),
            ).group_by(Transaction.effective_category, Transaction.effective_segment)
        )
        for cat, seg, amt in cat_result:
            if cat and amt and amt > 0:
                key = f"{cat}|{seg or 'personal'}"
                category_months.setdefault(key, []).append(amt)

    for key, amounts in category_months.items():
        cat, seg = key.split("|", 1)
        if cat in seen_categories:
            continue
        if len(amounts) < 2:
            continue  # Need at least 2 months of data
        med = round(median(amounts), 2)
        if med < 5:
            continue  # Skip tiny categories
        lines.append({
            "category": cat,
            "segment": seg,
            "budget_amount": med,
            "source": f"{len(amounts)}-month median",
            "detail": None,
        })
        seen_categories.add(cat)

    # 3. Active goal contributions
    goal_result = await session.execute(
        select(Goal).where(
            Goal.status == "active",
            Goal.monthly_contribution.isnot(None),
            Goal.monthly_contribution > 0,
        )
    )
    for g in goal_result.scalars():
        lines.append({
            "category": f"Goal: {g.name}",
            "segment": "personal",
            "budget_amount": g.monthly_contribution,
            "source": "goal",
            "detail": g.name,
        })

    # Sort: recurring first, then by amount descending
    source_order = {"recurring": 0, "goal": 1}
    lines.sort(key=lambda x: (source_order.get(x["source"], 2), -x["budget_amount"]))

    return lines


# ═══════════════════════════════════════════════════════════════════════════
# Comprehensive Personal Budget (for Retirement)
# ═══════════════════════════════════════════════════════════════════════════

# Categories that are internal money movement, not regular spending
_EXCLUDED_CATEGORIES = frozenset({
    "Transfer", "Credit Card Payment", "Savings", "Check",
    "Payment / Refund", "Vehicle Purchase", "Taxes", "Tax Payments",
    "Uncategorized", "Unknown",
})

# Income categories — not expenses
_INCOME_CATEGORIES = frozenset({
    "Other Income", "Dividend Income", "Interest Income", "Capital Gain",
    "Board / Director Income", "W-2 Wages", "1099-NEC / Consulting Income",
    "K-1 / Partnership Income", "Rental Income", "Trust Income",
})

# Substrings that indicate a category is savings/goals, not spending
_SAVINGS_GOAL_KEYWORDS = frozenset({
    "fund", "college", "wedding", "investment", "savings",
    "emergency", "529",
})

# Map variant category names to a canonical name so Plaid differences across
# banks don't create duplicate budget lines.
_CANONICAL_CATEGORY: dict[str, str] = {
    "Groceries & Food": "Groceries",
    "Restaurants & Dining": "Restaurants & Bars",
    "Coffee Shops": "Coffee & Beverages",
    "Shopping & Retail": "Shopping",
    "Gas & Fuel": "Gas",
    "Internet & Phone": "Internet & Phone",
    "Phone & Internet": "Internet & Phone",
    "Phone": "Internet & Phone",
    "Internet": "Internet & Phone",
    "Streaming & Subscriptions": "Streaming & Entertainment",
    "Streaming & Digital": "Streaming & Entertainment",
    "TV, Streaming & Entertainment": "Streaming & Entertainment",
    "Fitness & Gym": "Fitness",
    "Health & Fitness": "Fitness",
    "Sports & Fitness": "Fitness",
    "Baby & Kids": "Baby & Child",
    "Health & Medical": "Medical",
    "Personal Care & Beauty": "Personal Care & Spa",
    "Charitable Donations": "Charity",
    "Auto & Transportation": "Auto Maintenance",
    "Pet Care": "Pets",
    "Cleaning & Household": "Home & Garden",
    "Kitchen & Dining": "Home & Garden",
    "Hotel & Lodging": "Travel",
    "Airline & Travel": "Travel",
    "Vacation": "Travel",
    "Gift": "Gifts & Flowers",
    "Christmas Gifts": "Gifts & Flowers",
    "Birthday Gifts": "Gifts & Flowers",
}

# Minimum months of data required for a transaction-derived category
_MIN_MONTHS_DATA = 2
# Lookback window in months
_LOOKBACK_MONTHS = 6


def _canonicalize(cat: str) -> str:
    """Return the canonical category name, merging Plaid variants."""
    return _CANONICAL_CATEGORY.get(cat, cat)


def _is_excluded(cat: str) -> bool:
    """Check if category should be excluded from the spending budget.

    Excludes: transfers, income, savings/goals, work expenses, taxes.
    """
    if cat in _EXCLUDED_CATEGORIES or cat in _INCOME_CATEGORIES:
        return True
    # Work expenses, employer-specific categories, goal transfers
    if cat.startswith("Business") or cat.startswith("Goal:"):
        return True
    low = cat.lower()
    # Income patterns (e.g. "Accenture Paycheck", "Vivant Paycheck")
    if "paycheck" in low or "wages" in low or "trust" in low:
        return True
    # Work expense reimbursements (e.g. "Accenture Expenses")
    if "expenses" in low:
        return True
    # Savings & goal contributions (e.g. "Emergency Fund", "Eli College")
    if any(kw in low for kw in _SAVINGS_GOAL_KEYWORDS):
        return True
    # Tax payments
    if "tax" in low:
        return True
    # AI/tech subscriptions that are business expenses
    if low.startswith("gen ai") or low.startswith("office"):
        return True
    # Discretionary transfers (e.g. "Christine's Discretionary") are legitimate
    # household expenses — the budget amount represents spending on a separate
    # credit card not in the system.  The transaction-side filtering handles
    # exclusion via flow_type='transfer', so we keep them here for budget lines.
    return False


async def compute_comprehensive_personal_budget(
    session: AsyncSession,
) -> list[dict]:
    """Build a complete personal spending picture by merging curated Budget
    entries with 6-month transaction-history averages.

    Budget entries are authoritative; transaction history fills gaps.
    Key improvements over raw data:
    - Merges duplicate categories (e.g. "Groceries" + "Groceries & Food")
    - Requires minimum 2 months of data (filters one-off spikes)
    - Uses full-period average for infrequent categories, median for regular ones
    - Excludes transfers, CC payments, savings, income, and work expenses
    """
    today = date.today()
    year, month = today.year, today.month

    # --- 1. Curated Budget entries (personal only, current or prior month) ---
    # Note: Budget.segment may be "Personal" or "personal" — use case-insensitive
    budget_result = await session.execute(
        select(Budget.category, Budget.budget_amount)
        .where(
            Budget.year == year,
            Budget.month == month,
            func.lower(Budget.segment) == "personal",
        )
    )
    budget_rows = budget_result.all()
    if not budget_rows:
        prev_m = month - 1 if month > 1 else 12
        prev_y = year if month > 1 else year - 1
        budget_result = await session.execute(
            select(Budget.category, Budget.budget_amount)
            .where(
                Budget.year == prev_y,
                Budget.month == prev_m,
                func.lower(Budget.segment) == "personal",
            )
        )
        budget_rows = budget_result.all()

    lines: list[dict] = []
    seen_canonical: set[str] = set()

    for cat, amt in budget_rows:
        if _is_excluded(cat):
            continue
        canon = _canonicalize(cat)
        if canon in seen_canonical:
            # Merge into existing budget line
            for line in lines:
                if line["category"] == canon:
                    line["monthly_amount"] += round(abs(amt), 2)
                    break
            continue
        lines.append({
            "category": canon,
            "monthly_amount": round(abs(amt), 2),
            "source": "budget",
            "months_of_data": None,
        })
        seen_canonical.add(canon)

    # --- 2. Transaction-history (personal only, 6 months) ---
    # Use flow_type='expense' to cleanly exclude income, transfers, refunds.
    # Collect per-canonical-category totals per month
    canonical_months: dict[str, list[float]] = {}
    for offset in range(1, _LOOKBACK_MONTHS + 1):
        m = month - offset
        y = year
        if m <= 0:
            m += 12
            y -= 1

        cat_result = await session.execute(
            select(
                Transaction.effective_category,
                func.sum(Transaction.amount * -1),
            ).where(
                Transaction.period_year == y,
                Transaction.period_month == m,
                Transaction.effective_segment == "personal",
                Transaction.is_excluded.is_(False),
                Transaction.flow_type == "expense",
                Transaction.effective_category.isnot(None),
            ).group_by(Transaction.effective_category)
        )
        # Accumulate by canonical name per month
        month_totals: dict[str, float] = {}
        for cat, amt in cat_result:
            if not cat or not amt or amt <= 0:
                continue
            # Still exclude savings/goal categories that might be tagged as expense
            if _is_excluded(cat):
                continue
            canon = _canonicalize(cat)
            month_totals[canon] = month_totals.get(canon, 0) + amt

        for canon, total in month_totals.items():
            canonical_months.setdefault(canon, []).append(total)

    # --- 3. Merge transaction history with budget entries ---
    # For categories already in budget: upgrade to actual spending if higher
    # For new categories: add if they have enough data
    for canon, amounts in canonical_months.items():
        n_months = len(amounts)
        if n_months < _MIN_MONTHS_DATA:
            continue  # Skip one-off spikes — need at least 2 months of data

        # For categories appearing in most months (4+/6), use median
        # For less frequent (2-3/6), use sum / lookback to amortize
        if n_months >= 4:
            monthly_amt = round(median(amounts), 2)
        else:
            monthly_amt = round(sum(amounts) / _LOOKBACK_MONTHS, 2)

        if monthly_amt < 10:
            continue

        if canon in seen_canonical:
            # Category exists in budget — use the higher of budget vs actual
            # This ensures we don't understate spending
            for line in lines:
                if line["category"] == canon:
                    if monthly_amt > line["monthly_amount"]:
                        line["monthly_amount"] = monthly_amt
                        line["source"] = "spending_history"
                        line["months_of_data"] = n_months
                    break
        else:
            lines.append({
                "category": canon,
                "monthly_amount": monthly_amt,
                "source": "spending_history",
                "months_of_data": n_months,
            })

    # Sort by monthly amount descending
    lines.sort(key=lambda x: -x["monthly_amount"])
    return lines


# ═══════════════════════════════════════════════════════════════════════════
# Tax Carry-Forward
# ═══════════════════════════════════════════════════════════════════════════

async def get_tax_carry_forward(
    session: AsyncSession, from_year: int, to_year: int,
) -> list[dict]:
    """Get prior year tax items for carry-forward suggestions."""
    result = await session.execute(
        select(TaxItem)
        .where(TaxItem.tax_year == from_year)
        .order_by(TaxItem.form_type, TaxItem.payer_name)
    )
    items: list[dict] = []
    for item in result.scalars():
        amount = (
            item.w2_wages or item.nec_nonemployee_compensation
            or item.div_total_ordinary or item.b_proceeds
            or item.int_interest or item.k1_ordinary_income
            or 0
        )
        items.append({
            "form_type": item.form_type,
            "payer_name": item.payer_name,
            "payer_ein": item.payer_ein,
            "prior_year_amount": amount,
            "from_year": from_year,
            "to_year": to_year,
            "status": "expected",
        })

    # Check which ones already exist in to_year
    to_result = await session.execute(
        select(TaxItem.form_type, TaxItem.payer_ein)
        .where(TaxItem.tax_year == to_year)
    )
    received = {(r[0], r[1]) for r in to_result}

    for item in items:
        if (item["form_type"], item["payer_ein"]) in received:
            item["status"] = "received"

    return items


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _employer_match(stored: str, w2_name: str) -> bool:
    """Fuzzy match employer names (case-insensitive, ignoring common suffixes)."""
    if not stored or not w2_name:
        return False
    a = stored.lower().strip().rstrip(".,").replace(",", "")
    b = w2_name.lower().strip().rstrip(".,").replace(",", "")
    # Remove common suffixes
    for suffix in [" inc", " llc", " corp", " co", " ltd", " lp"]:
        a = a.removesuffix(suffix)
        b = b.removesuffix(suffix)
    return a == b or a in b or b in a
