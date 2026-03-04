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


class DefinedBenefitIn(BaseModel):
    self_employment_income: float
    age: int
    target_retirement_age: int = 65
    filing_status: str = "mfj"
    existing_retirement_contrib: float = 0


class RealEstateSTRIn(BaseModel):
    property_value: float
    annual_rental_income: float
    average_stay_days: float
    hours_per_week_managing: float
    w2_income: float
    filing_status: str = "mfj"
    land_value_pct: float = 0.20


@router.post("/defined-benefit")
async def defined_benefit(body: DefinedBenefitIn):
    return TaxModelingEngine.defined_benefit_plan_analysis(
        body.self_employment_income, body.age, body.target_retirement_age,
        body.filing_status, body.existing_retirement_contrib,
    )


@router.post("/real-estate-str")
async def real_estate_str(body: RealEstateSTRIn):
    return TaxModelingEngine.real_estate_str_analysis(
        body.property_value, body.annual_rental_income, body.average_stay_days,
        body.hours_per_week_managing, body.w2_income, body.filing_status,
        body.land_value_pct,
    )


class FilingStatusCompareIn(BaseModel):
    spouse_a_income: float
    spouse_b_income: float
    investment_income: float = 0
    itemized_deductions: float = 0
    student_loan_payment: float = 0
    state: str = "CA"


@router.post("/filing-status-compare")
async def filing_status_compare(body: FilingStatusCompareIn):
    return TaxModelingEngine.filing_status_comparison(
        body.spouse_a_income, body.spouse_b_income,
        body.investment_income, body.itemized_deductions,
        body.student_loan_payment, body.state,
    )


class Section179In(BaseModel):
    equipment_cost: float
    business_income: float
    filing_status: str = "mfj"
    equipment_category: str = "excavators"
    equipment_index: int = 0
    business_use_pct: float = 1.0
    will_rent_out: bool = True
    has_existing_business: bool = True


@router.post("/section-179")
async def section_179(body: Section179In):
    return TaxModelingEngine.section_179_equipment_analysis(
        body.equipment_cost, body.business_income, body.filing_status,
        body.equipment_category, body.equipment_index,
        body.business_use_pct, body.will_rent_out, body.has_existing_business,
    )


class QBIDeductionIn(BaseModel):
    qbi_income: float
    taxable_income: float
    w2_wages_paid: float = 0
    qualified_property: float = 0
    filing_status: str = "mfj"
    is_sstb: bool = False


@router.post("/qbi-deduction")
async def qbi_deduction(body: QBIDeductionIn):
    return TaxModelingEngine.qbi_deduction_check(
        body.qbi_income, body.taxable_income, body.w2_wages_paid,
        body.qualified_property, body.filing_status, body.is_sstb,
    )


class StateComparisonIn(BaseModel):
    income: float
    filing_status: str = "mfj"
    current_state: str = "CA"
    comparison_states: Optional[list[str]] = None


@router.post("/state-comparison")
async def state_comparison(body: StateComparisonIn):
    return TaxModelingEngine.state_tax_comparison(
        body.income, body.filing_status, body.current_state,
        body.comparison_states,
    )
