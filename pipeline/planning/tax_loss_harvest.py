"""
Tax-loss harvesting engine.
Identifies holdings with unrealized losses that can be harvested to offset gains.
Tracks wash sale windows and estimates tax savings.
"""
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from pipeline.tax.constants import NIIT_RATE, LTCG_RATES

logger = logging.getLogger(__name__)

WASH_SALE_WINDOW_DAYS = 30


def _top_ltcg_rate(filing_status: str = "mfj") -> float:
    """Return the top LTCG rate for the given filing status."""
    brackets = LTCG_RATES.get(filing_status, LTCG_RATES.get("mfj", []))
    return brackets[-1][1] if brackets else 0.20


@dataclass
class HarvestCandidate:
    holding_id: int
    ticker: str
    name: str
    shares: float
    cost_basis: float
    current_value: float
    unrealized_loss: float
    loss_pct: float
    term: str  # short | long
    purchase_date: Optional[date]
    tax_rate: float
    estimated_tax_savings: float
    wash_sale_risk: bool
    wash_sale_window_end: Optional[date]


@dataclass
class HarvestSummary:
    total_unrealized_losses: float
    total_unrealized_gains: float
    net_unrealized: float
    harvestable_losses: float
    estimated_tax_savings: float
    capital_loss_carryover_available: float
    candidates: list[HarvestCandidate]
    # Current year realized gains that can be offset
    realized_short_term_gains: float = 0.0
    realized_long_term_gains: float = 0.0
    # The $3,000 annual deduction against ordinary income
    ordinary_income_deduction: float = 3000.0


class TaxLossHarvestEngine:
    """
    Analyzes portfolio holdings to identify tax-loss harvesting opportunities.
    """

    @staticmethod
    def analyze(
        holdings: list[dict],
        realized_short_gains: float = 0.0,
        realized_long_gains: float = 0.0,
        marginal_tax_rate: float = 0.37,
        filing_status: str = "mfj",
        recent_purchases: Optional[list[dict]] = None,
    ) -> HarvestSummary:
        """
        holdings: list of dicts with keys: id, ticker, name, shares, total_cost_basis,
                  current_value, purchase_date, current_price, cost_basis_per_share
        recent_purchases: list of {ticker, date} for wash sale detection
        """
        candidates = []
        total_losses = 0.0
        total_gains = 0.0
        harvestable = 0.0

        recent_tickers = {}
        if recent_purchases:
            for rp in recent_purchases:
                t = rp.get("ticker", "").upper()
                d = rp.get("date")
                if t and d:
                    if isinstance(d, str):
                        d = date.fromisoformat(d)
                    recent_tickers.setdefault(t, []).append(d)

        today = date.today()

        for h in holdings:
            cost = h.get("total_cost_basis") or 0
            value = h.get("current_value") or 0
            gain_loss = value - cost

            if gain_loss >= 0:
                total_gains += gain_loss
                continue

            total_losses += abs(gain_loss)
            loss_pct = (gain_loss / cost * 100) if cost > 0 else 0

            pdate = h.get("purchase_date")
            if isinstance(pdate, str):
                pdate = date.fromisoformat(pdate)

            if pdate:
                days_held = (today - pdate).days
                term = "long" if days_held > 365 else "short"
            else:
                term = "short"

            long_term_rate = _top_ltcg_rate(filing_status)
            tax_rate = long_term_rate if term == "long" else marginal_tax_rate
            estimated_savings = abs(gain_loss) * tax_rate

            # Wash sale check — backward-looking only.
            # NOTE: IRS wash sale rule applies to purchases 30 days BEFORE or
            # AFTER the sale. We only check backward (recent_purchases). The
            # forward window (buying back within 30 days after harvesting) must
            # be tracked separately once the sale is actually executed.
            ticker = h.get("ticker", "").upper()
            wash_risk = False
            wash_end = None
            if ticker in recent_tickers:
                for rd in recent_tickers[ticker]:
                    if abs((today - rd).days) <= WASH_SALE_WINDOW_DAYS:
                        wash_risk = True
                        wash_end = rd + timedelta(days=WASH_SALE_WINDOW_DAYS)
                        break

            candidate = HarvestCandidate(
                holding_id=h.get("id", 0),
                ticker=ticker,
                name=h.get("name", ticker),
                shares=h.get("shares", 0),
                cost_basis=cost,
                current_value=value,
                unrealized_loss=gain_loss,
                loss_pct=round(loss_pct, 2),
                term=term,
                purchase_date=pdate,
                tax_rate=tax_rate,
                estimated_tax_savings=round(estimated_savings, 2),
                wash_sale_risk=wash_risk,
                wash_sale_window_end=wash_end,
            )
            candidates.append(candidate)
            if not wash_risk:
                harvestable += abs(gain_loss)

        # Sort by estimated tax savings descending
        candidates.sort(key=lambda c: c.estimated_tax_savings, reverse=True)

        # Total savings estimate: offset gains first, then up to $3k ordinary income
        total_realized_gains = realized_short_gains + realized_long_gains
        gains_offset = min(harvestable, total_realized_gains)
        remaining_loss = harvestable - gains_offset
        ordinary_offset = min(remaining_loss, 3000)
        carryover = max(0, remaining_loss - ordinary_offset)

        long_term_rate = _top_ltcg_rate(filing_status)
        short_savings = min(harvestable, realized_short_gains) * marginal_tax_rate
        long_savings = min(max(0, harvestable - realized_short_gains), realized_long_gains) * long_term_rate
        ordinary_savings = ordinary_offset * marginal_tax_rate
        total_savings = short_savings + long_savings + ordinary_savings

        return HarvestSummary(
            total_unrealized_losses=round(total_losses, 2),
            total_unrealized_gains=round(total_gains, 2),
            net_unrealized=round(total_gains - total_losses, 2),
            harvestable_losses=round(harvestable, 2),
            estimated_tax_savings=round(total_savings, 2),
            capital_loss_carryover_available=round(carryover, 2),
            candidates=candidates,
            realized_short_term_gains=realized_short_gains,
            realized_long_term_gains=realized_long_gains,
        )

    @staticmethod
    def to_dict(summary: HarvestSummary) -> dict:
        """Convert summary to JSON-serializable dict."""
        return {
            "total_unrealized_losses": summary.total_unrealized_losses,
            "total_unrealized_gains": summary.total_unrealized_gains,
            "net_unrealized": summary.net_unrealized,
            "harvestable_losses": summary.harvestable_losses,
            "estimated_tax_savings": summary.estimated_tax_savings,
            "capital_loss_carryover": summary.capital_loss_carryover_available,
            "realized_short_term_gains": summary.realized_short_term_gains,
            "realized_long_term_gains": summary.realized_long_term_gains,
            "ordinary_income_deduction": summary.ordinary_income_deduction,
            "candidates": [
                {
                    "holding_id": c.holding_id,
                    "ticker": c.ticker,
                    "name": c.name,
                    "shares": c.shares,
                    "cost_basis": c.cost_basis,
                    "current_value": c.current_value,
                    "unrealized_loss": c.unrealized_loss,
                    "loss_pct": c.loss_pct,
                    "term": c.term,
                    "purchase_date": c.purchase_date.isoformat() if c.purchase_date else None,
                    "tax_rate": c.tax_rate,
                    "estimated_tax_savings": c.estimated_tax_savings,
                    "wash_sale_risk": c.wash_sale_risk,
                    "wash_sale_window_end": c.wash_sale_window_end.isoformat() if c.wash_sale_window_end else None,
                }
                for c in summary.candidates
            ],
        }
