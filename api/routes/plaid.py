"""Plaid Link flow, sync, item management, and update mode endpoints."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.database import AsyncSessionLocal, get_session
from api.models.schemas import ExchangeTokenIn, PlaidAccountOut, PlaidItemOut
from pipeline.db import PlaidAccount, PlaidItem
from pipeline.db.schema import Account
from pipeline.db.encryption import decrypt_token, encrypt_token
from pipeline.plaid.client import (
    create_link_token, exchange_public_token, get_accounts, remove_item,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/plaid", tags=["plaid"])


async def _find_matching_account(
    session: AsyncSession,
    acct_data: dict[str, Any],
    institution_name: str,
) -> Account | None:
    """Multi-strategy account matcher for Plaid linking.

    Tries in order of confidence:
    1. last_four + institution (exact)
    2. name/official_name + institution (fuzzy substring)
    3. subtype + institution (unique match only)
    """
    # Strategy 1: last_four + institution (highest confidence)
    mask = acct_data.get("mask")
    if mask:
        result = await session.execute(
            select(Account).where(
                Account.is_active.is_(True),
                Account.last_four == mask,
                Account.institution.ilike(f"%{institution_name}%"),
                Account.data_source != "plaid",
            )
        )
        match = result.scalar_one_or_none()
        if match:
            return match

    # Strategy 2: name similarity + institution
    plaid_name = (acct_data.get("name") or "").lower().strip()
    plaid_official = (acct_data.get("official_name") or "").lower().strip()
    if plaid_name and institution_name:
        result = await session.execute(
            select(Account).where(
                Account.is_active.is_(True),
                Account.institution.ilike(f"%{institution_name}%"),
                Account.data_source != "plaid",
            )
        )
        candidates = list(result.scalars().all())
        for candidate in candidates:
            c_name = candidate.name.lower().strip()
            if (c_name == plaid_name
                    or c_name in plaid_name or plaid_name in c_name
                    or (plaid_official and (c_name == plaid_official or c_name in plaid_official))):
                return candidate

    # Strategy 3: only-account-of-subtype at institution
    plaid_subtype = acct_data.get("subtype", "")
    if institution_name and plaid_subtype:
        result = await session.execute(
            select(Account).where(
                Account.is_active.is_(True),
                Account.institution.ilike(f"%{institution_name}%"),
                Account.subtype == plaid_subtype,
                Account.data_source != "plaid",
            )
        )
        candidates = list(result.scalars().all())
        if len(candidates) == 1:
            return candidates[0]

    return None


async def _initial_sync_and_dedup(item_id: int, merged_account_ids: list[int]) -> None:
    """Background task: sync the new item's transactions, then dedup merged accounts."""
    async with AsyncSessionLocal() as s:
        async with s.begin():
            result = await s.execute(
                select(PlaidItem).where(PlaidItem.id == item_id)
            )
            item = result.scalar_one_or_none()
            if not item or not item.access_token:
                return

            item.sync_phase = "syncing"

            try:
                from pipeline.plaid.sync import sync_item, snapshot_net_worth
                added, updated = await sync_item(s, item)
                item.last_synced_at = datetime.now(timezone.utc)
                item.status = "active"
                logger.info(
                    f"Initial sync for {item.institution_name}: "
                    f"{added} transactions, {updated} accounts"
                )
            except Exception as e:
                logger.error(f"Initial sync failed for {item.institution_name}: {e}")
                item.status = "error"
                item.error_code = str(e)[:100]
                item.sync_phase = "error"
                return

            # AI categorization for new transactions
            if added > 0:
                item.sync_phase = "categorizing"
                try:
                    from pipeline.ai.categorizer import categorize_transactions
                    await asyncio.wait_for(categorize_transactions(s), timeout=120)
                except Exception as e:
                    logger.warning(f"Post-link categorization failed: {e}")

            # Auto-dedup merged accounts (Plaid vs CSV overlapping transactions)
            if merged_account_ids:
                from pipeline.dedup.cross_source import auto_resolve_duplicates
                for account_id in merged_account_ids:
                    try:
                        dedup_result = await auto_resolve_duplicates(s, account_id, min_confidence=0.8)
                        logger.info(f"Post-link dedup for account {account_id}: {dedup_result}")
                    except Exception as e:
                        logger.warning(f"Post-link dedup failed for account {account_id}: {e}")

            # Net worth snapshot
            try:
                await asyncio.wait_for(snapshot_net_worth(s), timeout=30)
            except Exception as e:
                logger.warning(f"Post-link net worth snapshot failed: {e}")

            item.sync_phase = "complete"


