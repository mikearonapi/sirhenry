"""
Tests for the tax pipeline modules:
- pipeline/tax/tax_estimate.py (compute_tax_estimate)
- pipeline/tax/deductions.py (compute_deduction_opportunities)
- pipeline/tax/tax_summary.py (get_tax_summary_with_fallback)

These tests verify the full DB-to-computation chain: seed the in-memory
SQLite with realistic tax data, then assert the pipeline produces correct
estimates, deduction opportunities, and data-source fallback behavior.
"""
import json
import hashlib
import pytest
from datetime import date, datetime, timezone

from pipeline.db.schema import (
    Account,
    BenefitPackage,
    Document,
    HouseholdProfile,
    LifeEvent,
    TaxItem,
    Transaction,
)
from pipeline.db.models import (
    create_tax_item,
    get_tax_summary,
)
from pipeline.tax.tax_estimate import compute_tax_estimate
from pipeline.tax.deductions import compute_deduction_opportunities
from pipeline.tax.tax_summary import get_tax_summary_with_fallback


# ============================================================================
# Helper fixtures
# ============================================================================


@pytest.fixture
def _doc_counter():
    """Shared counter for unique document hashes."""
    return [0]


async def _make_doc(session, _doc_counter, document_type="w2", tax_year=2025):
    """Utility to create a Document with a unique hash."""
    _doc_counter[0] += 1
    doc = Document(
        filename=f"test_{document_type}_{_doc_counter[0]}.pdf",
        original_path=f"/tmp/test_{_doc_counter[0]}.pdf",
        file_type="pdf",
        document_type=document_type,
        status="completed",
        file_hash=hashlib.sha256(f"doc-{_doc_counter[0]}-{document_type}".encode()).hexdigest(),
        tax_year=tax_year,
    )
    session.add(doc)
    await session.flush()
    return doc


@pytest.fixture
async def household_profile(session):
    """Create a primary HouseholdProfile for MFJ filers."""
    hp = HouseholdProfile(
        name="Test Household",
        filing_status="mfj",
        state="CA",
        spouse_a_name="Alice",
        spouse_a_income=150000.0,
        spouse_b_name="Bob",
        spouse_b_income=130000.0,
        combined_income=280000.0,
        other_income_annual=0.0,
        is_primary=True,
    )
    session.add(hp)
    await session.flush()
    return hp


@pytest.fixture
async def household_with_other_income(session):
    """Household with other income sources (1099, dividends)."""
    hp = HouseholdProfile(
        name="Test Household 2",
        filing_status="mfj",
        state="CA",
        spouse_a_name="Carol",
        spouse_a_income=100000.0,
        spouse_b_name="Dave",
        spouse_b_income=80000.0,
        combined_income=180000.0,
        other_income_annual=60000.0,
        other_income_sources_json=json.dumps([
            {"type": "business_1099", "amount": 40000, "description": "Consulting"},
            {"type": "dividends_1099", "amount": 10000, "description": "Brokerage dividends"},
            {"type": "rental", "amount": 10000, "description": "Rental property"},
        ]),
        is_primary=True,
    )
    session.add(hp)
    await session.flush()
    return hp


# ============================================================================
# compute_tax_estimate — document-sourced income
# ============================================================================


@pytest.mark.asyncio
async def test_tax_estimate_from_documents(session, _doc_counter):
    """compute_tax_estimate should use document data when W-2 items exist."""
    hp = HouseholdProfile(
        name="Doc Household",
        filing_status="mfj",
        state="CA",
        spouse_a_income=0.0,
        spouse_b_income=0.0,
        is_primary=True,
    )
    session.add(hp)
    await session.flush()

    doc = await _make_doc(session, _doc_counter, "w2")
    await create_tax_item(session, {
        "source_document_id": doc.id,
        "tax_year": 2025,
        "form_type": "w2",
        "w2_wages": 200000.0,
        "w2_federal_tax_withheld": 35000.0,
    })
    await session.flush()

    estimate = await compute_tax_estimate(session, 2025)

    assert estimate["data_source"] == "documents"
    assert estimate["tax_year"] == 2025
    assert estimate["filing_status"] == "mfj"
    assert estimate["estimated_agi"] > 0
    assert estimate["total_estimated_tax"] > 0
    assert estimate["w2_federal_already_withheld"] == 35000.0


