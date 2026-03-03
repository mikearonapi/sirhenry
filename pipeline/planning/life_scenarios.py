"""
Life decision affordability engine for HENRYs.
Answers questions like: "Can I afford a second home?" / "Should I buy a sports car?"
Each scenario type has a specific parameter set and calculation logic.
"""
import json
import logging
import math
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

SCENARIO_TEMPLATES = {
    "second_home": {
        "label": "Second Home / Vacation Property",
        "icon": "home",
        "description": "Evaluate the affordability of purchasing a second property",
        "parameters": {
            "purchase_price": {"label": "Purchase Price", "type": "currency", "default": 500000},
            "down_payment_pct": {"label": "Down Payment %", "type": "percent", "default": 20},
            "mortgage_rate_pct": {"label": "Mortgage Rate %", "type": "percent", "default": 6.5},
            "mortgage_term_years": {"label": "Mortgage Term (years)", "type": "number", "default": 30},
            "property_tax_annual": {"label": "Annual Property Tax", "type": "currency", "default": 6000},
            "insurance_annual": {"label": "Annual Insurance", "type": "currency", "default": 2400},
            "hoa_monthly": {"label": "Monthly HOA", "type": "currency", "default": 0},
            "maintenance_annual_pct": {"label": "Annual Maintenance % of Value", "type": "percent", "default": 1},
            "rental_income_monthly": {"label": "Expected Rental Income (if any)", "type": "currency", "default": 0},
        },
    },
    "vehicle": {
        "label": "Vehicle Purchase",
        "icon": "car",
        "description": "Can you afford that dream car or practical upgrade?",
        "parameters": {
            "purchase_price": {"label": "Vehicle Price", "type": "currency", "default": 60000},
            "down_payment": {"label": "Down Payment", "type": "currency", "default": 10000},
            "loan_rate_pct": {"label": "Loan Rate %", "type": "percent", "default": 5.5},
            "loan_term_months": {"label": "Loan Term (months)", "type": "number", "default": 60},
            "insurance_monthly": {"label": "Monthly Insurance", "type": "currency", "default": 200},
            "fuel_monthly": {"label": "Monthly Fuel", "type": "currency", "default": 150},
            "maintenance_annual": {"label": "Annual Maintenance", "type": "currency", "default": 1200},
            "trade_in_value": {"label": "Trade-In Value", "type": "currency", "default": 0},
        },
    },
    "home_renovation": {
        "label": "Home Renovation",
        "icon": "hammer",
        "description": "Evaluate a major home improvement project",
        "parameters": {
            "renovation_cost": {"label": "Total Renovation Cost", "type": "currency", "default": 50000},
            "financing_pct": {"label": "% Financed (HELOC/Loan)", "type": "percent", "default": 0},
            "loan_rate_pct": {"label": "Loan Rate % (if financed)", "type": "percent", "default": 7.0},
            "loan_term_years": {"label": "Loan Term (years)", "type": "number", "default": 10},
            "expected_value_increase": {"label": "Expected Home Value Increase", "type": "currency", "default": 30000},
        },
    },
    "college_fund": {
        "label": "College Fund (529 Plan)",
        "icon": "graduation-cap",
        "description": "Plan for your child's education expenses",
        "parameters": {
            "child_current_age": {"label": "Child's Current Age", "type": "number", "default": 5},
            "college_start_age": {"label": "College Start Age", "type": "number", "default": 18},
            "annual_tuition_today": {"label": "Annual Tuition (Today's $)", "type": "currency", "default": 40000},
            "years_of_college": {"label": "Years of College", "type": "number", "default": 4},
            "tuition_inflation_pct": {"label": "Tuition Inflation %", "type": "percent", "default": 5},
            "current_529_balance": {"label": "Current 529 Balance", "type": "currency", "default": 0},
            "expected_return_pct": {"label": "Expected Return %", "type": "percent", "default": 6},
        },
    },
    "starting_business": {
        "label": "Starting a Business",
        "icon": "briefcase",
        "description": "Evaluate the financial impact of launching a business",
        "parameters": {
            "startup_costs": {"label": "Total Startup Costs", "type": "currency", "default": 50000},
            "monthly_operating_costs": {"label": "Monthly Operating Costs", "type": "currency", "default": 5000},
            "months_to_revenue": {"label": "Months Until Revenue", "type": "number", "default": 6},
            "expected_monthly_revenue_year1": {"label": "Expected Monthly Revenue (Year 1)", "type": "currency", "default": 8000},
            "salary_replacement_needed": {"label": "Monthly Living Expenses", "type": "currency", "default": 8000},
            "emergency_fund_months": {"label": "Emergency Fund (months)", "type": "number", "default": 6},
        },
    },
    "sabbatical": {
        "label": "Career Break / Sabbatical",
        "icon": "palm-tree",
        "description": "Can you afford to take time off work?",
        "parameters": {
            "duration_months": {"label": "Duration (months)", "type": "number", "default": 6},
            "monthly_expenses_during": {"label": "Monthly Expenses During", "type": "currency", "default": 6000},
            "travel_budget": {"label": "Total Travel Budget", "type": "currency", "default": 10000},
            "health_insurance_monthly": {"label": "Health Insurance (monthly)", "type": "currency", "default": 800},
            "expected_income_during": {"label": "Any Income During (monthly)", "type": "currency", "default": 0},
        },
    },
    "lifestyle_upgrade": {
        "label": "Lifestyle Upgrade",
        "icon": "sparkles",
        "description": "Evaluate recurring lifestyle changes (new hobby, membership, etc.)",
        "parameters": {
            "monthly_cost_increase": {"label": "Monthly Cost Increase", "type": "currency", "default": 500},
            "one_time_cost": {"label": "One-Time Setup Cost", "type": "currency", "default": 2000},
            "description": {"label": "Description", "type": "text", "default": ""},
        },
    },
    "early_retirement": {
        "label": "Early Retirement",
        "icon": "sunset",
        "description": "What if you retired earlier than planned?",
        "parameters": {
            "current_age": {"label": "Current Age", "type": "number", "default": 35},
            "target_retirement_age": {"label": "Target Retirement Age", "type": "number", "default": 50},
            "annual_expenses_in_retirement": {"label": "Annual Expenses in Retirement", "type": "currency", "default": 80000},
            "current_savings": {"label": "Current Total Savings", "type": "currency", "default": 500000},
            "monthly_savings": {"label": "Current Monthly Savings", "type": "currency", "default": 5000},
            "expected_return_pct": {"label": "Expected Return %", "type": "percent", "default": 7},
            "social_security_age": {"label": "Social Security Start Age", "type": "number", "default": 67},
            "social_security_monthly": {"label": "Expected SS Monthly", "type": "currency", "default": 2500},
        },
    },
}


