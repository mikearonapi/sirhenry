"""
Annual financial insights engine.

Computes outlier detection, budget normalization, seasonal patterns,
category trends, and income analysis from raw transaction data using
IQR-based statistical methods (no external dependencies beyond SQLAlchemy).
"""
import json
import logging
import math
from collections import defaultdict
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import FinancialPeriod, OutlierFeedback, Transaction

logger = logging.getLogger(__name__)

INTERNAL_TRANSFER_CATEGORIES = {"Transfer", "Credit Card Payment", "Savings"}

# Categories that are never treated as outliers regardless of amount
NEVER_OUTLIER_CATEGORIES = {
    "Mortgage", "Rent", "Mortgage & Rent",
    "Housing", "Housing Payment",
}

# IQR multiplier for outlier fencing
IQR_MULTIPLIER = 1.5
# Minimum absolute amount to flag as an outlier (avoids noise on small txns)
MIN_EXPENSE_OUTLIER = 500.0
MIN_INCOME_OUTLIER = 1000.0


def _percentile(sorted_vals: list[float], pct: float) -> float:
    """Linear-interpolation percentile on a pre-sorted list."""
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * pct
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def _iqr_fences(values: list[float]) -> tuple[float, float]:
    """Return (lower_fence, upper_fence) using IQR method."""
    if len(values) < 4:
        return (min(values, default=0) - 1, max(values, default=0) + 1)
    s = sorted(values)
    q1 = _percentile(s, 0.25)
    q3 = _percentile(s, 0.75)
    iqr = q3 - q1
    return (q1 - IQR_MULTIPLIER * iqr, q3 + IQR_MULTIPLIER * iqr)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    return _percentile(sorted(values), 0.5)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


async def _fetch_transactions(
    session: AsyncSession,
    year: int,
) -> list[Any]:
    """Fetch all non-excluded, non-transfer transactions for a year."""
    result = await session.execute(
        select(
            Transaction.id,
            Transaction.date,
            Transaction.description,
            Transaction.amount,
            Transaction.effective_category,
            Transaction.effective_segment,
            Transaction.period_month,
            Transaction.period_year,
        ).where(
            Transaction.period_year == year,
            Transaction.is_excluded == False,  # noqa: E712
            Transaction.effective_category.notin_(INTERNAL_TRANSFER_CATEGORIES),
        )
    )
    return result.all()


async def _fetch_outlier_feedback(
    session: AsyncSession,
    year: int,
) -> list[Any]:
    """Fetch all outlier feedback for a year plus future-applicable rules from prior years."""
    result = await session.execute(
        select(OutlierFeedback).where(
            (OutlierFeedback.year == year)
            | (
                (OutlierFeedback.apply_to_future == True)  # noqa: E712
                & (OutlierFeedback.year < year)
            )
        )
    )
    return result.scalars().all()


async def _fetch_periods(
    session: AsyncSession,
    year: int,
) -> list[FinancialPeriod]:
    """Fetch monthly FinancialPeriod rows for a year."""
    result = await session.execute(
        select(FinancialPeriod).where(
            FinancialPeriod.year == year,
            FinancialPeriod.segment == "all",
            FinancialPeriod.month.isnot(None),
        )
    )
    return result.scalars().all()


def _build_feedback_index(
    feedback_rows: list[Any],
) -> tuple[dict[int, Any], set[str], set[str]]:
    """
    Build lookup structures from outlier feedback:
    - by_txn_id: {transaction_id: feedback_row}
    - suppressed_patterns: patterns with not_outlier classification
    - suppressed_categories: categories where all feedback is not_outlier
    """
    by_txn_id: dict[int, Any] = {}
    suppressed_patterns: set[str] = set()
    cat_feedback: dict[str, list[str]] = defaultdict(list)

    for fb in feedback_rows:
        by_txn_id[fb.transaction_id] = fb
        if fb.apply_to_future and fb.classification == "not_outlier":
            if fb.description_pattern:
                suppressed_patterns.add(fb.description_pattern.upper())
            if fb.category:
                cat_feedback[fb.category].append(fb.classification)

    suppressed_categories: set[str] = set()
    for cat, classes in cat_feedback.items():
        if all(c == "not_outlier" for c in classes) and len(classes) >= 2:
            suppressed_categories.add(cat)

    return by_txn_id, suppressed_patterns, suppressed_categories


