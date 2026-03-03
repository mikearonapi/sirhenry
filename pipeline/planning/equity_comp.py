"""
Equity compensation engine for HENRY users.
Handles RSU/ISO/ESPP/NSO analysis: withholding gaps, AMT crossover,
sell strategies, concentration risk, and departure modeling.
"""
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from pipeline.tax import (
    federal_tax as _federal_tax,
    marginal_rate as _marginal_rate,
    amt_tax as _amt_tax_shared,
    state_tax as _state_tax,
    SUPPLEMENTAL_WITHHOLDING_RATE,
    NIIT_RATE, NIIT_THRESHOLD,
    AMT_EXEMPTION, AMT_PHASEOUT,
    AMT_RATE_LOW, AMT_RATE_HIGH, AMT_RATE_THRESHOLD,
    STATE_TAX_RATES,
    LTCG_RATES,
)

logger = logging.getLogger(__name__)


def _ltcg_rate(taxable_income: float, filing_status: str = "mfj") -> float:
    """Look up the LTCG rate from bracket table based on income."""
    brackets = LTCG_RATES.get(filing_status, LTCG_RATES.get("mfj", []))
    for ceiling, rate in brackets:
        if taxable_income <= ceiling:
            return rate
    return 0.20


@dataclass
class VestingProjection:
    vest_date: str
    shares: float
    gross_value: float
    federal_withholding: float
    state_withholding: float
    net_value: float
    withholding_gap: float
    status: str  # upcoming | vested | sold | expired


@dataclass
class WithholdingGapResult:
    total_vest_income: float
    total_withholding_at_supplemental: float
    actual_marginal_rate: float
    total_tax_at_marginal: float
    withholding_gap: float
    quarterly_payments: list[dict]
    state_rate: float
    state_tax: float


@dataclass
class AMTCrossoverResult:
    safe_exercise_shares: int
    amt_trigger_point: float
    iso_bargain_element: float
    amt_exemption: float
    amt_tax_without_exercise: float
    amt_tax_with_exercise: float
    regular_tax: float
    recommendation: str


@dataclass
class SellStrategyResult:
    immediate_sell: dict
    hold_one_year: dict
    staged_sell: dict
    recommendation: str


@dataclass
class DepartureAnalysis:
    total_unvested_value: float
    total_vested_unexercised: float
    exercise_cost: float
    tax_on_exercise: float
    net_if_exercise: float
    forfeited_value: float
    recommendation: str
    by_grant: list[dict]


@dataclass
class ESPPAnalysis:
    qualifying_tax: float
    disqualifying_tax: float
    savings_from_qualifying: float
    qualifying_hold_date: str
    recommendation: str


@dataclass
class ConcentrationRisk:
    employer_stock_value: float
    total_net_worth: float
    concentration_pct: float
    risk_level: str  # low | moderate | elevated | high | critical
    recommendation: str


