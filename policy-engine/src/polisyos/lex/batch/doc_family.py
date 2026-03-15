"""Document family helpers for quality routing and reporting."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from polisyos.lex.batch.doc_identity import doc_type_category

_APPENDIX_STRUCT_KINDS = {"appendix", "table_row", "enumeration_item", "paragraph"}
_APPENDIX_SECTION_ROLES = {
    "appendix",
    "appendix_section",
    "table_clause",
    "table_header",
    "catalog_entry",
    "form_clause",
    "form_header",
    "questionnaire_item",
    "attachment_inventory",
}


def infer_doc_type_category(*, doc_type: str = "", doc_name: str = "") -> str:
    """Return a stable category for one legal document."""
    return doc_type_category(doc_type or doc_name) or "other"


def is_appendix_heavy(provision_rows: Sequence[dict[str, Any]] | None) -> bool:
    """Heuristic for appendix/list/table dominated documents."""
    if not provision_rows:
        return False
    total = 0
    appendix_like = 0
    appendix_ids = 0
    table_ids = 0
    for row in provision_rows:
        if not isinstance(row, dict):
            continue
        total += 1
        struct_kind = str(row.get("struct_kind") or row.get("kind") or "").strip().lower()
        section_role = str(row.get("section_role") or "").strip().lower()
        if struct_kind in _APPENDIX_STRUCT_KINDS or section_role in _APPENDIX_SECTION_ROLES:
            appendix_like += 1
        if row.get("appendix_id") is not None:
            appendix_ids += 1
        if row.get("table_id") is not None:
            table_ids += 1
    if total <= 0:
        return False
    appendix_ratio = appendix_like / total
    return appendix_ratio >= 0.45 or appendix_ids >= 2 or table_ids >= 2


def classify_doc_family(
    *,
    doc_type: str = "",
    doc_name: str = "",
    doc_type_category_value: str | None = None,
    provision_rows: Sequence[dict[str, Any]] | None = None,
) -> str:
    """Map raw doc categories into stable quality families."""
    category = (doc_type_category_value or infer_doc_type_category(doc_type=doc_type, doc_name=doc_name)).strip().lower()
    if category in {"constitution", "law", "code"}:
        return "law"
    if category in {"treaty", "protocol"}:
        return "treaty_protocol"
    appendix_heavy = is_appendix_heavy(provision_rows)
    if category in {"cabinet_resolution", "resolution", "decree", "decision", "directive"}:
        if appendix_heavy:
            return "appendix_heavy"
        return "decree_resolution"
    if category in {"order", "regulation"}:
        if appendix_heavy:
            return "appendix_heavy"
        return "order"
    if appendix_heavy:
        return "appendix_heavy"
    return "other"


__all__ = [
    "classify_doc_family",
    "infer_doc_type_category",
    "is_appendix_heavy",
]
