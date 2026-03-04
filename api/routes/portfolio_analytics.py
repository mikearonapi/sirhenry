"""Portfolio analytics — allocations, rebalancing, benchmarks, performance, tax-loss harvesting."""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db import InvestmentHolding, CryptoHolding, PortfolioSnapshot, TargetAllocation
from pipeline.market.yahoo_finance import YahooFinanceService
from pipeline.market.crypto import CryptoService
from pipeline.planning.tax_loss_harvest import TaxLossHarvestEngine
from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine

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
                if h.total_cost_basis:
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
                if c.total_cost_basis:
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

    # Manual investment assets (401k, IRA, brokerage, etc.)
    ma_result = await session.execute(
        select(ManualAsset).where(
            ManualAsset.is_active == True,
            ManualAsset.asset_type == "investment",
            ManualAsset.is_liability == False,
        )
    )
    manual_assets = list(ma_result.scalars().all())

    stock_val = sum((h.current_value or 0) for h in holdings if h.asset_class == "stock")
    etf_val = sum((h.current_value or 0) for h in holdings if h.asset_class == "etf")
    other_holding_val = sum((h.current_value or 0) for h in holdings if h.asset_class not in ("stock", "etf"))
    crypto_val = sum((c.current_value or 0) for c in cryptos)
    manual_val = sum((a.current_value or 0) for a in manual_assets)

    total_val = stock_val + etf_val + other_holding_val + crypto_val + manual_val
    total_cost = (
        sum((h.total_cost_basis or 0) for h in holdings)
        + sum((c.total_cost_basis or 0) for c in cryptos)
        + sum((a.purchase_price or 0) for a in manual_assets)
    )
    has_cost_basis = total_cost > 0
    total_gl = total_val - total_cost if has_cost_basis else 0
    total_gl_pct = (total_gl / total_cost * 100) if has_cost_basis else 0

    # Weighted-average annual return from manual assets (fallback when no cost basis)
    weighted_return_sum = 0.0
    weighted_return_base = 0.0
    for a in manual_assets:
        val = a.current_value or 0
        ret = a.annual_return_pct
        if val > 0 and ret is not None:
            weighted_return_sum += val * ret
            weighted_return_base += val
    weighted_avg_return = (
        round(weighted_return_sum / weighted_return_base, 2)
        if weighted_return_base > 0 else None
    )

    # Sector allocation (from ticker holdings)
    sectors: dict[str, float] = {}
    for h in holdings:
        s = h.sector or "Unknown"
        sectors[s] = sectors.get(s, 0) + (h.current_value or 0)

    # Asset class allocation — combine holdings + manual assets
    classes: dict[str, float] = {}
    for h in holdings:
        classes[h.asset_class] = classes.get(h.asset_class, 0) + (h.current_value or 0)
    if crypto_val > 0:
        classes["crypto"] = crypto_val

    # Classify manual assets by account subtype
    SUBTYPE_TO_CLASS = {
        "401k": "retirement_401k", "401k_roth": "retirement_401k",
        "403b": "retirement_403b", "457b": "retirement_457b",
        "ira": "traditional_ira", "rollover_ira": "traditional_ira",
        "roth_ira": "roth_ira", "sep_ira": "sep_ira",
        "trust": "trust", "brokerage": "brokerage",
        "rsu": "equity_comp", "iso": "equity_comp", "nso": "equity_comp",
        "espp": "equity_comp",
        "529": "education_529", "hsa": "hsa",
    }
    for a in manual_assets:
        cls = SUBTYPE_TO_CLASS.get(a.account_subtype or "", "other")
        classes[cls] = classes.get(cls, 0) + (a.current_value or 0)

    # Top holdings — include manual investment accounts
    all_items = [
        {"ticker": h.ticker, "name": h.name, "value": h.current_value or 0, "gain_loss_pct": h.unrealized_gain_loss_pct or 0, "is_annual_return": False}
        for h in holdings
    ] + [
        {"ticker": c.symbol, "name": c.name, "value": c.current_value or 0, "gain_loss_pct": 0, "is_annual_return": False}
        for c in cryptos
    ] + [
        {
            "ticker": (a.account_subtype or "ACCT").upper()[:6],
            "name": a.name,
            "value": a.current_value or 0,
            "gain_loss_pct": a.annual_return_pct or 0,
            "is_annual_return": a.annual_return_pct is not None,
        }
        for a in manual_assets
    ]
    all_items.sort(key=lambda x: x["value"], reverse=True)

    return {
        "total_value": round(total_val, 2),
        "total_cost_basis": round(total_cost, 2),
        "total_gain_loss": round(total_gl, 2),
        "total_gain_loss_pct": round(total_gl_pct, 2),
        "has_cost_basis": has_cost_basis,
        "weighted_avg_return": weighted_avg_return,
        "stock_value": round(stock_val, 2),
        "etf_value": round(etf_val, 2),
        "crypto_value": round(crypto_val, 2),
        "other_value": round(other_holding_val, 2),
        "manual_investment_value": round(manual_val, 2),
        "holdings_count": len(holdings) + len(cryptos),
        "accounts_count": len(manual_assets),
        "top_holdings": all_items[:10],
        "sector_allocation": sectors,
        "asset_class_allocation": classes,
    }


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
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Create or update target allocation."""
    name = body.get("name", "My Target Allocation")
    allocation = body.get("allocation", {})

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