@pytest.mark.asyncio
async def test_tax_estimate_with_self_employment(session, _doc_counter):
    """SE income from 1099-NEC should trigger SE tax calculation."""
    hp = HouseholdProfile(
        name="SE Household",
        filing_status="single",
        state="TX",
        spouse_a_income=0.0,
        spouse_b_income=0.0,
        is_primary=True,
    )
    session.add(hp)
    await session.flush()

    doc_w2 = await _make_doc(session, _doc_counter, "w2")
    doc_nec = await _make_doc(session, _doc_counter, "1099_nec")

    await create_tax_item(session, {
        "source_document_id": doc_w2.id,
        "tax_year": 2025,
        "form_type": "w2",
        "w2_wages": 120000.0,
        "w2_federal_tax_withheld": 20000.0,
    })
    await create_tax_item(session, {
        "source_document_id": doc_nec.id,
        "tax_year": 2025,
        "form_type": "1099_nec",
        "nec_nonemployee_compensation": 50000.0,
    })
    await session.flush()

    estimate = await compute_tax_estimate(session, 2025)

    assert estimate["data_source"] == "documents"
    assert estimate["self_employment_income"] == 50000.0
    assert estimate["self_employment_tax"] > 0  # SE tax should be nonzero
    assert estimate["filing_status"] == "single"


@pytest.mark.asyncio
async def test_tax_estimate_with_investment_income(session, _doc_counter):
    """Investment income (1099-DIV, 1099-INT, 1099-B) should be included in AGI."""
    hp = HouseholdProfile(
        name="Investor HH",
        filing_status="mfj",
        state="NY",
        spouse_a_income=0.0,
        spouse_b_income=0.0,
        is_primary=True,
    )
    session.add(hp)
    await session.flush()

    doc_w2 = await _make_doc(session, _doc_counter, "w2")
    doc_div = await _make_doc(session, _doc_counter, "1099_div")
    doc_int = await _make_doc(session, _doc_counter, "1099_int")
    doc_b = await _make_doc(session, _doc_counter, "1099_b")

    await create_tax_item(session, {
        "source_document_id": doc_w2.id,
        "tax_year": 2025, "form_type": "w2",
        "w2_wages": 300000.0, "w2_federal_tax_withheld": 55000.0,
    })
    await create_tax_item(session, {
        "source_document_id": doc_div.id,
        "tax_year": 2025, "form_type": "1099_div",
        "div_total_ordinary": 8000.0, "div_qualified": 5000.0,
    })
    await create_tax_item(session, {
        "source_document_id": doc_int.id,
        "tax_year": 2025, "form_type": "1099_int",
        "int_interest": 3000.0,
    })
    await create_tax_item(session, {
        "source_document_id": doc_b.id,
        "tax_year": 2025, "form_type": "1099_b",
        "b_gain_loss": 15000.0, "b_term": "long",
    })
    await session.flush()

    estimate = await compute_tax_estimate(session, 2025)

    assert estimate["data_source"] == "documents"
    assert estimate["qualified_dividends_and_ltcg"] == 5000.0 + 15000.0
    # AGI should include all income
    assert estimate["estimated_agi"] > 300000
    # NIIT should apply for high earners above $250K MFJ threshold
    assert estimate["niit"] > 0


