"""
Smart rematch: resolve 1:1 matching collisions using optimal assignment.

The greedy matcher assigns the first-found CC transaction to each Amazon
shipment. When multiple shipments have identical amounts within the same
date window, this produces collisions: one shipment grabs a CC transaction
that better belongs to another shipment.

This script:
1. Clears ALL existing matches
2. Builds a bipartite graph: Amazon shipments <-> CC transactions
3. Uses a greedy best-fit algorithm sorted by (amount_diff, date_diff)
4. Each CC transaction is assigned to at most one shipment (and vice versa)
5. Propagates categories to matched CC transactions

Usage:
    python scripts/smart_rematch.py
    python scripts/smart_rematch.py --year 2025
    python scripts/smart_rematch.py --dry-run
"""
import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update
from pipeline.db import init_db, init_extended_db, Transaction
from pipeline.db.schema_extended import AmazonOrder
from pipeline.importers.amazon import (
    AMAZON_DESCRIPTION_PATTERNS, _amazon_description_filter,
    MATCH_TOLERANCE_DAYS, MATCH_TOLERANCE_AMOUNT,
)
from pipeline.utils import create_engine_and_session

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def smart_rematch(dry_run=False, year=None):
    engine, Session = create_engine_and_session()
    await init_db(engine)

    async with Session() as session:
        async with session.begin():
            # --- Step 1: Load all Amazon shipments (non-refund) ---
            filters = [AmazonOrder.is_refund.is_(False)]
            if year:
                filters.extend([
                    AmazonOrder.order_date >= datetime(year, 1, 1),
                    AmazonOrder.order_date < datetime(year + 1, 1, 1),
                ])
            shipments = (await session.execute(
                select(AmazonOrder).where(*filters)
            )).scalars().all()

            # Also load refunds for separate matching
            refund_filters = [AmazonOrder.is_refund.is_(True)]
            if year:
                refund_filters.extend([
                    AmazonOrder.order_date >= datetime(year, 1, 1),
                    AmazonOrder.order_date < datetime(year + 1, 1, 1),
                ])
            refunds = (await session.execute(
                select(AmazonOrder).where(*refund_filters)
            )).scalars().all()

            # --- Step 2: Load all Amazon-like CC transactions ---
            tx_filters = [_amazon_description_filter()]
            if year:
                tx_filters.extend([
                    Transaction.date >= datetime(year, 1, 1),
                    Transaction.date < datetime(year + 1, 1, 1),
                ])
            cc_txns = (await session.execute(
                select(Transaction).where(*tx_filters)
            )).scalars().all()

            logger.info(f"Loaded {len(shipments)} shipments, {len(refunds)} refunds, "
                        f"{len(cc_txns)} Amazon CC transactions"
                        + (f" for {year}" if year else ""))

            # --- Step 3: Clear existing matches in scope ---
            if not dry_run:
                cleared = 0
                for s in shipments:
                    if s.matched_transaction_id is not None:
                        s.matched_transaction_id = None
                        cleared += 1
                for r in refunds:
                    if r.matched_transaction_id is not None:
                        r.matched_transaction_id = None
                        cleared += 1
                logger.info(f"Cleared {cleared} existing matches")

            # --- Step 4: Build candidate pairs and sort by quality ---
            # For purchases: CC amount is negative, Amazon total_charged is positive
            # Score = (amount_diff, date_diff) -- lower is better
            candidates = []

            for s in shipments:
                if s.total_charged <= 0:
                    continue
                for tx in cc_txns:
                    if tx.amount >= 0:
                        continue  # skip credits for purchase matching
                    amt_diff = abs(abs(tx.amount) - s.total_charged)
                    if amt_diff > MATCH_TOLERANCE_AMOUNT:
                        continue
                    day_diff = abs((tx.date - s.order_date).days)
                    if day_diff > MATCH_TOLERANCE_DAYS:
                        continue
                    candidates.append((amt_diff, day_diff, s.id, tx.id, "purchase"))

            # For refunds: CC amount is positive, Amazon total_charged is negative
            for r in refunds:
                for tx in cc_txns:
                    if tx.amount <= 0:
                        continue  # refunds match positive CC entries
                    amt_diff = abs(tx.amount - abs(r.total_charged))
                    if amt_diff > MATCH_TOLERANCE_AMOUNT:
                        continue
                    day_diff = abs((tx.date - r.order_date).days)
                    if day_diff > MATCH_TOLERANCE_DAYS:
                        continue
                    candidates.append((amt_diff, day_diff, r.id, tx.id, "refund"))

            # Sort: prefer exact amount match first, then closest date
            candidates.sort(key=lambda c: (c[0], c[1]))

            logger.info(f"Found {len(candidates)} candidate match pairs")

            # --- Step 5: Greedy best-fit assignment (1:1) ---
            used_shipments: set[int] = set()
            used_txns: set[int] = set()
            matches: list[tuple[int, int, str]] = []

            for amt_diff, day_diff, ship_id, tx_id, match_type in candidates:
                if ship_id in used_shipments or tx_id in used_txns:
                    continue
                used_shipments.add(ship_id)
                used_txns.add(tx_id)
                matches.append((ship_id, tx_id, match_type))

            purchase_matches = sum(1 for _, _, t in matches if t == "purchase")
            refund_matches = sum(1 for _, _, t in matches if t == "refund")
            logger.info(f"Optimal assignment: {purchase_matches} purchase matches, "
                        f"{refund_matches} refund matches")

            # --- Step 6: Apply matches ---
            if not dry_run:
                # Build lookup maps
                ship_map = {s.id: s for s in shipments}
                ship_map.update({r.id: r for r in refunds})
                tx_map = {t.id: t for t in cc_txns}

                propagated = 0
                for ship_id, tx_id, match_type in matches:
                    ship = ship_map.get(ship_id)
                    tx = tx_map.get(tx_id)
                    if ship and tx:
                        ship.matched_transaction_id = tx.id
                        # Propagate category
                        if ship.effective_category and not tx.is_manually_reviewed:
                            tx.effective_category = ship.effective_category
                            tx.category = ship.effective_category
                            if ship.segment:
                                tx.effective_segment = ship.segment
                                tx.segment = ship.segment
                            propagated += 1

                await session.flush()
                logger.info(f"Applied {len(matches)} matches, "
                            f"propagated categories to {propagated} CC transactions")

            # --- Summary ---
            total_cc = len(cc_txns)
            matched_cc = len(used_txns)
            unmatched_cc = total_cc - matched_cc
            total_cc_debit = [t for t in cc_txns if t.amount < 0]
            matched_debit = sum(1 for _, tx_id, t in matches if t == "purchase")

            print(f"\n{'=' * 70}")
            print(f"  SMART REMATCH RESULTS" + (f" ({year})" if year else ""))
            print(f"{'=' * 70}")
            print(f"  Total Amazon CC transactions:    {total_cc}")
            print(f"  CC debits (purchases):           {len(total_cc_debit)}")
            print(f"  Matched to Amazon shipments:     {matched_cc}")
            print(f"  Unmatched CC transactions:       {unmatched_cc}")
            print(f"  Match rate (of CC txns):         "
                  f"{matched_cc / total_cc * 100:.1f}%" if total_cc else "N/A")
            print(f"\n  Purchase matches:                {purchase_matches}")
            print(f"  Refund matches:                  {refund_matches}")

            if dry_run:
                print(f"\n  [DRY RUN - no changes made]")

            print(f"\n{'=' * 70}\n")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Smart rematch with optimal 1:1 assignment")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--year", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(smart_rematch(dry_run=args.dry_run, year=args.year))


if __name__ == "__main__":
    main()
