"""Reference resolution utilities extracted from postprocess."""

from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING, Any

from polisyos.lex.batch.doc_identity import (
    DocIndexEntry,
    build_doc_resolution_index,
    doc_family_id,
    doc_type_category,
    normalize_ref_number,
    normalize_text_key,
    parse_doc_date,
)

if TYPE_CHECKING:
    from pathlib import Path

_ARTICLE_RE = re.compile(r"статт[іяею]\s*([0-9]+(?:[-.][0-9]+)*)", re.IGNORECASE)
_PART_RE = re.compile(r"частин[аиі]\s*([0-9]+(?:[-.][0-9]+)*)", re.IGNORECASE)
_POINT_RE = re.compile(r"пункт[ауі]\s*([0-9]+(?:[-.][0-9]+)*)", re.IGNORECASE)
_NUMBER_HINT_RE = re.compile(r"[№N]\s*([\dA-ZА-ЯІЇЄҐ/-]+)", re.IGNORECASE)
_DATE_HINT_RE = re.compile(r"\b(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})\b")
_SELF_REFERENCE_RE = re.compile(
    r"цього\s+(?:закону|кодексу|порядку|положення|документа)",
    re.IGNORECASE,
)


def resolve_references(
    *,
    references_dir: Path,
    output_dir: Path,
    doc_metadata: dict[str, dict],
) -> dict[str, int]:
    """Resolve references."""
    output_dir.mkdir(parents=True, exist_ok=True)
    doc_index = build_doc_resolution_index(doc_metadata)
    stats = {"rows_total": 0, "rows_written": 0, "rows_resolved": 0, "rows_partial": 0}
    for jsonl_file in sorted(references_dir.glob("**/*.jsonl")):
        out_path = output_dir / jsonl_file.relative_to(references_dir)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with (
            open(jsonl_file, encoding="utf-8") as src,
            open(out_path, "w", encoding="utf-8") as dst,
        ):
            for line in src:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                stats["rows_total"] += 1
                target_raw = str(row.get("target_raw") or "")
                source_doc_id = str(row.get("doc_id") or "")
                source_entry = doc_index.by_doc_id.get(source_doc_id)
                matched_entry, match_score, matched_by, alternatives = _best_doc_match(
                    row=row,
                    target_raw=target_raw,
                    source_doc_id=source_doc_id,
                    doc_index=doc_index,
                )
                target_doc_id = matched_entry.doc_id if matched_entry is not None else ""
                target_anchor = _anchor_from_reference_text(target_raw)
                relation_type = str(row.get("relation_hint") or "").strip() or "references"
                resolution_confidence = min(
                    0.99, max(float(row.get("confidence") or 0.0), match_score)
                )
                resolution_status = _resolution_status(target_doc_id, target_anchor)
                if resolution_status in {"resolved", "partial"}:
                    stats["rows_resolved"] += 1
                if resolution_status == "partial":
                    stats["rows_partial"] += 1
                payload = {
                    **row,
                    "reference_edge_id": _stable_hash(
                        source_doc_id,
                        str(row.get("anchor_path") or ""),
                        target_raw,
                        target_doc_id,
                        target_anchor,
                    ),
                    "source_doc_family_id": source_entry.family_id
                    if source_entry is not None
                    else doc_family_id(doc_metadata.get(source_doc_id, {})),
                    "target_doc_id": target_doc_id,
                    "selected_target_doc_id": target_doc_id,
                    "target_anchor": target_anchor,
                    "target_doc_family_id": matched_entry.family_id
                    if matched_entry is not None
                    else "",
                    "target_doc_reestr_code": matched_entry.reestr_code
                    if matched_entry is not None
                    else "",
                    "target_doc_number": matched_entry.doc_number
                    if matched_entry is not None
                    else "",
                    "target_doc_type": matched_entry.doc_type if matched_entry is not None else "",
                    "target_doc_date_acc": matched_entry.doc_date_acc
                    if matched_entry is not None
                    else "",
                    "target_doc_status": matched_entry.status if matched_entry is not None else "",
                    "matched_by": matched_by,
                    "resolution_method": matched_by,
                    "relation_type": relation_type,
                    "resolution_confidence": resolution_confidence,
                    "resolution_status": resolution_status,
                    "candidate_count": len(alternatives),
                    "alternatives_json": json.dumps(alternatives, ensure_ascii=False),
                    "target_version_id": target_doc_id,
                }
                dst.write(json.dumps(payload, ensure_ascii=False) + "\n")
                stats["rows_written"] += 1
    return stats


