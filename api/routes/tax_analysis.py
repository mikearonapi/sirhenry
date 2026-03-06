"""Tax analysis endpoints — estimate, checklist, deduction opportunities, summary."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import (
    DeductionOpportunityOut,
    TaxChecklistItemOut,
    TaxChecklistOut,
    TaxDeductionInsightsOut,
    TaxSummaryOut,
)
from pipeline.db import (
    count_transactions,
    get_tax_items,
    get_tax_strategies,
    get_tax_summary,
)
from pipeline.db.schema import BenefitPackage, Document, HouseholdProfile, LifeEvent, TaxItem, TaxStrategy, Transaction

router = APIRouter(tags=["tax"])


@router.get("/summary", response_model=TaxSummaryOut)
async def get_tax_year_summary(
    tax_year: int = Query(default_factory=lambda: datetime.now(timezone.utc).year - 1),
    session: AsyncSession = Depends(get_session),
):
    import json as _json
    summary = await get_tax_summary(session, tax_year)

    # Check if document-sourced data exists
    has_doc_income = any(summary.get(k, 0) != 0 for k in (
        "w2_total_wages", "nec_total", "div_ordinary", "capital_gains_long",
        "capital_gains_short", "interest_income",
        "k1_ordinary_income", "k1_guaranteed_payments", "k1_rental_income",
    ))

    if has_doc_income:
        summary["data_source"] = "documents"
    else:
        # Fallback to household profile income
        household_result = await session.execute(
            select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
        )
        household = household_result.scalar_one_or_none()
        total_hh = (household.spouse_a_income or 0) + (household.spouse_b_income or 0) if household else 0
        if household and total_hh + (household.other_income_annual or 0) > 0:
            summary["data_source"] = "setup_profile"
            summary["w2_total_wages"] = total_hh
            if household.other_income_sources_json:
                try:
                    other_sources = _json.loads(household.other_income_sources_json)
                    for src in other_sources:
                        amt = float(src.get("amount", 0) or 0)
                        src_type = src.get("type", "")
                        if src_type in ("business_1099", "partnership_k1", "scorp_k1", "trust_k1"):
                            summary["nec_total"] = summary.get("nec_total", 0) + amt
                        elif src_type == "dividends_1099":
                            summary["div_ordinary"] = summary.get("div_ordinary", 0) + amt
                        elif src_type in ("rental", "other"):
                            summary["interest_income"] = summary.get("interest_income", 0) + amt
                except (ValueError, TypeError):
                    summary["interest_income"] = summary.get("interest_income", 0) + (household.other_income_annual or 0)
            elif household.other_income_annual:
                summary["interest_income"] = summary.get("interest_income", 0) + household.other_income_annual
        else:
            summary["data_source"] = "none"

    return TaxSummaryOut(**summary)


@router.get("/estimate")
async def get_tax_estimate(
    tax_year: int = Query(default_factory=lambda: datetime.now(timezone.utc).year),
    session: AsyncSession = Depends(get_session),
):
    """
    Compute a rough federal + SE tax estimate based on known income data.
    This is an estimate only — not professional tax advice.
    """
    return await _compute_tax_estimate(session, tax_year)


async def _compute_tax_estimate(session: AsyncSession, tax_year: int) -> dict:
    import json
    from pipeline.tax import (
        federal_tax as calc_fed_tax,
        se_tax as calc_se_tax,
        niit_tax as calc_niit,
        fica_tax as calc_fica,
        standard_deduction as std_deduction,
        marginal_rate as calc_marginal,
    )

    summary = await get_tax_summary(session, tax_year)

    # Resolve filing_status from HouseholdProfile instead of hardcoding "mfj"
    household_result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    household = household_result.scalar_one_or_none()
    filing_status = household.filing_status if household else "mfj"

    # Determine data source and fall back to HouseholdProfile income if no documents
    has_document_income = (
        summary["w2_total_wages"] > 0
        or summary["nec_total"] > 0
        or summary["div_ordinary"] > 0
        or summary["capital_gains_long"] > 0
        or summary["capital_gains_short"] > 0
        or summary["interest_income"] > 0
        or summary.get("k1_ordinary_income", 0) != 0
        or summary.get("k1_guaranteed_payments", 0) != 0
    )
    if has_document_income:
        data_source = "documents"
    elif household and ((household.spouse_a_income or 0) + (household.spouse_b_income or 0) + (household.other_income_annual or 0)) > 0:
        data_source = "setup_profile"
        # Use Setup income as fallback
        summary["w2_total_wages"] = (household.spouse_a_income or 0) + (household.spouse_b_income or 0)
        # Parse other_income_sources_json for income type breakdown
        if household.other_income_sources_json:
            try:
                other_sources = json.loads(household.other_income_sources_json)
                for src in other_sources:
                    amt = float(src.get("amount", 0) or 0)
                    src_type = src.get("type", "")
                    if src_type in ("business_1099", "partnership_k1", "scorp_k1", "trust_k1"):
                        summary["nec_total"] += amt
                    elif src_type == "dividends_1099":
                        summary["div_ordinary"] += amt
                    elif src_type in ("rental", "other"):
                        summary["interest_income"] += amt
            except (ValueError, TypeError):
                # Fallback: put all other income into interest as catch-all
                summary["interest_income"] += household.other_income_annual or 0
        elif household.other_income_annual:
            summary["interest_income"] += household.other_income_annual
    else:
        data_source = "none"

    # Fold in life event amounts for the tax year (capital gains, bonuses, etc.)
    life_event_cap_gains_long: float = 0.0
    life_event_cap_gains_short: float = 0.0
    life_event_bonus_income: float = 0.0
    le_result = await session.execute(
        select(LifeEvent).where(LifeEvent.tax_year == tax_year)
    )
    life_events = le_result.scalars().all()
    for le in life_events:
        if not le.amounts_json:
            continue
        try:
            amounts = json.loads(le.amounts_json)
        except (ValueError, TypeError):
            continue
        # real_estate:sale — capital_gain field
        if le.event_type == "real_estate" and le.event_subtype in ("sale", "sold"):
            cap_gain = float(amounts.get("capital_gain", 0) or 0)
            # Assume long-term unless explicitly marked short
            if amounts.get("holding_period") == "short":
                life_event_cap_gains_short += cap_gain
            else:
                life_event_cap_gains_long += cap_gain
        # employment:job_change — signing_bonus, bonus fields
        if le.event_type == "employment":
            life_event_bonus_income += float(amounts.get("signing_bonus", 0) or 0)
            life_event_bonus_income += float(amounts.get("bonus", 0) or 0)
        # Any event with a generic "capital_gain" or "bonus" key
        if le.event_type not in ("real_estate", "employment"):
            life_event_cap_gains_long += float(amounts.get("capital_gain", 0) or 0)
            life_event_bonus_income += float(amounts.get("bonus", 0) or 0)

    w2_wages = summary["w2_total_wages"] + life_event_bonus_income
    nec_income = summary["nec_total"]
    ord_div = summary["div_ordinary"]
    qual_div = summary["div_qualified"]
    cg_long = summary["capital_gains_long"] + life_event_cap_gains_long
    cg_short = summary["capital_gains_short"] + life_event_cap_gains_short
    interest = summary["interest_income"]

    # K-1 income components
    k1_ordinary = summary.get("k1_ordinary_income", 0)
    k1_guaranteed = summary.get("k1_guaranteed_payments", 0)
    k1_rental = summary.get("k1_rental_income", 0)
    k1_interest = summary.get("k1_interest_income", 0)
    k1_dividends = summary.get("k1_dividends", 0)
    k1_cap_gains = summary.get("k1_capital_gains", 0)

    # 1099-R retirement distributions (taxable portion is ordinary income)
    retirement_taxable = summary.get("retirement_taxable", 0)

    # 1099-G (unemployment = ordinary income; state tax refund = ordinary if itemized prior year)
    unemployment = summary.get("unemployment_income", 0)
    state_refund = summary.get("state_tax_refund", 0)

    # 1099-K (payment platform income — treated as self-employment unless W-2 employer)
    platform_income = summary.get("payment_platform_income", 0)

    # 1098 deductions (mortgage interest + property tax)
    mortgage_deduction = summary.get("mortgage_interest_deduction", 0)
    property_tax_ded = summary.get("property_tax_deduction", 0)

    # K-1 interest/dividends/cap gains add to their respective buckets
    interest += k1_interest
    ord_div += k1_dividends
    cg_long += k1_cap_gains

    unqualified_div = ord_div - qual_div
    ordinary_income = (
        w2_wages + nec_income + cg_short + unqualified_div + interest
        + k1_ordinary + k1_guaranteed + k1_rental
        + retirement_taxable + unemployment + state_refund + platform_income
    )

    # SE tax applies to NEC + K-1 guaranteed payments + 1099-K platform income
    se_eligible = nec_income + k1_guaranteed + platform_income
    se_tax_amt = calc_se_tax(se_eligible, filing_status) if se_eligible > 0 else 0
    se_deduction = se_tax_amt * 0.5

    agi = ordinary_income + qual_div + cg_long - se_deduction

    # Use itemized deduction if mortgage + property tax + state tax exceeds standard
    std_ded = std_deduction(filing_status)
    itemized = mortgage_deduction + min(property_tax_ded, 10000)  # SALT cap $10K
    deduction = max(std_ded, itemized)

    taxable_income = max(0, agi - deduction)

    fed_tax = calc_fed_tax(taxable_income, filing_status)
    mrate = calc_marginal(taxable_income, filing_status)

    investment_income = ord_div + cg_long + cg_short + interest
    niit = calc_niit(agi, investment_income, filing_status)

    additional_medicare = calc_fica(w2_wages, filing_status) - (w2_wages * 0.0765) if w2_wages > 0 else 0
    additional_medicare = max(0, additional_medicare)

    total_tax = fed_tax + se_tax_amt + niit + additional_medicare

    return {
        "tax_year": tax_year,
        "filing_status": filing_status,
        "estimated_agi": round(agi, 2),
        "estimated_taxable_income": round(taxable_income, 2),
        "ordinary_income": round(ordinary_income, 2),
        "qualified_dividends_and_ltcg": round(qual_div + cg_long, 2),
        "self_employment_income": round(nec_income, 2),
        "life_event_capital_gains": round(life_event_cap_gains_long + life_event_cap_gains_short, 2),
        "life_event_bonus_income": round(life_event_bonus_income, 2),
        "federal_income_tax": round(fed_tax, 2),
        "self_employment_tax": round(se_tax_amt, 2),
        "niit": round(niit, 2),
        "additional_medicare_tax": round(additional_medicare, 2),
        "total_estimated_tax": round(total_tax, 2),
        "effective_rate": round(total_tax / max(1, agi) * 100, 1),
        "marginal_rate": round(mrate * 100, 1),
        "w2_federal_already_withheld": round(summary["w2_federal_withheld"], 2),
        "estimated_balance_due": round(total_tax - summary["w2_federal_withheld"], 2),
        "data_source": data_source,
        "disclaimer": "This is a rough estimate only. Consult a CPA for official tax advice.",
    }


# ---------------------------------------------------------------------------
# Tax Checklist
# ---------------------------------------------------------------------------

@router.get("/checklist", response_model=TaxChecklistOut)
async def get_tax_checklist(
    tax_year: int = Query(default_factory=lambda: datetime.now(timezone.utc).year - 1),
    session: AsyncSession = Depends(get_session),
):
    """Computed tax filing readiness checklist based on actual data in the system."""
    items: list[TaxChecklistItemOut] = []
    tax_items_all = await get_tax_items(session, tax_year=tax_year)

    form_counts: dict[str, int] = {}
    for ti in tax_items_all:
        form_counts[ti.form_type] = form_counts.get(ti.form_type, 0) + 1

    # --- Document imports ---
    doc_checks = [
        ("import_w2", "Import W-2 Documents", "Upload all W-2 wage statements", "w2"),
        ("import_1099_nec", "Import 1099-NEC Documents", "Upload 1099-NEC forms for freelance/board income", "1099_nec"),
        ("import_1099_div", "Import 1099-DIV Documents", "Upload 1099-DIV forms for dividend income", "1099_div"),
        ("import_1099_b", "Import 1099-B Documents", "Upload 1099-B forms for capital gains/losses", "1099_b"),
        ("import_1099_int", "Import 1099-INT Documents", "Upload 1099-INT forms for interest income", "1099_int"),
        ("import_k1", "Import K-1 Documents", "Upload K-1 forms for partnership/S-corp income", "k1"),
        ("import_1099_r", "Import 1099-R Documents", "Upload 1099-R forms for retirement distributions", "1099_r"),
        ("import_1099_g", "Import 1099-G Documents", "Upload 1099-G forms for government payments", "1099_g"),
        ("import_1099_k", "Import 1099-K Documents", "Upload 1099-K forms for payment platform income", "1099_k"),
        ("import_1098", "Import 1098 Documents", "Upload 1098 forms for mortgage interest", "1098"),
    ]
    for check_id, label, desc, form in doc_checks:
        count = form_counts.get(form, 0)
        status = "complete" if count > 0 else "incomplete"
        detail = f"{count} document(s) imported" if count > 0 else "No documents found"
        items.append(TaxChecklistItemOut(
            id=check_id, label=label, description=desc,
            status=status, detail=detail, category="documents",
        ))

    # --- Transaction import ---
    total_txn = await count_transactions(session, year=tax_year)
    items.append(TaxChecklistItemOut(
        id="import_transactions",
        label="Import Transaction Statements",
        description="Upload credit card and bank statements for the tax year",
        status="complete" if total_txn > 0 else "incomplete",
        detail=f"{total_txn:,} transactions imported" if total_txn > 0 else "No transactions for this year",
        category="documents",
    ))

    # --- Categorization ---
    uncategorized = await session.execute(
        select(func.count(Transaction.id)).where(
            Transaction.period_year == tax_year,
            Transaction.is_excluded == False,
            Transaction.effective_category.is_(None),
        )
    )
    uncat_count = uncategorized.scalar_one()
    cat_pct = round((1 - uncat_count / max(1, total_txn)) * 100, 1) if total_txn > 0 else 0
    if uncat_count == 0 and total_txn > 0:
        cat_status = "complete"
    elif cat_pct >= 80:
        cat_status = "partial"
    else:
        cat_status = "incomplete"
    items.append(TaxChecklistItemOut(
        id="categorize_transactions",
        label="Categorize All Transactions",
        description="Ensure every transaction has a category (AI + manual review)",
        status=cat_status,
        detail=f"{cat_pct}% categorized ({uncat_count:,} remaining)",
        category="preparation",
    ))

    # --- Business expense review ---
    biz_txn_count = await count_transactions(session, year=tax_year, segment="business")
    biz_reviewed = await session.execute(
        select(func.count(Transaction.id)).where(
            Transaction.period_year == tax_year,
            Transaction.effective_segment == "business",
            Transaction.is_excluded == False,
            Transaction.is_manually_reviewed == True,
        )
    )
    biz_reviewed_count = biz_reviewed.scalar_one()
    if biz_txn_count == 0:
        biz_status = "not_applicable"
        biz_detail = "No business transactions found"
    elif biz_reviewed_count >= biz_txn_count:
        biz_status = "complete"
        biz_detail = f"All {biz_txn_count:,} business transactions reviewed"
    elif biz_reviewed_count > 0:
        biz_status = "partial"
        biz_detail = f"{biz_reviewed_count:,}/{biz_txn_count:,} reviewed"
    else:
        biz_status = "incomplete"
        biz_detail = f"{biz_txn_count:,} business transactions need review"
    items.append(TaxChecklistItemOut(
        id="review_business_expenses",
        label="Review Business Expenses",
        description="Verify all business deductions are correctly categorized and segmented",
        status=biz_status, detail=biz_detail, category="preparation",
    ))

    # --- AI tax analysis ---
    strategies = await get_tax_strategies(session, tax_year=tax_year)
    items.append(TaxChecklistItemOut(
        id="run_ai_analysis",
        label="Run AI Tax Strategy Analysis",
        description="Generate personalized tax optimization strategies",
        status="complete" if len(strategies) > 0 else "incomplete",
        detail=f"{len(strategies)} strategies generated" if strategies else "Not yet run",
        category="preparation",
    ))

    # --- Quarterly estimated payments (for current/future year) ---
    now = datetime.now(timezone.utc)
    q_deadlines = [
        ("q1_estimated", "Q1 Estimated Payment", f"Apr 15, {tax_year + 1}"),
        ("q2_estimated", "Q2 Estimated Payment", f"Jun 15, {tax_year + 1}"),
        ("q3_estimated", "Q3 Estimated Payment", f"Sep 15, {tax_year + 1}"),
        ("q4_estimated", "Q4 Estimated Payment", f"Jan 15, {tax_year + 2}"),
    ]
    for qid, qlabel, qdeadline in q_deadlines:
        items.append(TaxChecklistItemOut(
            id=qid, label=qlabel,
            description=f"Federal estimated tax payment due {qdeadline}",
            status="incomplete",
            detail=f"Due {qdeadline} — track manually or via Reminders",
            category="payments",
        ))

    # --- Filing deadlines ---
    filing_deadline = f"Apr 15, {tax_year + 1}"
    extension_deadline = f"Oct 15, {tax_year + 1}"
    items.append(TaxChecklistItemOut(
        id="file_federal", label="File Federal Tax Return",
        description=f"File Form 1040 by {filing_deadline} (or extend to {extension_deadline})",
        status="incomplete", detail=f"Deadline: {filing_deadline}",
        category="filing",
    ))
    items.append(TaxChecklistItemOut(
        id="file_state", label="File State Tax Return(s)",
        description="File state returns for all states with income allocation",
        status="incomplete", detail=f"Deadline typically {filing_deadline}",
        category="filing",
    ))

    completed = sum(1 for i in items if i.status == "complete")
    applicable = sum(1 for i in items if i.status != "not_applicable")
    pct = round(completed / max(1, applicable) * 100, 1)

    return TaxChecklistOut(
        tax_year=tax_year,
        items=items,
        completed=completed,
        total=applicable,
        progress_pct=pct,
    )


# ---------------------------------------------------------------------------
# Deduction Opportunities
# ---------------------------------------------------------------------------

@router.get("/deduction-opportunities", response_model=TaxDeductionInsightsOut)
async def get_deduction_opportunities(
    tax_year: int = Query(default_factory=lambda: datetime.now(timezone.utc).year),
    session: AsyncSession = Depends(get_session),
):
    """
    Smart deduction insights: shows what you could spend/invest to reduce
    your tax bill. Frames it as 'money leaves your account either way — IRS
    or as a business asset/deduction.'
    """
    from pipeline.tax import LIMIT_401K as _LIMIT_401K
    from pipeline.tax.constants import HSA_LIMIT as _HSA_LIMIT

    estimate = await _compute_tax_estimate(session, tax_year)
    balance_due = estimate["estimated_balance_due"]
    marginal_rate = estimate["marginal_rate"]
    effective_rate = estimate["effective_rate"]
    agi = estimate["estimated_agi"]
    se_income = estimate["self_employment_income"]
    est_data_source = estimate.get("data_source", "documents")

    # Check HSA eligibility from BenefitPackage
    household_result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    household = household_result.scalar_one_or_none()
    has_hsa_eligible = False
    if household:
        benefits_result = await session.execute(
            select(BenefitPackage).where(BenefitPackage.household_id == household.id)
        )
        benefits = benefits_result.scalars().all()
        has_hsa_eligible = any(getattr(b, "has_hsa", False) for b in benefits)

    # Get existing business expenses to understand current deduction picture
    biz_expense_result = await session.execute(
        select(
            Transaction.effective_category,
            func.sum(Transaction.amount).label("total"),
        )
        .where(
            Transaction.period_year == tax_year,
            Transaction.effective_segment == "business",
            Transaction.is_excluded == False,
            Transaction.amount < 0,
        )
        .group_by(Transaction.effective_category)
    )
    biz_expenses = {
        row.effective_category: abs(float(row.total))
        for row in biz_expense_result.all()
        if row.effective_category
    }
    total_biz_expenses = sum(biz_expenses.values())

    opportunities: list[DeductionOpportunityOut] = []
    mrate = marginal_rate / 100

    # --- Vehicle / Section 179 ---
    if se_income > 0 or total_biz_expenses > 0:
        vehicle_deduction = 30500  # approx bonus depreciation / Section 179 for SUV > 6000 lbs
        vehicle_savings_low = round(vehicle_deduction * mrate * 0.5, 2)
        vehicle_savings_high = round(vehicle_deduction * mrate, 2)
        opportunities.append(DeductionOpportunityOut(
            id="vehicle_179",
            title="Business Vehicle (Section 179 Deduction)",
            description=(
                "Purchase or lease a vehicle used for business. SUVs over 6,000 lbs GVW qualify "
                "for up to $30,500 first-year Section 179 deduction. Even a mixed-use vehicle "
                "deducts the business-use percentage. Instead of that money going to the IRS, "
                "you get a business asset."
            ),
            category="vehicle",
            estimated_tax_savings_low=vehicle_savings_low,
            estimated_tax_savings_high=vehicle_savings_high,
            estimated_cost=45000,
            net_benefit_explanation=(
                f"A $45K vehicle at {marginal_rate}% marginal rate saves ~${vehicle_savings_high:,.0f} in taxes. "
                f"The money leaves your account either way — it's either a depreciating asset you use, or a check to the IRS."
            ),
            urgency="medium",
            deadline=f"Dec 31, {tax_year}" if datetime.now(timezone.utc).year == tax_year else None,
        ))

    # --- Equipment / Technology (Section 179) ---
    if se_income > 0 or total_biz_expenses > 0:
        equip_cost = 5000
        equip_savings = round(equip_cost * mrate, 2)
        opportunities.append(DeductionOpportunityOut(
            id="equipment_179",
            title="Business Equipment & Technology",
            description=(
                "Computers, monitors, software, servers, and other business equipment qualify "
                "for full Section 179 expensing in the year of purchase. If you need it for "
                "your business, buying before year-end converts a tax payment into a productive asset."
            ),
            category="equipment",
            estimated_tax_savings_low=round(equip_cost * mrate * 0.5, 2),
            estimated_tax_savings_high=equip_savings,
            estimated_cost=equip_cost,
            net_benefit_explanation=(
                f"$5K in business equipment at {marginal_rate}% saves ~${equip_savings:,.0f}. "
                f"You get tools you need AND reduce your tax bill."
            ),
            urgency="medium",
            deadline=f"Dec 31, {tax_year}" if datetime.now(timezone.utc).year == tax_year else None,
        ))

    # --- Retirement: SEP-IRA ---
    if se_income > 0:
        sep_limit = min(se_income * 0.25, 70000)
        sep_savings_low = round(sep_limit * 0.5 * mrate, 2)
        sep_savings_high = round(sep_limit * mrate, 2)
        opportunities.append(DeductionOpportunityOut(
            id="sep_ira",
            title="SEP-IRA Contribution",
            description=(
                f"With ${se_income:,.0f} in self-employment income, you can contribute up to "
                f"${sep_limit:,.0f} to a SEP-IRA (25% of net SE income, max $70,000). "
                f"This is an above-the-line deduction — it reduces AGI directly. "
                f"The money goes into your retirement account instead of to the IRS."
            ),
            category="retirement",
            estimated_tax_savings_low=sep_savings_low,
            estimated_tax_savings_high=sep_savings_high,
            estimated_cost=round(sep_limit, 2),
            net_benefit_explanation=(
                f"Contributing ${sep_limit:,.0f} to a SEP-IRA saves ${sep_savings_high:,.0f} in taxes "
                f"AND builds retirement wealth. The money is yours, not the government's."
            ),
            urgency="high",
            deadline=f"Apr 15, {tax_year + 1} (with extension: Oct 15, {tax_year + 1})",
        ))

    # --- 401(k) Maximization ---
    max_401k = _LIMIT_401K
    savings_401k = round(max_401k * mrate, 2)
    opportunities.append(DeductionOpportunityOut(
        id="maximize_401k",
        title="Maximize 401(k) Contributions",
        description=(
            f"The 2025 401(k) employee contribution limit is $23,500 ($31,000 if age 50+). "
            f"Every dollar contributed reduces your taxable income dollar-for-dollar. "
            f"If you haven't maxed out, increasing contributions before year-end is one of the "
            f"simplest ways to lower your tax bill."
        ),
        category="retirement",
        estimated_tax_savings_low=round(savings_401k * 0.5, 2),
        estimated_tax_savings_high=savings_401k,
        estimated_cost=max_401k,
        net_benefit_explanation=(
            f"Maxing your 401(k) at {marginal_rate}% marginal rate saves up to ${savings_401k:,.0f} in taxes. "
            f"The money grows tax-deferred in your retirement account."
        ),
        urgency="high",
        deadline=f"Dec 31, {tax_year}",
    ))

    # --- HSA ---
    hsa_family_limit = _HSA_LIMIT["family"]
    hsa_savings = round(hsa_family_limit * mrate, 2)
    hsa_note = "" if has_hsa_eligible else " Note: No HDHP found in your benefits — update your benefits in Setup if you have one."
    opportunities.append(DeductionOpportunityOut(
        id="hsa_contribution",
        title="HSA Contribution" + (" (HDHP enrolled)" if has_hsa_eligible else " (requires HDHP)"),
        description=(
            "If enrolled in a High Deductible Health Plan, you can contribute up to "
            f"$8,550 (family, 2025) to an HSA. Triple tax advantage: deductible going in, "
            f"tax-free growth, tax-free withdrawals for medical expenses.{hsa_note}"
        ),
        category="other",
        estimated_tax_savings_low=round(hsa_savings * 0.5, 2),
        estimated_tax_savings_high=hsa_savings,
        estimated_cost=hsa_family_limit,
        net_benefit_explanation=(
            f"Full HSA contribution saves ~${hsa_savings:,.0f} in taxes while building a medical expense fund."
        ),
        urgency="medium",
        deadline=f"Apr 15, {tax_year + 1}",
        applicable=has_hsa_eligible,
    ))

    # --- Home Office ---
    home_office_current = biz_expenses.get("Home Office", 0) + biz_expenses.get("Office Expenses", 0)
    if se_income > 0 and home_office_current < 1500:
        ho_deduction = 1500  # simplified method max
        ho_savings = round(ho_deduction * mrate, 2)
        opportunities.append(DeductionOpportunityOut(
            id="home_office",
            title="Home Office Deduction",
            description=(
                "If you use a dedicated space in your home for business, claim the home office "
                "deduction. Simplified method: $5/sq ft up to 300 sq ft ($1,500). Regular method "
                "may yield more based on actual expenses (mortgage interest, utilities, insurance)."
            ),
            category="home_office",
            estimated_tax_savings_low=round(ho_savings * 0.5, 2),
            estimated_tax_savings_high=round(ho_deduction * 2 * mrate, 2),
            net_benefit_explanation=(
                f"Home office deduction of $1,500–$3,000+ saves ${ho_savings:,.0f}–${round(ho_deduction*2*mrate):,.0f} in taxes "
                f"with no additional out-of-pocket cost — you already pay for your home."
            ),
            urgency="medium",
            deadline=f"Filed with return",
        ))

    # --- Charitable (DAF) ---
    if agi > 200000:
        daf_amount = 10000
        daf_savings = round(daf_amount * mrate, 2)
        opportunities.append(DeductionOpportunityOut(
            id="charitable_daf",
            title="Donor-Advised Fund (DAF) Contribution",
            description=(
                "Contribute appreciated stock or cash to a DAF to get an immediate tax deduction. "
                "You can distribute the funds to charities over time. Bunching multiple years of "
                "giving into one year can push you above the standard deduction threshold if itemizing."
            ),
            category="charitable",
            estimated_tax_savings_low=round(daf_savings * 0.5, 2),
            estimated_tax_savings_high=daf_savings,
            estimated_cost=daf_amount,
            net_benefit_explanation=(
                f"A ${daf_amount:,.0f} DAF contribution at {marginal_rate}% saves ~${daf_savings:,.0f}. "
                f"You control when charities receive the funds while locking in this year's deduction."
            ),
            urgency="low",
            deadline=f"Dec 31, {tax_year}",
        ))

    # --- Education / Professional Development ---
    if se_income > 0 or total_biz_expenses > 0:
        edu_cost = 3000
        edu_savings = round(edu_cost * mrate, 2)
        opportunities.append(DeductionOpportunityOut(
            id="education_training",
            title="Professional Development & Education",
            description=(
                "Courses, certifications, conferences, and professional books related to your "
                "business are fully deductible. Invest in yourself instead of paying the IRS."
            ),
            category="education",
            estimated_tax_savings_low=round(edu_savings * 0.5, 2),
            estimated_tax_savings_high=edu_savings,
            estimated_cost=edu_cost,
            net_benefit_explanation=(
                f"$3K in business education at {marginal_rate}% saves ~${edu_savings:,.0f} in taxes "
                f"while increasing your earning potential."
            ),
            urgency="low",
            deadline=f"Dec 31, {tax_year}",
        ))

    # --- Backdoor Roth IRA ---
    if agi > 230000:
        opportunities.append(DeductionOpportunityOut(
            id="backdoor_roth",
            title="Backdoor Roth IRA Conversion",
            description=(
                "At your income level, direct Roth IRA contributions are phased out. "
                "A backdoor Roth (contribute to traditional IRA, then convert) lets you put "
                "$7,000/person into a Roth IRA for tax-free growth. Not a deduction, but "
                "shields future gains from taxation permanently."
            ),
            category="retirement",
            estimated_tax_savings_low=0,
            estimated_tax_savings_high=0,
            estimated_cost=14000,
            net_benefit_explanation=(
                "No immediate tax savings, but $14K/year ($7K each spouse) grows completely "
                "tax-free forever. At your marginal rate, the long-term value is substantial."
            ),
            urgency="medium",
            deadline=f"Apr 15, {tax_year + 1}",
            applicable=True,
        ))

    # Build summary
    if balance_due > 0:
        total_potential = sum(o.estimated_tax_savings_high for o in opportunities)
        summary_text = (
            f"You're estimated to owe ${balance_due:,.0f} for {tax_year}. "
            f"At your {marginal_rate}% marginal rate, there are up to ${total_potential:,.0f} in potential "
            f"tax savings through strategic spending and contributions. Every dollar spent on "
            f"deductible business expenses or retirement contributions saves you "
            f"${mrate:.2f} in taxes — the money leaves your account either way, but "
            f"with deductions, you keep the asset instead of sending it to the IRS."
        )
    else:
        summary_text = (
            f"Good news: you're currently estimated to get a ${abs(balance_due):,.0f} refund for {tax_year}. "
            f"These opportunities can still build wealth and reduce future tax bills."
        )

    return TaxDeductionInsightsOut(
        tax_year=tax_year,
        estimated_balance_due=balance_due,
        effective_rate=effective_rate,
        marginal_rate=marginal_rate,
        opportunities=opportunities,
        summary=summary_text,
        data_source=est_data_source,
    )


# ---------------------------------------------------------------------------
# PATCH /tax/items/{item_id} — Inline editing of OCR-extracted tax item fields
# ---------------------------------------------------------------------------

class TaxItemUpdate(BaseModel):
    """Partial update for a tax item. All fields optional."""
    payer_name: Optional[str] = None
    payer_ein: Optional[str] = None
    w2_wages: Optional[float] = None
    w2_federal_tax_withheld: Optional[float] = None
    w2_state: Optional[str] = None
    w2_state_wages: Optional[float] = None
    w2_state_income_tax: Optional[float] = None
    nec_nonemployee_compensation: Optional[float] = None
    nec_federal_tax_withheld: Optional[float] = None
    div_total_ordinary: Optional[float] = None
    div_qualified: Optional[float] = None
    div_total_capital_gain: Optional[float] = None
    b_proceeds: Optional[float] = None
    b_cost_basis: Optional[float] = None
    b_gain_loss: Optional[float] = None
    int_interest: Optional[float] = None
    k1_ordinary_income: Optional[float] = None
    k1_rental_income: Optional[float] = None
    k1_guaranteed_payments: Optional[float] = None
    k1_interest_income: Optional[float] = None
    k1_dividends: Optional[float] = None
    k1_short_term_capital_gain: Optional[float] = None
    k1_long_term_capital_gain: Optional[float] = None
    k1_section_179: Optional[float] = None
    k1_distributions: Optional[float] = None
    r_gross_distribution: Optional[float] = None
    r_taxable_amount: Optional[float] = None
    m_mortgage_interest: Optional[float] = None
    m_points_paid: Optional[float] = None
    m_property_tax: Optional[float] = None


@router.patch("/items/{item_id}")
async def update_tax_item(
    item_id: int,
    body: TaxItemUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update individual fields on a tax item (e.g., correcting OCR misreads)."""
    result = await session.execute(select(TaxItem).where(TaxItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Tax item not found")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    for field, value in updates.items():
        setattr(item, field, value)

    await session.flush()
    return {"id": item.id, "updated_fields": list(updates.keys())}


@router.get("/estimated-quarterly")
async def estimated_quarterly_tax(
    tax_year: int = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Calculate quarterly estimated tax payments based on self-employment and non-withheld income."""
    from pipeline.db.schema import BusinessEntity

    # Get household info for tax rate
    h_result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary.is_(True)).limit(1)
    )
    household = h_result.scalar_one_or_none()
    filing_status = household.filing_status if household else "single"

    # Sum YTD self-employment / non-withheld income
    nec_result = await session.execute(
        select(func.sum(TaxItem.nec_nonemployee_compensation))
        .where(TaxItem.tax_year == tax_year, TaxItem.form_type == "1099-nec")
    )
    nec_total = float(nec_result.scalar() or 0)

    k1_result = await session.execute(
        select(func.sum(TaxItem.k1_ordinary_income))
        .where(TaxItem.tax_year == tax_year, TaxItem.form_type == "k-1")
    )
    k1_total = float(k1_result.scalar() or 0)

    # Business transaction income
    biz_income_result = await session.execute(
        select(func.sum(Transaction.amount))
        .where(
            Transaction.period_year == tax_year,
            Transaction.amount > 0,
            Transaction.effective_segment == "business",
            Transaction.is_excluded.is_(False),
        )
    )
    biz_income = float(biz_income_result.scalar() or 0)

    total_se_income = nec_total + k1_total + biz_income

    # Marginal rate estimation — include other income (K-1, 1099, etc.) for bracket accuracy
    combined_income = ((household.combined_income or 0) + (household.other_income_annual or 0)) if household else 0
    if filing_status in ("married_filing_jointly", "mfj"):
        marginal_rate = 0.32 if combined_income > 340000 else 0.24 if combined_income > 190000 else 0.22
    else:
        marginal_rate = 0.32 if combined_income > 170000 else 0.24 if combined_income > 95000 else 0.22

    se_tax_rate = 0.153  # Self-employment tax
    annual_tax = total_se_income * (marginal_rate + se_tax_rate * 0.5)
    quarterly_amount = round(annual_tax / 4, 2)

    due_dates = [
        {"quarter": 1, "due_date": f"{tax_year}-04-15", "amount": quarterly_amount},
        {"quarter": 2, "due_date": f"{tax_year}-06-15", "amount": quarterly_amount},
        {"quarter": 3, "due_date": f"{tax_year}-09-15", "amount": quarterly_amount},
        {"quarter": 4, "due_date": f"{tax_year + 1}-01-15", "amount": quarterly_amount},
    ]

    return {
        "tax_year": tax_year,
        "total_se_income": round(total_se_income, 2),
        "marginal_rate": marginal_rate,
        "annual_estimated_tax": round(annual_tax, 2),
        "quarterly_amount": quarterly_amount,
        "due_dates": due_dates,
    }