@router.get("/link-token")
async def get_link_token():
    """Generate a Plaid Link token for the frontend to initialize Link."""
    try:
        token = create_link_token()
        return {"link_token": token}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plaid error: {e}")


@router.get("/link-token/update/{item_id}")
async def get_update_link_token(
    item_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Generate a Link token in update mode for re-authenticating an existing Item.
    Used when an Item enters ITEM_LOGIN_REQUIRED or PENDING_DISCONNECT state."""
    result = await session.execute(
        select(PlaidItem).where(PlaidItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Plaid item not found")
    try:
        access_token = decrypt_token(item.access_token)
        token = create_link_token(access_token=access_token)
        return {"link_token": token}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plaid error: {e}")


@router.post("/exchange-token")
async def exchange_token(
    body: ExchangeTokenIn,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Exchange a public token from Plaid Link for a permanent access token.

    After linking, schedules a background sync to immediately pull transactions
    and auto-dedup any accounts that were merged with existing CSV/manual accounts.
    """
    # S-5: Duplicate Item prevention — reject if institution already linked
    existing = await session.execute(
        select(PlaidItem).where(
            PlaidItem.institution_name == body.institution_name,
            PlaidItem.status != "removed",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"{body.institution_name} is already connected. "
            "Remove it first if you want to re-link.",
        )

    try:
        result = exchange_public_token(body.public_token)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {e}")

    item = PlaidItem(
        item_id=result["item_id"],
        access_token=encrypt_token(result["access_token"]),
        institution_name=body.institution_name,
        status="active",
        sync_phase="syncing",
    )
    session.add(item)
    await session.flush()

    merged_account_ids: list[int] = []
    accounts_created = 0

    try:
        accounts = get_accounts(result["access_token"])
        from pipeline.db import upsert_account
        for acct_data in accounts:
            existing_match = await _find_matching_account(
                session, acct_data, body.institution_name,
            )

            if existing_match:
                # Link Plaid to existing account, upgrade its source
                existing_match.data_source = "plaid"
                existing_match.institution = body.institution_name
                if acct_data.get("mask") and not existing_match.last_four:
                    existing_match.last_four = acct_data["mask"]
                our_account = existing_match
                merged_account_ids.append(our_account.id)
                logger.info(
                    f"Smart-linked Plaid account to existing: "
                    f"{our_account.name} (id={our_account.id})"
                )
            else:
                our_account = await upsert_account(session, {
                    "name": acct_data["name"],
                    "account_type": "personal",
                    "subtype": acct_data["subtype"],
                    "institution": body.institution_name,
                    "last_four": acct_data.get("mask"),
                    "data_source": "plaid",
                })
                accounts_created += 1

            pa = PlaidAccount(
                plaid_item_id=item.id,
                account_id=our_account.id,
                **acct_data,
            )
            session.add(pa)
    except Exception as e:
        logger.warning(f"Failed to fetch initial accounts: {e}")

    # Schedule background sync to pull transactions immediately
    background_tasks.add_task(_initial_sync_and_dedup, item.id, merged_account_ids)

    return {
        "id": item.id,
        "item_id": result["item_id"],
        "status": "connected",
        "sync_status": "started",
        "accounts_matched": len(merged_account_ids),
        "accounts_created": accounts_created,
    }


@router.get("/sync-status/{item_id}")
async def sync_status(
    item_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Lightweight endpoint for polling sync progress after linking a new institution."""
    result = await session.execute(
        select(PlaidItem).where(PlaidItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Plaid item not found")
    return {
        "id": item.id,
        "status": item.status,
        "sync_phase": item.sync_phase,
        "last_synced_at": str(item.last_synced_at) if item.last_synced_at else None,
        "error_code": item.error_code,
    }


@router.get("/items", response_model=list[PlaidItemOut])
async def list_items(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(PlaidItem)
        .where(PlaidItem.status != "removed")
        .options(selectinload(PlaidItem.plaid_accounts))
    )
    items = list(result.scalars().all())
    return [
        PlaidItemOut(
            id=item.id,
            institution_name=item.institution_name,
            status=item.status,
            last_synced_at=str(item.last_synced_at) if item.last_synced_at else None,
            account_count=len(item.plaid_accounts),
        )
        for item in items
    ]


@router.delete("/items/{item_id}")
async def delete_item(
    item_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Disconnect an institution — revokes the Plaid access token and marks the Item removed."""
    result = await session.execute(
        select(PlaidItem).where(PlaidItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Plaid item not found")

    try:
        access_token = decrypt_token(item.access_token)
        remove_item(access_token)
        logger.info(f"Revoked Plaid access token for {item.institution_name}")
    except Exception as e:
        logger.warning(f"Plaid /item/remove call failed (marking removed anyway): {e}")

    item.status = "removed"
    item.access_token = ""
    await session.flush()
    return {"status": "removed", "institution": item.institution_name}


@router.post("/sync")
async def sync_plaid(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Trigger a sync of all connected Plaid items."""
    async def _sync():
        async with AsyncSessionLocal() as s:
            async with s.begin():
                from pipeline.plaid.sync import sync_all_items
                result = await sync_all_items(s, run_categorize=True)
                logger.info(f"Plaid sync complete: {result}")

    background_tasks.add_task(_sync)
    return {"status": "sync_started"}


@router.get("/accounts", response_model=list[PlaidAccountOut])
async def list_plaid_accounts(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(PlaidAccount))
    accounts = list(result.scalars().all())
    return [PlaidAccountOut.model_validate(a) for a in accounts]


@router.get("/health")
async def plaid_health(session: AsyncSession = Depends(get_session)):
    """Diagnostic: returns sync status, balance summary, and staleness per Plaid item."""
    items_result = await session.execute(
        select(PlaidItem)
        .where(PlaidItem.status != "removed")
        .options(selectinload(PlaidItem.plaid_accounts))
    )
    items = list(items_result.scalars().all())
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    report = []
    total_assets = 0.0
    total_liabilities = 0.0

    for item in items:
        accts = item.plaid_accounts

        item_assets = sum((a.current_balance or 0) for a in accts if a.type in ("depository", "investment"))
        item_liabilities = sum(abs(a.current_balance or 0) for a in accts if a.type in ("credit", "loan"))
        total_assets += item_assets
        total_liabilities += item_liabilities

        last_sync = item.last_synced_at
        hours_since_sync = None
        if last_sync:
            try:
                sync_aware = last_sync if last_sync.tzinfo else last_sync.replace(tzinfo=timezone.utc)
                delta = now - sync_aware
                hours_since_sync = round(delta.total_seconds() / 3600, 1)
            except Exception:
                pass

        report.append({
            "id": item.id,
            "institution": item.institution_name,
            "status": item.status,
            "last_synced_at": str(last_sync) if last_sync else None,
            "hours_since_sync": hours_since_sync,
            "stale": hours_since_sync is not None and hours_since_sync > 24,
            "account_count": len(accts),
            "accounts": [
                {
                    "name": a.name,
                    "type": a.type,
                    "subtype": a.subtype,
                    "current_balance": a.current_balance,
                    "available_balance": a.available_balance,
                }
                for a in accts
            ],
            "total_assets": round(item_assets, 2),
            "total_liabilities": round(item_liabilities, 2),
        })

    return {
        "items": report,
        "summary": {
            "total_items": len(items),
            "total_accounts": sum(i["account_count"] for i in report),
            "total_assets": round(total_assets, 2),
            "total_liabilities": round(total_liabilities, 2),
            "net_balance": round(total_assets - total_liabilities, 2),
            "any_stale": any(i["stale"] for i in report),
        },
    }
