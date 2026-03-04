"""
Retirement calculator engine for HENRYs.
Computes: target nest egg, projected savings, monthly needed, FIRE numbers,
years money will last, and confidence metrics.
Uses deterministic projections with optional Monte Carlo simulation.
"""
import logging
import random
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DebtPayoff:
    """A debt that will be paid off, reducing retirement expenses."""
    name: str = ""
    monthly_payment: float = 0.0
    payoff_age: int = 0


@dataclass
class RetirementInputs:
    current_age: int
    retirement_age: int = 65
    life_expectancy: int = 90
    current_annual_income: float = 0.0
    expected_income_growth_pct: float = 3.0
    expected_social_security_monthly: float = 0.0
    social_security_start_age: int = 67
    pension_monthly: float = 0.0
    other_retirement_income_monthly: float = 0.0
    current_retirement_savings: float = 0.0
    current_other_investments: float = 0.0
    monthly_retirement_contribution: float = 0.0
    employer_match_pct: float = 0.0
    employer_match_limit_pct: float = 6.0
    desired_annual_retirement_income: Optional[float] = None
    income_replacement_pct: float = 80.0
    healthcare_annual_estimate: float = 12000.0
    additional_annual_expenses: float = 0.0
    inflation_rate_pct: float = 3.0
    pre_retirement_return_pct: float = 7.0
    post_retirement_return_pct: float = 5.0
    tax_rate_in_retirement_pct: float = 22.0
    # Budget-based expense estimation (overrides income_replacement_pct when set)
    current_annual_expenses: Optional[float] = None
    # Debts that pay off before/during retirement, reducing expenses
    debt_payoffs: list = field(default_factory=list)


@dataclass
class RetirementResults:
    years_to_retirement: int = 0
    years_in_retirement: int = 0
    # Income needs
    annual_income_needed_today: float = 0.0
    annual_income_needed_at_retirement: float = 0.0
    monthly_income_needed_at_retirement: float = 0.0
    # Nest egg targets
    target_nest_egg: float = 0.0
    fire_number: float = 0.0
    coast_fire_number: float = 0.0
    lean_fire_number: float = 0.0
    # Projections
    projected_nest_egg: float = 0.0
    projected_monthly_income: float = 0.0
    # Gap analysis
    savings_gap: float = 0.0
    monthly_savings_needed: float = 0.0
    retirement_readiness_pct: float = 0.0
    years_money_will_last: float = 0.0
    on_track: bool = False
    # Contribution analysis
    current_savings_rate_pct: float = 0.0
    recommended_savings_rate_pct: float = 0.0
    total_monthly_contribution: float = 0.0
    employer_match_monthly: float = 0.0
    # Year-by-year projection for charting
    yearly_projection: list = field(default_factory=list)
    # Social security impact
    social_security_annual: float = 0.0
    pension_annual: float = 0.0
    other_income_annual: float = 0.0
    total_guaranteed_income_annual: float = 0.0
    portfolio_income_needed_annual: float = 0.0
    # Debt payoff impact
    debt_payoff_savings_annual: float = 0.0
    # Earliest possible retirement age
    earliest_retirement_age: int = 0


