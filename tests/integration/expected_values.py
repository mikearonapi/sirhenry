"""Golden reference values derived from pipeline/demo/seeder.py.

All values here are deterministic because the seeder uses random.Random(42).
Tests assert against these constants to detect regressions in financial math.
"""

# ── Household ──────────────────────────────────────────────────────────
SPOUSE_A_INCOME = 245_000
SPOUSE_B_INCOME = 165_000
COMBINED_INCOME = 410_000
FILING_STATUS = "mfj"
STATE = "NY"
DEPENDENTS = 1  # Ethan, age 3
CHILDCARE_ANNUAL = 28_800

# ── Retirement Inputs ──────────────────────────────────────────────────
CURRENT_AGE = 33
RETIREMENT_AGE = 52
LIFE_EXPECTANCY = 90
YEARS_TO_RETIREMENT = RETIREMENT_AGE - CURRENT_AGE  # 19
YEARS_IN_RETIREMENT = LIFE_EXPECTANCY - RETIREMENT_AGE  # 38

CURRENT_RETIREMENT_SAVINGS = 310_000
CURRENT_OTHER_INVESTMENTS = 54_000
MONTHLY_RETIREMENT_CONTRIBUTION = 5_200
EMPLOYER_MATCH_PCT = 50
EMPLOYER_MATCH_LIMIT_PCT = 6
INCOME_REPLACEMENT_PCT = 75
HEALTHCARE_ANNUAL = 20_000
CURRENT_ANNUAL_EXPENSES = 195_000
INFLATION_RATE_PCT = 3.0
PRE_RETIREMENT_RETURN_PCT = 7.0
POST_RETIREMENT_RETURN_PCT = 5.0
TAX_RATE_IN_RETIREMENT_PCT = 22.0
EXPECTED_INCOME_GROWTH_PCT = 3.5
EXPECTED_SS_MONTHLY = 3_400
SS_START_AGE = 67

# ── Derived Retirement ─────────────────────────────────────────────────
# income need = current_annual_expenses + healthcare = $215,000
ANNUAL_INCOME_NEEDED_TODAY = CURRENT_ANNUAL_EXPENSES + HEALTHCARE_ANNUAL  # $215,000
FIRE_NUMBER = ANNUAL_INCOME_NEEDED_TODAY * 25  # $5,375,000

# Employer match: monthly_income * match_limit% * match%
MONTHLY_INCOME = COMBINED_INCOME / 12  # $34,166.67
MATCH_ELIGIBLE_MONTHLY = MONTHLY_INCOME * (EMPLOYER_MATCH_LIMIT_PCT / 100)  # $2,050
EMPLOYER_MATCH_MONTHLY = min(MONTHLY_RETIREMENT_CONTRIBUTION, MATCH_ELIGIBLE_MONTHLY) * (EMPLOYER_MATCH_PCT / 100)  # $1,025

# ── Investment Holdings ────────────────────────────────────────────────
HOLDINGS = [
    {"ticker": "VTI", "shares": 420.0, "cost_basis": 87_360, "value": 108_168, "sector": "Broad Market"},
    {"ticker": "VXUS", "shares": 350.0, "cost_basis": 19_775, "value": 21_616, "sector": "International"},
    {"ticker": "VGT", "shares": 85.0, "cost_basis": 40_800, "value": 46_070, "sector": "Technology"},
    {"ticker": "VNQ", "shares": 280.0, "cost_basis": 22_960, "value": 24_640, "sector": "Real Estate"},
    {"ticker": "BND", "shares": 580.0, "cost_basis": 42_630, "value": 44_080, "sector": "Fixed Income"},
    {"ticker": "IEMG", "shares": 400.0, "cost_basis": 20_000, "value": 21_400, "sector": "Emerging Markets"},
    {"ticker": "AAPL", "shares": 165.0, "cost_basis": 28_380, "value": 36_414, "sector": "Technology"},
    {"ticker": "MSFT", "shares": 42.0, "cost_basis": 15_960, "value": 17_430, "sector": "Technology"},
]
TOTAL_HOLDINGS_VALUE = sum(h["value"] for h in HOLDINGS)  # $319,818
TOTAL_HOLDINGS_COST = sum(h["cost_basis"] for h in HOLDINGS)  # $277,865
TOTAL_UNREALIZED_GAIN = TOTAL_HOLDINGS_VALUE - TOTAL_HOLDINGS_COST

CRYPTO = [
    {"symbol": "BTC", "quantity": 0.35, "cost_basis": 14_700, "value": 23_975},
    {"symbol": "ETH", "quantity": 4.2, "cost_basis": 11_760, "value": 16_170},
]
TOTAL_CRYPTO_VALUE = sum(c["value"] for c in CRYPTO)  # $40,145
TOTAL_CRYPTO_COST = sum(c["cost_basis"] for c in CRYPTO)  # $26,460

INVESTMENT_HOLDINGS_COUNT = len(HOLDINGS)  # 8
CRYPTO_HOLDINGS_COUNT = len(CRYPTO)  # 2
TOTAL_HOLDINGS_COUNT = INVESTMENT_HOLDINGS_COUNT + CRYPTO_HOLDINGS_COUNT  # 10

