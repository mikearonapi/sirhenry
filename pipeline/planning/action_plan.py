"""
Action Plan engine: assembles real financial data from the database
and computes the personalized Financial Order of Operations (FOO).

Future-proof: when multi-user is added, all queries here just need
a user_id filter added to the WHERE clauses.
"""
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import (
    PlaidAccount,
    ManualAsset,
    RetirementProfile,
    HouseholdProfile,
    BenefitPackage,
    FinancialPeriod,
    Transaction,
    NetWorthSnapshot,
)
from pipeline.planning.benchmarks import BenchmarkEngine

logger = logging.getLogger(__name__)


async def _get_credit_card_debt(session: AsyncSession) -> float:
    result = await session.execute(
        select(func.sum(func.abs(PlaidAccount.current_balance))).where(
            PlaidAccount.type == "credit"
        )
    )
    plaid_cc = result.scalar() or 0.0

    result = await session.execute(
        select(func.sum(ManualAsset.current_value)).where(
            ManualAsset.is_active == True,
            ManualAsset.is_liability == True,
            ManualAsset.asset_type.in_(["credit_card"]),
        )
    )
    manual_cc = result.scalar() or 0.0
    return plaid_cc + manual_cc


async def _get_loan_debt(session: AsyncSession) -> float:
    result = await session.execute(
        select(func.sum(func.abs(PlaidAccount.current_balance))).where(
            PlaidAccount.type.in_(["loan"])
        )
    )
    plaid_loans = result.scalar() or 0.0

    result = await session.execute(
        select(func.sum(ManualAsset.current_value)).where(
            ManualAsset.is_active == True,
            ManualAsset.is_liability == True,
            ManualAsset.asset_type.in_(["student_loan", "personal_loan", "auto_loan", "other"]),
        )
    )
    manual_loans = result.scalar() or 0.0
    return plaid_loans + manual_loans


async def _get_depository_balance(session: AsyncSession) -> float:
    result = await session.execute(
        select(func.sum(PlaidAccount.current_balance)).where(
            PlaidAccount.type == "depository"
        )
    )
    plaid = result.scalar() or 0.0

    result = await session.execute(
        select(func.sum(ManualAsset.current_value)).where(
            ManualAsset.is_active == True,
            ManualAsset.is_liability == False,
            ManualAsset.asset_type.in_(["cash", "savings", "checking", "money_market"]),
        )
    )
    manual = result.scalar() or 0.0
    return plaid + manual


async def _get_investment_balance(session: AsyncSession) -> float:
    result = await session.execute(
        select(func.sum(PlaidAccount.current_balance)).where(
            PlaidAccount.type == "investment"
        )
    )
    plaid = result.scalar() or 0.0

    result = await session.execute(
        select(func.sum(ManualAsset.current_value)).where(
            ManualAsset.is_active == True,
            ManualAsset.is_liability == False,
            ManualAsset.asset_type.in_(["brokerage", "taxable_investment"]),
            ManualAsset.is_retirement_account == False,
        )
    )
    manual = result.scalar() or 0.0
    return plaid + manual


async def _get_avg_monthly_expenses(session: AsyncSession) -> float:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(
            func.avg(FinancialPeriod.total_expenses)
        ).where(
            FinancialPeriod.segment == "all",
            FinancialPeriod.month.isnot(None),
            FinancialPeriod.total_expenses > 0,
            FinancialPeriod.year >= now.year - 1,
        )
    )
    avg = result.scalar()
    return abs(avg) if avg else 5000.0


