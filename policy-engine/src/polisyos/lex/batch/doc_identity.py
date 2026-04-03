"""Public batch doc identity module API."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from polisyos.lex.common import parse_iso_date

_WS_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^0-9a-zа-яіїєґ]+", re.IGNORECASE)
_NUMBER_NON_WORD_RE = re.compile(r"[^0-9a-zа-яіїєґ/-]+", re.IGNORECASE)
_DATE_DMY_RE = re.compile(r"^(?P<day>\d{2})\.(?P<month>\d{2})\.(?P<year>\d{4})$")


def _compact_ws(value: str) -> str:
    return _WS_RE.sub(" ", value.strip())


def _stable_hash(*parts: str, size: int = 18) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:size]


def normalize_text_key(value: str) -> str:
    """Normalize text key helper."""
    return _NON_ALNUM_RE.sub(" ", _compact_ws(value).lower()).strip()


def normalize_ref_number(value: str) -> str:
    """Normalize ref number helper."""
    return _NUMBER_NON_WORD_RE.sub("", _compact_ws(value).lower())


def normalize_publishers(value: Any) -> str:
    """Normalize publishers helper."""
    if isinstance(value, str):
        parts = [value]
    elif isinstance(value, (list, tuple)):
        parts = [str(item) for item in value if str(item).strip()]
    else:
        parts = []
    return normalize_text_key(" ".join(parts))


def doc_type_category(value: str) -> str:
    """Doc type category helper."""
    raw = normalize_text_key(value)
    if not raw:
        return ""
    if "конституц" in raw:
        return "constitution"
    if "кодекс" in raw:
        return "code"
    if "догов" in raw or "угод" in raw or "конвенц" in raw:
        return "treaty"
    if "протокол" in raw:
        return "protocol"
    if "закон" in raw:
        return "law"
    if "постан" in raw and ("кабінет" in raw or "кму" in raw):
        return "cabinet_resolution"
    if "постан" in raw:
        return "resolution"
    if "наказ" in raw:
        return "order"
    if "рішен" in raw:
        return "decision"
    if "указ" in raw:
        return "decree"
    if "розпоряджен" in raw:
        return "directive"
    if "положення" in raw or "порядок" in raw or "регламент" in raw:
        return "regulation"
    return raw


def parse_doc_date(value: str | None) -> date | None:
    """Parse doc date helper."""
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    parsed_iso = parse_iso_date(raw)
    if parsed_iso is not None:
        return parsed_iso
    match = _DATE_DMY_RE.fullmatch(raw)
    if match is None:
        return None
    try:
        return date(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        )
    except ValueError:
        return None


def doc_family_id(meta: dict[str, Any]) -> str:
    """Doc family ID helper."""
    doc_type = doc_type_category(str(meta.get("doc_type") or ""))
    number = normalize_ref_number(str(meta.get("number") or meta.get("reg_number") or ""))
    publisher = normalize_publishers(meta.get("publisher"))
    reestr_code = normalize_ref_number(str(meta.get("reestr_code") or ""))
    name = normalize_text_key(str(meta.get("name") or ""))
    if doc_type and number:
        return _stable_hash("family", doc_type, number, publisher or "no_publisher")
    if reestr_code:
        return _stable_hash("family", "reestr", reestr_code)
    return _stable_hash("family", doc_type or "generic", name or "unknown")


def version_sort_key(meta: dict[str, Any], doc_id: str) -> tuple[date, str, str]:
    """Version sort key helper."""
    doc_date = (
        parse_doc_date(str(meta.get("date_acc") or ""))
        or parse_doc_date(str(meta.get("reestr_date") or ""))
        or parse_doc_date(str(meta.get("reg_date") or ""))
        or date.min
    )
    return (
        doc_date,
        normalize_text_key(str(meta.get("status") or "")),
        doc_id,
    )


@dataclass(frozen=True)
class DocIndexEntry:
    """Doc index entry data model."""
    doc_id: str
    family_id: str
    reestr_code: str
    reestr_code_norm: str
    doc_type: str
    doc_type_category: str
    doc_number: str
    doc_number_norm: str
    reg_number: str
    reg_number_norm: str
    name: str
    name_norm: str
    publisher: str
    publisher_norm: str
    doc_date_acc: str
    doc_date: date | None
    status: str
    meta: dict[str, Any]


@dataclass(frozen=True)
class DocResolutionIndex:
    """Doc resolution index public type."""
    entries: list[DocIndexEntry]
    by_doc_id: dict[str, DocIndexEntry]
    by_reestr_code: dict[str, list[DocIndexEntry]]
    by_number: dict[str, list[DocIndexEntry]]
    by_number_date: dict[tuple[str, str], list[DocIndexEntry]]
    by_reg_number: dict[str, list[DocIndexEntry]]
    by_reg_number_date: dict[tuple[str, str], list[DocIndexEntry]]
    by_family: dict[str, list[DocIndexEntry]]
    latest_by_family: dict[str, DocIndexEntry]


def build_doc_resolution_index(doc_metadata: dict[str, dict[str, Any]]) -> DocResolutionIndex:
    """Build doc resolution index."""
    entries: list[DocIndexEntry] = []
    by_doc_id: dict[str, DocIndexEntry] = {}
    by_reestr_code: dict[str, list[DocIndexEntry]] = {}
    by_number: dict[str, list[DocIndexEntry]] = {}
    by_number_date: dict[tuple[str, str], list[DocIndexEntry]] = {}
    by_reg_number: dict[str, list[DocIndexEntry]] = {}
    by_reg_number_date: dict[tuple[str, str], list[DocIndexEntry]] = {}
    by_family: dict[str, list[DocIndexEntry]] = {}

    for doc_id, raw_meta in sorted(doc_metadata.items()):
        meta = dict(raw_meta)
        publisher_parts = meta.get("publisher")
        publisher = (
            " ".join(str(item) for item in publisher_parts)
            if isinstance(publisher_parts, (list, tuple))
            else str(publisher_parts or "")
        )
        entry = DocIndexEntry(
            doc_id=doc_id,
            family_id=doc_family_id(meta),
            reestr_code=str(meta.get("reestr_code") or ""),
            reestr_code_norm=normalize_ref_number(str(meta.get("reestr_code") or "")),
            doc_type=str(meta.get("doc_type") or ""),
            doc_type_category=doc_type_category(str(meta.get("doc_type") or "")),
            doc_number=str(meta.get("number") or ""),
            doc_number_norm=normalize_ref_number(str(meta.get("number") or "")),
            reg_number=str(meta.get("reg_number") or ""),
            reg_number_norm=normalize_ref_number(str(meta.get("reg_number") or "")),
            name=str(meta.get("name") or ""),
            name_norm=normalize_text_key(str(meta.get("name") or "")),
            publisher=publisher,
            publisher_norm=normalize_publishers(meta.get("publisher")),
            doc_date_acc=str(meta.get("date_acc") or ""),
            doc_date=parse_doc_date(str(meta.get("date_acc") or "")),
            status=str(meta.get("status") or ""),
            meta=meta,
        )
        if entry.name_norm:
            entries.append(entry)
        by_doc_id[doc_id] = entry
        if entry.reestr_code_norm:
            by_reestr_code.setdefault(entry.reestr_code_norm, []).append(entry)
        if entry.doc_number_norm:
            by_number.setdefault(entry.doc_number_norm, []).append(entry)
            if entry.doc_date_acc:
                by_number_date.setdefault((entry.doc_number_norm, entry.doc_date_acc), []).append(entry)
        if entry.reg_number_norm:
            by_reg_number.setdefault(entry.reg_number_norm, []).append(entry)
            if entry.doc_date_acc:
                by_reg_number_date.setdefault((entry.reg_number_norm, entry.doc_date_acc), []).append(entry)
        by_family.setdefault(entry.family_id, []).append(entry)

    latest_by_family: dict[str, DocIndexEntry] = {}
    for family_id, family_entries in by_family.items():
        ordered = sorted(
            family_entries,
            key=lambda item: version_sort_key(item.meta, item.doc_id),
        )
        by_family[family_id] = ordered
        named_ordered = [item for item in ordered if item.name_norm]
        latest_by_family[family_id] = (named_ordered or ordered)[-1]

    return DocResolutionIndex(
        entries=entries,
        by_doc_id=by_doc_id,
        by_reestr_code=by_reestr_code,
        by_number=by_number,
        by_number_date=by_number_date,
        by_reg_number=by_reg_number,
        by_reg_number_date=by_reg_number_date,
        by_family=by_family,
        latest_by_family=latest_by_family,
    )


__all__ = [
    "DocIndexEntry",
    "DocResolutionIndex",
    "build_doc_resolution_index",
    "doc_family_id",
    "doc_type_category",
    "normalize_publishers",
    "normalize_ref_number",
    "normalize_text_key",
    "parse_doc_date",
    "version_sort_key",
]