def _matches_suppressed_pattern(description: str, patterns: set[str]) -> bool:
    """Check if a transaction description matches any suppressed pattern."""
    desc_upper = description.upper()
    return any(pat in desc_upper for pat in patterns)


def _feedback_to_dict(fb: Any) -> dict[str, Any]:
    return {
        "id": fb.id,
        "transaction_id": fb.transaction_id,
        "classification": fb.classification,
        "user_note": fb.user_note,
        "description_pattern": fb.description_pattern,
        "category": fb.category,
        "apply_to_future": fb.apply_to_future,
        "year": fb.year,
        "created_at": fb.created_at.isoformat() if fb.created_at else None,
    }


def _detect_outlier_transactions(
    transactions: list[Any],
    feedback_rows: list[Any] | None = None,
    prior_year_transactions: list[Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Detect outlier transactions using per-category IQR fencing.

    When a category has < 3 transactions in the current year, prior year
    data (if available) is combined to establish a meaningful baseline.

    Respects user feedback:
    - not_outlier: suppressed from detection (by pattern or if category fully suppressed)
    - recurring / one_time: still shown as outliers but with feedback attached

    Returns (expense_outliers, income_outliers), each a list of dicts with
    transaction details and why it's flagged.
    """
    fb_by_txn, suppressed_patterns, suppressed_cats = _build_feedback_index(
        feedback_rows or []
    )

    expense_by_cat: dict[str, list[tuple[Any, float]]] = defaultdict(list)
    income_by_cat: dict[str, list[tuple[Any, float]]] = defaultdict(list)

    for tx in transactions:
        cat = tx.effective_category or "Unknown"
        amt = float(tx.amount)
        if amt < 0:
            expense_by_cat[cat].append((tx, abs(amt)))
        elif amt > 0:
            income_by_cat[cat].append((tx, amt))

    prior_expense_by_cat: dict[str, list[float]] = defaultdict(list)
    prior_income_by_cat: dict[str, list[float]] = defaultdict(list)
    if prior_year_transactions:
        for tx in prior_year_transactions:
            cat = tx.effective_category or "Unknown"
            amt = float(tx.amount)
            if amt < 0:
                prior_expense_by_cat[cat].append(abs(amt))
            elif amt > 0:
                prior_income_by_cat[cat].append(amt)

    current_year_txn_ids = {tx.id for tx in transactions}

    def _build_outlier_entry(
        tx: Any, amt: float, med: float, upper: float, cat: str, is_expense: bool,
    ) -> dict[str, Any]:
        fb = fb_by_txn.get(tx.id)
        excess_pct = round(((amt - med) / med) * 100, 1) if med > 0 else 0
        if med > 0:
            reason = f"${amt:,.0f} is {((amt - med) / med * 100):.0f}% above the typical ${med:,.0f} for {cat}"
        else:
            reason = f"Large {cat} {'expense' if is_expense else 'income'}"
        return {
            "id": tx.id,
            "date": tx.date.isoformat() if tx.date else None,
            "description": tx.description,
            "amount": -amt if is_expense else amt,
            "category": cat,
            "segment": tx.effective_segment,
            "typical_amount": round(med, 2),
            "threshold": round(upper, 2),
            "excess_pct": excess_pct,
            "reason": reason,
            "feedback": _feedback_to_dict(fb) if fb else None,
        }

    expense_outliers: list[dict[str, Any]] = []
    income_outliers: list[dict[str, Any]] = []

    for cat, items in expense_by_cat.items():
        if cat in NEVER_OUTLIER_CATEGORIES or cat in suppressed_cats:
            continue
        amounts = [a for _, a in items]

        if len(amounts) >= 3:
            _, upper = _iqr_fences(amounts)
            med = _median(amounts)
        elif prior_expense_by_cat.get(cat):
            combined = amounts + prior_expense_by_cat[cat]
            if len(combined) >= 3:
                _, upper = _iqr_fences(combined)
                med = _median(combined)
            else:
                continue
        else:
            continue

        for tx, amt in items:
            if amt > upper and amt >= MIN_EXPENSE_OUTLIER:
                if tx.id in fb_by_txn and fb_by_txn[tx.id].classification == "not_outlier":
                    continue
                if _matches_suppressed_pattern(tx.description, suppressed_patterns):
                    if tx.id not in fb_by_txn:
                        continue
                expense_outliers.append(
                    _build_outlier_entry(tx, amt, med, upper, cat, is_expense=True)
                )

    for cat, items in income_by_cat.items():
        amounts = [a for _, a in items]

        if len(amounts) >= 3:
            _, upper = _iqr_fences(amounts)
            med = _median(amounts)
        elif prior_income_by_cat.get(cat):
            combined = amounts + prior_income_by_cat[cat]
            if len(combined) >= 3:
                _, upper = _iqr_fences(combined)
                med = _median(combined)
            else:
                continue
        else:
            continue

        for tx, amt in items:
            if amt > upper and amt >= MIN_INCOME_OUTLIER:
                fb = fb_by_txn.get(tx.id)
                if fb and fb.classification == "not_outlier":
                    continue
                income_outliers.append(
                    _build_outlier_entry(tx, amt, med, upper, cat, is_expense=False)
                )

    expense_outliers.sort(key=lambda x: x["amount"])
    income_outliers.sort(key=lambda x: -x["amount"])
    return expense_outliers, income_outliers


def _normalize_budget(
    transactions: list[Any],
    expense_outlier_ids: set[int],
) -> dict[str, Any]:
    """
    Compute a "normalized" monthly budget by excluding outlier transactions.

    Returns per-category medians and an overall normalized monthly total.
    """
    monthly_cat_totals: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    monthly_totals: dict[int, float] = defaultdict(float)

    for tx in transactions:
        if tx.id in expense_outlier_ids:
            continue
        amt = float(tx.amount)
        if amt >= 0:
            continue
        cat = tx.effective_category or "Unknown"
        month = tx.period_month or 0
        if month == 0:
            continue
        monthly_cat_totals[cat][month] += abs(amt)
        monthly_totals[month] += abs(amt)

    by_category: list[dict[str, Any]] = []
    for cat, month_map in sorted(monthly_cat_totals.items()):
        vals = list(month_map.values())
        by_category.append({
            "category": cat,
            "normalized_monthly": round(_median(vals), 2),
            "mean_monthly": round(_mean(vals), 2),
            "min_monthly": round(min(vals), 2) if vals else 0,
            "max_monthly": round(max(vals), 2) if vals else 0,
            "months_active": len(vals),
        })
    by_category.sort(key=lambda x: -x["normalized_monthly"])

    all_monthly = list(monthly_totals.values())
    return {
        "normalized_monthly_total": round(_median(all_monthly), 2),
        "mean_monthly_total": round(_mean(all_monthly), 2),
        "min_month": round(min(all_monthly), 2) if all_monthly else 0,
        "max_month": round(max(all_monthly), 2) if all_monthly else 0,
        "by_category": by_category,
    }


MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _monthly_analysis(
    transactions: list[Any],
    expense_outlier_ids: set[int],
    income_outlier_ids: set[int],
    periods: list[FinancialPeriod],
) -> list[dict[str, Any]]:
    """
    For each month, compute total spending (with and without outliers),
    classify as normal / elevated / high, and identify top contributing categories.
    """
    monthly_expenses: dict[int, float] = defaultdict(float)
    monthly_expenses_clean: dict[int, float] = defaultdict(float)
    monthly_income: dict[int, float] = defaultdict(float)
    monthly_income_clean: dict[int, float] = defaultdict(float)
    monthly_cat_expenses: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    monthly_outlier_total: dict[int, float] = defaultdict(float)
    monthly_outlier_count: dict[int, int] = defaultdict(int)

    for tx in transactions:
        month = tx.period_month or 0
        if month == 0:
            continue
        amt = float(tx.amount)
        if amt < 0:
            expense = abs(amt)
            monthly_expenses[month] += expense
            cat = tx.effective_category or "Unknown"
            monthly_cat_expenses[month][cat] += expense
            if tx.id in expense_outlier_ids:
                monthly_outlier_total[month] += expense
                monthly_outlier_count[month] += 1
            else:
                monthly_expenses_clean[month] += expense
        elif amt > 0:
            monthly_income[month] += amt
            if tx.id in income_outlier_ids:
                pass
            else:
                monthly_income_clean[month] += amt

    clean_vals = [v for v in monthly_expenses_clean.values() if v > 0]
    median_clean = _median(clean_vals) if clean_vals else 0
    stdev_clean = _stdev(clean_vals) if len(clean_vals) >= 2 else 0

    result = []
    for m in range(1, 13):
        total_exp = monthly_expenses.get(m, 0)
        clean_exp = monthly_expenses_clean.get(m, 0)
        total_inc = monthly_income.get(m, 0)

        if total_exp == 0 and total_inc == 0:
            continue

        if median_clean > 0 and stdev_clean > 0:
            z_score = (clean_exp - median_clean) / stdev_clean if stdev_clean > 0 else 0
        else:
            z_score = 0

        if z_score > 1.5:
            classification = "very_high"
        elif z_score > 0.75:
            classification = "elevated"
        elif z_score < -0.75:
            classification = "low"
        else:
            classification = "normal"

        cats = monthly_cat_expenses.get(m, {})
        top_cats = sorted(cats.items(), key=lambda x: -x[1])[:5]

        explanation_parts = []
        if monthly_outlier_count.get(m, 0) > 0:
            explanation_parts.append(
                f"{monthly_outlier_count[m]} outlier(s) totaling ${monthly_outlier_total[m]:,.0f}"
            )
        if classification in ("very_high", "elevated") and top_cats:
            top_cat_name, top_cat_amt = top_cats[0]
            explanation_parts.append(f"highest category: {top_cat_name} (${top_cat_amt:,.0f})")

        result.append({
            "month": m,
            "month_name": MONTH_NAMES[m],
            "total_expenses": round(total_exp, 2),
            "expenses_excl_outliers": round(clean_exp, 2),
            "total_income": round(total_inc, 2),
            "outlier_expense_total": round(monthly_outlier_total.get(m, 0), 2),
            "outlier_count": monthly_outlier_count.get(m, 0),
            "classification": classification,
            "deviation_pct": round(((clean_exp - median_clean) / median_clean * 100), 1) if median_clean > 0 else 0,
            "top_categories": [{"category": c, "amount": round(a, 2)} for c, a in top_cats],
            "explanation": "; ".join(explanation_parts) if explanation_parts else None,
        })

    return result


def _seasonal_patterns(
    transactions: list[Any],
    prior_year_transactions: Optional[list[Any]] = None,
) -> list[dict[str, Any]]:
    """
    Identify seasonal spending patterns by comparing monthly averages
    across available years of data.
    """
    all_txns = list(transactions)
    if prior_year_transactions:
        all_txns.extend(prior_year_transactions)

    monthly_totals: dict[int, list[float]] = defaultdict(list)
    monthly_cat: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    yearly_monthly: dict[tuple[int, int], float] = defaultdict(float)
    yearly_monthly_cat: dict[tuple[int, int], dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for tx in all_txns:
        amt = float(tx.amount)
        if amt >= 0:
            continue
        month = tx.period_month or 0
        year = tx.period_year or 0
        if month == 0 or year == 0:
            continue
        cat = tx.effective_category or "Unknown"
        if cat in INTERNAL_TRANSFER_CATEGORIES:
            continue
        expense = abs(amt)
        yearly_monthly[(year, month)] += expense
        yearly_monthly_cat[(year, month)][cat] += expense

    years = set()
    for (y, m) in yearly_monthly:
        years.add(y)

    for (y, m), total in yearly_monthly.items():
        monthly_totals[m].append(total)
    for (y, m), cats in yearly_monthly_cat.items():
        for cat, amt in cats.items():
            monthly_cat[m][cat].append(amt)

    overall_avg = _mean([v for vals in monthly_totals.values() for v in vals])

    result = []
    for m in range(1, 13):
        vals = monthly_totals.get(m, [])
        if not vals:
            continue
        avg = _mean(vals)
        seasonal_idx = round((avg / overall_avg) * 100, 1) if overall_avg > 0 else 100

        top_seasonal_cats = []
        for cat, cat_vals in sorted(monthly_cat.get(m, {}).items(), key=lambda x: -_mean(x[1]))[:5]:
            top_seasonal_cats.append({
                "category": cat,
                "avg_amount": round(_mean(cat_vals), 2),
            })

        label = "typical"
        if seasonal_idx > 130:
            label = "peak"
        elif seasonal_idx > 115:
            label = "above_average"
        elif seasonal_idx < 85:
            label = "below_average"
        elif seasonal_idx < 70:
            label = "low"

        result.append({
            "month": m,
            "month_name": MONTH_NAMES[m],
            "average_expenses": round(avg, 2),
            "seasonal_index": seasonal_idx,
            "label": label,
            "years_of_data": len(vals),
            "top_categories": top_seasonal_cats,
        })

    return result


def _category_trends(
    transactions: list[Any],
    periods: list[FinancialPeriod],
) -> list[dict[str, Any]]:
    """
    Analyze spending trends per category: direction (increasing, decreasing, stable),
    volatility, and share of total budget.
    """
    cat_monthly: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    total_expenses = 0.0

    for tx in transactions:
        amt = float(tx.amount)
        if amt >= 0:
            continue
        cat = tx.effective_category or "Unknown"
        month = tx.period_month or 0
        if month == 0:
            continue
        expense = abs(amt)
        cat_monthly[cat][month] += expense
        total_expenses += expense

    result = []
    for cat, month_map in cat_monthly.items():
        months_sorted = sorted(month_map.items())
        vals = [v for _, v in months_sorted]

        if len(vals) < 2:
            trend = "insufficient_data"
        else:
            first_half = vals[:len(vals)//2]
            second_half = vals[len(vals)//2:]
            first_avg = _mean(first_half)
            second_avg = _mean(second_half)
            if first_avg == 0:
                change_pct = 100.0 if second_avg > 0 else 0.0
            else:
                change_pct = ((second_avg - first_avg) / first_avg) * 100

            if change_pct > 20:
                trend = "increasing"
            elif change_pct < -20:
                trend = "decreasing"
            else:
                trend = "stable"

        cat_total = sum(vals)
        share = (cat_total / total_expenses * 100) if total_expenses > 0 else 0

        result.append({
            "category": cat,
            "trend": trend,
            "total_annual": round(cat_total, 2),
            "monthly_average": round(_mean(vals), 2),
            "monthly_median": round(_median(vals), 2),
            "volatility": round(_stdev(vals), 2),
            "budget_share_pct": round(share, 1),
            "months_active": len(vals),
            "monthly_amounts": {str(m): round(v, 2) for m, v in months_sorted},
        })

    result.sort(key=lambda x: -x["total_annual"])
    return result


def _income_analysis(
    transactions: list[Any],
    income_outlier_ids: set[int],
) -> dict[str, Any]:
    """
    Break down income into regular (predictable) vs irregular (bonuses, windfalls).
    """
    regular_monthly: dict[int, float] = defaultdict(float)
    irregular_monthly: dict[int, float] = defaultdict(float)
    income_by_source: dict[str, float] = defaultdict(float)
    irregular_items: list[dict[str, Any]] = []

    for tx in transactions:
        amt = float(tx.amount)
        if amt <= 0:
            continue
        cat = tx.effective_category or "Unknown"
        month = tx.period_month or 0
        if month == 0:
            continue
        income_by_source[cat] += amt
        if tx.id in income_outlier_ids:
            irregular_monthly[month] += amt
            irregular_items.append({
                "date": tx.date.isoformat() if tx.date else None,
                "description": tx.description,
                "amount": round(amt, 2),
                "category": cat,
            })
        else:
            regular_monthly[month] += amt

    regular_vals = list(regular_monthly.values())
    return {
        "regular_monthly_median": round(_median(regular_vals), 2),
        "regular_monthly_mean": round(_mean(regular_vals), 2),
        "total_regular": round(sum(regular_vals), 2),
        "total_irregular": round(sum(irregular_monthly.values()), 2),
        "irregular_items": irregular_items,
        "by_source": [
            {"source": k, "total": round(v, 2)}
            for k, v in sorted(income_by_source.items(), key=lambda x: -x[1])
        ],
    }


def _year_over_year(
    current_periods: list[FinancialPeriod],
    prior_periods: list[FinancialPeriod],
    additional_prior_periods: Optional[list[FinancialPeriod]] = None,
) -> Optional[dict[str, Any]]:
    """Compare current year to prior year(s) on key metrics.

    additional_prior_periods is an optional second prior year (e.g., year-2)
    whose monthly data is included in the monthly comparison for multi-year charts.
    """
    if not prior_periods:
        return None

    def _period_totals(periods: list[FinancialPeriod]) -> tuple[float, float, float]:
        income = sum(p.total_income for p in periods if p.month is not None)
        expenses = sum(p.total_expenses for p in periods if p.month is not None)
        return income, expenses, income - expenses

    curr_inc, curr_exp, curr_net = _period_totals(current_periods)
    prev_inc, prev_exp, prev_net = _period_totals(prior_periods)

    def _delta_pct(curr: float, prev: float) -> float:
        if prev == 0:
            return 0.0
        return round(((curr - prev) / prev) * 100, 1)

    curr_map = {p.month: p for p in current_periods if p.month is not None}
    prev_map = {p.month: p for p in prior_periods if p.month is not None}
    add_map: dict[Optional[int], FinancialPeriod] = {}
    if additional_prior_periods:
        add_map = {p.month: p for p in additional_prior_periods if p.month is not None}

    monthly_comparison = []
    for m in range(1, 13):
        c = curr_map.get(m)
        p = prev_map.get(m)
        a = add_map.get(m)
        if c or p or a:
            entry: dict[str, Any] = {
                "month": m,
                "month_name": MONTH_NAMES[m],
                "current_expenses": round(c.total_expenses, 2) if c else 0,
                "prior_expenses": round(p.total_expenses, 2) if p else 0,
                "current_income": round(c.total_income, 2) if c else 0,
                "prior_income": round(p.total_income, 2) if p else 0,
                "prior_2_expenses": round(a.total_expenses, 2) if a else 0,
                "prior_2_income": round(a.total_income, 2) if a else 0,
            }
            monthly_comparison.append(entry)

    curr_expense_bd: dict[str, float] = {}
    prev_expense_bd: dict[str, float] = {}
    for p in current_periods:
        if p.month and p.expense_breakdown:
            bd = json.loads(p.expense_breakdown)
            for cat, amt in bd.items():
                curr_expense_bd[cat] = curr_expense_bd.get(cat, 0) + amt
    for p in prior_periods:
        if p.month and p.expense_breakdown:
            bd = json.loads(p.expense_breakdown)
            for cat, amt in bd.items():
                prev_expense_bd[cat] = prev_expense_bd.get(cat, 0) + amt

    all_cats = set(curr_expense_bd) | set(prev_expense_bd)
    category_yoy = []
    for cat in sorted(all_cats):
        c_amt = curr_expense_bd.get(cat, 0)
        p_amt = prev_expense_bd.get(cat, 0)
        category_yoy.append({
            "category": cat,
            "current_year": round(c_amt, 2),
            "prior_year": round(p_amt, 2),
            "change_pct": _delta_pct(c_amt, p_amt),
        })
    category_yoy.sort(key=lambda x: -abs(x["current_year"] - x["prior_year"]))

    result: dict[str, Any] = {
        "current_year_income": round(curr_inc, 2),
        "prior_year_income": round(prev_inc, 2),
        "income_change_pct": _delta_pct(curr_inc, prev_inc),
        "current_year_expenses": round(curr_exp, 2),
        "prior_year_expenses": round(prev_exp, 2),
        "expense_change_pct": _delta_pct(curr_exp, prev_exp),
        "current_year_net": round(curr_net, 2),
        "prior_year_net": round(prev_net, 2),
        "monthly_comparison": monthly_comparison,
        "category_changes": category_yoy[:15],
    }

    if additional_prior_periods:
        add_inc, add_exp, add_net = _period_totals(additional_prior_periods)
        prior_year_val = prior_periods[0].year if prior_periods else 0
        result["prior_year_2"] = prior_year_val - 1 if prior_year_val else None
        result["prior_year_2_income"] = round(add_inc, 2)
        result["prior_year_2_expenses"] = round(add_exp, 2)

    return result


async def compute_annual_insights(
    session: AsyncSession,
    year: int,
) -> dict[str, Any]:
    """
    Master function: computes all insights for a given year.

    Returns a dict matching the InsightsOut schema with:
    - outlier_transactions (expense + income)
    - normalized_budget
    - monthly_analysis
    - seasonal_patterns
    - category_trends
    - income_analysis
    - year_over_year (if prior year data exists, includes year-2 when available)
    """
    transactions = await _fetch_transactions(session, year)
    periods = await _fetch_periods(session, year)
    feedback_rows = await _fetch_outlier_feedback(session, year)

    prior_transactions = await _fetch_transactions(session, year - 1)
    prior_periods = await _fetch_periods(session, year - 1)

    prior_2_periods = await _fetch_periods(session, year - 2)

    logger.info(
        f"Computing insights for {year}: {len(transactions)} txns, "
        f"{len(periods)} periods, {len(prior_transactions)} prior-year txns, "
        f"{len(prior_2_periods)} year-2 periods, "
        f"{len(feedback_rows)} feedback entries"
    )

    expense_outliers, income_outliers = _detect_outlier_transactions(
        transactions,
        feedback_rows,
        prior_year_transactions=prior_transactions if prior_transactions else None,
    )
    expense_outlier_ids = {o["id"] for o in expense_outliers}
    income_outlier_ids = {o["id"] for o in income_outliers}

    normalized = _normalize_budget(transactions, expense_outlier_ids)
    monthly = _monthly_analysis(transactions, expense_outlier_ids, income_outlier_ids, periods)
    seasonal = _seasonal_patterns(transactions, prior_transactions if prior_transactions else None)
    cat_trends = _category_trends(transactions, periods)
    income = _income_analysis(transactions, income_outlier_ids)

    has_prior_2 = any(
        p.total_income > 0 or p.total_expenses > 0 for p in prior_2_periods
    ) if prior_2_periods else False
    yoy = _year_over_year(
        periods,
        prior_periods,
        additional_prior_periods=prior_2_periods if has_prior_2 else None,
    ) if prior_periods else None

    total_outlier_expenses = sum(abs(o["amount"]) for o in expense_outliers)
    total_outlier_income = sum(o["amount"] for o in income_outliers)

    active_months = sum(1 for m in monthly if m["total_expenses"] > 0)
    total_all_expenses = sum(abs(float(tx.amount)) for tx in transactions if float(tx.amount) < 0)
    actual_monthly_avg = total_all_expenses / active_months if active_months else 0

    normalization_savings = round(
        actual_monthly_avg - normalized["normalized_monthly_total"], 2
    ) if normalized["normalized_monthly_total"] > 0 and total_outlier_expenses > 0 else 0

    all_outliers = expense_outliers + income_outliers
    reviewed = [o for o in all_outliers if o.get("feedback")]
    review_summary = {
        "total_outliers": len(all_outliers),
        "reviewed": len(reviewed),
        "recurring": sum(1 for o in reviewed if o["feedback"]["classification"] == "recurring"),
        "one_time": sum(1 for o in reviewed if o["feedback"]["classification"] == "one_time"),
        "not_outlier": sum(1 for o in reviewed if o["feedback"]["classification"] == "not_outlier"),
    }

    return {
        "year": year,
        "transaction_count": len(transactions),
        "summary": {
            "total_outlier_expenses": round(total_outlier_expenses, 2),
            "total_outlier_income": round(total_outlier_income, 2),
            "expense_outlier_count": len(expense_outliers),
            "income_outlier_count": len(income_outliers),
            "normalized_monthly_budget": normalized["normalized_monthly_total"],
            "actual_monthly_average": round(actual_monthly_avg, 2),
            "normalization_savings": normalization_savings,
        },
        "expense_outliers": expense_outliers,
        "income_outliers": income_outliers,
        "outlier_review": review_summary,
        "normalized_budget": normalized,
        "monthly_analysis": monthly,
        "seasonal_patterns": seasonal,
        "category_trends": cat_trends,
        "income_analysis": income,
        "year_over_year": yoy,
    }
