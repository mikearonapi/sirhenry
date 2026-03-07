# Test Quality Audit Report

**Date:** 2026-03-07
**Scope:** All 38 test files in `tests/`
**Goal:** Identify assertions that pass trivially without verifying financial correctness.

## Audit Legend

- **WEAK:** Assertion that would pass even if the financial engine returned nonsensical values
- **GOOD:** Assertion that verifies a specific, mathematically derivable financial value

## Weakness Categories

1. **Type-only:** `isinstance(data, dict)` — proves nothing about financial correctness
2. **Existence-only:** `len(data) > 0` — data exists but could contain garbage
3. **Status-only:** `resp.status_code == 200` with no payload validation
4. **Missing financial validation:** `> 0` when specific dollar amounts are calculable
5. **Placeholder assertion:** Test re-implements the logic it's supposed to test
6. **Missing edge cases:** No boundary testing for financial thresholds

---

## Priority Files (8 named files)

### test_demo_integration.py

This is the **worst offender** in the codebase. Seeds a full Michael & Jessica Chen household ($410k combined income, 13 accounts, 2400+ transactions) but most endpoint assertions only verify the response is a dict or list.

- Line 147: WEAK: `counts.get("households", 0) >= 1` -> Demo seeds exactly 1 household; assert == 1
- Line 148: WEAK: `counts.get("accounts", 0) >= 10` -> Demo seeds exactly 13 accounts; assert == 13
- Line 149: WEAK: `counts.get("transactions", 0) >= 100` -> Demo seeds ~2400 transactions; assert >= 2000
- Line 161: WEAK: `len(data) >= 10` -> Demo has exactly 13 accounts; assert == 13
- Line 163: WEAK: `any("Chase" in n for n in names)` -> Should verify specific account names from seeder
- Line 183: WEAK: `len(data) > 0` -> Should verify transaction count range and that amounts are reasonable
- Line 191: WEAK: `len(categorized) > 0` -> Should verify categorization rate >= 80%
- Line 203: WEAK: `isinstance(data, list)` -> Type-only; no budget amounts checked
- Line 209: WEAK: `len(data) > 0` -> Should verify specific budget categories exist
- Line 215: WEAK: `isinstance(data, dict)` -> Type-only; no financial summary values checked
- Line 231: GOOD: `p["combined_income"] >= 400000` -> Verifies seeded income for Chen household
- Line 229: GOOD: `p["filing_status"] == "mfj"` -> Verifies seeded filing status
- Line 230: GOOD: `p["state"] == "NY"` -> Verifies seeded state
- Line 237: GOOD: `len(members) >= 3` -> Verifies Michael, Jessica, and Ethan exist
- Line 252-255: GOOD: Setup status booleans verified against seeded completeness
- Line 267: WEAK: `len(policies) >= 3` -> Should verify exact count and policy types
- Line 288: WEAK: `data["total_monthly_cost"] > 0` -> Should verify range ($5k-$15k for this household)
- Line 301: WEAK: `len(goals) >= 3` -> Should verify exact goal names from seeder
- Line 313: WEAK: `len(grants) >= 1` -> Should verify RSU grant details
- Line 319: WEAK: `isinstance(data, dict)` -> Type-only; equity dashboard values not checked
- Line 331: WEAK: `data["total_value"] > 0` -> Should verify portfolio value range ($500k-$2M for demo)
- Line 332: WEAK: `data["holdings_count"] > 0` -> Should verify exact holdings count from seeder
- Line 338: WEAK: `"allocation" in data` -> Key-existence only
- Line 344: WEAK: `"snapshots" in data or "data" in data or isinstance(data, dict)` -> Triple-fallback OR is extremely weak
- Line 351: GOOD: `len(data["presets"]) == 3` -> Verifies exact preset count
- Line 363: WEAK: `isinstance(data, dict)` -> Type-only; no tax amounts verified for $410k household
- Line 370: WEAK: `len(data["items"]) > 0` -> Should verify specific checklist items
- Line 382: WEAK: `len(profiles) >= 1` -> Should verify retirement projection values
- Line 406: WEAK: `isinstance(data, dict)` -> Type-only; no benchmark metrics checked
- Line 412: WEAK: `isinstance(data, (list, dict))` -> Type-only; no financial order of operations verified
- Line 426: WEAK: `isinstance(data, (list, dict))` -> Type-only
- Line 438: WEAK: `isinstance(data, dict)` -> Type-only; no rules summary values checked

