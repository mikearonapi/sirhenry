"""Retirement budget translation engine.

Translates a current personal budget into a projected retirement budget
by applying smart defaults (mortgage gone, medical up, etc.) and user overrides.
"""

# Smart defaults: category → (multiplier, reason)
# 1.0 = keep same, 0.0 = eliminated, 2.0 = doubled
RETIREMENT_DEFAULTS: dict[str, tuple[float, str]] = {
    # Eliminated — no longer working / kids independent
    "Child Activities": (0.0, "Kids independent"),
    "Childcare & Education": (0.0, "Kids independent"),
    "Babysitting": (0.0, "No childcare needed"),
    "Kid's Clothing": (0.0, "Kids independent"),
    "Destiny School": (0.0, "Kids independent"),
    "Education": (0.0, "Education complete"),
    "Education - Other": (0.0, "Education complete"),
    "Accenture Expenses": (0.0, "No longer working"),
    # Reduced — less commuting, smaller household
    "Groceries": (0.75, "Smaller household"),
    "Groceries & Food": (0.75, "Smaller household"),
    "Fast Food": (0.5, "Less convenience meals"),
    "Gas": (0.5, "Less commuting"),
    "Gas & Fuel": (0.5, "Less commuting"),
    "Parking & Tolls": (0.3, "Less commuting"),
    "Restaurants & Bars": (0.85, "Slightly less dining"),
    "Restaurants & Dining": (0.85, "Slightly less dining"),
    "Coffee Shops": (0.8, "Slightly less"),
    "Coffee & Beverages": (0.8, "Slightly less"),
    "Auto Maintenance": (0.7, "Less driving"),
    "Clothing & Apparel": (0.6, "No work wardrobe"),
    "Insurance": (0.8, "May decrease"),
    # Increased — more time, aging
    "Medical": (2.0, "Increased healthcare needs"),
    "Health & Medical": (2.0, "Increased healthcare needs"),
    "Fitness": (1.3, "More time for fitness"),
    "Fitness & Gym": (1.3, "More time for fitness"),
    "Vacation": (1.5, "More time to travel"),
    "Hotel & Lodging": (1.3, "More travel"),
    "Airline & Travel": (1.3, "More travel"),
    "Entertainment & Recreation": (1.2, "More leisure time"),
}

# Categories containing these substrings are auto-eliminated in retirement
_BUSINESS_PREFIXES = ("Business", "business")


def _is_mortgage_like(category: str) -> bool:
    """Check if a category represents a mortgage or home loan."""
    lower = category.lower()
    return "mortgage" in lower or "home loan" in lower


def _is_debt_paid_off(category: str, retirement_age: int, debt_payoffs: list[dict]) -> bool:
    """Check if a debt category will be paid off before retirement."""
    lower = category.lower()
    for d in debt_payoffs:
        name_lower = d.get("name", "").lower()
        payoff_age = d.get("payoff_age", 999)
        # Match mortgage categories to mortgage debts
        if ("mortgage" in lower or "home loan" in lower) and ("mortgage" in name_lower or "home loan" in name_lower):
            return payoff_age <= retirement_age
        # Match car/auto categories to car debts
        if "auto" in lower and "auto" in name_lower:
            return payoff_age <= retirement_age
    return False


def compute_retirement_budget(
    current_lines: list[dict],
    overrides: list[dict],
    retirement_age: int,
    debt_payoffs: list[dict],
) -> dict:
    """Translate current budget lines to retirement amounts.

    Priority: user override > debt payoff check > smart default > keep same (1.0)

    Returns dict with lines, totals, and summary.
    """
    override_map = {o["category"]: o for o in overrides}

    result_lines = []
    current_total = 0.0
    retirement_total = 0.0

    for line in current_lines:
        cat = line["category"]
        current_monthly = line["monthly_amount"]
        current_total += current_monthly

        # Skip business categories
        if any(cat.startswith(p) for p in _BUSINESS_PREFIXES):
            continue

        # Check for user override first
        if cat in override_map:
            ov = override_map[cat]
            if ov.get("fixed_amount") is not None:
                ret_monthly = ov["fixed_amount"]
                mult = ret_monthly / current_monthly if current_monthly > 0 else 0
            else:
                mult = ov.get("multiplier", 1.0)
                ret_monthly = current_monthly * mult
            reason = ov.get("reason") or "Your adjustment"
            is_override = True
        # Check if debt will be paid off
        elif _is_debt_paid_off(cat, retirement_age, debt_payoffs):
            mult = 0.0
            ret_monthly = 0.0
            reason = f"Paid off before age {retirement_age}"
            is_override = False
        # Check if mortgage-like and no debt info → still default to eliminated
        elif _is_mortgage_like(cat):
            mult = 0.0
            ret_monthly = 0.0
            reason = "Paid off before retirement"
            is_override = False
        # Apply smart default
        elif cat in RETIREMENT_DEFAULTS:
            mult, reason = RETIREMENT_DEFAULTS[cat]
            ret_monthly = current_monthly * mult
            is_override = False
        # No adjustment — keep same
        else:
            mult = 1.0
            ret_monthly = current_monthly
            reason = "Same as current"
            is_override = False

        ret_monthly = round(ret_monthly, 2)
        retirement_total += ret_monthly

        result_lines.append({
            "category": cat,
            "current_monthly": round(current_monthly, 2),
            "retirement_monthly": ret_monthly,
            "multiplier": round(mult, 2),
            "reason": reason,
            "source": line.get("source", "budget"),
            "is_user_override": is_override,
        })

    return {
        "lines": result_lines,
        "current_monthly_total": round(current_total, 2),
        "current_annual_total": round(current_total * 12, 2),
        "retirement_monthly_total": round(retirement_total, 2),
        "retirement_annual_total": round(retirement_total * 12, 2),
    }
