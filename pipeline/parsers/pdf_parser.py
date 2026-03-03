"""
PDF text extractor using pdfplumber.
Returns raw text per page and structured table data.
For machine-generated PDFs (W-2, 1099s, brokerage statements).
"""
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pdfplumber

logger = logging.getLogger(__name__)


@dataclass
class PDFPage:
    page_num: int
    text: str
    tables: list[list[list[str]]] = field(default_factory=list)


@dataclass
class PDFDocument:
    filepath: str
    pages: list[PDFPage]

    @property
    def full_text(self) -> str:
        return "\n\n--- PAGE BREAK ---\n\n".join(p.text for p in self.pages)

    @property
    def page_count(self) -> int:
        return len(self.pages)


def extract_pdf(filepath: str, max_pages: int = 50) -> PDFDocument:
    """
    Extract text and tables from a PDF file.
    Returns a PDFDocument with per-page text and tables.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {filepath}")

    pages: list[PDFPage] = []
    with pdfplumber.open(filepath) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            text = page.extract_text() or ""
            tables = []
            try:
                raw_tables = page.extract_tables()
                if raw_tables:
                    for tbl in raw_tables:
                        # Normalize: replace None cells with empty string
                        normalized = [
                            [str(cell).strip() if cell is not None else "" for cell in row]
                            for row in tbl
                        ]
                        tables.append(normalized)
            except Exception as e:
                logger.warning(f"Table extraction failed on page {i+1}: {e}")
            pages.append(PDFPage(page_num=i + 1, text=text, tables=tables))

    logger.info(f"Extracted {len(pages)} pages from {path.name}")
    return PDFDocument(filepath=filepath, pages=pages)


# ---------------------------------------------------------------------------
# Heuristic field extractors for common tax forms
# ---------------------------------------------------------------------------

def _find_amount(text: str, patterns: list[str]) -> Optional[float]:
    """Search text for amount following any of the given label patterns."""
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1).replace(",", "").replace("$", "").strip()
            try:
                return float(raw)
            except ValueError:
                continue
    return None


def _find_text(text: str, patterns: list[str]) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def extract_w2_fields(doc: PDFDocument) -> dict:
    """
    Heuristic extraction of W-2 fields from PDF text.
    Returns a dict of field names → values.
    For ambiguous/complex W-2s, Claude-assisted extraction is used as fallback.
    """
    text = doc.full_text
    fields: dict = {}

    # Employer / employee info
    fields["payer_name"] = _find_text(text, [
        r"employer(?:'s)?\s+name[,\s]+address.*?\n([A-Z][^\n]{2,60})",
        r"c\s+employer(?:'s)?\s+name[^\n]*\n([A-Z][^\n]{2,60})",
    ])
    fields["payer_ein"] = _find_text(text, [
        r"employer(?:'s)?\s+(?:identification|id)\s+number[:\s]+(\d{2}-\d{7})",
        r"\b(\d{2}-\d{7})\b",
    ])

    # Box 1–6
    fields["w2_wages"] = _find_amount(text, [
        r"(?:box\s*1|wages,?\s*tips)[^\n$]*?\$?([\d,]+\.?\d*)",
        r"1\s+wages,?\s*tips[^\n$]*\$?([\d,]+\.?\d*)",
    ])
    fields["w2_federal_tax_withheld"] = _find_amount(text, [
        r"(?:box\s*2|federal\s+income\s+tax\s+withheld)[^\n$]*?\$?([\d,]+\.?\d*)",
        r"2\s+federal[^\n$]*?\$?([\d,]+\.?\d*)",
    ])
    fields["w2_ss_wages"] = _find_amount(text, [
        r"(?:box\s*3|social\s+security\s+wages)[^\n$]*?\$?([\d,]+\.?\d*)",
    ])
    fields["w2_ss_tax_withheld"] = _find_amount(text, [
        r"(?:box\s*4|social\s+security\s+tax\s+withheld)[^\n$]*?\$?([\d,]+\.?\d*)",
    ])
    fields["w2_medicare_wages"] = _find_amount(text, [
        r"(?:box\s*5|medicare\s+wages)[^\n$]*?\$?([\d,]+\.?\d*)",
    ])
    fields["w2_medicare_tax_withheld"] = _find_amount(text, [
        r"(?:box\s*6|medicare\s+tax\s+withheld)[^\n$]*?\$?([\d,]+\.?\d*)",
    ])

    # Multi-state boxes 15–17
    # Find all state code matches
    state_pattern = re.finditer(
        r"(?:box\s*15\s+|state\s*)([A-Z]{2})\s+[\d-]+\s+"
        r"(?:box\s*16\s+|state\s+wages\s*)?\$?([\d,]+\.?\d*)\s+"
        r"(?:box\s*17\s+|state\s+income\s+tax\s*)?\$?([\d,]+\.?\d*)",
        text,
        re.IGNORECASE,
    )
    allocations = []
    for m in state_pattern:
        try:
            allocations.append({
                "state": m.group(1).upper(),
                "wages": float(m.group(2).replace(",", "")),
                "tax": float(m.group(3).replace(",", "")),
            })
        except (ValueError, IndexError):
            pass
    if allocations:
        import json
        fields["w2_state_allocations"] = json.dumps(allocations)
        # Primary state from first allocation
        fields["w2_state"] = allocations[0]["state"]
        fields["w2_state_wages"] = allocations[0]["wages"]
        fields["w2_state_income_tax"] = allocations[0]["tax"]

    return fields


def extract_1099_nec_fields(doc: PDFDocument) -> dict:
    text = doc.full_text
    fields: dict = {}
    fields["payer_name"] = _find_text(text, [r"payer(?:'s)?\s+name[^\n]*\n([A-Z][^\n]{2,60})"])
    fields["payer_ein"] = _find_text(text, [r"payer(?:'s)?\s+(?:tin|ein|id)[:\s]+(\d{2}-\d{7})"])
    fields["nec_nonemployee_compensation"] = _find_amount(text, [
        r"(?:box\s*1|nonemployee\s+compensation)[^\n$]*?\$?([\d,]+\.?\d*)",
        r"1\s+nonemployee[^\n$]*?\$?([\d,]+\.?\d*)",
    ])
    fields["nec_federal_tax_withheld"] = _find_amount(text, [
        r"(?:box\s*4|federal\s+income\s+tax\s+withheld)[^\n$]*?\$?([\d,]+\.?\d*)",
    ])
    return fields


def extract_1099_div_fields(doc: PDFDocument) -> dict:
    text = doc.full_text
    fields: dict = {}
    fields["payer_name"] = _find_text(text, [r"payer(?:'s)?\s+name[^\n]*\n([A-Z][^\n]{2,60})"])
    fields["payer_ein"] = _find_text(text, [r"payer(?:'s)?\s+(?:tin|ein|id)[:\s]+(\d{2}-\d{7})"])
    fields["div_total_ordinary"] = _find_amount(text, [
        r"(?:1a|total\s+ordinary\s+dividends)[^\n$]*?\$?([\d,]+\.?\d*)",
    ])
    fields["div_qualified"] = _find_amount(text, [
        r"(?:1b|qualified\s+dividends)[^\n$]*?\$?([\d,]+\.?\d*)",
    ])
    fields["div_total_capital_gain"] = _find_amount(text, [
        r"(?:2a|total\s+capital\s+gain)[^\n$]*?\$?([\d,]+\.?\d*)",
    ])
    fields["div_federal_tax_withheld"] = _find_amount(text, [
        r"(?:4|federal\s+income\s+tax\s+withheld)[^\n$]*?\$?([\d,]+\.?\d*)",
    ])
    return fields


def extract_1099_int_fields(doc: PDFDocument) -> dict:
    text = doc.full_text
    fields: dict = {}
    fields["payer_name"] = _find_text(text, [r"payer(?:'s)?\s+name[^\n]*\n([A-Z][^\n]{2,60})"])
    fields["int_interest"] = _find_amount(text, [
        r"(?:box\s*1|interest\s+income)[^\n$]*?\$?([\d,]+\.?\d*)",
        r"1\s+interest\s+income[^\n$]*?\$?([\d,]+\.?\d*)",
    ])
    fields["int_federal_tax_withheld"] = _find_amount(text, [
        r"(?:box\s*4|federal\s+income\s+tax\s+withheld)[^\n$]*?\$?([\d,]+\.?\d*)",
    ])
    return fields


def detect_form_type(doc: PDFDocument) -> str:
    """
    Heuristically detect form type from PDF text.
    Returns one of: w2, 1099_nec, 1099_div, 1099_b, 1099_int, brokerage_statement, other
    """
    text = doc.full_text.lower()
    if "wage and tax statement" in text or "w-2" in text:
        return "w2"
    if "nonemployee compensation" in text or "1099-nec" in text:
        return "1099_nec"
    if "dividends and distributions" in text or "1099-div" in text:
        return "1099_div"
    if "proceeds from broker" in text or "1099-b" in text:
        return "1099_b"
    if "interest income" in text and "1099" in text:
        return "1099_int"
    if any(k in text for k in ["account summary", "portfolio", "trade confirmations", "realized gain"]):
        return "brokerage_statement"
    return "other"