**Summary:** 25 WEAK assertions, 5 GOOD assertions. ~83% weak rate.

### test_retirement.py

Tests RetirementCalculator with $250k income, 35yo, $200k savings, 50% match on 6%.

- Line 39: GOOD: `r.years_to_retirement == 20` -> Exact years calculation
- Line 43: GOOD: `r.years_in_retirement == 25` -> Exact years calculation
- Line 47: GOOD: `r.years_to_retirement == 0` -> Edge case verified exactly
- Line 51: WEAK: `r.target_nest_egg > 0` -> With 80% of $250k = $200k/yr need, target should be $3M-$8M range
- Line 55: WEAK: `r.projected_nest_egg > 0` -> With $200k savings + $2k/mo + match for 30 years at 7%, should be $2M-$5M
- Line 59: GOOD: `0 <= r.retirement_readiness_pct <= 500` -> Bounded range check
- Line 69: WEAK: `r.annual_income_needed_today > 0` -> 80% of $250k = $200k; assert == pytest.approx(200_000)
- Line 75: GOOD: `r.annual_income_needed_today >= 150_000` -> Verifies override minimum
- Line 87: GOOD: `r_with.annual_income_needed_today != r_without.annual_income_needed_today` -> Directional
- Line 96: WEAK: `r.employer_match_monthly > 0` -> 50% match on 6% of $250k/12 = $625/mo; assert == pytest.approx(625)
- Line 102: GOOD: `r.employer_match_monthly == 0` -> Exact zero verified
- Line 106: WEAK: `r.current_savings_rate_pct > 0` -> ($2k + $625) * 12 / $250k = 12.6%; should verify range
- Line 112: WEAK: `r.fire_number > 0` -> FIRE = 25x annual expenses; should be $5M+ for $200k/yr
- Line 116: GOOD: `r.coast_fire_number <= r.fire_number` -> Good relational check
- Line 124-126: GOOD: Exact retire-earlier scenario counts and years
- Line 137: GOOD: `s["projected_nest_egg"] < r.projected_nest_egg` -> Directional correctness
- Line 150: WEAK: `len(r.yearly_projection) > 0` -> Should be exactly 56 entries (age 35 to 90 inclusive)
- Line 165: GOOD: `len(ages) >= inputs.retirement_age - inputs.current_age` -> Correct minimum
- Line 174: GOOD: Debt payoff reduces expenses directionally
- Line 181: GOOD: `r.debt_payoff_savings_annual == 0` -> Exact zero for post-retirement debt
- Line 187: WEAK: `r.target_nest_egg >= 0` -> Too loose for zero income; should be exact 0 or specific healthcare amount
- Line 191: GOOD: `r.annual_income_needed_at_retirement > r.annual_income_needed_today` -> Inflation verified
- Line 198: GOOD: `r.total_monthly_contribution == 0` -> Exact zero

**Summary:** 7 WEAK assertions, 14 GOOD assertions. ~33% weak rate.

### test_tax_calculator.py

**STRONG file.** Verifies specific bracket calculations against known 2025 values.

