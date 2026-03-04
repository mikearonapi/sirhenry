"""
Tax modeling engine for interactive strategy simulation.
Roth conversions, backdoor Roth, S-Corp, DAF bunching, student loans, multi-year projections,
Section 179 heavy equipment depreciation.
"""
import logging
import math
from dataclasses import dataclass

from pipeline.tax import (
    federal_tax as _fed_tax,
    marginal_rate as _marginal,
    standard_deduction as _std_deduction,
    get_brackets as _brackets,
    fica_tax as _fica,
    niit_tax as _niit,
    state_tax as _state_tax,
    FICA_SS_CAP, SE_TAX_DEDUCTION_FACTOR,
    ROTH_INCOME_PHASEOUT,
    NIIT_THRESHOLD, STATE_TAX_RATES,
)
from pipeline.tax.constants import (
    QBI_DEDUCTION_RATE, QBI_PHASEOUT_START, QBI_PHASEOUT_RANGE,
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

    @staticmethod
    def defined_benefit_plan_analysis(
        self_employment_income: float,
        age: int,
        target_retirement_age: int = 65,
        filing_status: str = "mfj",
        existing_retirement_contrib: float = 0,
    ) -> dict:
        """Model a defined benefit plan for self-employed individuals."""
        years_to_retirement = max(1, target_retirement_age - age)

        # DB plan contribution limits scale with age and target benefit
        # Max annual benefit at NRA: $280,000 (2025)
        max_annual_benefit = 280_000
        # Contribution limit depends on actuarial present value
        # Approximate: older = higher contribution allowed
        if age >= 60:
            max_contrib_pct = 0.95
        elif age >= 55:
            max_contrib_pct = 0.70
        elif age >= 50:
            max_contrib_pct = 0.55
        elif age >= 45:
            max_contrib_pct = 0.40
        else:
            max_contrib_pct = 0.25

        max_contribution = min(
            self_employment_income * max_contrib_pct,
            max_annual_benefit * (1.0 / max(1, years_to_retirement)),  # simplified actuarial
        )
        max_contribution = max(0, min(max_contribution, self_employment_income * 0.95))

        # Compare to SEP-IRA (25% of SE income, max $69K in 2025)
        sep_contribution = min(self_employment_income * 0.25, 69_000)

        # Tax savings
        marginal = _marginal(self_employment_income, filing_status)
        db_tax_savings = max_contribution * marginal
        sep_tax_savings = sep_contribution * marginal
        additional_savings = db_tax_savings - sep_tax_savings

        # Projected accumulation at 6% growth
        growth_rate = 0.06
        db_accumulation = sum(max_contribution * (1 + growth_rate) ** i for i in range(years_to_retirement))
        sep_accumulation = sum(sep_contribution * (1 + growth_rate) ** i for i in range(years_to_retirement))

        viable = self_employment_income >= 100_000 and age >= 40 and years_to_retirement <= 25

        return {
            "viable": viable,
            "max_annual_contribution": round(max_contribution),
            "sep_ira_contribution": round(sep_contribution),
            "additional_contribution": round(max_contribution - sep_contribution),
            "annual_tax_savings": round(db_tax_savings),
            "sep_annual_tax_savings": round(sep_tax_savings),
            "additional_annual_savings": round(additional_savings),
            "projected_accumulation": round(db_accumulation),
            "sep_projected_accumulation": round(sep_accumulation),
            "years_to_retirement": years_to_retirement,
            "marginal_rate": round(marginal, 3),
            "explanation": (
                f"A defined benefit plan allows you to contribute up to ${max_contribution:,.0f}/year "
                f"vs ${sep_contribution:,.0f} with a SEP-IRA, saving an additional ${additional_savings:,.0f}/year in taxes."
                if viable else
                "A defined benefit plan may not be ideal — it works best for self-employed age 40+ with consistent income over $100K."
            ),
        }

    @staticmethod
    def real_estate_str_analysis(
        property_value: float,
        annual_rental_income: float,
        average_stay_days: float,
        hours_per_week_managing: float,
        w2_income: float,
        filing_status: str = "mfj",
        land_value_pct: float = 0.20,
    ) -> dict:
        """Model the short-term rental (STR) tax loophole with cost segregation."""
        # STR qualification: average stay < 7 days
        qualifies_str = average_stay_days < 7
        # Material participation: 100+ hours and more than anyone else
        material_participation = hours_per_week_managing * 52 >= 100

        # Cost segregation: accelerate depreciation
        depreciable_basis = property_value * (1 - land_value_pct)
        # Standard depreciation: 27.5 years for residential
        standard_annual_depreciation = depreciable_basis / 27.5
        # Cost seg moves ~30% of basis to 5/7/15-year property + bonus depreciation
        cost_seg_year_one = depreciable_basis * 0.30 * 0.80  # 80% bonus depreciation (2025)
        cost_seg_remaining = depreciable_basis * 0.70 / 27.5

        # Operating expenses estimate (~40% of rental income)
        operating_expenses = annual_rental_income * 0.40

        # Net rental income/loss
        standard_net = annual_rental_income - operating_expenses - standard_annual_depreciation
        cost_seg_year_one_net = annual_rental_income - operating_expenses - cost_seg_year_one - cost_seg_remaining

        # Can losses offset W-2? Only if STR + material participation
        can_offset_w2 = qualifies_str and material_participation
        marginal = _marginal(w2_income, filing_status)

        if can_offset_w2 and cost_seg_year_one_net < 0:
            w2_offset = abs(cost_seg_year_one_net)
            tax_savings_year_one = w2_offset * marginal
        else:
            w2_offset = 0
            tax_savings_year_one = 0

        standard_tax_savings = abs(min(0, standard_net)) * marginal if standard_net < 0 and can_offset_w2 else 0

        return {
            "qualifies_str": qualifies_str,
            "material_participation": material_participation,
            "can_offset_w2": can_offset_w2,
            "property_value": round(property_value),
            "depreciable_basis": round(depreciable_basis),
            "standard_annual_depreciation": round(standard_annual_depreciation),
            "cost_seg_year_one_depreciation": round(cost_seg_year_one + cost_seg_remaining),
            "annual_rental_income": round(annual_rental_income),
            "operating_expenses": round(operating_expenses),
            "standard_net_income": round(standard_net),
            "cost_seg_net_income_year_one": round(cost_seg_year_one_net),
            "w2_offset_year_one": round(w2_offset),
            "tax_savings_year_one": round(tax_savings_year_one),
            "standard_tax_savings": round(standard_tax_savings),
            "marginal_rate": round(marginal, 3),
            "qualification_notes": [
                f"Average stay: {average_stay_days:.0f} days ({'qualifies' if qualifies_str else 'does NOT qualify'} as STR < 7 days)",
                f"Material participation: {hours_per_week_managing * 52:.0f} hrs/year ({'meets' if material_participation else 'does NOT meet'} 100hr threshold)",
                "STR + material participation = losses can offset W-2 income" if can_offset_w2 else "Losses limited to passive income only",
            ],
        }

    # -----------------------------------------------------------------------
    # Section 179 / Heavy Equipment Depreciation
    # -----------------------------------------------------------------------

    # 2025 Section 179 limits
    SEC_179_LIMIT = 1_160_000
    SEC_179_PHASEOUT_START = 4_600_000
    BONUS_DEPRECIATION_RATE = 0.60  # 60% for 2025, steps down yearly

    # Equipment database: realistic market data for common rental equipment
    # Keys: category → list of equipment with cost range, MACRS class, rental potential
    EQUIPMENT_DATABASE: dict[str, list[dict]] = {
        "excavators": [
            {"name": "Mini Excavator (3-6 ton)", "cost_low": 40_000, "cost_high": 80_000, "macrs_years": 5, "monthly_rental": 3_500, "utilization": 0.65, "annual_maintenance_pct": 0.05, "demand": "high"},
            {"name": "Midi Excavator (8-12 ton)", "cost_low": 80_000, "cost_high": 150_000, "macrs_years": 5, "monthly_rental": 6_000, "utilization": 0.60, "annual_maintenance_pct": 0.05, "demand": "high"},
            {"name": "Standard Excavator (20-30 ton)", "cost_low": 150_000, "cost_high": 350_000, "macrs_years": 5, "monthly_rental": 12_000, "utilization": 0.55, "annual_maintenance_pct": 0.06, "demand": "medium"},
        ],
        "skid_steers": [
            {"name": "Skid Steer Loader", "cost_low": 30_000, "cost_high": 65_000, "macrs_years": 5, "monthly_rental": 2_500, "utilization": 0.70, "annual_maintenance_pct": 0.06, "demand": "high"},
            {"name": "Compact Track Loader", "cost_low": 45_000, "cost_high": 90_000, "macrs_years": 5, "monthly_rental": 3_500, "utilization": 0.70, "annual_maintenance_pct": 0.06, "demand": "high"},
        ],
        "trucks_trailers": [
            {"name": "Dump Truck (single axle)", "cost_low": 50_000, "cost_high": 120_000, "macrs_years": 5, "monthly_rental": 4_000, "utilization": 0.60, "annual_maintenance_pct": 0.07, "demand": "high"},
            {"name": "Semi Truck + Flatbed Trailer", "cost_low": 80_000, "cost_high": 180_000, "macrs_years": 5, "monthly_rental": 5_500, "utilization": 0.55, "annual_maintenance_pct": 0.08, "demand": "medium"},
            {"name": "Equipment Trailer (tag-along)", "cost_low": 8_000, "cost_high": 25_000, "macrs_years": 5, "monthly_rental": 800, "utilization": 0.50, "annual_maintenance_pct": 0.03, "demand": "high"},
        ],
        "earthmoving": [
            {"name": "Bulldozer (small)", "cost_low": 80_000, "cost_high": 200_000, "macrs_years": 5, "monthly_rental": 7_000, "utilization": 0.50, "annual_maintenance_pct": 0.07, "demand": "medium"},
            {"name": "Wheel Loader", "cost_low": 60_000, "cost_high": 180_000, "macrs_years": 5, "monthly_rental": 5_000, "utilization": 0.55, "annual_maintenance_pct": 0.06, "demand": "medium"},
            {"name": "Backhoe Loader", "cost_low": 40_000, "cost_high": 100_000, "macrs_years": 5, "monthly_rental": 3_000, "utilization": 0.60, "annual_maintenance_pct": 0.05, "demand": "high"},
        ],
        "aerial_lifts": [
            {"name": "Scissor Lift (26-32 ft)", "cost_low": 15_000, "cost_high": 40_000, "macrs_years": 5, "monthly_rental": 1_500, "utilization": 0.65, "annual_maintenance_pct": 0.04, "demand": "high"},
            {"name": "Boom Lift (40-60 ft)", "cost_low": 40_000, "cost_high": 120_000, "macrs_years": 5, "monthly_rental": 4_000, "utilization": 0.55, "annual_maintenance_pct": 0.05, "demand": "medium"},
            {"name": "Telehandler / Forklift", "cost_low": 30_000, "cost_high": 80_000, "macrs_years": 5, "monthly_rental": 3_000, "utilization": 0.60, "annual_maintenance_pct": 0.05, "demand": "high"},
        ],
        "concrete_masonry": [
            {"name": "Concrete Mixer Truck", "cost_low": 60_000, "cost_high": 150_000, "macrs_years": 5, "monthly_rental": 5_000, "utilization": 0.50, "annual_maintenance_pct": 0.07, "demand": "medium"},
            {"name": "Concrete Pump (boom)", "cost_low": 100_000, "cost_high": 300_000, "macrs_years": 5, "monthly_rental": 8_000, "utilization": 0.45, "annual_maintenance_pct": 0.06, "demand": "low"},
        ],
        "vehicles": [
            {"name": "Heavy SUV / Pickup (>6,000 lbs GVWR)", "cost_low": 60_000, "cost_high": 110_000, "macrs_years": 5, "monthly_rental": 2_500, "utilization": 0.70, "annual_maintenance_pct": 0.04, "demand": "high"},
        ],
    }

    @staticmethod
    def section_179_equipment_analysis(
        equipment_cost: float,
        business_income: float,
        filing_status: str = "mfj",
        equipment_category: str = "excavators",
        equipment_index: int = 0,
        business_use_pct: float = 1.0,
        will_rent_out: bool = True,
        has_existing_business: bool = True,
    ) -> dict:
        """
        Model Section 179 + bonus depreciation for heavy equipment purchases.

        Covers: qualification, year-one deduction, rental income strategy,
        5-year cash flow projection, and what to do with the equipment.
        """
        # --- Section 179 qualification ---
        qualifies_179 = (
            equipment_cost <= TaxModelingEngine.SEC_179_LIMIT
            and equipment_cost <= TaxModelingEngine.SEC_179_PHASEOUT_START
            and business_use_pct > 0.50
            and has_existing_business
        )

        # Business use must be > 50% to qualify for Section 179
        deductible_cost = equipment_cost * business_use_pct

        # Section 179 deduction (limited to business income)
        sec_179_deduction = min(deductible_cost, business_income) if qualifies_179 else 0

        # Remaining basis after Section 179 gets bonus depreciation
        remaining_after_179 = max(0, deductible_cost - sec_179_deduction)
        bonus_deduction = remaining_after_179 * TaxModelingEngine.BONUS_DEPRECIATION_RATE

        # MACRS on whatever's left after 179 + bonus
        remaining_for_macrs = remaining_after_179 - bonus_deduction
        macrs_5yr_rates = [0.20, 0.32, 0.192, 0.1152, 0.1152, 0.0576]  # 5-year MACRS

        year_one_deduction = sec_179_deduction + bonus_deduction + (remaining_for_macrs * macrs_5yr_rates[0])
        total_year_one_deduction = year_one_deduction

        # Tax savings
        marginal = _marginal(business_income, filing_status)
        year_one_tax_savings = total_year_one_deduction * marginal

        # --- Equipment rental strategy ---
        equipment_list = TaxModelingEngine.EQUIPMENT_DATABASE.get(equipment_category, [])
        equipment = equipment_list[min(equipment_index, len(equipment_list) - 1)] if equipment_list else None

        rental_analysis = None
        five_year_projection = []

        if equipment and will_rent_out:
            monthly_rental = equipment["monthly_rental"]
            utilization = equipment["utilization"]
            maintenance_pct = equipment["annual_maintenance_pct"]

            # Scale rental rate proportionally to actual cost vs midpoint
            midpoint_cost = (equipment["cost_low"] + equipment["cost_high"]) / 2
            if midpoint_cost > 0:
                cost_ratio = equipment_cost / midpoint_cost
                monthly_rental = monthly_rental * min(max(cost_ratio, 0.5), 2.0)

            annual_rental_gross = monthly_rental * 12 * utilization
            annual_maintenance = equipment_cost * maintenance_pct
            annual_insurance = equipment_cost * 0.015
            annual_storage = 1_200 if equipment_cost < 80_000 else 2_400
            annual_transport = 3_000 if equipment_cost > 50_000 else 1_500
            annual_operating_expenses = annual_maintenance + annual_insurance + annual_storage + annual_transport
            annual_net_rental = annual_rental_gross - annual_operating_expenses

            rental_analysis = {
                "equipment_name": equipment["name"],
                "monthly_rental_rate": round(monthly_rental),
                "utilization_rate": utilization,
                "demand_level": equipment["demand"],
                "annual_rental_gross": round(annual_rental_gross),
                "annual_expenses": round(annual_operating_expenses),
                "annual_net_rental": round(annual_net_rental),
                "expense_breakdown": {
                    "maintenance": round(annual_maintenance),
                    "insurance": round(annual_insurance),
                    "storage": round(annual_storage),
                    "transport": round(annual_transport),
                },
            }

            # 5-year cash flow projection
            cumulative_cash = -equipment_cost  # initial outlay
            remaining_basis = remaining_for_macrs

            for yr in range(5):
                # Rental income (2% annual growth)
                yr_rental = annual_net_rental * (1.02 ** yr)

                # Depreciation deduction for this year
                if yr == 0:
                    yr_depreciation = total_year_one_deduction
                elif yr < len(macrs_5yr_rates):
                    yr_depreciation = remaining_basis * macrs_5yr_rates[yr]
                else:
                    yr_depreciation = 0

                yr_tax_savings = yr_depreciation * marginal
                yr_net_cash = yr_rental + yr_tax_savings
                cumulative_cash += yr_net_cash

                five_year_projection.append({
                    "year": yr + 1,
                    "rental_income": round(yr_rental),
                    "depreciation_deduction": round(yr_depreciation),
                    "tax_savings": round(yr_tax_savings),
                    "net_cash_flow": round(yr_net_cash),
                    "cumulative_cash": round(cumulative_cash),
                })

            # Resale value estimate (equipment depreciates ~15-20%/yr market value)
            resale_5yr = equipment_cost * 0.35  # ~35% of purchase price after 5 years
            rental_analysis["resale_value_5yr"] = round(resale_5yr)
            rental_analysis["total_return_5yr"] = round(cumulative_cash + resale_5yr)

        # --- Strategy recommendations ---
        strategies = []
        if qualifies_179:
            strategies.append({
                "strategy": "Section 179 Full Deduction",
                "description": f"Deduct the full ${equipment_cost:,.0f} purchase price in year one against your business income.",
                "applicable": business_income >= equipment_cost,
            })
        if not has_existing_business:
            strategies.append({
                "strategy": "Start Equipment Rental LLC",
                "description": "Form an LLC taxed as a sole proprietorship or S-Corp to rent equipment. The business entity gives you the ability to take Section 179.",
                "applicable": True,
            })
        if will_rent_out:
            strategies.append({
                "strategy": "Rent to Contractors",
                "description": "List on equipment rental platforms (BigRentz, Yard Club, local dealers) or direct to contractors. Target 55-70% utilization.",
                "applicable": True,
            })
            strategies.append({
                "strategy": "Rent to Your Own Projects",
                "description": "If you do any construction/landscaping work, rent the equipment to yourself at fair market rates through your LLC.",
                "applicable": has_existing_business,
            })
        strategies.append({
            "strategy": "Sell After Depreciation",
            "description": "After fully depreciating the equipment (5-7 years), sell it. The sale proceeds are taxed as ordinary income (depreciation recapture), but you've had years of tax savings and rental income.",
            "applicable": True,
        })
        strategies.append({
            "strategy": "1031 Exchange into New Equipment",
            "description": "Trade in or sell the equipment and use a like-kind exchange to defer the depreciation recapture tax while upgrading to newer equipment.",
            "applicable": True,
        })

        # --- Equipment recommendations based on budget ---
        recommended = []
        for cat_key, items in TaxModelingEngine.EQUIPMENT_DATABASE.items():
            for item in items:
                if item["cost_low"] <= equipment_cost * 1.2 and item["cost_high"] >= equipment_cost * 0.5:
                    if item["demand"] in ("high", "medium"):
                        recommended.append({
                            "category": cat_key.replace("_", " ").title(),
                            "name": item["name"],
                            "cost_range": f"${item['cost_low']:,.0f} – ${item['cost_high']:,.0f}",
                            "monthly_rental": item["monthly_rental"],
                            "demand": item["demand"],
                            "utilization": item["utilization"],
                        })

        # Sort by demand (high first) then utilization
        recommended.sort(key=lambda x: (0 if x["demand"] == "high" else 1, -x["utilization"]))

        return {
            "qualifies_section_179": qualifies_179,
            "equipment_cost": round(equipment_cost),
            "business_use_pct": business_use_pct,
            "deductible_cost": round(deductible_cost),
            "section_179_deduction": round(sec_179_deduction),
            "bonus_depreciation": round(bonus_deduction),
            "year_one_total_deduction": round(total_year_one_deduction),
            "year_one_tax_savings": round(year_one_tax_savings),
            "marginal_rate": round(marginal, 3),
            "rental_analysis": rental_analysis,
            "five_year_projection": five_year_projection,
            "exit_strategies": strategies,
            "recommended_equipment": recommended[:6],
            "qualification_notes": [
                f"Section 179 limit: ${TaxModelingEngine.SEC_179_LIMIT:,.0f} (2025)",
                f"Bonus depreciation: {TaxModelingEngine.BONUS_DEPRECIATION_RATE * 100:.0f}% (2025, declining 20%/yr)",
                f"Business use: {business_use_pct * 100:.0f}% ({'qualifies' if business_use_pct > 0.50 else 'does NOT qualify'} — must be >50%)",
                f"Business income: ${business_income:,.0f} (Section 179 limited to business income)",
                "Equipment must be purchased and placed in service in the same tax year" if qualifies_179 else "You need an active business or LLC to take Section 179",
            ],
        }

    # -----------------------------------------------------------------------
    # Filing Status Comparison (MFJ vs MFS)
    # -----------------------------------------------------------------------

    @staticmethod
    def filing_status_comparison(
        spouse_a_income: float,
        spouse_b_income: float,
        investment_income: float = 0,
        itemized_deductions: float = 0,
        student_loan_payment: float = 0,
        state: str = "CA",
    ) -> dict:
        """
        Compare Married Filing Jointly vs Married Filing Separately.

        Key scenarios where MFS may win:
        - High student loan payments on income-driven repayment (IDR)
        - Large disparity in spouse incomes with itemized deductions
        - State-specific benefits (community property states)
        """
        combined = spouse_a_income + spouse_b_income
        half_investment = investment_income / 2

        # --- MFJ calculation ---
        mfj_deduction = _std_deduction("mfj")
        mfj_use_itemized = itemized_deductions > mfj_deduction
        mfj_actual_deduction = max(itemized_deductions, mfj_deduction)
        mfj_taxable = max(0, combined + investment_income - mfj_actual_deduction)
        mfj_federal = _fed_tax(mfj_taxable, "mfj")
        mfj_niit = _niit(combined + investment_income, investment_income, "mfj")
        mfj_state = _state_tax(combined + investment_income, state)
        mfj_fica_a = _fica(spouse_a_income, "mfj")
        mfj_fica_b = _fica(spouse_b_income, "mfj")
        mfj_total = mfj_federal + mfj_niit + mfj_state + mfj_fica_a + mfj_fica_b

        # Student loan interest deduction (up to $2,500, phases out for MFJ at $165K-$195K MAGI)
        mfj_student_loan_deduction = 0
        if student_loan_payment > 0:
            mfj_magi = combined + investment_income
            if mfj_magi < 165_000:
                mfj_student_loan_deduction = min(student_loan_payment, 2_500)
            elif mfj_magi < 195_000:
                phase = 1 - (mfj_magi - 165_000) / 30_000
                mfj_student_loan_deduction = min(student_loan_payment, 2_500) * phase
            mfj_federal_with_sl = _fed_tax(max(0, mfj_taxable - mfj_student_loan_deduction), "mfj")
            mfj_sl_benefit = mfj_federal - mfj_federal_with_sl
            mfj_total -= mfj_sl_benefit
        else:
            mfj_sl_benefit = 0

        # --- MFS calculation ---
        # MFS: each spouse files separately. Key differences:
        # - Lower bracket thresholds (exactly half of MFJ)
        # - NIIT threshold drops to $125K each
        # - Can't take student loan interest deduction at all
        # - If one spouse itemizes, BOTH must itemize
        mfs_deduction = _std_deduction("mfs")

        # Spouse A
        mfs_a_itemized = itemized_deductions / 2 if mfj_use_itemized else 0
        mfs_a_deduction = max(mfs_a_itemized, mfs_deduction) if not mfj_use_itemized else max(mfs_a_itemized, 0)
        # If one itemizes, both must itemize
        if mfj_use_itemized:
            mfs_a_deduction = itemized_deductions / 2
            mfs_b_deduction = itemized_deductions / 2
        else:
            mfs_a_deduction = mfs_deduction
            mfs_b_deduction = mfs_deduction

        mfs_a_taxable = max(0, spouse_a_income + half_investment - mfs_a_deduction)
        mfs_b_taxable = max(0, spouse_b_income + half_investment - mfs_b_deduction)

        mfs_a_federal = _fed_tax(mfs_a_taxable, "mfs")
        mfs_b_federal = _fed_tax(mfs_b_taxable, "mfs")

        mfs_a_niit = _niit(spouse_a_income + half_investment, half_investment, "mfs")
        mfs_b_niit = _niit(spouse_b_income + half_investment, half_investment, "mfs")

        mfs_a_state = _state_tax(spouse_a_income + half_investment, state)
        mfs_b_state = _state_tax(spouse_b_income + half_investment, state)

        mfs_fica_a = _fica(spouse_a_income, "mfs")
        mfs_fica_b = _fica(spouse_b_income, "mfs")

        mfs_total = (mfs_a_federal + mfs_b_federal + mfs_a_niit + mfs_b_niit +
                     mfs_a_state + mfs_b_state + mfs_fica_a + mfs_fica_b)

        # MFS student loan: deduction is $0 (not allowed)
        mfs_sl_benefit = 0

        # IDR benefit: if on income-driven repayment, MFS means lower reported income
        idr_benefit = 0
        idr_note = ""
        if student_loan_payment > 0:
            # IDR plans (SAVE/PAYE/IBR) use AGI. MFS = only one spouse's income
            # Estimated monthly IDR payment: 10% of discretionary income / 12
            poverty_line_1 = 15_060 * 1.5  # 150% of poverty for single
            poverty_line_2 = 20_440 * 1.5  # 150% of poverty for family of 2
            mfj_discretionary = max(0, combined + investment_income - poverty_line_2)
            mfs_discretionary = max(0, min(spouse_a_income, spouse_b_income) + half_investment - poverty_line_1)
            mfj_idr_monthly = mfj_discretionary * 0.10 / 12
            mfs_idr_monthly = mfs_discretionary * 0.10 / 12
            idr_benefit = (mfj_idr_monthly - mfs_idr_monthly) * 12
            if idr_benefit > 0:
                idr_note = (f"Filing separately could reduce IDR payments by ~${idr_benefit:,.0f}/year "
                           f"(${mfj_idr_monthly:,.0f}/mo MFJ vs ${mfs_idr_monthly:,.0f}/mo MFS)")

        difference = mfj_total - mfs_total
        better = "mfj" if difference <= 0 else "mfs"

        # Build recommendation
        if abs(difference) < 500:
            recommendation = "The difference is minimal (<$500). MFJ is simpler and preserves all deductions and credits."
        elif better == "mfj":
            recommendation = f"Filing jointly saves {abs(difference):,.0f}. MFJ is the better choice."
        else:
            recommendation = f"Filing separately saves {abs(difference):,.0f} in taxes."
            if idr_benefit > 0:
                recommendation += f" Plus ~${idr_benefit:,.0f}/year in lower student loan payments on IDR."

        mfj_effective = mfj_total / (combined + investment_income) if (combined + investment_income) > 0 else 0
        mfs_effective = mfs_total / (combined + investment_income) if (combined + investment_income) > 0 else 0

        return {
            "mfj": {
                "federal_tax": round(mfj_federal),
                "niit": round(mfj_niit),
                "state_tax": round(mfj_state),
                "fica": round(mfj_fica_a + mfj_fica_b),
                "student_loan_benefit": round(mfj_sl_benefit),
                "total_tax": round(mfj_total),
                "effective_rate": round(mfj_effective, 4),
                "deduction_used": round(mfj_actual_deduction),
                "itemizing": mfj_use_itemized,
            },
            "mfs": {
                "federal_tax": round(mfs_a_federal + mfs_b_federal),
                "niit": round(mfs_a_niit + mfs_b_niit),
                "state_tax": round(mfs_a_state + mfs_b_state),
                "fica": round(mfs_fica_a + mfs_fica_b),
                "student_loan_benefit": round(mfs_sl_benefit),
                "total_tax": round(mfs_total),
                "effective_rate": round(mfs_effective, 4),
                "deduction_used": round(mfs_a_deduction + mfs_b_deduction),
                "itemizing": mfj_use_itemized,
            },
            "difference": round(abs(difference)),
            "better": better,
            "recommendation": recommendation,
            "idr_benefit": round(idr_benefit),
            "idr_note": idr_note,
            "mfs_limitations": [
                "Cannot claim student loan interest deduction",
                "Cannot claim education credits (AOTC, LLC)",
                "Cannot claim Earned Income Credit",
                "Cannot claim adoption credit",
                "Child tax credit phaseout starts at $200K (vs $400K MFJ)",
                "Capital loss deduction limited to $1,500 (vs $3,000 MFJ)",
                "Social Security benefits may be more taxable",
                "If one spouse itemizes, both must itemize",
            ],
        }

    # -----------------------------------------------------------------------
    # QBI / Section 199A Deduction Checker
    # -----------------------------------------------------------------------

    @staticmethod
    def qbi_deduction_check(
        qbi_income: float,
        taxable_income: float,
        w2_wages_paid: float = 0,
        qualified_property: float = 0,
        filing_status: str = "mfj",
        is_sstb: bool = False,
    ) -> dict:
        """
        Check Section 199A QBI deduction eligibility and compute the deduction.

        Three limitations:
        1. 20% of QBI
        2. Greater of: (a) 50% of W-2 wages, or (b) 25% of W-2 wages + 2.5% of UBIA
        3. 20% of taxable income (overall cap)

        SSTB (specified service trade/business) gets fully phased out above threshold.
        """
        fs = filing_status.lower()
        phaseout_start = QBI_PHASEOUT_START.get(fs, QBI_PHASEOUT_START["single"])
        phaseout_range = QBI_PHASEOUT_RANGE.get(fs, QBI_PHASEOUT_RANGE["single"])
        phaseout_end = phaseout_start + phaseout_range

        # Phase 1: Basic 20% of QBI
        basic_deduction = qbi_income * QBI_DEDUCTION_RATE

        # Overall cap: 20% of taxable income (before QBI deduction)
        taxable_cap = taxable_income * QBI_DEDUCTION_RATE

        # Determine phaseout status
        in_phaseout = phaseout_start < taxable_income <= phaseout_end
        above_phaseout = taxable_income > phaseout_end
        below_phaseout = taxable_income <= phaseout_start

        # SSTB handling
        sstb_eliminated = False
        if is_sstb and above_phaseout:
            # SSTB income is completely excluded above phaseout
            sstb_eliminated = True
            final_deduction = 0
            w2_wage_limit = 0
            ubia_limit = 0
        elif is_sstb and in_phaseout:
            # Partial phaseout for SSTB — reduce QBI proportionally
            phase_pct = (phaseout_end - taxable_income) / phaseout_range
            effective_qbi = qbi_income * phase_pct
            effective_w2 = w2_wages_paid * phase_pct
            effective_property = qualified_property * phase_pct

            basic_deduction = effective_qbi * QBI_DEDUCTION_RATE
            w2_wage_limit = max(effective_w2 * 0.50, effective_w2 * 0.25 + effective_property * 0.025)
            ubia_limit = w2_wage_limit  # combined limit
            final_deduction = min(basic_deduction, w2_wage_limit, taxable_cap)
        elif below_phaseout:
            # Below phaseout: full 20%, no W-2/UBIA limit
            w2_wage_limit = basic_deduction  # not binding
            ubia_limit = basic_deduction
            final_deduction = min(basic_deduction, taxable_cap)
        else:
            # Non-SSTB above phaseout: W-2 wage + UBIA limits fully apply
            w2_wage_limit = max(w2_wages_paid * 0.50, w2_wages_paid * 0.25 + qualified_property * 0.025)
            ubia_limit = w2_wage_limit
            if in_phaseout:
                # Partial phase-in of the W-2/UBIA limitation
                phase_pct = (taxable_income - phaseout_start) / phaseout_range
                reduction = (basic_deduction - w2_wage_limit) * phase_pct
                limited_deduction = basic_deduction - max(0, reduction)
                final_deduction = min(limited_deduction, taxable_cap)
            else:
                # Fully above phaseout: W-2/UBIA limit fully applies
                final_deduction = min(basic_deduction, w2_wage_limit, taxable_cap)

        final_deduction = max(0, final_deduction)
        marginal = _marginal(taxable_income, filing_status)
        tax_savings = final_deduction * marginal

        # Build warnings
        warnings = []
        if sstb_eliminated:
            warnings.append("Your business is classified as an SSTB and your income exceeds the phaseout — QBI deduction is $0.")
        elif is_sstb and in_phaseout:
            phase_pct_display = (phaseout_end - taxable_income) / phaseout_range * 100
            warnings.append(f"SSTB in phaseout range — only {phase_pct_display:.0f}% of QBI counts toward the deduction.")
        if above_phaseout and not is_sstb and w2_wages_paid == 0:
            warnings.append("Above phaseout with $0 W-2 wages paid — your deduction is limited. Consider paying W-2 wages through your business.")
        if w2_wage_limit < basic_deduction and not below_phaseout and not sstb_eliminated:
            warnings.append(f"W-2 wage/UBIA limitation reduces your deduction from {basic_deduction:,.0f} to {w2_wage_limit:,.0f}.")
        if taxable_cap < basic_deduction and not sstb_eliminated:
            warnings.append("Taxable income cap is binding — deduction limited to 20% of taxable income.")

        # Recommendation
        if sstb_eliminated:
            recommendation = "Consider reducing taxable income below the phaseout threshold to recover the QBI deduction."
        elif final_deduction > 0:
            recommendation = f"You qualify for a ${final_deduction:,.0f} QBI deduction, saving ~${tax_savings:,.0f} in taxes."
        else:
            recommendation = "No QBI deduction available. Review your business structure and income levels."

        return {
            "qbi_income": round(qbi_income),
            "taxable_income": round(taxable_income),
            "filing_status": fs,
            "is_sstb": is_sstb,
            "basic_20pct_deduction": round(basic_deduction),
            "w2_wage_limit": round(w2_wage_limit) if not sstb_eliminated else 0,
            "taxable_income_cap": round(taxable_cap),
            "final_deduction": round(final_deduction),
            "tax_savings": round(tax_savings),
            "marginal_rate": round(marginal, 3),
            "phaseout_start": round(phaseout_start),
            "phaseout_end": round(phaseout_end),
            "in_phaseout": in_phaseout,
            "above_phaseout": above_phaseout,
            "sstb_eliminated": sstb_eliminated,
            "warnings": warnings,
            "recommendation": recommendation,
        }

    # -----------------------------------------------------------------------
    # State Residency Tax Comparison
    # -----------------------------------------------------------------------

    @staticmethod
    def state_tax_comparison(
        income: float,
        filing_status: str = "mfj",
        current_state: str = "CA",
        comparison_states: list[str] | None = None,
    ) -> dict:
        """
        Compare state income tax across multiple states.

        Uses simplified flat top-marginal rates from STATE_TAX_RATES.
        Highlights savings from relocating to lower-tax states.
        """
        if comparison_states is None:
            comparison_states = ["TX", "FL", "WA", "NV", "TN"]

        # Ensure current state is included
        all_states = [current_state] + [s for s in comparison_states if s != current_state]

        deduction = _std_deduction(filing_status)
        taxable = max(0, income - deduction)
        federal = _fed_tax(taxable, filing_status)
        fica = _fica(income, filing_status)

        current_state_tax = _state_tax(income, current_state)
        current_total = federal + fica + current_state_tax

        results = []
        for state in all_states:
            st_tax = _state_tax(income, state)
            st_rate = STATE_TAX_RATES.get(state, 0)
            total = federal + fica + st_tax
            savings_vs_current = current_state_tax - st_tax
            effective_total_rate = total / income if income > 0 else 0

            results.append({
                "state": state,
                "state_name": _state_name(state),
                "state_tax": round(st_tax),
                "state_rate": round(st_rate, 4),
                "total_tax": round(total),
                "effective_total_rate": round(effective_total_rate, 4),
                "savings_vs_current": round(savings_vs_current),
                "is_current": state == current_state,
                "is_no_tax": st_rate == 0,
            })

        # Sort by total tax ascending
        results.sort(key=lambda x: x["total_tax"])

        best = results[0]
        max_savings = current_state_tax - best["state_tax"]

        return {
            "income": round(income),
            "filing_status": filing_status,
            "current_state": current_state,
            "federal_tax": round(federal),
            "fica": round(fica),
            "current_state_tax": round(current_state_tax),
            "current_total_tax": round(current_total),
            "states": results,
            "best_state": best["state"],
            "max_savings": round(max_savings),
            "recommendation": (
                f"Moving from {current_state} to {best['state']} ({best['state_name']}) "
                f"could save ${max_savings:,.0f}/year in state taxes."
                if max_savings > 0
                else f"{current_state} is already one of the lowest-tax states for your income level."
            ),
        }


def _state_name(code: str) -> str:
    """Map state abbreviation to full name."""
    names = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "DC": "Washington DC", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
        "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
        "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
        "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
        "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
        "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
        "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
        "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
        "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
        "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
        "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    }
    return names.get(code, code)
