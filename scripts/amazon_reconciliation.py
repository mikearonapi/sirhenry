"""
Amazon spending reconciliation: surfaces gaps between Amazon orders and
credit card transactions so nothing slips through uncategorized.

Reports:
  1. Unmatched Amazon orders (imported from data dump, no matching CC transaction)
  2. Unmatched Amazon-like transactions (CC charges with no linked order)
  3. Category mismatches (order vs transaction disagree on category)
  4. Spending summary by Amazon category
  5. Unmatched refunds (Amazon credit records with no matching CC credit)

Flags:
  --rematch       Re-run matching for all unmatched Amazon orders
  --year YYYY     Filter to a specific year
  --fix-cats      Push Amazon order categories onto matched transactions
  --owner NAME    Filter to a specific account owner ("Mike" or "Christine")

Usage:
    python scripts/amazon_reconciliation.py
    python scripts/amazon_reconciliation.py --rematch
    python scripts/amazon_reconciliation.py --year 2025 --fix-cats
    python scripts/amazon_reconciliation.py --year 2025 --owner Mike
"""
import argparse
import asyncio
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, or_, select, update
from pipeline.db import init_db
from pipeline.db.schema import Transaction
from pipeline.db.schema_extended import AmazonOrder
from pipeline.importers.amazon import AMAZON_DESCRIPTION_PATTERNS, _amazon_description_filter
from pipeline.utils import create_engine_and_session


def _fmt_money(val: float | None) -> str:
    if val is None:
        return "$0.00"
    return f"${abs(val):,.2f}"


async def _rematch_unmatched(session, tolerance_days=5, amount_tolerance=5.0) -> int:
    """Re-try matching for all Amazon orders/refunds that have no matched_transaction_id."""
    unmatched = (await session.execute(
        select(AmazonOrder).where(AmazonOrder.matched_transaction_id.is_(None))
    )).scalars().all()

    if not unmatched:
        print("  All Amazon records are already matched.")
        return 0

    already_matched_subq = select(AmazonOrder.matched_transaction_id).where(
        AmazonOrder.matched_transaction_id.isnot(None)
    ).scalar_subquery()

    matched_count = 0
    for order in unmatched:
        start = order.order_date - timedelta(days=tolerance_days)
        end = order.order_date + timedelta(days=tolerance_days)
        # Refunds are positive on the CC statement; purchases are negative
        is_refund = getattr(order, "is_refund", False)
        target_amount = abs(order.total_charged) if is_refund else -order.total_charged

        result = await session.execute(
            select(Transaction).where(
                Transaction.date >= start,
                Transaction.date <= end,
                _amazon_description_filter(),
                Transaction.amount >= target_amount - amount_tolerance,
                Transaction.amount <= target_amount + amount_tolerance,
                Transaction.id.notin_(already_matched_subq),
            ).order_by(
                func.abs(func.julianday(Transaction.date) - func.julianday(order.order_date))
            ).limit(1)
        )
        tx = result.scalar_one_or_none()
        if tx:
            order.matched_transaction_id = tx.id
            matched_count += 1
            label = "REFUND" if is_refund else "ORDER"
            print(f"  MATCHED {label}: {order.order_id} ({_fmt_money(order.total_charged)}) "
                  f"-> Txn #{tx.id} '{tx.description[:40]}' ({_fmt_money(tx.amount)})")

    if matched_count:
        await session.flush()
    return matched_count


async def _fix_categories(session, year: int | None = None) -> int:
    """Push Amazon order effective_category onto matched transactions that lack one."""
    query = (
        select(AmazonOrder)
        .where(
            AmazonOrder.matched_transaction_id.isnot(None),
            AmazonOrder.effective_category.isnot(None),
        )
    )
    if year:
        from datetime import datetime
        query = query.where(
            AmazonOrder.order_date >= datetime(year, 1, 1),
            AmazonOrder.order_date < datetime(year + 1, 1, 1),
        )

    orders = (await session.execute(query)).scalars().all()
    updated = 0
    for order in orders:
        tx = (await session.execute(
            select(Transaction).where(Transaction.id == order.matched_transaction_id)
        )).scalar_one_or_none()
        if not tx:
            continue
        if tx.effective_category and tx.is_manually_reviewed:
            continue
        if tx.effective_category != order.effective_category:
            tx.effective_category = order.effective_category
            tx.category = order.effective_category
            if order.segment:
                tx.effective_segment = order.segment
                tx.segment = order.segment
            updated += 1

    if updated:
        await session.flush()
    return updated


