"""Tests for the equity compensation engine."""
import json
import pytest
from datetime import date, timedelta

from pipeline.planning.equity_comp import (
    EquityCompEngine,
    VestingProjection,
    WithholdingGapResult,
    AMTCrossoverResult,
    SellStrategyResult,
    DepartureAnalysis,
    ESPPAnalysis,
    ConcentrationRisk,
)
from pipeline.tax.constants import SUPPLEMENTAL_WITHHOLDING_RATE


class TestVestingSchedule:
    """Test RSU/ISO vesting schedule projections."""

    def test_basic_rsu_schedule(self):
        schedule = json.dumps({
            "cliff_months": 12,
            "frequency": "quarterly",
            "total_months": 48,
        })
        projections = EquityCompEngine.project_vesting_schedule(
            grant_type="rsu",
            grant_date="2024-01-01",
            total_shares=1000,
            vesting_schedule_json=schedule,
            current_fmv=150.0,
        )
        assert len(projections) > 0
        assert all(isinstance(p, VestingProjection) for p in projections)

    def test_cliff_vesting_allocates_correct_shares(self):
        schedule = json.dumps({
            "cliff_months": 12,
            "frequency": "quarterly",
            "total_months": 48,
        })
        projections = EquityCompEngine.project_vesting_schedule(
            grant_type="rsu",
            grant_date="2024-01-01",
            total_shares=1000,
            vesting_schedule_json=schedule,
            current_fmv=100.0,
        )
        # Cliff should vest 25% of shares (12/48)
        cliff_shares = projections[0].shares
        assert cliff_shares == pytest.approx(250.0, abs=1)

    def test_total_shares_sum_to_grant(self):
        schedule = json.dumps({
            "cliff_months": 12,
            "frequency": "quarterly",
            "total_months": 48,
        })
        projections = EquityCompEngine.project_vesting_schedule(
            grant_type="rsu",
            grant_date="2024-01-01",
            total_shares=1200,
            vesting_schedule_json=schedule,
            current_fmv=100.0,
        )
        total = sum(p.shares for p in projections)
        assert total == pytest.approx(1200, abs=1)

    def test_rsu_gross_value_uses_fmv(self):
        schedule = json.dumps({
            "cliff_months": 12,
            "frequency": "annually",
            "total_months": 48,
        })
        projections = EquityCompEngine.project_vesting_schedule(
            grant_type="rsu",
            grant_date="2024-01-01",
            total_shares=400,
            vesting_schedule_json=schedule,
            current_fmv=200.0,
        )
        # Each vest: shares * FMV
        for p in projections:
            assert p.gross_value == pytest.approx(p.shares * 200.0, abs=1)

    def test_iso_spread_uses_fmv_minus_strike(self):
        schedule = json.dumps({
            "cliff_months": 12,
            "frequency": "quarterly",
            "total_months": 48,
        })
        projections = EquityCompEngine.project_vesting_schedule(
            grant_type="iso",
            grant_date="2024-01-01",
            total_shares=1000,
            vesting_schedule_json=schedule,
            current_fmv=150.0,
            strike_price=50.0,
        )
        for p in projections:
            expected_gross = p.shares * (150.0 - 50.0)
            assert p.gross_value == pytest.approx(expected_gross, abs=1)

    def test_federal_withholding_at_supplemental_rate(self):
        schedule = json.dumps({
            "cliff_months": 12,
            "frequency": "quarterly",
            "total_months": 48,
        })
        projections = EquityCompEngine.project_vesting_schedule(
            grant_type="rsu",
            grant_date="2024-01-01",
            total_shares=1000,
            vesting_schedule_json=schedule,
            current_fmv=100.0,
        )
        for p in projections:
            expected_wh = p.gross_value * SUPPLEMENTAL_WITHHOLDING_RATE
            assert p.federal_withholding == pytest.approx(expected_wh, abs=0.01)

    def test_existing_events_excluded(self):
        schedule = json.dumps({
            "cliff_months": 12,
            "frequency": "quarterly",
            "total_months": 48,
        })
        # Get the full schedule first
        full = EquityCompEngine.project_vesting_schedule(
            grant_type="rsu",
            grant_date="2024-01-01",
            total_shares=1000,
            vesting_schedule_json=schedule,
            current_fmv=100.0,
        )
        # Mark the first event as already existing
        existing = [{"vest_date": full[0].vest_date}]
        filtered = EquityCompEngine.project_vesting_schedule(
            grant_type="rsu",
            grant_date="2024-01-01",
            total_shares=1000,
            vesting_schedule_json=schedule,
            current_fmv=100.0,
            existing_events=existing,
        )
        assert len(filtered) == len(full) - 1

    def test_monthly_frequency(self):
        schedule = json.dumps({
            "cliff_months": 12,
            "frequency": "monthly",
            "total_months": 48,
        })
        projections = EquityCompEngine.project_vesting_schedule(
            grant_type="rsu",
            grant_date="2024-01-01",
            total_shares=480,
            vesting_schedule_json=schedule,
            current_fmv=100.0,
        )
        # After 12-month cliff, 36 monthly vests + 1 cliff = 37
        assert len(projections) == 37


