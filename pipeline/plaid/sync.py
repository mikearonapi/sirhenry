"""
Plaid sync orchestrator.
Syncs all connected PlaidItems: updates account balances, imports new transactions,
removes deleted ones, triggers AI categorization, recomputes period summaries.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func as sqlfunc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db import (
    InvestmentHolding, ManualAsset, NetWorthSnapshot, PlaidAccount, PlaidItem,
    Transaction, bulk_create_transactions, upsert_account,
)
from pipeline.db.encryption import decrypt_token
from pipeline.plaid.client import get_accounts, get_investment_holdings, sync_transactions

logger = logging.getLogger(__name__)


async def sync_all_items(session: AsyncSession, run_categorize: bool = True) -> dict[str, Any]:
    """Sync all active PlaidItems. Returns a summary."""
    result = await session.execute(
        select(PlaidItem).where(PlaidItem.status == "active")
    )
    items = list(result.scalars().all())

    if not items:
        logger.info("No active Plaid items to sync.")
        return {"items_synced": 0, "transactions_added": 0, "accounts_updated": 0}

    total_added = 0
    total_updated_accounts = 0

    for item in items:
        try:
            added, updated = await sync_item(session, item)
            total_added += added
            total_updated_accounts += updated
            item.last_synced_at = datetime.now(timezone.utc)
            item.status = "active"
        except Exception as e:
            logger.error(f"Sync failed for item {item.institution_name}: {e}")
            item.status = "error"
            item.error_code = str(e)[:100]
        # Intentional explicit commit: each PlaidItem is committed independently
        # so that a failure on item N doesn't roll back items 1..N-1. This is a
        # deliberate deviation from the auto-commit convention in get_session().
        await session.commit()

    # Post-sync tasks: best-effort, each with its own timeout protection
    if run_categorize and total_added > 0:
        # 1. Apply entity rules first (assigns business entities via vendor patterns)
        try:
            from pipeline.db.models import apply_entity_rules
            ent_count = await asyncio.wait_for(apply_entity_rules(session), timeout=30)
            logger.info(f"Entity rules applied to {ent_count} transactions after Plaid sync.")
        except asyncio.TimeoutError:
            logger.warning("Post-sync entity rules timed out after 30s")
        except Exception as e:
            logger.warning(f"Post-sync entity rules failed: {e}")

        # 2. Apply category rules (handles known merchants without AI)
        try:
            from pipeline.ai.category_rules import apply_rules
            cat_rules = await asyncio.wait_for(apply_rules(session), timeout=30)
            logger.info(f"Category rules applied to {cat_rules['applied']} transactions after Plaid sync.")
        except asyncio.TimeoutError:
            logger.warning("Post-sync category rules timed out after 30s")
        except Exception as e:
            logger.warning(f"Post-sync category rules failed: {e}")

        # 3. AI categorization for remaining uncategorized transactions
        try:
            from pipeline.ai.categorizer import categorize_transactions
            cat = await asyncio.wait_for(categorize_transactions(session), timeout=120)
            logger.info(f"Categorized {cat['categorized']} transactions after Plaid sync.")
        except asyncio.TimeoutError:
            logger.warning("Post-sync categorization timed out after 120s")
        except Exception as e:
            logger.warning(f"Post-sync categorization failed: {e}")

    if total_added > 0:
        try:
            from pipeline.importers.amazon import auto_match_amazon_orders
            match_result = await asyncio.wait_for(auto_match_amazon_orders(session), timeout=60)
            logger.info(f"Amazon auto-match after Plaid sync: {match_result}")
        except asyncio.TimeoutError:
            logger.warning("Amazon auto-match timed out after 60s")
        except Exception as e:
            logger.warning(f"Amazon auto-match failed: {e}")

    try:
        await asyncio.wait_for(snapshot_net_worth(session), timeout=30)
    except asyncio.TimeoutError:
        logger.warning("Net worth snapshot timed out after 30s")
    except Exception as e:
        logger.warning(f"Net worth snapshot failed: {e}")

    # Audit log
    try:
        from pipeline.security.audit import log_audit
        await log_audit(session, "plaid_sync", "bank_data", f"items={len(items)},added={total_added},accounts={total_updated_accounts}")
    except Exception:
        pass

    return {
        "items_synced": len(items),
        "transactions_added": total_added,
        "accounts_updated": total_updated_accounts,
    }


async def sync_item(
    session: AsyncSession,
    item: PlaidItem,
) -> tuple[int, int]:
    """
    Sync a single PlaidItem. Returns (transactions_added, accounts_updated).
    """
    if not item.access_token:
        logger.warning(f"Skipping sync for {item.institution_name}: no access token")
        return 0, 0

    logger.info(f"Syncing {item.institution_name}…")

    # 1. Refresh account balances
    token = decrypt_token(item.access_token)
    accounts_data = get_accounts(token)
    accounts_updated = await _update_account_balances(session, item, accounts_data)

    # 2. Sync investment holdings (if any investment accounts exist)
    has_investment_accounts = any(
        a.get("type") == "investment" for a in accounts_data
    )
    if has_investment_accounts:
        try:
            holdings_data = get_investment_holdings(token)
            await _sync_investment_holdings(session, item, holdings_data)
        except Exception as e:
            logger.warning(f"Investment holdings sync failed for {item.institution_name}: {e}")

    # 3. Sync transactions (incremental via cursor)
    sync_result = sync_transactions(token, cursor=item.plaid_cursor)

    added = await _process_new_transactions(session, item, sync_result["added"])
    await _update_modified_transactions(session, item, sync_result.get("modified", []))
    await _remove_transactions(session, sync_result["removed"])

    if sync_result.get("next_cursor"):
        item.plaid_cursor = sync_result["next_cursor"]

    return added, accounts_updated


async def _update_account_balances(
    session: AsyncSession,
    item: PlaidItem,
    accounts_data: list[dict[str, Any]],
) -> int:
    updated = 0
    for acct_data in accounts_data:
        result = await session.execute(
            select(PlaidAccount).where(
                PlaidAccount.plaid_account_id == acct_data["plaid_account_id"]
            )
        )
        plaid_acct = result.scalar_one_or_none()

        if plaid_acct:
            plaid_acct.current_balance = acct_data["current_balance"]
            plaid_acct.available_balance = acct_data["available_balance"]
            plaid_acct.limit_balance = acct_data["limit_balance"]
            plaid_acct.last_updated = datetime.now(timezone.utc)
        else:
            # Create Account + PlaidAccount
            our_account = await upsert_account(session, {
                "name": acct_data["name"],
                "account_type": _map_plaid_type(acct_data["type"]),
                "subtype": acct_data["subtype"],
                "institution": item.institution_name,
                "last_four": acct_data.get("mask"),
                "currency": acct_data.get("iso_currency", "USD"),
                "data_source": "plaid",
            })
            new_plaid_acct = PlaidAccount(
                plaid_item_id=item.id,
                account_id=our_account.id,
                **acct_data,
            )
            session.add(new_plaid_acct)
            plaid_acct = new_plaid_acct

        updated += 1

    await session.flush()
    return updated


async def _sync_investment_holdings(
    session: AsyncSession,
    item: PlaidItem,
    holdings_data: dict[str, Any],
) -> int:
    """Sync investment holdings from Plaid into the InvestmentHolding table.

    Uses plaid_security_id as the dedup key. On each sync:
    - Updates existing Plaid-sourced holdings (price, value, shares)
    - Creates new holdings for securities not yet tracked
    - Deactivates Plaid holdings that no longer appear (sold positions)
    """
    raw_holdings = holdings_data.get("holdings", [])
    if not raw_holdings:
        return 0

    # Map plaid_account_id → our account_id
    result = await session.execute(
        select(PlaidAccount).where(PlaidAccount.plaid_item_id == item.id)
    )
    plaid_accounts = {pa.plaid_account_id: pa for pa in result.scalars().all()}

    # Load existing Plaid-sourced holdings for this item's accounts
    account_ids = [pa.account_id for pa in plaid_accounts.values() if pa.account_id]
    existing_result = await session.execute(
        select(InvestmentHolding).where(
            InvestmentHolding.account_id.in_(account_ids),
            InvestmentHolding.data_source == "plaid",
        )
    )
    existing_by_security = {
        h.plaid_security_id: h
        for h in existing_result.scalars().all()
        if h.plaid_security_id
    }

    seen_security_ids: set[str] = set()
    created = 0
    updated = 0

    PLAID_ASSET_CLASS_MAP = {
        "equity": "stock",
        "etf": "etf",
        "mutual fund": "mutual_fund",
        "fixed income": "bond",
        "cash": "cash",
        "derivative": "other",
        "cryptocurrency": "crypto",
    }

    for h in raw_holdings:
        plaid_acct = plaid_accounts.get(h["plaid_account_id"])
        if not plaid_acct or not plaid_acct.account_id:
            continue

        sec_id = h.get("plaid_security_id")
        if not sec_id:
            continue
        seen_security_ids.add(sec_id)

        asset_class = PLAID_ASSET_CLASS_MAP.get(
            (h.get("asset_type") or "equity").lower(), "stock"
        )

        existing = existing_by_security.get(sec_id)
        if existing:
            # Update existing holding
            existing.shares = h["shares"]
            existing.current_price = h.get("current_price")
            existing.current_value = h.get("current_value")
            existing.cost_basis_per_share = h.get("cost_basis_per_share")
            existing.total_cost_basis = h.get("total_cost_basis")
            existing.is_active = True
            existing.last_price_update = datetime.now(timezone.utc)
            if h.get("current_value") and h.get("total_cost_basis"):
                existing.unrealized_gain_loss = h["current_value"] - h["total_cost_basis"]
                if h["total_cost_basis"] != 0:
                    existing.unrealized_gain_loss_pct = (
                        (h["current_value"] - h["total_cost_basis"]) / h["total_cost_basis"] * 100
                    )
            updated += 1
        else:
            # Create new holding
            unrealized_gl = None
            unrealized_gl_pct = None
            if h.get("current_value") and h.get("total_cost_basis"):
                unrealized_gl = h["current_value"] - h["total_cost_basis"]
                if h["total_cost_basis"] != 0:
                    unrealized_gl_pct = unrealized_gl / h["total_cost_basis"] * 100

            new_holding = InvestmentHolding(
                account_id=plaid_acct.account_id,
                ticker=h["ticker"],
                name=h.get("name"),
                asset_class=asset_class,
                shares=h["shares"],
                cost_basis_per_share=h.get("cost_basis_per_share"),
                total_cost_basis=h.get("total_cost_basis"),
                current_price=h.get("current_price"),
                current_value=h.get("current_value"),
                unrealized_gain_loss=unrealized_gl,
                unrealized_gain_loss_pct=unrealized_gl_pct,
                last_price_update=datetime.now(timezone.utc),
                is_active=True,
                data_source="plaid",
                plaid_security_id=sec_id,
                notes=f"Synced from {item.institution_name}",
            )
            session.add(new_holding)
            created += 1

    # Deactivate Plaid holdings that no longer appear (sold positions)
    for sec_id, holding in existing_by_security.items():
        if sec_id not in seen_security_ids and holding.is_active:
            holding.is_active = False
            holding.notes = (holding.notes or "") + " [position closed per Plaid]"

    await session.flush()
    logger.info(
        f"Investment holdings sync for {item.institution_name}: "
        f"{created} created, {updated} updated"
    )
    return created + updated


async def _process_new_transactions(
    session: AsyncSession,
    item: PlaidItem,
    added: list[dict[str, Any]],
) -> int:
    if not added:
        return 0

    # Map plaid_account_id → our account_id
    result = await session.execute(
        select(PlaidAccount).where(PlaidAccount.plaid_item_id == item.id)
    )
    plaid_accounts = {pa.plaid_account_id: pa for pa in result.scalars().all()}

    rows = []
    for tx in added:
        if tx.get("pending"):
            continue
        plaid_acct = plaid_accounts.get(tx["plaid_account_id"])
        if not plaid_acct or not plaid_acct.account_id:
            continue

        rows.append({
            "account_id": plaid_acct.account_id,
            "date": tx["date"],
            "authorized_date": tx.get("authorized_date"),
            "description": tx["description"],
            "merchant_name": tx.get("merchant_name"),
            "amount": tx["amount"],
            "currency": tx.get("currency", "USD"),
            "segment": "personal",
            "effective_segment": "personal",
            "period_month": tx["period_month"],
            "period_year": tx["period_year"],
            "transaction_hash": tx["transaction_hash"],
            "payment_channel": tx.get("payment_channel"),
            "plaid_pfc_primary": tx.get("plaid_pfc_primary"),
            "plaid_pfc_detailed": tx.get("plaid_pfc_detailed"),
            "plaid_pfc_confidence": tx.get("plaid_pfc_confidence"),
            "merchant_logo_url": tx.get("merchant_logo_url"),
            "merchant_website": tx.get("merchant_website"),
            "plaid_location_json": tx.get("plaid_location_json"),
            "plaid_counterparties_json": tx.get("plaid_counterparties_json"),
            "notes": f"Plaid: {tx.get('plaid_merchant', '')}",
            "data_source": "plaid",
        })

    # Pre-filter: batch-check for cross-source duplicates before calling
    # bulk_create_transactions (reduces N individual queries).
    if rows:
        account_ids = {r["account_id"] for r in rows}
        existing_csv = await session.execute(
            select(
                Transaction.account_id,
                sqlfunc.date(Transaction.date).label("tx_date"),
                Transaction.amount,
            ).where(
                Transaction.account_id.in_(account_ids),
                Transaction.data_source != "plaid",
                Transaction.is_excluded.is_(False),
            )
        )
        csv_keys = {(r.account_id, str(r.tx_date), r.amount) for r in existing_csv}

        pre_filter_count = len(rows)
        rows = [
            r for r in rows
            if (
                r["account_id"],
                str(r["date"].date() if hasattr(r["date"], "date") else r["date"]),
                r["amount"],
            ) not in csv_keys
        ]
        skipped = pre_filter_count - len(rows)
        if skipped:
            logger.info(f"Cross-source dedup: skipped {skipped} Plaid transactions already in CSV")

    inserted = await bulk_create_transactions(session, rows)
    logger.info(f"Inserted {inserted} new transactions from {item.institution_name}")
    return inserted


async def _update_modified_transactions(
    session: AsyncSession,
    item: PlaidItem,
    modified: list[dict[str, Any]],
) -> int:
    """Apply Plaid-reported modifications to existing transactions.

    Plaid sends modified transactions when a pending transaction posts with
    different details (amount, date, merchant name, etc.). We update the
    stored transaction to reflect the authoritative posted data.
    """
    if not modified:
        return 0

    import hashlib

    updated = 0
    for tx in modified:
        if tx.get("pending"):
            continue

        # transaction_hash is already a SHA-256 hex digest from _normalize_transaction —
        # use it directly (do NOT re-hash)
        tx_hash = tx.get("transaction_hash")
        # Fallback: compute hash from raw Plaid transaction ID (same logic as _normalize_transaction)
        plaid_id = tx.get("plaid_transaction_id") or tx.get("transaction_id", "")
        if not tx_hash and plaid_id:
            tx_hash = hashlib.sha256(plaid_id.encode()).hexdigest()

        if not tx_hash:
            continue

        result = await session.execute(
            select(Transaction).where(Transaction.transaction_hash == tx_hash)
        )
        existing = result.scalar_one_or_none()
        if not existing:
            continue

        # Update fields that Plaid may have corrected
        if "amount" in tx and tx["amount"] != existing.amount:
            existing.amount = tx["amount"]
        if "date" in tx:
            existing.date = tx["date"]
        if "description" in tx:
            existing.description = tx["description"]
        if tx.get("merchant_name"):
            existing.merchant_name = tx["merchant_name"]
        if tx.get("authorized_date"):
            existing.authorized_date = tx["authorized_date"]
        if tx.get("payment_channel"):
            existing.payment_channel = tx["payment_channel"]
        if tx.get("plaid_pfc_primary"):
            existing.plaid_pfc_primary = tx["plaid_pfc_primary"]
        if tx.get("plaid_pfc_detailed"):
            existing.plaid_pfc_detailed = tx["plaid_pfc_detailed"]
        if tx.get("plaid_pfc_confidence"):
            existing.plaid_pfc_confidence = tx["plaid_pfc_confidence"]
        if tx.get("merchant_logo_url"):
            existing.merchant_logo_url = tx["merchant_logo_url"]
        if tx.get("merchant_website"):
            existing.merchant_website = tx["merchant_website"]
        updated += 1

    if updated:
        logger.info(f"Updated {updated} modified transactions from {item.institution_name}")
    return updated


async def _remove_transactions(session: AsyncSession, removed_ids: list[str]) -> None:
    """Mark removed Plaid transactions as excluded (preserves original amount)."""
    if not removed_ids:
        return
    import hashlib
    for plaid_id in removed_ids:
        tx_hash = hashlib.sha256(plaid_id.encode()).hexdigest()
        await session.execute(
            update(Transaction)
            .where(Transaction.transaction_hash == tx_hash)
            .values(is_excluded=True, notes="[removed by Plaid]")
        )


def _map_plaid_type(plaid_type: str) -> str:
    """Map Plaid account type to our account_type.

    Note: loan and mortgage map to 'personal' because they are personal
    financial accounts. The finer-grained distinction is preserved in
    PlaidAccount.type and Account.subtype for display grouping.
    """
    mapping = {
        "depository": "personal",
        "credit": "personal",
        "investment": "investment",
        "loan": "personal",
        "mortgage": "personal",
    }
    return mapping.get(plaid_type.lower(), "personal")


async def snapshot_net_worth(session: AsyncSession) -> None:
    """Take a net worth snapshot from Plaid balances + manual assets (upsert by year/month)."""
    result = await session.execute(select(PlaidAccount))
    plaid_accounts = list(result.scalars().all())

    assets = 0.0
    liabilities = 0.0
    checking_savings = 0.0
    investment_value = 0.0
    real_estate_value = 0.0
    vehicle_value = 0.0
    other_assets = 0.0
    credit_debt = 0.0
    loan_bal = 0.0
    mortgage_bal = 0.0
    account_balances: dict[str, float] = {}

    for pa in plaid_accounts:
        balance = pa.current_balance or 0.0
        account_balances[pa.name] = balance

        if pa.type == "depository":
            checking_savings += balance
            assets += balance
        elif pa.type == "investment":
            investment_value += balance
            assets += balance
        elif pa.type == "credit":
            credit_debt += abs(balance)
            liabilities += abs(balance)
        elif pa.type == "mortgage":
            mortgage_bal += abs(balance)
            liabilities += abs(balance)
        elif pa.type == "loan":
            loan_bal += abs(balance)
            liabilities += abs(balance)

    # Include manual assets / liabilities
    ma_result = await session.execute(
        select(ManualAsset).where(ManualAsset.is_active == True)
    )
    for ma in ma_result.scalars().all():
        val = ma.current_value or 0.0
        account_balances[f"[manual] {ma.name}"] = val if not ma.is_liability else -val

        if ma.is_liability:
            liabilities += val
            if ma.asset_type == "mortgage":
                mortgage_bal += val
            else:
                loan_bal += val
        else:
            assets += val
            if ma.asset_type == "real_estate":
                real_estate_value += val
            elif ma.asset_type == "vehicle":
                vehicle_value += val
            elif ma.asset_type == "investment":
                investment_value += val
            else:
                other_assets += val

    now = datetime.now(timezone.utc)

    existing = await session.execute(
        select(NetWorthSnapshot).where(
            NetWorthSnapshot.year == now.year,
            NetWorthSnapshot.month == now.month,
        )
    )
    snapshot = existing.scalar_one_or_none()

    snapshot_data = dict(
        snapshot_date=now,
        total_assets=assets,
        total_liabilities=liabilities,
        net_worth=assets - liabilities,
        checking_savings=checking_savings,
        investment_value=investment_value,
        real_estate_value=real_estate_value,
        vehicle_value=vehicle_value,
        other_assets=other_assets,
        credit_card_debt=credit_debt,
        loan_balance=loan_bal,
        mortgage_balance=mortgage_bal,
        account_balances=json.dumps(account_balances),
    )

    if snapshot:
        for k, v in snapshot_data.items():
            setattr(snapshot, k, v)
    else:
        snapshot = NetWorthSnapshot(year=now.year, month=now.month, **snapshot_data)
        session.add(snapshot)

    await session.flush()
