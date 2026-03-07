"""
Plaid Income API client.
Handles: user creation, income link tokens, payroll income retrieval.

Plaid changed /user/create on Dec 10, 2025:
- Legacy integrations: returns user_token
- New integrations: returns user_id instead
This module handles both by preferring user_token, falling back to user_id.
"""
import json
import logging
import os
from typing import Any, Optional

import time

import httpx

from plaid.model.credit_payroll_income_get_request import CreditPayrollIncomeGetRequest

from pipeline.plaid.client import get_plaid_client, _retry_on_transient

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 503}
_MAX_RETRIES = 3


def _retry_httpx_post(url: str, **kwargs) -> httpx.Response:
    """POST with exponential backoff retry on transient HTTP errors (429, 500, 503)."""
    for attempt in range(_MAX_RETRIES):
        resp = httpx.post(url, **kwargs)
        if resp.status_code not in _RETRYABLE_STATUS:
            return resp
        wait = 2 ** attempt
        logger.warning(
            "Plaid HTTP %d for %s — retrying in %ds (attempt %d/%d)",
            resp.status_code, url, wait, attempt + 1, _MAX_RETRIES,
        )
        time.sleep(wait)
    return resp  # return last response if all retries exhausted

PLAID_HOST_MAP = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com",
}

PLAID_VERSION = "2020-09-14"


def _plaid_headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Plaid-Version": PLAID_VERSION,
    }


def _plaid_auth() -> dict[str, str]:
    return {
        "client_id": os.getenv("PLAID_CLIENT_ID", ""),
        "secret": os.getenv("PLAID_SECRET", ""),
    }


def _plaid_base_url() -> str:
    env_str = os.getenv("PLAID_ENV", "sandbox")
    return PLAID_HOST_MAP.get(env_str, PLAID_HOST_MAP["sandbox"])