class RetirementCalculator:
    """
    Deterministic retirement projection engine.
    Calculates how much you need, when you'll get there, and what to adjust.
    """

    @staticmethod
    def _parse_debt_payoffs(raw: list) -> list[DebtPayoff]:
        result = []
        for item in raw:
            if isinstance(item, DebtPayoff):
                result.append(item)
            elif isinstance(item, dict):
                result.append(DebtPayoff(
                    name=item.get("name", ""),
                    monthly_payment=float(item.get("monthly_payment", 0)),
                    payoff_age=int(item.get("payoff_age", 0)),
                ))
        return result

    @staticmethod
    def _compute_employer_match(monthly_contribution: float, annual_income: float,
                                match_pct: float, match_limit_pct: float) -> float:
        if annual_income <= 0:
            return 0.0
        monthly_income = annual_income / 12
        match_eligible = monthly_income * (match_limit_pct / 100)
        contribution_for_match = min(monthly_contribution, match_eligible)
        return contribution_for_match * (match_pct / 100)

    @staticmethod
    def calculate(inputs: RetirementInputs) -> RetirementResults:
        r = RetirementResults()
        debts = RetirementCalculator._parse_debt_payoffs(inputs.debt_payoffs)

        r.years_to_retirement = max(0, inputs.retirement_age - inputs.current_age)
        r.years_in_retirement = max(0, inputs.life_expectancy - inputs.retirement_age)

        # --- Step 1: Determine annual income need in retirement ---
        # Priority: desired_annual > current_annual_expenses > income_replacement_pct
        if inputs.desired_annual_retirement_income and inputs.desired_annual_retirement_income > 0:
            base_expenses = inputs.desired_annual_retirement_income
        elif inputs.current_annual_expenses and inputs.current_annual_expenses > 0:
            base_expenses = inputs.current_annual_expenses
        else:
            base_expenses = inputs.current_annual_income * (inputs.income_replacement_pct / 100)

        # Subtract debts that pay off before retirement
        debt_savings = 0.0
        for d in debts:
            if d.payoff_age > 0 and d.payoff_age <= inputs.retirement_age:
                debt_savings += d.monthly_payment * 12
        r.debt_payoff_savings_annual = debt_savings
        base_expenses = max(0, base_expenses - debt_savings)

        base_expenses += inputs.healthcare_annual_estimate
        base_expenses += inputs.additional_annual_expenses
        r.annual_income_needed_today = base_expenses

        inflation_mult = (1 + inputs.inflation_rate_pct / 100) ** r.years_to_retirement
        r.annual_income_needed_at_retirement = r.annual_income_needed_today * inflation_mult
        pre_tax = r.annual_income_needed_at_retirement / (1 - inputs.tax_rate_in_retirement_pct / 100)
        r.annual_income_needed_at_retirement = pre_tax
        r.monthly_income_needed_at_retirement = r.annual_income_needed_at_retirement / 12

        # --- Step 2: Guaranteed income sources ---
        ss_inflated = inputs.expected_social_security_monthly * inflation_mult
        pension_inflated = inputs.pension_monthly * inflation_mult
        other_inflated = inputs.other_retirement_income_monthly * inflation_mult

        r.social_security_annual = ss_inflated * 12
        r.pension_annual = pension_inflated * 12
        r.other_income_annual = other_inflated * 12
        r.total_guaranteed_income_annual = r.social_security_annual + r.pension_annual + r.other_income_annual

        r.portfolio_income_needed_annual = max(
            0, r.annual_income_needed_at_retirement - r.total_guaranteed_income_annual
        )

        # --- Step 3: Target nest egg (present value of withdrawals) ---
        real_return = (1 + inputs.post_retirement_return_pct / 100) / (1 + inputs.inflation_rate_pct / 100) - 1
        if real_return > 0 and r.years_in_retirement > 0:
            pv_factor = (1 - (1 + real_return) ** (-r.years_in_retirement)) / real_return
        else:
            pv_factor = r.years_in_retirement

        r.target_nest_egg = r.portfolio_income_needed_annual * pv_factor

        # --- Step 4: FIRE numbers ---
        annual_expenses_today = r.annual_income_needed_today
        r.fire_number = annual_expenses_today * 25
        r.lean_fire_number = annual_expenses_today * 0.7 * 25
        if r.years_to_retirement > 0 and inputs.pre_retirement_return_pct > 0:
            r.coast_fire_number = r.target_nest_egg / (
                (1 + inputs.pre_retirement_return_pct / 100) ** r.years_to_retirement
            )
        else:
            r.coast_fire_number = r.target_nest_egg

        # --- Step 5: Employer match calculation ---
        r.employer_match_monthly = RetirementCalculator._compute_employer_match(
            inputs.monthly_retirement_contribution, inputs.current_annual_income,
            inputs.employer_match_pct, inputs.employer_match_limit_pct,
        )
        r.total_monthly_contribution = inputs.monthly_retirement_contribution + r.employer_match_monthly

        # --- Step 6: Project nest egg at retirement (with income growth) ---
        # Year-by-year accumulation so contributions grow with income
        balance = inputs.current_retirement_savings + inputs.current_other_investments
        annual_return_rate = inputs.pre_retirement_return_pct / 100
        income_growth = inputs.expected_income_growth_pct / 100
        annual_contribution = r.total_monthly_contribution * 12
        current_income = inputs.current_annual_income

        for yr in range(r.years_to_retirement):
            growth = balance * annual_return_rate
            balance += growth + annual_contribution
            # Grow income and recalculate contribution with match for next year
            current_income *= (1 + income_growth)
            base_contribution = inputs.monthly_retirement_contribution * (1 + income_growth) ** (yr + 1)
            match = RetirementCalculator._compute_employer_match(
                base_contribution, current_income,
                inputs.employer_match_pct, inputs.employer_match_limit_pct,
            )
            annual_contribution = (base_contribution + match) * 12

        r.projected_nest_egg = balance

        # --- Step 7: Gap analysis ---
        r.savings_gap = r.projected_nest_egg - r.target_nest_egg
        r.retirement_readiness_pct = min(
            100, (r.projected_nest_egg / r.target_nest_egg * 100) if r.target_nest_egg > 0 else 0
        )
        r.on_track = r.savings_gap >= 0

        months = r.years_to_retirement * 12
        monthly_return = inputs.pre_retirement_return_pct / 100 / 12
        if r.savings_gap < 0 and months > 0 and monthly_return > 0:
            gap = abs(r.savings_gap)
            r.monthly_savings_needed = gap * monthly_return / ((1 + monthly_return) ** months - 1)
        else:
            r.monthly_savings_needed = 0

        # --- Step 8: How long will the money last? ---
        r.years_money_will_last = RetirementCalculator._years_money_lasts(
            r.projected_nest_egg, r.portfolio_income_needed_annual,
            inputs.post_retirement_return_pct, inputs.inflation_rate_pct,
            r.years_in_retirement,
        )

        r.projected_monthly_income = (
            (r.projected_nest_egg * (inputs.post_retirement_return_pct / 100) / 12)
            + (r.total_guaranteed_income_annual / 12)
        ) if r.projected_nest_egg > 0 else r.total_guaranteed_income_annual / 12

        # --- Step 9: Savings rate analysis ---
        if inputs.current_annual_income > 0:
            r.current_savings_rate_pct = (r.total_monthly_contribution * 12) / inputs.current_annual_income * 100
            needed_total = r.total_monthly_contribution + max(0, r.monthly_savings_needed)
            r.recommended_savings_rate_pct = (needed_total * 12) / inputs.current_annual_income * 100
        else:
            r.current_savings_rate_pct = 0
            r.recommended_savings_rate_pct = 0

        # --- Step 10: Earliest possible retirement age ---
        r.earliest_retirement_age = RetirementCalculator._find_earliest_retirement(inputs)

        # --- Step 11: Year-by-year projection for charting ---
        r.yearly_projection = RetirementCalculator._build_yearly_projection(inputs, r, debts)

        return r

    @staticmethod
    def _years_money_lasts(nest_egg: float, annual_withdrawal_need: float,
                           post_return_pct: float, inflation_pct: float,
                           years_in_retirement: int) -> float:
        if annual_withdrawal_need <= 0 or nest_egg <= 0:
            return years_in_retirement if nest_egg > 0 else 0

        monthly_withdrawal = annual_withdrawal_need / 12
        post_monthly_return = (1 + post_return_pct / 100) ** (1 / 12) - 1
        monthly_inflation = (1 + inflation_pct / 100) ** (1 / 12) - 1
        balance = nest_egg
        months_lasted = 0
        max_months = years_in_retirement * 12 + 120
        withdrawal = monthly_withdrawal
        while balance > 0 and months_lasted < max_months:
            balance = balance * (1 + post_monthly_return) - withdrawal
            withdrawal *= (1 + monthly_inflation)
            months_lasted += 1
        return months_lasted / 12

    @staticmethod
    def _find_earliest_retirement(inputs: RetirementInputs) -> int:
        """Binary-search for earliest age where projected savings cover retirement."""
        debts = RetirementCalculator._parse_debt_payoffs(inputs.debt_payoffs)
        lo, hi = inputs.current_age, inputs.life_expectancy

        # Quick check: can they ever retire?
        test = RetirementInputs(**{
            f.name: getattr(inputs, f.name) for f in inputs.__dataclass_fields__.values()
        })
        test.retirement_age = hi - 1
        if test.retirement_age <= inputs.current_age:
            return inputs.life_expectancy

        best = inputs.life_expectancy
        while lo <= hi:
            mid = (lo + hi) // 2
            if mid <= inputs.current_age:
                lo = mid + 1
                continue
            test_inputs = RetirementInputs(**{
                f.name: getattr(inputs, f.name) for f in inputs.__dataclass_fields__.values()
            })
            test_inputs.retirement_age = mid
            ytr = mid - inputs.current_age
            yir = max(0, inputs.life_expectancy - mid)

            # Compute target for this retirement age
            base_expenses = RetirementCalculator._base_expenses(test_inputs, debts, mid)
            infl = (1 + inputs.inflation_rate_pct / 100) ** ytr
            needed_at_retire = base_expenses * infl / (1 - inputs.tax_rate_in_retirement_pct / 100)
            ss = inputs.expected_social_security_monthly * infl * 12 if mid >= inputs.social_security_start_age else 0
            pension = inputs.pension_monthly * infl * 12
            other = inputs.other_retirement_income_monthly * infl * 12
            portfolio_need = max(0, needed_at_retire - ss - pension - other)
            real_ret = (1 + inputs.post_retirement_return_pct / 100) / (1 + inputs.inflation_rate_pct / 100) - 1
            pv = (1 - (1 + real_ret) ** (-yir)) / real_ret if real_ret > 0 and yir > 0 else yir
            target = portfolio_need * pv

            # Compute projected savings at this age
            projected = RetirementCalculator._project_savings_at_age(inputs, mid)

            if projected >= target:
                best = mid
                hi = mid - 1
            else:
                lo = mid + 1

        return best

    @staticmethod
    def _base_expenses(inputs: RetirementInputs, debts: list[DebtPayoff], retire_age: int) -> float:
        if inputs.desired_annual_retirement_income and inputs.desired_annual_retirement_income > 0:
            base = inputs.desired_annual_retirement_income
        elif inputs.current_annual_expenses and inputs.current_annual_expenses > 0:
            base = inputs.current_annual_expenses
        else:
            base = inputs.current_annual_income * (inputs.income_replacement_pct / 100)
        for d in debts:
            if d.payoff_age > 0 and d.payoff_age <= retire_age:
                base -= d.monthly_payment * 12
        base = max(0, base)
        base += inputs.healthcare_annual_estimate + inputs.additional_annual_expenses
        return base

    @staticmethod
    def _project_savings_at_age(inputs: RetirementInputs, target_age: int) -> float:
        years = max(0, target_age - inputs.current_age)
        balance = inputs.current_retirement_savings + inputs.current_other_investments
        annual_return = inputs.pre_retirement_return_pct / 100
        income_growth = inputs.expected_income_growth_pct / 100
        match_monthly = RetirementCalculator._compute_employer_match(
            inputs.monthly_retirement_contribution, inputs.current_annual_income,
            inputs.employer_match_pct, inputs.employer_match_limit_pct,
        )
        annual_contribution = (inputs.monthly_retirement_contribution + match_monthly) * 12
        current_income = inputs.current_annual_income

        for yr in range(years):
            balance += balance * annual_return + annual_contribution
            current_income *= (1 + income_growth)
            base_c = inputs.monthly_retirement_contribution * (1 + income_growth) ** (yr + 1)
            m = RetirementCalculator._compute_employer_match(
                base_c, current_income, inputs.employer_match_pct, inputs.employer_match_limit_pct,
            )
            annual_contribution = (base_c + m) * 12
        return balance

    @staticmethod
    def _build_yearly_projection(
        inputs: RetirementInputs,
        results: RetirementResults,
        debts: list[DebtPayoff],
    ) -> list[dict]:
        projection = []
        balance = inputs.current_retirement_savings + inputs.current_other_investments
        annual_contribution = results.total_monthly_contribution * 12
        current_income = inputs.current_annual_income
        income_growth = inputs.expected_income_growth_pct / 100

        for year_offset in range(max(results.years_to_retirement + results.years_in_retirement + 1, 1)):
            age = inputs.current_age + year_offset
            phase = "accumulation" if age < inputs.retirement_age else "distribution"

            if phase == "accumulation":
                growth = balance * (inputs.pre_retirement_return_pct / 100)
                balance = balance + growth + annual_contribution
                # Grow income and recalculate contributions for next year
                current_income *= (1 + income_growth)
                base_c = inputs.monthly_retirement_contribution * (1 + income_growth) ** (year_offset + 1)
                match = RetirementCalculator._compute_employer_match(
                    base_c, current_income, inputs.employer_match_pct, inputs.employer_match_limit_pct,
                )
                annual_contribution = (base_c + match) * 12
                withdrawal = 0
            else:
                growth = balance * (inputs.post_retirement_return_pct / 100)
                inflation_factor = (1 + inputs.inflation_rate_pct / 100) ** year_offset
                # Compute expenses, accounting for debts that have paid off by this age
                base_exp = results.annual_income_needed_today
                for d in debts:
                    if d.payoff_age > 0 and d.payoff_age > inputs.retirement_age and d.payoff_age <= age:
                        base_exp -= d.monthly_payment * 12
                base_exp = max(0, base_exp)
                needed = base_exp * inflation_factor
                guaranteed = results.total_guaranteed_income_annual * (
                    1 if age >= inputs.social_security_start_age else 0
                )
                withdrawal = max(0, needed - guaranteed)
                balance = balance + growth - withdrawal
                balance = max(0, balance)

            projection.append({
                "age": age,
                "year": year_offset,
                "phase": phase,
                "balance": round(balance, 0),
                "growth": round(growth if year_offset > 0 or phase == "distribution" else 0, 0),
                "contribution": round(annual_contribution if phase == "accumulation" else 0, 0),
                "withdrawal": round(withdrawal, 0),
            })

            if balance <= 0 and phase == "distribution":
                break

        return projection

    @staticmethod
    def monte_carlo(
        inputs: RetirementInputs,
        num_simulations: int = 1000,
        return_sigma: float = 15.0,
        inflation_sigma: float = 1.5,
        seed: int | None = 42,
    ) -> dict:
        """
        Monte Carlo retirement simulation.

        Runs `num_simulations` trials varying annual returns and inflation
        around the configured mean. Returns success rate and percentile outcomes.

        Args:
            inputs: Standard retirement inputs (mean assumptions)
            num_simulations: Number of simulation runs (default 1000)
            return_sigma: Std dev of annual return in percentage points (default 15)
            inflation_sigma: Std dev of annual inflation in percentage points (default 1.5)
            seed: Random seed for reproducibility (None for non-deterministic)
        """
        if seed is not None:
            random.seed(seed)

        years_to_ret = max(0, inputs.retirement_age - inputs.current_age)
        years_in_ret = max(0, inputs.life_expectancy - inputs.retirement_age)
        total_years = years_to_ret + years_in_ret

        debts = RetirementCalculator._parse_debt_payoffs(inputs.debt_payoffs)
        base_expenses = RetirementCalculator._base_expenses(inputs, debts, inputs.retirement_age)

        # Guaranteed income
        ss_annual = inputs.expected_social_security_monthly * 12
        pension_annual = inputs.pension_monthly * 12
        other_annual = inputs.other_retirement_income_monthly * 12

        # Track final balances
        final_balances: list[float] = []
        success_count = 0
        percentile_series: dict[str, list[dict]] = {
            "p10": [], "p25": [], "p50": [], "p75": [], "p90": [],
        }
        # Collect all simulation year-by-year for percentile extraction
        all_runs: list[list[float]] = []

        for _ in range(num_simulations):
            balance = inputs.current_retirement_savings + inputs.current_other_investments
            match_monthly = RetirementCalculator._compute_employer_match(
                inputs.monthly_retirement_contribution, inputs.current_annual_income,
                inputs.employer_match_pct, inputs.employer_match_limit_pct,
            )
            annual_contribution = (inputs.monthly_retirement_contribution + match_monthly) * 12
            current_income = inputs.current_annual_income
            yearly = []

            for yr in range(total_years):
                age = inputs.current_age + yr

                # Randomize returns and inflation for this year
                annual_return = random.gauss(inputs.pre_retirement_return_pct if yr < years_to_ret else inputs.post_retirement_return_pct, return_sigma) / 100
                annual_inflation = max(0, random.gauss(inputs.inflation_rate_pct, inflation_sigma)) / 100

                if yr < years_to_ret:
                    # Accumulation phase
                    balance = balance * (1 + annual_return) + annual_contribution
                    current_income *= (1 + inputs.expected_income_growth_pct / 100)
                    base_c = inputs.monthly_retirement_contribution * (1 + inputs.expected_income_growth_pct / 100) ** (yr + 1)
                    m = RetirementCalculator._compute_employer_match(
                        base_c, current_income, inputs.employer_match_pct, inputs.employer_match_limit_pct,
                    )
                    annual_contribution = (base_c + m) * 12
                else:
                    # Distribution phase
                    inflation_factor = (1 + annual_inflation) ** yr
                    needed = base_expenses * inflation_factor / (1 - inputs.tax_rate_in_retirement_pct / 100)
                    guaranteed = 0.0
                    if age >= inputs.social_security_start_age:
                        guaranteed = (ss_annual + pension_annual + other_annual) * inflation_factor
                    withdrawal = max(0, needed - guaranteed)
                    balance = balance * (1 + annual_return) - withdrawal
                    balance = max(0, balance)

                yearly.append(round(balance, 0))

            all_runs.append(yearly)
            final_balances.append(balance)
            if balance > 0:
                success_count += 1

        # Compute percentiles year-by-year
        for yr_idx in range(total_years):
            values = sorted(run[yr_idx] if yr_idx < len(run) else 0 for run in all_runs)
            n = len(values)
            age = inputs.current_age + yr_idx
            for pct_key, pct_val in [("p10", 0.10), ("p25", 0.25), ("p50", 0.50), ("p75", 0.75), ("p90", 0.90)]:
                idx = min(int(n * pct_val), n - 1)
                percentile_series[pct_key].append({"age": age, "balance": values[idx]})

        final_sorted = sorted(final_balances)
        n = len(final_sorted)

        return {
            "success_rate": round(success_count / num_simulations * 100, 1),
            "num_simulations": num_simulations,
            "final_balance_p10": round(final_sorted[int(n * 0.10)], 0),
            "final_balance_p25": round(final_sorted[int(n * 0.25)], 0),
            "final_balance_p50": round(final_sorted[int(n * 0.50)], 0),
            "final_balance_p75": round(final_sorted[int(n * 0.75)], 0),
            "final_balance_p90": round(final_sorted[int(n * 0.90)], 0),
            "percentile_series": percentile_series,
        }

    @staticmethod
    def from_db_row(row) -> RetirementResults:
        """Recalculate from a RetirementProfile DB row."""
        import json
        debt_payoffs = []
        if hasattr(row, "debt_payoffs_json") and row.debt_payoffs_json:
            try:
                debt_payoffs = json.loads(row.debt_payoffs_json)
            except (json.JSONDecodeError, TypeError):
                pass

        inputs = RetirementInputs(
            current_age=row.current_age,
            retirement_age=row.retirement_age,
            life_expectancy=row.life_expectancy,
            current_annual_income=row.current_annual_income,
            expected_income_growth_pct=row.expected_income_growth_pct,
            expected_social_security_monthly=row.expected_social_security_monthly,
            social_security_start_age=row.social_security_start_age,
            pension_monthly=row.pension_monthly,
            other_retirement_income_monthly=row.other_retirement_income_monthly,
            current_retirement_savings=row.current_retirement_savings,
            current_other_investments=row.current_other_investments,
            monthly_retirement_contribution=row.monthly_retirement_contribution,
            employer_match_pct=row.employer_match_pct,
            employer_match_limit_pct=row.employer_match_limit_pct,
            desired_annual_retirement_income=row.desired_annual_retirement_income,
            income_replacement_pct=row.income_replacement_pct,
            healthcare_annual_estimate=row.healthcare_annual_estimate,
            additional_annual_expenses=row.additional_annual_expenses,
            inflation_rate_pct=row.inflation_rate_pct,
            pre_retirement_return_pct=row.pre_retirement_return_pct,
            post_retirement_return_pct=row.post_retirement_return_pct,
            tax_rate_in_retirement_pct=row.tax_rate_in_retirement_pct,
            current_annual_expenses=getattr(row, "current_annual_expenses", None),
            debt_payoffs=debt_payoffs,
        )
        return RetirementCalculator.calculate(inputs)