class LifeScenarioEngine:
    """Computes affordability for various life decisions."""

    @staticmethod
    def get_templates() -> dict:
        return SCENARIO_TEMPLATES

    @staticmethod
    def calculate(
        scenario_type: str,
        params: dict,
        annual_income: float,
        monthly_take_home: float,
        current_monthly_expenses: float,
        current_monthly_debt: float,
        current_savings: float,
        current_investments: float,
    ) -> dict:
        """
        Run affordability calculation for a specific scenario type.
        Returns comprehensive results dict with score, verdict, and breakdown.
        """
        calculator = CALCULATORS.get(scenario_type)
        if not calculator:
            return {"error": f"Unknown scenario type: {scenario_type}"}

        monthly_surplus = monthly_take_home - current_monthly_expenses - current_monthly_debt
        context = {
            "annual_income": annual_income,
            "monthly_take_home": monthly_take_home,
            "current_monthly_expenses": current_monthly_expenses,
            "current_monthly_debt": current_monthly_debt,
            "current_savings": current_savings,
            "current_investments": current_investments,
            "monthly_surplus": monthly_surplus,
            "savings_rate_before": (monthly_surplus / monthly_take_home * 100) if monthly_take_home > 0 else 0,
            "dti_before": (current_monthly_debt / (annual_income / 12) * 100) if annual_income > 0 else 0,
        }

        result = calculator(params, context)

        # Compute affordability score (0-100) based on multiple factors
        score = _compute_affordability_score(result, context)
        verdict = _score_to_verdict(score)

        result.update({
            "affordability_score": round(score, 1),
            "verdict": verdict,
            "savings_rate_before_pct": round(context["savings_rate_before"], 1),
            "dti_before_pct": round(context["dti_before"], 1),
        })

        return result


