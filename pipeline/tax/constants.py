"""
Single source of truth for all federal and state tax constants.
Update these once per tax year — all engines and routes import from here.
Tax year: 2025/2026 (inflation-adjusted estimates).
"""

# ---------------------------------------------------------------------------
# Federal income tax brackets — (upper bound of bracket, marginal rate)
# ---------------------------------------------------------------------------
MFJ_BRACKETS: list[tuple[float, float]] = [
    (23_850, 0.10),
    (96_950, 0.12),
    (206_700, 0.22),
    (394_600, 0.24),
    (501_050, 0.32),
    (751_600, 0.35),
    (float("inf"), 0.37),
]

SINGLE_BRACKETS: list[tuple[float, float]] = [
    (11_925, 0.10),
    (48_475, 0.12),
    (103_350, 0.22),
    (197_300, 0.24),
    (250_525, 0.32),
    (626_350, 0.35),
    (float("inf"), 0.37),
]

MFS_BRACKETS: list[tuple[float, float]] = [
    (11_925, 0.10),
    (48_475, 0.12),
    (103_350, 0.22),
    (197_300, 0.24),
    (250_525, 0.32),
    (375_800, 0.35),
    (float("inf"), 0.37),
]

HOH_BRACKETS: list[tuple[float, float]] = [
    (17_000, 0.10),
    (64_850, 0.12),
    (103_350, 0.22),
    (197_300, 0.24),
    (250_500, 0.32),
    (626_350, 0.35),
    (float("inf"), 0.37),
]

# ---------------------------------------------------------------------------
# Standard deductions by filing status
# ---------------------------------------------------------------------------
STANDARD_DEDUCTION: dict[str, float] = {
    "mfj": 30_000,
    "married": 30_000,
    "mfs": 15_000,
    "single": 15_000,
    "hoh": 22_500,
}

# ---------------------------------------------------------------------------
# FICA / Self-Employment
# ---------------------------------------------------------------------------
FICA_SS_CAP = 176_100  # 2025 Social Security wage base
FICA_RATE = 0.0620        # Social Security employee share
MEDICARE_RATE = 0.0145     # Medicare employee share
ADDITIONAL_MEDICARE_RATE = 0.009  # on wages above threshold
ADDITIONAL_MEDICARE_THRESHOLD: dict[str, float] = {"mfj": 250_000, "single": 200_000, "mfs": 125_000}
SE_TAX_DEDUCTION_FACTOR = 0.9235  # multiply net SE income by this before computing SE tax

# ---------------------------------------------------------------------------
# Net Investment Income Tax (NIIT)
# ---------------------------------------------------------------------------
NIIT_RATE = 0.038
NIIT_THRESHOLD: dict[str, float] = {"mfj": 250_000, "married": 250_000, "single": 200_000, "mfs": 125_000, "hoh": 200_000}

# ---------------------------------------------------------------------------
# Alternative Minimum Tax (AMT)
# ---------------------------------------------------------------------------
AMT_EXEMPTION: dict[str, float] = {"mfj": 137_000, "single": 88_100, "mfs": 68_500}
AMT_PHASEOUT: dict[str, float] = {"mfj": 1_252_700, "single": 626_350, "mfs": 626_350}
AMT_RATE_LOW = 0.26
AMT_RATE_HIGH = 0.28
AMT_RATE_THRESHOLD = 239_100

# ---------------------------------------------------------------------------
# Capital gains rates
# ---------------------------------------------------------------------------
LTCG_RATES: dict[str, list[tuple[float, float]]] = {
    "mfj": [(96_700, 0.0), (600_050, 0.15), (float("inf"), 0.20)],
    "single": [(48_350, 0.0), (533_400, 0.15), (float("inf"), 0.20)],
    "mfs": [(48_350, 0.0), (300_000, 0.15), (float("inf"), 0.20)],
    "hoh": [(64_750, 0.0), (566_700, 0.15), (float("inf"), 0.20)],
}

# ---------------------------------------------------------------------------
# Supplemental wage withholding (RSUs, bonuses)
# ---------------------------------------------------------------------------
SUPPLEMENTAL_WITHHOLDING_RATE = 0.22

# ---------------------------------------------------------------------------
# State income tax — top marginal rates (simplified)
# ---------------------------------------------------------------------------
STATE_TAX_RATES: dict[str, float] = {
    "CA": 0.133, "NY": 0.109, "NJ": 0.1075, "OR": 0.099,
    "MN": 0.0985, "HI": 0.11, "DC": 0.1075, "VT": 0.0875,
    "IA": 0.06, "WI": 0.0765, "ME": 0.0715, "SC": 0.065,
    "CT": 0.0699, "ID": 0.058, "MT": 0.0675, "NE": 0.0664,
    "DE": 0.066, "WV": 0.065, "MA": 0.05, "NC": 0.045,
    "IL": 0.0495, "CO": 0.044, "MI": 0.0425, "IN": 0.0305,
    "PA": 0.0307, "AZ": 0.025, "ND": 0.0195, "UT": 0.0465,
    "GA": 0.055, "VA": 0.0575, "KY": 0.04, "MO": 0.048,
    "OH": 0.035, "OK": 0.0475, "KS": 0.057, "AR": 0.044,
    "AL": 0.05, "LA": 0.0425, "MS": 0.05, "RI": 0.0599,
    "NM": 0.059, "MD": 0.0575,
    # No income tax states
    "WA": 0.0, "TX": 0.0, "FL": 0.0, "NV": 0.0, "WY": 0.0,
    "TN": 0.0, "NH": 0.0, "SD": 0.0, "AK": 0.0,
}

# ---------------------------------------------------------------------------
# Credits & Limits
# ---------------------------------------------------------------------------
CHILD_TAX_CREDIT = 2_000
CHILD_TAX_CREDIT_PHASEOUT: dict[str, float] = {"mfj": 400_000, "single": 200_000}
ROTH_IRA_LIMIT = 7_000     # under 50
ROTH_IRA_LIMIT_CATCHUP = 8_000  # 50+
ROTH_INCOME_PHASEOUT: dict[str, float] = {"mfj": 236_000, "single": 150_000}
LIMIT_401K = 23_500
LIMIT_401K_CATCHUP = 31_000  # 50+
LIMIT_401K_TOTAL = 70_000   # including employer + after-tax (Section 415(c) 2025)
HSA_LIMIT: dict[str, float] = {"individual": 4_300, "family": 8_550}
DEP_CARE_FSA_LIMIT = 5_000

# ---------------------------------------------------------------------------
# QBI / Section 199A
# ---------------------------------------------------------------------------
QBI_DEDUCTION_RATE = 0.20
QBI_PHASEOUT_START: dict[str, float] = {"mfj": 383_900, "single": 191_950, "mfs": 191_950, "hoh": 191_950}
QBI_PHASEOUT_RANGE: dict[str, float] = {"mfj": 100_000, "single": 50_000, "mfs": 50_000, "hoh": 50_000}
