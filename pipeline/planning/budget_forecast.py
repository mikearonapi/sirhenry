"""
Budget forecasting engine: predict next month spending,
detect seasonal patterns, and calculate spend velocity alerts.
"""
import logging
import math
from collections import defaultdict
from datetime import date

logger = logging.getLogger(__name__)

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


class BudgetForecastEngine:

    @staticmethod
    def forecast_next_month(
        transactions: list[dict],
        recurring_monthly: float = 0,
        target_month: int = 0,
        target_year: int = 0,
    ) -> dict:
        today = date.today()
        if target_month == 0:
            target_month = today.month + 1 if today.month < 12 else 1
        if target_year == 0:
            target_year = today.year if today.month < 12 else today.year + 1

        # Group historical spending by category and month
        by_cat_month: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
        for t in transactions:
            if t.get("amount", 0) >= 0:
                continue
            cat = t.get("effective_category") or t.get("category") or "Uncategorized"
            month = t.get("period_month")
            amt = abs(t.get("amount", 0))
            if month:
                by_cat_month[cat][month].append(amt)

        categories = []
        total = 0.0
        for cat, months_data in by_cat_month.items():
            # Use target month's historical data if available, else overall average
            if target_month in months_data:
                seasonal_vals = months_data[target_month]
                predicted = sum(seasonal_vals) / len(seasonal_vals)
                confidence = min(0.95, 0.5 + len(seasonal_vals) * 0.1)
            else:
                all_vals = [v for vals in months_data.values() for v in vals]
                predicted = sum(all_vals) / max(1, len(all_vals))
                confidence = 0.4

            all_vals = [v for vals in months_data.values() for v in vals]
            historical_avg = sum(all_vals) / max(1, len(all_vals))

            categories.append({
                "category": cat,
                "predicted_amount": round(predicted, 2),
                "confidence": round(confidence, 2),
                "historical_avg": round(historical_avg, 2),
            })
            total += predicted

        categories.sort(key=lambda c: c["predicted_amount"], reverse=True)

        return {
            "month": target_month,
            "year": target_year,
            "categories": categories,
            "total_predicted": round(total, 2),
        }

    @staticmethod
    def detect_seasonal_patterns(
        transactions: list[dict],
    ) -> dict[str, dict[int, float]]:
        by_cat_month: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
        for t in transactions:
            if t.get("amount", 0) >= 0:
                continue
            cat = t.get("effective_category") or t.get("category") or "Uncategorized"
            month = t.get("period_month")
            if month:
                by_cat_month[cat][month].append(abs(t.get("amount", 0)))

        patterns = {}
        for cat, months_data in by_cat_month.items():
            monthly_avgs = {}
            for m in range(1, 13):
                vals = months_data.get(m, [])
                monthly_avgs[m] = round(sum(vals) / max(1, len(vals)), 2) if vals else 0
            overall_avg = sum(monthly_avgs.values()) / 12
            if overall_avg > 0:
                peaks = {m: round(v / overall_avg, 2) for m, v in monthly_avgs.items() if v > overall_avg * 1.5}
                if peaks:
                    patterns[cat] = {"monthly_averages": monthly_avgs, "peaks": peaks}

        return patterns

    @staticmethod
    def spending_velocity(
        budget_items: list[dict],
        mtd_spending: dict[str, float],
        day_of_month: int,
        days_in_month: int,
    ) -> list[dict]:
        results = []
        fraction_elapsed = day_of_month / days_in_month if days_in_month > 0 else 1

        for item in budget_items:
            cat = item.get("category", "")
            budget = item.get("budget_amount", 0)
            spent = abs(mtd_spending.get(cat, 0))

            if budget <= 0:
                continue

            projected = spent / fraction_elapsed if fraction_elapsed > 0 else spent
            utilization = spent / budget if budget > 0 else 0

            if utilization <= fraction_elapsed * 1.1:
                status = "on_track"
            elif utilization <= fraction_elapsed * 1.3:
                status = "watch"
            else:
                status = "over_budget"

            results.append({
                "category": cat,
                "budget": budget,
                "spent_so_far": round(spent, 2),
                "projected_total": round(projected, 2),
                "on_track": status == "on_track",
                "status": status,
            })

        return sorted(results, key=lambda r: r["projected_total"], reverse=True)