def _calc_monthly_payment(principal: float, annual_rate_pct: float, months: int) -> float:
    if annual_rate_pct <= 0 or months <= 0:
        return principal / max(months, 1)
    r = annual_rate_pct / 100 / 12
    return principal * (r * (1 + r) ** months) / ((1 + r) ** months - 1)


def _calc_second_home(params: dict, ctx: dict) -> dict:
    price = params.get("purchase_price", 500000)
    down_pct = params.get("down_payment_pct", 20)
    rate = params.get("mortgage_rate_pct", 6.5)
    term = params.get("mortgage_term_years", 30)
    prop_tax = params.get("property_tax_annual", 6000)
    insurance = params.get("insurance_annual", 2400)
    hoa = params.get("hoa_monthly", 0)
    maint_pct = params.get("maintenance_annual_pct", 1)
    rental = params.get("rental_income_monthly", 0)

    down_payment = price * down_pct / 100
    loan_amount = price - down_payment
    monthly_mortgage = _calc_monthly_payment(loan_amount, rate, term * 12)
    monthly_tax = prop_tax / 12
    monthly_ins = insurance / 12
    monthly_maint = price * maint_pct / 100 / 12

    total_monthly = monthly_mortgage + monthly_tax + monthly_ins + hoa + monthly_maint
    net_monthly = total_monthly - rental

    new_debt_total = ctx["current_monthly_debt"] + monthly_mortgage
    dti_after = (new_debt_total / (ctx["annual_income"] / 12) * 100) if ctx["annual_income"] > 0 else 0
    surplus_after = ctx["monthly_surplus"] - net_monthly
    savings_rate_after = (surplus_after / ctx["monthly_take_home"] * 100) if ctx["monthly_take_home"] > 0 else 0

    total_cost_30yr = down_payment + (total_monthly * term * 12)

    return {
        "total_cost": round(total_cost_30yr, 0),
        "new_monthly_payment": round(net_monthly, 2),
        "monthly_surplus_after": round(surplus_after, 2),
        "savings_rate_after_pct": round(savings_rate_after, 1),
        "dti_after_pct": round(dti_after, 1),
        "down_payment_needed": round(down_payment, 0),
        "can_afford_down_payment": down_payment <= (ctx["current_savings"] * 0.7),
        "breakdown": {
            "mortgage": round(monthly_mortgage, 2),
            "property_tax": round(monthly_tax, 2),
            "insurance": round(monthly_ins, 2),
            "hoa": round(hoa, 2),
            "maintenance": round(monthly_maint, 2),
            "rental_offset": round(rental, 2),
        },
    }


def _calc_vehicle(params: dict, ctx: dict) -> dict:
    price = params.get("purchase_price", 60000)
    down = params.get("down_payment", 10000)
    rate = params.get("loan_rate_pct", 5.5)
    term = params.get("loan_term_months", 60)
    ins = params.get("insurance_monthly", 200)
    fuel = params.get("fuel_monthly", 150)
    maint = params.get("maintenance_annual", 1200) / 12
    trade_in = params.get("trade_in_value", 0)

    net_price = price - trade_in
    loan_amount = max(0, net_price - down)
    monthly_loan = _calc_monthly_payment(loan_amount, rate, term)
    total_monthly = monthly_loan + ins + fuel + maint
    total_cost = down + (monthly_loan * term) + (ins + fuel + maint) * term

    surplus_after = ctx["monthly_surplus"] - total_monthly
    savings_rate_after = (surplus_after / ctx["monthly_take_home"] * 100) if ctx["monthly_take_home"] > 0 else 0
    new_debt = ctx["current_monthly_debt"] + monthly_loan
    dti_after = (new_debt / (ctx["annual_income"] / 12) * 100) if ctx["annual_income"] > 0 else 0

    return {
        "total_cost": round(total_cost, 0),
        "new_monthly_payment": round(total_monthly, 2),
        "monthly_surplus_after": round(surplus_after, 2),
        "savings_rate_after_pct": round(savings_rate_after, 1),
        "dti_after_pct": round(dti_after, 1),
        "loan_amount": round(loan_amount, 0),
        "breakdown": {
            "loan_payment": round(monthly_loan, 2),
            "insurance": round(ins, 2),
            "fuel": round(fuel, 2),
            "maintenance": round(maint, 2),
        },
    }


