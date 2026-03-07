"""
Insurance Document Parser — extracts policy details from insurance
declaration pages (PDF/image) using Claude vision.

Same pattern as tax_doc.py: PDF text extraction → Claude extraction → DB record.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import Document, InsurancePolicy

logger = logging.getLogger(__name__)


INSURANCE_EXTRACTION_PROMPT = """You are an insurance document data extractor. Extract the following fields from this insurance declaration page, policy document, or insurance card.

Return a JSON object with these fields (use null for missing values):
{
  "provider": "Insurance company name",
  "policy_number": "Policy number",
  "policy_type": "life | auto | home | renters | umbrella | disability | health | dental | vision | pet | other",
  "coverage_amount": 500000.00,
  "deductible": 1000.00,
  "oop_max": 5000.00,
  "annual_premium": 2400.00,
  "monthly_premium": 200.00,
  "renewal_date": "2026-06-15",
  "effective_date": "2025-06-15",
  "named_insured": "John and Jane Smith",
  "property_address": "123 Main St, Anytown, CA 90210",
  "vehicle_info": "2022 Toyota Camry",
  "employer_provided": false,
  "additional_details": "Any other relevant coverage details"
}

Important:
- All dollar amounts should be numeric (no $ or commas)
- Dates should be YYYY-MM-DD format
- policy_type must be one of the listed values
- If the document shows both annual and monthly premium, include both
- For auto insurance, include vehicle_info
- For home/renters, include property_address
"""


async def import_insurance_doc(
    session: AsyncSession,
    file_path: str,
    household_id: int | None = None,
) -> dict:
    """Extract insurance policy data from a PDF or image file."""
    path = Path(file_path)
    if not path.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    suffix = path.suffix.lower()
    is_image = suffix in (".jpg", ".jpeg", ".png")

    # Extract text and/or render images
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
        return {"status": "error", "message": "Could not extract insurance data from document"}

    # Create Document record
    import hashlib
    with open(file_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    doc = Document(
        filename=path.name,
        original_path=str(path),
        file_type="pdf" if not is_image else suffix.lstrip("."),
        document_type="insurance",
        file_hash=file_hash,
        status="completed",
        processed_at=datetime.utcnow(),
    )
    session.add(doc)
    await session.flush()

    # Create or update InsurancePolicy
    policy_data = {
        "household_id": household_id,
        "policy_type": extracted.get("policy_type", "other"),
        "provider": extracted.get("provider"),
        "policy_number": extracted.get("policy_number"),
        "coverage_amount": _to_float(extracted.get("coverage_amount")),
        "deductible": _to_float(extracted.get("deductible")),
        "oop_max": _to_float(extracted.get("oop_max")),
        "annual_premium": _to_float(extracted.get("annual_premium")),
        "monthly_premium": _to_float(extracted.get("monthly_premium")),
        "employer_provided": extracted.get("employer_provided", False),
        "is_active": True,
    }

    # Parse renewal date
    renewal = extracted.get("renewal_date")
    if renewal:
        try:
            from datetime import date
            policy_data["renewal_date"] = date.fromisoformat(renewal)
        except (ValueError, TypeError):
            pass

    # Check for duplicate by policy number
    if extracted.get("policy_number"):
        existing = await session.execute(
            select(InsurancePolicy).where(
                InsurancePolicy.policy_number == extracted["policy_number"]
            )
        )
        existing_policy = existing.scalar_one_or_none()
        if existing_policy:
            for k, v in policy_data.items():
                if v is not None:
                    setattr(existing_policy, k, v)
            existing_policy.updated_at = datetime.utcnow()
            return {
                "status": "updated",
                "policy_id": existing_policy.id,
                "document_id": doc.id,
                "extracted_fields": extracted,
                "message": f"Updated existing {extracted.get('policy_type', '')} policy from {extracted.get('provider', 'unknown')}",
            }

    policy = InsurancePolicy(**policy_data)
    session.add(policy)
    await session.flush()

    return {
        "status": "completed",
        "policy_id": policy.id,
        "document_id": doc.id,
        "extracted_fields": extracted,
        "message": f"Imported {extracted.get('policy_type', '')} policy from {extracted.get('provider', 'unknown')}",
    }


async def _extract_with_claude(text: str, images: list) -> dict | None:
    """Send document content to Claude for field extraction."""
    import os
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
    content.append({"type": "text", "text": INSURANCE_EXTRACTION_PROMPT})

    response = await call_claude_async_with_retry(
        client,
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": content}],
    )

    # Parse JSON from response
    response_text = response.content[0].text
    # Try to extract JSON from response
    import re
    json_match = re.search(r"\{[\s\S]*\}", response_text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return None


def _to_float(val) -> float | None:
    """Safely convert a value to float."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
