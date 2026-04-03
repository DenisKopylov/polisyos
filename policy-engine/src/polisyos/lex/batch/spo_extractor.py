"""Stage 3: Async LLM-based 2-pass extraction via Gonka (OpenAI-compatible API).

Pass 1: Extract statements.
Pass 2: Verify + normalize extracted statements against the same provision.

Policy: mark-and-continue for low confidence (no extra LLM passes).
"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from polisyos.common.logger import get_logger
from polisyos.lex.batch.canonicalizers import canonicalize_action, canonicalize_norm_type
from polisyos.lex.batch.provisions_io import _shard_prefix
from polisyos.lex.batch.spo_client import (
    GonkaClient,
    GonkaClientPool,
    GonkaRequestError,
    _SlidingWindowLimiter,
)
from polisyos.lex.batch.spo_prompts import (
    SPO_EXTRACT_BATCH_SYSTEM_PROMPT,
    SPO_EXTRACT_SYSTEM_PROMPT,
    SPO_LIGHT_BATCH_SYSTEM_PROMPT,
    SPO_LIGHT_PROMPT_VERSION,
    SPO_LIGHT_SYSTEM_PROMPT,
    SPO_PROMPT_VERSION,
    SPO_VERIFY_SYSTEM_PROMPT,
    build_spo_extract_batch_user_prompt,
    build_spo_extract_user_prompt,
    build_spo_light_batch_user_prompt,
    build_spo_light_user_prompt,
    build_spo_verify_user_prompt,
)
from polisyos.lex.batch.spo_utils import (
    _BatchProvisionItem,
    _choose_verify_statements,
    _group_request_items,
    _is_json_mode_invalid_request,
    _materialize_fallback_row,
    _merge_statement_lists,
    _normalize_statements,
    _parse_batch_extract_payload,
    _parse_json_object,
    _parse_light_statements,
    _parse_spo_statements,
    _split_float,
    _split_int,
    _usage_counts,
)
from polisyos.lex.batch.structurer import ProvisionSpan
from polisyos.lex.batch.xml_parser import NPADocument
from polisyos.lex.knowledge.types import SPOCandidate, SPOExtractionResult

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class _DispatchLaneSettings:
    name: str = "primary"
    worker_scale: float = 1.0
    dispatch_rps_scale: float = 1.0
    client_rate_scale: float = 1.0
    client_concurrency_scale: float = 1.0


def _request_meta(
    *,
    request_kind: str,
    prompt_chars: int,
    group_size: int,
    verify_mode: str | None = None,
    extract_mode: str | None = None,
    doc_id: str | None = None,
    provision_anchor: str | None = None,
    followup_pass_index: int = 0,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "request_kind": request_kind,
        "prompt_chars": max(0, int(prompt_chars)),
        "group_size": max(1, int(group_size)),
        "followup_pass_index": max(0, int(followup_pass_index)),
    }
    if verify_mode is not None:
        meta["verify_mode"] = verify_mode
    if extract_mode is not None:
        meta["extract_mode"] = extract_mode
    if doc_id:
        meta["doc_id"] = doc_id
    if provision_anchor:
        meta["provision_anchor"] = provision_anchor
    return meta


async def _chat_completion_compat(
    client: GonkaClient,
    messages: list[dict[str, str]],
    *,
    response_format: dict[str, str] | None = None,
    request_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chat_completion = client.chat_completion
    try:
        signature = inspect.signature(chat_completion)
    except (TypeError, ValueError):
        signature = None
    if signature is not None:
        accepts_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in signature.parameters.values()
        )
        if not accepts_kwargs and "request_meta" not in signature.parameters:
            return await chat_completion(messages, response_format=response_format)
    return await chat_completion(
        messages,
        response_format=response_format,
        request_meta=request_meta,
    )


def _build_extract_failed_result(
    *,
    client: GonkaClient,
    doc: NPADocument,
    provision: ProvisionSpan,
    error_message: str,
    pass1_latency_ms: int,
    error_class: str = "",
    retryable: bool = False,
    http_status: int = 0,
    provider_key_index: int | None = None,
    retry_count: int = 0,
) -> SPOExtractionResult:
    return SPOExtractionResult(
        doc_id=doc.card.doc_id,
        provision_anchor=provision.anchor_path,
        provision_citation=provision.citation_label,
        statements=[],
        raw_llm_response=error_message,
        raw_extract_response=error_message,
        model_id=client.model_id,
        prompt_version=SPO_PROMPT_VERSION,
        low_confidence=True,
        low_confidence_reasons=["extract_failed"],
        llm_error_class=error_class,
        llm_error_retryable=retryable,
        llm_error_http_status=http_status,
        llm_error_provider_key_index=provider_key_index,
        llm_error_retry_count=retry_count,
        latency_ms=pass1_latency_ms,
        pass1_latency_ms=pass1_latency_ms,
    )


async def _finalize_provision_from_pass1(
    client: GonkaClient,
    doc: NPADocument,
    provision: ProvisionSpan,
    *,
    statements_pass1: list[SPOCandidate],
    raw_extract: str,
    pass1_latency_ms: int,
    usage1_prompt: int,
    usage1_completion: int,
    cost1_base: float,
    cost1_platform: float,
    cost1_total: float,
    verify_mode: str = "llm",
    followup_pass_index: int = 0,
) -> SPOExtractionResult:
    raw_verify = ""
    data_verify: dict[str, Any] | None = None
    usage2_prompt = usage2_completion = 0
    cost2_base = cost2_platform = cost2_total = 0.0
    verify_failed = False
    pass2_latency_ms = 0
    verify_schema_fallback = False
    statements_pass2 = statements_pass1
    verify_report = {
        "input_count": len(statements_pass1),
        "output_count": len(statements_pass1),
        "dropped_count": 0,
    }

    if verify_mode == "llm":
        verify_input_json = json.dumps(
            {"statements": [s.model_dump(mode="json") for s in statements_pass1]},
            ensure_ascii=False,
        )
        verify_prompt = build_spo_verify_user_prompt(
            provision_text=provision.text,
            extracted_json=verify_input_json,
            provision_citation=provision.citation_label,
        )
        verify_messages = [
            {"role": "system", "content": SPO_VERIFY_SYSTEM_PROMPT},
            {"role": "user", "content": verify_prompt},
        ]

        t2 = time.monotonic()
        try:
            resp_verify = await _chat_completion_compat(
                client,
                verify_messages,
                response_format={"type": "json_object"},
                request_meta=_request_meta(
                    request_kind="spo_verify_single",
                    prompt_chars=len(verify_prompt),
                    group_size=1,
                    verify_mode=verify_mode,
                    doc_id=doc.card.doc_id,
                    provision_anchor=provision.anchor_path,
                    followup_pass_index=followup_pass_index,
                ),
            )
            pass2_latency_ms = int((time.monotonic() - t2) * 1000)
            usage2_prompt, usage2_completion, cost2_base, cost2_platform, cost2_total = _usage_counts(resp_verify)
            verify_choice = resp_verify.get("choices", [{}])[0]
            raw_verify = verify_choice.get("message", {}).get("content", "")
            data_verify = _parse_json_object(raw_verify)
        except Exception as exc:
            pass2_latency_ms = int((time.monotonic() - t2) * 1000)
            verify_failed = True
            raw_verify = str(exc)
            logger.warning("SPO verify failed for {} {}: {}", doc.card.doc_id, provision.anchor_path, exc)

        statements_pass2, verify_schema_fallback = _choose_verify_statements(
            doc_id=doc.card.doc_id,
            provision_anchor=provision.anchor_path,
            statements_pass1=statements_pass1,
            data_verify=data_verify,
        )

        verify_report = {}
        if isinstance(data_verify, dict):
            raw_report = data_verify.get("verify_report")
            if isinstance(raw_report, dict):
                verify_report = raw_report
        if not verify_report:
            verify_report = {
                "input_count": len(statements_pass1),
                "output_count": len(statements_pass2),
                "dropped_count": max(0, len(statements_pass1) - len(statements_pass2)),
            }
    else:
        verify_report["mode"] = "code"

    normalized, norm_reasons, norm_stats = _normalize_statements(statements_pass2)

    low_confidence_reasons: list[str] = []
    low_confidence = False
    if verify_failed:
        low_confidence = True
        low_confidence_reasons.append("verify_failed")
    if verify_schema_fallback:
        low_confidence = True
        low_confidence_reasons.append("verify_schema_fallback")
    if not normalized:
        low_confidence = True
        low_confidence_reasons.append("no_statements")
    if norm_stats["missing_quote"] > 0:
        low_confidence = True
        low_confidence_reasons.append("missing_quote")

    if isinstance(data_verify, dict):
        verify_low_conf = bool(data_verify.get("low_confidence", False))
        if verify_low_conf:
            low_confidence = True
        verify_reasons = data_verify.get("low_confidence_reasons", [])
        if isinstance(verify_reasons, list):
            for reason in verify_reasons:
                if isinstance(reason, str) and reason.strip():
                    low_confidence_reasons.append(reason.strip())

    low_confidence_reasons.extend(norm_reasons)
    low_confidence_reasons = sorted(set(low_confidence_reasons))

    total_prompt_tokens = usage1_prompt + usage2_prompt
    total_completion_tokens = usage1_completion + usage2_completion
    total_cost_base = cost1_base + cost2_base
    total_cost_platform = cost1_platform + cost2_platform
    total_cost = cost1_total + cost2_total
    if total_cost <= 0.0:
        total_cost = max(0.0, total_cost_base + total_cost_platform)

    normalization_report = {
        "oov_action": norm_stats["oov_action"],
        "oov_norm_type": norm_stats["oov_norm_type"],
        "missing_quote": norm_stats["missing_quote"],
        "added_thresholds": norm_stats["added_thresholds"],
    }

    return SPOExtractionResult(
        doc_id=doc.card.doc_id,
        provision_anchor=provision.anchor_path,
        provision_citation=provision.citation_label,
        statements=normalized,
        raw_llm_response=raw_verify or raw_extract,
        raw_extract_response=raw_extract,
        raw_verify_response=raw_verify,
        model_id=client.model_id,
        prompt_version=SPO_PROMPT_VERSION,
        extract_passes=2 if verify_mode == "llm" else 1,
        verify_report_json=json.dumps(verify_report, ensure_ascii=False),
        normalization_report_json=json.dumps(normalization_report, ensure_ascii=False),
        low_confidence=low_confidence,
        low_confidence_reasons=low_confidence_reasons,
        latency_ms=pass1_latency_ms + pass2_latency_ms,
        pass1_latency_ms=pass1_latency_ms,
        pass2_latency_ms=pass2_latency_ms,
        token_count_prompt=total_prompt_tokens,
        token_count_completion=total_completion_tokens,
        token_count_prompt_extract=usage1_prompt,
        token_count_completion_extract=usage1_completion,
        token_count_prompt_verify=usage2_prompt,
        token_count_completion_verify=usage2_completion,
        cost_base_usd=total_cost_base,
        cost_platform_usd=total_cost_platform,
        cost_total_usd=total_cost,
    )


async def _extract_one_provision(
    client: GonkaClient,
    doc: NPADocument,
    provision: ProvisionSpan,
    *,
    verify_mode: str = "llm",
    followup_pass_index: int = 0,
) -> SPOExtractionResult:
    """Run extraction for one provision (llm or code verify mode)."""

    # -------------------- Pass 1: Extract --------------------
    extract_prompt = build_spo_extract_user_prompt(
        provision_text=provision.text,
        doc_title=doc.card.name,
        doc_type=doc.card.doc_type,
        publisher=", ".join(doc.card.publisher) if doc.card.publisher else "",
        date_acc=doc.card.date_acc,
        provision_citation=provision.citation_label,
    )
    extract_messages = [
        {"role": "system", "content": SPO_EXTRACT_SYSTEM_PROMPT},
        {"role": "user", "content": extract_prompt},
    ]

    t1 = time.monotonic()
    try:
        resp_extract = await _chat_completion_compat(
            client,
            extract_messages,
            response_format={"type": "json_object"},
            request_meta=_request_meta(
                request_kind="spo_extract_single",
                prompt_chars=len(extract_prompt),
                group_size=1,
                verify_mode=verify_mode,
                extract_mode="full",
                doc_id=doc.card.doc_id,
                provision_anchor=provision.anchor_path,
                followup_pass_index=followup_pass_index,
            ),
        )
    except Exception as exc:
        logger.warning("SPO extract failed for {} {}: {}", doc.card.doc_id, provision.anchor_path, exc)
        error_class = ""
        retryable = False
        http_status = 0
        provider_key_index = None
        retry_count = 0
        if isinstance(exc, GonkaRequestError):
            error_class = exc.error_class
            retryable = exc.retryable
            http_status = exc.http_status
            provider_key_index = exc.provider_key_index
            retry_count = exc.retry_count
        return _build_extract_failed_result(
            client=client,
            doc=doc,
            provision=provision,
            error_message=str(exc),
            pass1_latency_ms=int((time.monotonic() - t1) * 1000),
            error_class=error_class,
            retryable=retryable,
            http_status=http_status,
            provider_key_index=provider_key_index,
            retry_count=retry_count,
        )

    pass1_latency_ms = int((time.monotonic() - t1) * 1000)
    usage1_prompt, usage1_completion, cost1_base, cost1_platform, cost1_total = _usage_counts(resp_extract)
    extract_choice = resp_extract.get("choices", [{}])[0]
    raw_extract = extract_choice.get("message", {}).get("content", "")
    data_extract = _parse_json_object(raw_extract)
    statements_pass1 = _parse_spo_statements(data_extract)

    return await _finalize_provision_from_pass1(
        client,
        doc,
        provision,
        statements_pass1=statements_pass1,
        raw_extract=raw_extract,
        pass1_latency_ms=pass1_latency_ms,
        usage1_prompt=usage1_prompt,
        usage1_completion=usage1_completion,
        cost1_base=cost1_base,
        cost1_platform=cost1_platform,
        cost1_total=cost1_total,
        verify_mode=verify_mode,
        followup_pass_index=followup_pass_index,
    )


async def _extract_one_provision_light(
    client: GonkaClient,
    doc: NPADocument,
    provision: ProvisionSpan,
    *,
    followup_pass_index: int = 0,
) -> SPOExtractionResult:
    """Single-provision light extraction: 1-pass, 7-field schema, code canonicalization."""
    # --- Cache lookup ---
    cache = getattr(client, "_cache", None)
    if cache is not None:
        cached = cache.get(provision.text, doc.card.doc_type, client.model_id)
        if cached is not None:
            statements = _parse_light_statements(cached)
            return SPOExtractionResult(
                doc_id=doc.card.doc_id,
                provision_anchor=provision.anchor_path,
                provision_citation=provision.citation_label,
                statements=statements,
                raw_llm_response=json.dumps(cached, ensure_ascii=False),
                raw_extract_response=json.dumps(cached, ensure_ascii=False),
                model_id=client.model_id,
                prompt_version=SPO_LIGHT_PROMPT_VERSION,
                extract_passes=1,
                extraction_source="cache",
                low_confidence=not statements,
                low_confidence_reasons=["no_statements"] if not statements else [],
                latency_ms=0,
                pass1_latency_ms=0,
            )

    user_prompt = build_spo_light_user_prompt(
        provision_text=provision.text,
        doc_title=doc.card.name,
        doc_type=doc.card.doc_type,
        publisher=", ".join(doc.card.publisher) if doc.card.publisher else "",
        date_acc=doc.card.date_acc,
        provision_citation=provision.citation_label,
    )
    messages = [
        {"role": "system", "content": SPO_LIGHT_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    t1 = time.monotonic()
    try:
        resp = await _chat_completion_compat(
            client,
            messages,
            response_format={"type": "json_object"},
            request_meta=_request_meta(
                request_kind="spo_extract_light_single",
                prompt_chars=len(user_prompt),
                group_size=1,
                extract_mode="light",
                doc_id=doc.card.doc_id,
                provision_anchor=provision.anchor_path,
                followup_pass_index=followup_pass_index,
            ),
        )
    except Exception as exc:
        logger.warning("SPO light extract failed for {} {}: {}", doc.card.doc_id, provision.anchor_path, exc)
        error_class = ""
        retryable = False
        http_status = 0
        provider_key_index = None
        retry_count = 0
        if isinstance(exc, GonkaRequestError):
            error_class = exc.error_class
            retryable = exc.retryable
            http_status = exc.http_status
            provider_key_index = exc.provider_key_index
            retry_count = exc.retry_count
        return _build_extract_failed_result(
            client=client,
            doc=doc,
            provision=provision,
            error_message=str(exc),
            pass1_latency_ms=int((time.monotonic() - t1) * 1000),
            error_class=error_class,
            retryable=retryable,
            http_status=http_status,
            provider_key_index=provider_key_index,
            retry_count=retry_count,
        )

    latency_ms = int((time.monotonic() - t1) * 1000)
    usage_prompt, usage_completion, cost_base, cost_platform, cost_total = _usage_counts(resp)
    choice = resp.get("choices", [{}])[0]
    raw_content = choice.get("message", {}).get("content", "")
    data = _parse_json_object(raw_content)

    # --- Cache store ---
    if cache is not None and data is not None:
        cache.put(provision.text, doc.card.doc_type, client.model_id, data)

    statements = _parse_light_statements(data)

    # Code-based normalization (thresholds already extracted in _parse_light_statements).
    norm_reasons: list[str] = []
    norm_stats = {"oov_action": 0, "oov_norm_type": 0, "missing_quote": 0}
    for stmt in statements:
        _, action_oov = canonicalize_action(stmt.predicate)
        _, norm_oov = canonicalize_norm_type(stmt.norm_type)
        if action_oov:
            norm_stats["oov_action"] += 1
            norm_reasons.append("oov_action")
        if norm_oov:
            norm_stats["oov_norm_type"] += 1
            norm_reasons.append("oov_norm_type")
        if not stmt.source_quote_uk.strip():
            norm_stats["missing_quote"] += 1
            norm_reasons.append("missing_quote")

    low_confidence = not statements
    low_confidence_reasons = sorted(set(norm_reasons))
    if not statements:
        low_confidence_reasons.append("no_statements")

    return SPOExtractionResult(
        doc_id=doc.card.doc_id,
        provision_anchor=provision.anchor_path,
        provision_citation=provision.citation_label,
        statements=statements,
        raw_llm_response=raw_content,
        raw_extract_response=raw_content,
        model_id=client.model_id,
        prompt_version=SPO_LIGHT_PROMPT_VERSION,
        extract_passes=1,
        normalization_report_json=json.dumps(norm_stats, ensure_ascii=False),
        low_confidence=low_confidence,
        low_confidence_reasons=low_confidence_reasons,
        latency_ms=latency_ms,
        pass1_latency_ms=latency_ms,
        token_count_prompt=usage_prompt,
        token_count_completion=usage_completion,
        token_count_prompt_extract=usage_prompt,
        token_count_completion_extract=usage_completion,
        cost_base_usd=cost_base,
        cost_platform_usd=cost_platform,
        cost_total_usd=cost_total,
    )


async def _run_single_extractions(
    client: GonkaClient,
    entries: list[_BatchProvisionItem],
    *,
    verify_mode: str = "llm",
    extract_mode: str = "full",
    followup_pass_index: int = 0,
) -> list[SPOExtractionResult]:
    if extract_mode == "light":
        tasks = [
            asyncio.create_task(
                _extract_one_provision_light(
                    client,
                    entry.doc,
                    entry.provision,
                    followup_pass_index=followup_pass_index,
                ),
            )
            for entry in entries
        ]
    else:
        tasks = [
            asyncio.create_task(
                _extract_one_provision(
                    client,
                    entry.doc,
                    entry.provision,
                    verify_mode=verify_mode,
                    followup_pass_index=followup_pass_index,
                ),
            )
            for entry in entries
        ]
    settled = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[SPOExtractionResult] = []
    for entry, result in zip(entries, settled, strict=True):
        if isinstance(result, Exception):
            logger.warning(
                "Single-request fallback crashed for {} {}: {}",
                entry.doc.card.doc_id,
                entry.provision.anchor_path,
                result,
            )
            results.append(
                _build_extract_failed_result(
                    client=client,
                    doc=entry.doc,
                    provision=entry.provision,
                    error_message=str(result),
                    pass1_latency_ms=0,
                ),
            )
            continue
        results.append(result)
    return results


async def _extract_batch_provisions(
    client: GonkaClient,
    batch_items: list[tuple[NPADocument, ProvisionSpan]],
    *,
    verify_mode: str = "llm",
    followup_pass_index: int = 0,
) -> list[SPOExtractionResult]:
    entries = [
        _BatchProvisionItem(
            item_id=f"item_{idx:04d}",
            doc=doc,
            provision=provision,
        )
        for idx, (doc, provision) in enumerate(batch_items)
    ]
    if not entries:
        return []
    if len(entries) == 1:
        return await _run_single_extractions(
            client,
            entries,
            verify_mode=verify_mode,
            followup_pass_index=followup_pass_index,
        )

    prompt_items = [
        {
            "id": entry.item_id,
            "doc_title": entry.doc.card.name,
            "doc_type": entry.doc.card.doc_type,
            "publisher": ", ".join(entry.doc.card.publisher) if entry.doc.card.publisher else "",
            "date_acc": entry.doc.card.date_acc,
            "provision_citation": entry.provision.citation_label,
            "provision_text": entry.provision.text,
        }
        for entry in entries
    ]
    extract_messages = [
        {"role": "system", "content": SPO_EXTRACT_BATCH_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_spo_extract_batch_user_prompt(items=prompt_items),
        },
    ]

    t1 = time.monotonic()
    try:
        resp_extract = await _chat_completion_compat(
            client,
            extract_messages,
            response_format={"type": "json_object"},
            request_meta=_request_meta(
                request_kind="spo_extract_batch",
                prompt_chars=len(extract_messages[1]["content"]),
                group_size=len(entries),
                verify_mode=verify_mode,
                extract_mode="full",
                followup_pass_index=followup_pass_index,
            ),
        )
    except Exception as exc:
        logger.warning(
            "SPO batched extract failed for {} provisions; fallback to single requests: {}",
            len(entries),
            exc,
        )
        return await _run_single_extractions(
            client,
            entries,
            verify_mode=verify_mode,
            followup_pass_index=followup_pass_index,
        )

    pass1_latency_ms = int((time.monotonic() - t1) * 1000)
    usage1_prompt, usage1_completion, cost1_base, cost1_platform, cost1_total = _usage_counts(resp_extract)
    extract_choice = resp_extract.get("choices", [{}])[0]
    raw_extract = extract_choice.get("message", {}).get("content", "")
    data_extract = _parse_json_object(raw_extract)
    payload_by_id = _parse_batch_extract_payload(data_extract)
    if not payload_by_id:
        logger.warning(
            "SPO batched extract returned incompatible schema for {} provisions; fallback to singles.",
            len(entries),
        )
        return await _run_single_extractions(
            client,
            entries,
            verify_mode=verify_mode,
            followup_pass_index=followup_pass_index,
        )

    prompt_parts = _split_int(usage1_prompt, len(entries))
    completion_parts = _split_int(usage1_completion, len(entries))
    cost_base_parts = _split_float(cost1_base, len(entries))
    cost_platform_parts = _split_float(cost1_platform, len(entries))
    cost_total_parts = _split_float(cost1_total, len(entries))

    entry_by_id = {entry.item_id: entry for entry in entries}
    scheduled_ids: list[str] = []
    scheduled_tasks: list[asyncio.Task[SPOExtractionResult]] = []

    for idx, entry in enumerate(entries):
        item_payload = payload_by_id.get(entry.item_id)
        if item_payload is None:
            continue
        statements_pass1 = _parse_spo_statements(item_payload)
        raw_item_extract = json.dumps(
            {
                "id": entry.item_id,
                "statements": item_payload.get("statements", []),
            },
            ensure_ascii=False,
        )
        scheduled_ids.append(entry.item_id)
        scheduled_tasks.append(
            asyncio.create_task(
                _finalize_provision_from_pass1(
                    client,
                    entry.doc,
                    entry.provision,
                    statements_pass1=statements_pass1,
                    raw_extract=raw_item_extract,
                    pass1_latency_ms=pass1_latency_ms,
                    usage1_prompt=prompt_parts[idx],
                    usage1_completion=completion_parts[idx],
                    cost1_base=cost_base_parts[idx],
                    cost1_platform=cost_platform_parts[idx],
                    cost1_total=cost_total_parts[idx],
                    verify_mode=verify_mode,
                    followup_pass_index=followup_pass_index,
                ),
            ),
        )

    settled = await asyncio.gather(*scheduled_tasks, return_exceptions=True)
    results_by_id: dict[str, SPOExtractionResult] = {}
    for item_id, result in zip(scheduled_ids, settled, strict=True):
        if isinstance(result, Exception):
            entry = entry_by_id[item_id]
            logger.warning(
                "Batched finalize failed for {} {}; fallback to single request: {}",
                entry.doc.card.doc_id,
                entry.provision.anchor_path,
                result,
            )
            fallback = await _run_single_extractions(
                client,
                [entry],
                verify_mode=verify_mode,
                followup_pass_index=followup_pass_index,
            )
            results_by_id[item_id] = fallback[0]
            continue
        results_by_id[item_id] = result

    for entry in entries:
        if entry.item_id in results_by_id:
            continue
        logger.warning(
            "Batched extract missing item id={} for {} {}; fallback to single request.",
            entry.item_id,
            entry.doc.card.doc_id,
            entry.provision.anchor_path,
        )
        fallback = await _run_single_extractions(
            client,
            [entry],
            verify_mode=verify_mode,
            followup_pass_index=followup_pass_index,
        )
        results_by_id[entry.item_id] = fallback[0]

    return [results_by_id[entry.item_id] for entry in entries]


async def _extract_batch_provisions_light(
    client: GonkaClient,
    batch_items: list[tuple[NPADocument, ProvisionSpan]],
    *,
    followup_pass_index: int = 0,
) -> list[SPOExtractionResult]:
    """Batch light extraction: 1-pass, 7-field schema, code canonicalization.

    Integrates with SPOCache: cached provisions are resolved immediately,
    only uncached provisions are sent to LLM in a single batch request.
    """
    entries = [
        _BatchProvisionItem(
            item_id=f"item_{idx:04d}",
            doc=doc,
            provision=provision,
        )
        for idx, (doc, provision) in enumerate(batch_items)
    ]
    if not entries:
        return []
    if len(entries) == 1:
        return await _run_single_extractions(
            client,
            entries,
            extract_mode="light",
            followup_pass_index=followup_pass_index,
        )

    # --- Cache lookup: resolve cached entries without LLM ---
    cache = getattr(client, "_cache", None)
    results_by_id: dict[str, SPOExtractionResult] = {}
    uncached_entries: list[_BatchProvisionItem] = []

    for entry in entries:
        if cache is not None:
            cached = cache.get(entry.provision.text, entry.doc.card.doc_type, client.model_id)
            if cached is not None:
                statements = _parse_light_statements(cached)
                results_by_id[entry.item_id] = SPOExtractionResult(
                    doc_id=entry.doc.card.doc_id,
                    provision_anchor=entry.provision.anchor_path,
                    provision_citation=entry.provision.citation_label,
                    statements=statements,
                    raw_llm_response=json.dumps(cached, ensure_ascii=False),
                    raw_extract_response=json.dumps(cached, ensure_ascii=False),
                    model_id=client.model_id,
                    prompt_version=SPO_LIGHT_PROMPT_VERSION,
                    extract_passes=1,
                    extraction_source="cache",
                    low_confidence=not statements,
                    low_confidence_reasons=["no_statements"] if not statements else [],
                    latency_ms=0,
                    pass1_latency_ms=0,
                )
                continue
        uncached_entries.append(entry)

    # All entries resolved from cache.
    if not uncached_entries:
        return [results_by_id[e.item_id] for e in entries]

    # Only 1 uncached — use single extraction (has its own cache store).
    if len(uncached_entries) == 1:
        single_results = await _run_single_extractions(
            client,
            uncached_entries,
            extract_mode="light",
            followup_pass_index=followup_pass_index,
        )
        for entry, result in zip(uncached_entries, single_results, strict=True):
            results_by_id[entry.item_id] = result
        return [results_by_id[e.item_id] for e in entries]

    # --- LLM batch request for uncached entries ---
    prompt_items = [
        {
            "id": entry.item_id,
            "doc_title": entry.doc.card.name,
            "doc_type": entry.doc.card.doc_type,
            "publisher": ", ".join(entry.doc.card.publisher) if entry.doc.card.publisher else "",
            "date_acc": entry.doc.card.date_acc,
            "provision_citation": entry.provision.citation_label,
            "provision_text": entry.provision.text,
        }
        for entry in uncached_entries
    ]
    messages = [
        {"role": "system", "content": SPO_LIGHT_BATCH_SYSTEM_PROMPT},
        {"role": "user", "content": build_spo_light_batch_user_prompt(items=prompt_items)},
    ]

    t1 = time.monotonic()
    try:
        resp = await _chat_completion_compat(
            client,
            messages,
            response_format={"type": "json_object"},
            request_meta=_request_meta(
                request_kind="spo_extract_light_batch",
                prompt_chars=len(messages[1]["content"]),
                group_size=len(uncached_entries),
                extract_mode="light",
                followup_pass_index=followup_pass_index,
            ),
        )
    except Exception as exc:
        logger.warning(
            "SPO batched light extract failed for {} provisions; fallback to singles: {}",
            len(uncached_entries),
            exc,
        )
        fallback = await _run_single_extractions(
            client,
            uncached_entries,
            extract_mode="light",
            followup_pass_index=followup_pass_index,
        )
        for entry, result in zip(uncached_entries, fallback, strict=True):
            results_by_id[entry.item_id] = result
        return [results_by_id[e.item_id] for e in entries]

    latency_ms = int((time.monotonic() - t1) * 1000)
    usage_prompt, usage_completion, cost_base, cost_platform, cost_total = _usage_counts(resp)
    choice = resp.get("choices", [{}])[0]
    raw_content = choice.get("message", {}).get("content", "")
    data = _parse_json_object(raw_content)
    payload_by_id = _parse_batch_extract_payload(data)

    if not payload_by_id:
        logger.warning(
            "SPO batched light extract returned incompatible schema for {} provisions; fallback to singles.",
            len(uncached_entries),
        )
        fallback = await _run_single_extractions(
            client,
            uncached_entries,
            extract_mode="light",
            followup_pass_index=followup_pass_index,
        )
        for entry, result in zip(uncached_entries, fallback, strict=True):
            results_by_id[entry.item_id] = result
        return [results_by_id[e.item_id] for e in entries]

    prompt_parts = _split_int(usage_prompt, len(uncached_entries))
    completion_parts = _split_int(usage_completion, len(uncached_entries))
    cost_base_parts = _split_float(cost_base, len(uncached_entries))
    cost_platform_parts = _split_float(cost_platform, len(uncached_entries))
    cost_total_parts = _split_float(cost_total, len(uncached_entries))

    for idx, entry in enumerate(uncached_entries):
        item_payload = payload_by_id.get(entry.item_id)
        if item_payload is None:
            logger.warning(
                "Batched light extract missing id={} for {} {}; fallback to single.",
                entry.item_id,
                entry.doc.card.doc_id,
                entry.provision.anchor_path,
            )
            fallback = await _run_single_extractions(
                client,
                [entry],
                extract_mode="light",
                followup_pass_index=followup_pass_index,
            )
            results_by_id[entry.item_id] = fallback[0]
            continue

        # --- Cache store for this item ---
        if cache is not None and item_payload:
            cache.put(entry.provision.text, entry.doc.card.doc_type, client.model_id, item_payload)

        statements = _parse_light_statements(item_payload)
        raw_item = json.dumps(
            {"id": entry.item_id, "statements": item_payload.get("statements", [])},
            ensure_ascii=False,
        )

        low_confidence = not statements
        low_confidence_reasons: list[str] = []
        if not statements:
            low_confidence_reasons.append("no_statements")

        results_by_id[entry.item_id] = SPOExtractionResult(
            doc_id=entry.doc.card.doc_id,
            provision_anchor=entry.provision.anchor_path,
            provision_citation=entry.provision.citation_label,
            statements=statements,
            raw_llm_response=raw_item,
            raw_extract_response=raw_item,
            model_id=client.model_id,
            prompt_version=SPO_LIGHT_PROMPT_VERSION,
            extract_passes=1,
            low_confidence=low_confidence,
            low_confidence_reasons=low_confidence_reasons,
            latency_ms=latency_ms,
            pass1_latency_ms=latency_ms,
            token_count_prompt=prompt_parts[idx],
            token_count_completion=completion_parts[idx],
            token_count_prompt_extract=prompt_parts[idx],
            token_count_completion_extract=completion_parts[idx],
            cost_base_usd=cost_base_parts[idx],
            cost_platform_usd=cost_platform_parts[idx],
            cost_total_usd=cost_total_parts[idx],
        )

    return [results_by_id[e.item_id] for e in entries]


async def _extract_provision_group(
    client: GonkaClient,
    group: list[tuple[NPADocument, ProvisionSpan]],
    *,
    verify_mode: str,
    extract_mode: str = "full",
    followup_pass_index: int = 0,
) -> list[SPOExtractionResult]:
    if not group:
        return []

    if extract_mode == "light":
        if len(group) == 1:
            doc, provision = group[0]
            return [
                await _extract_one_provision_light(
                    client,
                    doc,
                    provision,
                    followup_pass_index=followup_pass_index,
                )
            ]
        return await _extract_batch_provisions_light(
            client,
            group,
            followup_pass_index=followup_pass_index,
        )

    if len(group) == 1:
        doc, provision = group[0]
        return [
            await _extract_one_provision(
                client,
                doc,
                provision,
                verify_mode=verify_mode,
                followup_pass_index=followup_pass_index,
            ),
        ]
    return await _extract_batch_provisions(
        client,
        group,
        verify_mode=verify_mode,
        followup_pass_index=followup_pass_index,
    )


async def _extract_provision_group_with_timeout(
    client: GonkaClient,
    group: list[tuple[NPADocument, ProvisionSpan]],
    *,
    verify_mode: str,
    extract_mode: str,
    group_timeout_seconds: float | None,
    followup_pass_index: int = 0,
) -> list[SPOExtractionResult]:
    coroutine = _extract_provision_group(
        client,
        group,
        verify_mode=verify_mode,
        extract_mode=extract_mode,
        followup_pass_index=followup_pass_index,
    )
    if group_timeout_seconds is None:
        return await coroutine
    return await asyncio.wait_for(coroutine, timeout=group_timeout_seconds)


def _increment_counter(telemetry: dict[str, int] | None, key: str, amount: int = 1) -> None:
    if telemetry is None:
        return
    telemetry[key] = int(telemetry.get(key, 0) or 0) + amount


def _is_retryable_group_exception(exc: Exception) -> bool:
    if isinstance(exc, asyncio.TimeoutError):
        return True
    if isinstance(exc, GonkaRequestError):
        return bool(exc.retryable)
    return False


def _is_retryable_failed_result(result: SPOExtractionResult) -> bool:
    return (
        not result.statements
        and bool(result.llm_error_retryable)
        and bool(result.llm_error_class)
    )


def _dedupe_work_items(
    items: list[tuple[NPADocument, ProvisionSpan]],
) -> list[tuple[NPADocument, ProvisionSpan]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[tuple[NPADocument, ProvisionSpan]] = []
    for doc, provision in items:
        key = (doc.card.doc_id, provision.anchor_path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((doc, provision))
    return deduped


def _resolve_dispatch_worker_count(
    client: GonkaClient,
    groups_total: int,
    *,
    lane_settings: _DispatchLaneSettings,
) -> int:
    hint = max(1, int(getattr(client, "dispatch_worker_hint", 8) or 8))
    worker_scale = min(1.0, max(0.05, float(lane_settings.worker_scale)))
    hint = max(1, int(round(hint * worker_scale)))
    return max(1, min(groups_total, hint))


def _resolve_dispatch_rps(
    client: GonkaClient,
    *,
    lane_settings: _DispatchLaneSettings,
) -> float:
    aggregate_rps = float(getattr(client, "theoretical_aggregate_rps", 0.0) or 0.0)
    if aggregate_rps <= 0.0:
        return 0.0
    scale = min(1.0, max(0.05, float(lane_settings.dispatch_rps_scale)))
    if scale >= 0.999:
        return 0.0
    return max(0.05, aggregate_rps * scale)


def _resolve_lane_settings(
    *,
    followup_pass_index: int,
    retryable_followup_worker_scale: float,
    retryable_followup_dispatch_rps_scale: float,
    retryable_followup_client_rate_scale: float,
    retryable_followup_client_concurrency_scale: float,
) -> _DispatchLaneSettings:
    if followup_pass_index <= 0:
        return _DispatchLaneSettings()
    return _DispatchLaneSettings(
        name="retry_followup",
        worker_scale=min(1.0, max(0.05, float(retryable_followup_worker_scale))),
        dispatch_rps_scale=min(1.0, max(0.05, float(retryable_followup_dispatch_rps_scale))),
        client_rate_scale=min(1.0, max(0.05, float(retryable_followup_client_rate_scale))),
        client_concurrency_scale=min(1.0, max(0.05, float(retryable_followup_client_concurrency_scale))),
    )


async def _run_request_groups(
    client: GonkaClient,
    request_groups: list[list[tuple[NPADocument, ProvisionSpan]]],
    *,
    verify_mode: str,
    extract_mode: str,
    group_timeout_seconds: float | None,
    lane_settings: _DispatchLaneSettings,
    followup_pass_index: int,
) -> list[list[SPOExtractionResult] | Exception]:
    if not request_groups:
        return []

    worker_count = _resolve_dispatch_worker_count(
        client,
        len(request_groups),
        lane_settings=lane_settings,
    )
    dispatch_limiter: _SlidingWindowLimiter | None = None
    dispatch_rps = _resolve_dispatch_rps(client, lane_settings=lane_settings)
    if dispatch_rps > 0.0:
        dispatch_limiter = _SlidingWindowLimiter(
            max_requests=1,
            window=(1.0 / dispatch_rps),
            jitter_ratio=0.12,
        )

    queue: asyncio.Queue[tuple[int, list[tuple[NPADocument, ProvisionSpan]]] | None] = asyncio.Queue()
    for index, group in enumerate(request_groups):
        queue.put_nowait((index, group))

    results: list[list[SPOExtractionResult] | Exception | None] = [None] * len(request_groups)

    async def _worker() -> None:
        while True:
            item = await queue.get()
            if item is None:
                queue.task_done()
                break
            index, group = item
            try:
                if dispatch_limiter is not None:
                    await dispatch_limiter.acquire()
                results[index] = await _extract_provision_group_with_timeout(
                    client,
                    group,
                    verify_mode=verify_mode,
                    extract_mode=extract_mode,
                    group_timeout_seconds=group_timeout_seconds,
                    followup_pass_index=followup_pass_index,
                )
            except Exception as exc:  # pragma: no cover - exercised via callers
                results[index] = exc
            finally:
                queue.task_done()

    workers = [asyncio.create_task(_worker()) for _ in range(worker_count)]
    await queue.join()
    for _ in workers:
        queue.put_nowait(None)
    await asyncio.gather(*workers)
    return [result if result is not None else RuntimeError("request_group_missing_result") for result in results]


_RETRY_TIMEOUT_MULTIPLIER = 1.5
_RETRY_BACKOFF_BASE_SECONDS = 3.0
"""Retry config:
- 50% more time than the original timeout (single-item batches are cheaper).
- 3s base backoff before first retry, growing per sub-group to let API drain.
"""


async def _retry_timed_out_group(
    client: GonkaClient,
    group: list[tuple[NPADocument, ProvisionSpan]],
    *,
    verify_mode: str,
    extract_mode: str,
    retry_batch_size: int,
    retry_batch_chars: int | None,
    adaptive_batch_downshift_enabled: bool,
    adaptive_batch_soft_chars_share: float,
    group_timeout_seconds: float | None,
    followup_pass_index: int = 0,
) -> list[SPOExtractionResult]:
    retry_timeout = (
        group_timeout_seconds * _RETRY_TIMEOUT_MULTIPLIER
        if group_timeout_seconds is not None
        else None
    )
    retried_results: list[SPOExtractionResult] = []
    retry_groups = _group_request_items(
        group,
        request_batch_size=max(1, retry_batch_size),
        request_batch_chars=retry_batch_chars,
        adaptive_batch_downshift_enabled=adaptive_batch_downshift_enabled,
        adaptive_batch_soft_chars_share=adaptive_batch_soft_chars_share,
    )
    # Backoff before first retry — let the API drain queued requests
    await asyncio.sleep(_RETRY_BACKOFF_BASE_SECONDS)
    for idx, retry_group in enumerate(retry_groups):
        if idx > 0:
            # Incremental backoff between sub-groups to avoid re-congesting
            await asyncio.sleep(_RETRY_BACKOFF_BASE_SECONDS * min(idx, 3))
        retried_results.extend(
            await _extract_provision_group_with_timeout(
                client,
                retry_group,
                verify_mode=verify_mode,
                extract_mode=extract_mode,
                group_timeout_seconds=retry_timeout,
                followup_pass_index=followup_pass_index,
            )
        )
    return retried_results


async def extract_spo_for_documents(
    client: GonkaClient,
    documents: list[NPADocument],
    provisions_by_doc: dict[str, list[ProvisionSpan]],
    *,
    results_dir: Path,
    task_batch_size: int = 1000,
    request_batch_size: int = 1,
    request_batch_chars: int | None = None,
    adaptive_batch_downshift_enabled: bool = False,
    adaptive_batch_soft_chars_share: float = 0.80,
    group_timeout_seconds: float | None = None,
    verify_mode: str = "llm",
    extract_mode: str = "full",
    overwrite_existing: bool = True,
    extraction_source: str = "llm",
    gate_meta_by_anchor: dict[str, dict[str, dict[str, Any]]] | None = None,
    fallback_rows_by_anchor: dict[str, dict[str, dict[str, Any]]] | None = None,
    merge_baseline_rows_by_anchor: dict[str, dict[str, dict[str, Any]]] | None = None,
    result_sink: Callable[[dict[str, Any]], None] | None = None,
    timeout_retry_enabled: bool = False,
    timeout_retry_batch_size: int = 1,
    timeout_retry_chars: int | None = None,
    retryable_followup_passes: int = 0,
    retryable_followup_delay_seconds: float = 0.0,
    retryable_followup_worker_scale: float = 0.5,
    retryable_followup_dispatch_rps_scale: float = 0.5,
    retryable_followup_client_rate_scale: float = 0.5,
    retryable_followup_client_concurrency_scale: float = 0.5,
    telemetry: dict[str, int] | None = None,
) -> tuple[int, set[str]]:
    """Extract SPO for all provisions across documents.

    Results are written to ``results_dir/{doc_id}.jsonl`` with one JSON line per provision.
    Returns ``(total_statement_count, failed_doc_ids)``.
    """
    work_items: list[tuple[NPADocument, ProvisionSpan]] = []
    for doc in documents:
        shard_dir = results_dir / _shard_prefix(doc.card.doc_id)
        shard_dir.mkdir(parents=True, exist_ok=True)
        out_path = shard_dir / f"{doc.card.doc_id}.jsonl"
        if overwrite_existing and out_path.exists():
            out_path.unlink()
        provisions = provisions_by_doc.get(doc.card.doc_id, [])
        for prov in provisions:
            work_items.append((doc, prov))

    if not work_items:
        return 0, set()

    total_statements = 0
    failed_doc_ids: set[str] = set()
    batch_size = max(1, task_batch_size)
    request_size = max(1, request_batch_size)
    max_followup_passes = max(0, int(retryable_followup_passes))
    gap_fill_null_yield_path = results_dir.parent / "gap_fill_null_yield.jsonl"

    def _append_gap_fill_null_yield(row: dict[str, Any]) -> None:
        gap_fill_null_yield_path.parent.mkdir(parents=True, exist_ok=True)
        with open(gap_fill_null_yield_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    for i in range(0, len(work_items), batch_size):
        pending_items = work_items[i : i + batch_size]
        passes_run = 0

        for followup_pass_index in range(max_followup_passes + 1):
            if not pending_items:
                break
            if followup_pass_index > 0:
                passes_run += 1
                _increment_counter(telemetry, "retry_followup_passes_run")
                if retryable_followup_delay_seconds > 0:
                    await asyncio.sleep(retryable_followup_delay_seconds)

            lane_settings = _resolve_lane_settings(
                followup_pass_index=followup_pass_index,
                retryable_followup_worker_scale=retryable_followup_worker_scale,
                retryable_followup_dispatch_rps_scale=retryable_followup_dispatch_rps_scale,
                retryable_followup_client_rate_scale=retryable_followup_client_rate_scale,
                retryable_followup_client_concurrency_scale=retryable_followup_client_concurrency_scale,
            )
            lane_context_factory = getattr(client, "request_lane", None)
            lane_context = (
                lane_context_factory(
                    lane_name=lane_settings.name,
                    rate_scale=lane_settings.client_rate_scale,
                    concurrency_scale=lane_settings.client_concurrency_scale,
                )
                if callable(lane_context_factory)
                else nullcontext()
            )

            with lane_context:
                request_groups = _group_request_items(
                    pending_items,
                    request_batch_size=max(1, timeout_retry_batch_size if followup_pass_index > 0 else request_size),
                    request_batch_chars=(
                        timeout_retry_chars
                        if followup_pass_index > 0 and timeout_retry_chars is not None
                        else request_batch_chars
                    ),
                    adaptive_batch_downshift_enabled=adaptive_batch_downshift_enabled,
                    adaptive_batch_soft_chars_share=adaptive_batch_soft_chars_share,
                )
                group_results = await _run_request_groups(
                    client,
                    request_groups,
                    verify_mode=verify_mode,
                    extract_mode=extract_mode,
                    group_timeout_seconds=group_timeout_seconds,
                    lane_settings=lane_settings,
                    followup_pass_index=followup_pass_index,
                )

                doc_buffers: dict[str, list[dict[str, Any]]] = {}
                retry_items_next: list[tuple[NPADocument, ProvisionSpan]] = []

                for group, group_result in zip(request_groups, group_results, strict=True):
                    if isinstance(group_result, Exception):
                        timeout = isinstance(group_result, asyncio.TimeoutError)
                        if timeout and timeout_retry_enabled:
                            _increment_counter(telemetry, "timeout_retry_groups_total")
                            try:
                                group_result = await _retry_timed_out_group(
                                    client,
                                    group,
                                    verify_mode=verify_mode,
                                    extract_mode=extract_mode,
                                    retry_batch_size=max(1, timeout_retry_batch_size),
                                    retry_batch_chars=timeout_retry_chars,
                                    adaptive_batch_downshift_enabled=adaptive_batch_downshift_enabled,
                                    adaptive_batch_soft_chars_share=adaptive_batch_soft_chars_share,
                                    group_timeout_seconds=group_timeout_seconds,
                                    followup_pass_index=followup_pass_index,
                                )
                                timeout = False
                                _increment_counter(telemetry, "timeout_retry_success_total")
                                logger.info(
                                    "Recovered timed-out provision group of {} items via retry split",
                                    len(group),
                                )
                            except Exception as retry_exc:
                                group_result = retry_exc
                                timeout = isinstance(retry_exc, asyncio.TimeoutError)
                                _increment_counter(telemetry, "timeout_retry_failure_total")
                        if isinstance(group_result, Exception):
                            if followup_pass_index < max_followup_passes and _is_retryable_group_exception(group_result):
                                retry_items_next.extend(group)
                                _increment_counter(telemetry, "retry_followup_pending_items_total", len(group))
                                continue
                            error_label = "timeout" if timeout else "failure"
                            logger.warning(
                                "Provision-group task {} for {} items: {}",
                                error_label,
                                len(group),
                                group_result,
                            )
                            fallback_rows: list[tuple[str, dict[str, Any]]] = []
                            if fallback_rows_by_anchor:
                                for doc, prov in group:
                                    base_row = fallback_rows_by_anchor.get(doc.card.doc_id, {}).get(prov.anchor_path)
                                    if base_row is None:
                                        fallback_rows = []
                                        break
                                    fallback_rows.append(
                                        (
                                            doc.card.doc_id,
                                            _materialize_fallback_row(
                                                base_row,
                                                error_message=str(group_result),
                                                timeout=timeout,
                                            ),
                                        )
                                    )
                            if fallback_rows:
                                for doc_id, row in fallback_rows:
                                    statements = row.get("statements")
                                    stmt_count = len(statements) if isinstance(statements, list) else 0
                                    if result_sink is not None:
                                        result_sink(row)
                                    # Skip persisting empty fallback rows — they inflate
                                    # empty_statement_rows_pct without adding value.
                                    if stmt_count > 0:
                                        doc_buffers.setdefault(doc_id, []).append(row)
                                        total_statements += stmt_count
                                continue
                            for doc, _ in group:
                                failed_doc_ids.add(doc.card.doc_id)
                            continue

                    for (doc, provision), result in zip(group, group_result, strict=True):
                        if followup_pass_index < max_followup_passes and _is_retryable_failed_result(result):
                            retry_items_next.append((doc, provision))
                            _increment_counter(telemetry, "retry_followup_pending_items_total")
                            continue
                        if not result.statements and (
                            "failed" in result.raw_llm_response.lower() or result.llm_error_class
                        ):
                            failed_doc_ids.add(result.doc_id)

                        row = result.model_dump(mode="json")
                        row["extraction_source"] = extraction_source
                        gate_score = 0.0
                        gate_reasons: list[str] = []
                        if gate_meta_by_anchor:
                            per_doc = gate_meta_by_anchor.get(result.doc_id, {})
                            meta = per_doc.get(result.provision_anchor)
                            if meta:
                                gate_score = float(meta.get("gate_score", 0.0) or 0.0)
                                gate_reasons = list(meta.get("gate_reason_codes") or [])
                                for key in (
                                    "legal_unit_subtype",
                                    "route_class",
                                    "empty_spo_retry_eligible",
                                    "audit_miss_prone",
                                    "reference_bearing",
                                    "threshold_bearing",
                                ):
                                    if key in meta:
                                        row[key] = meta.get(key)
                        row["gate_score"] = gate_score
                        row["gate_reason_codes"] = gate_reasons
                        row["extraction_source"] = extraction_source
                        persist_row = True
                        if merge_baseline_rows_by_anchor:
                            baseline_row = merge_baseline_rows_by_anchor.get(result.doc_id, {}).get(result.provision_anchor)
                            baseline_statements = (
                                baseline_row.get("statements", [])
                                if isinstance(baseline_row, dict)
                                else []
                            )
                            if not isinstance(baseline_statements, list):
                                baseline_statements = []
                            llm_statements = row.get("statements", [])
                            if not isinstance(llm_statements, list):
                                llm_statements = []
                            merged_statements, added_count = _merge_statement_lists(baseline_statements, llm_statements)
                            row["statements"] = merged_statements
                            row["baseline_statement_count"] = len(baseline_statements)
                            row["llm_gap_fill_llm_statement_count"] = len(llm_statements)
                            row["llm_gap_fill_added_statement_count"] = added_count
                            if extraction_source == "llm_gap_fill" and not llm_statements:
                                telemetry_row = {
                                    **row,
                                    "persisted_to_output": False,
                                }
                                if baseline_statements and merged_statements == baseline_statements:
                                    telemetry_row["gap_fill_null_yield_kind"] = "preserved_baseline"
                                else:
                                    telemetry_row["gap_fill_null_yield_kind"] = "persisted_empty"
                                _append_gap_fill_null_yield(telemetry_row)
                                row["persisted_to_output"] = False
                                row["gap_fill_null_yield_kind"] = telemetry_row["gap_fill_null_yield_kind"]
                                persist_row = False
                        if result_sink is not None:
                            result_sink(row)
                        if persist_row:
                            doc_buffers.setdefault(result.doc_id, []).append(row)
                            statements = row.get("statements")
                            total_statements += len(statements) if isinstance(statements, list) else 0
                            if followup_pass_index > 0:
                                _increment_counter(telemetry, "retry_followup_recovered_items_total")

                for doc_id, rows in doc_buffers.items():
                    out_path = results_dir / _shard_prefix(doc_id) / f"{doc_id}.jsonl"
                    with open(out_path, "a", encoding="utf-8") as fh:
                        for row in rows:
                            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

                pending_items = _dedupe_work_items(retry_items_next)

        if passes_run > 0 and pending_items:
            _increment_counter(telemetry, "retry_followup_items_exhausted_total", len(pending_items))

    if failed_doc_ids:
        logger.warning(
            "{} documents had failed provisions and will NOT be marked as done: {}",
            len(failed_doc_ids),
            ", ".join(sorted(failed_doc_ids)[:10]) + ("..." if len(failed_doc_ids) > 10 else ""),
        )

    return total_statements, failed_doc_ids