@pytest.mark.asyncio
async def test_tax_estimate_with_life_events(session, _doc_counter):
    """Life events (real estate sale, job change bonus) should fold into estimate."""
    hp = HouseholdProfile(
        name="Life Event HH",
        filing_status="mfj",
        state="CA",
        spouse_a_income=0.0,
        spouse_b_income=0.0,
        is_primary=True,
    )
    session.add(hp)
    await session.flush()

    doc = await _make_doc(session, _doc_counter, "w2")
    await create_tax_item(session, {
        "source_document_id": doc.id,
        "tax_year": 2025, "form_type": "w2",
        "w2_wages": 250000.0, "w2_federal_tax_withheld": 40000.0,
    })

    # Home sale with capital gain
    le1 = LifeEvent(
        event_type="real_estate",
        event_subtype="sale",
        title="Sold investment property",
        tax_year=2025,
        amounts_json=json.dumps({"capital_gain": 100000}),
    )
    # Job change with signing bonus
    le2 = LifeEvent(
        event_type="employment",
        event_subtype="job_change",
        title="New job",
        tax_year=2025,
        amounts_json=json.dumps({"signing_bonus": 30000}),
    )
    session.add_all([le1, le2])
    await session.flush()

    estimate = await compute_tax_estimate(session, 2025)

    assert estimate["life_event_capital_gains"] == 100000.0
    assert estimate["life_event_bonus_income"] == 30000.0
    # AGI should include the life event amounts
    assert estimate["estimated_agi"] > 250000 + 100000


@pytest.mark.asyncio
async def test_tax_estimate_empty_db(session):
    """compute_tax_estimate with no data should return data_source='none'."""
    estimate = await compute_tax_estimate(session, 2025)

    assert estimate["data_source"] == "none"
    assert estimate["estimated_agi"] == 0.0
    assert estimate["total_estimated_tax"] == 0.0


@pytest.mark.asyncio
async def test_tax_estimate_fallback_to_household(session, household_profile):
    """When no tax documents exist, estimate should fall back to household income."""
    estimate = await compute_tax_estimate(session, 2025)

    assert estimate["data_source"] == "setup_profile"
    # Total W2 from household: 150K + 130K = 280K
    assert estimate["estimated_agi"] > 0
    assert estimate["total_estimated_tax"] > 0


@pytest.mark.asyncio
async def test_tax_estimate_household_with_other_income(session, household_with_other_income):
    """Household other_income_sources_json should be parsed into correct buckets."""
    estimate = await compute_tax_estimate(session, 2025)

    assert estimate["data_source"] == "setup_profile"
    # 100K + 80K W2 + 40K 1099 + 10K div + 10K rental = 240K total
    assert estimate["estimated_agi"] > 200000
    # SE income from 1099 should be 40K
    assert estimate["self_employment_income"] == 40000.0


@pytest.mark.asyncio
async def test_tax_estimate_mfj_vs_single_rates(session, _doc_counter):
    """MFJ filers should pay less tax than single on the same income."""
    # MFJ household
    hp_mfj = HouseholdProfile(
        name="MFJ HH", filing_status="mfj",
        spouse_a_income=0.0, spouse_b_income=0.0,
        is_primary=True,
    )
    session.add(hp_mfj)
    await session.flush()

    doc = await _make_doc(session, _doc_counter, "w2")
    await create_tax_item(session, {
        "source_document_id": doc.id,
        "tax_year": 2025, "form_type": "w2",
        "w2_wages": 200000.0, "w2_federal_tax_withheld": 30000.0,
    })
    await session.flush()

    estimate_mfj = await compute_tax_estimate(session, 2025)

    # Change to single
    hp_mfj.filing_status = "single"
    await session.flush()

    estimate_single = await compute_tax_estimate(session, 2025)

    # Single filer should have higher federal tax
    assert estimate_single["federal_income_tax"] > estimate_mfj["federal_income_tax"]


# ============================================================================
# compute_deduction_opportunities
# ============================================================================


