"""
Benchmarking engine: personal financial health assessment using
Federal Reserve SCF data, and Financial Order of Operations
(Money Guy Show framework).
"""
import bisect
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Net worth by age — percentiles from Federal Reserve Survey of Consumer Finances (2022)
# Format: {age_bracket: {percentile: net_worth}}
NW_BY_AGE = {
    30: {10: -30_000, 25: 7_500, 50: 35_000, 75: 130_000, 90: 350_000},
    35: {10: -20_000, 25: 20_000, 50: 75_000, 75: 250_000, 90: 600_000},
    40: {10: -10_000, 25: 40_000, 50: 130_000, 75: 400_000, 90: 900_000},
    45: {10: 0, 25: 55_000, 50: 180_000, 75: 550_000, 90: 1_300_000},
    50: {10: 5_000, 25: 70_000, 50: 250_000, 75: 750_000, 90: 1_700_000},
    55: {10: 10_000, 25: 95_000, 50: 350_000, 75: 1_000_000, 90: 2_200_000},
    60: {10: 15_000, 25: 120_000, 50: 420_000, 75: 1_200_000, 90: 2_800_000},
    65: {10: 20_000, 25: 150_000, 50: 500_000, 75: 1_500_000, 90: 3_200_000},
}

# Savings rates by income band (rough benchmarks)
SAVINGS_RATE_BY_INCOME = {
    75_000: {25: 5, 50: 10, 75: 15},
    100_000: {25: 8, 50: 13, 75: 20},
    150_000: {25: 10, 50: 15, 75: 22},
    200_000: {25: 12, 50: 18, 75: 25},
    300_000: {25: 15, 50: 22, 75: 30},
    500_000: {25: 18, 50: 25, 75: 35},
}


def _interpolate_percentile(value: float, benchmarks: dict[int, float]) -> float:
    """Given a value and {percentile: benchmark_value}, estimate which percentile the value falls at."""
    pts = sorted(benchmarks.items(), key=lambda x: x[1])
    if value <= pts[0][1]:
        if pts[0][1] < 0 and value < 0:
            # For negative benchmarks: deeper negatives = lower percentile
            ratio = pts[0][1] / value if value != 0 else 0
            return max(0, pts[0][0] * min(1, ratio))
        elif pts[0][1] > 0:
            return max(0, pts[0][0] * (value / pts[0][1]))
        else:
            return max(0, pts[0][0] * 0.5)
    if value >= pts[-1][1]:
        return min(99, pts[-1][0] + (99 - pts[-1][0]) * min(1, (value - pts[-1][1]) / max(1, pts[-1][1])))
    for i in range(len(pts) - 1):
        p1, v1 = pts[i]
        p2, v2 = pts[i + 1]
        if v1 <= value <= v2:
            frac = (value - v1) / (v2 - v1) if v2 != v1 else 0
            return p1 + frac * (p2 - p1)
    return 50


def _nearest_bracket(age: int, table: dict) -> dict:
    ages = sorted(table.keys())
    idx = bisect.bisect_right(ages, age)
    if idx == 0:
        return table[ages[0]]
    if idx >= len(ages):
        return table[ages[-1]]
    if age - ages[idx - 1] <= ages[idx] - age:
        return table[ages[idx - 1]]
    return table[ages[idx]]


