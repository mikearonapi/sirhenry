"""Account linking and merging endpoints.

Allows users to link accounts that represent the same real-world account
from different sources (e.g., CSV import + Plaid), and merge them so all
transactions flow to a single Account record.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import AccountLinkOut, LinkAccountIn, MergeResultOut, SuggestedLinkOut
from pipeline.db.schema import Account, AccountLink, Document, PlaidAccount, Transaction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/accounts", tags=["account-links"])


# ---- Endpoints ----

@router.post("/{account_id}/link", response_model=AccountLinkOut)
async def link_accounts(
    account_id: int,
    body: LinkAccountIn,
    session: AsyncSession = Depends(get_session),
):
    """Link two accounts as representing the same real-world account."""
    if account_id == body.target_account_id:
        raise HTTPException(400, "Cannot link an account to itself")

    # Verify both accounts exist
    for aid in (account_id, body.target_account_id):
        result = await session.execute(select(Account).where(Account.id == aid))
        if not result.scalar_one_or_none():
            raise HTTPException(404, f"Account {aid} not found")

    # Check for existing link
    existing = await session.execute(
        select(AccountLink).where(
            ((AccountLink.primary_account_id == account_id) & (AccountLink.secondary_account_id == body.target_account_id))
            | ((AccountLink.primary_account_id == body.target_account_id) & (AccountLink.secondary_account_id == account_id))
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "These accounts are already linked")

    link = AccountLink(
        primary_account_id=account_id,
        secondary_account_id=body.target_account_id,
        link_type=body.link_type,
    )
    session.add(link)
    await session.flush()

    return AccountLinkOut(
        id=link.id,
        primary_account_id=link.primary_account_id,
        secondary_account_id=link.secondary_account_id,
        link_type=link.link_type,
        created_at=link.created_at.isoformat(),
    )


@router.get("/{account_id}/links", response_model=list[AccountLinkOut])
async def get_account_links(
    account_id: int,
    session: AsyncSession = Depends(get_session),
):
    """List all accounts linked to this account."""
    result = await session.execute(
        select(AccountLink).where(
            (AccountLink.primary_account_id == account_id)
            | (AccountLink.secondary_account_id == account_id)
        )
    )
    links = result.scalars().all()
    return [
        AccountLinkOut(
            id=l.id,
            primary_account_id=l.primary_account_id,
            secondary_account_id=l.secondary_account_id,
            link_type=l.link_type,
            created_at=l.created_at.isoformat(),
        )
        for l in links
    ]


@router.delete("/{account_id}/link/{link_id}")
async def remove_link(
    account_id: int,
    link_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Remove a link between two accounts."""
    result = await session.execute(
        select(AccountLink).where(AccountLink.id == link_id)
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(404, "Link not found")
    if link.primary_account_id != account_id and link.secondary_account_id != account_id:
        raise HTTPException(403, "Link does not belong to this account")

    await session.delete(link)
    return {"status": "removed"}


@router.post("/{primary_id}/merge", response_model=MergeResultOut)
async def merge_accounts(
    primary_id: int,
    body: LinkAccountIn,
    session: AsyncSession = Depends(get_session),
):
    """Merge secondary account into primary.

    Moves all transactions and documents from secondary to primary,
    reassigns PlaidAccount if applicable, and deactivates the secondary.
    """
    secondary_id = body.target_account_id
    if primary_id == secondary_id:
        raise HTTPException(400, "Cannot merge an account into itself")

    # Verify both exist
    r1 = await session.execute(select(Account).where(Account.id == primary_id))
    primary = r1.scalar_one_or_none()
    if not primary:
        raise HTTPException(404, f"Primary account {primary_id} not found")

    r2 = await session.execute(select(Account).where(Account.id == secondary_id))
    secondary = r2.scalar_one_or_none()
    if not secondary:
        raise HTTPException(404, f"Secondary account {secondary_id} not found")

    # Move transactions
    tx_result = await session.execute(
        update(Transaction)
        .where(Transaction.account_id == secondary_id)
        .values(account_id=primary_id)
    )
    txn_moved = tx_result.rowcount  # type: ignore[attr-defined]

    # Move documents
    doc_result = await session.execute(
        update(Document)
        .where(Document.account_id == secondary_id)
        .values(account_id=primary_id)
    )
    docs_moved = doc_result.rowcount  # type: ignore[attr-defined]

    # Reassign PlaidAccount if secondary had one
    pa_result = await session.execute(
        select(PlaidAccount).where(PlaidAccount.account_id == secondary_id)
    )
    for pa in pa_result.scalars().all():
        pa.account_id = primary_id
        # Upgrade primary to plaid source
        if primary.data_source != "plaid":
            primary.data_source = "plaid"

    # Create audit link
    link = AccountLink(
        primary_account_id=primary_id,
        secondary_account_id=secondary_id,
        link_type="same_account",
    )
    session.add(link)

    # Deactivate secondary
    secondary.is_active = False

    await session.flush()
    logger.info(
        f"Merged account {secondary_id} into {primary_id}: "
        f"{txn_moved} txns, {docs_moved} docs moved"
    )

    return MergeResultOut(
        primary_account_id=primary_id,
        secondary_account_id=secondary_id,
        transactions_moved=txn_moved,
        documents_moved=docs_moved,
        secondary_deactivated=True,
    )


@router.get("/suggest-links", response_model=list[SuggestedLinkOut])
async def suggest_links(
    session: AsyncSession = Depends(get_session),
):
    """Auto-detect accounts that likely represent the same real-world account.

    Matches by: institution + last_four, or institution + similar name,
    across different data_source values.
    """
    result = await session.execute(
        select(Account).where(Account.is_active.is_(True))
    )
    all_accounts = list(result.scalars().all())

    suggestions: list[SuggestedLinkOut] = []
    seen_pairs: set[tuple[int, int]] = set()

    for i, a in enumerate(all_accounts):
        for b in all_accounts[i + 1:]:
            # Skip if same source — only suggest cross-source links
            if a.data_source == b.data_source:
                continue

            pair = (min(a.id, b.id), max(a.id, b.id))
            if pair in seen_pairs:
                continue

            reason = _match_reason(a, b)
            if reason:
                seen_pairs.add(pair)
                suggestions.append(SuggestedLinkOut(
                    account_a_id=a.id,
                    account_a_name=a.name,
                    account_a_source=a.data_source,
                    account_b_id=b.id,
                    account_b_name=b.name,
                    account_b_source=b.data_source,
                    match_reason=reason,
                ))

    return suggestions


@router.get("/{account_id}/duplicates")
async def find_duplicates(
    account_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Find candidate cross-source duplicate transactions in this account."""
    from pipeline.dedup.cross_source import find_cross_source_duplicates
    candidates = await find_cross_source_duplicates(session, account_id)
    return {"account_id": account_id, "candidates": candidates, "count": len(candidates)}


@router.post("/{account_id}/auto-dedup")
async def auto_dedup(
    account_id: int,
    min_confidence: float = 0.8,
    session: AsyncSession = Depends(get_session),
):
    """Auto-resolve obvious cross-source duplicates (high confidence)."""
    from pipeline.dedup.cross_source import auto_resolve_duplicates
    result = await auto_resolve_duplicates(session, account_id, min_confidence)
    return result


@router.post("/resolve-duplicate")
async def resolve_duplicate(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Manually resolve a duplicate pair: keep one, exclude the other."""
    keep_id = body.get("keep_id")
    exclude_id = body.get("exclude_id")
    if not keep_id or not exclude_id:
        raise HTTPException(400, "Both keep_id and exclude_id are required")

    result = await session.execute(
        select(Transaction).where(Transaction.id == exclude_id)
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(404, f"Transaction {exclude_id} not found")

    tx.is_excluded = True
    tx.notes = f"[manual-dedup] Duplicate of tx #{keep_id}"
    await session.flush()
    return {"status": "resolved", "excluded_id": exclude_id, "kept_id": keep_id}


def _match_reason(a: Account, b: Account) -> Optional[str]:
    """Return a match reason string if two accounts likely represent the same
    real-world account, or None if no match."""
    # Same institution + same last four digits
    if (a.institution and b.institution
            and a.institution.lower() == b.institution.lower()
            and a.last_four and b.last_four
            and a.last_four == b.last_four):
        return f"Same institution ({a.institution}) and last 4 digits ({a.last_four})"

    # Same institution + similar name
    if (a.institution and b.institution
            and a.institution.lower() == b.institution.lower()):
        a_name = a.name.lower().strip()
        b_name = b.name.lower().strip()
        if a_name == b_name or a_name in b_name or b_name in a_name:
            return f"Same institution ({a.institution}) with similar name"

    # Same name + same subtype (likely same account from different sources)
    if a.name.lower().strip() == b.name.lower().strip() and a.subtype == b.subtype:
        return f"Same name and subtype ({a.subtype})"

    return None
