"""
Plaid API client wrapper.
Handles: link token creation, public token exchange, account/balance sync,
transaction sync, item removal, and Link update mode.
"""
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv
import plaid
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.item_remove_request import ItemRemoveRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.link_token_transactions import LinkTokenTransactions

load_dotenv()
logger = logging.getLogger(__name__)

PLAID_ENV_MAP = {
    "sandbox": plaid.Environment.Sandbox,
    "development": plaid.Environment.Sandbox,  # plaid-python >=27 removed Development; use Sandbox for dev
    "production": plaid.Environment.Production,
}

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.5  # seconds


def _retry_on_transient(func, *args, **kwargs):
    """Retry a Plaid API call on transient errors (network, rate-limit, internal)."""
    for attempt in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except plaid.ApiException as e:
            error_code = ""
            try:
                body = json.loads(e.body) if e.body else {}
                error_code = body.get("error_code", "")
            except (json.JSONDecodeError, AttributeError):
                pass

            retriable = (
                e.status in (429, 500, 503)
                or error_code in ("INTERNAL_SERVER_ERROR", "PLANNED_MAINTENANCE")
            )
            if retriable and attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.warning(
                    f"Plaid transient error (attempt {attempt + 1}/{MAX_RETRIES}, "
                    f"status={e.status}, code={error_code}), retrying in {wait:.1f}s"
                )
                time.sleep(wait)
                continue
            raise


def get_plaid_client() -> plaid_api.PlaidApi:
    env_str = os.getenv("PLAID_ENV", "sandbox")
    configuration = plaid.Configuration(
        host=PLAID_ENV_MAP.get(env_str, plaid.Environment.Sandbox),
        api_key={
            "clientId": os.getenv("PLAID_CLIENT_ID", ""),
            "secret": os.getenv("PLAID_SECRET", ""),
        },
    )
    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)


def create_link_token(
    user_id: str = "default-user",
    access_token: Optional[str] = None,
) -> str:
    """Create a Plaid Link token.

    If access_token is provided, creates an update-mode token for re-authenticating
    an existing Item (no products needed). Otherwise creates a new-link token.

    redirect_uri is required for OAuth-flow institutions (Capital One, Chase, etc.).
    It must be registered in the Plaid dashboard under Allowed Redirect URIs.
    """
    client = get_plaid_client()
    kwargs: dict[str, Any] = {
        "client_name": "SirHENRY",
        "country_codes": [CountryCode("US")],
        "language": "en",
        "user": LinkTokenCreateRequestUser(client_user_id=user_id),
    }

    # OAuth redirect URI — required for Capital One, Chase, and other OAuth-flow banks.
    # Falls back gracefully if not set (non-OAuth banks will still work).
    app_url = os.getenv("NEXT_PUBLIC_APP_URL", "").rstrip("/")
    if app_url:
        kwargs["redirect_uri"] = f"{app_url}/oauth-redirect"

    if access_token:
        kwargs["access_token"] = access_token
    else:
        kwargs["products"] = [Products("transactions")]
        kwargs["optional_products"] = [Products("investments"), Products("liabilities")]
        kwargs["transactions"] = LinkTokenTransactions(days_requested=730)

    request = LinkTokenCreateRequest(**kwargs)
    response = _retry_on_transient(client.link_token_create, request)
    return response["link_token"]


def exchange_public_token(public_token: str) -> dict[str, str]:
    """Exchange a public token (from Link) for a permanent access token."""
    client = get_plaid_client()
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = _retry_on_transient(client.item_public_token_exchange, request)
    return {
        "access_token": response["access_token"],
        "item_id": response["item_id"],
    }


def remove_item(access_token: str) -> bool:
    """Revoke an access token and remove the Item from Plaid.
    Returns True on success, raises on failure."""
    client = get_plaid_client()
    request = ItemRemoveRequest(access_token=access_token)
    response = _retry_on_transient(client.item_remove, request)
    return response.get("removed", False)


def get_accounts(access_token: str) -> list[dict[str, Any]]:
    """Fetch account details and current balances."""
    client = get_plaid_client()
    request = AccountsGetRequest(access_token=access_token)
    response = _retry_on_transient(client.accounts_get, request)

    accounts = []
    for acct in response["accounts"]:
        accounts.append({
            "plaid_account_id": acct["account_id"],
            "name": acct["name"],
            "official_name": acct.get("official_name"),
            "type": str(acct["type"]),
            "subtype": str(acct.get("subtype", "")),
            "current_balance": acct["balances"]["current"],
            "available_balance": acct["balances"].get("available"),
            "limit_balance": acct["balances"].get("limit"),
            "iso_currency": acct["balances"].get("iso_currency_code", "USD"),
            "mask": acct.get("mask"),
            "last_updated": datetime.now(timezone.utc),
        })
    return accounts


class TransactionsSyncMutationError(Exception):
    """Raised when Plaid reports TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION."""