- Lines 34-35: GOOD: `tax == pytest.approx(2_385.0, abs=1)` -> Exact 10% bracket calculation
- Lines 39-41: GOOD: Multi-bracket accumulation with exact expected values
- Lines 46-47: GOOD: Three-bracket calculation verified exactly
- Lines 50-58: GOOD: Four-bracket calculation verified exactly
- Lines 60-72: GOOD: Full seven-bracket calculation verified exactly
- Lines 75-78: GOOD: Zero and negative income edge cases
- Lines 81-82: GOOD: Single filer 10% bracket exact
- Lines 86-88: GOOD: Single filer higher bracket exact
- Lines 94-123: GOOD: All marginal rate lookups by bracket boundary
- Lines 130-143: GOOD: Standard deduction values by filing status
- Lines 149-182: GOOD: FICA calculations with specific expected values
- Lines 188-207: GOOD: SE tax with 0.9235 factor and SS cap
- Lines 213-235: GOOD: NIIT with threshold and min(excess, investment) logic
- Lines 241-267: GOOD: AMT exemption and phaseout
- Lines 273-292: GOOD: State tax rates (CA 13.3%, NY 10.9%, TX/FL = 0)
- Line 301: WEAK: `result["federal_tax"] > 0` -> For $250k MFJ W-2, federal tax is calculable (~$38k)
- Line 302: WEAK: `result["fica_tax"] > 0` -> For $250k, FICA is calculable
- Line 305: WEAK: `0 < result["effective_rate"] < 1` -> Range too wide; for $250k MFJ should be ~25-30%
- Line 309: WEAK: `result["marginal_rate"] >= 0.32` -> For $500k MFJ should be exactly 0.35
- Line 310: WEAK: `result["total_tax"] > 100_000` -> Should verify tighter range
- Line 314: WEAK: `result["se_tax"] > 0` -> SE tax on $150k is calculable
- Line 315: WEAK: `result["federal_tax"] > 0` -> Federal tax on $150k single is calculable
- Line 335: WEAK: `result["state_tax"] > 0` -> $200k * 0.133 = $26,600
- Line 348-350: GOOD: Child tax credit = $4,000 for 2 dependents
- Lines 353-355: GOOD: Zero income produces zero tax
- Lines 366: GOOD: `result["gross_income"] == 290_000` -> Exact gross calculation

**Summary:** 8 WEAK assertions (all in `TestTotalTaxEstimate`), ~50 GOOD assertions. ~14% weak rate.

### test_budget_actuals.py

**STRONG file.** Verifies exact dollar amounts from aggregated transactions.

- All assertions use exact values: `== 200.0`, `== 50.0`, `== 5000.0`, `== 275.0`
- No weak assertions found.

**Summary:** 0 WEAK assertions. 0% weak rate.

### test_planning_household.py

Mix of strong directional tests and weak `> 0` assertions.