async def main():
    parser = argparse.ArgumentParser(description="Amazon spending reconciliation")
    parser.add_argument("--rematch", action="store_true",
                        help="Re-run matching for unmatched Amazon orders")
    parser.add_argument("--fix-cats", action="store_true",
                        help="Push Amazon order categories onto matched transactions")
    parser.add_argument("--year", type=int, default=None,
                        help="Filter to a specific year")
    parser.add_argument("--owner", type=str, default=None,
                        help='Filter to a specific account owner, e.g. "Mike" or "Christine"')
    args = parser.parse_args()

    engine, Session = create_engine_and_session()
    await init_db(engine)

    async with Session() as session:
        async with session.begin():
            from datetime import datetime
            year_filter_order = []
            year_filter_tx = []
            if args.year:
                y_start = datetime(args.year, 1, 1)
                y_end = datetime(args.year + 1, 1, 1)
                year_filter_order = [AmazonOrder.order_date >= y_start, AmazonOrder.order_date < y_end]
                year_filter_tx = [Transaction.date >= y_start, Transaction.date < y_end]

            owner_filter = []
            if args.owner:
                owner_filter = [AmazonOrder.owner == args.owner]

            all_order_filters = [*year_filter_order, *owner_filter,
                                  AmazonOrder.is_refund.is_(False)]
            refund_order_filters = [*year_filter_order, *owner_filter,
                                    AmazonOrder.is_refund.is_(True)]

            # --- 0. Totals ---
            total_orders = (await session.execute(
                select(func.count(AmazonOrder.id)).where(*all_order_filters)
            )).scalar() or 0

            total_amazon_txns = (await session.execute(
                select(func.count(Transaction.id)).where(
                    _amazon_description_filter(), *year_filter_tx
                )
            )).scalar() or 0

            matched_orders = (await session.execute(
                select(func.count(AmazonOrder.id)).where(
                    AmazonOrder.matched_transaction_id.isnot(None), *all_order_filters
                )
            )).scalar() or 0

            total_refunds = (await session.execute(
                select(func.count(AmazonOrder.id)).where(*refund_order_filters)
            )).scalar() or 0

            matched_refunds = (await session.execute(
                select(func.count(AmazonOrder.id)).where(
                    AmazonOrder.matched_transaction_id.isnot(None), *refund_order_filters
                )
            )).scalar() or 0

            yr_label = f" ({args.year})" if args.year else ""
            owner_label = f" [{args.owner}]" if args.owner else ""
            print(f"\n{'='*70}")
            print(f"  AMAZON SPENDING RECONCILIATION{yr_label}{owner_label}")
            print(f"{'='*70}")
            print(f"  Amazon orders in DB:           {total_orders}")
            print(f"  Amazon-like CC transactions:    {total_amazon_txns}")
            print(f"  Orders matched to transactions: {matched_orders}")
            print(f"  Orders unmatched:               {total_orders - matched_orders}")
            match_pct = (matched_orders / total_orders * 100) if total_orders else 0
            print(f"  Match rate:                     {match_pct:.1f}%")
            print(f"  Refund records in DB:          {total_refunds}  ({matched_refunds} matched)")

            # --- 1. Rematch ---
            if args.rematch:
                print(f"\n{'-'*70}")
                print("  RE-MATCHING unmatched orders and refunds...")
                newly_matched = await _rematch_unmatched(session)
                print(f"  Newly matched: {newly_matched}")

            # --- 2. Fix categories ---
            if args.fix_cats:
                print(f"\n{'-'*70}")
                print("  PUSHING Amazon categories -> matched transactions...")
                fixed = await _fix_categories(session, args.year)
                print(f"  Transactions updated: {fixed}")

            # --- 3. Unmatched Amazon orders ---
            unmatched_orders = (await session.execute(
                select(AmazonOrder).where(
                    AmazonOrder.matched_transaction_id.is_(None), *all_order_filters
                ).order_by(AmazonOrder.order_date.desc())
            )).scalars().all()

            if unmatched_orders:
                print(f"\n{'-'*70}")
                print(f"  UNMATCHED AMAZON ORDERS ({len(unmatched_orders)})")
                print(f"  These orders have no matching credit card transaction.")
                print(f"{'-'*70}")
                for o in unmatched_orders[:30]:
                    cat = o.effective_category or "uncategorized"
                    seg = o.segment or "?"
                    owner_tag = f"[{o.owner}] " if o.owner else ""
                    print(f"  {o.order_date.strftime('%Y-%m-%d')}  {_fmt_money(o.total_charged):>10}  "
                          f"{owner_tag}[{seg:8}] [{cat:25}]  {o.items_description[:55]}")
                if len(unmatched_orders) > 30:
                    print(f"  ... and {len(unmatched_orders) - 30} more")

            # --- 4. Unmatched Amazon-like transactions ---
            matched_tx_ids_subq = select(AmazonOrder.matched_transaction_id).where(
                AmazonOrder.matched_transaction_id.isnot(None)
            ).scalar_subquery()

            unmatched_txns = (await session.execute(
                select(Transaction).where(
                    _amazon_description_filter(),
                    Transaction.id.notin_(matched_tx_ids_subq),
                    *year_filter_tx,
                ).order_by(Transaction.date.desc())
            )).scalars().all()

            if unmatched_txns:
                total_unmatched_spend = sum(t.amount for t in unmatched_txns)
                print(f"\n{'-'*70}")
                print(f"  UNMATCHED AMAZON TRANSACTIONS ({len(unmatched_txns)}) "
                      f"-- {_fmt_money(total_unmatched_spend)} total")
                print(f"  These CC charges look Amazon-related but have no linked order.")
                print(f"{'-'*70}")
                for t in unmatched_txns[:30]:
                    cat = t.effective_category or "uncategorized"
                    seg = t.effective_segment or "?"
                    print(f"  {t.date.strftime('%Y-%m-%d')}  {_fmt_money(t.amount):>10}  "
                          f"[{seg:8}] [{cat:25}]  {t.description[:50]}")
                if len(unmatched_txns) > 30:
                    print(f"  ... and {len(unmatched_txns) - 30} more")

            # --- 5. Category mismatches ---
            matched_pairs = (await session.execute(
                select(AmazonOrder, Transaction).join(
                    Transaction, AmazonOrder.matched_transaction_id == Transaction.id
                ).where(*all_order_filters)
            )).all()

            mismatches = []
            for ao, tx in matched_pairs:
                ao_cat = (ao.effective_category or "").strip().lower()
                tx_cat = (tx.effective_category or "").strip().lower()
                if ao_cat and tx_cat and ao_cat != tx_cat:
                    mismatches.append((ao, tx))

            if mismatches:
                print(f"\n{'-'*70}")
                print(f"  CATEGORY MISMATCHES ({len(mismatches)})")
                print(f"  Amazon order and matched transaction disagree on category.")
                print(f"{'-'*70}")
                for ao, tx in mismatches[:20]:
                    print(f"  Order {ao.order_id}  {ao.order_date.strftime('%Y-%m-%d')}  "
                          f"{_fmt_money(ao.total_charged):>10}")
                    print(f"    Amazon says: {ao.effective_category}")
                    print(f"    Txn says:    {tx.effective_category}")
                    print(f"    Items:       {ao.items_description[:70]}")
                    print()

            # --- 6. Spending summary by Amazon category ---
            cat_totals = (await session.execute(
                select(
                    AmazonOrder.effective_category,
                    AmazonOrder.segment,
                    func.count(AmazonOrder.id),
                    func.sum(AmazonOrder.total_charged),
                ).where(*all_order_filters).group_by(
                    AmazonOrder.effective_category, AmazonOrder.segment
                ).order_by(func.sum(AmazonOrder.total_charged).desc())
            )).all()

            if cat_totals:
                print(f"\n{'-'*70}")
                print(f"  AMAZON SPENDING BY CATEGORY")
                print(f"{'-'*70}")
                grand_total = 0.0
                for cat, seg, count, total in cat_totals:
                    cat = cat or "uncategorized"
                    seg = seg or "?"
                    total = total or 0.0
                    grand_total += total
                    print(f"  {_fmt_money(total):>12}  ({count:3} orders)  [{seg:8}]  {cat}")
                print(f"  {'-'*40}")
                print(f"  {_fmt_money(grand_total):>12}  TOTAL")

            # --- 7. Uncategorized orders ---
            uncategorized = (await session.execute(
                select(func.count(AmazonOrder.id)).where(
                    or_(
                        AmazonOrder.effective_category.is_(None),
                        AmazonOrder.effective_category == "",
                        AmazonOrder.effective_category == "Unknown",
                    ),
                    *all_order_filters,
                )
            )).scalar() or 0

            if uncategorized:
                print(f"\n  ! {uncategorized} Amazon orders are uncategorized or 'Unknown'.")
                print(f"    Re-run the Amazon importer with Claude categorization,")
                print(f"    or use --fix-cats to push existing categories to transactions.")

            # --- 8. Unmatched refunds ---
            unmatched_refunds = (await session.execute(
                select(AmazonOrder).where(
                    AmazonOrder.matched_transaction_id.is_(None),
                    *refund_order_filters,
                ).order_by(AmazonOrder.order_date.desc())
            )).scalars().all()

            if unmatched_refunds:
                total_refund_amt = sum(abs(r.total_charged) for r in unmatched_refunds)
                print(f"\n{'-'*70}")
                print(f"  UNMATCHED REFUNDS ({len(unmatched_refunds)}) -- {_fmt_money(total_refund_amt)} total")
                print(f"  These Amazon refunds have no matching CC credit transaction.")
                print(f"{'-'*70}")
                for r in unmatched_refunds[:20]:
                    owner_tag = f"[{r.owner}] " if r.owner else ""
                    print(f"  {r.order_date.strftime('%Y-%m-%d')}  {_fmt_money(abs(r.total_charged)):>10}  "
                          f"{owner_tag}{r.items_description[:60]}")
                if len(unmatched_refunds) > 20:
                    print(f"  ... and {len(unmatched_refunds) - 20} more")

            print(f"\n{'='*70}\n")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