def _calc_renovation(params: dict, ctx: dict) -> dict:
    cost = params.get("renovation_cost", 50000)
    fin_pct = params.get("financing_pct", 0)
    rate = params.get("loan_rate_pct", 7.0)
    term = params.get("loan_term_years", 10)
    value_increase = params.get("expected_value_increase", 30000)

    financed = cost * fin_pct / 100
    out_of_pocket = cost - financed
    monthly_loan = _calc_monthly_payment(financed, rate, term * 12) if financed > 0 else 0

    surplus_after = ctx["monthly_surplus"] - monthly_loan
    roi = ((value_increase - cost) / cost * 100) if cost > 0 else 0

    return {
        "total_cost": round(cost, 0),
        "new_monthly_payment": round(monthly_loan, 2),
        "monthly_surplus_after": round(surplus_after, 2),
        "savings_rate_after_pct": round(
            (surplus_after / ctx["monthly_take_home"] * 100) if ctx["monthly_take_home"] > 0 else 0, 1
        ),
        "dti_after_pct": round(ctx["dti_before"] + (monthly_loan / (ctx["annual_income"] / 12) * 100 if ctx["annual_income"] > 0 else 0), 1),
        "out_of_pocket": round(out_of_pocket, 0),
        "roi_pct": round(roi, 1),
        "breakdown": {
            "out_of_pocket": round(out_of_pocket, 2),
            "financed": round(financed, 2),
            "monthly_payment": round(monthly_loan, 2),
            "expected_value_add": round(value_increase, 0),
        },
    }


def _calc_college(params: dict, ctx: dict) -> dict:
    child_age = params.get("child_current_age", 5)
    start_age = params.get("college_start_age", 18)
    tuition = params.get("annual_tuition_today", 40000)
    years_college = params.get("years_of_college", 4)
    inflation = params.get("tuition_inflation_pct", 5)
    balance_529 = params.get("current_529_balance", 0)
    ret = params.get("expected_return_pct", 6)

    years_until = max(0, start_age - child_age)
    total_needed = sum(
        tuition * (1 + inflation / 100) ** (years_until + y)
        for y in range(years_college)
    )

    monthly_return = ret / 100 / 12
    months = years_until * 12
    if monthly_return > 0 and months > 0:
        fv_current = balance_529 * (1 + monthly_return) ** months
        monthly_needed = (total_needed - fv_current) * monthly_return / ((1 + monthly_return) ** months - 1)
        monthly_needed = max(0, monthly_needed)
    else:
        fv_current = balance_529
        monthly_needed = (total_needed - fv_current) / max(months, 1)

    surplus_after = ctx["monthly_surplus"] - monthly_needed

    return {
        "total_cost": round(total_needed, 0),
        "new_monthly_payment": round(monthly_needed, 2),
        "monthly_surplus_after": round(surplus_after, 2),
        "savings_rate_after_pct": round(
            (surplus_after / ctx["monthly_take_home"] * 100) if ctx["monthly_take_home"] > 0 else 0, 1
        ),
        "dti_after_pct": round(ctx["dti_before"], 1),
        "years_until_college": years_until,
        "projected_529_at_start": round(fv_current, 0),
        "breakdown": {
            "total_tuition_inflation_adjusted": round(total_needed, 0),
            "current_529_projected": round(fv_current, 0),
            "gap": round(max(0, total_needed - fv_current), 0),
            "monthly_savings_needed": round(monthly_needed, 2),
        },
    }