class TestWithholdingGap:
    """Test withholding gap calculations for RSU vest income."""

    def test_gap_exists_for_high_earner(self):
        result = EquityCompEngine.calculate_withholding_gap(
            vest_income=100_000,
            other_income=250_000,
            filing_status="mfj",
            state="CA",
        )
        assert isinstance(result, WithholdingGapResult)
        # At $350k total, marginal rate is 24%, supplemental is 22%, plus state tax
        assert result.withholding_gap > 0

    def test_quarterly_payments_generated(self):
        result = EquityCompEngine.calculate_withholding_gap(
            vest_income=200_000,
            other_income=300_000,
            filing_status="mfj",
            state="CA",
        )
        if result.withholding_gap > 0:
            assert len(result.quarterly_payments) == 4
            assert all("quarter" in q for q in result.quarterly_payments)
            assert all("amount" in q for q in result.quarterly_payments)

    def test_no_state_tax_state(self):
        result = EquityCompEngine.calculate_withholding_gap(
            vest_income=100_000,
            other_income=200_000,
            filing_status="mfj",
            state="TX",
        )
        assert result.state_rate == 0.0
        assert result.state_tax == 0.0

    def test_california_state_rate(self):
        result = EquityCompEngine.calculate_withholding_gap(
            vest_income=100_000,
            other_income=200_000,
            filing_status="mfj",
            state="CA",
        )
        assert result.state_rate == 0.133

    def test_withholding_supplemental_rate(self):
        result = EquityCompEngine.calculate_withholding_gap(
            vest_income=100_000,
            other_income=200_000,
        )
        assert result.total_withholding_at_supplemental == pytest.approx(
            100_000 * SUPPLEMENTAL_WITHHOLDING_RATE, abs=0.01
        )


class TestAMTCrossover:
    """Test ISO AMT impact calculations."""

    def test_basic_amt_crossover(self):
        result = EquityCompEngine.calculate_amt_crossover(
            iso_shares_available=1000,
            strike_price=10.0,
            current_fmv=50.0,
            other_income=200_000,
            filing_status="mfj",
        )
        assert isinstance(result, AMTCrossoverResult)
        assert result.safe_exercise_shares >= 0
        assert result.iso_bargain_element == 40.0  # 50 - 10

    def test_zero_bargain_element(self):
        # Strike == FMV means no bargain element
        result = EquityCompEngine.calculate_amt_crossover(
            iso_shares_available=1000,
            strike_price=50.0,
            current_fmv=50.0,
            other_income=200_000,
        )
        assert result.iso_bargain_element == 0.0
        assert result.safe_exercise_shares == 1000

    def test_all_shares_safe_at_low_income(self):
        result = EquityCompEngine.calculate_amt_crossover(
            iso_shares_available=100,
            strike_price=10.0,
            current_fmv=20.0,
            other_income=50_000,
        )
        # Small bargain element with low income: all shares should be safe
        assert result.safe_exercise_shares == 100
        assert "all shares" in result.recommendation.lower()

    def test_recommendation_text_populated(self):
        result = EquityCompEngine.calculate_amt_crossover(
            iso_shares_available=500,
            strike_price=10.0,
            current_fmv=100.0,
            other_income=300_000,
        )
        assert len(result.recommendation) > 0


