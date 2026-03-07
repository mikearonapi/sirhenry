"""
Pay Stub Parser — extracts earnings, deductions, and benefits data from
pay stubs using Claude vision. Returns suggestions for household profile
and benefits package updates.
"""
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import Document

logger = logging.getLogger(__name__)


PAYSTUB_EXTRACTION_PROMPT = """You are a pay stub data extractor. Extract the following fields from this pay stub / earnings statement.

Return a JSON object with these fields (use null for missing values):
{
  "employer_name": "Company Name",
  "employee_name": "John Smith",
  "pay_period_start": "2026-02-01",
  "pay_period_end": "2026-02-15",
  "pay_date": "2026-02-20",

  "gross_pay": 7500.00,
  "net_pay": 5200.00,
  "ytd_gross": 30000.00,
  "ytd_net": 20800.00,

  "federal_withholding": 1200.00,
  "federal_withholding_ytd": 4800.00,
  "state_withholding": 450.00,
  "state_withholding_ytd": 1800.00,
  "state": "CA",
  "social_security": 465.00,
  "social_security_ytd": 1860.00,
  "medicare": 108.75,
  "medicare_ytd": 435.00,

  "retirement_401k": 750.00,
  "retirement_401k_ytd": 3000.00,
  "retirement_roth_401k": null,
  "retirement_roth_401k_ytd": null,
  "employer_401k_match": 375.00,
  "employer_401k_match_ytd": 1500.00,

  "hsa_contribution": 150.00,
  "hsa_contribution_ytd": 600.00,
  "hsa_employer_contribution": 50.00,
  "fsa_contribution": null,

  "health_premium": 250.00,
  "dental_premium": 25.00,
  "vision_premium": 10.00,
  "life_insurance": 15.00,
  "disability_insurance": 20.00,

  "espp_contribution": null,
  "stock_purchase": null,

  "filing_status": "Married",
  "allowances": 2,

  "hours_worked": 80,
  "hourly_rate": null,
  "annual_salary": 195000.00
}

Important:
- All dollar amounts should be numeric (no $ or commas)
- Dates should be YYYY-MM-DD format
- Include YTD (year-to-date) amounts where visible
- If annual salary is shown, include it
- For 401k, distinguish between traditional and Roth if labeled
"""


async def import_paystub(
    session: AsyncSession,
    file_path: str,
) -> dict:
    """Extract pay stub data from PDF or image. Returns suggestions, does NOT auto-apply."""
    path = Path(file_path)
    if not path.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    suffix = path.suffix.lower()
    is_image = suffix in (".jpg", ".jpeg", ".png")

    text_content = ""
    images = []

    if is_image:
        import base64
        with open(file_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")
        media_type = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
        images.append({"type": media_type, "data": img_data})
    else:
        try:
            from pipeline.parsers.pdf_parser import extract_pdf, render_pdf_pages
            pdf_doc = extract_pdf(file_path)
            text_content = pdf_doc.full_text[:8000] if pdf_doc.full_text else ""
            if len(text_content.strip()) < 100:
                images = render_pdf_pages(file_path, max_pages=2)
        except Exception as e:
            logger.warning(f"PDF extraction failed: {e}")
            return {"status": "error", "message": f"Failed to read PDF: {e}"}

    # Send to Claude for extraction
    try:
        extracted = await _extract_with_claude(text_content, images)
    except Exception as e:
        logger.error(f"Claude extraction failed: {e}")
        return {"status": "error", "message": f"AI extraction failed: {e}"}

    if not extracted:
        return {"status": "error", "message": "Could not extract pay stub data"}

    # Create Document record
    import hashlib
    with open(file_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    doc = Document(
        filename=path.name,
        original_path=str(path),
        file_type="pdf" if not is_image else suffix.lstrip("."),
        document_type="pay_stub",
        file_hash=file_hash,
        status="completed",
        processed_at=datetime.utcnow(),
    )
    session.add(doc)
    await session.flush()

    # Build suggestions for household profile and benefits
    suggestions = _build_suggestions(extracted)

    return {
        "status": "completed",
        "document_id": doc.id,
        "extracted": extracted,
        "suggestions": suggestions,
        "message": f"Extracted pay stub from {extracted.get('employer_name', 'unknown employer')}",
    }


def _build_suggestions(data: dict) -> dict:
    """Build household profile and benefits update suggestions from extracted data."""
    household_updates = {}
    benefit_updates = {}

    # Household profile suggestions
    employer = data.get("employer_name")
    if employer:
        household_updates["employer"] = employer

    annual_salary = data.get("annual_salary")
    if not annual_salary:
        gross = data.get("gross_pay")
        ytd = data.get("ytd_gross")
        if ytd and data.get("pay_date"):
            # Extrapolate from YTD
            try:
                pay_date = datetime.strptime(data["pay_date"], "%Y-%m-%d")
                months_elapsed = max(pay_date.month, 1)
                annual_salary = round(ytd / months_elapsed * 12, 2)
            except (ValueError, ZeroDivisionError):
                pass
        elif gross:
            # Assume biweekly pay
            annual_salary = round(gross * 26, 2)

    if annual_salary:
        household_updates["income"] = annual_salary

    state = data.get("state")
    if state:
        household_updates["work_state"] = state

    # Benefits suggestions
    if data.get("retirement_401k") or data.get("retirement_401k_ytd"):
        benefit_updates["has_401k"] = True
        if data.get("retirement_401k"):
            benefit_updates["annual_401k_contribution"] = round(data["retirement_401k"] * 26, 2)  # assume biweekly

    if data.get("employer_401k_match"):
        benefit_updates["has_401k"] = True
        match = data["employer_401k_match"]
        pre_tax = data.get("retirement_401k", 0)
        if pre_tax and pre_tax > 0:
            match_pct = round(match / pre_tax * 100, 1)
            benefit_updates["employer_match_pct"] = match_pct

    if data.get("hsa_contribution") or data.get("hsa_contribution_ytd"):
        benefit_updates["has_hsa"] = True
        if data.get("hsa_employer_contribution"):
            benefit_updates["hsa_employer_contribution"] = round(data["hsa_employer_contribution"] * 26, 2)

    if data.get("health_premium"):
        # Convert from per-pay-period to monthly (assume biweekly)
        benefit_updates["health_premium_monthly"] = round(data["health_premium"] * 26 / 12, 2)

    if data.get("dental_premium") or data.get("vision_premium"):
        dental = data.get("dental_premium", 0) or 0
        vision = data.get("vision_premium", 0) or 0
        benefit_updates["dental_vision_monthly"] = round((dental + vision) * 26 / 12, 2)

    if data.get("espp_contribution"):
        benefit_updates["has_espp"] = True

    if data.get("retirement_roth_401k"):
        benefit_updates["has_roth_401k"] = True

    return {
        "household": household_updates,
        "benefits": benefit_updates,
    }


async def _extract_with_claude(text: str, images: list) -> dict | None:
    """Send pay stub to Claude for field extraction."""
    from pipeline.utils import get_async_claude_client, call_claude_async_with_retry

    client = get_async_claude_client()

    content = []
    for img in images:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": img["type"],
                "data": img["data"],
            },
        })
    if text:
        content.append({"type": "text", "text": f"Document text:\n{text}"})
    content.append({"type": "text", "text": PAYSTUB_EXTRACTION_PROMPT})

    response = await call_claude_async_with_retry(
        client,
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": content}],
    )

    response_text = response.content[0].text
    json_match = re.search(r"\{[\s\S]*\}", response_text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return None