def _calc_business(params: dict, ctx: dict) -> dict:
    startup = params.get("startup_costs", 50000)
    monthly_ops = params.get("monthly_operating_costs", 5000)
    months_no_rev = params.get("months_to_revenue", 6)
    rev_y1 = params.get("expected_monthly_revenue_year1", 8000)
    living = params.get("salary_replacement_needed", 8000)
    ef_months = params.get("emergency_fund_months", 6)

    runway_needed = startup + (monthly_ops + living) * months_no_rev + living * ef_months
    net_monthly_y1 = rev_y1 - monthly_ops - living
    months_to_breakeven = math.ceil(startup / max(net_monthly_y1, 1)) if net_monthly_y1 > 0 else 999

    return {
        "total_cost": round(runway_needed, 0),
        "new_monthly_payment": round(monthly_ops + living, 2),
        "monthly_surplus_after": round(net_monthly_y1, 2),
        "savings_rate_after_pct": 0,
        "dti_after_pct": round(ctx["dti_before"], 1),
        "runway_needed": round(runway_needed, 0),
        "can_self_fund": runway_needed <= (ctx["current_savings"] + ctx["current_investments"]) * 0.5,
        "months_to_breakeven": months_to_breakeven,
        "breakdown": {
            "startup_costs": round(startup, 0),
            "burn_rate_monthly": round(monthly_ops + living, 2),
            "revenue_year1_monthly": round(rev_y1, 2),
            "net_monthly_year1": round(net_monthly_y1, 2),
        },
    }


def _calc_sabbatical(params: dict, ctx: dict) -> dict:
    duration = params.get("duration_months", 6)
    expenses = params.get("monthly_expenses_during", 6000)
    travel = params.get("travel_budget", 10000)
    health = params.get("health_insurance_monthly", 800)
    income = params.get("expected_income_during", 0)

    monthly_cost = expenses + health - income
    total_cost = monthly_cost * duration + travel
    lost_income = (ctx["annual_income"] / 12) * duration
    total_impact = total_cost + lost_income

    can_afford = total_cost <= ctx["current_savings"] * 0.4

    return {
        "total_cost": round(total_cost, 0),
        "new_monthly_payment": round(monthly_cost, 2),
        "monthly_surplus_after": round(-monthly_cost, 2),
        "savings_rate_after_pct": 0,
        "dti_after_pct": round(ctx["dti_before"], 1),
        "lost_income": round(lost_income, 0),
        "total_financial_impact": round(total_impact, 0),
        "can_afford_from_savings": can_afford,
        "breakdown": {
            "monthly_expenses": round(expenses, 2),
            "health_insurance": round(health, 2),
            "travel_budget": round(travel, 0),
            "income_offset": round(income, 2),
            "lost_salary": round(lost_income, 0),
        },
    }


def _calc_lifestyle(params: dict, ctx: dict) -> dict:
    monthly_increase = params.get("monthly_cost_increase", 500)
    one_time = params.get("one_time_cost", 2000)

    annual_cost = monthly_increase * 12 + one_time
    surplus_after = ctx["monthly_surplus"] - monthly_increase
    savings_rate_after = (surplus_after / ctx["monthly_take_home"] * 100) if ctx["monthly_take_home"] > 0 else 0

    return {
        "total_cost": round(annual_cost, 0),
        "new_monthly_payment": round(monthly_increase, 2),
        "monthly_surplus_after": round(surplus_after, 2),
        "savings_rate_after_pct": round(savings_rate_after, 1),
        "dti_after_pct": round(ctx["dti_before"], 1),
        "one_time_cost": round(one_time, 0),
        "annual_recurring": round(monthly_increase * 12, 0),
        "breakdown": {
            "one_time": round(one_time, 2),
            "monthly_recurring": round(monthly_increase, 2),
        },
    }