class BenchmarkEngine:

    @staticmethod
    def compute_benchmarks(
        age: int,
        income: float,
        net_worth: float,
        savings_rate: float,
    ) -> dict:
        nw_brackets = _nearest_bracket(age, NW_BY_AGE)
        nw_percentile = _interpolate_percentile(net_worth, nw_brackets)

        income_keys = sorted(SAVINGS_RATE_BY_INCOME.keys())
        idx = bisect.bisect_right(income_keys, income)
        sr_key = income_keys[min(idx, len(income_keys) - 1)]
        sr_brackets = SAVINGS_RATE_BY_INCOME[sr_key]
        savings_percentile = _interpolate_percentile(savings_rate, sr_brackets)

        return {
            "user_age": age,
            "income": income,
            "net_worth": net_worth,
            "savings_rate": savings_rate,
            "nw_percentile": round(nw_percentile, 1),
            "savings_percentile": round(savings_percentile, 1),
            "nw_for_age_median": nw_brackets.get(50, 0),
            "nw_for_age_75th": nw_brackets.get(75, 0),
        }

    @staticmethod
    def financial_order_of_operations(
        has_employer_match: bool = False,
        employer_match_captured: bool = False,
        high_interest_debt: float = 0,
        emergency_fund_months: float = 0,
        hsa_contributions: float = 0,
        hsa_limit: float = 8300,
        roth_contributions: float = 0,
        roth_limit: float = 7000,
        contrib_401k: float = 0,
        limit_401k: float = 23500,
        has_mega_backdoor: bool = False,
        mega_backdoor_contrib: float = 0,
        mega_backdoor_limit: float = 46000,
        taxable_investing: float = 0,
        low_interest_debt: float = 0,
        monthly_expenses: float = 5000,
    ) -> list[dict]:
        """Build the personalized Financial Order of Operations.

        Uses the Money Guy Show framework, adapted for HENRYs.
        Descriptions are dynamically generated based on actual values.
        """
        def _next_status(prior_steps: list[dict]) -> str:
            return "next" if all(s["status"] == "done" for s in prior_steps) else "locked"

        steps: list[dict] = []

        # Step 1: Employer match
        if has_employer_match:
            done = employer_match_captured
            desc = (
                "You're capturing the full employer match."
                if done else
                "Contribute enough to get the full 401(k) employer match — it's free money."
            )
            steps.append({
                "step": 1, "name": "Capture Employer Match",
                "description": desc,
                "status": "done" if done else "next",
                "current_value": None, "target_value": None, "link": "/retirement",
            })
        else:
            steps.append({
                "step": 1, "name": "Capture Employer Match",
                "description": "No employer match detected. If you have one, update your benefits in Household.",
                "status": "done", "current_value": None, "target_value": None, "link": "/household",
            })

        # Step 2: High-interest debt (credit cards, >6%)
        done = high_interest_debt <= 0
        if done:
            desc = "No high-interest debt — you're clear."
        else:
            desc = f"${high_interest_debt:,.0f} in credit card / high-interest debt. Eliminate this before optimizing savings."
        steps.append({
            "step": 2, "name": "Pay Off High-Interest Debt",
            "description": desc,
            "status": "done" if done else _next_status(steps),
            "current_value": high_interest_debt, "target_value": 0, "link": "/accounts",
        })

        # Step 3: Emergency fund (3-6 months of expenses)
        target_ef = round(monthly_expenses * 6, 2)
        current_ef = round(emergency_fund_months * monthly_expenses, 2)
        done = emergency_fund_months >= 3
        if done:
            months_str = f"{emergency_fund_months:.1f}"
            desc = f"You have ~{months_str} months of expenses in liquid savings."
        else:
            desc = f"You have ~{emergency_fund_months:.1f} months saved. Target 3-6 months (${target_ef:,.0f}) in a HYSA."
        steps.append({
            "step": 3, "name": "Build Emergency Fund (3-6 months)",
            "description": desc,
            "status": "done" if done else _next_status(steps),
            "current_value": current_ef, "target_value": target_ef, "link": "/goals",
        })

        # Step 4: Max HSA
        done = hsa_contributions >= hsa_limit * 0.95
        gap = max(0, hsa_limit - hsa_contributions)
        if done:
            desc = f"HSA is maxed at ${hsa_contributions:,.0f}."
        else:
            desc = f"${gap:,.0f} remaining to max HSA. Triple tax advantage: deductible, tax-free growth, tax-free medical withdrawals."
        steps.append({
            "step": 4, "name": "Max HSA",
            "description": desc,
            "status": "done" if done else _next_status(steps),
            "current_value": hsa_contributions, "target_value": hsa_limit, "link": "/household",
        })

        # Step 5: Max Roth IRA (or Backdoor Roth for HENRYs)
        done = roth_contributions >= roth_limit * 0.95
        gap = max(0, roth_limit - roth_contributions)
        if done:
            desc = f"Roth IRA is maxed at ${roth_contributions:,.0f}."
        else:
            desc = f"${gap:,.0f} remaining. Tax-free growth and withdrawals. Use backdoor if income exceeds Roth limits."
        steps.append({
            "step": 5, "name": "Max Roth IRA (or Backdoor Roth)",
            "description": desc,
            "status": "done" if done else _next_status(steps),
            "current_value": roth_contributions, "target_value": roth_limit, "link": "/tax-strategy",
        })

        # Step 6: Max 401(k) / 403(b)
        done = contrib_401k >= limit_401k * 0.95
        gap = max(0, limit_401k - contrib_401k)
        if done:
            desc = f"401(k) is maxed at ${contrib_401k:,.0f}."
        else:
            desc = f"${gap:,.0f} remaining to max 401(k). Reduces your taxable income dollar-for-dollar."
        steps.append({
            "step": 6, "name": "Max 401(k) / 403(b)",
            "description": desc,
            "status": "done" if done else _next_status(steps),
            "current_value": contrib_401k, "target_value": limit_401k, "link": "/retirement",
        })

        # Step 7: Mega Backdoor Roth (only if plan supports it)
        if has_mega_backdoor:
            done = mega_backdoor_contrib >= mega_backdoor_limit * 0.95
            gap = max(0, mega_backdoor_limit - mega_backdoor_contrib)
            if done:
                desc = f"Mega backdoor Roth is maxed at ${mega_backdoor_contrib:,.0f}."
            else:
                desc = f"${gap:,.0f} remaining. After-tax 401(k) → Roth conversion for additional tax-free growth."
            steps.append({
                "step": 7, "name": "Mega Backdoor Roth",
                "description": desc,
                "status": "done" if done else _next_status(steps),
                "current_value": mega_backdoor_contrib, "target_value": mega_backdoor_limit, "link": "/tax-strategy",
            })

        # Step 8: Taxable brokerage investing
        all_prior_done = all(s["status"] == "done" for s in steps)
        if taxable_investing > 0 and all_prior_done:
            status = "in_progress"
            desc = f"${taxable_investing:,.0f} invested in taxable accounts. Keep building after tax-advantaged space is full."
        elif all_prior_done:
            status = "next"
            desc = "All tax-advantaged space is full. Invest in low-cost index funds in a taxable brokerage."
        else:
            status = "locked"
            desc = "Invest in taxable accounts after maxing all tax-advantaged space."
        steps.append({
            "step": len(steps) + 1, "name": "Taxable Brokerage Investing",
            "description": desc, "status": status,
            "current_value": taxable_investing, "target_value": None, "link": "/portfolio",
        })

        # Step 9: Low-interest debt paydown
        done = low_interest_debt <= 0
        if done:
            desc = "No low-interest debt remaining."
        else:
            desc = f"${low_interest_debt:,.0f} in student loans / low-rate debt. Pay extra once higher-priority items are handled."
        steps.append({
            "step": len(steps) + 1, "name": "Pay Off Low-Interest Debt",
            "description": desc,
            "status": "done" if done else "locked",
            "current_value": low_interest_debt, "target_value": 0, "link": "/accounts",
        })

        # Enforce exactly one "next" step
        found_next = False
        for s in steps:
            if s["status"] == "next":
                if found_next:
                    s["status"] = "locked"
                found_next = True

        return steps
