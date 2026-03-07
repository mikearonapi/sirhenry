"""
Monte Carlo simulation engine for financial scenario projections.
Runs N random trials with randomized growth rates and inflation to produce
a distribution of potential outcomes over a given time horizon.
"""
import logging
import random

logger = logging.getLogger(__name__)


def run_monte_carlo_simulation(params: dict) -> dict:
    """Run a Monte Carlo simulation over a fixed time horizon.

    Parameters
    ----------
    params : dict
        Required keys:
        - ``initial_balance`` (float): starting portfolio value
        - ``annual_contribution`` (float): net new savings added each year
        - ``runs`` (int): number of random trials (100-10000)

        Optional keys:
        - ``years`` (int): projection horizon, default 20
        - ``mean_return`` (float): expected annual return, default 0.07
        - ``std_dev`` (float): annual return volatility, default 0.15

    Returns
    -------
    dict
        Percentile outcomes (p10, p25, p50, p75, p90) and the run count.
    """
    initial_balance: float = params["initial_balance"]
    annual_contribution: float = params["annual_contribution"]
    runs: int = params["runs"]
    years: int = params.get("years", 20)
    mean_return: float = params.get("mean_return", 0.07)
    std_dev: float = params.get("std_dev", 0.15)

    outcomes: list[float] = []
    for _ in range(runs):
        balance = initial_balance
        for _ in range(years):
            r = random.gauss(mean_return, std_dev)
            balance = balance * (1 + r) + annual_contribution
        outcomes.append(balance)

    outcomes.sort()
    n = len(outcomes)

    return {
        "p10": round(outcomes[int(n * 0.10)], 2),
        "p25": round(outcomes[int(n * 0.25)], 2),
        "p50": round(outcomes[int(n * 0.50)], 2),
        "p75": round(outcomes[int(n * 0.75)], 2),
        "p90": round(outcomes[int(n * 0.90)], 2),
        "runs": runs,
    }