class TestSellStrategy:
    """Test hold vs sell analysis."""

    def test_basic_sell_strategy(self):
        result = EquityCompEngine.model_sell_strategy(
            shares=100,
            cost_basis_per_share=50.0,
            current_price=150.0,
            other_income=200_000,
            filing_status="mfj",
            holding_period_months=0,
        )
        assert isinstance(result, SellStrategyResult)
        assert result.immediate_sell["gross_proceeds"] == 15_000.0
        assert result.immediate_sell["gain"] == 10_000.0

    def test_short_term_taxed_at_marginal(self):
        result = EquityCompEngine.model_sell_strategy(
            shares=100,
            cost_basis_per_share=50.0,
            current_price=150.0,
            other_income=200_000,
            holding_period_months=6,  # short term
        )
        # Short-term gain taxed at marginal rate
        assert result.immediate_sell["tax_rate"] > 0.15

    def test_long_term_lower_rate(self):
        result = EquityCompEngine.model_sell_strategy(
            shares=100,
            cost_basis_per_share=50.0,
            current_price=150.0,
            other_income=200_000,
            holding_period_months=13,  # long term
        )
        # Long-term rate should be at or below 20%
        assert result.immediate_sell["tax_rate"] <= 0.20

    def test_staged_sell_splits_shares(self):
        result = EquityCompEngine.model_sell_strategy(
            shares=100,
            cost_basis_per_share=50.0,
            current_price=150.0,
            other_income=200_000,
        )
        assert result.staged_sell["sell_now_shares"] == 50.0
        assert result.staged_sell["sell_later_shares"] == 50.0

    def test_hold_one_year_assumes_appreciation(self):
        result = EquityCompEngine.model_sell_strategy(
            shares=100,
            cost_basis_per_share=50.0,
            current_price=100.0,
            other_income=200_000,
        )
        # Hold scenario assumes 8% appreciation
        assert result.hold_one_year["projected_price"] == pytest.approx(108.0, abs=0.01)

    def test_no_gain_scenario(self):
        result = EquityCompEngine.model_sell_strategy(
            shares=100,
            cost_basis_per_share=100.0,
            current_price=100.0,
            other_income=200_000,
        )
        assert result.immediate_sell["gain"] == 0.0
        assert result.immediate_sell["tax"] == 0.0

    def test_recommendation_populated(self):
        result = EquityCompEngine.model_sell_strategy(
            shares=100,
            cost_basis_per_share=50.0,
            current_price=150.0,
            other_income=200_000,
        )
        assert len(result.recommendation) > 0


class TestConcentrationRisk:
    """Test concentration risk scoring."""

    def test_low_concentration(self):
        result = EquityCompEngine.concentration_risk(
            employer_stock_value=50_000,
            total_net_worth=1_000_000,
        )
        assert result.concentration_pct == 5.0
        assert result.risk_level == "low"

    def test_moderate_concentration(self):
        result = EquityCompEngine.concentration_risk(
            employer_stock_value=150_000,
            total_net_worth=1_000_000,
        )
        assert result.concentration_pct == 15.0
        assert result.risk_level == "moderate"

    def test_elevated_concentration(self):
        result = EquityCompEngine.concentration_risk(
            employer_stock_value=250_000,
            total_net_worth=1_000_000,
        )
        assert result.concentration_pct == 25.0
        assert result.risk_level == "elevated"

    def test_high_concentration(self):
        result = EquityCompEngine.concentration_risk(
            employer_stock_value=400_000,
            total_net_worth=1_000_000,
        )
        assert result.concentration_pct == 40.0
        assert result.risk_level == "high"

    def test_critical_concentration(self):
        result = EquityCompEngine.concentration_risk(
            employer_stock_value=600_000,
            total_net_worth=1_000_000,
        )
        assert result.concentration_pct == 60.0
        assert result.risk_level == "critical"

    def test_zero_net_worth(self):
        result = EquityCompEngine.concentration_risk(
            employer_stock_value=50_000,
            total_net_worth=0,
        )
        assert result.risk_level == "critical"
        assert result.concentration_pct == 100.0

    def test_negative_net_worth(self):
        result = EquityCompEngine.concentration_risk(
            employer_stock_value=50_000,
            total_net_worth=-100_000,
        )
        assert result.risk_level == "critical"


