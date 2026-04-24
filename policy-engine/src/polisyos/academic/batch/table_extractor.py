"""Optional table extraction from academic PDFs.

Dependencies (marker-pdf) are OPTIONAL — only installed on server.
Falls back gracefully when not available.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)

try:
    from marker.converters.pdf import PdfConverter  # type: ignore[import-untyped]

    _HAS_MARKER = True
except ImportError:
    _HAS_MARKER = False

# Regex patterns for extracting numeric estimates from table cells
_COEFF_RE = re.compile(r"[-+]?\d+\.?\d*")
_SE_PAREN_RE = re.compile(r"\((\d+\.?\d*)\)")
_STAR_RE = re.compile(r"\*{1,3}")
_CI_RE = re.compile(r"\[?\(?([-+]?\d+\.?\d*)\s*[,;]\s*([-+]?\d+\.?\d*)\)?\]?")


def is_available() -> bool:
    """Check if table extraction dependencies are installed."""
    return _HAS_MARKER


def extract_tables_from_pdf(pdf_path: Path) -> list[dict[str, Any]]:
    """Extract structured tables from a PDF file.

    Returns a list of table dicts, each with:
      - table_index: int
      - headers: list[str]
      - rows: list[list[str]]
      - numeric_cells: list[dict] with row, col, value, std_error, significance

    Returns empty list if dependencies not installed or extraction fails.
    """
    if not _HAS_MARKER:
        return []

    if not pdf_path.exists():
        return []

    try:
        converter = PdfConverter(str(pdf_path))
        document = converter()
    except Exception:
        logger.warning("table_extractor: failed to convert %s", pdf_path, exc_info=True)
        return []

    tables: list[dict[str, Any]] = []
    table_index = 0

    for page in getattr(document, "pages", []):
        for block in getattr(page, "blocks", []):
            if getattr(block, "block_type", "") != "Table":
                continue

            cells = getattr(block, "cells", [])
            if not cells:
                continue

            headers: list[str] = []
            rows: list[list[str]] = []
            numeric_cells: list[dict[str, Any]] = []

            for row_idx, row in enumerate(cells):
                row_values = [str(getattr(cell, "text", cell) or "").strip() for cell in row]
                if row_idx == 0:
                    headers = row_values
                else:
                    rows.append(row_values)

                for col_idx, cell_text in enumerate(row_values):
                    parsed = _parse_numeric_cell(cell_text)
                    if parsed is not None:
                        numeric_cells.append(
                            {
                                "row": row_idx,
                                "col": col_idx,
                                "header": headers[col_idx] if col_idx < len(headers) else "",
                                **parsed,
                            }
                        )

            tables.append(
                {
                    "table_index": table_index,
                    "headers": headers,
                    "rows": rows,
                    "numeric_cells": numeric_cells,
                }
            )
            table_index += 1

    return tables


def _parse_numeric_cell(text: str) -> dict[str, Any] | None:
    """Parse a table cell for numeric coefficient + optional SE/CI."""
    text = text.strip()
    if not text or not _COEFF_RE.search(text):
        return None

    significance = len(_STAR_RE.findall(text))
    text_clean = _STAR_RE.sub("", text).strip()

    se_match = _SE_PAREN_RE.search(text_clean)
    ci_match = _CI_RE.search(text_clean)

    coeff_text = _SE_PAREN_RE.sub("", text_clean)
    coeff_text = _CI_RE.sub("", coeff_text).strip()
    coeff_match = _COEFF_RE.search(coeff_text)

    if coeff_match is None:
        return None

    result: dict[str, Any] = {
        "value": float(coeff_match.group()),
        "significance_stars": significance,
    }

    if se_match:
        result["std_error"] = float(se_match.group(1))
    if ci_match:
        result["confidence_interval"] = [float(ci_match.group(1)), float(ci_match.group(2))]

    return result


def tables_to_parameters(
    tables: list[dict[str, Any]],
    *,
    openalex_id: str = "",
) -> list[dict[str, Any]]:
    """Convert extracted table numeric cells to EvidenceParameter-like dicts."""
    parameters: list[dict[str, Any]] = []
    for table in tables:
        for cell in table.get("numeric_cells", []):
            header = str(cell.get("header") or "").strip()
            if not header:
                continue
            param: dict[str, Any] = {
                "name": header.lower().replace(" ", "_"),
                "display_name": header,
                "parameter_type": "quantitative",
                "value": cell.get("value"),
                "unit": "",
                "evidence_strength": "unknown",
                "source": "table_extraction",
                "openalex_id": openalex_id,
            }
            if "std_error" in cell:
                param["std_error"] = cell["std_error"]
            if "confidence_interval" in cell:
                param["confidence_interval"] = cell["confidence_interval"]
            parameters.append(param)
    return parameters


__all__ = [
    "extract_tables_from_pdf",
    "is_available",
    "tables_to_parameters",
]
