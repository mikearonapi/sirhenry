import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import DashboardOut, FinancialPeriodOut, MonthlyReportOut, TransactionOut
from pipeline.db import get_financial_periods, get_tax_strategies, get_transactions
from pipeline.db.schema import FinancialPeriod
from sqlalchemy import select

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    session: AsyncSession = Depends(get_session),
):
    now = datetime.now(timezone.utc)
    is_current_year = year is None or year == now.year
    year = year or now.year

    if month is not None:
        display_month = month
    elif is_current_year:
        display_month = now.month
    else:
        display_month = 12

    periods = await get_financial_periods(session, year=year, segment="all")
    period_map: dict[Optional[int], FinancialPeriod] = {p.month: p for p in periods}

    # For current year: YTD up to current month. For past years: full year.
    end_month = display_month
    ytd_income = sum(
        (period_map[m].total_income for m in range(1, end_month + 1) if m in period_map), 0.0
    )
    ytd_expenses = sum(
        (period_map[m].total_expenses for m in range(1, end_month + 1) if m in period_map), 0.0
    )
    ytd_net = ytd_income - ytd_expenses

    from pipeline.tax import total_tax_estimate
    from pipeline.db.schema import HouseholdProfile
    hp_result = await session.execute(select(HouseholdProfile).limit(1))
    hp = hp_result.scalar_one_or_none()
    filing_status = hp.filing_status if hp and hp.filing_status else "mfj"

    tax_breakdown = total_tax_estimate(w2_wages=ytd_income, filing_status=filing_status)
    ytd_tax_estimate = tax_breakdown["total_tax"]

    current = period_map.get(display_month)
    current_income = current.total_income if current else 0.0
    current_expenses = current.total_expenses if current else 0.0
    current_net = current_income - current_expenses

    monthly_tax = total_tax_estimate(
        w2_wages=current_income * 12, filing_status=filing_status
    )
    current_month_tax_estimate = monthly_tax["total_tax"] / 12

    recent = await get_transactions(session, limit=10, offset=0, year=year)

    trend = [p for p in periods if p.month is not None]
    trend.sort(key=lambda p: p.month or 0)

    strategies = await get_tax_strategies(session, tax_year=year)

    return DashboardOut(
        current_year=year,
        current_month=display_month,
        ytd_income=ytd_income,
        ytd_expenses=ytd_expenses,
        ytd_net=ytd_net,
        ytd_tax_estimate=ytd_tax_estimate,
        current_month_income=current_income,
        current_month_expenses=current_expenses,
        current_month_net=current_net,
        current_month_tax_estimate=current_month_tax_estimate,
        recent_transactions=[TransactionOut.model_validate(t) for t in recent],
        monthly_trend=[FinancialPeriodOut.model_validate(p) for p in trend],
        top_strategies_count=len(strategies),
    )


@router.get("/monthly", response_model=MonthlyReportOut)
async def get_monthly_report(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    include_ai_insights: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    from pipeline.ai.report_gen import compute_period_summary, generate_monthly_insights

    period_data = await compute_period_summary(session, year, month=month)

    # Prior month (wrap January to December of prior year)
    prior_month = month - 1 if month > 1 else 12
    prior_year = year if month > 1 else year - 1
    prior_data: Optional[dict] = None
    prior_data = await compute_period_summary(session, prior_year, month=prior_month)

    # Top expense categories
    expense_breakdown = json.loads(period_data.get("expense_breakdown") or "{}")
    income_breakdown = json.loads(period_data.get("income_breakdown") or "{}")

    top_expenses = [
        {"category": k, "amount": v}
        for k, v in sorted(expense_breakdown.items(), key=lambda x: x[1], reverse=True)[:8]
    ]
    top_incomes = [
        {"source": k, "amount": v}
        for k, v in sorted(income_breakdown.items(), key=lambda x: x[1], reverse=True)[:5]
    ]

    vs_prior = None
    if prior_data:
        vs_prior = {
            "income_delta": period_data["total_income"] - prior_data["total_income"],
            "expense_delta": period_data["total_expenses"] - prior_data["total_expenses"],
            "net_delta": period_data["net_cash_flow"] - prior_data["net_cash_flow"],
        }

    ai_insights = None
    if include_ai_insights:
        ai_insights = await generate_monthly_insights(
            session, year, month, period_data, prior_data
        )

    # Fetch stored period
    result = await session.execute(
        select(FinancialPeriod).where(
            FinancialPeriod.year == year,
            FinancialPeriod.month == month,
            FinancialPeriod.segment == "all",
        )
    )
    period_obj = result.scalar_one_or_none()

    return MonthlyReportOut(
        period=FinancialPeriodOut.model_validate(period_obj) if period_obj else FinancialPeriodOut(
            id=0, **period_data, computed_at=datetime.now(timezone.utc)
        ),
        top_expense_categories=top_expenses,
        top_income_sources=top_incomes,
        vs_prior_month=vs_prior,
        ai_insights=ai_insights,
    )


@router.get("/periods", response_model=list[FinancialPeriodOut])
async def list_periods(
    year: Optional[int] = Query(None),
    segment: str = Query("all"),
    session: AsyncSession = Depends(get_session),
):
    periods = await get_financial_periods(session, year=year, segment=segment)
    return [FinancialPeriodOut.model_validate(p) for p in periods]


@router.post("/recompute")
async def recompute_periods(
    year: int = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Recompute all period summaries for a year (call after bulk imports)."""
    from pipeline.ai.report_gen import recompute_all_periods
    results = await recompute_all_periods(session, year)
    return {"recomputed": len(results), "year": year}
