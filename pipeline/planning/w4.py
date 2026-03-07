"""
W-4 withholding optimization for dual-income households.

Dual earners systematically under-withhold because each employer treats
the other spouse's income as $0 when calculating withholding.
"""

from pipeline.tax.calculator import federal_tax, marginal_rate, standard_deduction
from pipeline.tax.constants import (
    MFJ_BRACKETS,
    SINGLE_BRACKETS,
    STANDARD_DEDUCTION,
)


def compute_w4_recommendations(
    spouse_a_income: float,
    spouse_b_income: float,
    spouse_a_pay_periods: int = 26,
    spouse_b_pay_periods: int = 26,
    other_income: float = 0,
    pre_tax_deductions_a: float = 0,
    pre_tax_deductions_b: float = 0,
    filing_status: str = "mfj",
) -> dict:
    """Compute W-4 withholding recommendations for a dual-income household.

    Returns a dict matching the API response shape for /w4-optimization.
    """
    combined = spouse_a_income + spouse_b_income + other_income

    std_ded = STANDARD_DEDUCTION.get(filing_status, STANDARD_DEDUCTION["single"])
    single_std_ded = STANDARD_DEDUCTION["single"]

    # Actual MFJ tax owed
    taxable_mfj = max(0, combined - std_ded - pre_tax_deductions_a - pre_tax_deductions_b)
    actual_tax = federal_tax(taxable_mfj, filing_status)

    # What each spouse will withhold (employer calculates as if single)
    taxable_a_as_single = max(0, spouse_a_income - single_std_ded - pre_tax_deductions_a)
    taxable_b_as_single = max(0, spouse_b_income - single_std_ded - pre_tax_deductions_b)
    withheld_a = federal_tax(taxable_a_as_single, "single")
    withheld_b = federal_tax(taxable_b_as_single, "single")
    total_withheld = withheld_a + withheld_b

    shortfall = actual_tax - total_withheld

    # Per-paycheck extra withholding to cover the shortfall
    extra_per_paycheck_a = (
        max(0, (shortfall / 2) / spouse_a_pay_periods) if spouse_a_pay_periods > 0 else 0
    )
    extra_per_paycheck_b = (
        max(0, (shortfall / 2) / spouse_b_pay_periods) if spouse_b_pay_periods > 0 else 0
    )

    marg = marginal_rate(taxable_mfj, filing_status)

    recommendation_lines: list[str] = []
    if shortfall > 500:
        recommendation_lines.append(
            f"Your combined withholding is estimated to be short by {shortfall:,.0f}. "
            f"To avoid an underpayment penalty, consider adding extra withholding."
        )
        recommendation_lines.append(
            f"Spouse A: Add ~${extra_per_paycheck_a:,.0f} per paycheck (W-4 Step 4c)."
        )
        recommendation_lines.append(
            f"Spouse B: Add ~${extra_per_paycheck_b:,.0f} per paycheck (W-4 Step 4c)."
        )
        recommendation_lines.append(
            "Alternatively, use the IRS Tax Withholding Estimator at irs.gov/W4app for a precise calculation."
        )
    elif shortfall > 0:
        recommendation_lines.append(
            f"Minor shortfall of ~${shortfall:,.0f} estimated — within safe harbor threshold."
        )
    else:
        recommendation_lines.append("Withholding appears sufficient. You may receive a refund.")

    return {
        "spouse_a_income": spouse_a_income,
        "spouse_b_income": spouse_b_income,
        "combined_income": combined,
        "estimated_mfj_tax": round(actual_tax, 0),
        "estimated_withheld_a": round(withheld_a, 0),
        "estimated_withheld_b": round(withheld_b, 0),
        "total_estimated_withheld": round(total_withheld, 0),
        "estimated_shortfall": round(shortfall, 0),
        "extra_per_paycheck_a": round(extra_per_paycheck_a, 0),
        "extra_per_paycheck_b": round(extra_per_paycheck_b, 0),
        "marginal_rate": marg,
        "effective_rate": round(actual_tax / combined, 4) if combined > 0 else 0,
        "recommendation": " ".join(recommendation_lines),
        "recommendation_lines": recommendation_lines,
    }
