"""
Seed a SEPARATE demo database with synthetic HENRY data.

Creates ~/.sirhenry/data/demo.db — NEVER touches financials.db.
Persona: Sarah (SWE, $220K) & Alex (PM, $160K), age 34, combined $380K.

Usage:
    python scripts/seed_demo.py

Then start the app with the demo DB:
    # macOS/Linux:
    export DATABASE_URL="sqlite+aiosqlite:///$HOME/.sirhenry/data/demo.db"
    # Windows:
    set DATABASE_URL=sqlite+aiosqlite:///%USERPROFILE%/.sirhenry/data/demo.db

    python -m uvicorn api.main:app --reload --port 8000
"""
import asyncio
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pipeline.db.schema import (
    Account,
    Base,
    BenefitPackage,
    Budget,
    ChatConversation,
    ChatMessage,
    EquityGrant,
    EquityTaxProjection,
    FamilyMember,
    FinancialPeriod,
    Goal,
    HouseholdOptimization,
    HouseholdProfile,
    InsurancePolicy,
    InvestmentHolding,
    LifeEvent,
    ManualAsset,
    NetWorthSnapshot,
    RecurringTransaction,
    RetirementProfile,
    TargetAllocation,
    TaxItem,
    TaxStrategy,
    Transaction,
    UserPrivacyConsent,
    VestingEvent,
    Document,
)

# ── Database path: always demo.db, never financials.db ─────────────────
HOME = os.path.expanduser("~")
DATA_DIR = os.path.join(HOME, ".sirhenry", "data")
DEMO_DB_PATH = os.path.join(DATA_DIR, "demo.db")
DEMO_DB_URL = f"sqlite+aiosqlite:///{DEMO_DB_PATH}"

# ── Dates ──────────────────────────────────────────────────────────────
TODAY = date(2026, 3, 5)
NOW = datetime(2026, 3, 5, 9, 0, 0)


def _dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


# ── Transaction generation helpers ─────────────────────────────────────
EXPENSE_TEMPLATES = [
    # (description, category, amount_low, amount_high, segment)
    ("Whole Foods Market", "Groceries", 85, 220, "personal"),
    ("Trader Joe's", "Groceries", 45, 120, "personal"),
    ("DoorDash", "Food & Dining", 28, 65, "personal"),
    ("Starbucks", "Coffee & Tea", 6, 15, "personal"),
    ("Amazon.com", "Shopping", 25, 180, "personal"),
    ("Target", "Shopping", 30, 120, "personal"),
    ("Shell Gas Station", "Auto & Gas", 45, 75, "personal"),
    ("Walgreens", "Health", 12, 45, "personal"),
    ("Pediatrician Co-pay", "Healthcare", 30, 50, "personal"),
    ("Home Depot", "Home Improvement", 35, 250, "personal"),
    ("Nordstrom", "Clothing", 60, 200, "personal"),
    ("Delta Airlines", "Travel", 250, 600, "personal"),
    ("Marriott Hotels", "Travel", 180, 350, "personal"),
    ("Uber", "Transportation", 15, 45, "personal"),
    ("Restaurant - Dinner", "Food & Dining", 60, 150, "personal"),
    ("Costco", "Groceries", 150, 350, "personal"),
    ("Wine.com", "Food & Dining", 30, 80, "personal"),
    ("Bright Horizons Daycare", "Childcare", 2200, 2200, "personal"),
    ("Piano Lessons", "Education", 200, 200, "personal"),
]

RECURRING_ITEMS = [
    ("Mortgage Payment", "Housing", -3800.00, "monthly", "Chase Checking"),
    ("HOA Dues", "Housing", -400.00, "monthly", "Chase Checking"),
    ("Auto Insurance - Progressive", "Insurance", -420.00, "monthly", "Chase Checking"),
    ("Home Insurance - Allstate", "Insurance", -185.00, "monthly", "Chase Checking"),
    ("Life Insurance - Northwestern", "Insurance", -95.00, "monthly", "Chase Checking"),
    ("Umbrella Insurance", "Insurance", -540.00, "annual", "Chase Checking"),
    ("Electric - ConEd", "Utilities", -180.00, "monthly", "Chase Checking"),
    ("Internet - Verizon Fios", "Utilities", -89.99, "monthly", "Chase Checking"),
    ("Cell Phone - T-Mobile", "Utilities", -140.00, "monthly", "Chase Checking"),
    ("Netflix", "Entertainment", -22.99, "monthly", "Chase Sapphire Reserve"),
    ("Spotify Family", "Entertainment", -16.99, "monthly", "Chase Sapphire Reserve"),
    ("Disney+", "Entertainment", -13.99, "monthly", "Chase Sapphire Reserve"),
    ("YouTube Premium", "Entertainment", -22.99, "monthly", "Chase Sapphire Reserve"),
    ("Apple One Family", "Entertainment", -32.95, "monthly", "Chase Sapphire Reserve"),
    ("Equinox Membership", "Fitness", -120.00, "monthly", "Amex Gold"),
    ("Peloton Subscription", "Fitness", -44.00, "monthly", "Amex Gold"),
    ("Claude Pro", "Software", -20.00, "monthly", "Chase Sapphire Reserve"),
    ("1Password Family", "Software", -4.99, "monthly", "Chase Sapphire Reserve"),
]


