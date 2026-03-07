"""
Claude-powered scenario analysis for life scenario planning.
Generates actionable AI advice for HENRY financial scenarios
(home purchase, college fund, early retirement, etc.).
"""
import json
import logging

from pipeline.utils import CLAUDE_MODEL, get_claude_client, call_claude_with_retry

logger = logging.getLogger(__name__)


def _build_scenario_prompt(scenario_data: dict, household_context: dict) -> str:
    """Build the Claude prompt from scenario data and household context."""
    household_line = ""
    if household_context:
        income = household_context.get("income", 0)
        filing = household_context.get("filing_status", "")
        state = household_context.get("state", "")
        household_line = f"Household income: ${income:,.0f}, Filing: {filing}, State: {state}"

    params_json = json.dumps(scenario_data.get("parameters", {}))

    return f"""Analyze this life scenario for a HENRY (High Earner, Not Rich Yet) and provide actionable advice in 3-4 concise paragraphs.

Scenario: {scenario_data.get("name", "Unknown")} ({scenario_data.get("scenario_type", "Unknown")})
{household_line}

Financial Impact:
- Total cost: ${scenario_data.get("total_cost", 0):,.0f}
- New monthly payment: ${scenario_data.get("new_monthly_payment", 0):,.0f}
- Monthly surplus after: ${scenario_data.get("monthly_surplus_after", 0):,.0f}
- Savings rate: {scenario_data.get("savings_rate_before_pct", 0):.1f}% \u2192 {scenario_data.get("savings_rate_after_pct", 0):.1f}%
- DTI ratio: {scenario_data.get("dti_before_pct", 0):.1f}% \u2192 {scenario_data.get("dti_after_pct", 0):.1f}%
- Affordability score: {scenario_data.get("affordability_score", 0):.0f}/100
- Verdict: {scenario_data.get("verdict", "unknown")}

Parameters: {params_json}

Provide:
1. Whether this is a good financial decision and why
2. Key risks to watch out for
3. Specific steps to prepare (tax optimization, timing, savings targets)
4. How this affects their long-term wealth building as a HENRY"""


def analyze_scenario_with_ai(scenario_data: dict, household_context: dict) -> dict:
    """Generate AI analysis for a life scenario using Claude.

    Parameters
    ----------
    scenario_data : dict
        Flat dict with the scenario fields:
        ``name``, ``scenario_type``, ``total_cost``, ``new_monthly_payment``,
        ``monthly_surplus_after``, ``savings_rate_before_pct``,
        ``savings_rate_after_pct``, ``dti_before_pct``, ``dti_after_pct``,
        ``affordability_score``, ``verdict``, ``parameters`` (dict).

    household_context : dict
        Household info with optional keys: ``income``, ``filing_status``, ``state``.
        Pass an empty dict if no household profile exists.

    Returns
    -------
    dict
        ``{"analysis": str}`` containing the Claude-generated analysis text.

    Raises
    ------
    RuntimeError
        If the Anthropic API key is not configured.
    """
    client = get_claude_client()
    prompt = _build_scenario_prompt(scenario_data, household_context)

    response = call_claude_with_retry(
        client,
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    analysis = response.content[0].text if response.content else ""
    return {"analysis": analysis}
