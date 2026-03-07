"""
Portfolio summary aggregation logic.

Extracted from api/routes/portfolio_analytics.py to keep routes thin.
"""
from __future__ import annotations

from typing import Any


# Manual asset account subtype → asset class mapping
SUBTYPE_TO_CLASS: dict[str, str] = {
    "401k": "retirement_401k", "401k_roth": "retirement_401k",
    "403b": "retirement_403b", "457b": "retirement_457b",
    "ira": "traditional_ira", "rollover_ira": "traditional_ira",
    "roth_ira": "roth_ira", "sep_ira": "sep_ira",
    "trust": "trust", "brokerage": "brokerage",
    "rsu": "equity_comp", "iso": "equity_comp", "nso": "equity_comp",
    "espp": "equity_comp",
    "529": "education_529", "hsa": "hsa",
}


def build_portfolio_summary(
    holdings: list[Any],
    cryptos: list[Any],
    manual_assets: list[Any],
) -> dict:
    """Aggregate portfolio data into a summary dict.

    Accepts ORM objects (InvestmentHolding, CryptoHolding, ManualAsset).
    """
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