import random

random.seed(42)  # Reproducible data


def _generate_transactions(accounts_map: dict[str, int], months: int = 6) -> list[dict]:
    """Generate realistic transactions for the past N months."""
    txns = []
    checking_id = accounts_map["Chase Checking"]
    savings_id = accounts_map["Chase Savings"]
    csr_id = accounts_map["Chase Sapphire Reserve"]
    amex_id = accounts_map["Amex Gold"]

    for month_offset in range(months):
        m_date = TODAY.replace(day=1) - timedelta(days=30 * month_offset)
        year, month = m_date.year, m_date.month
        days_in_month = 28 if month == 2 else 30

        # Payroll deposits — biweekly, 2 per month
        for paycheck_day in [1, 15]:
            pay_date = date(year, month, min(paycheck_day, days_in_month))
            # Sarah's paycheck (net after tax/401k): ~$8,460
            txns.append({
                "account_id": checking_id, "date": _dt(pay_date),
                "description": "TECH CORP PAYROLL - DIRECT DEPOSIT",
                "amount": 8460.00, "category": "Paycheck", "segment": "personal",
                "period_year": year, "period_month": month, "ai_confidence": 0.99,
                "effective_category": "Paycheck", "effective_segment": "personal",
            })
            # Alex's paycheck: ~$6,154
            txns.append({
                "account_id": checking_id, "date": _dt(pay_date),
                "description": "MEDTECH INC PAYROLL - DIRECT DEPOSIT",
                "amount": 6154.00, "category": "Paycheck", "segment": "personal",
                "period_year": year, "period_month": month, "ai_confidence": 0.99,
                "effective_category": "Paycheck", "effective_segment": "personal",
            })

        # Recurring expenses
        for name, cat, amt, freq, acct_name in RECURRING_ITEMS:
            if freq == "annual" and month != 1:
                continue
            txn_date = date(year, month, random.randint(1, min(28, days_in_month)))
            acct_id = accounts_map.get(acct_name, checking_id)
            txns.append({
                "account_id": acct_id, "date": _dt(txn_date),
                "description": name, "amount": amt, "category": cat,
                "segment": "personal", "period_year": year, "period_month": month,
                "ai_confidence": 0.95, "effective_category": cat, "effective_segment": "personal",
            })

        # Variable expenses — 12-18 per month
        num_variable = random.randint(12, 18)
        for _ in range(num_variable):
            template = random.choice(EXPENSE_TEMPLATES)
            desc, cat, lo, hi, seg = template
            amt = -round(random.uniform(lo, hi), 2)
            txn_date = date(year, month, random.randint(1, min(28, days_in_month)))
            # Alternate between credit cards
            acct_id = random.choice([csr_id, amex_id])
            txns.append({
                "account_id": acct_id, "date": _dt(txn_date),
                "description": desc, "amount": amt, "category": cat,
                "segment": seg, "period_year": year, "period_month": month,
                "ai_confidence": round(random.uniform(0.75, 0.98), 2),
                "effective_category": cat, "effective_segment": seg,
            })

        # Savings transfer
        txns.append({
            "account_id": checking_id, "date": _dt(date(year, month, 5)),
            "description": "Transfer to Savings", "amount": -2000.00,
            "category": "Transfer", "segment": "personal",
            "period_year": year, "period_month": month, "ai_confidence": 0.99,
            "effective_category": "Transfer", "effective_segment": "personal",
        })

    return txns


