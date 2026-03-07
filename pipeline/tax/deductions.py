"""
Generate smart deduction opportunity suggestions based on the user's
tax estimate, self-employment status, business expenses, and benefits.

Each opportunity is framed as "money leaves your account either way —
IRS or as a business asset/deduction" to help HENRYs make informed
year-end spending decisions.
"""
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import BenefitPackage, HouseholdProfile, Transaction
from pipeline.tax.constants import HSA_LIMIT, LIMIT_401K
from pipeline.tax.tax_estimate import compute_tax_estimate


async def compute_deduction_opportunities(
    session: AsyncSession,
    tax_year: int,
) -> dict:
    """
    Compute deduction opportunity insights for the given tax year.

    Returns a dict matching the TaxDeductionInsightsOut schema fields:
    tax_year, estimated_balance_due, effective_rate, marginal_rate,
    opportunities (list of dicts), summary, data_source.
    """
    estimate = await compute_tax_estimate(session, tax_year)
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

    opportunities: list[dict] = []
    mrate = marginal_rate / 100

    # --- Vehicle / Section 179 ---
    if se_income > 0 or total_biz_expenses > 0:
        vehicle_deduction = 30500  # approx bonus depreciation / Section 179 for SUV > 6000 lbs
        vehicle_savings_low = round(vehicle_deduction * mrate * 0.5, 2)
        vehicle_savings_high = round(vehicle_deduction * mrate, 2)
        opportunities.append({
            "id": "vehicle_179",
            "title": "Business Vehicle (Section 179 Deduction)",
            "description": (
                "Purchase or lease a vehicle used for business. SUVs over 6,000 lbs GVW qualify "
                "for up to $30,500 first-year Section 179 deduction. Even a mixed-use vehicle "
                "deducts the business-use percentage. Instead of that money going to the IRS, "
                "you get a business asset."
            ),
            "category": "vehicle",
            "estimated_tax_savings_low": vehicle_savings_low,
            "estimated_tax_savings_high": vehicle_savings_high,
            "estimated_cost": 45000,
            "net_benefit_explanation": (
                f"A $45K vehicle at {marginal_rate}% marginal rate saves ~${vehicle_savings_high:,.0f} in taxes. "
                f"The money leaves your account either way — it's either a depreciating asset you use, or a check to the IRS."
            ),
            "urgency": "medium",
            "deadline": f"Dec 31, {tax_year}" if datetime.now(timezone.utc).year == tax_year else None,
        })

    # --- Equipment / Technology (Section 179) ---
    if se_income > 0 or total_biz_expenses > 0:
        equip_cost = 5000
        equip_savings = round(equip_cost * mrate, 2)
        opportunities.append({
            "id": "equipment_179",
            "title": "Business Equipment & Technology",
            "description": (
                "Computers, monitors, software, servers, and other business equipment qualify "
                "for full Section 179 expensing in the year of purchase. If you need it for "
                "your business, buying before year-end converts a tax payment into a productive asset."
            ),
            "category": "equipment",
            "estimated_tax_savings_low": round(equip_cost * mrate * 0.5, 2),
            "estimated_tax_savings_high": equip_savings,
            "estimated_cost": equip_cost,
            "net_benefit_explanation": (
                f"$5K in business equipment at {marginal_rate}% saves ~${equip_savings:,.0f}. "
                f"You get tools you need AND reduce your tax bill."
            ),
            "urgency": "medium",
            "deadline": f"Dec 31, {tax_year}" if datetime.now(timezone.utc).year == tax_year else None,
        })

    # --- Retirement: SEP-IRA ---
    if se_income > 0:
        sep_limit = min(se_income * 0.25, 70000)
        sep_savings_low = round(sep_limit * 0.5 * mrate, 2)
        sep_savings_high = round(sep_limit * mrate, 2)
        opportunities.append({
            "id": "sep_ira",
            "title": "SEP-IRA Contribution",
            "description": (
                f"With ${se_income:,.0f} in self-employment income, you can contribute up to "
                f"${sep_limit:,.0f} to a SEP-IRA (25% of net SE income, max $70,000). "
                f"This is an above-the-line deduction — it reduces AGI directly. "
                f"The money goes into your retirement account instead of to the IRS."
            ),
            "category": "retirement",
            "estimated_tax_savings_low": sep_savings_low,
            "estimated_tax_savings_high": sep_savings_high,
            "estimated_cost": round(sep_limit, 2),
            "net_benefit_explanation": (
                f"Contributing ${sep_limit:,.0f} to a SEP-IRA saves ${sep_savings_high:,.0f} in taxes "
                f"AND builds retirement wealth. The money is yours, not the government's."
            ),
            "urgency": "high",
            "deadline": f"Apr 15, {tax_year + 1} (with extension: Oct 15, {tax_year + 1})",
        })

    # --- 401(k) Maximization ---
    max_401k = LIMIT_401K
    savings_401k = round(max_401k * mrate, 2)
    opportunities.append({
        "id": "maximize_401k",
        "title": "Maximize 401(k) Contributions",
        "description": (
            f"The 2025 401(k) employee contribution limit is $23,500 ($31,000 if age 50+). "
            f"Every dollar contributed reduces your taxable income dollar-for-dollar. "
            f"If you haven't maxed out, increasing contributions before year-end is one of the "
            f"simplest ways to lower your tax bill."
        ),
        "category": "retirement",
        "estimated_tax_savings_low": round(savings_401k * 0.5, 2),
        "estimated_tax_savings_high": savings_401k,
        "estimated_cost": max_401k,
        "net_benefit_explanation": (
            f"Maxing your 401(k) at {marginal_rate}% marginal rate saves up to ${savings_401k:,.0f} in taxes. "
            f"The money grows tax-deferred in your retirement account."
        ),
        "urgency": "high",
        "deadline": f"Dec 31, {tax_year}",
    })

    # --- HSA ---
    hsa_family_limit = HSA_LIMIT["family"]
    hsa_savings = round(hsa_family_limit * mrate, 2)
    hsa_note = "" if has_hsa_eligible else " Note: No HDHP found in your benefits — update your benefits in Setup if you have one."
    opportunities.append({
        "id": "hsa_contribution",
        "title": "HSA Contribution" + (" (HDHP enrolled)" if has_hsa_eligible else " (requires HDHP)"),
        "description": (
            "If enrolled in a High Deductible Health Plan, you can contribute up to "
            f"$8,550 (family, 2025) to an HSA. Triple tax advantage: deductible going in, "
            f"tax-free growth, tax-free withdrawals for medical expenses.{hsa_note}"
        ),
        "category": "other",
        "estimated_tax_savings_low": round(hsa_savings * 0.5, 2),
        "estimated_tax_savings_high": hsa_savings,
        "estimated_cost": hsa_family_limit,
        "net_benefit_explanation": (
            f"Full HSA contribution saves ~${hsa_savings:,.0f} in taxes while building a medical expense fund."
        ),
        "urgency": "medium",
        "deadline": f"Apr 15, {tax_year + 1}",
        "applicable": has_hsa_eligible,
    })

    # --- Home Office ---
    home_office_current = biz_expenses.get("Home Office", 0) + biz_expenses.get("Office Expenses", 0)
    if se_income > 0 and home_office_current < 1500:
        ho_deduction = 1500  # simplified method max
        ho_savings = round(ho_deduction * mrate, 2)
        opportunities.append({
            "id": "home_office",
            "title": "Home Office Deduction",
            "description": (
                "If you use a dedicated space in your home for business, claim the home office "
                "deduction. Simplified method: $5/sq ft up to 300 sq ft ($1,500). Regular method "
                "may yield more based on actual expenses (mortgage interest, utilities, insurance)."
            ),
            "category": "home_office",
            "estimated_tax_savings_low": round(ho_savings * 0.5, 2),
            "estimated_tax_savings_high": round(ho_deduction * 2 * mrate, 2),
            "net_benefit_explanation": (
                f"Home office deduction of $1,500–$3,000+ saves ${ho_savings:,.0f}–${round(ho_deduction*2*mrate):,.0f} in taxes "
                f"with no additional out-of-pocket cost — you already pay for your home."
            ),
            "urgency": "medium",
            "deadline": f"Filed with return",
        })

    # --- Charitable (DAF) ---
    if agi > 200000:
        daf_amount = 10000
        daf_savings = round(daf_amount * mrate, 2)
        opportunities.append({
            "id": "charitable_daf",
            "title": "Donor-Advised Fund (DAF) Contribution",
            "description": (
                "Contribute appreciated stock or cash to a DAF to get an immediate tax deduction. "
                "You can distribute the funds to charities over time. Bunching multiple years of "
                "giving into one year can push you above the standard deduction threshold if itemizing."
            ),
            "category": "charitable",
            "estimated_tax_savings_low": round(daf_savings * 0.5, 2),
            "estimated_tax_savings_high": daf_savings,
            "estimated_cost": daf_amount,
            "net_benefit_explanation": (
                f"A ${daf_amount:,.0f} DAF contribution at {marginal_rate}% saves ~${daf_savings:,.0f}. "
                f"You control when charities receive the funds while locking in this year's deduction."
            ),
            "urgency": "low",
            "deadline": f"Dec 31, {tax_year}",
        })

    # --- Education / Professional Development ---
    if se_income > 0 or total_biz_expenses > 0:
        edu_cost = 3000
        edu_savings = round(edu_cost * mrate, 2)
        opportunities.append({
            "id": "education_training",
            "title": "Professional Development & Education",
            "description": (
                "Courses, certifications, conferences, and professional books related to your "
                "business are fully deductible. Invest in yourself instead of paying the IRS."
            ),
            "category": "education",
            "estimated_tax_savings_low": round(edu_savings * 0.5, 2),
            "estimated_tax_savings_high": edu_savings,
            "estimated_cost": edu_cost,
            "net_benefit_explanation": (
                f"$3K in business education at {marginal_rate}% saves ~${edu_savings:,.0f} in taxes "
                f"while increasing your earning potential."
            ),
            "urgency": "low",
            "deadline": f"Dec 31, {tax_year}",
        })

    # --- Backdoor Roth IRA ---
    if agi > 230000:
        opportunities.append({
            "id": "backdoor_roth",
            "title": "Backdoor Roth IRA Conversion",
            "description": (
                "At your income level, direct Roth IRA contributions are phased out. "
                "A backdoor Roth (contribute to traditional IRA, then convert) lets you put "
                "$7,000/person into a Roth IRA for tax-free growth. Not a deduction, but "
                "shields future gains from taxation permanently."
            ),
            "category": "retirement",
            "estimated_tax_savings_low": 0,
            "estimated_tax_savings_high": 0,
            "estimated_cost": 14000,
            "net_benefit_explanation": (
                "No immediate tax savings, but $14K/year ($7K each spouse) grows completely "
                "tax-free forever. At your marginal rate, the long-term value is substantial."
            ),
            "urgency": "medium",
            "deadline": f"Apr 15, {tax_year + 1}",
            "applicable": True,
        })

    # Build summary
    if balance_due > 0:
        total_potential = sum(o["estimated_tax_savings_high"] for o in opportunities)
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

    return {
        "tax_year": tax_year,
        "estimated_balance_due": balance_due,
        "effective_rate": effective_rate,
        "marginal_rate": marginal_rate,
        "opportunities": opportunities,
        "summary": summary_text,
        "data_source": est_data_source,
    }
