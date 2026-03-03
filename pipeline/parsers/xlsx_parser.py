"""
Excel (.xlsx / .xls) parser using pandas + openpyxl.
Extracts all sheets into structured data suitable for AI-assisted
financial analysis.
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class SheetData:
    """One sheet from an Excel workbook."""
    name: str
    headers: list[str]
    rows: list[list[Any]]
    row_count: int
    col_count: int

    def to_text(self, max_rows: int = 200) -> str:
        """Render the sheet as a pipe-delimited text table."""
        lines: list[str] = []
        if self.headers:
            lines.append(" | ".join(str(h) for h in self.headers))
            lines.append("-" * max(len(lines[0]), 20))

        for row in self.rows[:max_rows]:
            lines.append(" | ".join(str(cell) for cell in row))

        if self.row_count > max_rows:
            lines.append(f"... ({self.row_count - max_rows} more rows)")

        return "\n".join(lines)

    def to_dicts(self) -> list[dict[str, Any]]:
        """Convert rows to list of header-keyed dicts."""
        if not self.headers:
            return [{"col_" + str(i): v for i, v in enumerate(row)} for row in self.rows]
        return [dict(zip(self.headers, row)) for row in self.rows]


@dataclass
class ExcelDocument:
    """Structured representation of a parsed Excel workbook."""
    filepath: str
    sheets: list[SheetData]
    metadata: dict = field(default_factory=dict)

    @property
    def sheet_names(self) -> list[str]:
        return [s.name for s in self.sheets]

    @property
    def total_rows(self) -> int:
        return sum(s.row_count for s in self.sheets)

    def get_sheet(self, name: str) -> SheetData | None:
        for s in self.sheets:
            if s.name == name:
                return s
        return None

    @property
    def full_text(self) -> str:
        """All sheets rendered as text, for AI consumption."""
        parts: list[str] = []
        for sheet in self.sheets:
            parts.append(f"=== SHEET: {sheet.name} ({sheet.row_count} rows) ===")
            parts.append(sheet.to_text())
        return "\n\n".join(parts)


def _clean_cell(val: Any) -> Any:
    """Normalize a cell value: NaN → empty string, trim strings."""
    if pd.isna(val):
        return ""
    if isinstance(val, str):
        return val.strip()
    return val


def extract_xlsx(filepath: str, max_rows_per_sheet: int = 5000) -> ExcelDocument:
    """
    Parse an Excel file and return an ExcelDocument with all sheets.

    Raises FileNotFoundError if the file does not exist.
    Raises ValueError if the file cannot be parsed.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Excel file not found: {filepath}")

    try:
        xls = pd.ExcelFile(filepath, engine="openpyxl")
    except Exception as e:
        raise ValueError(f"Cannot open Excel file: {e}") from e

    sheets: list[SheetData] = []

    for sheet_name in xls.sheet_names:
        try:
            df = xls.parse(sheet_name, dtype=str, nrows=max_rows_per_sheet)
        except Exception as e:
            logger.warning(f"Skipping sheet '{sheet_name}' in {path.name}: {e}")
            continue

        if df.empty:
            continue

        # Drop fully empty rows and columns
        df = df.dropna(how="all").dropna(axis=1, how="all")
        if df.empty:
            continue

        df.columns = [str(c).strip() for c in df.columns]

        # Skip sheets that are just a single unnamed column of noise
        if len(df.columns) == 1 and df.columns[0].startswith("Unnamed"):
            continue

        headers = list(df.columns)
        rows: list[list[Any]] = []
        for _, row in df.iterrows():
            rows.append([_clean_cell(v) for v in row])

        sheets.append(SheetData(
            name=sheet_name,
            headers=headers,
            rows=rows,
            row_count=len(rows),
            col_count=len(headers),
        ))

    metadata: dict = {}
    try:
        wb = xls.book
        if hasattr(wb, "properties") and wb.properties:
            props = wb.properties
            if props.title:
                metadata["title"] = props.title
            if props.creator:
                metadata["author"] = props.creator
            if props.created:
                metadata["created"] = props.created.isoformat()
    except Exception:
        pass

    logger.info(
        f"Extracted {len(sheets)} sheets ({sum(s.row_count for s in sheets)} total rows) "
        f"from {path.name}"
    )
    return ExcelDocument(filepath=filepath, sheets=sheets, metadata=metadata)