async def seed():
    """Main seed function — creates demo.db and populates with synthetic data."""
    # ── Setup ──────────────────────────────────────────────────────────
    os.makedirs(DATA_DIR, exist_ok=True)

    # Remove old demo.db if exists
    if os.path.exists(DEMO_DB_PATH):
        os.remove(DEMO_DB_PATH)
        print(f"  Removed old {DEMO_DB_PATH}")

    engine = create_async_engine(DEMO_DB_URL, echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  Schema created")

    # Run migrations
    from pipeline.db.migrations import run_migrations
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        count = await run_migrations(session)
        print(f"  Migrations applied: {count}")

    # ── Seed data ──────────────────────────────────────────────────────
    async with session_factory() as session:
        # 1. Household Profile
        household = HouseholdProfile(
            name="Our Household", filing_status="mfj", state="NY",
            spouse_a_name="Sarah", spouse_b_name="Alex",
            spouse_a_income=220_000, spouse_b_income=160_000,
            spouse_a_employer="Tech Corp", spouse_b_employer="MedTech Inc",
            spouse_a_work_state="NY", spouse_b_work_state="NJ",
            combined_income=380_000, is_primary=True,
            dependents_json=json.dumps([{"name": "Emma", "age": 4, "relationship": "daughter"}]),
        )
        session.add(household)
        await session.flush()
        hh_id = household.id
        print(f"  HouseholdProfile: id={hh_id}")

        # 2. Family Members
        family = [
            FamilyMember(household_id=hh_id, name="Sarah", relationship="self",
                         date_of_birth=date(1992, 6, 15), is_earner=True,
                         income=220_000, employer="Tech Corp", work_state="NY"),
            FamilyMember(household_id=hh_id, name="Alex", relationship="spouse",
                         date_of_birth=date(1992, 3, 22), is_earner=True,
                         income=160_000, employer="MedTech Inc", work_state="NJ"),
            FamilyMember(household_id=hh_id, name="Emma", relationship="child",
                         date_of_birth=date(2022, 1, 10),
                         grade_level="Pre-K", care_cost_annual=26_400),
        ]
        session.add_all(family)
        print(f"  FamilyMembers: {len(family)}")

        # 3. Benefit Packages
        benefits = [
            BenefitPackage(
                household_id=hh_id, spouse="A", employer_name="Tech Corp",
                has_401k=True, has_roth_401k=True, has_mega_backdoor=True,
                has_hsa=True, has_fsa=False, has_dep_care_fsa=True, has_espp=True,
                employer_match_pct=50, employer_match_limit_pct=6,
                annual_401k_limit=23_500, mega_backdoor_limit=46_000,
                hsa_employer_contribution=1_000,
                health_premium_monthly=450, dental_vision_monthly=45,
                life_insurance_coverage=440_000, life_insurance_cost_monthly=0,
                espp_discount_pct=15,
            ),
            BenefitPackage(
                household_id=hh_id, spouse="B", employer_name="MedTech Inc",
                has_401k=True, has_roth_401k=False, has_mega_backdoor=False,
                has_hsa=False, has_fsa=True, has_dep_care_fsa=False, has_espp=False,
                employer_match_pct=100, employer_match_limit_pct=4,
                annual_401k_limit=23_500,
                health_premium_monthly=380, dental_vision_monthly=35,
                life_insurance_coverage=320_000, life_insurance_cost_monthly=22,
            ),
        ]
        session.add_all(benefits)
        print(f"  BenefitPackages: {len(benefits)}")

        # 4. Accounts
        acct_defs = [
            ("Chase Checking", "personal", "bank", "checking", "Chase", "4521"),
            ("Chase Savings", "personal", "bank", "savings", "Chase", "7893"),
            ("Fidelity 401(k) - Sarah", "investment", "brokerage", "401k", "Fidelity", "1234"),
            ("Vanguard Roth IRA", "investment", "brokerage", "ira", "Vanguard", "5678"),
            ("Fidelity 401(k) - Alex", "investment", "brokerage", "401k", "Fidelity", "9012"),
            ("Schwab Brokerage", "investment", "brokerage", "taxable", "Charles Schwab", "3456"),
            ("Chase Sapphire Reserve", "personal", "credit_card", "credit_card", "Chase", "7890"),
            ("Amex Gold", "personal", "credit_card", "credit_card", "American Express", "2345"),
            ("Tech Corp W-2", "income", "w2_employer", None, "Tech Corp", None),
            ("MedTech Inc W-2", "income", "w2_employer", None, "MedTech Inc", None),
        ]
        accounts = []
        accounts_map = {}
        for name, atype, subtype, _, inst, last4 in acct_defs:
            acct = Account(
                name=name, account_type=atype, subtype=subtype,
                institution=inst, last_four=last4, data_source="manual",
            )
            session.add(acct)
            accounts.append(acct)
        await session.flush()
        for acct in accounts:
            accounts_map[acct.name] = acct.id
        print(f"  Accounts: {len(accounts)}")

        # 5. Manual Assets (real estate + liabilities)
        assets = [
            ManualAsset(
                name="Home Equity", asset_type="real_estate", is_liability=False,
                current_value=120_000, purchase_price=450_000,
                purchase_date=_dt(date(2023, 6, 1)),
                address="123 Oak Street, Westchester, NY",
                description="Primary residence - estimated equity",
                owner="joint",
            ),
            ManualAsset(
                name="Student Loans - Sarah", asset_type="loan", is_liability=True,
                current_value=62_000, description="Federal student loans - MBA",
                institution="FedLoan Servicing",
            ),
            ManualAsset(
                name="Student Loans - Alex", asset_type="loan", is_liability=True,
                current_value=32_000, description="Federal student loans - MS",
                institution="FedLoan Servicing",
            ),
            ManualAsset(
                name="Tesla Model Y", asset_type="vehicle", is_liability=False,
                current_value=35_000, purchase_price=52_000,
                purchase_date=_dt(date(2024, 3, 1)),
                description="2024 Tesla Model Y Long Range",
            ),
        ]
        session.add_all(assets)
        print(f"  ManualAssets: {len(assets)}")

        # 6. Transactions
        txns_data = _generate_transactions(accounts_map, months=6)
        txn_objects = [Transaction(**t) for t in txns_data]
        session.add_all(txn_objects)
        print(f"  Transactions: {len(txn_objects)}")

        # 7. Budgets (3 months)
        budget_categories = [
            ("Groceries", 1400), ("Food & Dining", 800), ("Coffee & Tea", 80),
            ("Housing", 4200), ("Utilities", 410), ("Insurance", 700),
            ("Childcare", 2200), ("Education", 200),
            ("Healthcare", 300), ("Fitness", 164),
            ("Shopping", 500), ("Clothing", 200),
            ("Transportation", 200), ("Auto & Gas", 150),
            ("Travel", 800), ("Entertainment", 110),
            ("Software", 25), ("Home Improvement", 200),
        ]
        budget_objects = []
        for month_offset in range(3):
            m = TODAY.replace(day=1) - timedelta(days=30 * month_offset)
            for cat, amt in budget_categories:
                budget_objects.append(Budget(
                    year=m.year, month=m.month, category=cat,
                    segment="personal", budget_amount=amt,
                ))
        session.add_all(budget_objects)
        print(f"  Budgets: {len(budget_objects)}")

        # 8. Recurring Transactions
        recurring_objects = []
        for name, cat, amt, freq, acct_name in RECURRING_ITEMS:
            recurring_objects.append(RecurringTransaction(
                name=name, amount=abs(amt), frequency=freq, category=cat,
                segment="personal", status="active",
                account_id=accounts_map.get(acct_name),
                first_seen_date=_dt(date(2025, 7, 1)),
                last_seen_date=_dt(TODAY - timedelta(days=5)),
                next_expected_date=_dt(TODAY + timedelta(days=25)),
                is_auto_detected=True,
            ))
        session.add_all(recurring_objects)
        print(f"  RecurringTransactions: {len(recurring_objects)}")

        # 9. Goals
        goals = [
            Goal(name="Emergency Fund", goal_type="savings", target_amount=50_000,
                 current_amount=32_000, status="active", monthly_contribution=2_000,
                 color="#22c55e", icon="shield"),
            Goal(name="House Down Payment", goal_type="savings", target_amount=150_000,
                 current_amount=48_000, status="active", monthly_contribution=3_000,
                 color="#3b82f6", icon="home"),
            Goal(name="Pay Off Student Loans", goal_type="debt_payoff", target_amount=82_000,
                 current_amount=52_000, status="active", monthly_contribution=2_500,
                 color="#6366f1", icon="graduation-cap",
                 description="Combined federal student loans"),
            Goal(name="Max Tax-Advantaged Accounts", goal_type="tax", target_amount=30_500,
                 current_amount=22_875, status="active", monthly_contribution=2_542,
                 color="#f59e0b", icon="piggy-bank"),
        ]
        session.add_all(goals)
        print(f"  Goals: {len(goals)}")

        # 10. Investment Holdings
        holdings = [
            InvestmentHolding(
                account_id=accounts_map["Fidelity 401(k) - Sarah"], ticker="VTI",
                name="Vanguard Total Stock Market ETF", asset_class="etf",
                shares=380.5, cost_basis_per_share=210.00, total_cost_basis=79_905,
                current_price=257.54, current_value=98_000,
                unrealized_gain_loss=18_095, unrealized_gain_loss_pct=22.6,
                sector="Broad Market", is_active=True,
            ),
            InvestmentHolding(
                account_id=accounts_map["Vanguard Roth IRA"], ticker="VXUS",
                name="Vanguard Total International Stock ETF", asset_class="etf",
                shares=680.0, cost_basis_per_share=57.00, total_cost_basis=38_760,
                current_price=61.76, current_value=42_000,
                unrealized_gain_loss=3_240, unrealized_gain_loss_pct=8.4,
                sector="International", is_active=True,
            ),
            InvestmentHolding(
                account_id=accounts_map["Fidelity 401(k) - Alex"], ticker="BND",
                name="Vanguard Total Bond Market ETF", asset_class="bond",
                shares=500.0, cost_basis_per_share=74.00, total_cost_basis=37_000,
                current_price=76.00, current_value=38_000,
                unrealized_gain_loss=1_000, unrealized_gain_loss_pct=2.7,
                sector="Fixed Income", is_active=True,
            ),
            InvestmentHolding(
                account_id=accounts_map["Schwab Brokerage"], ticker="AAPL",
                name="Apple Inc (RSU)", asset_class="stock",
                shares=145.0, cost_basis_per_share=172.00, total_cost_basis=24_940,
                current_price=220.69, current_value=32_000,
                unrealized_gain_loss=7_060, unrealized_gain_loss_pct=28.3,
                sector="Technology", is_active=True,
            ),
            InvestmentHolding(
                account_id=accounts_map["Vanguard Roth IRA"], ticker="VNQ",
                name="Vanguard Real Estate ETF", asset_class="reit",
                shares=250.0, cost_basis_per_share=83.00, total_cost_basis=20_750,
                current_price=88.00, current_value=22_000,
                unrealized_gain_loss=1_250, unrealized_gain_loss_pct=6.0,
                sector="Real Estate", is_active=True,
            ),
        ]
        session.add_all(holdings)
        print(f"  InvestmentHoldings: {len(holdings)}")

        # 11. Target Allocation
        target = TargetAllocation(
            name="Growth Balanced",
            allocation_json=json.dumps({
                "US Stocks": 50, "International Stocks": 20,
                "Bonds": 15, "REITs": 10, "Cash": 5,
            }),
            is_active=True,
        )
        session.add(target)
        print("  TargetAllocation: 1")

        # 12. Retirement Profile
        retirement = RetirementProfile(
            name="Sarah & Alex Retirement Plan",
            current_age=34, retirement_age=54, life_expectancy=90,
            current_annual_income=380_000, expected_income_growth_pct=3.0,
            expected_social_security_monthly=3_200, social_security_start_age=67,
            current_retirement_savings=255_000, current_other_investments=30_000,
            monthly_retirement_contribution=4_500,
            employer_match_pct=50, employer_match_limit_pct=6,
            income_replacement_pct=75, healthcare_annual_estimate=18_000,
            current_annual_expenses=180_000,
            inflation_rate_pct=3.0,
            pre_retirement_return_pct=7.0, post_retirement_return_pct=5.0,
            tax_rate_in_retirement_pct=22.0,
            target_nest_egg=3_200_000, projected_nest_egg_at_retirement=3_450_000,
            retirement_readiness_pct=84.0,
            fire_number=3_200_000, coast_fire_number=890_000,
            earliest_retirement_age=52,
            is_primary=True, last_computed_at=NOW,
        )
        session.add(retirement)
        print("  RetirementProfile: 1")

        # 13. Equity Grant + Vesting Events
        grant = EquityGrant(
            employer_name="Tech Corp", grant_type="RSU",
            grant_date=date(2024, 3, 15),
            total_shares=500, vested_shares=145, unvested_shares=355,
            current_fmv=220.69, ticker="AAPL", is_active=True,
            vesting_schedule_json=json.dumps({
                "type": "4yr_cliff_1yr",
                "cliff_date": "2025-03-15",
                "cliff_shares": 125,
                "monthly_shares_after_cliff": 10.42,
            }),
        )
        session.add(grant)
        await session.flush()

        vest_events = [
            VestingEvent(grant_id=grant.id, vest_date=date(2025, 3, 15),
                         shares=125, price_at_vest=195.00, status="vested",
                         federal_withholding_pct=22, state_withholding_pct=6.85),
            VestingEvent(grant_id=grant.id, vest_date=date(2025, 6, 15),
                         shares=10, price_at_vest=208.50, status="vested"),
            VestingEvent(grant_id=grant.id, vest_date=date(2025, 9, 15),
                         shares=10, price_at_vest=215.00, status="vested"),
            VestingEvent(grant_id=grant.id, vest_date=date(2026, 3, 15),
                         shares=42, price_at_vest=None, status="upcoming"),
            VestingEvent(grant_id=grant.id, vest_date=date(2026, 6, 15),
                         shares=42, price_at_vest=None, status="upcoming"),
        ]
        session.add_all(vest_events)
        print(f"  EquityGrant: 1, VestingEvents: {len(vest_events)}")

        # Equity tax projection
        eq_tax = EquityTaxProjection(
            grant_id=grant.id, tax_year=2026,
            projected_vest_income=62_000, projected_withholding=13_640,
            withholding_gap=8_060, marginal_rate_used=35.0,
            recommendations_json=json.dumps([
                "Set aside $8,060 for tax underpayment",
                "Consider selling on vest to reduce concentration",
                "Review RSU timing with Q4 tax-loss harvesting",
            ]),
            computed_at=NOW,
        )
        session.add(eq_tax)

        # 14. Tax Items (W-2s for 2025)
        # Create dummy documents first
        doc_sarah = Document(
            filename="w2_techcorp_2025.pdf", original_path="/demo/w2_techcorp_2025.pdf",
            file_type="pdf", document_type="w2", status="completed",
            file_hash="demo_sarah_w2_2025", tax_year=2025,
            account_id=accounts_map["Tech Corp W-2"],
        )
        doc_alex = Document(
            filename="w2_medtech_2025.pdf", original_path="/demo/w2_medtech_2025.pdf",
            file_type="pdf", document_type="w2", status="completed",
            file_hash="demo_alex_w2_2025", tax_year=2025,
            account_id=accounts_map["MedTech Inc W-2"],
        )
        session.add_all([doc_sarah, doc_alex])
        await session.flush()

        tax_items = [
            TaxItem(
                source_document_id=doc_sarah.id, tax_year=2025, form_type="w2",
                payer_name="Tech Corp", w2_wages=220_000,
                w2_federal_tax_withheld=44_000, w2_ss_wages=168_600,
                w2_ss_tax_withheld=10_453, w2_medicare_wages=220_000,
                w2_medicare_tax_withheld=3_190, w2_state="NY",
                w2_state_wages=220_000, w2_state_income_tax=13_200,
            ),
            TaxItem(
                source_document_id=doc_alex.id, tax_year=2025, form_type="w2",
                payer_name="MedTech Inc", w2_wages=160_000,
                w2_federal_tax_withheld=28_800, w2_ss_wages=160_000,
                w2_ss_tax_withheld=9_920, w2_medicare_wages=160_000,
                w2_medicare_tax_withheld=2_320, w2_state="NJ",
                w2_state_wages=160_000, w2_state_income_tax=8_000,
            ),
        ]
        session.add_all(tax_items)
        print(f"  TaxItems: {len(tax_items)}")

        # 15. Tax Strategies
        strategies = [
            TaxStrategy(
                tax_year=2025, priority=1,
                title="Mega Backdoor Roth",
                description="Sarah's Tech Corp plan allows after-tax 401(k) contributions up to $69,000. Convert to Roth for tax-free growth.",
                strategy_type="retirement", category="quick_win", complexity="medium",
                estimated_savings_low=8_400, estimated_savings_high=12_600,
                action_required="Contact Fidelity to set up after-tax contributions and automatic Roth conversion",
                confidence=0.92, generated_at=NOW,
            ),
            TaxStrategy(
                tax_year=2025, priority=2,
                title="Tax-Loss Harvest Q4",
                description="International holdings (VXUS) have unrealized losses in certain lots. Harvest to offset RSU gains.",
                strategy_type="investment", category="quick_win", complexity="low",
                estimated_savings_low=1_200, estimated_savings_high=1_800,
                action_required="Review VXUS lots in Schwab. Sell loss lots, repurchase similar (not identical) fund after 30 days.",
                confidence=0.88, generated_at=NOW,
            ),
            TaxStrategy(
                tax_year=2025, priority=2,
                title="Donor Advised Fund",
                description="Contribute appreciated AAPL shares to a DAF. Deduct fair market value, avoid capital gains.",
                strategy_type="deduction", category="this_year", complexity="low",
                estimated_savings_low=3_500, estimated_savings_high=5_200,
                action_required="Open DAF at Fidelity Charitable. Contribute 50-75 AAPL shares before year-end.",
                confidence=0.85, generated_at=NOW,
            ),
            TaxStrategy(
                tax_year=2025, priority=3,
                title="RSU Timing Optimization",
                description="March vest of $62K at 35% marginal rate. Withholding gap of ~$8K. Plan estimated payments.",
                strategy_type="timing", category="this_year", complexity="medium",
                estimated_savings_low=2_800, estimated_savings_high=4_100,
                action_required="File Q1 estimated payment by April 15. Adjust W-4 withholding for remainder of year.",
                confidence=0.90, generated_at=NOW,
            ),
        ]
        session.add_all(strategies)
        print(f"  TaxStrategies: {len(strategies)}")

        # 16. Household Optimization
        optimization = HouseholdOptimization(
            household_id=hh_id, tax_year=2025,
            optimal_filing_status="mfj",
            mfj_tax=108_600, mfs_tax=112_800, filing_savings=4_200,
            total_annual_savings=25_250,
            recommendations_json=json.dumps([
                {"area": "Filing Status", "action": "MFJ saves $4,200 vs MFS", "savings": 4200},
                {"area": "401(k) Coordination", "action": "Max both 401(k)s — $46K combined", "savings": 16100},
                {"area": "Health Insurance", "action": "Use Tech Corp HDHP + HSA", "savings": 3200},
                {"area": "Childcare FSA", "action": "Elect Dependent Care FSA ($5K)", "savings": 1750},
            ]),
            computed_at=NOW,
        )
        session.add(optimization)
        print("  HouseholdOptimization: 1")

        # 17. Insurance Policies
        policies = [
            InsurancePolicy(household_id=hh_id, policy_type="health", provider="Aetna",
                            annual_premium=5_400, monthly_premium=450,
                            deductible=3_000, oop_max=7_000, employer_provided=True,
                            owner_spouse="A", is_active=True),
            InsurancePolicy(household_id=hh_id, policy_type="life", provider="Northwestern Mutual",
                            coverage_amount=1_000_000, annual_premium=1_140,
                            monthly_premium=95, owner_spouse="A", is_active=True),
            InsurancePolicy(household_id=hh_id, policy_type="disability", provider="Tech Corp",
                            coverage_amount=146_000, annual_premium=0,
                            employer_provided=True, owner_spouse="A", is_active=True),
            InsurancePolicy(household_id=hh_id, policy_type="auto", provider="Progressive",
                            annual_premium=5_040, monthly_premium=420,
                            deductible=500, is_active=True),
            InsurancePolicy(household_id=hh_id, policy_type="umbrella", provider="Allstate",
                            coverage_amount=2_000_000, annual_premium=540,
                            is_active=True),
        ]
        session.add_all(policies)
        print(f"  InsurancePolicies: {len(policies)}")

        # 18. Life Events
        events = [
            LifeEvent(household_id=hh_id, event_type="marriage", title="Married Alex",
                      event_date=date(2020, 9, 12), tax_year=2020, status="completed",
                      notes="Updated filing status to MFJ"),
            LifeEvent(household_id=hh_id, event_type="child", title="Emma born",
                      event_date=date(2022, 1, 10), tax_year=2022, status="completed",
                      amounts_json=json.dumps({"childcare_annual": 26_400})),
            LifeEvent(household_id=hh_id, event_type="home_purchase", title="Bought first home",
                      event_date=date(2023, 6, 1), tax_year=2023, status="completed",
                      amounts_json=json.dumps({"purchase_price": 450_000, "down_payment": 90_000})),
            LifeEvent(household_id=hh_id, event_type="job_change",
                      title="Sarah joined Tech Corp",
                      event_date=date(2024, 1, 15), tax_year=2024, status="completed",
                      notes="$40K raise + RSU grant"),
        ]
        session.add_all(events)
        print(f"  LifeEvents: {len(events)}")

        # 19. Net Worth Snapshots (6 months)
        nw_data = [
            (2025, 10, 305_000), (2025, 11, 314_000), (2025, 12, 322_000),
            (2026, 1, 330_000), (2026, 2, 338_000), (2026, 3, 347_000),
        ]
        snapshots = []
        for yr, mo, nw in nw_data:
            snapshots.append(NetWorthSnapshot(
                snapshot_date=_dt(date(yr, mo, 28)),
                year=yr, month=mo, net_worth=nw,
                total_assets=nw + 100_000,  # liabilities ~100K
                total_liabilities=100_000,
                checking_savings=42_000, investment_value=285_000 - (347_000 - nw),
                real_estate_value=120_000, credit_card_debt=6_000,
                loan_balance=94_000,
            ))
        session.add_all(snapshots)
        print(f"  NetWorthSnapshots: {len(snapshots)}")

        # 20. Financial Periods (6 months)
        periods = []
        for yr, mo, nw in nw_data:
            periods.append(FinancialPeriod(
                year=yr, month=mo, segment="all",
                total_income=29_228, total_expenses=23_200,
                net_cash_flow=6_028, w2_income=29_228,
                personal_expenses=23_200,
                computed_at=_dt(date(yr, mo, 28)),
            ))
        session.add_all(periods)
        print(f"  FinancialPeriods: {len(periods)}")

        # 21. Chat Conversation
        convo = ChatConversation(title="Tax Planning Discussion", created_at=NOW)
        session.add(convo)
        await session.flush()

        messages = [
            ChatMessage(conversation_id=convo.id, role="user",
                        content="My RSUs vest next month. What should I do?",
                        created_at=NOW - timedelta(hours=2)),
            ChatMessage(conversation_id=convo.id, role="assistant",
                        content="Your March vest is $62K (42 shares at ~$220.69/share). At your 35% marginal rate, that's a $21,700 tax event — but withholding only covers $13,640. Here's what I recommend:\n\n1. **Set aside $8,060 now** for the tax gap\n2. **Consider selling on vest** to reduce your AAPL concentration (currently 11% of portfolio)\n3. **Pair with tax-loss harvesting** — you have $4,200 in harvestable losses that could offset some of the gain\n\nWant me to run a scenario comparing hold vs. sell?",
                        actions_json=json.dumps([
                            {"tool": "equity_vest_lookup", "status": "completed"},
                            {"tool": "tax_estimate", "status": "completed"},
                        ]),
                        created_at=NOW - timedelta(hours=1, minutes=59)),
            ChatMessage(conversation_id=convo.id, role="user",
                        content="Should we do MFJ or MFS this year?",
                        created_at=NOW - timedelta(hours=1)),
            ChatMessage(conversation_id=convo.id, role="assistant",
                        content="**MFJ saves you $4,200 this year.** Here's the breakdown:\n\n| Filing Status | Federal Tax | State Tax | Total |\n|---|---|---|---|\n| MFJ | $72,800 | $35,800 | $108,600 |\n| MFS | $77,000 | $35,800 | $112,800 |\n\nMFS only makes sense if you're pursuing income-driven student loan repayment — but at your combined $380K income, you won't qualify for meaningful IDR savings. Stick with MFJ.",
                        actions_json=json.dumps([
                            {"tool": "filing_status_compare", "status": "completed"},
                            {"tool": "household_optimization", "status": "completed"},
                        ]),
                        created_at=NOW - timedelta(minutes=59)),
        ]
        session.add_all(messages)
        print(f"  ChatConversation: 1, Messages: {len(messages)}")

        # 22. Privacy Consent
        consents = [
            UserPrivacyConsent(consent_type="ai_features", consented=True,
                               consented_at=NOW - timedelta(days=30)),
            UserPrivacyConsent(consent_type="plaid_sync", consented=True,
                               consented_at=NOW - timedelta(days=30)),
        ]
        session.add_all(consents)
        print(f"  PrivacyConsents: {len(consents)}")

        # Commit everything
        await session.commit()

    await engine.dispose()
    print(f"\n{'='*60}")
    print(f"  Demo database created: {DEMO_DB_PATH}")
    print(f"  Size: {os.path.getsize(DEMO_DB_PATH) / 1024:.0f} KB")
    print(f"{'='*60}")
    print(f"\nTo use it, start the API with:")
    print(f'  set DATABASE_URL=sqlite+aiosqlite:///{DEMO_DB_PATH}')
    print(f"  python -m uvicorn api.main:app --reload --port 8000")


if __name__ == "__main__":
    print("Seeding demo database...")
    print(f"  Target: {DEMO_DB_PATH}")
    print(f"  Real DB will NOT be touched.\n")
    asyncio.run(seed())