def _anchor_from_reference_text(text: str) -> str:
    anchors: list[str] = []
    for label, pattern in (("article", _ARTICLE_RE), ("part", _PART_RE), ("point", _POINT_RE)):
        match = pattern.search(text)
        if match:
            anchors.append(f"{label}:{match.group(1)}")
    return "/".join(anchors)


def _stable_hash(*parts: str, size: int = 24) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:size]


def _parse_hint_date(value: str) -> str:
    parsed = parse_doc_date(value)
    return parsed.isoformat() if parsed is not None else ""


def _extract_date_hint(row: dict[str, Any], target_raw: str) -> str:
    raw_hint = str(row.get("target_date") or "").strip()
    if raw_hint:
        parsed = _parse_hint_date(raw_hint)
        if parsed:
            return parsed
    match = _DATE_HINT_RE.search(target_raw)
    if match:
        return _parse_hint_date(match.group(1))
    return ""


def _extract_number_hint(row: dict[str, Any], target_raw: str) -> str:
    raw_hint = str(row.get("target_number") or "").strip()
    if raw_hint:
        return normalize_ref_number(raw_hint)
    match = _NUMBER_HINT_RE.search(target_raw)
    if match:
        return normalize_ref_number(match.group(1))
    return ""


def _doc_type_hint(row: dict[str, Any], target_raw: str) -> str:
    raw_hint = str(row.get("target_doc_type") or "").strip()
    if raw_hint:
        return raw_hint
    return doc_type_category(target_raw)


def _doc_type_matches(hint: str, entry: DocIndexEntry) -> bool:
    if not hint or hint == "self_reference":
        return True
    if hint == entry.doc_type_category:
        return True
    if hint == "cabinet_resolution":
        publisher_norm = normalize_text_key(entry.publisher)
        return entry.doc_type_category in {"cabinet_resolution", "resolution"} and (
            "кабінет" in publisher_norm or "кму" in publisher_norm
        )
    if hint == "law":
        return entry.doc_type_category in {"law", "code"}
    return hint in normalize_text_key(entry.doc_type)


def _resolution_status(target_doc_id: str, target_anchor: str) -> str:
    if target_doc_id and target_anchor:
        return "resolved"
    if target_doc_id or target_anchor:
        return "partial"
    return "unresolved"


def _family_latest_candidates(
    candidates: list[DocIndexEntry],
    *,
    date_hint: str,
    index_by_family: dict[str, list[DocIndexEntry]],
) -> list[DocIndexEntry]:
    if not candidates:
        return []
    resolved: list[DocIndexEntry] = []
    seen_doc_ids: set[str] = set()
    for family_id in sorted({candidate.family_id for candidate in candidates}):
        family_entries = index_by_family.get(family_id, [])
        chosen: DocIndexEntry | None = None
        if date_hint:
            dated = [entry for entry in family_entries if entry.doc_date_acc == date_hint]
            if dated:
                chosen = dated[-1]
        if chosen is None:
            chosen = family_entries[-1] if family_entries else None
        if chosen is not None and chosen.doc_id not in seen_doc_ids:
            seen_doc_ids.add(chosen.doc_id)
            resolved.append(chosen)
    return resolved


