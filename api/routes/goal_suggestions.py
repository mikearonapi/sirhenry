"""Goal suggestions — personalized goal recommendations based on user data."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db.schema import (
    HouseholdProfile,
    ManualAsset,
    EquityGrant,
    Goal,
)

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("/suggestions")
async def suggest_goals(session: AsyncSession = Depends(get_session)):
    """Return personalized goal suggestions based on household, assets, and equity."""

    suggestions: list[dict] = []

    # Load user data
    hp_result = await session.execute(
        select(HouseholdProfile).order_by(HouseholdProfile.is_primary.desc()).limit(1)
    )
    household = hp_result.scalar_one_or_none()

    assets_result = await session.execute(select(ManualAsset).where(ManualAsset.is_active == True))
    assets = list(assets_result.scalars().all())

    grants_result = await session.execute(select(EquityGrant).where(EquityGrant.is_active == True))
    grants = list(grants_result.scalars().all())

    existing_result = await session.execute(
        select(Goal.goal_type).where(Goal.status.in_(["active", "completed"]))
    )
    existing_types = set(existing_result.scalars().all())

    # Calculate income-based amounts
    annual_income = 200000  # default HENRY income
    if household:
        income = (household.primary_w2_income or 0) + (household.spouse_w2_income or 0)
        if income > 0:
            annual_income = income

    monthly_income = annual_income / 12

    # 1. Emergency Fund (if not already set)
    if "emergency_fund" not in existing_types:
        target = round(monthly_income * 6, -2)  # 6 months, rounded to nearest 100
        suggestions.append({
            "name": "Emergency Fund (6 months)",
            "goal_type": "emergency_fund",
            "target_amount": target,
            "monthly_contribution": round(target / 24, -1),  # 2-year plan
            "description": f"6 months of income ({monthly_income:,.0f}/mo) as your safety net",
            "color": "#22c55e",
            "priority": 1,
        })

    # 2. Student Loans (if liabilities exist)
    student_liabilities = [
        a for a in assets
        if a.is_liability and a.asset_type == "other"
        and a.name and "student" in a.name.lower()
    ]
    if student_liabilities and "debt_payoff" not in existing_types:
        total_loans = sum(a.current_value for a in student_liabilities)
        suggestions.append({
            "name": "Pay Off Student Loans",
            "goal_type": "debt_payoff",
            "target_amount": total_loans,
            "monthly_contribution": round(total_loans / 48, -1),  # 4-year plan
            "description": f"Eliminate ${total_loans:,.0f} in student debt",
            "color": "#6366f1",
            "priority": 2,
        })
    elif "debt_payoff" not in existing_types:
        suggestions.append({
            "name": "Pay Off Student Loans",
            "goal_type": "debt_payoff",
            "target_amount": 100000,
            "monthly_contribution": 2500,
            "description": "Accelerate student debt payoff to free up cash flow",
            "color": "#6366f1",
            "priority": 2,
        })

    # 3. House Down Payment
    if "purchase" not in existing_types:
        suggestions.append({
            "name": "House Down Payment",
            "goal_type": "purchase",
            "target_amount": round(annual_income * 0.75, -3),  # ~75% of income = ~20% of 3.75x
            "monthly_contribution": round(annual_income * 0.75 / 36, -1),  # 3-year plan
            "description": "20% down payment fund for your first home",
            "color": "#3b82f6",
            "priority": 3,
        })

    # 4. Max Tax-Advantaged Accounts
    if "tax" not in existing_types:
        # 2026 limits: 401k $23,500 + IRA $7,000
        target = 30500
        suggestions.append({
            "name": "Max Tax-Advantaged Accounts",
            "goal_type": "tax",
            "target_amount": target,
            "monthly_contribution": round(target / 12),
            "description": "Max out 401(k) and IRA contributions this year",
            "color": "#f59e0b",
            "priority": 4,
        })

    # 5. RSU Tax Reserve (if equity grants exist)
    rsu_grants = [g for g in grants if g.grant_type == "rsu"]
    if rsu_grants:
        annual_vest = sum(
            (g.unvested_shares or 0) * (g.current_fmv or 0) / max(1, 4)  # ~4 vests/year
            for g in rsu_grants
        )
        if annual_vest > 0:
            gap = round(annual_vest * 0.15, -2)  # ~15% underwithholding gap
            suggestions.append({
                "name": "RSU Tax Withholding Reserve",
                "goal_type": "tax",
                "target_amount": gap,
                "monthly_contribution": round(gap / 12, -1),
                "description": f"Cover the ~${gap:,.0f} underwithholding gap on RSU vests",
                "color": "#ef4444",
                "priority": 5,
            })

    # 6. Wealth Building
    if "investment" not in existing_types:
        suggestions.append({
            "name": "Wealth Building (Taxable Brokerage)",
            "goal_type": "investment",
            "target_amount": 100000,
            "monthly_contribution": 3000,
            "description": "Build long-term wealth beyond retirement accounts",
            "color": "#06b6d4",
            "priority": 6,
        })

    suggestions.sort(key=lambda s: s["priority"])
    return {"suggestions": suggestions, "annual_income": annual_income}
