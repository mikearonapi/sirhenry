"""
ORM-based demo data seeder.

Persona: Michael Chen (Sr. Software Engineer, $245K) & Jessica Chen (Finance Manager,
$165K), age 33/32, combined $410K. Living in Westchester, NY with one child (Ethan, 3).

Michael has a small side consulting LLC and RSU grants from his employer.
Comprehensive HENRY household with 12 months of transaction history.
"""
import json
import logging
import random
from datetime import date, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import (
    Account,
    AppSettings,
    Base,
    BenefitPackage,
    Budget,
    BusinessEntity,
    CategoryRule,
    ChatConversation,
    ChatMessage,
    CryptoHolding,
    Document,
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
    LifeScenario,
    ManualAsset,
    NetWorthSnapshot,
    PortfolioSnapshot,
    RecurringTransaction,
    RetirementProfile,
    TargetAllocation,
    TaxItem,
    TaxProjection,
    TaxStrategy,
    Transaction,
    UserContext,
    UserPrivacyConsent,
    VendorEntityRule,
    VestingEvent,
)

logger = logging.getLogger(__name__)

# ── Dates ──────────────────────────────────────────────────────────────
TODAY = date(2026, 3, 5)
NOW = datetime(2026, 3, 5, 9, 0, 0)


def _dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


# ── Transaction templates ──────────────────────────────────────────────
EXPENSE_TEMPLATES = [
    ("Whole Foods Market", "Groceries", 85, 220, "personal"),
    ("Trader Joe's", "Groceries", 45, 120, "personal"),
    ("Costco", "Groceries", 150, 350, "personal"),
    ("DoorDash", "Food & Dining", 28, 65, "personal"),
    ("Starbucks", "Coffee & Tea", 6, 15, "personal"),
    ("Blue Bottle Coffee", "Coffee & Tea", 8, 18, "personal"),
    ("Amazon.com", "Shopping", 25, 180, "personal"),
    ("Target", "Shopping", 30, 120, "personal"),
    ("Shell Gas Station", "Auto & Gas", 45, 75, "personal"),
    ("Exxon", "Auto & Gas", 40, 70, "personal"),
    ("CVS Pharmacy", "Health", 12, 45, "personal"),
    ("Pediatrician Co-pay", "Healthcare", 30, 50, "personal"),
    ("Home Depot", "Home Improvement", 35, 250, "personal"),
    ("Nordstrom", "Clothing", 60, 200, "personal"),
    ("J.Crew", "Clothing", 40, 150, "personal"),
    ("Delta Airlines", "Travel", 250, 600, "personal"),
    ("United Airlines", "Travel", 200, 550, "personal"),
    ("Marriott Hotels", "Travel", 180, 350, "personal"),
    ("Uber", "Transportation", 15, 45, "personal"),
    ("Lyft", "Transportation", 12, 40, "personal"),
    ("Restaurant - Dinner", "Food & Dining", 60, 150, "personal"),
    ("Restaurant - Lunch", "Food & Dining", 18, 40, "personal"),
    ("Wine.com", "Food & Dining", 30, 80, "personal"),
    ("Bright Horizons Daycare", "Childcare", 2400, 2400, "personal"),
    ("KinderMusic Classes", "Education", 120, 120, "personal"),
    ("Lowe's", "Home Improvement", 40, 200, "personal"),
    ("REI", "Shopping", 50, 200, "personal"),
]

# Business expense templates (for Michael's consulting LLC)
BUSINESS_EXPENSE_TEMPLATES = [
    ("AWS Monthly", "Cloud Services", 85, 150, "business"),
    ("Vercel Pro", "Cloud Services", 20, 20, "business"),
    ("GitHub Enterprise", "Software", 21, 21, "business"),
    ("Figma Professional", "Software", 15, 15, "business"),
    ("WeWork Day Pass", "Office", 35, 65, "business"),
    ("Client Dinner", "Meals & Entertainment", 80, 200, "business"),
    ("Udemy Course", "Education", 15, 85, "business"),
    ("LinkedIn Premium", "Marketing", 60, 60, "business"),
]

RECURRING_ITEMS = [
    ("Mortgage Payment", "Housing", -3800.00, "monthly", "Chase Checking"),
    ("HOA Dues", "Housing", -425.00, "monthly", "Chase Checking"),
    ("Auto Insurance - Progressive", "Insurance", -380.00, "monthly", "Chase Checking"),
    ("Home Insurance - Allstate", "Insurance", -195.00, "monthly", "Chase Checking"),
    ("Life Insurance - Northwestern", "Insurance", -85.00, "monthly", "Chase Checking"),
    ("Umbrella Insurance", "Insurance", -540.00, "annual", "Chase Checking"),
    ("Electric - ConEd", "Utilities", -185.00, "monthly", "Chase Checking"),
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
    ("Property Tax Escrow", "Housing", -850.00, "monthly", "Chase Checking"),
]