# ── Manual Assets ──────────────────────────────────────────────────────
PRIMARY_RESIDENCE_VALUE = 580_000
MORTGAGE_BALANCE = 392_000
STUDENT_LOANS_MICHAEL = 48_000
STUDENT_LOANS_JESSICA = 28_000
TOTAL_STUDENT_LOANS = STUDENT_LOANS_MICHAEL + STUDENT_LOANS_JESSICA  # $76,000
TESLA_VALUE = 32_000
BMW_VALUE = 38_000
HSA_BALANCE = 18_500
COLLEGE_529_BALANCE = 12_800
TOTAL_LIABILITIES = MORTGAGE_BALANCE + TOTAL_STUDENT_LOANS  # $468,000

# ── Insurance ──────────────────────────────────────────────────────────
INSURANCE_POLICY_COUNT = 6
PERSONAL_LIFE_COVERAGE_A = 1_500_000  # Northwestern Mutual
PERSONAL_LIFE_COVERAGE_B = 1_000_000  # Haven Life
EMPLOYER_LIFE_COVERAGE_A = 490_000  # Meridian benefit
EMPLOYER_LIFE_COVERAGE_B = 330_000  # BlackRock benefit
TOTAL_LIFE_COVERAGE = (
    PERSONAL_LIFE_COVERAGE_A + PERSONAL_LIFE_COVERAGE_B
    + EMPLOYER_LIFE_COVERAGE_A + EMPLOYER_LIFE_COVERAGE_B
)  # $3,320,000
UMBRELLA_COVERAGE = 2_000_000
DISABILITY_COVERAGE = 163_000

ANNUAL_PREMIUMS = {
    "health": 5_760,
    "life_a": 1_020,
    "life_b": 780,
    "disability": 0,
    "auto": 4_560,
    "umbrella": 540,
}
TOTAL_ANNUAL_PREMIUMS = sum(ANNUAL_PREMIUMS.values())  # $12,660

# ── Budget ─────────────────────────────────────────────────────────────
BUDGET_CATEGORIES = {
    "Groceries": 1_500, "Food & Dining": 900, "Coffee & Tea": 100,
    "Housing": 5_075, "Utilities": 415, "Insurance": 660,
    "Childcare": 2_400, "Education": 120,
    "Healthcare": 350, "Fitness": 164,
    "Shopping": 500, "Clothing": 200,
    "Transportation": 200, "Auto & Gas": 150,
    "Travel": 800, "Entertainment": 110,
    "Software": 25, "Home Improvement": 200,
    "HSA": 692, "Education Savings": 500,
}
BUDGET_CATEGORY_COUNT = len(BUDGET_CATEGORIES)  # 20

# ── Recurring ──────────────────────────────────────────────────────────
RECURRING_COUNT = 19
# Key recurring amounts
MORTGAGE_PAYMENT = 3_800.0
PROPERTY_TAX_ESCROW = 850.0
DAYCARE = 2_400.0  # Bright Horizons in expenses, not in recurring items list

# ── Goals ──────────────────────────────────────────────────────────────
GOAL_COUNT = 4
EMERGENCY_FUND_TARGET = 60_000
EMERGENCY_FUND_CURRENT = 38_000
STUDENT_LOAN_GOAL_TARGET = 76_000
MAX_TAX_ADVANTAGED_TARGET = 55_300
SABBATICAL_FUND_TARGET = 80_000

# ── Equity ─────────────────────────────────────────────────────────────
EQUITY_GRANT_TOTAL_SHARES = 600
EQUITY_GRANT_VESTED_SHARES = 165
EQUITY_GRANT_UNVESTED_SHARES = 435
EQUITY_GRANT_FMV = 220.69
EQUITY_GRANT_TICKER = "AAPL"

# ── Tax Items ──────────────────────────────────────────────────────────
MICHAEL_W2_WAGES = 245_000
JESSICA_W2_WAGES = 165_000
MICHAEL_FED_WITHHELD = 49_000
JESSICA_FED_WITHHELD = 29_700
TAX_YEAR = 2025

# ── Household Optimization (seeded) ───────────────────────────────────
SEEDED_MFJ_TAX = 114_600
SEEDED_MFS_TAX = 119_800
SEEDED_FILING_SAVINGS = 5_200
SEEDED_TOTAL_ANNUAL_SAVINGS = 29_650

# ── Net Worth Snapshots ────────────────────────────────────────────────
NET_WORTH_SNAPSHOT_COUNT = 24
EARLIEST_NET_WORTH = 165_000  # April 2024
LATEST_NET_WORTH = 395_000  # March 2026

# ── Life Events ────────────────────────────────────────────────────────
LIFE_EVENT_COUNT = 5

# ── Category Rules ─────────────────────────────────────────────────────
CATEGORY_RULE_COUNT = 12

# ── Accounts ───────────────────────────────────────────────────────────
ACCOUNT_COUNT = 13

# ── Chat ───────────────────────────────────────────────────────────────
CHAT_MESSAGE_COUNT = 4

# ── Tax Strategies ─────────────────────────────────────────────────────
TAX_STRATEGY_COUNT = 5

# ── Life Scenarios ─────────────────────────────────────────────────────
LIFE_SCENARIO_COUNT = 3