- Line 52: WEAK: `result["recommendation"] in ("mfj", "mfs")` -> For equal $200k incomes, recommendation is deterministic
- Line 53: WEAK: `result["mfj_tax"] > 0` -> For $400k combined MFJ income, tax is ~$70k; verify range
- Line 54: WEAK: `result["mfs_tax"] > 0` -> For $200k/$200k MFS, each tax is ~$35k; verify range
- Line 63: GOOD: `result["recommendation"] == "mfj"` -> Correct for unequal incomes
- Line 64: GOOD: `result["filing_savings"] > 0` -> MFJ saves money vs MFS with unequal incomes
- Line 78: GOOD: `result_with_deps["mfj_tax"] < result_no_deps["mfj_tax"]` -> CTC reduces tax
- Line 85: WEAK: `result["filing_savings"] >= 0` -> Should verify specific savings amount for $150k/$150k
- Line 92-93: GOOD: Explanation text contains dollar sign
- Line 108: WEAK: `len(result["spouse_a_strategy"]) > 0` -> Should verify exact strategy count and actions
- Line 109: WEAK: `len(result["spouse_b_strategy"]) > 0` -> Same as above
- Line 110: WEAK: `result["total_tax_savings"] > 0` -> For $200k/$150k with 401k+HSA, tax savings ~$20k-$40k
- Line 122: GOOD: Strategy includes "HSA" action
- Line 134: GOOD: Strategy includes "Mega" action
- Line 146: GOOD: Strategy includes "Dependent Care" action
- Line 161-163: GOOD: No benefits = empty strategies and zero savings (exact values)
- Line 174: GOOD: HSA plan recommended
- Line 180-181: GOOD: Lower premium spouse recommended
- Line 187: GOOD: Triple tax recommendation text
- Line 207-209: GOOD: FSA recommended with specific child count and savings
- Line 219-220: GOOD: Credit when no FSA, FSA savings = 0
- Line 230-231: GOOD: No children under 13, zero childcare
- Line 251: GOOD: Net second income after childcare < gross
- Lines 270-275: GOOD: Full optimization returns all required sections
- Line 292: GOOD: `total_annual_savings == sum of parts` -> Verifies arithmetic consistency
- Line 303: WEAK: `len(result["recommendations"]) > 0` -> Should verify recommendation count and content
- Line 319-320: WEAK: `result["mfj_tax"] >= 0` and `result["mfs_tax"] >= 0` -> Floor check only
- Line 338-339: WEAK: `result["mfj_tax"] > 0` and `result["mfs_tax"] > 0` -> For $1.5M income, should verify high tax range
- Line 349-350: GOOD: Zero income = zero tax (exact values)

**Summary:** 11 WEAK assertions, ~20 GOOD assertions. ~35% weak rate.

### test_tax_modeling.py

Generally strong directional tests for advanced tax strategies.

- Lines 38-42: GOOD: Structure keys verified with exact count
- Lines 53-55: GOOD: Roth conversion reduces traditional balance vs. growth-only
- Lines 65-67: GOOD: Roth grows year over year
- Lines 69-76: GOOD: High income limits conversion room (directional)
- Various `> 0` assertions for tax amounts that could be more specific
- S-Corp analysis tests verify directional savings (SE tax reduction)
- QBI deduction tests verify 20% rate application
- State relocation tests verify directional savings
- Capital gains timing tests verify rate differences

**Summary:** Mostly directional (appropriate for modeling), ~15% could be tighter. Good overall.

### test_life_scenarios.py

Good mix of specific financial values and structural checks.

- Line 53-54: GOOD: `2500 < pmt < 2600` -> Tight range for $400k mortgage at 6.5%
- Line 59: GOOD: `pmt == pytest.approx(1_000, abs=1)` -> 0% interest exact
- Line 85: GOOD: `score <= 100` -> Ceiling verified
- Line 100: GOOD: `score >= 0` -> Floor verified
- Lines 104-117: GOOD: Parametrized verdict thresholds with exact mappings
- Line 128: GOOD: `len(templates) == 8` -> Exact template count
- Line 137: GOOD: Exact set of scenario types verified
- Line 165: GOOD: `result["down_payment_needed"] == 100_000` -> 20% of $500k exact
- Line 218: GOOD: `result["loan_amount"] == 50_000` -> $60k - $10k exact
- Line 290: GOOD: `result["years_until_college"] == 13` -> 18 - 5 exact
- Line 425: GOOD: `result["annual_recurring"] == 6_000` -> $500/mo * 12 exact
- Line 427: GOOD: `result["total_cost"] == 8_000` -> $6k + $2k exact
- Line 451: GOOD: `result["fire_number"] == 2_000_000` -> 25 * $80k exact
- Line 476: GOOD: `result["fire_number"] == 3_000_000` -> 25 * $120k exact
- Line 484: GOOD: `result["years_until_ss"] == 17` -> 67 - 50 exact
- Line 551: WEAK: `result["affordability_score"] >= 0` -> Floor only for zero income edge case
- Line 555: GOOD: `result["affordability_score"] <= 40` -> Ceiling for extreme case

**Summary:** ~3 WEAK assertions, ~30 GOOD assertions. ~9% weak rate.

