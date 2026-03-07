"""
Scenario composition, multi-year projection, and retirement impact calculations.

Extracted from api/routes/scenarios_calc.py to keep routes thin.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Constants (formerly magic numbers in the route file)
# ---------------------------------------------------------------------------
DEFAULT_INCOME_GROWTH_RATE = 0.03
DEFAULT_INVESTMENT_RETURN_RATE = 0.07
DEFAULT_INFLATION_RATE = 0.02

AFFORDABILITY_THRESHOLDS = {
    "comfortable": 70,
    "feasible": 55,
    "stretch": 40,
    "risky": 25,
}

# Life-event → suggested scenario mapping
EVENT_TO_SCENARIO_MAP: dict[str, list[dict]] = {
    "real_estate_purchase": [
        {"scenario_type": "second_home", "label": "Model Home Purchase", "reason": "You recorded a real estate purchase — run the numbers"},
    ],
    "real_estate_sale": [
        {"scenario_type": "lifestyle_upgrade", "label": "Lifestyle Upgrade with Proceeds", "reason": "Home sale proceeds could fund an upgrade"},
        {"scenario_type": "early_retirement", "label": "Accelerate Retirement", "reason": "Could sale proceeds accelerate your FIRE timeline?"},
    ],
    "family_birth": [
        {"scenario_type": "college_fund", "label": "Start a College Fund", "reason": "New child — start a 529 plan early for max compound growth"},
    ],
    "family_adoption": [
        {"scenario_type": "college_fund", "label": "Start a College Fund", "reason": "Plan for education expenses with a 529"},
    ],
    "family_marriage": [
        {"scenario_type": "second_home", "label": "Buy a Home Together", "reason": "Combined income could support a home purchase"},
        {"scenario_type": "lifestyle_upgrade", "label": "Combined Lifestyle Adjustment", "reason": "Marriage changes your financial picture"},
    ],
    "employment_job_change": [
        {"scenario_type": "lifestyle_upgrade", "label": "Lifestyle Adjustment", "reason": "New job may change your income and expenses"},
    ],
    "employment_layoff": [
        {"scenario_type": "sabbatical", "label": "Plan Career Break", "reason": "Model how long your savings can sustain you"},
        {"scenario_type": "starting_business", "label": "Start a Business", "reason": "Layoff could be the push to go entrepreneurial"},
    ],
    "employment_start_business": [
        {"scenario_type": "starting_business", "label": "Business Viability Analysis", "reason": "Run the numbers on your new venture"},
    ],
    "education_college": [
        {"scenario_type": "college_fund", "label": "College Fund Calculator", "reason": "Model tuition costs and savings needed"},
    ],
}

DEFAULT_HENRY_SUGGESTIONS = [
    {"scenario_type": "second_home", "label": "Buy a Home", "reason": "Most HENRYs' biggest financial decision", "source": "default"},
    {"scenario_type": "college_fund", "label": "Start a College Fund", "reason": "Early 529 contributions have max compound growth", "source": "default"},
    {"scenario_type": "early_retirement", "label": "Early Retirement / FIRE", "reason": "See if your savings rate supports early retirement", "source": "default"},
    {"scenario_type": "starting_business", "label": "Side Business", "reason": "Many HENRYs build wealth through entrepreneurship", "source": "default"},
]


# ---------------------------------------------------------------------------
# Compose — combine multiple saved scenarios
# ---------------------------------------------------------------------------

def compose_scenarios(scenarios: list[Any]) -> dict:
    """Combine multiple saved scenario ORM objects into an aggregate impact view."""
    if not scenarios:
        return {
            "combined_monthly_impact": 0,
            "combined_savings_rate_after": 0,
            "combined_dti_after": 0,
            "combined_affordability_score": 50,
            "combined_verdict": "feasible",
            "scenarios": [],
        }
    combined_payment = sum(s.new_monthly_payment or 0 for s in scenarios)
    base = scenarios[0]
    take_home = base.monthly_take_home or 0
    expenses = base.current_monthly_expenses or 0
    income = base.annual_income or 0

    new_surplus = take_home - expenses - combined_payment
    sr_before = ((take_home - expenses) / take_home * 100) if take_home > 0 else 0
    sr_after = (new_surplus / take_home * 100) if take_home > 0 else 0
    dti_after = ((expenses + combined_payment) / (income / 12) * 100) if income > 0 else 0

    score = max(0, min(100, 50 + (new_surplus / take_home * 100) if take_home > 0 else 0))
    if score >= AFFORDABILITY_THRESHOLDS["comfortable"]:
        verdict = "comfortable"
    elif score >= AFFORDABILITY_THRESHOLDS["feasible"]:
        verdict = "feasible"
    elif score >= AFFORDABILITY_THRESHOLDS["stretch"]:
        verdict = "stretch"
    elif score >= AFFORDABILITY_THRESHOLDS["risky"]:
        verdict = "risky"
    else:
        verdict = "not_recommended"

    return {
        "combined_monthly_impact": round(combined_payment, 2),
        "combined_savings_rate_after": round(sr_after, 2),
        "combined_dti_after": round(dti_after, 2),
        "combined_affordability_score": round(score, 2),
        "combined_verdict": verdict,
        "scenarios": [
            {"id": s.id, "name": s.name, "monthly_impact": s.new_monthly_payment or 0}
            for s in scenarios
        ],
    }


# ---------------------------------------------------------------------------
# Multi-year projection
# ---------------------------------------------------------------------------

def project_multi_year(
    scenario: Any,
    years: int = 10,
    income_growth: float = DEFAULT_INCOME_GROWTH_RATE,
    inflation: float = DEFAULT_INFLATION_RATE,
    investment_return: float = DEFAULT_INVESTMENT_RETURN_RATE,
) -> dict:
    """Project net worth over N years given a scenario's financial parameters."""
    take_home = (scenario.monthly_take_home or 0) * 12
    expenses = (scenario.current_monthly_expenses or 0) * 12
    payment = (scenario.new_monthly_payment or 0) * 12
    savings = (scenario.current_savings or 0) + (scenario.current_investments or 0)

    year_data = []
    net_worth = savings
    for y in range(1, years + 1):
        annual_income = take_home * ((1 + income_growth) ** y)
        annual_expenses = (expenses + payment) * ((1 + inflation) ** y)
        annual_savings = annual_income - annual_expenses
        net_worth = net_worth * (1 + investment_return) + annual_savings
        year_data.append({
            "year": y,
            "net_worth": round(net_worth, 2),
            "savings": round(annual_savings, 2),
            "expenses": round(annual_expenses, 2),
            "cash_flow": round(annual_income - annual_expenses, 2),
        })

    return {"years": year_data}