class EquityCompEngine:

    @staticmethod
    def project_vesting_schedule(
        grant_type: str,
        grant_date: str,
        total_shares: float,
        vesting_schedule_json: Optional[str],
        current_fmv: float,
        strike_price: float = 0.0,
        existing_events: Optional[list[dict]] = None,
    ) -> list[VestingProjection]:
        schedule = json.loads(vesting_schedule_json) if vesting_schedule_json else {}
        cliff_months = schedule.get("cliff_months", 12)
        frequency = schedule.get("frequency", "quarterly")  # monthly | quarterly | annually
        total_months = schedule.get("total_months", 48)

        freq_months = {"monthly": 1, "quarterly": 3, "annually": 12}.get(frequency, 3)
        gd = date.fromisoformat(grant_date) if isinstance(grant_date, str) else grant_date

        existing_dates = set()
        if existing_events:
            for ev in existing_events:
                existing_dates.add(ev.get("vest_date", ""))

        events_after_cliff = max(1, (total_months - cliff_months) // freq_months + 1)
        shares_at_cliff = total_shares * (cliff_months / total_months)
        shares_per_event = (total_shares - shares_at_cliff) / max(1, events_after_cliff - 1)

        projections: list[VestingProjection] = []
        today = date.today()

        for i in range(events_after_cliff):
            if i == 0:
                vest_date = gd + timedelta(days=cliff_months * 30)
                shares = shares_at_cliff
            else:
                vest_date = gd + timedelta(days=(cliff_months + i * freq_months) * 30)
                shares = shares_per_event

            vest_str = vest_date.isoformat()
            if vest_str in existing_dates:
                continue

            spread = max(0, current_fmv - strike_price) if grant_type in ("iso", "nso") else current_fmv
            gross = shares * spread
            fed_wh = gross * SUPPLEMENTAL_WITHHOLDING_RATE
            state_wh = gross * 0.05
            net = gross - fed_wh - state_wh

            status = "upcoming" if vest_date > today else "vested"

            projections.append(VestingProjection(
                vest_date=vest_str,
                shares=round(shares, 4),
                gross_value=round(gross, 2),
                federal_withholding=round(fed_wh, 2),
                state_withholding=round(state_wh, 2),
                net_value=round(net, 2),
                withholding_gap=0.0,
                status=status,
            ))

        return projections

    @staticmethod
    def calculate_withholding_gap(
        vest_income: float,
        other_income: float,
        filing_status: str = "mfj",
        state: str = "CA",
    ) -> WithholdingGapResult:
        total_income = other_income + vest_income
        marginal = _marginal_rate(total_income, filing_status)
        withholding_at_supp = vest_income * SUPPLEMENTAL_WITHHOLDING_RATE
        tax_at_marginal = vest_income * marginal

        state_rate = STATE_TAX_RATES.get(state.upper(), 0.05)
        state_tax_amt = vest_income * state_rate

        # NIIT does NOT apply to W-2 vest income (RSUs/ESPPs are wages, not investment income)
        total_actual_tax = tax_at_marginal + state_tax_amt
        gap = total_actual_tax - withholding_at_supp

        quarterly = []
        if gap > 0:
            per_quarter = math.ceil(gap / 4)
            for q, due in enumerate(["04/15", "06/15", "09/15", "01/15"], 1):
                quarterly.append({"quarter": q, "due_date": due, "amount": per_quarter})

        return WithholdingGapResult(
            total_vest_income=round(vest_income, 2),
            total_withholding_at_supplemental=round(withholding_at_supp, 2),
            actual_marginal_rate=round(marginal, 4),
            total_tax_at_marginal=round(total_actual_tax, 2),
            withholding_gap=round(max(0, gap), 2),
            quarterly_payments=quarterly,
            state_rate=round(state_rate, 4),
            state_tax=round(state_tax_amt, 2),
        )

    @staticmethod
    def calculate_amt_crossover(
        iso_shares_available: int,
        strike_price: float,
        current_fmv: float,
        other_income: float,
        filing_status: str = "mfj",
    ) -> AMTCrossoverResult:
        exemption = AMT_EXEMPTION.get(filing_status, 85_700)
        bargain = max(0, current_fmv - strike_price)

        regular_tax = _federal_tax(other_income, filing_status)
        amt_without = _amt_tax_shared(other_income, filing_status)

        safe_shares = 0
        for n in range(1, iso_shares_available + 1):
            total_bargain = n * bargain
            amti = other_income + total_bargain
            amt = _amt_tax_shared(amti, filing_status)
            reg = _federal_tax(other_income + total_bargain, filing_status)
            if amt > reg:
                safe_shares = n - 1
                break
        else:
            safe_shares = iso_shares_available

        trigger_point = safe_shares * bargain
        full_bargain = iso_shares_available * bargain
        amt_full = _amt_tax_shared(other_income + full_bargain, filing_status)

        rec = f"You can safely exercise {safe_shares} shares (${trigger_point:,.0f} bargain element) without triggering AMT."
        if safe_shares == iso_shares_available:
            rec = "You can exercise all shares without triggering AMT at your current income level."

        return AMTCrossoverResult(
            safe_exercise_shares=safe_shares,
            amt_trigger_point=round(trigger_point, 2),
            iso_bargain_element=round(bargain, 2),
            amt_exemption=round(exemption, 2),
            amt_tax_without_exercise=round(amt_without, 2),
            amt_tax_with_exercise=round(amt_full, 2),
            regular_tax=round(regular_tax, 2),
            recommendation=rec,
        )

    @staticmethod
    def model_sell_strategy(
        shares: float,
        cost_basis_per_share: float,
        current_price: float,
        other_income: float,
        filing_status: str = "mfj",
        holding_period_months: int = 0,
    ) -> SellStrategyResult:
        gain = (current_price - cost_basis_per_share) * shares
        gross = current_price * shares

        marginal = _marginal_rate(other_income + gain, filing_status)
        ltcg = _ltcg_rate(other_income + gain, filing_status)
        stcg_tax = gain * marginal if gain > 0 else 0
        ltcg_tax = gain * ltcg if gain > 0 else 0

        immediate = {
            "gross_proceeds": round(gross, 2),
            "gain": round(gain, 2),
            "tax_rate": round(marginal if holding_period_months < 12 else ltcg, 4),
            "tax": round(stcg_tax if holding_period_months < 12 else ltcg_tax, 2),
            "net_proceeds": round(gross - (stcg_tax if holding_period_months < 12 else ltcg_tax), 2),
        }

        appreciation_1yr = current_price * 1.08
        gain_1yr = (appreciation_1yr - cost_basis_per_share) * shares
        ltcg_tax_1yr = gain_1yr * ltcg if gain_1yr > 0 else 0
        gross_1yr = appreciation_1yr * shares
        hold_1yr = {
            "projected_price": round(appreciation_1yr, 2),
            "gross_proceeds": round(gross_1yr, 2),
            "gain": round(gain_1yr, 2),
            "tax_rate": ltcg,
            "tax": round(ltcg_tax_1yr, 2),
            "net_proceeds": round(gross_1yr - ltcg_tax_1yr, 2),
        }

        half_shares = shares / 2
        immediate_half_gain = (current_price - cost_basis_per_share) * half_shares
        immediate_half_tax = immediate_half_gain * (marginal if holding_period_months < 12 else ltcg)
        later_half_gain = (appreciation_1yr - cost_basis_per_share) * half_shares
        later_half_tax = later_half_gain * ltcg
        staged = {
            "sell_now_shares": round(half_shares, 4),
            "sell_later_shares": round(half_shares, 4),
            "total_gross": round(current_price * half_shares + appreciation_1yr * half_shares, 2),
            "total_tax": round(immediate_half_tax + later_half_tax, 2),
            "net_proceeds": round(
                current_price * half_shares - immediate_half_tax +
                appreciation_1yr * half_shares - later_half_tax, 2
            ),
        }

        nets = {"immediate": immediate["net_proceeds"], "hold": hold_1yr["net_proceeds"], "staged": staged["net_proceeds"]}
        best = max(nets, key=nets.get)
        rec_map = {
            "immediate": "Selling now locks in gains and reduces concentration risk.",
            "hold": "Holding for long-term capital gains treatment significantly reduces your tax bill.",
            "staged": "A staged approach balances risk reduction with tax optimization.",
        }

        return SellStrategyResult(
            immediate_sell=immediate,
            hold_one_year=hold_1yr,
            staged_sell=staged,
            recommendation=rec_map[best],
        )

    @staticmethod
    def what_if_i_leave(
        grants: list[dict],
        leave_date: str,
        other_income: float = 200_000,
        filing_status: str = "mfj",
    ) -> DepartureAnalysis:
        ld = date.fromisoformat(leave_date)
        total_unvested = 0.0
        total_vested_unexercised = 0.0
        total_exercise_cost = 0.0
        total_tax = 0.0
        by_grant = []

        for g in grants:
            fmv = g.get("current_fmv", 0) or 0
            strike = g.get("strike_price", 0) or 0
            gtype = g.get("grant_type", "rsu")
            vested = g.get("vested_shares", 0) or 0
            unvested = g.get("unvested_shares", 0) or 0

            forfeited = unvested * fmv
            total_unvested += forfeited

            if gtype in ("iso", "nso"):
                ex_cost = vested * strike
                spread = max(0, fmv - strike) * vested
                nso_rate = _marginal_rate(other_income + spread, filing_status) if gtype == "nso" else 0.0
                tax = spread * nso_rate
                total_vested_unexercised += vested * fmv
                total_exercise_cost += ex_cost
                total_tax += tax
            else:
                ex_cost = 0
                tax = 0

            by_grant.append({
                "employer": g.get("employer_name", ""),
                "grant_type": gtype,
                "vested_shares": vested,
                "unvested_shares": unvested,
                "forfeited_value": round(forfeited, 2),
                "exercise_cost": round(ex_cost, 2),
                "tax_on_exercise": round(tax, 2),
            })

        net = total_vested_unexercised - total_exercise_cost - total_tax
        rec = f"Leaving forfeits ${total_unvested:,.0f} in unvested equity."
        if total_exercise_cost > 0:
            rec += f" Exercising vested options costs ${total_exercise_cost:,.0f} plus ${total_tax:,.0f} in taxes."

        return DepartureAnalysis(
            total_unvested_value=round(total_unvested, 2),
            total_vested_unexercised=round(total_vested_unexercised, 2),
            exercise_cost=round(total_exercise_cost, 2),
            tax_on_exercise=round(total_tax, 2),
            net_if_exercise=round(net, 2),
            forfeited_value=round(total_unvested, 2),
            recommendation=rec,
            by_grant=by_grant,
        )

    @staticmethod
    def espp_disposition_analysis(
        purchase_price: float,
        fmv_at_purchase: float,
        fmv_at_sale: float,
        shares: float,
        purchase_date: str,
        sale_date: str,
        offering_date: str,
        discount_pct: float = 15.0,
        other_income: float = 200_000,
        filing_status: str = "mfj",
    ) -> ESPPAnalysis:
        pd_date = date.fromisoformat(purchase_date)
        sd_date = date.fromisoformat(sale_date)
        od_date = date.fromisoformat(offering_date)

        # Qualifying: held > 2yr from offering, > 1yr from purchase
        qual_hold = sd_date >= od_date + timedelta(days=730) and sd_date >= pd_date + timedelta(days=365)
        qual_hold_date = max(od_date + timedelta(days=730), pd_date + timedelta(days=365))

        gain = (fmv_at_sale - purchase_price) * shares
        discount_amount = fmv_at_purchase * (discount_pct / 100) * shares

        ordinary_rate = _marginal_rate(other_income + gain, filing_status)
        ltcg_r = _ltcg_rate(other_income + gain, filing_status)

        if qual_hold:
            ordinary_income = min(discount_amount, gain)
            ltcg_portion = max(0, gain - ordinary_income)
            qual_tax = ordinary_income * ordinary_rate + ltcg_portion * ltcg_r
        else:
            qual_tax = float("inf")
            ordinary_income = discount_amount
            ltcg_portion = max(0, gain - ordinary_income)

        disqual_ordinary = (fmv_at_purchase - purchase_price) * shares
        disqual_ltcg = max(0, (fmv_at_sale - fmv_at_purchase) * shares)
        disqual_tax = disqual_ordinary * ordinary_rate + disqual_ltcg * ltcg_r

        if not qual_hold:
            ordinary_income_q = min(discount_amount, gain)
            ltcg_q = max(0, gain - ordinary_income_q)
            qual_tax = ordinary_income_q * ordinary_rate + ltcg_q * ltcg_r

        savings = disqual_tax - qual_tax

        if qual_hold:
            rec = "This is a qualifying disposition. You're already optimized."
        else:
            rec = f"Hold until {qual_hold_date.isoformat()} for a qualifying disposition, saving ~${max(0, savings):,.0f}."

        return ESPPAnalysis(
            qualifying_tax=round(qual_tax, 2),
            disqualifying_tax=round(disqual_tax, 2),
            savings_from_qualifying=round(max(0, savings), 2),
            qualifying_hold_date=qual_hold_date.isoformat(),
            recommendation=rec,
        )

    @staticmethod
    def concentration_risk(
        employer_stock_value: float,
        total_net_worth: float,
    ) -> ConcentrationRisk:
        if total_net_worth <= 0:
            return ConcentrationRisk(
                employer_stock_value=employer_stock_value,
                total_net_worth=total_net_worth,
                concentration_pct=100.0,
                risk_level="critical",
                recommendation="Unable to assess — net worth data needed.",
            )

        pct = (employer_stock_value / total_net_worth) * 100

        if pct < 10:
            level, rec = "low", "Employer stock concentration is healthy."
        elif pct < 20:
            level, rec = "moderate", "Consider gradually diversifying above 10% concentration."
        elif pct < 35:
            level, rec = "elevated", "Significant concentration risk. Create a diversification plan."
        elif pct < 50:
            level, rec = "high", "High concentration risk. Prioritize systematic selling."
        else:
            level, rec = "critical", "Critical concentration. Over 50% of net worth in one stock."

        return ConcentrationRisk(
            employer_stock_value=round(employer_stock_value, 2),
            total_net_worth=round(total_net_worth, 2),
            concentration_pct=round(pct, 2),
            risk_level=level,
            recommendation=rec,
        )

    @staticmethod
    def quarterly_estimated_payments(
        total_gap: float,
        current_quarter: int = 1,
    ) -> list[dict]:
        if total_gap <= 0:
            return []
        remaining_quarters = max(1, 4 - current_quarter + 1)
        per_quarter = math.ceil(total_gap / remaining_quarters)
        due_dates = {1: "04/15", 2: "06/15", 3: "09/15", 4: "01/15"}
        payments = []
        for q in range(current_quarter, 5):
            payments.append({
                "quarter": q,
                "due_date": due_dates[q],
                "amount": per_quarter,
                "cumulative": per_quarter * (q - current_quarter + 1),
            })
        return payments