def _calc_early_retirement(params: dict, ctx: dict) -> dict:
    target_age = params.get("target_retirement_age", 50)
    annual_expenses = params.get("annual_expenses_in_retirement", 80000)
    savings = params.get("current_savings", 500000)
    monthly_saving = params.get("monthly_savings", 5000)
    ret_pct = params.get("expected_return_pct", 7)
    ss_age = params.get("social_security_age", 67)
    ss_monthly = params.get("social_security_monthly", 2500)

    current_age = params.get("current_age", 0) or ctx.get("current_age", 0) or max(25, target_age - 15)
    years_to_retire = max(0, target_age - current_age)

    monthly_return = ret_pct / 100 / 12
    months = years_to_retire * 12
    if monthly_return > 0 and months > 0:
        projected = savings * (1 + monthly_return) ** months + monthly_saving * (
            ((1 + monthly_return) ** months - 1) / monthly_return
        )
    else:
        projected = savings + monthly_saving * months

    fire_number = annual_expenses * 25
    gap = projected - fire_number
    years_gap_to_ss = max(0, ss_age - target_age)

    return {
        "total_cost": round(fire_number, 0),
        "new_monthly_payment": round(annual_expenses / 12, 2),
        "monthly_surplus_after": round(0, 2),
        "savings_rate_after_pct": 0,
        "dti_after_pct": 0,
        "fire_number": round(fire_number, 0),
        "projected_at_target_age": round(projected, 0),
        "gap": round(gap, 0),
        "feasible": gap >= 0,
        "years_until_ss": years_gap_to_ss,
        "breakdown": {
            "fire_number_25x": round(fire_number, 0),
            "projected_savings": round(projected, 0),
            "annual_withdrawal_4pct": round(projected * 0.04, 0),
            "annual_expenses_needed": round(annual_expenses, 0),
            "ss_bridge_gap_years": years_gap_to_ss,
        },
    }


CALCULATORS = {
    "second_home": _calc_second_home,
    "vehicle": _calc_vehicle,
    "home_renovation": _calc_renovation,
    "college_fund": _calc_college,
    "starting_business": _calc_business,
    "sabbatical": _calc_sabbatical,
    "lifestyle_upgrade": _calc_lifestyle,
    "early_retirement": _calc_early_retirement,
}


def _compute_affordability_score(result: dict, ctx: dict) -> float:
    """
    0-100 score based on:
    - Monthly surplus remaining (40% weight)
    - Savings rate after (25% weight)
    - DTI after (20% weight)
    - Can afford upfront costs (15% weight)
    """
    score = 0.0

    # Monthly surplus: positive is good
    surplus = result.get("monthly_surplus_after", 0)
    if surplus >= ctx["monthly_take_home"] * 0.2:
        score += 40
    elif surplus >= ctx["monthly_take_home"] * 0.1:
        score += 30
    elif surplus >= 0:
        score += 20
    elif surplus >= -ctx["monthly_take_home"] * 0.1:
        score += 10
    # else: 0

    # Savings rate after
    sr = result.get("savings_rate_after_pct", 0)
    if sr >= 20:
        score += 25
    elif sr >= 15:
        score += 20
    elif sr >= 10:
        score += 15
    elif sr >= 5:
        score += 10
    elif sr > 0:
        score += 5

    # DTI after
    dti = result.get("dti_after_pct", 0)
    if dti < 28:
        score += 20
    elif dti < 36:
        score += 15
    elif dti < 43:
        score += 10
    elif dti < 50:
        score += 5

    # Upfront cost feasibility
    total = result.get("total_cost", 0) or result.get("down_payment_needed", 0)
    liquid = ctx["current_savings"] + ctx["current_investments"]
    if total <= liquid * 0.3:
        score += 15
    elif total <= liquid * 0.5:
        score += 10
    elif total <= liquid * 0.7:
        score += 5

    return min(100, max(0, score))


def _score_to_verdict(score: float) -> str:
    if score >= 80:
        return "comfortable"
    if score >= 60:
        return "feasible"
    if score >= 40:
        return "stretch"
    if score >= 20:
        return "risky"
    return "not_recommended"
