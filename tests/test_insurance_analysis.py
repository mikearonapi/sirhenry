"""Tests for pipeline/planning/insurance_analysis.py — insurance gap analysis."""
from datetime import date, timedelta

import pytest

from pipeline.planning.insurance_analysis import (
    calculate_life_insurance_need,
    analyze_insurance_gaps,
)


# ---------------------------------------------------------------------------
# Mock ORM objects
# ---------------------------------------------------------------------------

class _Policy:
    def __init__(self, policy_type="life", coverage_amount=500000,
                 annual_premium=1200, is_active=True, provider="MetLife",
                 renewal_date=None, notes=None):
        self.id = 1
        self.policy_type = policy_type
        self.coverage_amount = coverage_amount
        self.annual_premium = annual_premium
        self.is_active = is_active
        self.provider = provider
        self.renewal_date = renewal_date
        self.notes = notes


class _BenefitPackage:
    def __init__(self, spouse="A", life_insurance_coverage=100000,
                 std_coverage_pct=60, ltd_coverage_pct=60):
        self.spouse = spouse
        self.life_insurance_coverage = life_insurance_coverage
        self.std_coverage_pct = std_coverage_pct
        self.ltd_coverage_pct = ltd_coverage_pct


# ---------------------------------------------------------------------------
# calculate_life_insurance_need (DIME method)
# ---------------------------------------------------------------------------

class TestLifeInsuranceNeed:
    def test_basic(self):
        # 200k * 10 + 50k debt + 1 child * 50k = 2.1M
        need = calculate_life_insurance_need(200000, 10, 50000, 1)
        assert need == 2_100_000

    def test_no_dependents_no_debt(self):
        need = calculate_life_insurance_need(150000)
        assert need == 1_500_000  # 150k * 10

    def test_zero_income(self):
        need = calculate_life_insurance_need(0, 10, 100000, 2)
        assert need == 200_000  # debt(0) + education(2*50k) + income(0)

    def test_multiple_dependents(self):
        need = calculate_life_insurance_need(100000, 10, 0, 3)
        assert need == 1_150_000  # 1M + 150k education

    def test_custom_years(self):
        need = calculate_life_insurance_need(100000, 5, 0, 0)
        assert need == 500_000


# ---------------------------------------------------------------------------
# analyze_insurance_gaps — life
# ---------------------------------------------------------------------------

class TestLifeGap:
    def test_adequate_coverage(self):
        # Combined need: A(200k*10 + 25k debt + 50k edu) + B(100k*10 + 25k debt + 50k edu)
        # = 2.275M + 1.075M = 3.35M
        result = analyze_insurance_gaps(
            spouse_a_income=200000,
            spouse_b_income=100000,
            total_debt=50000,
            dependents=1,
            net_worth=500000,
            policies=[_Policy("life", coverage_amount=4_000_000)],
            benefit_packages=[],
        )
        life_gap = next(g for g in result["gaps"] if g["type"] == "life")
        assert life_gap["gap"] == 0  # More than enough coverage

    def test_insufficient_coverage(self):
        result = analyze_insurance_gaps(
            spouse_a_income=250000,
            spouse_b_income=150000,
            total_debt=200000,
            dependents=2,
            net_worth=500000,
            policies=[_Policy("life", coverage_amount=500000)],
            benefit_packages=[],
        )
        life_gap = next(g for g in result["gaps"] if g["type"] == "life")
        assert life_gap["gap"] > 0

    def test_employer_life_counted(self):
        result = analyze_insurance_gaps(
            spouse_a_income=200000,
            spouse_b_income=0,
            total_debt=0,
            dependents=0,
            net_worth=100000,
            policies=[],
            benefit_packages=[_BenefitPackage("A", life_insurance_coverage=2_000_000)],
        )
        life_gap = next(g for g in result["gaps"] if g["type"] == "life")
        assert life_gap["employer_provided"] == 2_000_000

    def test_severity_high(self):
        result = analyze_insurance_gaps(
            spouse_a_income=300000,
            spouse_b_income=200000,
            total_debt=500000,
            dependents=3,
            net_worth=1_000_000,
            policies=[],
            benefit_packages=[],
        )
        life_gap = next(g for g in result["gaps"] if g["type"] == "life")
        assert life_gap["severity"] == "high"


