"""Insurance gap analysis and life insurance need calculations.

Pure computation — all data is passed in, no direct DB access.  The route
layer is responsible for querying policies, benefit packages, etc. and
handing them to these functions.
"""
from datetime import date
from typing import Any


def calculate_life_insurance_need(
    income: float,
    years_to_replace: int = 10,
    debt: float = 0,
    dependents: int = 0,
) -> float:
    """DIME-method approximation for life insurance need.

    ``Debt + Income replacement + Mortgage + Education`` simplified to:
    ``income * years_to_replace + debt + (dependents * 50_000)``.
    """
    education_estimate = dependents * 50_000
    return income * years_to_replace + debt + education_estimate


def analyze_insurance_gaps(
    *,
    spouse_a_income: float,
    spouse_b_income: float,
    total_debt: float,
    dependents: int,
    net_worth: float,
    policies: list[Any],
    benefit_packages: list[Any],
) -> dict:
    """Analyse insurance coverage gaps for a household.

    Parameters
    ----------
    spouse_a_income / spouse_b_income:
        Gross annual income for each spouse.
    total_debt:
        Outstanding household debt (used for life-insurance DIME calc).
    dependents:
        Number of dependent children (used for education funding estimate).
    net_worth:
        Household net worth (drives umbrella-policy recommendation).
    policies:
        Active ``InsurancePolicy`` ORM objects (or duck-typed equivalents).
    benefit_packages:
        ``BenefitPackage`` ORM objects for employer-provided coverage.

    Returns
    -------
    dict  matching the shape expected by the ``/insurance/gap-analysis``
    endpoint response.
    """
    combined_income = spouse_a_income + spouse_b_income

    # Aggregate employer-provided coverage from benefit packages
    employer_life_total = 0.0
    employer_std_monthly = 0.0
    employer_ltd_monthly = 0.0
    for bp in benefit_packages:
        employer_life_total += bp.life_insurance_coverage or 0
        spouse_income = spouse_a_income if bp.spouse == "A" else spouse_b_income
        if bp.std_coverage_pct:
            employer_std_monthly += spouse_income * (bp.std_coverage_pct / 100) / 12
        if bp.ltd_coverage_pct:
            employer_ltd_monthly += spouse_income * (bp.ltd_coverage_pct / 100) / 12

    # Group policies by type
    by_type: dict[str, list[Any]] = {}
    for p in policies:
        by_type.setdefault(p.policy_type, []).append(p)

    gaps: list[dict] = []
    total_annual_premium = sum(
        (p.annual_premium or 0) for p in policies if p.is_active
    )

    # --- Life insurance gap ---
    gaps.append(_life_insurance_gap(
        by_type, employer_life_total,
        spouse_a_income, spouse_b_income,
        total_debt, dependents,
    ))

    # --- Disability insurance gap ---
    gaps.append(_disability_gap(
        by_type, combined_income,
        spouse_a_income, spouse_b_income,
        employer_std_monthly, employer_ltd_monthly,
    ))

    # --- Umbrella policy gap ---
    gaps.append(_umbrella_gap(by_type, net_worth))

    # --- Policies renewing soon ---
    renewing_soon = _renewing_soon(policies)

    high_severity_count = sum(1 for g in gaps if g["severity"] == "high")
    medium_severity_count = sum(1 for g in gaps if g["severity"] == "medium")

    return {
        "total_policies": len(policies),
        "total_annual_premium": round(total_annual_premium),
        "total_monthly_premium": round(total_annual_premium / 12),
        "gaps": gaps,
        "high_severity_gaps": high_severity_count,
        "medium_severity_gaps": medium_severity_count,
        "renewing_soon": renewing_soon,
        "recommendations": [
            g["note"] for g in gaps if g["severity"] in ("high", "medium")
        ],
    }


# ------------------------------------------------------------------
# Internal gap calculators
# ------------------------------------------------------------------