### test_smart_defaults.py

**STRONG file.** Very specific computed values verified.

- Lines 43-68: GOOD: Employer match pure function tests with exact boolean results
- Lines 72-83: GOOD: Canonicalization mapping tests
- Lines 86-101: GOOD: Exclusion pattern tests
- Async DB tests verify exact aggregated values: `== 600_000`, `== 400_000`, `== 37_500`, `== 60.0`

**Summary:** 0% weak rate. Exemplary test file.

---

## Remaining Files (alphabetical)

### test_action_plan.py
- GOOD overall. Tests financial order of operations step status.
- No significant weak assertions.

### test_api_auth_portfolio.py
- GOOD. Allocation validation (sum to 100), CRUD operations.
- No significant weak assertions.

### test_api_household.py
- GOOD. CRUD lifecycle tests appropriate for API layer.

### test_api_insurance_recurring.py
- GOOD. Uses `pytest.approx` for insurance and recurring amounts.

### test_api_routes.py
- Appropriate for API layer (status codes + field presence).
- These are thin API contract tests, not financial logic tests.

### test_api_setup.py
- GOOD. Boolean status checks appropriate for setup status endpoint.

### test_budget_actuals.py
- GOOD. (Covered above.) Exact dollar amounts verified.

### test_budget_forecast.py
- Line 32: WEAK: `result["total_predicted"] > 0` -> For known transaction set, predicted amount is calculable
- Line 44: GOOD: `result["total_predicted"] > 400` -> Reasonable range for $1100 December spending
- Line 50: WEAK: `result["total_predicted"] > 0` -> Fallback average is calculable from inputs
- Line 200: GOOD: `result["total_predicted"] == pytest.approx(150, abs=1)` -> Exact single-month prediction
- Lines 148, 154, 161, 168: GOOD: Specific velocity status and projected totals
- **Summary:** 2 WEAK, ~15 GOOD. ~12% weak rate.

### test_category_rules.py
- GOOD. Boolean pattern matching assertions appropriate for rule engine.

### test_checklist_quarterly.py
- GOOD. Specific status values, dates, and amounts verified.

### test_data_access_layer.py
- GOOD. Large DAL test file with specific CRUD verification and exact value checks.

### test_diagnostic_endpoints.py
- Line 53-54: WEAK (Placeholder): Test re-implements the logic being tested:
  ```python
  for rate, expected in [(95, "good"), (80, "needs_attention"), (50, "poor")]:
      quality = "good" if rate >= 90 else "needs_attention" if rate >= 70 else "poor"
      assert quality == expected
  ```
  This test literally contains the implementation in the test body. It tests nothing from the codebase.
- Lines 82-87: WEAK (Placeholder): Same pattern — test re-implements status badge logic locally.
- Line 66: WEAK: `assert monthly > 0` and `assert monthly < annual_income` -> Tax on $300k MFJ is calculable
- **Summary:** 3 WEAK (2 placeholder), 3 GOOD. 50% weak rate.

### test_encryption.py
- GOOD. Fernet roundtrip encryption tests.

### test_importers.py
- GOOD. Specific parsed values from CSV files.

### test_insurance_analysis.py
- GOOD. DIME method with exact values: `== 2_100_000`, `== 1_500_000`, `== 200_000`.
- Employer coverage, severity levels, premium totals all verified exactly.

### test_migrations.py
- GOOD. Infrastructure tests with appropriate assertions.

### test_monte_carlo.py
- Lines 27-30: GOOD: Percentile ordering verified (p10 <= p25 <= p50 <= p75 <= p90)
- Line 68: WEAK: `result["p50"] > 100000` -> With 7% return, 1% vol, p50 after 10 years should be ~$196k
- Line 77: WEAK: `result["p50"] > 0` -> Trivially true for any positive initial balance
- Line 89: WEAK: `result["p50"] > 0` -> Same as above
- Line 107: GOOD: `high_spread > low_spread` -> Volatility increases dispersion
- **Summary:** 3 WEAK, ~8 GOOD. ~27% weak rate.

