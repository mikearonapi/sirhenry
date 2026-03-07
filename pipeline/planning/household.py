"""
Household optimization engine for dual-income HENRY couples.
Coordinates filing strategy, retirement contributions, insurance, childcare.
"""
import json
import logging
import math
from dataclasses import dataclass, field
from typing import Optional

from pipeline.tax import (
    federal_tax, standard_deduction as std_deduction,
    marginal_rate as _marginal_rate,
    STANDARD_DEDUCTION,
    FICA_RATE, FICA_SS_CAP,
    HSA_LIMIT, DEP_CARE_FSA_LIMIT,
    CHILD_TAX_CREDIT, CHILD_TAX_CREDIT_PHASEOUT,
    LIMIT_401K,
)

logger = logging.getLogger(__name__)

HSA_FAMILY_LIMIT_2026 = HSA_LIMIT["family"]
HSA_INDIVIDUAL_LIMIT_2026 = HSA_LIMIT["individual"]
FICA_COMBINED_RATE = 0.0765  # employee SS + Medicare combined
ROTH_401K_LIMIT = LIMIT_401K


def _compute_tax(income_a: float, income_b: float, filing: str,
                 deduction_a: float = 0, deduction_b: float = 0,
                 dependents: int = 0) -> float:
    if filing == "mfj":
        combined = income_a + income_b
        taxable = max(0, combined - std_deduction("mfj") - deduction_a - deduction_b)
        tax = federal_tax(taxable, "mfj")
        phaseout = CHILD_TAX_CREDIT_PHASEOUT.get("mfj", 400_000)
        full_ctc = dependents * CHILD_TAX_CREDIT
        reduction = max(0, math.ceil((combined - phaseout) / 1000)) * 50 if combined > phaseout else 0
        tax -= max(0, full_ctc - reduction)
    elif filing == "mfs":
        taxable_a = max(0, income_a - std_deduction("mfs") - deduction_a)
        taxable_b = max(0, income_b - std_deduction("mfs") - deduction_b)
        tax = federal_tax(taxable_a, "mfs") + federal_tax(taxable_b, "mfs")
        # MFS: only one spouse claims dependents; apply CTC once using higher earner's income
        mfs_phaseout = CHILD_TAX_CREDIT_PHASEOUT.get("single", 200_000)
        claiming_income = max(income_a, income_b)
        full_ctc = dependents * CHILD_TAX_CREDIT
        reduction = max(0, math.ceil((claiming_income - mfs_phaseout) / 1000)) * 50 if claiming_income > mfs_phaseout else 0
        tax -= max(0, full_ctc - reduction)
    else:
        taxable = max(0, income_a - std_deduction("single") - deduction_a)
        tax = federal_tax(taxable, "single")
        phaseout = CHILD_TAX_CREDIT_PHASEOUT.get("single", 200_000)
        full_ctc = dependents * CHILD_TAX_CREDIT
        reduction = max(0, math.ceil((income_a - phaseout) / 1000)) * 50 if income_a > phaseout else 0
        tax -= max(0, full_ctc - reduction)
    return max(0, tax)