def sync_transactions(
    access_token: str,
    cursor: Optional[str] = None,
) -> dict[str, Any]:
    """
    Fetch new/updated/removed transactions using /transactions/sync.
    Returns {added, modified, removed, next_cursor}.

    Handles TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION by restarting the
    pagination loop from the original cursor (per Plaid docs).
    """
    client = get_plaid_client()

    for _pagination_attempt in range(3):
        all_added = []
        all_modified = []
        all_removed = []
        has_more = True
        next_cursor = cursor
        mutation_error = False

        while has_more:
            kwargs: dict[str, Any] = {"access_token": access_token}
            if next_cursor:
                kwargs["cursor"] = next_cursor
            request = TransactionsSyncRequest(**kwargs)

            try:
                response = _retry_on_transient(client.transactions_sync, request)
            except plaid.ApiException as e:
                error_code = ""
                try:
                    body = json.loads(e.body) if e.body else {}
                    error_code = body.get("error_code", "")
                except (json.JSONDecodeError, AttributeError):
                    pass
                if error_code == "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION":
                    logger.warning("Pagination mutation detected, restarting sync loop")
                    mutation_error = True
                    break
                raise

            all_added.extend(response.get("added", []))
            all_modified.extend(response.get("modified", []))
            all_removed.extend(response.get("removed", []))
            has_more = response.get("has_more", False)
            next_cursor = response.get("next_cursor")

        if not mutation_error:
            break
    else:
        raise TransactionsSyncMutationError(
            "Pagination mutation persisted after 3 attempts"
        )

    return {
        "added": [_normalize_transaction(t) for t in all_added],
        "modified": [_normalize_transaction(t) for t in all_modified],
        "removed": [t.get("transaction_id") for t in all_removed],
        "next_cursor": next_cursor,
    }


def _parse_date(val: Any) -> Optional[datetime]:
    """Parse a date value from Plaid (date object, string, or None)."""
    if val is None:
        return None
    if hasattr(val, "strftime"):
        return datetime.combine(val, datetime.min.time())
    try:
        return datetime.strptime(str(val), "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _normalize_transaction(tx: Any) -> dict[str, Any]:
    """Convert a Plaid transaction object to our internal Transaction format,
    capturing all enriched fields (merchant, PFC category, location, counterparties)."""
    tx_dict = tx if isinstance(tx, dict) else tx.to_dict()
    amount = tx_dict.get("amount", 0)
    # Plaid: positive = money leaving account (debit), negative = credit
    normalized_amount = -amount

    tx_date = _parse_date(tx_dict.get("date")) or _parse_date(tx_dict.get("authorized_date"))
    if tx_date is None:
        tx_date = datetime.now(timezone.utc)

    authorized_date = _parse_date(tx_dict.get("authorized_date"))

    description = tx_dict.get("name", "") or tx_dict.get("merchant_name", "")
    merchant_name = tx_dict.get("merchant_name")
    plaid_tx_id = tx_dict.get("transaction_id", "")

    # Personal finance category (structured categorization from Plaid)
    pfc = tx_dict.get("personal_finance_category") or {}
    if hasattr(pfc, "to_dict"):
        pfc = pfc.to_dict()

    # Location data
    location = tx_dict.get("location") or {}
    if hasattr(location, "to_dict"):
        location = location.to_dict()
    location_clean = {k: v for k, v in location.items() if v is not None} if location else {}

    # Counterparties (merchant/institution entities)
    counterparties_raw = tx_dict.get("counterparties") or []
    counterparties = []
    for cp in counterparties_raw:
        cp_dict = cp.to_dict() if hasattr(cp, "to_dict") else (cp if isinstance(cp, dict) else {})
        counterparties.append({
            "name": cp_dict.get("name"),
            "type": cp_dict.get("type"),
            "website": cp_dict.get("website"),
            "logo_url": cp_dict.get("logo_url"),
            "entity_id": cp_dict.get("entity_id"),
            "confidence_level": cp_dict.get("confidence_level"),
        })

    return {
        "plaid_transaction_id": plaid_tx_id,
        "plaid_account_id": tx_dict.get("account_id"),
        "date": tx_date,
        "authorized_date": authorized_date,
        "description": description,
        "merchant_name": merchant_name,
        "amount": normalized_amount,
        "currency": tx_dict.get("iso_currency_code", "USD"),
        "period_month": tx_date.month,
        "period_year": tx_date.year,
        "transaction_hash": hashlib.sha256(plaid_tx_id.encode()).hexdigest(),
        "payment_channel": tx_dict.get("payment_channel"),
        "plaid_pfc_primary": pfc.get("primary"),
        "plaid_pfc_detailed": pfc.get("detailed"),
        "plaid_pfc_confidence": pfc.get("confidence_level"),
        "merchant_logo_url": tx_dict.get("logo_url"),
        "merchant_website": tx_dict.get("website"),
        "plaid_location_json": json.dumps(location_clean) if location_clean else None,
        "plaid_counterparties_json": json.dumps(counterparties) if counterparties else None,
        "plaid_category": json.dumps(tx_dict.get("category", [])),
        "plaid_merchant": merchant_name,
        "pending": tx_dict.get("pending", False),
    }