### test_onboarding_flow.py
- GOOD. Integration flow tests with appropriate assertions.

### test_plaid_sync.py
- GOOD. Specific balance values and transaction details.

### test_planning_equity.py
- GOOD. Uses `pytest.approx` for vesting calculations.

### test_portfolio_summary.py
- GOOD. Specific aggregation values verified.

### test_recurring_detection.py
- GOOD. Frequency detection and pattern matching.

### test_scenario_projection.py
- Line 63: GOOD: `result["combined_monthly_impact"] == 2000` -> Exact
- Line 70: GOOD: `result["combined_monthly_impact"] == 3500` -> Exact sum
- Line 103: GOOD: `pytest.approx(result["combined_savings_rate_after"], abs=0.1) == 33.33` -> Exact rate
- Line 129: GOOD: Net worth grows above $250k initial -> directional with specific floor
- Line 169-170: GOOD: Retirement age >= 60, years delayed >= 0
- Line 200-201: GOOD: Exact differences in comparison
- **Summary:** ~1 WEAK, ~15 GOOD. ~6% weak rate.

### test_setup_domains.py
- API CRUD integration tests. Appropriate assertions for API layer.

### test_tax_loss_harvest.py
- GOOD. Specific gain/loss amounts and wash sale rule verification.

### test_tax_modeling.py
- (Covered above.) Mostly directional, appropriate for modeling. ~15% could be tighter.

### test_tax_pipeline.py
- GOOD. Specific tax estimates verified with exact or tight-range values.

### test_thresholds_w4.py
- GOOD. Very thorough threshold verification with specific values.

### test_transaction_mutations.py
- GOOD. CRUD operations with specific dollar amounts.

### test_utils.py
- GOOD. Known SHA-256 hashes verified exactly.

---

## Summary Statistics

| File | WEAK | GOOD | Weak Rate |
|------|------|------|-----------|
| test_demo_integration.py | 25 | 5 | **83%** |
| test_diagnostic_endpoints.py | 3 | 3 | **50%** |
| test_planning_household.py | 11 | 20 | **35%** |
| test_retirement.py | 7 | 14 | **33%** |
| test_monte_carlo.py | 3 | 8 | **27%** |
| test_tax_modeling.py | ~10 | ~55 | **15%** |
| test_tax_calculator.py | 8 | 50 | **14%** |
| test_budget_forecast.py | 2 | 15 | **12%** |
| test_life_scenarios.py | 3 | 30 | **9%** |
| test_scenario_projection.py | 1 | 15 | **6%** |
| All other files (28) | ~0 | ~200+ | **<2%** |

## Top Weakness Patterns

1. **`isinstance(data, dict)` and `isinstance(data, list)`** — 15 instances, all in test_demo_integration.py
2. **`> 0` for calculable dollar amounts** — 18 instances across retirement, household, tax calculator
3. **`len(data) > 0` or `>= N` when exact count is known** — 8 instances
4. **Placeholder tests** — 2 instances in test_diagnostic_endpoints.py where the test body re-implements the logic

## Recommendations

1. **test_demo_integration.py needs a complete overhaul.** Every endpoint check should verify at least one specific financial value from the seeded Chen household.
2. **test_retirement.py** should verify target_nest_egg and projected_nest_egg are in specific ranges given the known inputs ($250k income, 35yo, $200k savings).
3. **test_tax_calculator.py** `TestTotalTaxEstimate` section should verify specific federal/FICA/SE amounts, not just `> 0`.
4. **test_diagnostic_endpoints.py** placeholder tests should call actual codebase functions instead of re-implementing logic inline.
5. **test_planning_household.py** should verify specific MFJ/MFS tax amounts and total savings ranges for the given income levels.