class HouseholdEngine:

    @staticmethod
    def optimize_filing_status(
        spouse_a_income: float,
        spouse_b_income: float,
        dependents: int = 0,
        state: str = "CA",
    ) -> dict:
        mfj = _compute_tax(spouse_a_income, spouse_b_income, "mfj", dependents=dependents)
        mfs = _compute_tax(spouse_a_income, spouse_b_income, "mfs", dependents=dependents)

        savings = mfs - mfj
        rec = "mfj" if mfj <= mfs else "mfs"

        # MFS disqualification warnings — even if MFS is cheaper on paper,
        # these hidden costs often make MFJ the better choice.
        mfs_warnings: list[str] = []
        combined = spouse_a_income + spouse_b_income
        if rec == "mfs":
            mfs_warnings.append("Roth IRA contributions phased out at $10K MAGI (effectively $0 for MFS)")
            mfs_warnings.append("Student loan interest deduction ($2,500) is disallowed under MFS")
            mfs_warnings.append("Education credits (American Opportunity, Lifetime Learning) are disallowed under MFS")
            if combined > 150_000:
                mfs_warnings.append("Child and Dependent Care Credit is severely limited under MFS")

        result = {
            "mfj_tax": round(mfj, 2),
            "mfs_tax": round(mfs, 2),
            "filing_savings": round(abs(savings), 2),
            "recommendation": rec,
            "explanation": f"Filing {'jointly' if rec == 'mfj' else 'separately'} saves ${abs(savings):,.0f}/year.",
        }
        if mfs_warnings:
            result["mfs_warnings"] = mfs_warnings
        return result

    @staticmethod
    def optimize_retirement_contributions(
        spouse_a_income: float,
        spouse_b_income: float,
        benefits_a: dict,
        benefits_b: dict,
        filing_status: str = "mfj",
    ) -> dict:
        strategy_a: list[dict] = []
        strategy_b: list[dict] = []
        total_savings = 0.0

        for spouse, income, benefits, strategy in [
            ("a", spouse_a_income, benefits_a, strategy_a),
            ("b", spouse_b_income, benefits_b, strategy_b),
        ]:
            # Step 1: Get employer match
            if benefits.get("has_401k"):
                match_pct = benefits.get("employer_match_pct", 0) / 100
                match_limit = benefits.get("employer_match_limit_pct", 6) / 100
                contrib_for_match = income * match_limit
                match_value = contrib_for_match * match_pct
                strategy.append({
                    "action": f"Contribute {match_limit*100:.0f}% to 401(k) for full employer match",
                    "amount": round(contrib_for_match, 2),
                    "savings": round(match_value, 2),
                    "priority": 1,
                })
                total_savings += match_value

            # Step 2: HSA if available
            if benefits.get("has_hsa"):
                plan_type = benefits.get("hsa_plan_type", "family" if filing_status == "mfj" else "individual")
                hsa_limit = HSA_LIMIT.get(plan_type, HSA_FAMILY_LIMIT_2026)
                employer_hsa = benefits.get("hsa_employer_contribution", 0)
                remaining_hsa = hsa_limit - employer_hsa
                marginal = _marginal_rate(income, filing_status)
                tax_saved = remaining_hsa * (marginal + FICA_COMBINED_RATE)
                strategy.append({
                    "action": f"Max HSA (${remaining_hsa:,.0f} after employer contribution)",
                    "amount": round(remaining_hsa, 2),
                    "savings": round(tax_saved, 2),
                    "priority": 2,
                })
                total_savings += tax_saved

            # Step 3: Max out 401k
            if benefits.get("has_401k"):
                marginal = _marginal_rate(income, filing_status)
                roth_available = benefits.get("has_roth_401k", False)
                if income > 200_000 and roth_available:
                    trad_savings = ROTH_401K_LIMIT * marginal
                    strategy.append({
                        "action": "Max Traditional 401(k) to reduce taxable income",
                        "amount": ROTH_401K_LIMIT,
                        "savings": round(trad_savings, 2),
                        "priority": 3,
                    })
                    total_savings += trad_savings
                else:
                    k401_savings = ROTH_401K_LIMIT * marginal
                    strategy.append({
                        "action": "Max 401(k) contributions",
                        "amount": ROTH_401K_LIMIT,
                        "savings": round(k401_savings, 2),
                        "priority": 3,
                    })
                    total_savings += k401_savings

            # Step 4: Mega backdoor Roth if available
            if benefits.get("has_mega_backdoor"):
                mega_limit = benefits.get("mega_backdoor_limit", 46000)
                strategy.append({
                    "action": f"Mega Backdoor Roth (${mega_limit:,.0f} after-tax to Roth)",
                    "amount": mega_limit,
                    "savings": 0,
                    "priority": 4,
                })

            # Step 5: Dep care FSA
            if benefits.get("has_dep_care_fsa"):
                marginal = _marginal_rate(income, filing_status)
                fsa_savings = DEP_CARE_FSA_LIMIT * (marginal + FICA_COMBINED_RATE)
                strategy.append({
                    "action": f"Max Dependent Care FSA (${DEP_CARE_FSA_LIMIT:,.0f})",
                    "amount": DEP_CARE_FSA_LIMIT,
                    "savings": round(fsa_savings, 2),
                    "priority": 5,
                })
                total_savings += fsa_savings

        return {
            "spouse_a_strategy": strategy_a,
            "spouse_b_strategy": strategy_b,
            "total_tax_savings": round(total_savings, 2),
        }

    @staticmethod
    def optimize_insurance(
        benefits_a: dict,
        benefits_b: dict,
        dependents: int = 0,
    ) -> dict:
        a_premium = benefits_a.get("health_premium_monthly", 0) or 0
        b_premium = benefits_b.get("health_premium_monthly", 0) or 0

        a_has_hsa = benefits_a.get("has_hsa", False)
        b_has_hsa = benefits_b.get("has_hsa", False)

        hsa_tax_rate = _marginal_rate(200_000, "mfj") + FICA_COMBINED_RATE
        if a_has_hsa and not b_has_hsa:
            recommendation = "Use Spouse A's plan (HSA-eligible) for the family"
            annual_savings = (b_premium - a_premium) * 12 + HSA_FAMILY_LIMIT_2026 * hsa_tax_rate
        elif b_has_hsa and not a_has_hsa:
            recommendation = "Use Spouse B's plan (HSA-eligible) for the family"
            annual_savings = (a_premium - b_premium) * 12 + HSA_FAMILY_LIMIT_2026 * hsa_tax_rate
        elif a_premium <= b_premium:
            recommendation = "Use Spouse A's plan (lower premium)"
            annual_savings = (b_premium - a_premium) * 12
        else:
            recommendation = "Use Spouse B's plan (lower premium)"
            annual_savings = (a_premium - b_premium) * 12

        return {
            "recommendation": recommendation,
            "estimated_annual_savings": round(annual_savings, 2),
            "hsa_recommendation": "Yes — contribute to HSA for triple tax advantage" if (a_has_hsa or b_has_hsa) else "Consider switching to HDHP plan for HSA eligibility",
        }

    @staticmethod
    def childcare_strategy(
        dependents_json: str,
        income_a: float,
        income_b: float,
        dep_care_fsa_available: bool,
        filing_status: str = "mfj",
    ) -> dict:
        dependents = json.loads(dependents_json) if dependents_json else []
        children_under_13 = [d for d in dependents if d.get("age", 99) < 13]
        total_care_cost = sum(d.get("care_cost_annual", 0) for d in children_under_13)

        lower_income = min(income_a, income_b)
        marginal = _marginal_rate(lower_income, filing_status)

        fsa_savings = 0
        credit_value = 0
        if dep_care_fsa_available and total_care_cost > 0:
            fsa_amount = min(total_care_cost, DEP_CARE_FSA_LIMIT)
            fsa_savings = fsa_amount * (marginal + FICA_COMBINED_RATE)

        if total_care_cost > 0 and not dep_care_fsa_available:
            credit_rate = 0.20
            credit_value = min(total_care_cost, 6000) * credit_rate

        net_second_income = lower_income - total_care_cost - (lower_income * FICA_COMBINED_RATE) - (lower_income * marginal)

        return {
            "children_under_13": len(children_under_13),
            "total_annual_childcare": round(total_care_cost, 2),
            "fsa_tax_savings": round(fsa_savings, 2),
            "child_care_credit": round(credit_value, 2),
            "net_second_income_after_childcare": round(net_second_income, 2),
            "recommendation": "Use Dependent Care FSA" if fsa_savings > credit_value else "Claim Child and Dependent Care Credit",
        }

    @staticmethod
    def full_optimization(
        spouse_a_income: float,
        spouse_b_income: float,
        benefits_a: dict,
        benefits_b: dict,
        dependents_json: str = "[]",
        state: str = "CA",
    ) -> dict:
        dependents = json.loads(dependents_json) if dependents_json else []
        n_dep = len(dependents)

        filing = HouseholdEngine.optimize_filing_status(spouse_a_income, spouse_b_income, n_dep, state)
        retirement = HouseholdEngine.optimize_retirement_contributions(
            spouse_a_income, spouse_b_income, benefits_a, benefits_b, filing["recommendation"],
        )
        insurance = HouseholdEngine.optimize_insurance(benefits_a, benefits_b, n_dep)
        childcare = HouseholdEngine.childcare_strategy(
            dependents_json, spouse_a_income, spouse_b_income,
            benefits_a.get("has_dep_care_fsa", False) or benefits_b.get("has_dep_care_fsa", False),
            filing["recommendation"],
        )

        total_savings = (
            filing["filing_savings"] +
            retirement["total_tax_savings"] +
            insurance["estimated_annual_savings"] +
            childcare["fsa_tax_savings"]
        )

        recommendations = []
        if filing["filing_savings"] > 0:
            recommendations.append({"area": "Filing Status", "action": filing["explanation"], "savings": filing["filing_savings"]})
        recommendations.append({"area": "Retirement", "action": f"Coordinate retirement contributions", "savings": retirement["total_tax_savings"]})
        if insurance["estimated_annual_savings"] > 0:
            recommendations.append({"area": "Insurance", "action": insurance["recommendation"], "savings": insurance["estimated_annual_savings"]})
        if childcare["fsa_tax_savings"] > 0:
            recommendations.append({"area": "Childcare", "action": childcare["recommendation"], "savings": childcare["fsa_tax_savings"]})

        return {
            "filing": filing,
            "retirement": retirement,
            "insurance": insurance,
            "childcare": childcare,
            "total_annual_savings": round(total_savings, 2),
            "recommendations": recommendations,
        }
