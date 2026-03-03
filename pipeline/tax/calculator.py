"""
Shared tax calculation functions used by all planning engines and API routes.
Single source of truth — do NOT duplicate this logic elsewhere.
"""
import math

from .constants import (
    MFJ_BRACKETS, SINGLE_BRACKETS, MFS_BRACKETS, HOH_BRACKETS,
    STANDARD_DEDUCTION, FICA_SS_CAP, FICA_RATE, MEDICARE_RATE,
    SE_TAX_DEDUCTION_FACTOR, NIIT_RATE, NIIT_THRESHOLD,
    AMT_EXEMPTION, AMT_PHASEOUT, AMT_RATE_LOW, AMT_RATE_HIGH, AMT_RATE_THRESHOLD,
    STATE_TAX_RATES, ADDITIONAL_MEDICARE_RATE, ADDITIONAL_MEDICARE_THRESHOLD,
)


def get_brackets(filing_status: str) -> list[tuple[float, float]]:
    """Return the bracket table for the given filing status."""
    return {
        "mfj": MFJ_BRACKETS, "married": MFJ_BRACKETS,
        "mfs": MFS_BRACKETS,
        "single": SINGLE_BRACKETS,
        "hoh": HOH_BRACKETS,
    }.get(filing_status, MFJ_BRACKETS)


def standard_deduction(filing_status: str) -> float:
    return STANDARD_DEDUCTION.get(filing_status, 15_000)


def federal_tax(taxable_income: float, filing_status: str = "mfj") -> float:
    """Compute federal income tax from taxable income (after deductions)."""
    brackets = get_brackets(filing_status)
    tax = 0.0
    prev = 0.0
    for ceiling, rate in brackets:
        if taxable_income <= prev:
            break
        tax += (min(taxable_income, ceiling) - prev) * rate
        prev = ceiling
    return max(0.0, tax)


def marginal_rate(taxable_income: float, filing_status: str = "mfj") -> float:
    """Return the marginal federal rate for the given taxable income."""
    for ceiling, rate in get_brackets(filing_status):
        if taxable_income <= ceiling:
            return rate
    return 0.37


def fica_tax(wages: float, filing_status: str = "mfj") -> float:
    """Employee share of FICA (Social Security + Medicare) on W-2 wages,
    including the Additional Medicare Tax (0.9%) above the threshold."""
    ss = min(wages, FICA_SS_CAP) * FICA_RATE
    med = wages * MEDICARE_RATE
    threshold = ADDITIONAL_MEDICARE_THRESHOLD.get(filing_status, 200_000)
    additional_med = max(0, wages - threshold) * ADDITIONAL_MEDICARE_RATE
    return ss + med + additional_med


def se_tax(net_se_income: float, filing_status: str = "mfj") -> float:
    """Self-employment tax on Schedule C / 1099 net income,
    including the Additional Medicare Tax (0.9%) above the threshold."""
    se_base = net_se_income * SE_TAX_DEDUCTION_FACTOR
    ss = min(se_base, FICA_SS_CAP) * 0.124
    med = se_base * 0.029
    threshold = ADDITIONAL_MEDICARE_THRESHOLD.get(filing_status, 200_000)
    additional_med = max(0, se_base - threshold) * ADDITIONAL_MEDICARE_RATE
    return ss + med + additional_med


def niit_tax(agi: float, investment_income: float, filing_status: str = "mfj") -> float:
    """Net Investment Income Tax — 3.8% on lesser of NII or AGI above threshold."""
    threshold = NIIT_THRESHOLD.get(filing_status, 200_000)
    excess = max(0, agi - threshold)
    return min(excess, investment_income) * NIIT_RATE


def amt_tax(amti: float, filing_status: str = "mfj") -> float:
    """Tentative minimum tax from Alternative Minimum Taxable Income."""
    exemption = AMT_EXEMPTION.get(filing_status, 85_700)
    phaseout = AMT_PHASEOUT.get(filing_status, 609_350)
    effective_exemption = max(0, exemption - max(0, amti - phaseout) * 0.25)
    amt_base = max(0, amti - effective_exemption)
    if amt_base <= AMT_RATE_THRESHOLD:
        return amt_base * AMT_RATE_LOW
    return AMT_RATE_THRESHOLD * AMT_RATE_LOW + (amt_base - AMT_RATE_THRESHOLD) * AMT_RATE_HIGH


def state_tax(income: float, state: str = "CA") -> float:
    """Simplified state income tax using top marginal rate."""
    rate = STATE_TAX_RATES.get(state.upper(), 0.05)
    return income * rate


def total_tax_estimate(
    w2_wages: float = 0,
    se_income: float = 0,
    investment_income: float = 0,
    other_income: float = 0,
    filing_status: str = "mfj",
    state_code: str = "CA",
    dependents: int = 0,
) -> dict:
    """Full tax estimate combining all sources — returns a breakdown dict."""
    gross = w2_wages + se_income + investment_income + other_income
    deduction = standard_deduction(filing_status)
    se_deduction = se_tax(se_income, filing_status) / 2 if se_income > 0 else 0
    taxable = max(0, gross - deduction - se_deduction)

    fed = federal_tax(taxable, filing_status)
    fica = fica_tax(w2_wages, filing_status)
    se = se_tax(se_income, filing_status) if se_income > 0 else 0
    agi = gross - se_deduction
    nii = niit_tax(agi, investment_income, filing_status)
    st = state_tax(agi, state_code)

    from .constants import CHILD_TAX_CREDIT, CHILD_TAX_CREDIT_PHASEOUT
    ctc = 0
    if dependents > 0:
        phaseout = CHILD_TAX_CREDIT_PHASEOUT.get(filing_status, 200_000)
        full_ctc = dependents * CHILD_TAX_CREDIT
        reduction = max(0, math.ceil((gross - phaseout) / 1000)) * 50 if gross > phaseout else 0
        ctc = max(0, full_ctc - reduction)

    total = fed + fica + se + nii + st - ctc
    effective = total / gross if gross > 0 else 0

    return {
        "gross_income": round(gross, 2),
        "taxable_income": round(taxable, 2),
        "federal_tax": round(fed, 2),
        "fica_tax": round(fica, 2),
        "se_tax": round(se, 2),
        "niit": round(nii, 2),
        "state_tax": round(st, 2),
        "child_tax_credit": round(ctc, 2),
        "total_tax": round(total, 2),
        "effective_rate": round(effective, 4),
        "marginal_rate": marginal_rate(taxable, filing_status),
    }