def _generate_transactions(accounts_map: dict[str, int], months: int = 12) -> list[dict]:
    """Generate realistic transactions for the past N months."""
    rng = random.Random(42)  # Reproducible
    txns: list[dict] = []
    checking_id = accounts_map["Chase Checking"]
    savings_id = accounts_map["Chase Savings"]
    csr_id = accounts_map["Chase Sapphire Reserve"]
    amex_id = accounts_map["Amex Gold"]
    biz_checking_id = accounts_map.get("Chase Business Checking", checking_id)

    for month_offset in range(months):
        # Exact month arithmetic to avoid duplicate months
        year = TODAY.year
        month = TODAY.month - month_offset
        while month <= 0:
            month += 12
            year -= 1
        days_in_month = 28 if month == 2 else 30

        # Payroll deposits — biweekly (Michael: $9,420/check, Jessica: $6,346/check)
        for paycheck_day in [1, 15]:
            pay_date = date(year, month, min(paycheck_day, days_in_month))
            txns.append({
                "account_id": checking_id, "date": _dt(pay_date),
                "description": "MERIDIAN TECH PAYROLL - DIRECT DEPOSIT",
                "amount": 9420.00, "category": "Paycheck", "segment": "personal",
                "period_year": year, "period_month": month, "ai_confidence": 0.99,
                "effective_category": "Paycheck", "effective_segment": "personal",
            })
            txns.append({
                "account_id": checking_id, "date": _dt(pay_date),
                "description": "BLACKROCK PAYROLL - DIRECT DEPOSIT",
                "amount": 6346.00, "category": "Paycheck", "segment": "personal",
                "period_year": year, "period_month": month, "ai_confidence": 0.99,
                "effective_category": "Paycheck", "effective_segment": "personal",
            })

        # Consulting income — irregular (1-2 payments per month, $2K-$8K)
        num_invoices = rng.choice([0, 1, 1, 1, 2])
        for _ in range(num_invoices):
            inv_date = date(year, month, rng.randint(5, min(25, days_in_month)))
            inv_amount = round(rng.uniform(2000, 8000), 2)
            txns.append({
                "account_id": biz_checking_id, "date": _dt(inv_date),
                "description": "ACH DEPOSIT - CONSULTING INVOICE",
                "amount": inv_amount, "category": "Business Income",
                "segment": "business", "period_year": year, "period_month": month,
                "ai_confidence": 0.95,
                "effective_category": "Business Income", "effective_segment": "business",
            })

        # Recurring expenses
        for name, cat, amt, freq, acct_name in RECURRING_ITEMS:
            if freq == "annual" and month != 1:
                continue
            txn_date = date(year, month, rng.randint(1, min(28, days_in_month)))
            acct_id = accounts_map.get(acct_name, checking_id)
            txns.append({
                "account_id": acct_id, "date": _dt(txn_date),
                "description": name, "amount": amt, "category": cat,
                "segment": "personal", "period_year": year, "period_month": month,
                "ai_confidence": 0.95, "effective_category": cat,
                "effective_segment": "personal",
            })

        # Variable personal expenses (15-22 per month)
        num_variable = rng.randint(15, 22)
        for _ in range(num_variable):
            desc, cat, lo, hi, seg = rng.choice(EXPENSE_TEMPLATES)
            amt = -round(rng.uniform(lo, hi), 2)
            txn_date = date(year, month, rng.randint(1, min(28, days_in_month)))
            acct_id = rng.choice([csr_id, amex_id])
            txns.append({
                "account_id": acct_id, "date": _dt(txn_date),
                "description": desc, "amount": amt, "category": cat,
                "segment": seg, "period_year": year, "period_month": month,
                "ai_confidence": round(rng.uniform(0.75, 0.98), 2),
                "effective_category": cat, "effective_segment": seg,
            })

        # Business expenses (3-6 per month)
        num_biz = rng.randint(3, 6)
        for _ in range(num_biz):
            desc, cat, lo, hi, seg = rng.choice(BUSINESS_EXPENSE_TEMPLATES)
            amt = -round(rng.uniform(lo, hi), 2)
            txn_date = date(year, month, rng.randint(1, min(28, days_in_month)))
            txns.append({
                "account_id": biz_checking_id, "date": _dt(txn_date),
                "description": desc, "amount": amt, "category": cat,
                "segment": "business", "period_year": year, "period_month": month,
                "ai_confidence": round(rng.uniform(0.80, 0.96), 2),
                "effective_category": cat, "effective_segment": "business",
            })

        # Savings transfer
        txns.append({
            "account_id": checking_id, "date": _dt(date(year, month, 5)),
            "description": "Transfer to Savings", "amount": -3000.00,
            "category": "Transfer", "segment": "personal",
            "period_year": year, "period_month": month, "ai_confidence": 0.99,
            "effective_category": "Transfer", "effective_segment": "personal",
        })
        txns.append({
            "account_id": savings_id, "date": _dt(date(year, month, 5)),
            "description": "Transfer from Checking", "amount": 3000.00,
            "category": "Transfer", "segment": "personal",
            "period_year": year, "period_month": month, "ai_confidence": 0.99,
            "effective_category": "Transfer", "effective_segment": "personal",
        })

        # HSA contribution
        txns.append({
            "account_id": checking_id,
            "date": _dt(date(year, month, min(1, days_in_month))),
            "description": "HSA Contribution - Fidelity", "amount": -692.00,
            "category": "HSA", "segment": "personal",
            "period_year": year, "period_month": month, "ai_confidence": 0.99,
            "effective_category": "HSA", "effective_segment": "personal",
        })

        # 529 contribution
        txns.append({
            "account_id": checking_id,
            "date": _dt(date(year, month, min(15, days_in_month))),
            "description": "529 Plan Contribution - NY Saves", "amount": -500.00,
            "category": "Education Savings", "segment": "personal",
            "period_year": year, "period_month": month, "ai_confidence": 0.99,
            "effective_category": "Education Savings", "effective_segment": "personal",
        })

        # Credit card payments (pay off monthly)
        txns.append({
            "account_id": checking_id,
            "date": _dt(date(year, month, min(25, days_in_month))),
            "description": "Chase Sapphire Reserve Payment", "amount": -3200.00,
            "category": "Credit Card Payment", "segment": "personal",
            "period_year": year, "period_month": month, "ai_confidence": 0.99,
            "effective_category": "Credit Card Payment", "effective_segment": "personal",
        })
        txns.append({
            "account_id": checking_id,
            "date": _dt(date(year, month, min(25, days_in_month))),
            "description": "Amex Gold Payment", "amount": -1800.00,
            "category": "Credit Card Payment", "segment": "personal",
            "period_year": year, "period_month": month, "ai_confidence": 0.99,
            "effective_category": "Credit Card Payment", "effective_segment": "personal",
        })

    return txns


