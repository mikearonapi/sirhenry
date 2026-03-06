"""
Action tools for Sir Henry chat — asset management, stock quotes,
Plaid sync, AI categorization, data health checks, and CRUD operations.

Each tool follows the pattern:
    async def _tool_<name>(session: AsyncSession, params: dict) -> str
returning a JSON string. Write tools use session.flush() (never commit).
"""
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import (
    Account,
    BusinessEntity,
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


# ---------------------------------------------------------------------------
# 7. Update transaction (notes, exclude/include, mark reviewed)
# ---------------------------------------------------------------------------

async def _tool_update_transaction(session: AsyncSession, params: dict) -> str:
    """Update transaction metadata: notes, is_excluded, is_manually_reviewed."""
    tid = params["transaction_id"]
    result = await session.execute(
        select(Transaction).where(Transaction.id == tid)
    )
    tx = result.scalar_one_or_none()
    if not tx:
        return json.dumps({"error": f"Transaction {tid} not found"})

    values: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    changes: list[str] = []

    if "is_excluded" in params:
        values["is_excluded"] = params["is_excluded"]
        action = "excluded from reports" if params["is_excluded"] else "re-included in reports"
        changes.append(action)

    if "notes" in params and params["notes"] is not None:
        values["notes"] = params["notes"]
        changes.append("notes updated")

    if "is_manually_reviewed" in params:
        values["is_manually_reviewed"] = params["is_manually_reviewed"]
        if params["is_manually_reviewed"]:
            changes.append("marked as manually reviewed")

    if not changes:
        return json.dumps({"error": "No changes specified"})

    await session.execute(
        update(Transaction).where(Transaction.id == tid).values(**values)
    )
    await session.flush()

    return json.dumps({
        "success": True,
        "transaction_id": tid,
        "description": tx.description,
        "amount": tx.amount,
        "date": str(tx.date)[:10],
        "changes": changes,
    })


# ---------------------------------------------------------------------------
# 8. Create manual transaction
# ---------------------------------------------------------------------------

async def _tool_create_transaction(session: AsyncSession, params: dict) -> str:
    """Create a manual transaction."""
    from pipeline.db.models import create_transaction

    # Validate account exists
    acct_result = await session.execute(
        select(Account).where(Account.id == params["account_id"])
    )
    account = acct_result.scalar_one_or_none()
    if not account:
        return json.dumps({"error": f"Account {params['account_id']} not found"})

    try:
        tx_date = datetime.strptime(params["date"], "%Y-%m-%d")
    except ValueError:
        return json.dumps({"error": f"Invalid date format: {params['date']}. Use YYYY-MM-DD."})

    segment = params.get("segment", "personal")
    category = params.get("category")

    data = {
        "account_id": params["account_id"],
        "date": tx_date,
        "description": params["description"],
        "amount": params["amount"],
        "segment": segment,
        "effective_segment": segment,
        "category": category,
        "effective_category": category,
        "notes": params.get("notes"),
        "data_source": "manual",
        "is_manually_reviewed": True,
        "period_year": tx_date.year,
        "period_month": tx_date.month,
    }

    tx = await create_transaction(session, data)

    return json.dumps({
        "success": True,
        "transaction_id": tx.id,
        "description": tx.description,
        "amount": tx.amount,
        "date": str(tx.date)[:10],
        "category": category,
        "segment": segment,
        "account": account.name,
    })


# ---------------------------------------------------------------------------
# 9. Batch exclude/include transactions
# ---------------------------------------------------------------------------

async def _tool_exclude_transactions(session: AsyncSession, params: dict) -> str:
    """Batch exclude or include transactions by IDs or query."""
    action = params["action"]
    is_excluding = action == "exclude"
    new_excluded_val = is_excluding
    reason = params.get("reason", "")

    tx_ids = params.get("transaction_ids")
    if tx_ids:
        if len(tx_ids) > 50:
            return json.dumps({"error": "Maximum 50 transactions per batch. Use query-based matching for larger sets."})
        q = select(Transaction).where(
            Transaction.id.in_(tx_ids),
            Transaction.is_excluded == (not new_excluded_val),
        )
    else:
        query_text = params.get("query")
        if not query_text:
            return json.dumps({"error": "Provide either transaction_ids or a query to match transactions"})

        q = select(Transaction).where(
            Transaction.is_excluded == (not new_excluded_val),
            Transaction.description.ilike(f"%{query_text}%"),
        )
        if params.get("year"):
            q = q.where(Transaction.period_year == params["year"])
        if params.get("month"):
            q = q.where(Transaction.period_month == params["month"])
        if params.get("account_id"):
            q = q.where(Transaction.account_id == params["account_id"])
        q = q.limit(100)

    result = await session.execute(q)
    transactions = list(result.scalars().all())

    if not transactions:
        return json.dumps({
            "success": True,
            "count": 0,
            "message": f"No matching transactions found to {action}",
        })

    now = datetime.now(timezone.utc)
    for tx in transactions:
        tx.is_excluded = new_excluded_val
        tx.updated_at = now
        if reason:
            note_prefix = f"[{now.strftime('%Y-%m-%d')}] {'Excluded' if is_excluding else 'Re-included'}: {reason}"
            tx.notes = f"{tx.notes}\n{note_prefix}" if tx.notes else note_prefix

    await session.flush()

    verb = "excluded from" if is_excluding else "re-included in"
    return json.dumps({
        "success": True,
        "count": len(transactions),
        "action": action,
        "message": f"{len(transactions)} transaction(s) {verb} reports",
        "sample": [
            {"id": tx.id, "description": tx.description, "amount": tx.amount, "date": str(tx.date)[:10]}
            for tx in transactions[:5]
        ],
    })


# ---------------------------------------------------------------------------
# 10. Manage budgets (upsert / delete)
# ---------------------------------------------------------------------------

async def _tool_manage_budget(session: AsyncSession, params: dict) -> str:
    """Create, update, or delete budget entries."""
    from pipeline.db.models import upsert_budget, delete_budget

    action = params["action"]

    if action == "delete":
        budget_id = params.get("budget_id")
        if not budget_id:
            return json.dumps({"error": "budget_id is required for delete"})
        deleted = await delete_budget(session, budget_id)
        if not deleted:
            return json.dumps({"error": f"Budget {budget_id} not found"})
        return json.dumps({"success": True, "action": "deleted", "budget_id": budget_id})

    if action == "upsert":
        for field in ("year", "month", "category", "budget_amount"):
            if field not in params or params[field] is None:
                return json.dumps({"error": f"'{field}' is required for upsert"})

        data: dict[str, Any] = {
            "year": params["year"],
            "month": params["month"],
            "category": params["category"],
            "budget_amount": params["budget_amount"],
            "segment": params.get("segment", "personal"),
        }
        if params.get("notes"):
            data["notes"] = params["notes"]

        budget = await upsert_budget(session, data)
        return json.dumps({
            "success": True,
            "action": "saved",
            "budget_id": budget.id,
            "year": budget.year,
            "month": budget.month,
            "category": budget.category,
            "budget_amount": budget.budget_amount,
            "segment": budget.segment,
        })

    return json.dumps({"error": f"Unknown action: {action}"})


# ---------------------------------------------------------------------------
# 11. Manage goals (upsert / delete)
# ---------------------------------------------------------------------------

async def _tool_manage_goal(session: AsyncSession, params: dict) -> str:
    """Create, update, or delete financial goals."""
    from pipeline.db.models import upsert_goal, delete_goal

    action = params["action"]

    if action == "delete":
        goal_id = params.get("goal_id")
        if not goal_id:
            return json.dumps({"error": "goal_id is required for delete"})
        deleted = await delete_goal(session, goal_id)
        if not deleted:
            return json.dumps({"error": f"Goal {goal_id} not found"})
        return json.dumps({"success": True, "action": "deleted", "goal_id": goal_id})

    if action == "upsert":
        data: dict[str, Any] = {}

        if params.get("goal_id"):
            data["id"] = params["goal_id"]
        else:
            if not params.get("name"):
                return json.dumps({"error": "'name' is required for new goals"})
            if not params.get("target_amount"):
                return json.dumps({"error": "'target_amount' is required for new goals"})

        for key in ("name", "goal_type", "notes", "status"):
            if params.get(key):
                data[key] = params[key]
        for key in ("target_amount", "current_amount", "monthly_contribution"):
            if params.get(key) is not None:
                data[key] = params[key]

        if params.get("target_date"):
            try:
                data["target_date"] = datetime.strptime(params["target_date"], "%Y-%m-%d")
            except ValueError:
                return json.dumps({"error": f"Invalid date: {params['target_date']}. Use YYYY-MM-DD."})

        is_new = "id" not in data
        goal = await upsert_goal(session, data)

        return json.dumps({
            "success": True,
            "action": "created" if is_new else "updated",
            "goal_id": goal.id,
            "name": goal.name,
            "target_amount": goal.target_amount,
            "current_amount": goal.current_amount,
            "target_date": str(goal.target_date)[:10] if goal.target_date else None,
            "monthly_contribution": goal.monthly_contribution,
            "status": goal.status,
        })

    return json.dumps({"error": f"Unknown action: {action}"})


# ---------------------------------------------------------------------------
# 12. Create reminder
# ---------------------------------------------------------------------------

async def _tool_create_reminder(session: AsyncSession, params: dict) -> str:
    """Create a financial reminder."""
    from pipeline.db.models import create_reminder_record

    try:
        due_date = datetime.strptime(params["due_date"], "%Y-%m-%d")
    except ValueError:
        return json.dumps({"error": f"Invalid date format: {params['due_date']}. Use YYYY-MM-DD."})

    data: dict[str, Any] = {
        "title": params["title"],
        "due_date": due_date,
        "description": params.get("description"),
        "reminder_type": params.get("reminder_type", "custom"),
        "amount": params.get("amount"),
        "advance_notice": params.get("advance_notice", "7_days"),
        "status": "pending",
    }

    reminder = await create_reminder_record(session, data)

    return json.dumps({
        "success": True,
        "reminder_id": reminder.id,
        "title": reminder.title,
        "due_date": str(reminder.due_date)[:10],
        "reminder_type": reminder.reminder_type,
        "amount": reminder.amount,
        "advance_notice": reminder.advance_notice,
    })


# ---------------------------------------------------------------------------
# 13. Update business entity profile
# ---------------------------------------------------------------------------

async def _tool_update_business_entity(session: AsyncSession, params: dict) -> str:
    """Update a business entity's profile fields through conversation."""
    from sqlalchemy import select as sa_select
    from pipeline.db.models import upsert_business_entity

    # Look up by name or ID
    entity = None
    if params.get("entity_id"):
        result = await session.execute(
            sa_select(BusinessEntity).where(BusinessEntity.id == params["entity_id"])
        )
        entity = result.scalar_one_or_none()
    elif params.get("entity_name"):
        result = await session.execute(
            sa_select(BusinessEntity).where(
                BusinessEntity.name.ilike(params["entity_name"])
            )
        )
        entity = result.scalar_one_or_none()

    if not entity:
        name = params.get("entity_name") or params.get("entity_id")
        return json.dumps({"error": f"Business entity '{name}' not found. Use create_business_entity to create a new one."})

    # Build update data — use current name as the lookup key for upsert
    data: dict[str, Any] = {"name": entity.name}
    updatable = [
        "new_name", "description", "expected_expenses", "entity_type", "tax_treatment",
        "ein", "owner", "is_provisional", "notes",
    ]
    changes: list[str] = []
    for field in updatable:
        if field in params and params[field] is not None:
            data[field] = params[field]
            changes.append(field)

    # Handle rename: update the name field directly on the ORM object
    if "new_name" in data:
        entity.name = data.pop("new_name")
        data["name"] = entity.name
        await session.flush()

    # Handle date fields
    for date_field in ("active_from", "active_to"):
        if params.get(date_field):
            try:
                data[date_field] = datetime.strptime(params[date_field], "%Y-%m-%d").date()
                changes.append(date_field)
            except ValueError:
                return json.dumps({"error": f"Invalid date format for {date_field}: {params[date_field]}. Use YYYY-MM-DD."})

    if not changes:
        return json.dumps({"error": "No fields provided to update"})

    # Append to notes rather than overwrite
    if "notes" in data and entity.notes:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        data["notes"] = f"{entity.notes}\n[{timestamp}] {data['notes']}"

    updated = await upsert_business_entity(session, data)

    # Report completeness
    missing = []
    if not updated.description:
        missing.append("description")
    if not updated.expected_expenses:
        missing.append("expected expense types")
    if not updated.owner:
        missing.append("owner")
    if not updated.ein:
        missing.append("EIN")

    return json.dumps({
        "success": True,
        "entity_id": updated.id,
        "entity_name": updated.name,
        "fields_updated": changes,
        "missing_fields": missing,
        "profile_complete": len(missing) == 0,
    })


# ---------------------------------------------------------------------------
# 14. Create business entity
# ---------------------------------------------------------------------------

async def _tool_create_business_entity(session: AsyncSession, params: dict) -> str:
    """Create a new business entity through conversation."""
    from pipeline.db.models import upsert_business_entity

    name = params.get("name")
    if not name:
        return json.dumps({"error": "'name' is required to create a business entity"})

    data: dict[str, Any] = {"name": name}
    for field in [
        "description", "expected_expenses", "entity_type", "tax_treatment",
        "ein", "owner", "is_provisional", "notes",
    ]:
        if params.get(field) is not None:
            data[field] = params[field]

    for date_field in ("active_from", "active_to"):
        if params.get(date_field):
            try:
                data[date_field] = datetime.strptime(params[date_field], "%Y-%m-%d").date()
            except ValueError:
                return json.dumps({"error": f"Invalid date format for {date_field}. Use YYYY-MM-DD."})

    entity = await upsert_business_entity(session, data)

    missing = []
    if not entity.description:
        missing.append("description")
    if not entity.expected_expenses:
        missing.append("expected expense types")
    if not entity.owner:
        missing.append("owner")
    if not entity.ein:
        missing.append("EIN")

    return json.dumps({
        "success": True,
        "entity_id": entity.id,
        "entity_name": entity.name,
        "entity_type": entity.entity_type,
        "tax_treatment": entity.tax_treatment,
        "missing_fields": missing,
        "profile_complete": len(missing) == 0,
        "hint": "Ask follow-up questions to complete the profile" if missing else "Profile is complete",
    })


# ---------------------------------------------------------------------------
# 15. Save user context (learned fact)
# ---------------------------------------------------------------------------

async def _tool_save_user_context(session: AsyncSession, params: dict) -> str:
    """Save or update a learned fact about the user."""
    from pipeline.db.models import upsert_user_context

    category = params.get("category")
    key = params.get("key")
    value = params.get("value")

    if not all([category, key, value]):
        return json.dumps({"error": "category, key, and value are all required"})

    valid_categories = [
        "business", "tax", "preference", "household",
        "financial_goal", "investment", "career",
    ]
    if category not in valid_categories:
        return json.dumps({"error": f"Invalid category. Must be one of: {', '.join(valid_categories)}"})

    ctx = await upsert_user_context(session, {
        "category": category,
        "key": key,
        "value": value,
        "source": "chat",
        "confidence": 1.0,
    })

    return json.dumps({
        "success": True,
        "context_id": ctx.id,
        "category": ctx.category,
        "key": ctx.key,
        "value": ctx.value,
        "remembered": True,
    })


# ---------------------------------------------------------------------------
# 16. Get user context (retrieve learned facts)
# ---------------------------------------------------------------------------

async def _tool_get_user_context(session: AsyncSession, params: dict) -> str:
    """Retrieve stored user context facts."""
    from pipeline.db.models import get_active_user_context

    category = params.get("category")
    facts = await get_active_user_context(session, category=category)

    items = [
        {
            "id": f.id,
            "category": f.category,
            "key": f.key,
            "value": f.value,
            "source": f.source,
        }
        for f in facts
    ]

    return json.dumps({
        "count": len(items),
        "facts": items,
    })