async def _get_retirement_and_benefits(session: AsyncSession) -> dict:
    """Pull retirement profile, household, and benefit package data."""
    ret_result = await session.execute(
        select(RetirementProfile).where(RetirementProfile.is_primary == True).limit(1)
    )
    ret = ret_result.scalar_one_or_none()

    hh_result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    hh = hh_result.scalar_one_or_none()

    benefits = []
    if hh:
        bp_result = await session.execute(
            select(BenefitPackage).where(BenefitPackage.household_id == hh.id)
        )
        benefits = list(bp_result.scalars().all())

    total_401k_contrib = 0.0
    total_401k_limit = 23500.0
    has_employer_match = False
    employer_match_captured = False
    has_hsa = False
    hsa_total = 0.0
    hsa_limit = 8300.0  # 2025 family limit
    has_mega_backdoor = False
    mega_backdoor_contrib = 0.0
    mega_backdoor_limit = 46000.0

    for bp in benefits:
        if bp.has_401k:
            annual = bp.annual_401k_contribution or 0.0
            total_401k_contrib += annual
            if bp.employer_match_pct and bp.employer_match_pct > 0:
                has_employer_match = True
        if bp.has_hsa:
            has_hsa = True
            hsa_total += bp.hsa_employer_contribution or 0.0
        if bp.has_mega_backdoor:
            has_mega_backdoor = True
            mega_backdoor_limit = bp.mega_backdoor_limit or 46000.0

    if not benefits and ret:
        monthly = ret.monthly_retirement_contribution or 0
        total_401k_contrib = monthly * 12
        if ret.employer_match_pct and ret.employer_match_pct > 0:
            has_employer_match = True
        annual_income = ret.current_annual_income or 0
        match_limit = (ret.employer_match_limit_pct or 6) / 100
        if annual_income > 0 and monthly > 0:
            employer_match_captured = (monthly * 12 / annual_income) >= match_limit

    if benefits and has_employer_match:
        for bp in benefits:
            if bp.has_401k and bp.employer_match_pct and bp.employer_match_pct > 0:
                limit_pct = (bp.employer_match_limit_pct or 6) / 100
                annual = bp.annual_401k_contribution or 0.0
                if hh:
                    income = hh.spouse_a_income if bp.spouse == "A" else hh.spouse_b_income
                    if income and income > 0:
                        if annual / income >= limit_pct:
                            employer_match_captured = True

    roth_contributions = 0.0
    ma_result = await session.execute(
        select(func.sum(ManualAsset.employee_contribution_ytd)).where(
            ManualAsset.is_active == True,
            ManualAsset.tax_treatment.in_(["roth_ira", "roth"]),
        )
    )
    roth_contributions = ma_result.scalar() or 0.0

    return {
        "retirement_profile": ret,
        "household": hh,
        "benefits": benefits,
        "total_401k_contrib": total_401k_contrib,
        "total_401k_limit": total_401k_limit,
        "has_employer_match": has_employer_match,
        "employer_match_captured": employer_match_captured,
        "has_hsa": has_hsa,
        "hsa_total": hsa_total,
        "hsa_limit": hsa_limit,
        "has_mega_backdoor": has_mega_backdoor,
        "mega_backdoor_contrib": mega_backdoor_contrib,
        "mega_backdoor_limit": mega_backdoor_limit,
        "roth_contributions": roth_contributions,
    }


async def _get_user_profile(session: AsyncSession) -> dict:
    """Get age and income from the best available source."""
    hh_result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    hh = hh_result.scalar_one_or_none()

    ret_result = await session.execute(
        select(RetirementProfile).where(RetirementProfile.is_primary == True).limit(1)
    )
    ret = ret_result.scalar_one_or_none()

    age = ret.current_age if ret else 35
    income = 0.0
    if hh and hh.combined_income and hh.combined_income > 0:
        income = hh.combined_income
    elif ret and ret.current_annual_income and ret.current_annual_income > 0:
        income = ret.current_annual_income
    else:
        now = datetime.now(timezone.utc)
        fp_result = await session.execute(
            select(func.sum(FinancialPeriod.total_income)).where(
                FinancialPeriod.year == now.year,
                FinancialPeriod.segment == "all",
                FinancialPeriod.month.isnot(None),
            )
        )
        ytd_income = fp_result.scalar() or 0.0
        current_month = now.month or 1
        income = ytd_income * (12.0 / max(current_month, 1))

    if income <= 0:
        income = 200000.0

    return {"age": age, "income": income, "household": hh, "retirement": ret}


async def compute_action_plan(session: AsyncSession) -> list[dict]:
    """
    Compute a personalized Financial Order of Operations from real DB data.
    Returns a list of FOOStep-compatible dicts.
    """
    credit_card_debt = await _get_credit_card_debt(session)
    loan_debt = await _get_loan_debt(session)
    depository = await _get_depository_balance(session)
    taxable_investing = await _get_investment_balance(session)
    monthly_expenses = await _get_avg_monthly_expenses(session)
    rb = await _get_retirement_and_benefits(session)

    emergency_months = depository / monthly_expenses if monthly_expenses > 0 else 0

    steps = BenchmarkEngine.financial_order_of_operations(
        has_employer_match=rb["has_employer_match"],
        employer_match_captured=rb["employer_match_captured"],
        high_interest_debt=credit_card_debt,
        emergency_fund_months=emergency_months,
        hsa_contributions=rb["hsa_total"],
        hsa_limit=rb["hsa_limit"],
        roth_contributions=rb["roth_contributions"],
        contrib_401k=rb["total_401k_contrib"],
        limit_401k=rb["total_401k_limit"],
        has_mega_backdoor=rb["has_mega_backdoor"],
        mega_backdoor_contrib=rb["mega_backdoor_contrib"],
        mega_backdoor_limit=rb["mega_backdoor_limit"],
        taxable_investing=taxable_investing,
        low_interest_debt=loan_debt,
        monthly_expenses=monthly_expenses,
    )

    logger.info(
        "Action plan computed: cc_debt=%.0f, loans=%.0f, ef_months=%.1f, "
        "401k=%.0f, hsa=%.0f, roth=%.0f, invest=%.0f, expenses=%.0f/mo",
        credit_card_debt, loan_debt, emergency_months,
        rb["total_401k_contrib"], rb["hsa_total"],
        rb["roth_contributions"], taxable_investing, monthly_expenses,
    )
    return steps