async def seed_demo_data(session: AsyncSession) -> dict:
    """
    Seed demo data into the current database.

    Returns dict with counts of created records.
    Raises ValueError if database already contains data.
    """
    # Safety check: refuse to seed into a non-empty DB
    hh_count = await session.scalar(select(func.count()).select_from(HouseholdProfile))
    acct_count = await session.scalar(select(func.count()).select_from(Account))
    if (hh_count or 0) > 0 or (acct_count or 0) > 0:
        raise ValueError("Database already contains data. Reset first.")

    counts: dict[str, int] = {}

    # ── 1. Household Profile ──────────────────────────────────────────
    household = HouseholdProfile(
        name="Our Household", filing_status="mfj", state="NY",
        spouse_a_name="Michael", spouse_b_name="Jessica",
        spouse_a_income=245_000, spouse_b_income=165_000,
        spouse_a_employer="Meridian Technologies", spouse_b_employer="BlackRock",
        spouse_a_work_state="NY", spouse_b_work_state="NY",
        combined_income=410_000, is_primary=True,
        dependents_json=json.dumps([
            {"name": "Ethan", "age": 3, "relationship": "son"},
        ]),
    )
    session.add(household)
    await session.flush()
    hh_id = household.id
    counts["households"] = 1

    # ── 2. Family Members ─────────────────────────────────────────────
    family = [
        FamilyMember(household_id=hh_id, name="Michael", relationship="self",
                     date_of_birth=date(1993, 4, 12), is_earner=True,
                     income=245_000, employer="Meridian Technologies",
                     work_state="NY"),
        FamilyMember(household_id=hh_id, name="Jessica", relationship="spouse",
                     date_of_birth=date(1994, 8, 3), is_earner=True,
                     income=165_000, employer="BlackRock", work_state="NY"),
        FamilyMember(household_id=hh_id, name="Ethan", relationship="child",
                     date_of_birth=date(2023, 5, 18),
                     grade_level="Pre-K", care_cost_annual=28_800),
    ]
    session.add_all(family)
    counts["family_members"] = len(family)

    # ── 3. Business Entity (consulting LLC) ───────────────────────────
    biz = BusinessEntity(
        name="Chen Digital Consulting LLC", owner="Michael",
        entity_type="llc", tax_treatment="schedule_c",
        is_active=True, is_provisional=False,
        active_from=date(2024, 1, 1),
        description="Software architecture consulting and technical advisory",
        expected_expenses="Cloud services, software, office, meals, education",
    )
    session.add(biz)
    await session.flush()
    biz_id = biz.id
    counts["business_entities"] = 1

    # ── 4. Benefit Packages ───────────────────────────────────────────
    benefits = [
        BenefitPackage(
            household_id=hh_id, spouse="A", employer_name="Meridian Technologies",
            has_401k=True, has_roth_401k=True, has_mega_backdoor=True,
            has_hsa=True, has_fsa=False, has_dep_care_fsa=True, has_espp=True,
            employer_match_pct=50, employer_match_limit_pct=6,
            annual_401k_limit=23_500, mega_backdoor_limit=46_000,
            hsa_employer_contribution=1_200,
            health_premium_monthly=480, dental_vision_monthly=52,
            life_insurance_coverage=490_000, life_insurance_cost_monthly=0,
            espp_discount_pct=15,
        ),
        BenefitPackage(
            household_id=hh_id, spouse="B", employer_name="BlackRock",
            has_401k=True, has_roth_401k=True, has_mega_backdoor=False,
            has_hsa=False, has_fsa=True, has_dep_care_fsa=True, has_espp=True,
            employer_match_pct=100, employer_match_limit_pct=5,
            annual_401k_limit=23_500,
            health_premium_monthly=420, dental_vision_monthly=38,
            life_insurance_coverage=330_000, life_insurance_cost_monthly=18,
            espp_discount_pct=10,
        ),
    ]
    session.add_all(benefits)
    counts["benefit_packages"] = len(benefits)

    # ── 5. Accounts ───────────────────────────────────────────────────
    acct_defs = [
        ("Chase Checking", "personal", "bank", "checking", "Chase", "4521"),
        ("Chase Savings", "personal", "bank", "savings", "Chase", "7893"),
        ("Chase Business Checking", "business", "bank", "checking", "Chase", "3318"),
        ("Fidelity 401(k) - Michael", "investment", "brokerage", "401k", "Fidelity", "1234"),
        ("Fidelity HSA", "investment", "brokerage", "hsa", "Fidelity", "4455"),
        ("Vanguard Roth IRA", "investment", "brokerage", "ira", "Vanguard", "5678"),
        ("BlackRock 401(k) - Jessica", "investment", "brokerage", "401k", "BlackRock", "9012"),
        ("Schwab Brokerage", "investment", "brokerage", "taxable", "Charles Schwab", "3456"),
        ("NY 529 College Savings", "investment", "brokerage", "529", "Vanguard", "7722"),
        ("Chase Sapphire Reserve", "personal", "credit_card", "credit_card", "Chase", "7890"),
        ("Amex Gold", "personal", "credit_card", "credit_card", "American Express", "2345"),
        ("Meridian Technologies W-2", "income", "w2_employer", None, "Meridian Technologies", None),
        ("BlackRock W-2", "income", "w2_employer", None, "BlackRock", None),
    ]
    accounts = []
    accounts_map: dict[str, int] = {}
    for name, atype, subtype, _, inst, last4 in acct_defs:
        acct = Account(
            name=name, account_type=atype, subtype=subtype,
            institution=inst, last_four=last4, data_source="manual",
        )
        if atype == "business":
            acct.default_segment = "business"
            acct.default_business_entity_id = biz_id
        session.add(acct)
        accounts.append(acct)
    await session.flush()
    for acct in accounts:
        accounts_map[acct.name] = acct.id
    counts["accounts"] = len(accounts)

    # ── 6. Manual Assets & Liabilities ────────────────────────────────
    assets = [
        ManualAsset(
            name="Primary Residence", asset_type="real_estate", is_liability=False,
            current_value=580_000, purchase_price=520_000,
            purchase_date=_dt(date(2023, 9, 1)),
            address="47 Maple Drive, Scarsdale, NY 10583",
            description="3BR/2BA colonial — primary residence",
            owner="joint",
        ),
        ManualAsset(
            name="Mortgage - Chase", asset_type="loan", is_liability=True,
            current_value=392_000, purchase_price=416_000,
            purchase_date=_dt(date(2023, 9, 1)),
            institution="Chase", owner="joint",
            description="30yr fixed @ 6.75%, $3,800/mo P&I",
        ),
        ManualAsset(
            name="Student Loans - Michael", asset_type="loan", is_liability=True,
            current_value=48_000, description="Federal student loans - MS CS (Stanford)",
            institution="FedLoan Servicing",
        ),
        ManualAsset(
            name="Student Loans - Jessica", asset_type="loan", is_liability=True,
            current_value=28_000, description="Federal student loans - MBA (NYU Stern)",
            institution="FedLoan Servicing",
        ),
        ManualAsset(
            name="Tesla Model 3", asset_type="vehicle", is_liability=False,
            current_value=32_000, purchase_price=48_000,
            purchase_date=_dt(date(2024, 6, 1)),
            description="2024 Tesla Model 3 Long Range",
            vin="5YJ3E1EA1RF123456",
        ),
        ManualAsset(
            name="BMW X3", asset_type="vehicle", is_liability=False,
            current_value=38_000, purchase_price=52_000,
            purchase_date=_dt(date(2023, 3, 15)),
            description="2023 BMW X3 xDrive30i",
        ),
        # HSA as manual asset for balance tracking
        ManualAsset(
            name="Fidelity HSA Balance", asset_type="hsa", is_liability=False,
            current_value=18_500, institution="Fidelity",
            is_retirement_account=True, tax_treatment="hsa",
            linked_account_id=None,  # Will link after flush
            description="Health Savings Account - invested in index funds",
        ),
        # 529 as manual asset
        ManualAsset(
            name="NY 529 - Ethan", asset_type="529", is_liability=False,
            current_value=12_800, institution="Vanguard",
            tax_treatment="529",
            description="NY 529 College Savings Plan for Ethan",
        ),
    ]
    session.add_all(assets)
    counts["manual_assets"] = len(assets)

    # ── 7. Transactions (24 months) ──────────────────────────────────
    txns_data = _generate_transactions(accounts_map, months=24)
    session.add_all([Transaction(**t) for t in txns_data])
    counts["transactions"] = len(txns_data)

    # ── 8. Budgets (12 months) ────────────────────────────────────────
    budget_categories = [
        ("Groceries", 1500), ("Food & Dining", 900), ("Coffee & Tea", 100),
        ("Housing", 5075), ("Utilities", 415), ("Insurance", 660),
        ("Childcare", 2400), ("Education", 120),
        ("Healthcare", 350), ("Fitness", 164),
        ("Shopping", 500), ("Clothing", 200),
        ("Transportation", 200), ("Auto & Gas", 150),
        ("Travel", 800), ("Entertainment", 110),
        ("Software", 25), ("Home Improvement", 200),
        ("HSA", 692), ("Education Savings", 500),
    ]
    budget_objects = []
    for month_offset in range(12):
        # Exact month arithmetic to avoid duplicate (year, month) pairs
        y = TODAY.year
        m = TODAY.month - month_offset
        while m <= 0:
            m += 12
            y -= 1
        for cat, amt in budget_categories:
            budget_objects.append(Budget(
                year=y, month=m, category=cat,
                segment="personal", budget_amount=amt,
            ))
    session.add_all(budget_objects)
    counts["budgets"] = len(budget_objects)

    # ── 9. Recurring Transactions ─────────────────────────────────────
    recurring_objects = []
    for name, cat, amt, freq, acct_name in RECURRING_ITEMS:
        recurring_objects.append(RecurringTransaction(
            name=name, amount=abs(amt), frequency=freq, category=cat,
            segment="personal", status="active",
            account_id=accounts_map.get(acct_name),
            first_seen_date=_dt(date(2025, 3, 1)),
            last_seen_date=_dt(TODAY - timedelta(days=5)),
            next_expected_date=_dt(TODAY + timedelta(days=25)),
            is_auto_detected=True,
        ))
    session.add_all(recurring_objects)
    counts["recurring_transactions"] = len(recurring_objects)

    # ── 10. Goals ─────────────────────────────────────────────────────
    goals = [
        Goal(name="Emergency Fund", goal_type="savings", target_amount=60_000,
             current_amount=38_000, status="active", monthly_contribution=2_000,
             color="#22c55e", icon="shield",
             description="6 months of expenses"),
        Goal(name="Pay Off Student Loans", goal_type="debt_payoff", target_amount=76_000,
             current_amount=52_000, status="active", monthly_contribution=2_500,
             color="#6366f1", icon="graduation-cap",
             description="Combined federal student loans - Michael & Jessica"),
        Goal(name="Max Tax-Advantaged Accounts", goal_type="tax", target_amount=55_300,
             current_amount=41_500, status="active", monthly_contribution=4_608,
             color="#f59e0b", icon="piggy-bank",
             description="401(k)s + HSA + 529 annual max"),
        Goal(name="Sabbatical Fund", goal_type="savings", target_amount=80_000,
             current_amount=22_000, status="active", monthly_contribution=1_500,
             color="#3b82f6", icon="compass",
             description="1 year mini-retirement at 40"),
    ]
    session.add_all(goals)
    counts["goals"] = len(goals)

    # ── 11. Investment Holdings ────────────────────────────────────────
    holdings = [
        InvestmentHolding(
            account_id=accounts_map["Fidelity 401(k) - Michael"], ticker="VTI",
            name="Vanguard Total Stock Market ETF", asset_class="etf",
            shares=420.0, cost_basis_per_share=208.00, total_cost_basis=87_360,
            current_price=257.54, current_value=108_168,
            unrealized_gain_loss=20_808, unrealized_gain_loss_pct=23.8,
            sector="Broad Market", is_active=True,
        ),
        InvestmentHolding(
            account_id=accounts_map["Fidelity 401(k) - Michael"], ticker="VXUS",
            name="Vanguard Total International Stock ETF", asset_class="etf",
            shares=350.0, cost_basis_per_share=56.50, total_cost_basis=19_775,
            current_price=61.76, current_value=21_616,
            unrealized_gain_loss=1_841, unrealized_gain_loss_pct=9.3,
            sector="International", is_active=True,
        ),
        InvestmentHolding(
            account_id=accounts_map["Vanguard Roth IRA"], ticker="VGT",
            name="Vanguard Information Technology ETF", asset_class="etf",
            shares=85.0, cost_basis_per_share=480.00, total_cost_basis=40_800,
            current_price=542.00, current_value=46_070,
            unrealized_gain_loss=5_270, unrealized_gain_loss_pct=12.9,
            sector="Technology", is_active=True,
        ),
        InvestmentHolding(
            account_id=accounts_map["Vanguard Roth IRA"], ticker="VNQ",
            name="Vanguard Real Estate ETF", asset_class="reit",
            shares=280.0, cost_basis_per_share=82.00, total_cost_basis=22_960,
            current_price=88.00, current_value=24_640,
            unrealized_gain_loss=1_680, unrealized_gain_loss_pct=7.3,
            sector="Real Estate", is_active=True,
        ),
        InvestmentHolding(
            account_id=accounts_map["BlackRock 401(k) - Jessica"], ticker="BND",
            name="Vanguard Total Bond Market ETF", asset_class="bond",
            shares=580.0, cost_basis_per_share=73.50, total_cost_basis=42_630,
            current_price=76.00, current_value=44_080,
            unrealized_gain_loss=1_450, unrealized_gain_loss_pct=3.4,
            sector="Fixed Income", is_active=True,
        ),
        InvestmentHolding(
            account_id=accounts_map["BlackRock 401(k) - Jessica"], ticker="IEMG",
            name="iShares Core MSCI Emerging Markets ETF", asset_class="etf",
            shares=400.0, cost_basis_per_share=50.00, total_cost_basis=20_000,
            current_price=53.50, current_value=21_400,
            unrealized_gain_loss=1_400, unrealized_gain_loss_pct=7.0,
            sector="Emerging Markets", is_active=True,
        ),
        InvestmentHolding(
            account_id=accounts_map["Schwab Brokerage"], ticker="AAPL",
            name="Apple Inc (RSU)", asset_class="stock",
            shares=165.0, cost_basis_per_share=172.00, total_cost_basis=28_380,
            current_price=220.69, current_value=36_414,
            unrealized_gain_loss=8_034, unrealized_gain_loss_pct=28.3,
            sector="Technology", is_active=True,
        ),
        InvestmentHolding(
            account_id=accounts_map["Schwab Brokerage"], ticker="MSFT",
            name="Microsoft Corp", asset_class="stock",
            shares=42.0, cost_basis_per_share=380.00, total_cost_basis=15_960,
            current_price=415.00, current_value=17_430,
            unrealized_gain_loss=1_470, unrealized_gain_loss_pct=9.2,
            sector="Technology", is_active=True,
        ),
    ]
    session.add_all(holdings)
    counts["investment_holdings"] = len(holdings)

    # ── 12. Crypto Holdings ───────────────────────────────────────────
    crypto = [
        CryptoHolding(
            coin_id="bitcoin", symbol="BTC", name="Bitcoin",
            quantity=0.35, cost_basis_per_unit=42_000, total_cost_basis=14_700,
            purchase_date=date(2024, 3, 1),
            current_price=68_500, current_value=23_975,
            unrealized_gain_loss=9_275, price_change_24h_pct=2.1,
            last_price_update=NOW, wallet_or_exchange="Coinbase", is_active=True,
        ),
        CryptoHolding(
            coin_id="ethereum", symbol="ETH", name="Ethereum",
            quantity=4.2, cost_basis_per_unit=2_800, total_cost_basis=11_760,
            purchase_date=date(2024, 6, 15),
            current_price=3_850, current_value=16_170,
            unrealized_gain_loss=4_410, price_change_24h_pct=-0.8,
            last_price_update=NOW, wallet_or_exchange="Coinbase", is_active=True,
        ),
    ]
    session.add_all(crypto)
    counts["crypto_holdings"] = len(crypto)

    # ── 13. Target Allocation ─────────────────────────────────────────
    session.add(TargetAllocation(
        name="Growth Balanced",
        allocation_json=json.dumps({
            "US Stocks": 45, "International Stocks": 20,
            "Bonds": 15, "REITs": 8, "Crypto": 5, "Cash": 7,
        }),
        is_active=True,
    ))

    # ── 14. Retirement Profile ────────────────────────────────────────
    session.add(RetirementProfile(
        name="Michael & Jessica Retirement Plan",
        current_age=33, retirement_age=52, life_expectancy=90,
        current_annual_income=410_000, expected_income_growth_pct=3.5,
        expected_social_security_monthly=3_400, social_security_start_age=67,
        current_retirement_savings=310_000, current_other_investments=54_000,
        monthly_retirement_contribution=5_200,
        employer_match_pct=50, employer_match_limit_pct=6,
        income_replacement_pct=75, healthcare_annual_estimate=20_000,
        current_annual_expenses=195_000, inflation_rate_pct=3.0,
        pre_retirement_return_pct=7.0, post_retirement_return_pct=5.0,
        tax_rate_in_retirement_pct=22.0,
        target_nest_egg=3_500_000, projected_nest_egg_at_retirement=3_800_000,
        retirement_readiness_pct=87.0,
        fire_number=3_500_000, coast_fire_number=920_000,
        earliest_retirement_age=50, is_primary=True, last_computed_at=NOW,
    ))
    counts["retirement_profiles"] = 1

    # ── 15. Equity Grant + Vesting Events ─────────────────────────────
    grant = EquityGrant(
        employer_name="Meridian Technologies", grant_type="RSU",
        grant_date=date(2024, 6, 1),
        total_shares=600, vested_shares=165, unvested_shares=435,
        current_fmv=220.69, ticker="AAPL", is_active=True,
        vesting_schedule_json=json.dumps({
            "type": "4yr_cliff_1yr",
            "cliff_date": "2025-06-01",
            "cliff_shares": 150,
            "quarterly_shares_after_cliff": 37.5,
        }),
    )
    session.add(grant)
    await session.flush()

    vest_events = [
        VestingEvent(grant_id=grant.id, vest_date=date(2025, 6, 1),
                     shares=150, price_at_vest=195.00, status="vested",
                     federal_withholding_pct=22, state_withholding_pct=6.85),
        VestingEvent(grant_id=grant.id, vest_date=date(2025, 9, 1),
                     shares=15, price_at_vest=210.50, status="vested"),
        VestingEvent(grant_id=grant.id, vest_date=date(2026, 3, 1),
                     shares=38, price_at_vest=None, status="upcoming"),
        VestingEvent(grant_id=grant.id, vest_date=date(2026, 6, 1),
                     shares=38, price_at_vest=None, status="upcoming"),
        VestingEvent(grant_id=grant.id, vest_date=date(2026, 9, 1),
                     shares=38, price_at_vest=None, status="upcoming"),
        VestingEvent(grant_id=grant.id, vest_date=date(2026, 12, 1),
                     shares=38, price_at_vest=None, status="upcoming"),
    ]
    session.add_all(vest_events)
    counts["equity_grants"] = 1
    counts["vesting_events"] = len(vest_events)

    # Equity tax projection
    session.add(EquityTaxProjection(
        grant_id=grant.id, tax_year=2026,
        projected_vest_income=75_000, projected_withholding=16_500,
        withholding_gap=9_750, marginal_rate_used=35.0,
        recommendations_json=json.dumps([
            "Set aside $9,750 for the tax underpayment gap",
            "Consider selling on vest to reduce AAPL concentration (currently 10% of portfolio)",
            "Pair with Q4 tax-loss harvesting on VXUS lots",
            "File Q1 estimated payment by April 15",
        ]),
        computed_at=NOW,
    ))

    # ── 16. Tax Items (W-2s) ──────────────────────────────────────────
    doc_michael = Document(
        filename="w2_meridian_2025.pdf", original_path="/demo/w2_meridian_2025.pdf",
        file_type="pdf", document_type="w2", status="completed",
        file_hash="demo_michael_w2_2025", tax_year=2025,
        account_id=accounts_map["Meridian Technologies W-2"],
    )
    doc_jessica = Document(
        filename="w2_blackrock_2025.pdf", original_path="/demo/w2_blackrock_2025.pdf",
        file_type="pdf", document_type="w2", status="completed",
        file_hash="demo_jessica_w2_2025", tax_year=2025,
        account_id=accounts_map["BlackRock W-2"],
    )
    session.add_all([doc_michael, doc_jessica])
    await session.flush()

    tax_items = [
        TaxItem(
            source_document_id=doc_michael.id, tax_year=2025, form_type="w2",
            payer_name="Meridian Technologies", w2_wages=245_000,
            w2_federal_tax_withheld=49_000, w2_ss_wages=168_600,
            w2_ss_tax_withheld=10_453, w2_medicare_wages=245_000,
            w2_medicare_tax_withheld=3_553, w2_state="NY",
            w2_state_wages=245_000, w2_state_income_tax=14_700,
        ),
        TaxItem(
            source_document_id=doc_jessica.id, tax_year=2025, form_type="w2",
            payer_name="BlackRock", w2_wages=165_000,
            w2_federal_tax_withheld=29_700, w2_ss_wages=165_000,
            w2_ss_tax_withheld=10_230, w2_medicare_wages=165_000,
            w2_medicare_tax_withheld=2_393, w2_state="NY",
            w2_state_wages=165_000, w2_state_income_tax=9_900,
        ),
    ]
    session.add_all(tax_items)
    counts["tax_items"] = len(tax_items)

    # ── 17. Tax Strategies ────────────────────────────────────────────
    strategies = [
        TaxStrategy(
            tax_year=2025, priority=1, title="Mega Backdoor Roth",
            description="Michael's Meridian Technologies plan allows after-tax 401(k) contributions up to $69,000. Convert to Roth for tax-free growth on an additional $22,500.",
            strategy_type="retirement", category="quick_win", complexity="medium",
            estimated_savings_low=9_200, estimated_savings_high=13_800,
            action_required="Contact Fidelity to set up after-tax contributions and automatic Roth conversion",
            confidence=0.92, generated_at=NOW,
        ),
        TaxStrategy(
            tax_year=2025, priority=2, title="Tax-Loss Harvest Q4",
            description="International holdings (VXUS) have unrealized losses in certain tax lots. Harvest to offset RSU vest gains.",
            strategy_type="investment", category="quick_win", complexity="low",
            estimated_savings_low=1_400, estimated_savings_high=2_100,
            action_required="Review VXUS lots in Schwab. Sell loss lots, repurchase similar (not identical) fund after 30 days.",
            confidence=0.88, generated_at=NOW,
        ),
        TaxStrategy(
            tax_year=2025, priority=2, title="Donor Advised Fund",
            description="Contribute appreciated AAPL shares to a DAF. Deduct fair market value, avoid capital gains on $8K+ gain.",
            strategy_type="deduction", category="this_year", complexity="low",
            estimated_savings_low=3_800, estimated_savings_high=5_600,
            action_required="Open DAF at Fidelity Charitable. Contribute 50-80 AAPL shares before year-end.",
            confidence=0.85, generated_at=NOW,
        ),
        TaxStrategy(
            tax_year=2025, priority=3, title="RSU Timing Optimization",
            description="$75K in RSU vests this year at 35% marginal rate. Withholding gap of ~$9.75K. Plan estimated payments.",
            strategy_type="timing", category="this_year", complexity="medium",
            estimated_savings_low=3_000, estimated_savings_high=4_500,
            action_required="File Q1 estimated payment by April 15. Adjust W-4 withholding for remainder of year.",
            confidence=0.90, generated_at=NOW,
        ),
        TaxStrategy(
            tax_year=2025, priority=3, title="529 NY State Tax Deduction",
            description="NY allows $10K/couple deduction for 529 contributions. At 6.85% marginal state rate, that's $685 saved.",
            strategy_type="deduction", category="quick_win", complexity="low",
            estimated_savings_low=685, estimated_savings_high=685,
            action_required="Ensure $10K total 529 contributions by Dec 31 to maximize NY deduction.",
            confidence=0.95, generated_at=NOW,
        ),
    ]
    session.add_all(strategies)
    counts["tax_strategies"] = len(strategies)

    # ── 18. Tax Projection ────────────────────────────────────────────
    session.add(TaxProjection(
        name="2025 Current Estimate",
        tax_year=2025,
        scenario_json=json.dumps({
            "w2_income_michael": 245_000,
            "w2_income_jessica": 165_000,
            "consulting_income": 42_000,
            "rsu_income": 32_000,
            "filing_status": "mfj",
            "state": "NY",
        }),
        federal_tax=82_400, state_tax=32_200, fica=27_600,
        niit=0, amt=0,
        total_tax=142_200, effective_rate=29.4, marginal_rate=35.0,
        credits_json=json.dumps([
            {"name": "Child Tax Credit", "amount": 2000},
            {"name": "Dependent Care Credit", "amount": 600},
        ]),
        deductions_json=json.dumps([
            {"name": "Standard Deduction (MFJ)", "amount": 30950},
            {"name": "401(k) Contributions", "amount": 47000},
            {"name": "HSA Contribution", "amount": 8300},
        ]),
    ))
    counts["tax_projections"] = 1

    # ── 19. Household Optimization ────────────────────────────────────
    session.add(HouseholdOptimization(
        household_id=hh_id, tax_year=2025,
        optimal_filing_status="mfj",
        mfj_tax=114_600, mfs_tax=119_800, filing_savings=5_200,
        total_annual_savings=29_650,
        recommendations_json=json.dumps([
            {"area": "Filing Status", "action": "MFJ saves $5,200 vs MFS", "savings": 5200},
            {"area": "401(k) Coordination", "action": "Max both 401(k)s — $47K combined", "savings": 16450},
            {"area": "Health Insurance", "action": "Use Meridian HDHP + HSA ($8,300 limit)", "savings": 3200},
            {"area": "Childcare FSA", "action": "Elect Dependent Care FSA ($5K)", "savings": 1750},
            {"area": "529 NY Deduction", "action": "Contribute $10K to NY 529", "savings": 685},
            {"area": "Mega Backdoor Roth", "action": "After-tax 401(k) → Roth conversion", "savings": 2365},
        ]),
        computed_at=NOW,
    ))

    # ── 20. Insurance Policies ────────────────────────────────────────
    policies = [
        InsurancePolicy(household_id=hh_id, policy_type="health", provider="Aetna",
                        annual_premium=5_760, monthly_premium=480,
                        deductible=3_000, oop_max=7_500, employer_provided=True,
                        owner_spouse="A", is_active=True),
        InsurancePolicy(household_id=hh_id, policy_type="life", provider="Northwestern Mutual",
                        coverage_amount=1_500_000, annual_premium=1_020,
                        monthly_premium=85, owner_spouse="A", is_active=True),
        InsurancePolicy(household_id=hh_id, policy_type="life", provider="Haven Life",
                        coverage_amount=1_000_000, annual_premium=780,
                        monthly_premium=65, owner_spouse="B", is_active=True),
        InsurancePolicy(household_id=hh_id, policy_type="disability", provider="Meridian Technologies",
                        coverage_amount=163_000, annual_premium=0,
                        employer_provided=True, owner_spouse="A", is_active=True),
        InsurancePolicy(household_id=hh_id, policy_type="auto", provider="Progressive",
                        annual_premium=4_560, monthly_premium=380,
                        deductible=500, is_active=True),
        InsurancePolicy(household_id=hh_id, policy_type="umbrella", provider="Allstate",
                        coverage_amount=2_000_000, annual_premium=540,
                        is_active=True),
    ]
    session.add_all(policies)
    counts["insurance_policies"] = len(policies)

    # ── 21. Life Events ───────────────────────────────────────────────
    events = [
        LifeEvent(household_id=hh_id, event_type="marriage", title="Married Jessica",
                  event_date=date(2021, 10, 16), tax_year=2021, status="completed",
                  notes="Updated filing status to MFJ"),
        LifeEvent(household_id=hh_id, event_type="child", title="Ethan born",
                  event_date=date(2023, 5, 18), tax_year=2023, status="completed",
                  amounts_json=json.dumps({"childcare_annual": 28_800})),
        LifeEvent(household_id=hh_id, event_type="home_purchase", title="Bought first home",
                  event_date=date(2023, 9, 1), tax_year=2023, status="completed",
                  amounts_json=json.dumps({"purchase_price": 520_000, "down_payment": 104_000})),
        LifeEvent(household_id=hh_id, event_type="job_change",
                  title="Michael joined Meridian Technologies",
                  event_date=date(2024, 1, 15), tax_year=2024, status="completed",
                  notes="$45K raise + 600-share RSU grant"),
        LifeEvent(household_id=hh_id, event_type="business_start",
                  title="Started consulting LLC",
                  event_date=date(2024, 1, 1), tax_year=2024, status="completed",
                  notes="Chen Digital Consulting LLC — architecture advisory"),
    ]
    session.add_all(events)
    counts["life_events"] = len(events)

    # ── 22. Net Worth Snapshots (24 months) ──────────────────────────
    nw_data = [
        (2024, 4, 165_000), (2024, 5, 172_000), (2024, 6, 180_000),
        (2024, 7, 188_000), (2024, 8, 183_000), (2024, 9, 195_000),
        (2024, 10, 208_000), (2024, 11, 220_000), (2024, 12, 235_000),
        (2025, 1, 242_000), (2025, 2, 250_000), (2025, 3, 262_000),
        (2025, 4, 285_000), (2025, 5, 296_000), (2025, 6, 308_000),
        (2025, 7, 318_000), (2025, 8, 312_000), (2025, 9, 325_000),
        (2025, 10, 338_000), (2025, 11, 350_000), (2025, 12, 362_000),
        (2026, 1, 370_000), (2026, 2, 382_000), (2026, 3, 395_000),
    ]
    snapshots = []
    for yr, mo, nw in nw_data:
        total_liabilities = 468_000 - (395_000 - nw) * 0.3  # Mortgage + student loans declining
        total_assets = nw + total_liabilities
        snapshots.append(NetWorthSnapshot(
            snapshot_date=_dt(date(yr, mo, 28)),
            year=yr, month=mo, net_worth=nw,
            total_assets=total_assets, total_liabilities=total_liabilities,
            checking_savings=52_000 + (nw - 285_000) * 0.15,
            investment_value=320_000 + (nw - 285_000) * 0.7,
            real_estate_value=580_000,
            credit_card_debt=round(random.Random(yr * 100 + mo).uniform(3000, 7000)),
            loan_balance=round(total_liabilities - 392_000),
        ))
    session.add_all(snapshots)
    counts["net_worth_snapshots"] = len(snapshots)

    # ── 23. Portfolio Snapshots (24 months) ──────────────────────────
    portfolio_snapshots = []
    base_portfolio = 180_000
    for i, (yr, mo, _) in enumerate(nw_data):
        pv = round(base_portfolio + i * 8500 + random.Random(yr * 100 + mo).uniform(-5000, 5000))
        portfolio_snapshots.append(PortfolioSnapshot(
            snapshot_date=date(yr, mo, 28),
            total_stock_value=round(pv * 0.30),
            total_etf_value=round(pv * 0.52),
            total_bond_value=round(pv * 0.12),
            total_crypto_value=round(pv * 0.06),
            total_other_value=0,
            total_portfolio_value=pv,
            total_cost_basis=round(pv * 0.85),
            total_unrealized_gain_loss=round(pv * 0.15),
            day_change=round(random.Random(yr * 1000 + mo).uniform(-3000, 4000), 2),
            day_change_pct=round(random.Random(yr * 1000 + mo + 1).uniform(-1.2, 1.5), 2),
            allocation_by_sector=json.dumps({
                "Technology": 35, "Broad Market": 25,
                "International": 15, "Fixed Income": 12,
                "Real Estate": 8, "Crypto": 5,
            }),
            allocation_by_asset_class=json.dumps({
                "ETF": 52, "Stock": 30, "Bond": 12, "Crypto": 6,
            }),
            top_holdings=json.dumps([
                {"ticker": "VTI", "value": round(pv * 0.28)},
                {"ticker": "VGT", "value": round(pv * 0.12)},
                {"ticker": "BND", "value": round(pv * 0.12)},
                {"ticker": "AAPL", "value": round(pv * 0.10)},
                {"ticker": "VXUS", "value": round(pv * 0.06)},
            ]),
        ))
    session.add_all(portfolio_snapshots)
    counts["portfolio_snapshots"] = len(portfolio_snapshots)

    # ── 24. Financial Periods (12 months) ─────────────────────────────
    await session.execute(text("DELETE FROM financial_periods"))
    periods = []
    for yr, mo, _ in nw_data:
        biz_income = round(random.Random(yr * 100 + mo + 5).uniform(2000, 8000))
        periods.append(FinancialPeriod(
            year=yr, month=mo, segment="all",
            total_income=31_532 + biz_income,
            total_expenses=24_800,
            net_cash_flow=31_532 + biz_income - 24_800,
            w2_income=31_532,
            personal_expenses=24_800,
            computed_at=_dt(date(yr, mo, 28)),
        ))
    session.add_all(periods)
    counts["financial_periods"] = len(periods)

    # ── 25. Life Scenarios ────────────────────────────────────────────
    scenarios = [
        LifeScenario(
            name="Upgrade to $1.2M Home",
            scenario_type="home_purchase",
            parameters=json.dumps({
                "purchase_price": 1_200_000, "down_payment_pct": 20,
                "mortgage_rate": 6.5, "term_years": 30,
            }),
            annual_income=410_000, monthly_take_home=26_500,
            current_monthly_expenses=24_800,
            current_savings=52_000, current_investments=364_000,
            total_cost=1_200_000, new_monthly_payment=6_080,
            monthly_surplus_after=1_620,
            savings_rate_before_pct=18.5, savings_rate_after_pct=6.1,
            dti_before_pct=28.0, dti_after_pct=38.0,
            affordability_score=62.0, verdict="stretch",
            results_detail=json.dumps({
                "monthly_mortgage": 6080, "property_tax_monthly": 1200,
                "retirement_delay_years": 5,
            }),
            ai_analysis="Upgrading to a $1.2M home is technically affordable but pushes your DTI to 38% and delays retirement from 52 to 57. Your savings rate drops to 6.1%, well below the 15% HENRY target. Consider waiting 2-3 years to build more equity.",
            status="completed", is_favorite=True,
        ),
        LifeScenario(
            name="Second Child Impact",
            scenario_type="family_change",
            parameters=json.dumps({
                "additional_childcare": 28_800, "additional_healthcare": 3_600,
                "additional_misc": 6_000,
            }),
            annual_income=410_000, monthly_take_home=26_500,
            current_monthly_expenses=24_800,
            current_savings=52_000, current_investments=364_000,
            total_cost=38_400, new_monthly_payment=3_200,
            monthly_surplus_after=650,
            savings_rate_before_pct=18.5, savings_rate_after_pct=2.5,
            dti_before_pct=28.0, dti_after_pct=28.0,
            affordability_score=58.0, verdict="tight",
            ai_analysis="A second child adds ~$3,200/mo in expenses. Your savings rate drops to 2.5% — effectively pausing wealth building for 3-4 years. Consider negotiating a raise or increasing consulting income to maintain $4K+/mo savings.",
            status="completed", is_favorite=False,
        ),
        LifeScenario(
            name="Jessica Goes Part-Time",
            scenario_type="career_change",
            parameters=json.dumps({
                "new_income": 82_500, "income_reduction": 82_500,
            }),
            annual_income=327_500, monthly_take_home=21_200,
            current_monthly_expenses=24_800,
            current_savings=52_000, current_investments=364_000,
            total_cost=0, new_monthly_payment=0,
            monthly_surplus_after=-3_600,
            savings_rate_before_pct=18.5, savings_rate_after_pct=-17.0,
            dti_before_pct=28.0, dti_after_pct=35.0,
            affordability_score=35.0, verdict="not_feasible",
            ai_analysis="Going part-time creates a $3,600/mo deficit. You'd need to cut $3,600 in monthly expenses or increase Michael's consulting income to $12K+/mo to break even. This is not sustainable without significant lifestyle changes.",
            status="completed", is_favorite=False,
        ),
    ]
    session.add_all(scenarios)
    counts["life_scenarios"] = len(scenarios)

    # ── 26. Category Rules ────────────────────────────────────────────
    rules = [
        CategoryRule(merchant_pattern="WHOLE FOODS", category="Groceries",
                     segment="personal", source="ai_generated", match_count=24, is_active=True),
        CategoryRule(merchant_pattern="TRADER JOE", category="Groceries",
                     segment="personal", source="ai_generated", match_count=18, is_active=True),
        CategoryRule(merchant_pattern="COSTCO", category="Groceries",
                     segment="personal", source="ai_generated", match_count=12, is_active=True),
        CategoryRule(merchant_pattern="DOORDASH", category="Food & Dining",
                     segment="personal", source="ai_generated", match_count=15, is_active=True),
        CategoryRule(merchant_pattern="STARBUCKS", category="Coffee & Tea",
                     segment="personal", source="ai_generated", match_count=30, is_active=True),
        CategoryRule(merchant_pattern="AWS", category="Cloud Services",
                     segment="business", source="user_override", match_count=12,
                     business_entity_id=biz_id, is_active=True),
        CategoryRule(merchant_pattern="VERCEL", category="Cloud Services",
                     segment="business", source="user_override", match_count=12,
                     business_entity_id=biz_id, is_active=True),
        CategoryRule(merchant_pattern="GITHUB", category="Software",
                     segment="business", source="user_override", match_count=12,
                     business_entity_id=biz_id, is_active=True),
        CategoryRule(merchant_pattern="EQUINOX", category="Fitness",
                     segment="personal", source="ai_generated", match_count=12, is_active=True),
        CategoryRule(merchant_pattern="PROGRESSIVE", category="Insurance",
                     segment="personal", source="ai_generated", match_count=12, is_active=True),
        CategoryRule(merchant_pattern="NETFLIX", category="Entertainment",
                     segment="personal", source="ai_generated", match_count=12, is_active=True),
        CategoryRule(merchant_pattern="BRIGHT HORIZONS", category="Childcare",
                     segment="personal", source="user_override", match_count=12, is_active=True),
    ]
    session.add_all(rules)
    counts["category_rules"] = len(rules)

    # ── 27. Chat Conversation ─────────────────────────────────────────
    convo = ChatConversation(title="Tax & RSU Planning", created_at=NOW)
    session.add(convo)
    await session.flush()

    messages = [
        ChatMessage(conversation_id=convo.id, role="user",
                    content="My RSUs vest next month. What should I do to minimize the tax hit?",
                    created_at=NOW - timedelta(hours=2)),
        ChatMessage(conversation_id=convo.id, role="assistant",
                    content="Your March vest is 38 shares at ~$220.69/share = **$8,386 in ordinary income**. At your 35% marginal rate, that's about $2,935 in taxes — but withholding only covers $1,845. Here's what I recommend:\n\n1. **Set aside $1,090 now** for the withholding gap\n2. **Consider selling on vest** to reduce your AAPL concentration (currently 10% of portfolio)\n3. **Pair with tax-loss harvesting** — you have $2,100 in harvestable VXUS losses that could offset the gain\n4. **Update your W-4** to increase withholding for the remaining 3 quarterly vests\n\nWant me to run a scenario comparing hold vs. sell?",
                    actions_json=json.dumps([
                        {"tool": "equity_vest_lookup", "status": "completed"},
                        {"tool": "tax_estimate", "status": "completed"},
                    ]),
                    created_at=NOW - timedelta(hours=1, minutes=59)),
        ChatMessage(conversation_id=convo.id, role="user",
                    content="Should we file MFJ or MFS this year?",
                    created_at=NOW - timedelta(hours=1)),
        ChatMessage(conversation_id=convo.id, role="assistant",
                    content="**MFJ saves you $5,200 this year.** Here's the breakdown:\n\n| Filing Status | Federal Tax | State Tax | Total |\n|---|---|---|---|\n| MFJ | $82,400 | $32,200 | $114,600 |\n| MFS | $87,000 | $32,800 | $119,800 |\n\nMFS only makes sense if you're pursuing income-driven student loan repayment — but at your combined $410K income, you won't qualify for meaningful IDR savings. Your consulting Schedule C income actually makes MFJ even more beneficial because of the QBI deduction. Stick with MFJ.",
                    actions_json=json.dumps([
                        {"tool": "filing_status_compare", "status": "completed"},
                        {"tool": "household_optimization", "status": "completed"},
                    ]),
                    created_at=NOW - timedelta(minutes=59)),
    ]
    session.add_all(messages)
    counts["chat_messages"] = len(messages)

    # ── 28. Vendor Entity Rules ─────────────────────────────────────
    vendor_rules = [
        VendorEntityRule(vendor_pattern="AWS", business_entity_id=biz_id,
                         segment_override="business", priority=10, is_active=True),
        VendorEntityRule(vendor_pattern="VERCEL", business_entity_id=biz_id,
                         segment_override="business", priority=10, is_active=True),
        VendorEntityRule(vendor_pattern="GITHUB", business_entity_id=biz_id,
                         segment_override="business", priority=10, is_active=True),
        VendorEntityRule(vendor_pattern="FIGMA", business_entity_id=biz_id,
                         segment_override="business", priority=10, is_active=True),
        VendorEntityRule(vendor_pattern="WEWORK", business_entity_id=biz_id,
                         segment_override="business", priority=5, is_active=True),
        VendorEntityRule(vendor_pattern="LINKEDIN PREMIUM", business_entity_id=biz_id,
                         segment_override="business", priority=5, is_active=True),
    ]
    session.add_all(vendor_rules)
    counts["vendor_entity_rules"] = len(vendor_rules)

    # ── 29. User Context (AI personalization) ─────────────────────────
    user_contexts = [
        UserContext(category="career", key="primary_employer",
                    value="Michael is a Senior Software Engineer at Meridian Technologies, earning $245K + RSUs",
                    source="chat", confidence=1.0),
        UserContext(category="career", key="spouse_employer",
                    value="Jessica is a Finance Manager at BlackRock, earning $165K + ESPP",
                    source="chat", confidence=1.0),
        UserContext(category="business", key="consulting_llc",
                    value="Michael runs Chen Digital Consulting LLC on the side — software architecture advisory, ~$4K/mo average",
                    source="chat", confidence=1.0),
        UserContext(category="financial_goal", key="retirement_target",
                    value="Target early retirement at 52 (FIRE). Both want to take a 1-year sabbatical at 40.",
                    source="chat", confidence=0.95),
        UserContext(category="tax", key="tax_preference",
                    value="Aggressive but legal tax optimization. Open to mega backdoor Roth, DAF, and tax-loss harvesting.",
                    source="chat", confidence=0.90),
        UserContext(category="household", key="child_plans",
                    value="Considering a second child in 2027. Want to understand the financial impact first.",
                    source="chat", confidence=0.85),
        UserContext(category="investment", key="risk_tolerance",
                    value="Moderate-aggressive. Comfortable with 80/20 stock/bond allocation. Small crypto allocation (5%) as asymmetric bet.",
                    source="inferred", confidence=0.88),
        UserContext(category="preference", key="communication_style",
                    value="Prefers data-driven recommendations with specific dollar amounts. Likes tables and comparisons.",
                    source="inferred", confidence=0.80),
    ]
    session.add_all(user_contexts)
    counts["user_contexts"] = len(user_contexts)

    # ── 30. Privacy Consents ──────────────────────────────────────────
    consents = [
        UserPrivacyConsent(consent_type="ai_features", consented=True,
                           consented_at=NOW - timedelta(days=30)),
        UserPrivacyConsent(consent_type="plaid_sync", consented=True,
                           consented_at=NOW - timedelta(days=30)),
    ]
    session.add_all(consents)

    # ── 31. Set demo mode flag ────────────────────────────────────────
    session.add(AppSettings(key="demo_mode", value="true"))

    await session.flush()
    logger.info(f"Demo data seeded: {counts}")
    return counts


