"""
Tax modeling engine for interactive strategy simulation.
Roth conversions, backdoor Roth, S-Corp, DAF bunching, student loans, multi-year projections.
"""
import logging
import math
from dataclasses import dataclass

from pipeline.tax import (
    federal_tax as _fed_tax,
    marginal_rate as _marginal,
    standard_deduction as _std_deduction,
    get_brackets as _brackets,
    FICA_SS_CAP, SE_TAX_DEDUCTION_FACTOR,
    ROTH_INCOME_PHASEOUT,
)

logger = logging.getLogger(__name__)


class TaxModelingEngine:

    @staticmethod
    def roth_conversion_ladder(
        traditional_balance: float,
        current_income: float,
        filing_status: str = "mfj",
        years: int = 10,
        target_bracket_rate: float = 0.24,
        growth_rate: float = 0.07,
    ) -> dict:
        brackets = _brackets(filing_status)
        deduction = _std_deduction(filing_status)

        # Find the top of the target bracket
        target_ceiling = 0
        for ceiling, rate in brackets:
            if rate >= target_bracket_rate:
                target_ceiling = ceiling + deduction
                break

        year_by_year = []
        remaining = traditional_balance
        roth = 0.0
        total_tax = 0.0

        for y in range(years):
            income = current_income * ((1.02) ** y)
            room = max(0, target_ceiling - income)
            conversion = min(remaining, room)

            taxable_before = max(0, income - deduction)
            taxable_after = max(0, income + conversion - deduction)
            tax_on_conversion = _fed_tax(taxable_after, filing_status) - _fed_tax(taxable_before, filing_status)

            remaining -= conversion
            remaining *= (1 + growth_rate)
            roth += conversion
            roth *= (1 + growth_rate)
            total_tax += tax_on_conversion

            year_by_year.append({
                "year": y + 1,
                "conversion_amount": round(conversion, 2),
                "tax_on_conversion": round(tax_on_conversion, 2),
                "marginal_rate": _marginal(taxable_after, filing_status),
                "effective_conversion_rate": round(tax_on_conversion / conversion, 4) if conversion > 0 else 0,
                "remaining_traditional": round(remaining, 2),
                "roth_balance": round(roth, 2),
            })

        return {
            "year_by_year": year_by_year,
            "total_converted": round(traditional_balance - remaining / ((1 + growth_rate) ** years), 2),
            "total_tax_paid": round(total_tax, 2),
            "projected_roth_at_retirement": round(roth, 2),
        }

    @staticmethod
    def backdoor_roth_checklist(
        has_traditional_ira_balance: bool,
        traditional_ira_balance: float = 0,
        income: float = 0,
        filing_status: str = "mfj",
    ) -> dict:
        limit = ROTH_INCOME_PHASEOUT.get(filing_status, 153_000)
        over_limit = income > limit

        steps = [
            "Contribute $7,000 ($8,000 if 50+) to a Traditional IRA (non-deductible)",
            "Wait 1-2 business days for funds to settle",
            "Convert the entire Traditional IRA balance to Roth IRA",
            "File Form 8606 with your tax return to report the non-deductible contribution",
        ]

        pro_rata = has_traditional_ira_balance and traditional_ira_balance > 0
        if pro_rata:
            steps.insert(0, f"WARNING: You have ${traditional_ira_balance:,.0f} in Traditional IRA — pro-rata rule applies")
            steps.append(f"Consider rolling Traditional IRA into employer 401(k) to avoid pro-rata taxation")

        return {
            "eligible": over_limit,
            "income_over_roth_limit": over_limit,
            "steps": steps,
            "pro_rata_warning": pro_rata,
            "pro_rata_taxable_pct": round(traditional_ira_balance / (traditional_ira_balance + 7000) * 100, 1) if pro_rata else 0,
        }

    @staticmethod
    def mega_backdoor_roth_analysis(
        employer_plan_allows: bool,
        current_employee_contrib: float = 23500,
        employer_match_contrib: float = 10000,
        plan_limit: float = 69000,
    ) -> dict:
        if not employer_plan_allows:
            return {
                "available": False,
                "available_space": 0,
                "explanation": "Your employer plan does not allow after-tax contributions or in-service withdrawals.",
            }

        used = current_employee_contrib + employer_match_contrib
        available = max(0, plan_limit - used)

        return {
            "available": True,
            "available_space": round(available, 2),
            "employee_contributions": current_employee_contrib,
            "employer_contributions": employer_match_contrib,
            "plan_limit": plan_limit,
            "tax_free_growth_value_20yr": round(available * ((1.07) ** 20), 2),
        }

    @staticmethod
    def daf_bunching_strategy(
        annual_charitable: float,
        standard_deduction: float = 30000,
        itemized_deductions_excl_charitable: float = 15000,
        bunch_years: int = 2,
        filing_status: str = "mfj",
        taxable_income: float = 300_000,
    ) -> dict:
        marginal = _marginal(taxable_income, filing_status)
        annual_itemized = itemized_deductions_excl_charitable + annual_charitable
        annual_benefit = max(0, annual_itemized - standard_deduction)
        annual_tax_savings = annual_benefit * marginal * bunch_years

        bunched = annual_charitable * bunch_years
        bunched_year_itemized = itemized_deductions_excl_charitable + bunched
        bunched_year_benefit = max(0, bunched_year_itemized - standard_deduction)
        off_year_benefit = 0
        bunched_tax_savings = bunched_year_benefit * marginal + off_year_benefit * (bunch_years - 1)

        savings = bunched_tax_savings - annual_tax_savings

        return {
            "annual_strategy_tax_savings": round(annual_tax_savings, 2),
            "bunched_strategy_tax_savings": round(bunched_tax_savings, 2),
            "savings": round(max(0, savings), 2),
            "bunch_years": bunch_years,
            "bunched_amount": round(bunched, 2),
            "recommendation": f"Bunch {bunch_years} years of giving into a DAF contribution to save ${max(0, savings):,.0f}." if savings > 0 else "Annual giving is already optimal at your deduction level.",
        }

    @staticmethod
    def scorp_election_model(
        gross_1099_income: float,
        reasonable_salary: float,
        business_expenses: float = 0,
        state: str = "CA",
        filing_status: str = "mfj",
    ) -> dict:
        from pipeline.tax import se_tax as _se_tax, fica_tax as _fica_tax
        net_income = gross_1099_income - business_expenses
        deduction = _std_deduction(filing_status)

        # Schedule C path
        se_tax_c = _se_tax(net_income, filing_status)
        deductible_se = se_tax_c / 2
        taxable_c = max(0, net_income - deductible_se - deduction)
        fed_tax_c = _fed_tax(taxable_c, filing_status)
        total_c = fed_tax_c + se_tax_c

        # S-Corp path
        employer_fica = reasonable_salary * 0.0765
        employee_fica = reasonable_salary * 0.0765
        corp_taxable = net_income - reasonable_salary - employer_fica
        distributions = max(0, corp_taxable)
        taxable_s = max(0, reasonable_salary + distributions - deduction)
        total_s = _fed_tax(taxable_s, filing_status) + employer_fica + employee_fica

        savings = total_c - total_s

        return {
            "schedule_c_tax": round(total_c, 2),
            "scorp_tax": round(total_s, 2),
            "se_tax_savings": round(savings, 2),
            "reasonable_salary": round(reasonable_salary, 2),
            "distributions": round(distributions, 2),
            "total_savings": round(max(0, savings), 2),
            "recommendation": f"S-Corp election saves ${max(0, savings):,.0f}/year" if savings > 500 else "S-Corp election does not provide meaningful savings at this income level.",
        }

    @staticmethod
    def multi_year_projection(
        current_income: float,
        income_growth_rate: float = 0.03,
        filing_status: str = "mfj",
        state_rate: float = 0.093,
        years: int = 5,
        roth_conversions: list[float] | None = None,
        equity_vesting: list[float] | None = None,
    ) -> dict:
        years_data = []
        for y in range(years):
            income = current_income * ((1 + income_growth_rate) ** y)
            extra = 0
            if roth_conversions and y < len(roth_conversions):
                extra += roth_conversions[y]
            if equity_vesting and y < len(equity_vesting):
                extra += equity_vesting[y]

            total = income + extra
            deduction = _std_deduction(filing_status)
            taxable = max(0, total - deduction)
            federal = _fed_tax(taxable, filing_status)
            state_tax_amt = taxable * state_rate
            from pipeline.tax import fica_tax as _fica_tax
            fica = _fica_tax(income, filing_status)
            total_tax = federal + state_tax_amt + fica

            years_data.append({
                "year": y + 1,
                "income": round(total, 2),
                "federal_tax": round(federal, 2),
                "state_tax": round(state_tax_amt, 2),
                "fica": round(fica, 2),
                "total_tax": round(total_tax, 2),
                "effective_rate": round(total_tax / total, 4) if total > 0 else 0,
            })

        return {"years": years_data}

    @staticmethod
    def estimated_payment_calculator(
        total_underwithholding: float,
        prior_year_tax: float = 0,
        current_withholding: float = 0,
    ) -> dict:
        safe_harbor = max(prior_year_tax * 1.10, 0) if prior_year_tax > 0 else 0
        gap = max(0, total_underwithholding - current_withholding)
        if safe_harbor > 0:
            gap = min(gap, safe_harbor - current_withholding)

        per_q = math.ceil(gap / 4) if gap > 0 else 0
        due = {1: "04/15", 2: "06/15", 3: "09/15", 4: "01/15"}
        return {
            "quarterly_payments": [{"quarter": q, "due_date": due[q], "amount": per_q} for q in range(1, 5)] if per_q > 0 else [],
            "total_estimated_payments": round(gap, 2),
            "safe_harbor_amount": round(safe_harbor, 2),
        }

    @staticmethod
    def student_loan_optimizer(
        loan_balance: float,
        interest_rate: float,
        monthly_income: float,
        filing_status: str = "mfj",
        pslf_eligible: bool = False,
    ) -> dict:
        strategies = []
        annual_income = monthly_income * 12

        # Standard repayment (10 years)
        r = interest_rate / 100 / 12
        if r > 0:
            standard_payment = loan_balance * (r * (1 + r) ** 120) / ((1 + r) ** 120 - 1)
        else:
            standard_payment = loan_balance / 120
        standard_total = standard_payment * 120
        strategies.append({
            "name": "Standard (10-year)",
            "monthly_payment": round(standard_payment, 2),
            "total_paid": round(standard_total, 2),
            "total_interest": round(standard_total - loan_balance, 2),
            "payoff_years": 10,
            "forgiveness_amount": 0,
        })

        # IBR / SAVE (income-driven) — 225% of 2025 Federal Poverty Level ($15,060 for single)
        fpl_225_pct = 33_885
        discretionary = max(0, annual_income - fpl_225_pct) * 0.10 / 12
        ibr_payment = min(discretionary, standard_payment)
        ibr_months = 240 if not pslf_eligible else 120
        ibr_total = ibr_payment * ibr_months
        remaining = loan_balance * ((1 + interest_rate / 100 / 12) ** ibr_months) - ibr_total
        forgiveness = max(0, remaining) if ibr_months >= 240 or pslf_eligible else 0

        strategies.append({
            "name": "SAVE/IBR" + (" + PSLF" if pslf_eligible else ""),
            "monthly_payment": round(ibr_payment, 2),
            "total_paid": round(ibr_total, 2),
            "total_interest": round(ibr_total - loan_balance + forgiveness, 2),
            "payoff_years": ibr_months / 12,
            "forgiveness_amount": round(forgiveness, 2),
        })

        # Aggressive payoff (5 years)
        if r > 0:
            agg_payment = loan_balance * (r * (1 + r) ** 60) / ((1 + r) ** 60 - 1)
        else:
            agg_payment = loan_balance / 60
        agg_total = agg_payment * 60
        strategies.append({
            "name": "Aggressive (5-year)",
            "monthly_payment": round(agg_payment, 2),
            "total_paid": round(agg_total, 2),
            "total_interest": round(agg_total - loan_balance, 2),
            "payoff_years": 5,
            "forgiveness_amount": 0,
        })

        best = min(strategies, key=lambda s: s["total_paid"])
        if pslf_eligible:
            rec = "PSLF is likely your best option — make qualifying payments and apply after 120 months."
        elif best["name"].startswith("SAVE"):
            rec = "Income-driven repayment with forgiveness is most cost-effective given your income."
        else:
            rec = f"{best['name']} minimizes total cost at ${best['total_paid']:,.0f}."

        return {"strategies": strategies, "recommendation": rec}