def _candidate_score(
    entry: DocIndexEntry, target_raw: str, *, number_hint: str, date_hint: str
) -> float:
    raw_norm = normalize_text_key(target_raw)
    raw_tokens = set(raw_norm.split())
    entry_tokens = set(entry.name_norm.split())
    score = 0.0
    if entry.reestr_code_norm and entry.reestr_code_norm in normalize_ref_number(target_raw):
        score = max(score, 1.0)
    if number_hint and (
        entry.doc_number_norm == number_hint or entry.reg_number_norm == number_hint
    ):
        score = max(score, 0.95)
    if date_hint and entry.doc_date_acc == date_hint:
        score += 0.03
    if raw_norm:
        if raw_norm in entry.name_norm or entry.name_norm in raw_norm:
            score = max(score, 0.9 if raw_norm in entry.name_norm else 0.76)
        elif raw_tokens and entry_tokens:
            score = max(
                score, len(raw_tokens & entry_tokens) / max(len(raw_tokens), len(entry_tokens))
            )
    return min(score, 1.0)


def _best_doc_match(
    *,
    row: dict[str, Any],
    target_raw: str,
    source_doc_id: str,
    doc_index: Any,
) -> tuple[DocIndexEntry | None, float, str, list[dict[str, Any]]]:
    if not target_raw.strip():
        return None, 0.0, "", []
    if _SELF_REFERENCE_RE.search(target_raw):
        source_entry = doc_index.by_doc_id.get(source_doc_id)
        if source_entry is not None:
            return (
                source_entry,
                0.99,
                "self_reference",
                [{"doc_id": source_entry.doc_id, "score": 0.99}],
            )
    number_hint = _extract_number_hint(row, target_raw)
    date_hint = _extract_date_hint(row, target_raw)
    type_hint = _doc_type_hint(row, target_raw)
    candidate_pool: list[DocIndexEntry] = []
    matched_by = ""
    raw_norm_number = normalize_ref_number(target_raw)
    if raw_norm_number and raw_norm_number in doc_index.by_reestr_code:
        candidate_pool = [
            entry
            for entry in doc_index.by_reestr_code[raw_norm_number]
            if _doc_type_matches(type_hint, entry)
        ]
        matched_by = "reestr_code"
    if not candidate_pool and number_hint and date_hint:
        candidate_pool = [
            *doc_index.by_number_date.get((number_hint, date_hint), []),
            *doc_index.by_reg_number_date.get((number_hint, date_hint), []),
        ]
        candidate_pool = [entry for entry in candidate_pool if _doc_type_matches(type_hint, entry)]
        matched_by = "number_date" if candidate_pool else matched_by
    if not candidate_pool and number_hint:
        candidate_pool = [
            *doc_index.by_number.get(number_hint, []),
            *doc_index.by_reg_number.get(number_hint, []),
        ]
        candidate_pool = [entry for entry in candidate_pool if _doc_type_matches(type_hint, entry)]
        candidate_pool = _family_latest_candidates(
            candidates=candidate_pool, date_hint=date_hint, index_by_family=doc_index.by_family
        )
        matched_by = "number_family" if candidate_pool else matched_by
    if not candidate_pool:
        candidate_pool = [
            entry for entry in doc_index.entries if _doc_type_matches(type_hint, entry)
        ]
        matched_by = "name_overlap"

    scored = [
        (
            entry,
            _candidate_score(entry, target_raw, number_hint=number_hint, date_hint=date_hint),
        )
        for entry in candidate_pool
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    alternatives = [
        {
            "doc_id": entry.doc_id,
            "doc_name": entry.name,
            "score": round(score, 4),
        }
        for entry, score in scored[:5]
        if score > 0
    ]
    if matched_by == "name_overlap" and (not scored or scored[0][1] < 0.55):
        return None, 0.0, "", alternatives
    if matched_by == "number_family" and (not scored or scored[0][1] < 0.85):
        return None, 0.0, "", alternatives
    if not scored or scored[0][1] <= 0:
        return None, 0.0, "", alternatives
    return scored[0][0], scored[0][1], matched_by, alternatives