@pytest.mark.asyncio
async def test_deduction_opportunities_with_se_income(session, _doc_counter):
    """SE income should trigger SEP-IRA, vehicle, equipment, home office opportunities."""
    hp = HouseholdProfile(
        name="SE Deductions HH", filing_status="mfj",
        spouse_a_income=0.0, spouse_b_income=0.0,
        is_primary=True,
    )
    session.add(hp)
    await session.flush()

    doc = await _make_doc(session, _doc_counter, "1099_nec")
    await create_tax_item(session, {
        "source_document_id": doc.id,
        "tax_year": 2025, "form_type": "1099_nec",
        "nec_nonemployee_compensation": 100000.0,
    })
    await session.flush()

    result = await compute_deduction_opportunities(session, 2025)

    assert result["tax_year"] == 2025
    opp_ids = [o["id"] for o in result["opportunities"]]
    assert "sep_ira" in opp_ids
    assert "vehicle_179" in opp_ids
    assert "equipment_179" in opp_ids
    assert "home_office" in opp_ids


@pytest.mark.asyncio
async def test_deduction_opportunities_always_has_401k(session, _doc_counter):
    """401(k) maximization should always appear in opportunities."""
    hp = HouseholdProfile(
        name="401k HH", filing_status="mfj",
        spouse_a_income=0.0, spouse_b_income=0.0,
        is_primary=True,
    )
    session.add(hp)
    await session.flush()

    doc = await _make_doc(session, _doc_counter, "w2")
    await create_tax_item(session, {
        "source_document_id": doc.id,
        "tax_year": 2025, "form_type": "w2",
        "w2_wages": 150000.0, "w2_federal_tax_withheld": 25000.0,
    })
    await session.flush()

    result = await compute_deduction_opportunities(session, 2025)

    opp_ids = [o["id"] for o in result["opportunities"]]
    assert "maximize_401k" in opp_ids


@pytest.mark.asyncio
async def test_deduction_opportunities_high_agi_backdoor_roth(session, _doc_counter):
    """High AGI ($230K+) should trigger backdoor Roth opportunity."""
    hp = HouseholdProfile(
        name="High Income HH", filing_status="mfj",
        spouse_a_income=0.0, spouse_b_income=0.0,
        is_primary=True,
    )
    session.add(hp)
    await session.flush()

    doc = await _make_doc(session, _doc_counter, "w2")
    await create_tax_item(session, {
        "source_document_id": doc.id,
        "tax_year": 2025, "form_type": "w2",
        "w2_wages": 350000.0, "w2_federal_tax_withheld": 60000.0,
    })
    await session.flush()

    result = await compute_deduction_opportunities(session, 2025)

    opp_ids = [o["id"] for o in result["opportunities"]]
    assert "backdoor_roth" in opp_ids
    assert "charitable_daf" in opp_ids  # Also triggers for AGI > 200K


@pytest.mark.asyncio
async def test_deduction_opportunities_hsa_with_benefits(session, _doc_counter):
    """HSA opportunity should reflect HDHP enrollment from BenefitPackage."""
    hp = HouseholdProfile(
        name="HSA HH", filing_status="mfj",
        spouse_a_income=0.0, spouse_b_income=0.0,
        is_primary=True,
    )
    session.add(hp)
    await session.flush()

    # Add a benefit package with HSA
    bp = BenefitPackage(
        household_id=hp.id,
        spouse="A",
        has_hsa=True,
    )
    session.add(bp)

    doc = await _make_doc(session, _doc_counter, "w2")
    await create_tax_item(session, {
        "source_document_id": doc.id,
        "tax_year": 2025, "form_type": "w2",
        "w2_wages": 200000.0, "w2_federal_tax_withheld": 30000.0,
    })
    await session.flush()

    result = await compute_deduction_opportunities(session, 2025)

    hsa_opp = next(o for o in result["opportunities"] if o["id"] == "hsa_contribution")
    assert "(HDHP enrolled)" in hsa_opp["title"]
    assert hsa_opp.get("applicable") is True


