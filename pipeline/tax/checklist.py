"""
Compute tax filing readiness checklist based on actual data in the system.

Checks document imports (W-2, 1099-*, K-1, 1098), transaction imports,
categorization progress, business expense review, AI strategy analysis,
quarterly payment tracking, and filing deadlines.
"""
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db import count_transactions, get_tax_items, get_tax_strategies
from pipeline.db.schema import Transaction


async def compute_tax_checklist(session: AsyncSession, tax_year: int) -> dict:
    """
    Compute the full tax checklist for a given tax year.

    Returns a dict matching the TaxChecklistOut schema fields:
    tax_year, items (list of dicts), completed, total, progress_pct.
    """
    items: list[dict] = []
    tax_items_all = await get_tax_items(session, tax_year=tax_year)

    form_counts: dict[str, int] = {}
    for ti in tax_items_all:
        form_counts[ti.form_type] = form_counts.get(ti.form_type, 0) + 1

    # --- Document imports ---
    doc_checks = [
        ("import_w2", "Import W-2 Documents", "Upload all W-2 wage statements", "w2"),
        ("import_1099_nec", "Import 1099-NEC Documents", "Upload 1099-NEC forms for freelance/board income", "1099_nec"),
        ("import_1099_div", "Import 1099-DIV Documents", "Upload 1099-DIV forms for dividend income", "1099_div"),
        ("import_1099_b", "Import 1099-B Documents", "Upload 1099-B forms for capital gains/losses", "1099_b"),
        ("import_1099_int", "Import 1099-INT Documents", "Upload 1099-INT forms for interest income", "1099_int"),
        ("import_k1", "Import K-1 Documents", "Upload K-1 forms for partnership/S-corp income", "k1"),
        ("import_1099_r", "Import 1099-R Documents", "Upload 1099-R forms for retirement distributions", "1099_r"),
        ("import_1099_g", "Import 1099-G Documents", "Upload 1099-G forms for government payments", "1099_g"),
        ("import_1099_k", "Import 1099-K Documents", "Upload 1099-K forms for payment platform income", "1099_k"),
        ("import_1098", "Import 1098 Documents", "Upload 1098 forms for mortgage interest", "1098"),
    ]
    for check_id, label, desc, form in doc_checks:
        count = form_counts.get(form, 0)
        status = "complete" if count > 0 else "incomplete"
        detail = f"{count} document(s) imported" if count > 0 else "No documents found"
        items.append({
            "id": check_id, "label": label, "description": desc,
            "status": status, "detail": detail, "category": "documents",
        })

    # --- Transaction import ---
    total_txn = await count_transactions(session, year=tax_year)
    items.append({
        "id": "import_transactions",
        "label": "Import Transaction Statements",
        "description": "Upload credit card and bank statements for the tax year",
        "status": "complete" if total_txn > 0 else "incomplete",
        "detail": f"{total_txn:,} transactions imported" if total_txn > 0 else "No transactions for this year",
        "category": "documents",
    })

    # --- Categorization ---
    uncategorized = await session.execute(
        select(func.count(Transaction.id)).where(
            Transaction.period_year == tax_year,
            Transaction.is_excluded == False,
            Transaction.effective_category.is_(None),
        )
    )
    uncat_count = uncategorized.scalar_one()
    cat_pct = round((1 - uncat_count / max(1, total_txn)) * 100, 1) if total_txn > 0 else 0
    if uncat_count == 0 and total_txn > 0:
        cat_status = "complete"
    elif cat_pct >= 80:
        cat_status = "partial"
    else:
        cat_status = "incomplete"
    items.append({
        "id": "categorize_transactions",
        "label": "Categorize All Transactions",
        "description": "Ensure every transaction has a category (AI + manual review)",
        "status": cat_status,
        "detail": f"{cat_pct}% categorized ({uncat_count:,} remaining)",
        "category": "preparation",
    })

    # --- Business expense review ---
    biz_txn_count = await count_transactions(session, year=tax_year, segment="business")
    biz_reviewed = await session.execute(
        select(func.count(Transaction.id)).where(
            Transaction.period_year == tax_year,
            Transaction.effective_segment == "business",
            Transaction.is_excluded == False,
            Transaction.is_manually_reviewed == True,
        )
    )
    biz_reviewed_count = biz_reviewed.scalar_one()
    if biz_txn_count == 0:
        biz_status = "not_applicable"
        biz_detail = "No business transactions found"
    elif biz_reviewed_count >= biz_txn_count:
        biz_status = "complete"
        biz_detail = f"All {biz_txn_count:,} business transactions reviewed"
    elif biz_reviewed_count > 0:
        biz_status = "partial"
        biz_detail = f"{biz_reviewed_count:,}/{biz_txn_count:,} reviewed"
    else:
        biz_status = "incomplete"
        biz_detail = f"{biz_txn_count:,} business transactions need review"
    items.append({
        "id": "review_business_expenses",
        "label": "Review Business Expenses",
        "description": "Verify all business deductions are correctly categorized and segmented",
        "status": biz_status, "detail": biz_detail, "category": "preparation",
    })

    # --- AI tax analysis ---
    strategies = await get_tax_strategies(session, tax_year=tax_year)
    items.append({
        "id": "run_ai_analysis",
        "label": "Run AI Tax Strategy Analysis",
        "description": "Generate personalized tax optimization strategies",
        "status": "complete" if len(strategies) > 0 else "incomplete",
        "detail": f"{len(strategies)} strategies generated" if strategies else "Not yet run",
        "category": "preparation",
    })

    # --- Quarterly estimated payments (for current/future year) ---
    q_deadlines = [
        ("q1_estimated", "Q1 Estimated Payment", f"Apr 15, {tax_year + 1}"),
        ("q2_estimated", "Q2 Estimated Payment", f"Jun 15, {tax_year + 1}"),
        ("q3_estimated", "Q3 Estimated Payment", f"Sep 15, {tax_year + 1}"),
        ("q4_estimated", "Q4 Estimated Payment", f"Jan 15, {tax_year + 2}"),
    ]
    for qid, qlabel, qdeadline in q_deadlines:
        items.append({
            "id": qid, "label": qlabel,
            "description": f"Federal estimated tax payment due {qdeadline}",
            "status": "incomplete",
            "detail": f"Due {qdeadline} — track manually or via Reminders",
            "category": "payments",
        })

    # --- Filing deadlines ---
    filing_deadline = f"Apr 15, {tax_year + 1}"
    extension_deadline = f"Oct 15, {tax_year + 1}"
    items.append({
        "id": "file_federal", "label": "File Federal Tax Return",
        "description": f"File Form 1040 by {filing_deadline} (or extend to {extension_deadline})",
        "status": "incomplete", "detail": f"Deadline: {filing_deadline}",
        "category": "filing",
    })
    items.append({
        "id": "file_state", "label": "File State Tax Return(s)",
        "description": "File state returns for all states with income allocation",
        "status": "incomplete", "detail": f"Deadline typically {filing_deadline}",
        "category": "filing",
    })

    completed = sum(1 for i in items if i["status"] == "complete")
    applicable = sum(1 for i in items if i["status"] != "not_applicable")
    pct = round(completed / max(1, applicable) * 100, 1)

    return {
        "tax_year": tax_year,
        "items": items,
        "completed": completed,
        "total": applicable,
        "progress_pct": pct,
    }