async def compute_required_savings_rate(session: AsyncSession) -> float:
    """
    Derive the required savings rate from the retirement profile.
    Uses a simplified FV calculation: what % of income must be saved monthly
    to reach the target nest egg by retirement age, given current balances.
    Falls back to 20% if no retirement profile exists.
    """
    ret_result = await session.execute(
        select(RetirementProfile).where(RetirementProfile.is_primary == True).limit(1)
    )
    ret = ret_result.scalar_one_or_none()
    if not ret or not ret.retirement_age or not ret.current_age:
        return 20.0

    years_to_retire = max(ret.retirement_age - ret.current_age, 1)
    annual_income = ret.current_annual_income or 200000.0
    target_income_replacement = 0.80
    withdrawal_rate = 0.04
    target_nest_egg = (annual_income * target_income_replacement) / withdrawal_rate

    current_retirement = await _get_investment_balance(session)
    current_retirement += await _get_depository_balance(session) * 0.1
    annual_return = 0.07

    fv_existing = current_retirement * ((1 + annual_return) ** years_to_retire)
    gap = max(target_nest_egg - fv_existing, 0)

    if gap <= 0:
        return 5.0

    fv_annuity_factor = (((1 + annual_return) ** years_to_retire) - 1) / annual_return
    annual_savings_needed = gap / fv_annuity_factor if fv_annuity_factor > 0 else gap
    required_rate = (annual_savings_needed / annual_income) * 100

    return round(min(max(required_rate, 5.0), 80.0), 1)


async def compute_benchmarks_from_db(session: AsyncSession) -> dict:
    """
    Compute benchmark data using real profile and net worth data.
    Returns a dict compatible with the BenchmarkData frontend type.
    """
    profile = await _get_user_profile(session)

    nw_result = await session.execute(
        select(NetWorthSnapshot)
        .order_by(NetWorthSnapshot.snapshot_date.desc())
        .limit(1)
    )
    nw_snap = nw_result.scalar_one_or_none()
    net_worth = nw_snap.net_worth if nw_snap else 0.0

    if not nw_snap:
        assets_r = await session.execute(
            select(func.sum(ManualAsset.current_value)).where(
                ManualAsset.is_active == True, ManualAsset.is_liability == False,
            )
        )
        liab_r = await session.execute(
            select(func.sum(ManualAsset.current_value)).where(
                ManualAsset.is_active == True, ManualAsset.is_liability == True,
            )
        )
        net_worth = (assets_r.scalar() or 0.0) - (liab_r.scalar() or 0.0)

    now = datetime.now(timezone.utc)
    fp_result = await session.execute(
        select(FinancialPeriod).where(
            FinancialPeriod.year == now.year,
            FinancialPeriod.segment == "all",
            FinancialPeriod.month.isnot(None),
        )
    )
    periods = fp_result.scalars().all()
    ytd_income = sum(p.total_income for p in periods if p.month and p.month <= now.month)
    ytd_expenses = sum(p.total_expenses for p in periods if p.month and p.month <= now.month)

    savings_rate = 0.0
    if ytd_income > 0:
        savings_rate = ((ytd_income - ytd_expenses) / ytd_income) * 100

    income = profile["income"]
    if ytd_income > 0 and now.month >= 2:
        income = ytd_income * (12.0 / max(now.month, 1))

    required_rate = await compute_required_savings_rate(session)

    result = BenchmarkEngine.compute_benchmarks(
        age=profile["age"],
        income=income,
        net_worth=net_worth,
        savings_rate=savings_rate,
    )
    result["required_savings_rate"] = required_rate
    return result
