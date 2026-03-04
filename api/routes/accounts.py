from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import AccountCreateIn, AccountOut, AccountUpdateIn, AccountWithBalanceOut
from pipeline.db import PlaidAccount, get_account, get_all_accounts, upsert_account
from pipeline.db.schema import PlaidItem, Transaction

router = APIRouter(prefix="/accounts", tags=["accounts"])


# ---- Endpoints ----

@router.get("", response_model=list[AccountWithBalanceOut])
async def list_accounts(
    session: AsyncSession = Depends(get_session),
    exclude_plaid: bool = Query(False, description="Exclude accounts linked to Plaid"),
):
    """Return all active accounts with balances and Plaid metadata.

    Plaid-sourced accounts get their balance from PlaidAccount;
    CSV/manual accounts compute balance from sum(transactions).
    """
    accounts = await get_all_accounts(session)

    # Build Plaid metadata map: account_id → PlaidAccount + PlaidItem info
    pa_result = await session.execute(
        select(PlaidAccount, PlaidItem.last_synced_at)
        .join(PlaidItem, PlaidAccount.plaid_item_id == PlaidItem.id)
        .where(PlaidItem.status != "removed")
    )
    plaid_map: dict[int, tuple] = {}  # account_id → (PlaidAccount, last_synced_at)
    plaid_linked_ids: set[int] = set()
    for pa, last_synced in pa_result:
        if pa.account_id is not None:
            plaid_map[pa.account_id] = (pa, last_synced)
            plaid_linked_ids.add(pa.account_id)

    # Transaction-based balances for non-Plaid accounts
    balance_q = (
        select(
            Transaction.account_id,
            func.sum(Transaction.amount).label("balance"),
            func.count(Transaction.id).label("txn_count"),
        )
        .where(Transaction.is_excluded.is_(False))
        .group_by(Transaction.account_id)
    )
    result = await session.execute(balance_q)
    balance_map = {row.account_id: (float(row.balance or 0), int(row.txn_count)) for row in result}

    out = []
    for a in accounts:
        if exclude_plaid and a.id in plaid_linked_ids:
            continue

        data = AccountWithBalanceOut.model_validate(a)

        # Plaid-sourced: use Plaid balance + attach metadata
        if a.id in plaid_map:
            pa, last_synced = plaid_map[a.id]
            data.balance = float(pa.current_balance or 0)
            data.current_balance = pa.current_balance
            data.available_balance = pa.available_balance
            data.plaid_mask = pa.mask
            data.plaid_type = pa.type
            data.plaid_subtype = pa.subtype
            data.plaid_last_synced = last_synced.isoformat() if last_synced else None
            data.plaid_institution = a.institution
            # Also include transaction count
            _, txn_count = balance_map.get(a.id, (0.0, 0))
            data.transaction_count = txn_count
        else:
            bal, txn_count = balance_map.get(a.id, (0.0, 0))
            data.balance = bal
            data.transaction_count = txn_count

        out.append(data)
    return out


@router.get("/{account_id}", response_model=AccountOut)
async def get_single_account(
    account_id: int,
    session: AsyncSession = Depends(get_session),
):
    account = await get_account(session, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.post("", response_model=AccountOut, status_code=201)
async def create_account(
    body: AccountCreateIn,
    session: AsyncSession = Depends(get_session),
):
    account = await upsert_account(session, body.model_dump())
    return account


@router.patch("/{account_id}", response_model=AccountOut)
async def update_account(
    account_id: int,
    body: AccountUpdateIn,
    session: AsyncSession = Depends(get_session),
):
    account = await get_account(session, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(account, k, v)
    await session.flush()
    return account


@router.delete("/{account_id}", response_model=AccountOut)
async def deactivate_account(
    account_id: int,
    session: AsyncSession = Depends(get_session),
):
    account = await get_account(session, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.is_active = False
    await session.flush()
    return account