class TestDepartureAnalysis:
    """Test what-if-I-leave analysis."""

    def test_rsu_departure_forfeits_unvested(self):
        grants = [{
            "grant_type": "rsu",
            "current_fmv": 100.0,
            "strike_price": 0,
            "vested_shares": 500,
            "unvested_shares": 500,
            "employer_name": "TechCorp",
        }]
        result = EquityCompEngine.what_if_i_leave(
            grants=grants,
            leave_date="2025-06-01",
        )
        assert isinstance(result, DepartureAnalysis)
        assert result.total_unvested_value == 50_000.0
        assert result.forfeited_value == 50_000.0

    def test_nso_departure_exercise_cost(self):
        grants = [{
            "grant_type": "nso",
            "current_fmv": 100.0,
            "strike_price": 20.0,
            "vested_shares": 200,
            "unvested_shares": 300,
            "employer_name": "TechCorp",
        }]
        result = EquityCompEngine.what_if_i_leave(
            grants=grants,
            leave_date="2025-06-01",
        )
        assert result.exercise_cost == 200 * 20.0  # 4000
        assert result.forfeited_value == 300 * 100.0  # 30000
        assert result.tax_on_exercise > 0

    def test_empty_grants(self):
        result = EquityCompEngine.what_if_i_leave(
            grants=[],
            leave_date="2025-06-01",
        )
        assert result.total_unvested_value == 0.0
        assert result.exercise_cost == 0.0
        assert len(result.by_grant) == 0

    def test_multiple_grants(self):
        grants = [
            {
                "grant_type": "rsu",
                "current_fmv": 100.0,
                "vested_shares": 100,
                "unvested_shares": 200,
            },
            {
                "grant_type": "nso",
                "current_fmv": 80.0,
                "strike_price": 30.0,
                "vested_shares": 50,
                "unvested_shares": 150,
            },
        ]
        result = EquityCompEngine.what_if_i_leave(
            grants=grants,
            leave_date="2025-06-01",
        )
        assert len(result.by_grant) == 2
        assert result.total_unvested_value == 200 * 100.0 + 150 * 80.0


class TestQuarterlyEstimatedPayments:
    """Test quarterly estimated payment splitting."""

    def test_four_quarters(self):
        payments = EquityCompEngine.quarterly_estimated_payments(10_000, current_quarter=1)
        assert len(payments) == 4
        assert all(p["amount"] > 0 for p in payments)

    def test_mid_year_start(self):
        payments = EquityCompEngine.quarterly_estimated_payments(10_000, current_quarter=3)
        assert len(payments) == 2
        assert payments[0]["quarter"] == 3
        assert payments[1]["quarter"] == 4

    def test_zero_gap_returns_empty(self):
        payments = EquityCompEngine.quarterly_estimated_payments(0, current_quarter=1)
        assert payments == []

    def test_negative_gap_returns_empty(self):
        payments = EquityCompEngine.quarterly_estimated_payments(-500, current_quarter=1)
        assert payments == []

    def test_cumulative_totals(self):
        payments = EquityCompEngine.quarterly_estimated_payments(8_000, current_quarter=1)
        assert payments[-1]["cumulative"] >= 8_000
