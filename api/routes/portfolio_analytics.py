"""Portfolio analytics — allocations, rebalancing, benchmarks, performance, tax-loss harvesting."""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import TargetAllocationIn
from pipeline.db import InvestmentHolding, CryptoHolding, PortfolioSnapshot, TargetAllocation
from pipeline.market.yahoo_finance import YahooFinanceService
from pipeline.market.crypto import CryptoService
from pipeline.planning.tax_loss_harvest import TaxLossHarvestEngine
from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine
from pipeline.planning.portfolio_summary import build_portfolio_summary

logger = logging.getLogger(__name__)
router = APIRouter(tags=["portfolio"])


# ---------------------------------------------------------------------------
# Market Quotes & Price Refresh
# ---------------------------------------------------------------------------
@router.post("/refresh-prices")
async def refresh_prices(session: AsyncSession = Depends(get_session)):
    """Refresh all holding prices from Yahoo Finance + CoinGecko."""
    from pipeline.db import MarketQuoteCache

    # Stock/ETF holdings
    result = await session.execute(
        select(InvestmentHolding).where(InvestmentHolding.is_active == True)
    )
    holdings = list(result.scalars().all())
    tickers = list({h.ticker for h in holdings})

    updated_stocks = 0
    if tickers:
        quotes = YahooFinanceService.get_bulk_quotes(tickers)
        now = datetime.now(timezone.utc)
        for h in holdings:
            q = quotes.get(h.ticker.upper())
            if q and q.get("price"):
                h.current_price = q["price"]
                h.current_value = q["price"] * h.shares
                if h.total_cost_basis is not None:
                    h.unrealized_gain_loss = h.current_value - h.total_cost_basis
                    h.unrealized_gain_loss_pct = (
                        (h.unrealized_gain_loss / h.total_cost_basis * 100)
                        if h.total_cost_basis > 0 else 0
                    )
                h.sector = q.get("sector")
                h.dividend_yield = q.get("dividend_yield")
                h.last_price_update = now
                updated_stocks += 1

                # Update cache
                await _upsert_quote_cache(session, q, now)

    # Crypto holdings
    cr = await session.execute(
        select(CryptoHolding).where(CryptoHolding.is_active == True)
    )
    cryptos = list(cr.scalars().all())
    updated_crypto = 0
    if cryptos:
        coin_ids = list({c.coin_id for c in cryptos})
        prices = await CryptoService.get_prices(coin_ids)
        now = datetime.now(timezone.utc)
        for c in cryptos:
            p = prices.get(c.coin_id)
            if p and "usd" in p:
                c.current_price = p["usd"]
                c.current_value = p["usd"] * c.quantity
                if c.total_cost_basis is not None:
                    c.unrealized_gain_loss = c.current_value - c.total_cost_basis
                c.price_change_24h_pct = p.get("usd_24h_change")
                c.last_price_update = now
                updated_crypto += 1

    await session.flush()
    return {"stocks_updated": updated_stocks, "crypto_updated": updated_crypto}


@router.get("/quote/{ticker}")
async def get_quote(ticker: str):
    """Get real-time quote for any ticker."""
    quote = YahooFinanceService.get_quote(ticker)
    if not quote:
        raise HTTPException(404, f"Quote not found for {ticker}")
    return quote


@router.get("/history/{ticker}")
async def get_history(ticker: str, period: str = "1y", interval: str = "1d"):
    """Get historical price data for charting."""
    data = YahooFinanceService.get_history(ticker, period=period, interval=interval)
    return {"ticker": ticker.upper(), "period": period, "data": data}


@router.get("/stats/{ticker}")
async def get_stats(ticker: str):
    """Get key fundamental statistics for a ticker."""
    stats = YahooFinanceService.get_key_stats(ticker)
    if not stats:
        raise HTTPException(404, f"Stats not found for {ticker}")
    return stats


