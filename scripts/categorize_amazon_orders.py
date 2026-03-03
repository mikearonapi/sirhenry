"""
Standalone Claude categorization pass for amazon_orders rows that have no
effective_category. Run this after import_amazon_all.py if the importer
ran with --no-claude or if Claude batches failed mid-import.

Usage:
    python scripts/categorize_amazon_orders.py
    python scripts/categorize_amazon_orders.py --owner Mike
    python scripts/categorize_amazon_orders.py --owner Christine --batch-size 25
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_, select, update
from pipeline.db import init_db, init_extended_db, AmazonOrder
from pipeline.utils import create_engine_and_session, CLAUDE_MODEL, strip_json_fences
from pipeline.ai.categories import AMAZON_CATEGORIES

import anthropic
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _build_claude_prompt(orders: list[dict]) -> str:
    categories = AMAZON_CATEGORIES
    order_list = [
        {"order_id": o["order_id"], "items": o["items_description"], "total": o["total_charged"]}
        for o in orders
    ]
    return f"""You are categorizing Amazon orders for a family's financial tracking.

Household context:
- Primary earner works at Accenture (consulting) — tech, books, office items may be business
- Wife sits on corporate boards — professional/business books or supplies may be deductible
- Family has children — toys, baby items, school supplies are personal
- High Amazon usage includes household staples, electronics, clothing

For each order, determine:
1. category: pick the best from the list
2. segment: "personal" or "business"
3. is_business: true if likely a deductible business expense
4. is_gift: true if it appears to be a gift purchase

Category options: {json.dumps(categories)}

Return a JSON array with one object per order:
{{"order_id": "...", "category": "...", "segment": "personal|business", "is_business": bool, "is_gift": bool}}

Return ONLY the JSON array.

Orders:
{json.dumps(order_list, indent=2)}"""


async def categorize_uncategorized(
    session,
    owner: str | None = None,
    batch_size: int = 30,
) -> dict:
    """Fetch uncategorized retail orders and run them through Claude."""
    filters = [
        AmazonOrder.is_refund.is_(False),
        or_(
            AmazonOrder.effective_category.is_(None),
            AmazonOrder.effective_category == "",
            AmazonOrder.effective_category == "Unknown",
        ),
    ]
    if owner:
        filters.append(AmazonOrder.owner == owner)

    orders = (await session.execute(
        select(AmazonOrder).where(*filters).order_by(AmazonOrder.order_date.desc())
    )).scalars().all()

    if not orders:
        logger.info("No uncategorized orders found.")
        return {"total": 0, "categorized": 0, "failed_batches": 0}

    logger.info(f"Found {len(orders)} uncategorized orders to process"
                + (f" (owner={owner})" if owner else ""))

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    categorized_count = 0
    failed_batches = 0

    for i in range(0, len(orders), batch_size):
        batch = orders[i: i + batch_size]
        batch_dicts = [
            {
                "order_id": o.order_id,
                "items_description": o.items_description,
                "total_charged": o.total_charged,
            }
            for o in batch
        ]

        try:
            prompt = _build_claude_prompt(batch_dicts)
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = strip_json_fences(response.content[0].text)
            results = json.loads(raw)
            cat_map = {r["order_id"]: r for r in results}

            for order in batch:
                cat_info = cat_map.get(order.order_id, {})
                if cat_info:
                    order.effective_category = cat_info.get("category")
                    order.suggested_category = cat_info.get("category")
                    order.segment = cat_info.get("segment", "personal")
                    order.is_business = cat_info.get("is_business", False)
                    order.is_gift = cat_info.get("is_gift", False)
                    categorized_count += 1

            batch_num = i // batch_size + 1
            total_batches = (len(orders) + batch_size - 1) // batch_size
            logger.info(f"Batch {batch_num}/{total_batches}: categorized {len(batch)} orders")

        except Exception as e:
            failed_batches += 1
            logger.warning(f"Batch {i // batch_size + 1} failed: {e}")

    await session.flush()
    return {
        "total": len(orders),
        "categorized": categorized_count,
        "failed_batches": failed_batches,
    }


async def run(args) -> None:
    engine, Session = create_engine_and_session()
    await init_db(engine)
    await init_extended_db()

    async with Session() as session:
        async with session.begin():
            result = await categorize_uncategorized(
                session,
                owner=args.owner,
                batch_size=args.batch_size,
            )

    print(json.dumps(result, indent=2))
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Categorize uncategorized Amazon orders with Claude")
    parser.add_argument("--owner", default=None,
                        help='Only process orders for one owner, e.g. "Mike"')
    parser.add_argument("--batch-size", type=int, default=30,
                        help="Orders per Claude API call (default: 30)")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