def _life_insurance_gap(
    by_type: dict[str, list[Any]],
    employer_life_total: float,
    spouse_a_income: float,
    spouse_b_income: float,
    total_debt: float,
    dependents: int,
) -> dict:
    life_policies = by_type.get("life", [])
    personal_life_coverage = sum(p.coverage_amount or 0 for p in life_policies)
    total_life_coverage = personal_life_coverage + employer_life_total
    recommended_life_a = calculate_life_insurance_need(
        spouse_a_income, 10, total_debt / 2, dependents,
    )
    recommended_life_b = calculate_life_insurance_need(
        spouse_b_income, 10, total_debt / 2, dependents,
    )
    recommended_life = recommended_life_a + recommended_life_b
    life_gap = max(0, recommended_life - total_life_coverage)
    life_note = (
        f"Recommended: 10x combined income + debt. "
        f"Current total: ${total_life_coverage:,.0f}"
    )
    if employer_life_total > 0:
        life_note += f" (includes ${employer_life_total:,.0f} employer-provided)"
    life_note += f". Recommended: ${recommended_life:,.0f}."
    return {
        "type": "life",
        "label": "Life Insurance",
        "current_coverage": total_life_coverage,
        "recommended_coverage": round(recommended_life),
        "gap": round(life_gap),
        "severity": "high" if life_gap > 500_000 else "medium" if life_gap > 100_000 else "low",
        "employer_provided": employer_life_total,
        "note": life_note,
    }


def _disability_gap(
    by_type: dict[str, list[Any]],
    combined_income: float,
    spouse_a_income: float,
    spouse_b_income: float,
    employer_std_monthly: float,
    employer_ltd_monthly: float,
) -> dict:
    dis_policies = by_type.get("disability", [])
    has_ltd = any(
        "ltd" in (p.notes or "").lower() or "long" in (p.notes or "").lower()
        for p in dis_policies
    )
    recommended_disability_monthly = combined_income * 0.65 / 12
    personal_disability_monthly = sum(
        (p.coverage_amount or 0) / 12
        if (p.coverage_amount or 0) > 5000
        else (p.coverage_amount or 0)
        for p in dis_policies
    )
    covered_disability_monthly = (
        personal_disability_monthly + employer_std_monthly + employer_ltd_monthly
    )
    dis_gap = max(0, recommended_disability_monthly - covered_disability_monthly)
    employer_dis_monthly = employer_std_monthly + employer_ltd_monthly
    has_any_disability = dis_policies or employer_dis_monthly > 0

    dis_note = f"Recommended: 65% of combined income = ${recommended_disability_monthly:,.0f}/mo. "
    if not has_any_disability:
        dis_note += "No disability coverage found."
    else:
        dis_note += f"Current: ${covered_disability_monthly:,.0f}/mo"
        if employer_dis_monthly > 0:
            dis_note += f" (includes ${employer_dis_monthly:,.0f}/mo employer STD/LTD)"
        dis_note += "."
    return {
        "type": "disability",
        "label": "Disability Insurance",
        "current_coverage": round(covered_disability_monthly),
        "recommended_coverage": round(recommended_disability_monthly),
        "gap": round(dis_gap),
        "severity": "high" if not has_any_disability else ("medium" if dis_gap > 3000 else "low"),
        "employer_provided": round(employer_dis_monthly),
        "note": dis_note,
    }


def _umbrella_gap(
    by_type: dict[str, list[Any]],
    net_worth: float,
) -> dict:
    umbrella_policies = by_type.get("umbrella", [])
    needs_umbrella = net_worth > 300_000
    umbrella_gap = not umbrella_policies and needs_umbrella
    return {
        "type": "umbrella",
        "label": "Umbrella / Excess Liability",
        "current_coverage": sum(p.coverage_amount or 0 for p in umbrella_policies),
        "recommended_coverage": (
            max(1_000_000, int(net_worth / 1_000_000) * 1_000_000 + 1_000_000)
            if needs_umbrella
            else 0
        ),
        "gap": 0 if not umbrella_gap else 1_000_000,
        "severity": "medium" if umbrella_gap else "low",
        "note": (
            "Umbrella policy recommended when net worth exceeds $300k. "
            f"{'No umbrella policy found.' if not umbrella_policies else 'Umbrella coverage in place.'} "
            "Typically $1M-$5M coverage for ~$200-$500/year."
        ),
    }


def _renewing_soon(policies: list[Any]) -> list[dict]:
    today = date.today()
    renewing: list[dict] = []
    for p in policies:
        if p.renewal_date:
            try:
                rd = (
                    p.renewal_date
                    if isinstance(p.renewal_date, date)
                    else date.fromisoformat(str(p.renewal_date))
                )
                days_until = (rd - today).days
                if 0 <= days_until <= 60:
                    renewing.append({
                        "id": p.id,
                        "label": f"{p.policy_type.title()} — {p.provider or 'Unknown'}",
                        "renewal_date": str(rd),
                        "days_until": days_until,
                    })
            except Exception:
                pass
    return renewing
