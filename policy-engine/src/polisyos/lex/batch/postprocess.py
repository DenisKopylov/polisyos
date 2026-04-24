"""Post-processing stages for Lex batch outputs.

These stages are lightweight enough to run after the main SPO pass and before
graph publishing. They improve grounding, reference resolution and downstream
claim interoperability without re-running the expensive extraction step.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING, Any

import duckdb

from polisyos.common.logger import get_logger
from polisyos.lex.batch.confidence import compute_fused_confidence, quality_band_for_score
from polisyos.lex.batch.doc_identity import (
    DocIndexEntry,
    doc_type_category,
    normalize_ref_number,
    normalize_text_key,
    parse_doc_date,
)
from polisyos.lex.batch.hallucination_detector import (
    detect_hallucination_flags,
    encode_hallucination_flags,
    has_blocking_hallucination,
)
from polisyos.lex.batch.provisions_io import read_provisions
from polisyos.lex.batch.reference_resolution import resolve_references as resolve_reference_edges
from polisyos.lex.knowledge.types import SPOCandidate, SPOExtractionResult

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)

_ARTICLE_RE = re.compile(r"статт[іяею]\s*([0-9]+(?:[-.][0-9]+)*)", re.IGNORECASE)
_PART_RE = re.compile(r"частин[аиі]\s*([0-9]+(?:[-.][0-9]+)*)", re.IGNORECASE)
_POINT_RE = re.compile(r"пункт[ауі]\s*([0-9]+(?:[-.][0-9]+)*)", re.IGNORECASE)
_NUMBER_HINT_RE = re.compile(r"[№N]\s*([\dA-ZА-ЯІЇЄҐ/-]+)", re.IGNORECASE)
_DATE_HINT_RE = re.compile(r"\b(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})\b")
_SELF_REFERENCE_RE = re.compile(
    r"цього\s+(?:закону|кодексу|порядку|положення|документа)",
    re.IGNORECASE,
)
_WS_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^0-9a-zа-яіїєґ]+", re.IGNORECASE)


def _normalize_text(value: str) -> str:
    return _NON_ALNUM_RE.sub(" ", value.strip().lower()).strip()


def _compact_ws(value: str) -> str:
    return _WS_RE.sub(" ", value.strip())


def _stable_hash(*parts: str, size: int = 24) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:size]


def _candidate_quote(stmt: SPOCandidate, provision_text: str) -> str:
    candidates = [
        stmt.source_quote_uk,
        stmt.fact_text_uk,
        stmt.condition_text_uk,
        stmt.exception_text_uk,
        stmt.procedure_text_uk,
        stmt.temporal_text_uk,
        stmt.sanction_text_uk,
    ]
    compact_prov = _compact_ws(provision_text)
    for candidate in candidates:
        cleaned = _compact_ws(candidate)
        if cleaned and cleaned in compact_prov:
            return candidate.strip()
    # Tier 2: case-insensitive + unicode-normalized fallback for statement fields
    norm_prov = _normalize_quote_text(provision_text)
    for candidate in candidates:
        norm_cand = _normalize_quote_text(candidate)
        if norm_cand and len(norm_cand) >= 15 and norm_cand in norm_prov:
            return candidate.strip()
    # Tier 3: full-provision fallback only for very short provisions where the
    # entire text IS the normative content (single clause).
    stripped = provision_text.strip()
    if len(stripped) <= 500 and len(stripped.split()) >= 4:
        return stripped
    return ""


_QUOTE_NORM_RE = re.compile(r"[''`ʼ\u0027\u2018\u2019\u201A\u201B]")
_QUOTE_PUNCT_RE = re.compile(r"[«»\"\u201C\u201D\u201E\u201F]")


def _normalize_quote_text(text: str) -> str:
    """Normalize unicode quotes, apostrophes and whitespace for fuzzy matching."""
    text = _QUOTE_NORM_RE.sub("'", text)
    text = _QUOTE_PUNCT_RE.sub('"', text)
    return _compact_ws(text).lower()


def _find_quote_offsets(provision_text: str, quote_text: str) -> tuple[int | None, int | None]:
    if not quote_text.strip():
        return None, None
    # Tier 1: exact match
    exact_start = provision_text.find(quote_text)
    if exact_start >= 0:
        return exact_start, exact_start + len(quote_text)

    # Tier 2: whitespace-collapsed match
    compact_provision = _compact_ws(provision_text)
    compact_quote = _compact_ws(quote_text)
    if not compact_quote:
        return None, None
    compact_start = compact_provision.find(compact_quote)

    # Tier 3: case + unicode normalization
    if compact_start < 0:
        norm_provision = _normalize_quote_text(provision_text)
        norm_quote = _normalize_quote_text(quote_text)
        if norm_quote:
            norm_start = norm_provision.find(norm_quote)
            if norm_start >= 0:
                # Use normalized repr for offset mapping
                compact_provision = norm_provision
                compact_quote = norm_quote
                compact_start = norm_start

    # Tier 4: longest-prefix substring match (at least 60% of quote)
    if compact_start < 0:
        norm_provision = _normalize_quote_text(provision_text)
        norm_quote = _normalize_quote_text(quote_text)
        min_len = max(40, int(len(norm_quote) * 0.6))
        if len(norm_quote) >= 40:
            for try_len in range(len(norm_quote), min_len - 1, -1):
                prefix = norm_quote[:try_len]
                idx = norm_provision.find(prefix)
                if idx >= 0:
                    compact_provision = norm_provision
                    compact_quote = prefix
                    compact_start = idx
                    break

    if compact_start < 0:
        return None, None

    # Best-effort map back from whitespace-collapsed representation.
    running = 0
    start = None
    end = None
    prev_was_space = False
    for idx, char in enumerate(provision_text):
        is_space = char.isspace()
        if is_space:
            if prev_was_space:
                continue
            prev_was_space = True
            mapped_len = 1
        else:
            prev_was_space = False
            mapped_len = 1
        if start is None and running == compact_start:
            start = idx
        running += mapped_len
        if start is not None and running >= compact_start + len(compact_quote):
            end = idx + 1
            break
    return start, end


def ground_spo_quotes(
    *,
    spo_results_dir: Path,
    provisions_dir: Path,
    output_dir: Path,
) -> dict[str, int]:
    """Rewrite SPO rows with grounded quotes and structure-aware trust metadata."""
    output_dir.mkdir(parents=True, exist_ok=True)
    stats = {
        "rows_total": 0,
        "rows_written": 0,
        "statements_total": 0,
        "statements_grounded": 0,
        "statements_normative": 0,
    }

    for jsonl_file in sorted(spo_results_dir.glob("**/*.jsonl")):
        doc_id = jsonl_file.stem
        provisions = read_provisions(provisions_dir=provisions_dir, doc_id=doc_id)
        by_anchor = {
            str(row.get("anchor_path") or ""): row
            for row in provisions
            if str(row.get("anchor_path") or "")
        }
        out_path = output_dir / jsonl_file.relative_to(spo_results_dir)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with (
            open(jsonl_file, encoding="utf-8") as src,
            open(
                out_path,
                "w",
                encoding="utf-8",
            ) as dst,
        ):
            for line in src:
                line = line.strip()
                if not line:
                    continue
                stats["rows_total"] += 1
                result = SPOExtractionResult.model_validate_json(line)
                provision_row = by_anchor.get(result.provision_anchor, {})
                provision_text = str(provision_row.get("text") or "")
                struct_kind = str(provision_row.get("struct_kind") or "").strip()
                section_role = str(provision_row.get("section_role") or "").strip()
                reasoning_allowed = bool(
                    provision_row.get(
                        "fallback_allowed_for_reasoning",
                        not bool(provision_row.get("is_fallback_chunk", False)),
                    )
                )
                if (
                    bool(provision_row.get("is_fallback_chunk", False))
                    or not reasoning_allowed
                    or section_role in {"table_header", "appendix_section", "fallback_recall"}
                ):
                    structure_quality = "fallback_search_only"
                elif struct_kind:
                    structure_quality = struct_kind
                else:
                    structure_quality = "structured_legal_unit"

                grounded_statements: list[SPOCandidate] = []
                for stmt in result.statements:
                    stats["statements_total"] += 1
                    quote_text = stmt.source_quote_uk.strip() or _candidate_quote(
                        stmt, provision_text
                    )
                    quote_start = stmt.source_quote_start
                    quote_end = stmt.source_quote_end
                    if quote_text and (quote_start is None or quote_end is None):
                        quote_start, quote_end = _find_quote_offsets(provision_text, quote_text)
                    if quote_text and quote_start is not None and quote_end is not None:
                        grounding_status = "exact_quote"
                    elif quote_text:
                        grounding_status = "quote_without_offsets"
                    elif quote_start is not None and quote_end is not None:
                        grounding_status = "offsets_without_quote"
                    else:
                        grounding_status = "missing_quote"

                    hallucination_flags = detect_hallucination_flags(
                        statement=stmt,
                        provision_text=provision_text,
                    )
                    fused = compute_fused_confidence(
                        extraction_conf=stmt.confidence_extract
                        if stmt.confidence_extract is not None
                        else stmt.confidence,
                        grounding_status=grounding_status,
                        structural_quality=structure_quality,
                        verification_conf=stmt.confidence_verify,
                        extraction_source=result.extraction_source or "llm",
                    )
                    quality_band = quality_band_for_score(fused.fused_score)
                    has_blocking = bool(
                        hallucination_flags and has_blocking_hallucination(hallucination_flags)
                    )
                    # Promotion ladder: search_candidate → grounded_fact → normative_fact
                    if grounding_status in ("exact_quote", "quote_without_offsets"):
                        if has_blocking and grounding_status != "exact_quote":
                            # Blocking hallucination demotes unless saved by exact quote
                            trust_tier_override = "search_candidate"
                        else:
                            trust_tier_override = "grounded_fact"
                    else:
                        trust_tier_override = "search_candidate"

                    # Promote grounded facts with sufficient quality to normative
                    if trust_tier_override == "grounded_fact" and not has_blocking:
                        if quality_band in ("high_confidence_norm", "normative_ready"):
                            trust_tier_override = "normative_fact"

                    grounded = SPOCandidate.model_validate(
                        {
                            **stmt.model_dump(mode="python"),
                            "source_quote_uk": quote_text,
                            "source_quote_start": quote_start,
                            "source_quote_end": quote_end,
                            "grounding_status": grounding_status,
                            "structure_quality": structure_quality,
                            "trust_tier": trust_tier_override,
                            "fused_confidence": fused.fused_score,
                            "confidence_breakdown_json": fused.breakdown_json(),
                            "consistency_score": 1.0,
                            "hallucination_flags_json": encode_hallucination_flags(
                                hallucination_flags
                            ),
                            "quality_band": quality_band,
                        }
                    )
                    if grounded.trust_tier in {"grounded_fact", "normative_fact"}:
                        stats["statements_grounded"] += 1
                    if grounded.trust_tier == "normative_fact":
                        stats["statements_normative"] += 1
                    grounded_statements.append(grounded)

                grounded_result = SPOExtractionResult.model_validate(
                    {
                        **result.model_dump(mode="python"),
                        "statements": [
                            stmt.model_dump(mode="python") for stmt in grounded_statements
                        ],
                    }
                )
                dst.write(
                    json.dumps(
                        grounded_result.model_dump(mode="json"),
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                stats["rows_written"] += 1
    return stats


def _anchor_from_reference_text(text: str) -> str:
    anchors: list[str] = []
    for label, pattern in (
        ("article", _ARTICLE_RE),
        ("part", _PART_RE),
        ("point", _POINT_RE),
    ):
        match = pattern.search(text)
        if match:
            anchors.append(f"{label}:{match.group(1)}")
    return "/".join(anchors)


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


def _resolution_rank(status: str) -> int:
    return {"unresolved": 0, "partial": 1, "resolved": 2}.get(status, 0)


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
) -> tuple[DocIndexEntry | None, float, str]:
    if not target_raw.strip():
        return None, 0.0, ""

    if _SELF_REFERENCE_RE.search(target_raw):
        source_entry = doc_index.by_doc_id.get(source_doc_id)
        if source_entry is not None:
            return source_entry, 0.99, "self_reference"

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
            candidate_pool,
            date_hint=date_hint,
            index_by_family=doc_index.by_family,
        )
        matched_by = "number_family" if candidate_pool else matched_by

    if not candidate_pool:
        candidate_pool = [
            entry for entry in doc_index.entries if _doc_type_matches(type_hint, entry)
        ]
        matched_by = "name_overlap"

    best_entry: DocIndexEntry | None = None
    best_score = 0.0
    for entry in candidate_pool:
        score = _candidate_score(
            entry,
            target_raw,
            number_hint=number_hint,
            date_hint=date_hint,
        )
        if score > best_score:
            best_entry = entry
            best_score = score

    if matched_by == "name_overlap" and best_score < 0.55:
        return None, 0.0, ""
    if matched_by == "number_family" and best_score < 0.85:
        return None, 0.0, ""
    if best_entry is None:
        return None, 0.0, ""
    return best_entry, best_score, matched_by


def resolve_references(
    *,
    references_dir: Path,
    output_dir: Path,
    doc_metadata: dict[str, dict],
) -> dict[str, int]:
    """Resolve raw references into doc/anchor edges using local metadata."""
    return resolve_reference_edges(
        references_dir=references_dir,
        output_dir=output_dir,
        doc_metadata=doc_metadata,
    )


def export_normative_claims(*, db_path: Path, output_dir: Path) -> dict[str, int]:
    """Export high-trust legal facts into a simple claim-set-like JSONL artifact."""
    output_dir.mkdir(parents=True, exist_ok=True)
    claims_path = output_dir / "normative_claims.jsonl"
    summary_path = output_dir / "normative_claims_summary.json"
    stats = {"claims_total": 0, "documents_total": 0}

    if not db_path.exists():
        with open(summary_path, "w", encoding="utf-8") as fh:
            json.dump({"status": "missing_db"}, fh, ensure_ascii=False, indent=2)
        return stats

    with duckdb.connect(str(db_path), read_only=True) as con:
        rows = con.execute(
            """
            SELECT
                fact_id,
                doc_id,
                provision_anchor,
                provision_citation,
                subject_id,
                subject_en,
                predicate,
                object_id,
                object_en,
                action_canon,
                norm_type_canon,
                trust_tier,
                jurisdiction,
                top_domain,
                effective_from,
                effective_to,
                source_quote_uk,
                source_quote_start,
                source_quote_end,
                doc_name,
                doc_reestr_code
            FROM lex_normative_facts
            ORDER BY doc_id, provision_anchor, fact_id
            """
        ).fetchall()

    seen_docs: set[str] = set()
    with open(claims_path, "w", encoding="utf-8") as fh:
        for row in rows:
            seen_docs.add(str(row[1] or ""))
            claim_payload = {
                "claim_id": _stable_hash(str(row[0]), str(row[5]), str(row[8])),
                "fact_id": str(row[0] or ""),
                "predicate_id": str(row[9] or row[6] or ""),
                "subject_id": str(row[4] or ""),
                "subject_text": str(row[5] or ""),
                "object_id": str(row[7] or ""),
                "value_text": str(row[8] or ""),
                "norm_type": str(row[10] or ""),
                "trust_tier": str(row[11] or ""),
                "jurisdiction": str(row[12] or "UA"),
                "domain": str(row[13] or ""),
                "valid_from": str(row[14] or ""),
                "valid_to": str(row[15] or ""),
                "provenance": {
                    "doc_id": str(row[1] or ""),
                    "provision_anchor": str(row[2] or ""),
                    "provision_citation": str(row[3] or ""),
                    "doc_name": str(row[19] or ""),
                    "doc_reestr_code": str(row[20] or ""),
                    "source_quote_uk": str(row[16] or ""),
                    "source_quote_start": row[17],
                    "source_quote_end": row[18],
                },
            }
            fh.write(json.dumps(claim_payload, ensure_ascii=False) + "\n")
            stats["claims_total"] += 1
    stats["documents_total"] = len(seen_docs)

    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "status": "ok",
                "claims_total": stats["claims_total"],
                "documents_total": stats["documents_total"],
                "artifact": str(claims_path),
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )
    return stats