@pytest.mark.asyncio
async def test_deduction_opportunities_summary_text(session, _doc_counter):
    """Summary text should mention balance due when tax is owed."""
    hp = HouseholdProfile(
        name="Summary HH", filing_status="mfj",
        spouse_a_income=0.0, spouse_b_income=0.0,
        is_primary=True,
    )
    session.add(hp)
    await session.flush()

    doc = await _make_doc(session, _doc_counter, "w2")
    await create_tax_item(session, {
        "source_document_id": doc.id,
        "tax_year": 2025, "form_type": "w2",
        "w2_wages": 200000.0, "w2_federal_tax_withheld": 5000.0,  # Low withholding = balance due
    })
    await session.flush()

    result = await compute_deduction_opportunities(session, 2025)

    assert result["summary"] is not None
    assert len(result["summary"]) > 0
    assert result["estimated_balance_due"] > 0


@pytest.mark.asyncio
async def test_deduction_opportunities_empty_db(session):
    """compute_deduction_opportunities with no data should still return valid structure."""
    result = await compute_deduction_opportunities(session, 2025)

    assert result["tax_year"] == 2025
    assert isinstance(result["opportunities"], list)
    # 401k opportunity should still appear
    opp_ids = [o["id"] for o in result["opportunities"]]
    assert "maximize_401k" in opp_ids


# ============================================================================
# get_tax_summary_with_fallback
# ============================================================================


@pytest.mark.asyncio
async def test_tax_summary_fallback_documents(session, _doc_counter):
    """When tax documents exist, data_source should be 'documents'."""
    doc = await _make_doc(session, _doc_counter, "w2")
    await create_tax_item(session, {
        "source_document_id": doc.id,
        "tax_year": 2025, "form_type": "w2",
        "w2_wages": 150000.0, "w2_federal_tax_withheld": 25000.0,
    })
    await session.flush()

    summary = await get_tax_summary_with_fallback(session, 2025)

    assert summary["data_source"] == "documents"
    assert summary["w2_total_wages"] == 150000.0


@pytest.mark.asyncio
async def test_tax_summary_fallback_household_profile(session, household_profile):
    """When no docs but household has income, data_source='setup_profile'."""
    summary = await get_tax_summary_with_fallback(session, 2025)

    assert summary["data_source"] == "setup_profile"
    assert summary["w2_total_wages"] == 280000.0  # 150K + 130K


@pytest.mark.asyncio
async def test_tax_summary_fallback_household_other_sources(session, household_with_other_income):
    """Household other_income_sources_json should be parsed into correct summary fields."""
    summary = await get_tax_summary_with_fallback(session, 2025)

    assert summary["data_source"] == "setup_profile"
    assert summary["w2_total_wages"] == 180000.0  # 100K + 80K
    assert summary["nec_total"] == 40000.0  # business_1099
    assert summary["div_ordinary"] == 10000.0  # dividends_1099
    assert summary["interest_income"] == 10000.0  # rental


@pytest.mark.asyncio
async def test_tax_summary_fallback_none(session):
    """When no docs and no household, data_source should be 'none'."""
    summary = await get_tax_summary_with_fallback(session, 2025)

    assert summary["data_source"] == "none"
    assert summary["w2_total_wages"] == 0.0


@pytest.mark.asyncio
async def test_tax_summary_fallback_empty_household(session):
    """Household with zero income should result in data_source='none'."""
    hp = HouseholdProfile(
        name="Empty HH",
        filing_status="mfj",
        spouse_a_income=0.0,
        spouse_b_income=0.0,
        other_income_annual=0.0,
        is_primary=True,
    )
    session.add(hp)
    await session.flush()

    summary = await get_tax_summary_with_fallback(session, 2025)

    assert summary["data_source"] == "none"