# ---------------------------------------------------------------------------
# Portfolio Summary
# ---------------------------------------------------------------------------
@router.get("/summary")
async def portfolio_summary(session: AsyncSession = Depends(get_session)):
    from pipeline.db import ManualAsset

    result = await session.execute(
        select(InvestmentHolding).where(InvestmentHolding.is_active == True)
    )
    holdings = list(result.scalars().all())

    cr = await session.execute(
        select(CryptoHolding).where(CryptoHolding.is_active == True)
    )
    cryptos = list(cr.scalars().all())

    ma_result = await session.execute(
        select(ManualAsset).where(
            ManualAsset.is_active == True,
            ManualAsset.asset_type == "investment",
            ManualAsset.is_liability == False,
        )
    )
    manual_assets = list(ma_result.scalars().all())

    return build_portfolio_summary(holdings, cryptos, manual_assets)


# ---------------------------------------------------------------------------
# Tax-Loss Harvesting
# ---------------------------------------------------------------------------
@router.get("/tax-loss-harvest")
async def tax_loss_harvest_analysis(
    marginal_rate: float = Query(0.37, ge=0, le=1),
    filing_status: str = Query("mfj"),
    realized_short_gains: float = Query(0.0),
    realized_long_gains: float = Query(0.0),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(InvestmentHolding).where(InvestmentHolding.is_active == True)
    )
    holdings = list(result.scalars().all())

    holding_dicts = [
        {
            "id": h.id,
            "ticker": h.ticker,
            "name": h.name or h.ticker,
            "shares": h.shares,
            "total_cost_basis": h.total_cost_basis,
            "current_value": h.current_value,
            "current_price": h.current_price,
            "cost_basis_per_share": h.cost_basis_per_share,
            "purchase_date": h.purchase_date.isoformat() if h.purchase_date else None,
        }
        for h in holdings
    ]

    summary = TaxLossHarvestEngine.analyze(
        holdings=holding_dicts,
        realized_short_gains=realized_short_gains,
        realized_long_gains=realized_long_gains,
        marginal_tax_rate=marginal_rate,
        filing_status=filing_status,
    )
    return TaxLossHarvestEngine.to_dict(summary)


# ---------------------------------------------------------------------------
# Target Allocation
# ---------------------------------------------------------------------------
HENRY_PRESETS = {
    "aggressive": {"name": "Aggressive Growth", "allocation": {"stock": 70, "etf": 15, "crypto": 10, "bond": 5}},
    "balanced": {"name": "Balanced Growth", "allocation": {"stock": 50, "etf": 25, "bond": 15, "crypto": 5, "reit": 5}},
    "conservative": {"name": "Conservative", "allocation": {"stock": 30, "etf": 20, "bond": 35, "reit": 10, "crypto": 5}},
}


@router.get("/target-allocation")
async def get_target_allocation(session: AsyncSession = Depends(get_session)):
    """Get current target allocation or return default."""
    result = await session.execute(
        select(TargetAllocation).where(TargetAllocation.is_active == True).limit(1)
    )
    target = result.scalar_one_or_none()
    if target:
        return {
            "id": target.id,
            "name": target.name,
            "allocation": json.loads(target.allocation_json),
        }
    # Return default HENRY balanced preset
    return {"id": None, "name": "Balanced Growth", "allocation": {"stock": 50, "etf": 25, "bond": 15, "crypto": 5, "reit": 5}}


@router.put("/target-allocation")
async def set_target_allocation(
    body: TargetAllocationIn,
    session: AsyncSession = Depends(get_session),
):
    """Create or update target allocation."""
    name = body.name
    allocation = body.allocation

    # Validate: percentages should sum to ~100
    total = sum(allocation.values())
    if abs(total - 100) > 1:
        raise HTTPException(400, f"Allocation percentages must sum to 100 (got {total})")

    # Deactivate existing
    existing = await session.execute(
        select(TargetAllocation).where(TargetAllocation.is_active == True)
    )
    for ta in existing.scalars().all():
        ta.is_active = False

    new_ta = TargetAllocation(
        name=name,
        allocation_json=json.dumps(allocation),
        is_active=True,
    )
    session.add(new_ta)
    await session.flush()
    return {"id": new_ta.id, "name": new_ta.name, "allocation": allocation}


@router.get("/target-allocation/presets")
async def get_allocation_presets():
    """Return HENRY-optimized allocation presets."""
    return {"presets": HENRY_PRESETS}


