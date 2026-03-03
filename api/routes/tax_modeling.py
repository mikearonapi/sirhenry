"""Tax strategy modeling endpoints — interactive Roth, S-Corp, multi-year, student loan analysis."""
import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from pipeline.planning.tax_modeling import TaxModelingEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tax/model", tags=["tax-modeling"])


class RothConversionIn(BaseModel):
    traditional_balance: float
    current_income: float
    filing_status: str = "mfj"
    years: int = 10
    target_bracket_rate: float = 0.24
    growth_rate: float = 0.07


class BackdoorRothIn(BaseModel):
    has_traditional_ira_balance: bool = False
    traditional_ira_balance: float = 0
    income: float = 0
    filing_status: str = "mfj"


class MegaBackdoorIn(BaseModel):
    employer_plan_allows: bool = True
    current_employee_contrib: float = 23500
    employer_match_contrib: float = 10000
    plan_limit: float = 69000


class DAFBunchingIn(BaseModel):
    annual_charitable: float
    standard_deduction: float = 30000
    itemized_deductions_excl_charitable: float = 15000
    bunch_years: int = 2
    filing_status: str = "mfj"
    taxable_income: float = 300_000


class SCorpIn(BaseModel):
    gross_1099_income: float
    reasonable_salary: float
    business_expenses: float = 0
    state: str = "CA"
    filing_status: str = "mfj"


class MultiYearIn(BaseModel):
    current_income: float
    income_growth_rate: float = 0.03
    filing_status: str = "mfj"
    state_rate: float = 0.093
    years: int = 5
    roth_conversions: Optional[list[float]] = None
    equity_vesting: Optional[list[float]] = None


class EstimatedPaymentsIn(BaseModel):
    total_underwithholding: float
    prior_year_tax: float = 0
    current_withholding: float = 0


class StudentLoanIn(BaseModel):
    loan_balance: float
    interest_rate: float
    monthly_income: float
    filing_status: str = "mfj"
    pslf_eligible: bool = False


@router.post("/roth-conversion")
async def roth_conversion(body: RothConversionIn):
    return TaxModelingEngine.roth_conversion_ladder(
        body.traditional_balance, body.current_income, body.filing_status,
        body.years, body.target_bracket_rate, body.growth_rate,
    )

@router.post("/backdoor-roth")
async def backdoor_roth(body: BackdoorRothIn):
    return TaxModelingEngine.backdoor_roth_checklist(
        body.has_traditional_ira_balance, body.traditional_ira_balance,
        body.income, body.filing_status,
    )

@router.post("/mega-backdoor")
async def mega_backdoor(body: MegaBackdoorIn):
    return TaxModelingEngine.mega_backdoor_roth_analysis(
        body.employer_plan_allows, body.current_employee_contrib,
        body.employer_match_contrib, body.plan_limit,
    )

@router.post("/daf-bunching")
async def daf_bunching(body: DAFBunchingIn):
    return TaxModelingEngine.daf_bunching_strategy(
        body.annual_charitable, body.standard_deduction,
        body.itemized_deductions_excl_charitable, body.bunch_years,
        body.filing_status, body.taxable_income,
    )

@router.post("/scorp")
async def scorp_model(body: SCorpIn):
    return TaxModelingEngine.scorp_election_model(
        body.gross_1099_income, body.reasonable_salary,
        body.business_expenses, body.state, body.filing_status,
    )

@router.post("/multi-year")
async def multi_year(body: MultiYearIn):
    return TaxModelingEngine.multi_year_projection(
        body.current_income, body.income_growth_rate, body.filing_status,
        body.state_rate, body.years, body.roth_conversions, body.equity_vesting,
    )

@router.post("/estimated-payments")
async def estimated_payments(body: EstimatedPaymentsIn):
    return TaxModelingEngine.estimated_payment_calculator(
        body.total_underwithholding, body.prior_year_tax, body.current_withholding,
    )

@router.post("/student-loan")
async def student_loan(body: StudentLoanIn):
    return TaxModelingEngine.student_loan_optimizer(
        body.loan_balance, body.interest_rate, body.monthly_income,
        body.filing_status, body.pslf_eligible,
    )
