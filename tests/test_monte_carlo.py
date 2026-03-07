"""Tests for pipeline/planning/monte_carlo.py — Monte Carlo simulation engine."""
import random

import pytest

from pipeline.planning.monte_carlo import run_monte_carlo_simulation


class TestMonteCarloBasic:
    """Core Monte Carlo simulation behaviour."""

    def test_returns_all_percentiles(self):
        result = run_monte_carlo_simulation({
            "initial_balance": 100000,
            "annual_contribution": 10000,
            "runs": 100,
        })
        for key in ("p10", "p25", "p50", "p75", "p90", "runs"):
            assert key in result

    def test_percentile_ordering(self):
        result = run_monte_carlo_simulation({
            "initial_balance": 500000,
            "annual_contribution": 20000,
            "runs": 500,
        })
        assert result["p10"] <= result["p25"]
        assert result["p25"] <= result["p50"]
        assert result["p50"] <= result["p75"]
        assert result["p75"] <= result["p90"]

    def test_run_count_matches(self):
        result = run_monte_carlo_simulation({
            "initial_balance": 100000,
            "annual_contribution": 0,
            "runs": 200,
        })
        assert result["runs"] == 200

    def test_deterministic_with_seed(self):
        params = {
            "initial_balance": 100000,
            "annual_contribution": 10000,
            "runs": 100,
            "years": 10,
        }
        random.seed(42)
        r1 = run_monte_carlo_simulation(params)
        random.seed(42)
        r2 = run_monte_carlo_simulation(params)
        assert r1["p50"] == r2["p50"]


class TestMonteCarloEdgeCases:
    """Edge cases and boundary conditions."""

    def test_zero_contribution(self):
        """Portfolio should still grow from returns alone."""
        result = run_monte_carlo_simulation({
            "initial_balance": 100000,
            "annual_contribution": 0,
            "runs": 500,
            "years": 10,
            "mean_return": 0.07,
            "std_dev": 0.01,  # Low volatility for predictable growth
        })
        # With 7% return and low volatility, median should grow
        assert result["p50"] > 100000

    def test_single_year(self):
        result = run_monte_carlo_simulation({
            "initial_balance": 100000,
            "annual_contribution": 10000,
            "runs": 100,
            "years": 1,
        })
        assert result["p50"] > 0

    def test_zero_initial_balance(self):
        """Starting from zero with contributions should still produce positive outcomes."""
        result = run_monte_carlo_simulation({
            "initial_balance": 0,
            "annual_contribution": 50000,
            "runs": 500,
            "years": 20,
            "mean_return": 0.07,
            "std_dev": 0.01,
        })
        assert result["p50"] > 0

    def test_high_volatility_wider_spread(self):
        """Higher std_dev should produce wider spread between percentiles."""
        params_base = {
            "initial_balance": 100000,
            "annual_contribution": 10000,
            "runs": 1000,
            "years": 20,
            "mean_return": 0.07,
        }
        random.seed(123)
        low_vol = run_monte_carlo_simulation({**params_base, "std_dev": 0.05})
        random.seed(123)
        high_vol = run_monte_carlo_simulation({**params_base, "std_dev": 0.30})

        low_spread = low_vol["p90"] - low_vol["p10"]
        high_spread = high_vol["p90"] - high_vol["p10"]
        assert high_spread > low_spread

    def test_custom_defaults(self):
        """Default values for optional params should work."""
        result = run_monte_carlo_simulation({
            "initial_balance": 100000,
            "annual_contribution": 10000,
            "runs": 50,
        })
        # Default: years=20, mean_return=0.07, std_dev=0.15
        assert result["runs"] == 50
        assert all(result[k] > 0 for k in ("p10", "p25", "p50", "p75", "p90"))