# ---------------------------------------------------------------------------
# analyze_insurance_gaps — disability
# ---------------------------------------------------------------------------

class TestDisabilityGap:
    def test_no_disability_coverage(self):
        result = analyze_insurance_gaps(
            spouse_a_income=200000,
            spouse_b_income=100000,
            total_debt=0,
            dependents=0,
            net_worth=100000,
            policies=[],
            benefit_packages=[],
        )
        dis_gap = next(g for g in result["gaps"] if g["type"] == "disability")
        assert dis_gap["severity"] == "high"  # No coverage at all

    def test_employer_disability_counted(self):
        result = analyze_insurance_gaps(
            spouse_a_income=200000,
            spouse_b_income=0,
            total_debt=0,
            dependents=0,
            net_worth=100000,
            policies=[],
            benefit_packages=[_BenefitPackage("A", std_coverage_pct=60, ltd_coverage_pct=60)],
        )
        dis_gap = next(g for g in result["gaps"] if g["type"] == "disability")
        assert dis_gap["employer_provided"] > 0


# ---------------------------------------------------------------------------
# analyze_insurance_gaps — umbrella
# ---------------------------------------------------------------------------

class TestUmbrellaGap:
    def test_low_net_worth_no_need(self):
        result = analyze_insurance_gaps(
            spouse_a_income=100000,
            spouse_b_income=0,
            total_debt=0,
            dependents=0,
            net_worth=200000,  # Below $300k threshold
            policies=[],
            benefit_packages=[],
        )
        umbrella = next(g for g in result["gaps"] if g["type"] == "umbrella")
        assert umbrella["severity"] == "low"
        assert umbrella["gap"] == 0

    def test_high_net_worth_no_umbrella(self):
        result = analyze_insurance_gaps(
            spouse_a_income=200000,
            spouse_b_income=100000,
            total_debt=0,
            dependents=0,
            net_worth=1_000_000,
            policies=[],
            benefit_packages=[],
        )
        umbrella = next(g for g in result["gaps"] if g["type"] == "umbrella")
        assert umbrella["severity"] == "medium"
        assert umbrella["gap"] == 1_000_000

    def test_has_umbrella(self):
        result = analyze_insurance_gaps(
            spouse_a_income=200000,
            spouse_b_income=100000,
            total_debt=0,
            dependents=0,
            net_worth=1_000_000,
            policies=[_Policy("umbrella", coverage_amount=2_000_000)],
            benefit_packages=[],
        )
        umbrella = next(g for g in result["gaps"] if g["type"] == "umbrella")
        assert umbrella["severity"] == "low"


# ---------------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------------

class TestAnalysisSummary:
    def test_premium_totals(self):
        result = analyze_insurance_gaps(
            spouse_a_income=200000,
            spouse_b_income=0,
            total_debt=0,
            dependents=0,
            net_worth=100000,
            policies=[
                _Policy("life", annual_premium=1200),
                _Policy("disability", annual_premium=600),
            ],
            benefit_packages=[],
        )
        assert result["total_annual_premium"] == 1800
        assert result["total_monthly_premium"] == 150

    def test_recommendations_from_gaps(self):
        result = analyze_insurance_gaps(
            spouse_a_income=300000,
            spouse_b_income=200000,
            total_debt=0,
            dependents=0,
            net_worth=1_000_000,
            policies=[],
            benefit_packages=[],
        )
        assert len(result["recommendations"]) > 0


# ---------------------------------------------------------------------------
# Renewing soon
# ---------------------------------------------------------------------------

class TestRenewingSoon:
    def test_policy_renewing_within_60_days(self):
        renewal = date.today() + timedelta(days=30)
        result = analyze_insurance_gaps(
            spouse_a_income=100000,
            spouse_b_income=0,
            total_debt=0,
            dependents=0,
            net_worth=100000,
            policies=[_Policy("life", renewal_date=renewal)],
            benefit_packages=[],
        )
        assert len(result["renewing_soon"]) == 1

    def test_policy_renewal_too_far(self):
        renewal = date.today() + timedelta(days=90)
        result = analyze_insurance_gaps(
            spouse_a_income=100000,
            spouse_b_income=0,
            total_debt=0,
            dependents=0,
            net_worth=100000,
            policies=[_Policy("life", renewal_date=renewal)],
            benefit_packages=[],
        )
        assert len(result["renewing_soon"]) == 0
