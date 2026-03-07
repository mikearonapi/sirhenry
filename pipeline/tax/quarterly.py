"""
Calculate quarterly estimated tax payments based on self-employment
and non-withheld income.

Uses NEC forms, K-1 ordinary income, and business transaction income
to estimate the annual SE tax liability, then divides into four
quarterly payment amounts with their due dates.
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import HouseholdProfile, TaxItem, Transaction
from pipeline.tax.calculator import marginal_rate as _marginal_rate
from pipeline.tax.constants import SE_TAX_DEDUCTION_FACTOR


async def compute_quarterly_estimate(session: AsyncSession, tax_year: int) -> dict:
    """
    Calculate quarterly estimated tax payments for the given tax year.

    Returns a dict with tax_year, total_se_income, marginal_rate,
    annual_estimated_tax, quarterly_amount, and due_dates list.
    """
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

    # Marginal rate — use proper bracket lookup from constants
    # Floor at 22%: anyone with SE income is likely in at least the 22% bracket
    combined_income = ((household.combined_income or 0) + (household.other_income_annual or 0)) if household else 0
    marginal_rate = max(0.22, _marginal_rate(combined_income, filing_status))

    # SE tax: apply 92.35% factor, then 15.3% rate; half of SE tax is deductible
    se_taxable = total_se_income * SE_TAX_DEDUCTION_FACTOR
    se_tax = se_taxable * 0.153
    half_se_deduction = se_tax * 0.5
    income_tax = (total_se_income - half_se_deduction) * marginal_rate
    annual_tax = se_tax + income_tax
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