# ---------------------------------------------------------------------------
# Portfolio Analytics
# ---------------------------------------------------------------------------
@router.get("/rebalance")
async def rebalance_recommendations(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(InvestmentHolding).where(InvestmentHolding.is_active == True)
    )
    holdings = list(result.scalars().all())
    ta_result = await session.execute(
        select(TargetAllocation).where(TargetAllocation.is_active == True).limit(1)
    )
    target = ta_result.scalar_one_or_none()
    target_dict = json.loads(target.allocation_json) if target and target.allocation_json else {"stock": 60, "etf": 25, "bond": 10, "crypto": 5}
    holding_dicts = [
        {"ticker": h.ticker, "asset_class": h.asset_class, "current_value": h.current_value or 0, "shares": h.shares}
        for h in holdings
    ]
    return PortfolioAnalyticsEngine.rebalancing_recommendations(holding_dicts, target_dict)


@router.get("/benchmark")
async def benchmark_comparison(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(PortfolioSnapshot).order_by(PortfolioSnapshot.snapshot_date.asc())
    )
    snapshots = [
        {"date": s.snapshot_date.isoformat() if s.snapshot_date else "", "total_value": s.total_value or 0}
        for s in result.scalars().all()
    ]
    return PortfolioAnalyticsEngine.benchmark_comparison(snapshots)


@router.get("/concentration")
async def concentration_risk(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(InvestmentHolding).where(InvestmentHolding.is_active == True)
    )
    holdings = [
        {"ticker": h.ticker, "current_value": h.current_value or 0, "sector": h.sector}
        for h in result.scalars().all()
    ]
    return PortfolioAnalyticsEngine.concentration_risk(holdings)


@router.get("/performance")
async def performance_metrics(session: AsyncSession = Depends(get_session)):
    snap_result = await session.execute(
        select(PortfolioSnapshot).order_by(PortfolioSnapshot.snapshot_date.asc())
    )
    snapshots = [
        {"date": s.snapshot_date.isoformat() if s.snapshot_date else "", "total_value": s.total_value or 0}
        for s in snap_result.scalars().all()
    ]
    hold_result = await session.execute(
        select(InvestmentHolding).where(InvestmentHolding.is_active == True)
    )
    holdings = [
        {"ticker": h.ticker, "current_value": h.current_value or 0, "total_cost_basis": h.total_cost_basis or 0}
        for h in hold_result.scalars().all()
    ]
    return PortfolioAnalyticsEngine.performance_metrics(snapshots, holdings)


@router.get("/net-worth-trend")
async def net_worth_trend(session: AsyncSession = Depends(get_session)):
    from pipeline.db.schema import NetWorthSnapshot
    result = await session.execute(
        select(NetWorthSnapshot).order_by(NetWorthSnapshot.snapshot_date.asc())
    )
    snapshots = [
        {"snapshot_date": s.snapshot_date.isoformat() if s.snapshot_date else "", "net_worth": s.net_worth or 0}
        for s in result.scalars().all()
    ]
    return PortfolioAnalyticsEngine.net_worth_trend(snapshots)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _upsert_quote_cache(session: AsyncSession, quote: dict, now: datetime):
    from pipeline.db import MarketQuoteCache
    ticker = quote["ticker"]
    result = await session.execute(
        select(MarketQuoteCache).where(MarketQuoteCache.ticker == ticker)
    )
    cached = result.scalar_one_or_none()
    if cached:
        for key in ("price", "previous_close", "change", "change_pct", "volume",
                     "market_cap", "pe_ratio", "forward_pe", "dividend_yield",
                     "fifty_two_week_high", "fifty_two_week_low", "beta",
                     "sector", "industry", "company_name", "earnings_per_share",
                     "book_value", "profit_margin", "revenue_growth"):
            if key in quote:
                setattr(cached, key, quote[key])
        cached.fetched_at = now
    else:
        cached = MarketQuoteCache(ticker=ticker, fetched_at=now)
        for key in ("price", "previous_close", "change", "change_pct", "volume",
                     "market_cap", "pe_ratio", "forward_pe", "dividend_yield",
                     "fifty_two_week_high", "fifty_two_week_low", "beta",
                     "sector", "industry", "company_name", "earnings_per_share",
                     "book_value", "profit_margin", "revenue_growth"):
            if key in quote:
                setattr(cached, key, quote[key])
        session.add(cached)
