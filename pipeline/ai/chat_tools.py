"""
Action tools for Sir Henry chat — asset management, stock quotes,
Plaid sync, AI categorization, and data health checks.

Each tool follows the pattern:
    async def _tool_<name>(session: AsyncSession, params: dict) -> str
returning a JSON string. Write tools use session.flush() (never commit).
"""
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import (
    Account,
    ManualAsset,
    NetWorthSnapshot,
    PlaidAccount,
    PlaidItem,
    Transaction,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. List manual assets
# ---------------------------------------------------------------------------

async def _tool_list_manual_assets(session: AsyncSession, params: dict) -> str:
    """List all active manual assets/liabilities with optional type filter."""
    q = select(ManualAsset).where(ManualAsset.is_active == True)

    asset_type = params.get("asset_type")
    if asset_type:
        q = q.where(ManualAsset.asset_type == asset_type)

    q = q.order_by(ManualAsset.asset_type, ManualAsset.name)
    result = await session.execute(q)
    assets = list(result.scalars().all())

    items = []
    total_assets = 0.0
    total_liabilities = 0.0

    for a in assets:
        val = a.current_value or 0.0
        if a.is_liability:
            total_liabilities += val
        else:
            total_assets += val

        items.append({
            "id": a.id,
            "name": a.name,
            "asset_type": a.asset_type,
            "is_liability": a.is_liability,
            "current_value": val,
            "as_of_date": str(a.as_of_date)[:10] if a.as_of_date else None,
            "institution": a.institution,
            "owner": a.owner,
            "notes": a.notes,
        })

    return json.dumps({
        "count": len(items),
        "total_assets": round(total_assets, 2),
        "total_liabilities": round(total_liabilities, 2),
        "net": round(total_assets - total_liabilities, 2),
        "assets": items,
    })


# ---------------------------------------------------------------------------
# 2. Update asset value
# ---------------------------------------------------------------------------

async def _tool_update_asset_value(session: AsyncSession, params: dict) -> str:
    """Update the current value of a manual asset."""
    asset_id = params["asset_id"]
    new_value = params["new_value"]
    notes = params.get("notes", "")

    result = await session.execute(
        select(ManualAsset).where(ManualAsset.id == asset_id)
    )
    asset = result.scalar_one_or_none()

    if not asset:
        return json.dumps({"error": f"Manual asset {asset_id} not found"})
    if not asset.is_active:
        return json.dumps({"error": f"Asset '{asset.name}' is inactive"})

    old_value = asset.current_value
    now = datetime.now(timezone.utc)

    asset.current_value = new_value
    asset.as_of_date = now

    # Append note with timestamp
    if notes:
        timestamp = now.strftime("%Y-%m-%d")
        new_note = f"[{timestamp}] {notes}"
        if asset.notes:
            asset.notes = f"{asset.notes}\n{new_note}"
        else:
            asset.notes = new_note

    await session.flush()

    return json.dumps({
        "success": True,
        "asset_name": asset.name,
        "asset_type": asset.asset_type,
        "old_value": old_value,
        "new_value": new_value,
        "change": round(new_value - (old_value or 0), 2),
        "as_of_date": str(now)[:10],
    })


# ---------------------------------------------------------------------------
# 3. Stock quote
# ---------------------------------------------------------------------------

async def _tool_get_stock_quote(session: AsyncSession, params: dict) -> str:
    """Fetch real-time stock quote via Yahoo Finance."""
    ticker = params["ticker"].upper().strip()

    try:
        from pipeline.market.yahoo_finance import YahooFinanceService
        loop = asyncio.get_event_loop()
        quote = await loop.run_in_executor(None, YahooFinanceService.get_quote, ticker)
    except Exception as e:
        logger.warning(f"Stock quote failed for {ticker}: {e}")
        return json.dumps({"error": f"Could not fetch quote for {ticker}: {str(e)}"})

    if not quote:
        return json.dumps({"error": f"No data found for ticker {ticker}"})

    return json.dumps(quote)


# ---------------------------------------------------------------------------
# 4. Trigger Plaid sync
# ---------------------------------------------------------------------------

async def _tool_trigger_plaid_sync(session: AsyncSession, params: dict) -> str:
    """Sync transactions and balances from connected Plaid institutions."""
    institution = params.get("institution")

    q = select(PlaidItem).where(PlaidItem.status == "active")
    if institution:
        q = q.where(PlaidItem.institution_name.ilike(f"%{institution}%"))

    result = await session.execute(q)
    items = list(result.scalars().all())

    if not items:
        msg = f"No active Plaid items found"
        if institution:
            msg += f" matching '{institution}'"
        return json.dumps({"error": msg})

    from pipeline.plaid.sync import sync_item, snapshot_net_worth

    total_added = 0
    total_updated = 0
    synced_institutions: list[str] = []

    for item in items:
        if not item.access_token:
            continue
        try:
            added, updated = await asyncio.wait_for(
                sync_item(session, item), timeout=60
            )
            item.last_synced_at = datetime.now(timezone.utc)
            item.status = "active"
            total_added += added
            total_updated += updated
            synced_institutions.append(item.institution_name or "Unknown")
        except asyncio.TimeoutError:
            logger.warning(f"Sync timed out for {item.institution_name}")
            item.status = "error"
            item.error_code = "sync_timeout"
        except Exception as e:
            logger.error(f"Sync failed for {item.institution_name}: {e}")
            item.status = "error"
            item.error_code = str(e)[:100]

    # Net worth snapshot
    try:
        await asyncio.wait_for(snapshot_net_worth(session), timeout=30)
    except Exception as e:
        logger.warning(f"Post-sync net worth snapshot failed: {e}")

    await session.flush()

    return json.dumps({
        "items_synced": len(synced_institutions),
        "institutions": synced_institutions,
        "transactions_added": total_added,
        "accounts_updated": total_updated,
    })


# ---------------------------------------------------------------------------
# 5. Run AI categorization
# ---------------------------------------------------------------------------

async def _tool_run_categorization(session: AsyncSession, params: dict) -> str:
    """Run AI categorization on uncategorized transactions."""
    year = params.get("year")
    month = params.get("month")

    try:
        from pipeline.ai.categorizer import categorize_transactions
        result = await asyncio.wait_for(
            categorize_transactions(session, year=year, month=month),
            timeout=120,
        )
        return json.dumps(result)
    except asyncio.TimeoutError:
        return json.dumps({"error": "Categorization timed out after 120 seconds"})
    except Exception as e:
        logger.error(f"Categorization failed: {e}")
        return json.dumps({"error": f"Categorization failed: {str(e)}"})


# ---------------------------------------------------------------------------
# 6. Data health check
# ---------------------------------------------------------------------------

async def _tool_get_data_health(session: AsyncSession, params: dict) -> str:
    """Comprehensive data quality diagnostic."""
    now = datetime.now(timezone.utc)
    gaps: list[str] = []

    # --- Accounts ---
    acct_result = await session.execute(
        select(
            Account.data_source,
            func.count(Account.id),
        ).where(Account.is_active == True).group_by(Account.data_source)
    )
    acct_by_source = {row[0]: row[1] for row in acct_result.all()}
    total_accounts = sum(acct_by_source.values())

    # Accounts with zero transactions
    empty_acct_result = await session.execute(
        select(Account.id, Account.name, Account.institution).where(
            Account.is_active == True,
        )
    )
    empty_accounts = []
    for acct_row in empty_acct_result.all():
        tx_count_result = await session.execute(
            select(func.count(Transaction.id)).where(
                Transaction.account_id == acct_row[0],
                Transaction.is_excluded == False,
            )
        )
        if (tx_count_result.scalar() or 0) == 0:
            empty_accounts.append({"id": acct_row[0], "name": acct_row[1], "institution": acct_row[2]})

    if empty_accounts:
        names = ", ".join(a["name"] for a in empty_accounts[:5])
        gaps.append(f"{len(empty_accounts)} account(s) with zero transactions: {names}")

    # --- Transactions ---
    tx_total_result = await session.execute(
        select(func.count(Transaction.id)).where(Transaction.is_excluded == False)
    )
    total_transactions = tx_total_result.scalar() or 0

    uncat_result = await session.execute(
        select(func.count(Transaction.id)).where(
            Transaction.is_excluded == False,
            Transaction.effective_category.is_(None),
        )
    )
    uncategorized = uncat_result.scalar() or 0
    if uncategorized > 0:
        gaps.append(f"{uncategorized:,} uncategorized transactions")

    low_conf_result = await session.execute(
        select(func.count(Transaction.id)).where(
            Transaction.is_excluded == False,
            Transaction.ai_confidence.isnot(None),
            Transaction.ai_confidence < 0.7,
            Transaction.is_manually_reviewed == False,
        )
    )
    low_confidence = low_conf_result.scalar() or 0
    if low_confidence > 0:
        gaps.append(f"{low_confidence:,} low-confidence AI categorizations (< 70%)")

    # --- Plaid items ---
    plaid_result = await session.execute(
        select(PlaidItem).where(PlaidItem.status != "removed")
    )
    plaid_items = list(plaid_result.scalars().all())

    plaid_status = []
    for pi in plaid_items:
        hours_since = None
        stale = False
        if pi.last_synced_at:
            try:
                sync_aware = pi.last_synced_at if pi.last_synced_at.tzinfo else pi.last_synced_at.replace(tzinfo=timezone.utc)
                hours_since = round((now - sync_aware).total_seconds() / 3600, 1)
                stale = hours_since > 24
            except Exception:
                pass

        if pi.status == "error":
            gaps.append(f"Plaid connection error: {pi.institution_name} ({pi.error_code or 'unknown'})")
        elif stale:
            gaps.append(f"{pi.institution_name} last synced {hours_since:.0f}h ago (stale)")

        plaid_status.append({
            "institution": pi.institution_name,
            "status": pi.status,
            "last_synced": str(pi.last_synced_at)[:19] if pi.last_synced_at else None,
            "hours_since_sync": hours_since,
            "stale": stale,
        })

    # --- Manual assets ---
    ma_result = await session.execute(
        select(ManualAsset).where(ManualAsset.is_active == True)
    )
    manual_assets = list(ma_result.scalars().all())

    stale_threshold = now - timedelta(days=90)
    stale_assets = []
    for ma in manual_assets:
        if not ma.as_of_date or ma.as_of_date.replace(tzinfo=timezone.utc) < stale_threshold:
            stale_assets.append(ma.name)

    if stale_assets:
        names = ", ".join(stale_assets[:5])
        suffix = f" (+{len(stale_assets) - 5} more)" if len(stale_assets) > 5 else ""
        gaps.append(f"{len(stale_assets)} manual asset(s) with stale values (90+ days): {names}{suffix}")

    # --- Net worth ---
    nw_result = await session.execute(
        select(NetWorthSnapshot).order_by(NetWorthSnapshot.snapshot_date.desc()).limit(1)
    )
    latest_nw = nw_result.scalar_one_or_none()

    return json.dumps({
        "accounts": {
            "total_active": total_accounts,
            "by_source": acct_by_source,
            "empty_accounts": empty_accounts,
        },
        "transactions": {
            "total": total_transactions,
            "uncategorized": uncategorized,
            "low_confidence": low_confidence,
        },
        "plaid": plaid_status,
        "manual_assets": {
            "total": len(manual_assets),
            "stale_count": len(stale_assets),
            "stale_names": stale_assets,
        },
        "net_worth": {
            "latest_date": str(latest_nw.snapshot_date)[:10] if latest_nw else None,
            "net_worth": latest_nw.net_worth if latest_nw else None,
            "total_assets": latest_nw.total_assets if latest_nw else None,
            "total_liabilities": latest_nw.total_liabilities if latest_nw else None,
        },
        "gaps": gaps,
        "gap_count": len(gaps),
    })
