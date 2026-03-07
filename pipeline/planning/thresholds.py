"""
Tax threshold monitor for dual-income (HENRY) households.

Calculates proximity to key federal tax thresholds: Additional Medicare Tax,
NIIT, Roth IRA phase-out, Child Tax Credit phase-out, SALT cap, and AMT.
"""

from pipeline.tax.calculator import federal_tax, standard_deduction
from pipeline.tax.constants import (
    ADDITIONAL_MEDICARE_THRESHOLD,
    AMT_EXEMPTION,
    CHILD_TAX_CREDIT,
    CHILD_TAX_CREDIT_PHASEOUT,
    MFJ_BRACKETS,
    NIIT_RATE,
    NIIT_THRESHOLD,
    ROTH_INCOME_PHASEOUT,
    ROTH_INCOME_PHASEOUT_END,
    SALT_CAP,
    STANDARD_DEDUCTION,
)


def compute_tax_thresholds(
    spouse_a_income: float,
    spouse_b_income: float,
    capital_gains: float = 0,
    qualified_dividends: float = 0,
    pre_tax_deductions: float = 0,
    filing_status: str = "mfj",
    dependents: int = 0,
) -> dict:
    """Compute proximity to key HENRY tax thresholds for a dual-income household.

    Returns a dict matching the API response shape for /tax-thresholds.
    """
    combined = spouse_a_income + spouse_b_income
    magi_estimate = combined + capital_gains + qualified_dividends - pre_tax_deductions

    thresholds: list[dict] = []

    # 1. Additional Medicare Tax (0.9%)
    amt_threshold = ADDITIONAL_MEDICARE_THRESHOLD.get(filing_status, 200_000)
    amt_exposure = max(0, magi_estimate - amt_threshold)
    thresholds.append({
        "id": "additional_medicare",
        "label": "Additional Medicare Tax (0.9%)",
        "threshold": amt_threshold,
        "current_magi": magi_estimate,
        "exposure": round(amt_exposure),
        "tax_impact": round(amt_exposure * 0.009),
        "proximity_pct": min(100, round((magi_estimate / amt_threshold) * 100, 1)),
        "exceeded": magi_estimate > amt_threshold,
        "description": (
            "An extra 0.9% Medicare tax applies to wages and self-employment income above "
            "this threshold. Cannot be avoided through pre-tax deductions (applies to wages, "
            "not MAGI)."
        ),
        "actions": [
            "No direct avoidance — this is on wages/SE income",
            "Ensure proper withholding to avoid underpayment penalty",
            "Track via W-2 Box 6 and Form 8959 at filing",
        ],
    })

    # 2. Net Investment Income Tax (3.8%)
    niit_threshold = NIIT_THRESHOLD.get(filing_status, 200_000)
    investment_income = capital_gains + qualified_dividends
    niit_exposure = min(investment_income, max(0, magi_estimate - niit_threshold))
    thresholds.append({
        "id": "niit",
        "label": "Net Investment Income Tax / NIIT (3.8%)",
        "threshold": niit_threshold,
        "current_magi": magi_estimate,
        "exposure": round(niit_exposure),
        "tax_impact": round(niit_exposure * NIIT_RATE),
        "proximity_pct": min(100, round((magi_estimate / niit_threshold) * 100, 1)),
        "exceeded": magi_estimate > niit_threshold,
        "description": (
            "3.8% surtax on net investment income (dividends, interest, capital gains) "
            "when MAGI exceeds threshold. Reducing MAGI below threshold eliminates it."
        ),
        "actions": [
            "Maximize 401k, HSA, and pre-tax deductions to reduce MAGI",
            "Harvest capital losses to offset gains",
            "Consider tax-exempt municipal bonds for investment income",
            "Shift investments to deferred accounts where possible",
        ],
    })

    # 3. Roth IRA Phase-out
    roth_start = ROTH_INCOME_PHASEOUT.get(filing_status, 150_000)
    roth_end = ROTH_INCOME_PHASEOUT_END.get(filing_status, 165_000)
    roth_reduced = magi_estimate > roth_start
    roth_eliminated = magi_estimate >= roth_end
    status_label = "MFJ" if filing_status == "mfj" else "Single"
    thresholds.append({
        "id": "roth_ira",
        "label": "Roth IRA Direct Contribution Limit",
        "threshold": roth_start,
        "threshold_end": roth_end,
        "current_magi": magi_estimate,
        "exposure": 0,
        "tax_impact": 0,
        "proximity_pct": min(100, round((magi_estimate / roth_start) * 100, 1)),
        "exceeded": roth_eliminated,
        "partially_exceeded": roth_reduced and not roth_eliminated,
        "description": (
            f"Direct Roth IRA contributions phase out between ${roth_start:,} and "
            f"${roth_end:,} MAGI ({status_label}). Above the upper limit, direct "
            "contributions are not allowed."
        ),
        "actions": [
            "Use the Backdoor Roth IRA strategy (Traditional IRA → convert to Roth) if over the limit",
            "Mega Backdoor Roth via after-tax 401k contributions if your plan allows",
            "Pre-tax deductions (401k, HSA) reduce MAGI and may restore eligibility",
        ],
    })

    # 4. Child Tax Credit Phase-out ($400k MFJ)
    ctc_threshold = CHILD_TAX_CREDIT_PHASEOUT.get(filing_status, 200_000)
    if dependents > 0:
        ctc_excess = max(0, magi_estimate - ctc_threshold)
        ctc_reduction = min(dependents * CHILD_TAX_CREDIT, (ctc_excess / 1000) * 50)
        thresholds.append({
            "id": "child_tax_credit",
            "label": "Child Tax Credit Phase-out",
            "threshold": ctc_threshold,
            "current_magi": magi_estimate,
            "exposure": round(ctc_excess),
            "tax_impact": round(ctc_reduction),
            "proximity_pct": min(100, round((magi_estimate / ctc_threshold) * 100, 1)),
            "exceeded": magi_estimate > ctc_threshold,
            "description": (
                f"The ${dependents * CHILD_TAX_CREDIT:,} Child Tax Credit reduces by $50 "
                f"for every $1,000 of income above ${ctc_threshold:,} (MFJ). "
                f"With {dependents} dependent(s), estimated credit reduction: "
                f"${ctc_reduction:,.0f}."
            ),
            "actions": [
                "Maximize pre-tax deductions to reduce MAGI below the threshold",
                "401k, HSA, and FSA contributions all reduce MAGI",
            ],
        })

    # 5. SALT Cap ($10,000)
    estimated_salt = magi_estimate * 0.05  # rough 5% effective state+local rate
    thresholds.append({
        "id": "salt_cap",
        "label": f"SALT Deduction Cap (${SALT_CAP:,})",
        "threshold": SALT_CAP,
        "current_magi": magi_estimate,
        "exposure": 0,
        "tax_impact": 0,
        "proximity_pct": min(100, round((estimated_salt / SALT_CAP) * 100, 1)),
        "exceeded": estimated_salt > SALT_CAP,
        "description": (
            "State and local tax (SALT) deductions are capped at $10,000 for itemizers. "
            "High earners in high-tax states typically cannot deduct their full state tax "
            "bill. Standard deduction is $30,000 MFJ (2025) — compare before itemizing."
        ),
        "actions": [
            "Verify whether itemizing or standard deduction is more beneficial",
            "Bunch deductions in alternating years (mortgage interest + SALT + charitable)",
            "Consider Donor Advised Fund to front-load charitable deductions in high-income years",
        ],
    })

    # 6. AMT Exposure (simplified check)
    amt_exemption = AMT_EXEMPTION.get(filing_status, 88_100)
    # Rough AMT income = MAGI - pre_tax_deductions + some add-backs
    amt_income_est = magi_estimate + pre_tax_deductions  # rough
    amt_taxable_est = max(0, amt_income_est - amt_exemption)
    amt_tax_est = amt_taxable_est * 0.26  # 26% AMT rate below $232k, 28% above
    std_ded = STANDARD_DEDUCTION.get(filing_status, STANDARD_DEDUCTION["single"])
    # magi_estimate already has pre_tax_deductions subtracted, so only subtract std_ded
    regular_tax = federal_tax(
        max(0, magi_estimate - std_ded), filing_status
    )
    amt_applies = amt_tax_est > regular_tax and amt_taxable_est > 0
    thresholds.append({
        "id": "amt",
        "label": "Alternative Minimum Tax (AMT)",
        "threshold": amt_exemption,
        "current_magi": magi_estimate,
        "exposure": round(max(0, amt_tax_est - regular_tax)) if amt_applies else 0,
        "tax_impact": round(max(0, amt_tax_est - regular_tax)) if amt_applies else 0,
        "proximity_pct": min(100, round((amt_income_est / (amt_exemption + 200_000)) * 100, 1)),
        "exceeded": amt_applies,
        "description": (
            "The AMT is a parallel tax system that disallows many deductions. "
            "Most relevant for ISO stock option holders — exercising ISOs triggers AMT "
            "preference items. Also triggered by high miscellaneous itemized deductions."
        ),
        "actions": [
            "ISO holders: run AMT crossover analysis before exercising options",
            "Spread ISO exercises across tax years to stay below AMT",
            "Check Form 6251 at filing to understand AMT exposure",
            "AMT credits from prior-year exercise can offset future regular tax",
        ],
    })

    # Summary metrics
    exceeded_count = sum(1 for t in thresholds if t.get("exceeded"))
    total_estimated_impact = sum(t.get("tax_impact", 0) for t in thresholds if t.get("exceeded"))

    return {
        "combined_income": combined,
        "magi_estimate": round(magi_estimate),
        "filing_status": filing_status,
        "thresholds": thresholds,
        "exceeded_count": exceeded_count,
        "total_estimated_additional_tax": total_estimated_impact,
        "note": "MAGI estimates are approximate. Consult a tax professional for precise calculations.",
    }
