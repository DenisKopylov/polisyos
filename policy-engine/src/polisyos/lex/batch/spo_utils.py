"""Parsing and normalization helpers for Lex SPO extraction."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from polisyos.common.logger import get_logger
from polisyos.lex.batch.canonicalizers import (
    canonicalize_action,
    canonicalize_norm_type,
    extract_thresholds_from_text,
)
from polisyos.lex.batch.structurer import ProvisionSpan
from polisyos.lex.batch.xml_parser import NPADocument
from polisyos.lex.knowledge.types import SPOCandidate

logger = get_logger(__name__)
_GroupedItemT = TypeVar("_GroupedItemT")


def _parse_json_object(raw_content: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw_content)
        if isinstance(data, dict):
            return data
        return None
    except json.JSONDecodeError:
        start = raw_content.find("{")
        if start != -1:
            try:
                parsed, _ = json.JSONDecoder().raw_decode(raw_content[start:])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_content, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                logger.warning("Failed to parse extracted codeblock JSON: {}", raw_content[:200])

        start = raw_content.find("{")
        end = raw_content.rfind("}")
        if start != -1 and end > start:
            candidate = raw_content[start : end + 1]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        logger.warning("Failed to parse LLM response as JSON: {}", raw_content[:200])
        return None


def _is_json_mode_invalid_request(status: int, body: str) -> bool:
    if status != 400:
        return False
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    err = payload.get("error")
    if not isinstance(err, dict):
        return False
    err_type = str(err.get("type") or "").strip().lower()
    err_code = str(err.get("code") or "").strip().lower()
    return err_type == "invalid_request_error" and err_code == "invalid_request"


def _parse_spo_statements(raw_data: dict[str, Any] | None) -> list[SPOCandidate]:
    if not raw_data:
        return []
    statements = raw_data.get("statements", [])
    if not isinstance(statements, list):
        return []

    parsed: list[SPOCandidate] = []
    for stmt in statements:
        if not isinstance(stmt, dict):
            continue
        payload = _normalize_provider_statement(stmt)
        try:
            parsed.append(SPOCandidate.model_validate(payload))
        except Exception as exc:
            payload_no_thresholds = dict(payload)
            payload_no_thresholds["thresholds"] = []
            try:
                parsed.append(SPOCandidate.model_validate(payload_no_thresholds))
            except Exception:
                logger.debug("Skipping invalid SPO statement: {} -- {}", payload, exc)
    return parsed


def _parse_light_statements(raw_data: dict[str, Any] | None) -> list[SPOCandidate]:
    if not raw_data:
        return []
    statements = raw_data.get("statements", [])
    if not isinstance(statements, list):
        return []

    parsed: list[SPOCandidate] = []
    for stmt in statements:
        if not isinstance(stmt, dict):
            continue

        subject_uk = str(stmt.get("subject_uk") or "").strip()
        predicate = str(stmt.get("predicate") or "requires").strip()
        object_uk = str(stmt.get("object_uk") or "").strip()
        norm_type = str(stmt.get("norm_type") or "obligation").strip()
        fact_text = str(stmt.get("fact_text") or "").strip()
        source_quote_uk = str(stmt.get("source_quote_uk") or "").strip()

        confidence = stmt.get("confidence")
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            confidence_value = 0.7
        confidence_value = min(1.0, max(0.0, confidence_value))

        if not subject_uk and not object_uk:
            continue

        action_canon, _action_oov = canonicalize_action(predicate)
        norm_type_canon, _norm_oov = canonicalize_norm_type(norm_type)

        threshold_text = "\n".join(part for part in (fact_text, source_quote_uk, object_uk) if part)
        thresholds = extract_thresholds_from_text(threshold_text, applies_to=object_uk)

        payload: dict[str, Any] = {
            "subject_en": subject_uk,
            "subject_uk": subject_uk or "unknown_subject",
            "predicate": predicate,
            "object_en": object_uk,
            "object_uk": object_uk or "unknown_object",
            "fact_text": fact_text or f"{subject_uk} {predicate} {object_uk}".strip(),
            "confidence": confidence_value,
            "norm_type": norm_type,
            "action_raw": predicate,
            "action_canon": action_canon,
            "norm_type_raw": norm_type,
            "norm_type_canon": norm_type_canon,
            "source_quote_uk": source_quote_uk,
            "thresholds": [th.model_dump(mode="json") for th in thresholds],
        }
        try:
            parsed.append(SPOCandidate.model_validate(payload))
        except Exception as exc:
            logger.debug("Skipping invalid light SPO statement: {} -- {}", payload, exc)
    return parsed


def _normalize_provider_statement(stmt: dict[str, Any]) -> dict[str, Any]:
    payload = dict(stmt)

    alias_map = {
        "quote_start": "source_quote_start",
        "quote_end": "source_quote_end",
        "start": "source_quote_start",
        "end": "source_quote_end",
        "source_quote": "source_quote_uk",
        "subject": "subject_uk",
        "subject_name": "subject_uk",
        "subject_role": "subject_uk",
        "object": "object_uk",
        "object_name": "object_uk",
        "object_role": "object_uk",
        "condition": "condition_text_uk",
        "exception": "exception_text_uk",
        "procedure": "procedure_text_uk",
        "temporal": "temporal_text_uk",
        "sanction": "sanction_text_uk",
    }
    for src, dst in alias_map.items():
        src_val = payload.get(src)
        dst_val = payload.get(dst)
        if src_val not in (None, "") and dst_val in (None, ""):
            payload[dst] = src_val

    if "thresholds" not in payload and isinstance(payload.get("threshold"), dict):
        payload["thresholds"] = [payload["threshold"]]
    thresholds = payload.get("thresholds")
    if not isinstance(thresholds, list):
        thresholds = []
    payload["thresholds"] = [_normalize_threshold_item(item) for item in thresholds if isinstance(item, dict)]

    if not isinstance(payload.get("links"), list):
        payload["links"] = []

    subject_uk = str(payload.get("subject_uk") or "").strip()
    object_uk = str(payload.get("object_uk") or "").strip()
    payload["subject_en"] = str(payload.get("subject_en") or payload.get("actor_en") or subject_uk or "unknown_subject")
    payload["subject_uk"] = subject_uk or payload["subject_en"]
    payload["object_en"] = str(payload.get("object_en") or payload.get("target_en") or object_uk or "unknown_object")
    payload["object_uk"] = object_uk or payload["object_en"]

    payload["predicate"] = str(payload.get("predicate") or payload.get("action_canon") or payload.get("action_raw") or "requires")
    payload["norm_type"] = str(payload.get("norm_type") or payload.get("norm_type_canon") or payload.get("norm_type_raw") or "obligation")

    fact_text = payload.get("fact_text")
    if not isinstance(fact_text, str) or not fact_text.strip():
        fact_text = payload.get("fact_text_en") or payload.get("fact_text_uk") or payload.get("source_quote_uk")
    if not isinstance(fact_text, str) or not fact_text.strip():
        fact_text = f"{payload['subject_uk']} {payload['predicate']} {payload['object_uk']}".strip()
    payload["fact_text"] = fact_text

    confidence = payload.get("confidence")
    if confidence is None:
        confidence = (
            payload.get("confidence_final")
            or payload.get("confidence_extract")
            or payload.get("confidence_verify")
            or 0.7
        )
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0.7
    payload["confidence"] = min(1.0, max(0.0, confidence_value))

    for key in ("source_quote_start", "source_quote_end"):
        value = payload.get(key)
        if value in ("", None):
            payload[key] = None
            continue
        try:
            payload[key] = int(value)
        except (TypeError, ValueError):
            payload[key] = None

    for key in (
        "statement_id",
        "actor_en",
        "actor_uk",
        "target_en",
        "target_uk",
        "beneficiary_en",
        "beneficiary_uk",
        "action_raw",
        "action_canon",
        "norm_type_raw",
        "norm_type_canon",
        "fact_text_en",
        "fact_text_uk",
        "condition_text_uk",
        "exception_text_uk",
        "procedure_text_uk",
        "temporal_text_uk",
        "sanction_text_uk",
        "source_quote_uk",
    ):
        if key in payload and payload[key] is not None and not isinstance(payload[key], str):
            payload[key] = str(payload[key])

    for key in (
        "subject",
        "subject_name",
        "subject_role",
        "object",
        "object_name",
        "object_role",
        "quote_start",
        "quote_end",
        "start",
        "end",
        "source_quote",
        "condition",
        "exception",
        "procedure",
        "temporal",
        "sanction",
        "threshold",
    ):
        payload.pop(key, None)

    return payload


def _normalize_threshold_item(raw: dict[str, Any]) -> dict[str, Any]:
    metric = raw.get("metric")
    if metric in (None, ""):
        metric = raw.get("type") or ""

    operator = raw.get("operator")
    if operator in (None, ""):
        operator = raw.get("comparator") or ""

    value_decimal = raw.get("value_decimal")
    if value_decimal in (None, ""):
        value_decimal = raw.get("value")
    if value_decimal in (None, ""):
        value_decimal = raw.get("amount")
    if value_decimal not in (None, "") and not isinstance(value_decimal, str):
        value_decimal = str(value_decimal)

    value_text = raw.get("value_text")
    if value_text in (None, "") and value_decimal not in (None, ""):
        value_text = str(value_decimal)
    if value_text not in (None, "") and not isinstance(value_text, str):
        value_text = str(value_text)

    unit = raw.get("unit")
    if unit not in (None, "") and not isinstance(unit, str):
        unit = str(unit)

    applies_to = raw.get("applies_to")
    if applies_to in (None, ""):
        applies_to = raw.get("applicable_to")
    if applies_to not in (None, "") and not isinstance(applies_to, str):
        applies_to = str(applies_to)

    return {
        "metric": str(metric or ""),
        "operator": str(operator or ""),
        "value_decimal": value_decimal if value_decimal not in (None, "") else None,
        "value_text": value_text if value_text not in (None, "") else None,
        "unit": unit if unit not in (None, "") else None,
        "applies_to": applies_to if applies_to not in (None, "") else None,
    }


def _choose_verify_statements(
    *,
    doc_id: str,
    provision_anchor: str,
    statements_pass1: list[SPOCandidate],
    data_verify: dict[str, Any] | None,
) -> tuple[list[SPOCandidate], bool]:
    if data_verify is None:
        return statements_pass1, False

    statements_pass2 = _parse_spo_statements(data_verify)
    if statements_pass2:
        return statements_pass2, False

    if statements_pass1:
        logger.warning(
            "SPO verify returned incompatible schema for {} {}; keeping pass1 statements.",
            doc_id,
            provision_anchor,
        )
        return statements_pass1, True
    return statements_pass2, False


def _usage_counts(resp: dict[str, Any]) -> tuple[int, int, float, float, float]:
    usage = resp.get("usage", {})
    if not isinstance(usage, dict):
        usage = {}
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)

    cost_base = float(
        usage.get("base_cost_usd")
        or usage.get("cost_base_usd")
        or usage.get("prompt_cost_usd")
        or 0.0
    )
    cost_platform = float(
        usage.get("platform_cost_usd")
        or usage.get("cost_platform_usd")
        or usage.get("service_cost_usd")
        or 0.0
    )
    total_candidates = [
        usage.get("total_cost_usd"),
        usage.get("cost_total_usd"),
        usage.get("total_cost"),
    ]
    total = 0.0
    for value in total_candidates:
        if value is None:
            continue
        try:
            total = float(value)
            break
        except (TypeError, ValueError):
            continue
    if total <= 0.0:
        total = max(0.0, cost_base + cost_platform)

    return prompt, completion, cost_base, cost_platform, total


def _normalize_statements(statements: list[SPOCandidate]) -> tuple[list[SPOCandidate], list[str], dict[str, int]]:
    normalized: list[SPOCandidate] = []
    reasons: list[str] = []
    stats = {
        "oov_action": 0,
        "oov_norm_type": 0,
        "missing_quote": 0,
        "added_thresholds": 0,
    }

    for stmt in statements:
        action_candidates = [
            stmt.action_canon,
            stmt.predicate,
            stmt.action_raw,
        ]
        norm_candidates = [
            stmt.norm_type_canon,
            stmt.norm_type,
            stmt.norm_type_raw,
        ]

        action_canon = "requires"
        action_oov = True
        for candidate in action_candidates:
            if not candidate:
                continue
            c_canon, c_oov = canonicalize_action(candidate)
            action_canon = c_canon
            action_oov = c_oov
            if not c_oov:
                break

        norm_canon = "obligation"
        norm_oov = True
        for candidate in norm_candidates:
            if not candidate:
                continue
            c_canon, c_oov = canonicalize_norm_type(candidate)
            norm_canon = c_canon
            norm_oov = c_oov
            if not c_oov:
                break

        thresholds = list(stmt.thresholds)
        if not thresholds:
            derived = extract_thresholds_from_text(
                "\n".join(
                    part
                    for part in (
                        stmt.condition_text_uk,
                        stmt.fact_text_uk,
                        stmt.source_quote_uk,
                        stmt.object_uk,
                    )
                    if part
                ),
                applies_to=stmt.target_en or stmt.object_en,
            )
            if derived:
                thresholds = derived
                stats["added_thresholds"] += len(derived)

        if action_oov:
            stats["oov_action"] += 1
            reasons.append("oov_action")
        if norm_oov:
            stats["oov_norm_type"] += 1
            reasons.append("oov_norm_type")

        if not stmt.source_quote_uk.strip() or stmt.source_quote_start is None or stmt.source_quote_end is None:
            stats["missing_quote"] += 1
            reasons.append("missing_quote")

        payload = stmt.model_dump(mode="json")
        payload["action_raw"] = stmt.action_raw or stmt.predicate
        payload["action_canon"] = action_canon
        payload["norm_type_raw"] = stmt.norm_type_raw or stmt.norm_type
        payload["norm_type_canon"] = norm_canon
        payload["thresholds"] = [th.model_dump(mode="json") for th in thresholds]

        normalized.append(SPOCandidate.model_validate(payload))

    dedup_reasons = sorted(set(reasons))
    return normalized, dedup_reasons, stats


@dataclass(frozen=True, slots=True)
class _BatchProvisionItem:
    item_id: str
    doc: NPADocument
    provision: ProvisionSpan


def _split_int(total: int, parts: int) -> list[int]:
    if parts <= 0:
        return []
    base = total // parts
    remainder = total % parts
    return [base + (1 if idx < remainder else 0) for idx in range(parts)]


def _split_float(total: float, parts: int) -> list[float]:
    if parts <= 0:
        return []
    if parts == 1:
        return [total]
    share = total / parts
    return [share for _ in range(parts)]


def _estimate_request_item_chars(doc: NPADocument, provision: ProvisionSpan) -> int:
    return (
        len(provision.text)
        + len(provision.citation_label or "")
        + len(doc.card.name or "")
        + len(doc.card.doc_type or "")
        + 128
    )


def _resolve_adaptive_soft_batch_chars(
    *,
    request_batch_chars: int | None,
    adaptive_batch_downshift_enabled: bool,
    adaptive_batch_soft_chars_share: float,
) -> int:
    if not adaptive_batch_downshift_enabled:
        return 0
    if request_batch_chars is None or int(request_batch_chars) <= 0:
        return 0
    share = float(adaptive_batch_soft_chars_share)
    if share >= 0.999:
        return int(request_batch_chars)
    return max(500, min(int(request_batch_chars), int(int(request_batch_chars) * share)))


def _adaptive_batch_item_cap(
    *,
    item_chars: int,
    request_batch_size: int,
    soft_batch_chars: int,
) -> int:
    base_size = max(1, int(request_batch_size))
    if base_size <= 1 or soft_batch_chars <= 0:
        return base_size
    per_item_budget = max(1.0, float(soft_batch_chars) / float(base_size))
    ratio = float(max(1, int(item_chars))) / per_item_budget
    if ratio >= 2.15:
        return 1
    if ratio >= 1.75:
        return min(base_size, 2)
    if ratio >= 1.35:
        return min(base_size, 3)
    if ratio >= 1.10:
        return min(base_size, 4)
    return base_size


def _group_items_by_request_budget(
    items: list[_GroupedItemT],
    *,
    request_batch_size: int,
    request_batch_chars: int | None,
    estimate_chars: Callable[[_GroupedItemT], int],
    adaptive_batch_downshift_enabled: bool = False,
    adaptive_batch_soft_chars_share: float = 0.80,
) -> list[list[_GroupedItemT]]:
    groups: list[list[_GroupedItemT]] = []
    current: list[_GroupedItemT] = []
    current_chars = 0
    max_items = max(1, int(request_batch_size))
    max_chars = int(request_batch_chars) if request_batch_chars is not None else 0
    soft_chars = _resolve_adaptive_soft_batch_chars(
        request_batch_chars=request_batch_chars,
        adaptive_batch_downshift_enabled=adaptive_batch_downshift_enabled,
        adaptive_batch_soft_chars_share=adaptive_batch_soft_chars_share,
    )
    current_item_cap = max_items

    for item in items:
        item_chars = max(1, int(estimate_chars(item)))
        item_cap = _adaptive_batch_item_cap(
            item_chars=item_chars,
            request_batch_size=max_items,
            soft_batch_chars=soft_chars,
        )
        effective_group_cap = min(current_item_cap, item_cap) if current else item_cap
        would_overflow_items = bool(current and len(current) >= effective_group_cap)
        would_overflow_soft_chars = bool(current and soft_chars > 0 and current_chars + item_chars > soft_chars)
        would_overflow_hard_chars = bool(current and max_chars > 0 and current_chars + item_chars > max_chars)
        if would_overflow_items or would_overflow_soft_chars or would_overflow_hard_chars:
            groups.append(current)
            current = []
            current_chars = 0
            current_item_cap = max_items

        current.append(item)
        current_chars += item_chars
        current_item_cap = min(current_item_cap, item_cap)

    if current:
        groups.append(current)
    return groups


def _group_request_items(
    items: list[tuple[NPADocument, ProvisionSpan]],
    *,
    request_batch_size: int,
    request_batch_chars: int | None,
    adaptive_batch_downshift_enabled: bool = False,
    adaptive_batch_soft_chars_share: float = 0.80,
) -> list[list[tuple[NPADocument, ProvisionSpan]]]:
    return _group_items_by_request_budget(
        items,
        request_batch_size=request_batch_size,
        request_batch_chars=request_batch_chars,
        estimate_chars=lambda item: _estimate_request_item_chars(item[0], item[1]),
        adaptive_batch_downshift_enabled=adaptive_batch_downshift_enabled,
        adaptive_batch_soft_chars_share=adaptive_batch_soft_chars_share,
    )


def _materialize_fallback_row(
    base_row: dict[str, Any],
    *,
    error_message: str,
    timeout: bool,
) -> dict[str, Any]:
    row = json.loads(json.dumps(base_row, ensure_ascii=False))
    existing_reasons = row.get("low_confidence_reasons")
    reasons = list(existing_reasons) if isinstance(existing_reasons, list) else []
    reason_code = "llm_group_timeout_fallback" if timeout else "llm_group_error_fallback"
    if reason_code not in reasons:
        reasons.append(reason_code)
    row["low_confidence"] = True
    row["low_confidence_reasons"] = reasons
    row["raw_llm_response"] = error_message[:1000]
    row["raw_extract_response"] = error_message[:1000]
    base_source = str(base_row.get("extraction_source") or "")
    if timeout:
        row["extraction_source"] = (
            base_source if base_source.endswith("timeout_fallback") else "llm_timeout_fallback"
        )
    else:
        if base_source.endswith("timeout_fallback"):
            row["extraction_source"] = f"{base_source[:-len('timeout_fallback')]}error_fallback"
        elif base_source.endswith("error_fallback"):
            row["extraction_source"] = base_source
        else:
            row["extraction_source"] = "llm_error_fallback"
    return row


def _statement_as_dict(statement: Any) -> dict[str, Any] | None:
    payload = statement
    if hasattr(statement, "model_dump"):
        payload = statement.model_dump(mode="json")
    if not isinstance(payload, dict):
        return None
    return payload


def _normalize_merge_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _statement_merge_key(statement: Any) -> tuple[Any, ...] | None:
    payload = _statement_as_dict(statement)
    if payload is None:
        return None
    thresholds = payload.get("thresholds")
    links = payload.get("links")
    thresholds_key = json.dumps(thresholds if isinstance(thresholds, list) else [], ensure_ascii=False, sort_keys=True)
    links_key = json.dumps(links if isinstance(links, list) else [], ensure_ascii=False, sort_keys=True)
    return (
        _normalize_merge_text(payload.get("action_canon") or payload.get("predicate") or payload.get("action_raw")),
        _normalize_merge_text(payload.get("fact_text_en") or payload.get("fact_text") or payload.get("fact_text_uk")),
        _normalize_merge_text(payload.get("temporal_text_uk")),
        _normalize_merge_text(payload.get("condition_text_uk")),
        thresholds_key,
        links_key,
    )


_GAP_FILL_CONFIDENCE_FLOOR = 0.86
"""Minimum confidence for gap_fill statements added alongside an existing
deterministic baseline.  When deterministic already found ≥1 statement and
LLM adds more, those additions are corroborated by the fact that the
provision is normatively active — they deserve ≥ 0.86 to qualify for the
lex_high_confidence_norms view (threshold 0.85)."""


def _merge_statement_lists(
    baseline_statements: list[Any],
    llm_statements: list[Any],
) -> tuple[list[dict[str, Any]], int]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    added = 0
    has_baseline = False

    for statement in baseline_statements:
        payload = _statement_as_dict(statement)
        if payload is None:
            continue
        key = _statement_merge_key(payload)
        if key is not None:
            seen.add(key)
        merged.append(payload)
        has_baseline = True

    for statement in llm_statements:
        payload = _statement_as_dict(statement)
        if payload is None:
            continue
        key = _statement_merge_key(payload)
        if key is not None and key in seen:
            continue
        if key is not None:
            seen.add(key)
        # Boost confidence for LLM additions when deterministic baseline
        # already confirmed the provision is normatively active.
        if has_baseline:
            raw_conf = float(payload.get("confidence") or 0.0)
            if 0 < raw_conf < _GAP_FILL_CONFIDENCE_FLOOR:
                payload["confidence"] = _GAP_FILL_CONFIDENCE_FLOOR
        merged.append(payload)
        added += 1

    return merged, added


def _coerce_batch_item_payload(item_payload: Any) -> dict[str, Any] | None:
    if isinstance(item_payload, list):
        return {"statements": item_payload}
    if not isinstance(item_payload, dict):
        return None

    statements = item_payload.get("statements")
    payload: dict[str, Any] = {
        "statements": statements if isinstance(statements, list) else [],
    }
    for key in ("low_confidence", "low_confidence_reasons", "verify_report"):
        if key in item_payload:
            payload[key] = item_payload[key]
    return payload


def _parse_batch_extract_payload(raw_data: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not raw_data:
        return {}

    parsed: dict[str, dict[str, Any]] = {}
    raw_items = raw_data.get("items")
    if raw_items is None:
        raw_items = raw_data.get("results")

    if isinstance(raw_items, list):
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            raw_id = raw_item.get("id") or raw_item.get("item_id")
            if not isinstance(raw_id, str):
                continue
            item_id = raw_id.strip()
            if not item_id:
                continue
            payload = _coerce_batch_item_payload(raw_item)
            if payload is not None:
                parsed[item_id] = payload
        return parsed

    if isinstance(raw_items, dict):
        for raw_id, item_payload in raw_items.items():
            if not isinstance(raw_id, str):
                continue
            item_id = raw_id.strip()
            if not item_id:
                continue
            payload = _coerce_batch_item_payload(item_payload)
            if payload is not None:
                parsed[item_id] = payload
        return parsed

    return parsed


__all__ = [
    "_BatchProvisionItem",
    "_choose_verify_statements",
    "_coerce_batch_item_payload",
    "_group_request_items",
    "_is_json_mode_invalid_request",
    "_materialize_fallback_row",
    "_merge_statement_lists",
    "_normalize_provider_statement",
    "_normalize_statements",
    "_normalize_threshold_item",
    "_parse_batch_extract_payload",
    "_parse_json_object",
    "_parse_light_statements",
    "_parse_spo_statements",
    "_split_float",
    "_split_int",
    "_statement_as_dict",
    "_statement_merge_key",
    "_usage_counts",
]