async def reset_demo_data(session: AsyncSession) -> None:
    """Clear ALL data from all tables. Uses metadata for automatic coverage."""
    # SAFETY: Verify we're operating on a demo database, NEVER the user's real data.
    bind = session.get_bind()
    db_url = str(bind.url) if bind else ""
    if "demo" not in db_url.lower():
        raise RuntimeError(
            f"ABORT: reset_demo_data refused to operate on non-demo database: {db_url}"
        )
    # Disable FK checks for clean truncation order
    await session.execute(text("PRAGMA foreign_keys = OFF"))
    for table in reversed(Base.metadata.sorted_tables):
        await session.execute(table.delete())
    # Also clear any tables not in ORM metadata (e.g., raw-SQL-created tables)
    result = await session.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' AND name != '_schema_migrations'"
    ))
    db_tables = {row[0] for row in result}
    orm_tables = {t.name for t in Base.metadata.sorted_tables}
    for extra_table in db_tables - orm_tables:
        await session.execute(text(f'DELETE FROM "{extra_table}"'))
    await session.execute(text("PRAGMA foreign_keys = ON"))
    await session.flush()
    logger.info("All data cleared.")


async def get_demo_status(session: AsyncSession) -> dict:
    """Check whether the app is in demo mode."""
    result = await session.execute(
        text("SELECT value FROM app_settings WHERE key = 'demo_mode'")
    )
    row = result.scalar_one_or_none()
    active = row == "true" if row else False

    profile_name = None
    if active:
        hp = await session.scalar(select(HouseholdProfile).limit(1))
        if hp:
            profile_name = hp.name

    return {"active": active, "profile_name": profile_name}
