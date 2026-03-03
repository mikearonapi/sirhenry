"""
Portfolio analytics engine: rebalancing, benchmarks, concentration risk,
asset location, performance metrics, net worth trends.
"""
import json
import logging
import math
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)


class PortfolioAnalyticsEngine:

    @staticmethod
    def rebalancing_recommendations(
        holdings: list[dict],
        target_allocation: dict[str, float],
    ) -> list[dict]:
        total_value = sum(h.get("current_value", 0) or 0 for h in holdings)
        if total_value <= 0:
            return []

        current_by_class: dict[str, float] = {}
        for h in holdings:
            ac = h.get("asset_class", "other")
            current_by_class[ac] = current_by_class.get(ac, 0) + (h.get("current_value", 0) or 0)

        recs = []
        for asset_class, target_pct in target_allocation.items():
            current_val = current_by_class.get(asset_class, 0)
            current_pct = (current_val / total_value) * 100 if total_value > 0 else 0
            target_val = total_value * (target_pct / 100)
            diff = target_val - current_val

            if abs(diff) < total_value * 0.01:
                action = "hold"
            elif diff > 0:
                action = "buy"
            else:
                action = "sell"

            recs.append({
                "asset_class": asset_class,
                "current_pct": round(current_pct, 2),
                "target_pct": target_pct,
                "action": action,
                "amount": round(abs(diff), 2),
            })

        return sorted(recs, key=lambda r: abs(r["amount"]), reverse=True)

    @staticmethod
    def benchmark_comparison(
        portfolio_snapshots: list[dict],
        benchmark_returns: float = 0.10,
        period_months: int = 12,
    ) -> dict:
        if len(portfolio_snapshots) < 2:
            return {
                "portfolio_return": 0,
                "benchmark_return": benchmark_returns,
                "alpha": -benchmark_returns,
                "benchmark_ticker": "SPY",
                "period_months": period_months,
            }

        start_val = portfolio_snapshots[0].get("total_portfolio_value", 0)
        end_val = portfolio_snapshots[-1].get("total_portfolio_value", 0)
        portfolio_return = (end_val - start_val) / start_val if start_val > 0 else 0

        alpha = portfolio_return - benchmark_returns

        return {
            "portfolio_return": round(portfolio_return, 4),
            "benchmark_return": round(benchmark_returns, 4),
            "alpha": round(alpha, 4),
            "benchmark_ticker": "SPY",
            "period_months": period_months,
        }

    @staticmethod
    def concentration_risk(holdings: list[dict]) -> dict:
        total = sum(h.get("current_value", 0) or 0 for h in holdings)
        if total <= 0:
            return {"top_holding_pct": 0, "top_3_pct": 0, "single_stock_risk": "low", "by_sector": {}}

        sorted_h = sorted(holdings, key=lambda h: h.get("current_value", 0) or 0, reverse=True)
        top_pct = ((sorted_h[0].get("current_value", 0) or 0) / total * 100) if sorted_h else 0
        top3_val = sum((h.get("current_value", 0) or 0) for h in sorted_h[:3])
        top3_pct = (top3_val / total * 100)

        by_sector: dict[str, float] = {}
        for h in holdings:
            sector = h.get("sector", "Unknown") or "Unknown"
            by_sector[sector] = by_sector.get(sector, 0) + (h.get("current_value", 0) or 0)
        by_sector = {k: round(v / total * 100, 2) for k, v in by_sector.items()}

        if top_pct > 40:
            risk = "critical"
        elif top_pct > 25:
            risk = "high"
        elif top_pct > 15:
            risk = "elevated"
        elif top_pct > 10:
            risk = "moderate"
        else:
            risk = "low"

        return {
            "top_holding_pct": round(top_pct, 2),
            "top_3_pct": round(top3_pct, 2),
            "single_stock_risk": risk,
            "top_holding": sorted_h[0].get("ticker", "") if sorted_h else "",
            "by_sector": by_sector,
        }

    @staticmethod
    def performance_metrics(
        snapshots: list[dict],
    ) -> dict:
        if len(snapshots) < 2:
            return {"time_weighted_return": 0, "sharpe_ratio": None, "max_drawdown": 0, "volatility": None, "period_months": 0}

        values = [s.get("total_portfolio_value", 0) for s in snapshots]
        returns = [(values[i] - values[i - 1]) / values[i - 1] if values[i - 1] > 0 else 0 for i in range(1, len(values))]

        total_return = (values[-1] - values[0]) / values[0] if values[0] > 0 else 0
        avg_return = sum(returns) / len(returns) if returns else 0
        n = len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / (n - 1) if n > 1 else 0
        volatility = math.sqrt(variance) if variance > 0 else 0
        sharpe = (avg_return - 0.004) / volatility if volatility > 0 else None  # ~5% risk-free annualized

        peak = values[0]
        max_dd = 0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        return {
            "time_weighted_return": round(total_return, 4),
            "sharpe_ratio": round(sharpe, 2) if sharpe is not None else None,
            "max_drawdown": round(max_dd, 4),
            "volatility": round(volatility, 4) if volatility > 0 else None,
            "period_months": len(snapshots),
        }

    @staticmethod
    def net_worth_trend(snapshots: list[dict]) -> dict:
        if not snapshots:
            return {"monthly_series": [], "growth_rate": 0, "current_net_worth": 0}

        series = [{"date": s.get("snapshot_date", ""), "net_worth": s.get("net_worth", 0)} for s in snapshots]
        current = series[-1]["net_worth"] if series else 0
        first = series[0]["net_worth"] if series else 0
        growth = (current - first) / first if first > 0 else 0

        return {
            "monthly_series": series,
            "growth_rate": round(growth, 4),
            "current_net_worth": round(current, 2),
        }
