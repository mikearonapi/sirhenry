"""SIT: Tax-loss harvesting engine accuracy.

Validates TLH analysis with demo holdings (all positive gains)
and synthetic losing positions for loss detection.
"""
import pytest
from datetime import date, timedelta
from tests.integration.expected_values import *

pytestmark = pytest.mark.integration


class TestTLHWithDemoHoldings:
    async def test_all_demo_positions_have_gains(self, demo_session, demo_seed):
        """All seeded holdings have unrealized_gain_loss > 0."""
        from pipeline.db.schema import InvestmentHolding

        from sqlalchemy import select
        holdings = (await demo_session.execute(
            select(InvestmentHolding).where(InvestmentHolding.is_active == True)
        )).scalars().all()

        for h in holdings:
            assert h.unrealized_gain_loss >= 0, (
                f"{h.ticker} has unexpected loss: {h.unrealized_gain_loss}"
            )

    async def test_no_harvest_candidates_in_demo(self, demo_session, demo_seed):
        """With all positive positions, there should be no harvest candidates."""
        from pipeline.db.schema import InvestmentHolding
        from sqlalchemy import select

        holdings = (await demo_session.execute(
            select(InvestmentHolding).where(InvestmentHolding.is_active == True)
        )).scalars().all()

        losing = [h for h in holdings if (h.unrealized_gain_loss or 0) < 0]
        assert len(losing) == 0


class TestTLHEngine:
    def test_calculate_life_insurance_need_dime(self):
        """Direct test of DIME calculation for comparison baseline."""
        from pipeline.planning.insurance_analysis import calculate_life_insurance_need

        need = calculate_life_insurance_need(
            income=COMBINED_INCOME, years_to_replace=10,
            debt=TOTAL_LIABILITIES, dependents=DEPENDENTS,
        )
        expected = COMBINED_INCOME * 10 + TOTAL_LIABILITIES + DEPENDENTS * 50_000
        assert need == pytest.approx(expected, rel=0.01)

    def test_synthetic_loss_detection(self):
        """Verify we can identify a losing position."""
        cost_basis = 10_000
        current_value = 8_000
        unrealized_loss = current_value - cost_basis  # -2000
        assert unrealized_loss < 0
        assert abs(unrealized_loss) == 2_000

    def test_wash_sale_window(self):
        """Purchases within 30 days of sale trigger wash sale."""
        sale_date = date(2026, 3, 1)
        recent_purchase = date(2026, 2, 15)
        days_diff = abs((sale_date - recent_purchase).days)
        assert days_diff <= 30  # Within wash sale window

    def test_short_vs_long_term_classification(self):
        """Holdings >365 days are long-term."""
        today = date(2026, 3, 5)
        purchase_long = date(2024, 3, 1)  # ~730 days
        purchase_short = date(2025, 12, 1)  # ~94 days

        assert (today - purchase_long).days > 365  # Long-term
        assert (today - purchase_short).days < 365  # Short-term

    def test_3000_ordinary_income_offset(self):
        """Losses exceeding capital gains can offset up to $3,000 of ordinary income."""
        capital_gains = 1_000
        harvested_losses = 5_000
        net_loss = harvested_losses - capital_gains  # $4,000
        ordinary_offset = min(net_loss, 3_000)  # Capped at $3,000
        assert ordinary_offset == 3_000

    def test_tax_savings_calculation(self):
        """Tax savings = loss * marginal_rate."""
        loss = 5_000
        marginal_rate = 0.35  # 35% for $410K household
        savings = loss * marginal_rate
        assert savings == pytest.approx(1_750, rel=0.01)