# ---------------------------------------------------------------------------
# Retirement impact
# ---------------------------------------------------------------------------

def compute_retirement_impact(scenario: Any, retirement_profile: Any | None) -> dict:
    """Calculate how a scenario delays retirement based on reduced savings capacity."""
    if not retirement_profile:
        return {
            "current_retirement_age": 65, "new_retirement_age": 65,
            "years_delayed": 0, "current_fire_number": 0, "new_fire_number": 0,
        }

    r = retirement_profile
    monthly_impact = scenario.new_monthly_payment or 0
    annual_impact = monthly_impact * 12
    current_fire = r.fire_number or 0
    new_fire = current_fire + annual_impact * 25

    current_age = r.retirement_age or 65
    savings_monthly = r.monthly_retirement_contribution or 0
    reduced_savings = max(0, savings_monthly - monthly_impact)
    if reduced_savings > 0 and savings_monthly > 0:
        ratio = savings_monthly / reduced_savings
        delay = max(0, (ratio - 1) * (current_age - (r.current_age or 35)))
    else:
        delay = 5
    new_age = min(75, current_age + round(delay))

    return {
        "current_retirement_age": current_age,
        "new_retirement_age": new_age,
        "years_delayed": round(delay, 1),
        "current_fire_number": round(current_fire, 2),
        "new_fire_number": round(new_fire, 2),
    }


# ---------------------------------------------------------------------------
# Scenario comparison
# ---------------------------------------------------------------------------

def compare_scenario_metrics(scenario_a: Any, scenario_b: Any) -> dict:
    """Extract and diff metrics from two scenario ORM objects."""
    def _metrics(s: Any) -> dict:
        return {
            "monthly_payment": s.new_monthly_payment or 0,
            "total_cost": s.total_cost or 0,
            "savings_rate_after": s.savings_rate_after_pct or 0,
            "dti_after": s.dti_after_pct or 0,
            "affordability_score": s.affordability_score or 0,
        }

    ma = _metrics(scenario_a)
    mb = _metrics(scenario_b)
    diffs = {k: round(ma[k] - mb[k], 2) for k in ma}

    return {
        "scenario_a": {"id": scenario_a.id, "name": scenario_a.name, "metrics": ma},
        "scenario_b": {"id": scenario_b.id, "name": scenario_b.name, "metrics": mb},
        "differences": diffs,
    }


# ---------------------------------------------------------------------------
# Suggestions — event-based + equity-based
# ---------------------------------------------------------------------------

def build_scenario_suggestions(
    events: list[Any],
    grants: list[Any],
) -> list[dict]:
    """Build scenario suggestions from life events and equity grants."""
    suggestions: list[dict] = []
    seen_types: set[str] = set()

    # 1. Life event-based
    for event in events:
        key = f"{event.event_type}_{event.event_subtype}" if event.event_subtype else event.event_type
        mapped = EVENT_TO_SCENARIO_MAP.get(key, EVENT_TO_SCENARIO_MAP.get(event.event_type, []))
        for suggestion in mapped:
            if suggestion["scenario_type"] not in seen_types:
                suggestions.append({
                    **suggestion,
                    "source": "life_event",
                    "source_detail": event.title,
                })
                seen_types.add(suggestion["scenario_type"])

    # 2. Equity-based
    if grants and "lifestyle_upgrade" not in seen_types:
        total_vest_value = sum(
            (g.unvested_shares or 0) * (g.current_fmv or 0) for g in grants
        )
        if total_vest_value > 0:
            suggestions.append({
                "scenario_type": "lifestyle_upgrade",
                "label": "RSU Tax Reserve Strategy",
                "reason": f"~${total_vest_value:,.0f} in unvested equity — plan for tax withholding gaps",
                "source": "equity_grants",
            })

    # 3. Defaults
    if not suggestions:
        suggestions = list(DEFAULT_HENRY_SUGGESTIONS)

    return suggestions