@pytest.mark.asyncio
async def test_tax_summary_documents_take_precedence(session, household_profile, _doc_counter):
    """Documents should take precedence over household profile data."""
    doc = await _make_doc(session, _doc_counter, "w2")
    await create_tax_item(session, {
        "source_document_id": doc.id,
        "tax_year": 2025, "form_type": "w2",
        "w2_wages": 999999.0, "w2_federal_tax_withheld": 200000.0,
    })
    await session.flush()

    summary = await get_tax_summary_with_fallback(session, 2025)

    # Should use document data, not household
    assert summary["data_source"] == "documents"
    assert summary["w2_total_wages"] == 999999.0


@pytest.mark.asyncio
async def test_tax_summary_k1_income(session, _doc_counter):
    """K-1 income should be aggregated into the summary."""
    doc = await _make_doc(session, _doc_counter, "k1")
    await create_tax_item(session, {
        "source_document_id": doc.id,
        "tax_year": 2025, "form_type": "k1",
        "k1_ordinary_income": 50000.0,
        "k1_guaranteed_payments": 20000.0,
        "k1_rental_income": 15000.0,
    })
    await session.flush()

    summary = await get_tax_summary_with_fallback(session, 2025)

    assert summary["data_source"] == "documents"
    assert summary["k1_ordinary_income"] == 50000.0
    assert summary["k1_guaranteed_payments"] == 20000.0
    assert summary["k1_rental_income"] == 15000.0


@pytest.mark.asyncio
async def test_tax_summary_1098_mortgage(session, _doc_counter):
    """1098 mortgage interest and property tax should appear in summary."""
    doc = await _make_doc(session, _doc_counter, "1098")
    await create_tax_item(session, {
        "source_document_id": doc.id,
        "tax_year": 2025, "form_type": "1098",
        "m_mortgage_interest": 18000.0,
        "m_property_tax": 12000.0,
        "m_points_paid": 500.0,
    })
    await session.flush()

    # Need at least some other income for data_source check
    doc_w2 = await _make_doc(session, _doc_counter, "w2")
    await create_tax_item(session, {
        "source_document_id": doc_w2.id,
        "tax_year": 2025, "form_type": "w2",
        "w2_wages": 100000.0,
    })
    await session.flush()

    summary = await get_tax_summary_with_fallback(session, 2025)

    assert summary["mortgage_interest_deduction"] == 18000.0 + 500.0  # interest + points
    assert summary["property_tax_deduction"] == 12000.0


# ============================================================================
# compute_tax_estimate — itemized vs standard deduction
# ============================================================================


@pytest.mark.asyncio
async def test_tax_estimate_itemized_deduction_when_higher(session, _doc_counter):
    """Estimate should use itemized deduction when mortgage+SALT > standard deduction."""
    hp = HouseholdProfile(
        name="Itemizer HH", filing_status="mfj",
        spouse_a_income=0.0, spouse_b_income=0.0,
        is_primary=True,
    )
    session.add(hp)
    await session.flush()

    doc_w2 = await _make_doc(session, _doc_counter, "w2")
    doc_1098 = await _make_doc(session, _doc_counter, "1098")

    await create_tax_item(session, {
        "source_document_id": doc_w2.id,
        "tax_year": 2025, "form_type": "w2",
        "w2_wages": 300000.0, "w2_federal_tax_withheld": 50000.0,
    })
    await create_tax_item(session, {
        "source_document_id": doc_1098.id,
        "tax_year": 2025, "form_type": "1098",
        "m_mortgage_interest": 25000.0,  # High mortgage interest
        "m_property_tax": 15000.0,  # But SALT cap = $10K
    })
    await session.flush()

    estimate = await compute_tax_estimate(session, 2025)

    # Itemized = $25K mortgage + $10K SALT cap = $35K > $30K standard deduction
    # So taxable income should use itemized deduction
    expected_agi = 300000.0
    expected_taxable = expected_agi - 35000.0  # itemized $35K
    assert abs(estimate["estimated_taxable_income"] - expected_taxable) < 1.0
