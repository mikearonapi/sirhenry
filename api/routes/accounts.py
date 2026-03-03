from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import AccountOut, AccountWithBalanceOut
from pipeline.db import PlaidAccount, get_account, get_all_accounts, upsert_account
from pipeline.db.schema import Transaction

router = APIRouter(prefix="/accounts", tags=["accounts"])


# ---- Pydantic models for create / update ----

class AccountCreateIn(BaseModel):
    name: str
    account_type: str
    subtype: Optional[str] = None
    institution: Optional[str] = None
    last_four: Optional[str] = None
    currency: str = "USD"
    notes: Optional[str] = None
    default_segment: Optional[str] = None
    default_business_entity_id: Optional[int] = None


class AccountUpdateIn(BaseModel):
    name: Optional[str] = None
    account_type: Optional[str] = None
    subtype: Optional[str] = None
    institution: Optional[str] = None
    last_four: Optional[str] = None
    currency: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    default_segment: Optional[str] = None
    default_business_entity_id: Optional[int] = None


# ---- Endpoints ----

@router.get("", response_model=list[AccountWithBalanceOut])
async def list_accounts(
    session: AsyncSession = Depends(get_session),
    exclude_plaid: bool = Query(True, description="Exclude accounts linked to Plaid (shown via /plaid/accounts)"),
):
    accounts = await get_all_accounts(session)

    plaid_linked_ids: set[int] = set()
    if exclude_plaid:
        pa_result = await session.execute(select(PlaidAccount.account_id))
        plaid_linked_ids = {row[0] for row in pa_result if row[0] is not None}

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
        if a.id in plaid_linked_ids:
            continue
        bal, txn_count = balance_map.get(a.id, (0.0, 0))
        data = AccountWithBalanceOut.model_validate(a)
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