def create_plaid_user(client_user_id: str) -> dict[str, str]:
    """Create a Plaid user and return user_token or user_id.

    Uses raw HTTP because plaid-python SDK v29 predates the Dec 2025
    API change where /user/create returns user_id instead of user_token.
    """
    resp = _retry_httpx_post(
        f"{_plaid_base_url()}/user/create",
        headers=_plaid_headers(),
        json={
            **_plaid_auth(),
            "client_user_id": client_user_id,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("error_code"):
        raise ValueError(f"Plaid /user/create error: {data['error_code']} - {data.get('error_message', '')}")

    user_token = data.get("user_token", "")
    user_id = data.get("user_id", "")

    if not user_token and not user_id:
        raise ValueError("Plaid /user/create returned neither user_token nor user_id")

    if not user_token and user_id:
        logger.warning(
            "Plaid /user/create returned user_id but no user_token. "
            "Income verification requires user_token — enable Income in your Plaid Dashboard."
        )

    logger.info(
        "Plaid user created: has_user_token=%s, has_user_id=%s",
        bool(user_token), bool(user_id),
    )
    return {"user_token": user_token, "user_id": user_id}


def create_income_link_token(
    income_source_type: str = "payroll",
    user_token: str = "",
    user_id: str = "",
) -> str:
    """Create a Plaid Link token for income verification.

    Uses raw HTTP to support both user_token (legacy) and user_id (post Dec 2025).
    income_source_type: "payroll" for payroll provider, "bank" for bank income.
    """
    if not user_token and not user_id:
        raise ValueError("Either user_token or user_id is required")

    payload: dict[str, Any] = {
        **_plaid_auth(),
        "client_name": "SirHENRY",
        "country_codes": ["US"],
        "language": "en",
        "products": ["income_verification"],
        "income_verification": {
            "income_source_types": [income_source_type],
        },
    }

    # Use user_token (legacy) or user_id (new) — not both
    if user_token:
        payload["user_token"] = user_token
        payload["user"] = {"client_user_id": "default-user"}
    else:
        payload["user_id"] = user_id

    app_url = os.getenv("NEXT_PUBLIC_APP_URL", "").rstrip("/")
    if app_url:
        payload["redirect_uri"] = f"{app_url}/oauth-redirect"

    resp = _retry_httpx_post(
        f"{_plaid_base_url()}/link/token/create",
        headers=_plaid_headers(),
        json=payload,
        timeout=30,
    )

    if not resp.is_success:
        error_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        error_msg = error_data.get("error_message", resp.text[:200])
        raise ValueError(f"Plaid link/token/create failed: {error_msg}")

    data = resp.json()
    return data["link_token"]


def get_payroll_income(user_token: str = "", user_id: str = "") -> dict[str, Any]:
    """Retrieve payroll income data (pay stubs + W-2s) after user connects.

    Supports both user_token (legacy) and user_id (post Dec 2025).
    """
    if user_token:
        # Use SDK for legacy user_token flow
        client = get_plaid_client()
        request = CreditPayrollIncomeGetRequest(user_token=user_token)
        response = _retry_on_transient(client.credit_payroll_income_get, request)
        return _normalize_payroll_response(response)
    elif user_id:
        # Use raw HTTP for new user_id flow
        resp = _retry_httpx_post(
            f"{_plaid_base_url()}/credit/payroll_income/get",
            headers=_plaid_headers(),
            json={**_plaid_auth(), "user_id": user_id},
            timeout=60,
        )
        resp.raise_for_status()
        return _normalize_payroll_response(resp.json())
    else:
        raise ValueError("Either user_token or user_id is required")


def _normalize_payroll_response(response: Any) -> dict[str, Any]:
    """Normalize Plaid payroll income response into our internal format."""
    resp_dict = response.to_dict() if hasattr(response, "to_dict") else response
    items = resp_dict.get("items", [])

    result: dict[str, Any] = {
        "pay_stubs": [],
        "w2s": [],
        "employers": [],
    }

    for item in items:
        payroll_income = item.get("payroll_income", [])
        for income in payroll_income:
            # Pay stubs
            for stub in income.get("pay_stubs", []):
                employer = stub.get("employer", {})
                earnings = stub.get("income_breakdown", [])
                deductions = stub.get("deductions", {})
                net_pay = stub.get("net_pay", {})

                result["pay_stubs"].append({
                    "pay_date": stub.get("pay_date"),
                    "pay_period_start": stub.get("pay_period_start_date"),
                    "pay_period_end": stub.get("pay_period_end_date"),
                    "pay_frequency": stub.get("pay_frequency"),
                    "gross_pay": (
                        sum(e.get("current_amount", 0) for e in earnings) if earnings else None
                    ),
                    "gross_pay_ytd": (
                        sum(e.get("ytd_amount", 0) for e in earnings) if earnings else None
                    ),
                    "net_pay": net_pay.get("current_amount"),
                    "net_pay_ytd": net_pay.get("ytd_amount"),
                    "deductions": deductions.get("breakdown", []),
                    "employer_name": employer.get("name"),
                    "employer_ein": employer.get("tax_id"),
                    "employer_address": employer.get("address"),
                })

                if employer.get("name") and employer not in result["employers"]:
                    result["employers"].append({
                        "name": employer.get("name"),
                        "ein": employer.get("tax_id"),
                        "address": employer.get("address"),
                    })

            # W-2s
            for w2 in income.get("w2s", []):
                employer = w2.get("employer", {})
                result["w2s"].append({
                    "tax_year": w2.get("tax_year"),
                    "employer_name": employer.get("name"),
                    "employer_ein": employer.get("tax_id"),
                    "wages_tips": w2.get("wages_tips_other_comp"),
                    "federal_tax_withheld": w2.get("federal_income_tax_withheld"),
                    "ss_wages": w2.get("social_security_wages"),
                    "ss_tax_withheld": w2.get("social_security_tax_withheld"),
                    "medicare_wages": w2.get("medicare_wages_and_tips"),
                    "medicare_tax_withheld": w2.get("medicare_tax_withheld"),
                    "state_wages": w2.get("state_and_local_wages", []),
                    "box_12": w2.get("box_12", []),
                    "retirement_plan": w2.get("retirement_plan"),
                })

    return result
