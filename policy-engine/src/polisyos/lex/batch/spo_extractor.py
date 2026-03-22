"""Stage 3: Async LLM-based 2-pass extraction via Gonka (OpenAI-compatible API).

Pass 1: Extract statements.
Pass 2: Verify + normalize extracted statements against the same provision.

Policy: mark-and-continue for low confidence (no extra LLM passes).
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Callable

from polisyos.common.logger import get_logger
from polisyos.lex.batch.provisions_io import _shard_prefix
from polisyos.lex.batch.spo_client import (
    GonkaClient,
    GonkaClientPool,
    _SlidingWindowLimiter,
    _retry_delay_seconds,
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


def _build_extract_failed_result(
    *,
    client: GonkaClient,
    doc: NPADocument,
    provision: ProvisionSpan,
    error_message: str,
    pass1_latency_ms: int,
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
            resp_verify = await client.chat_completion(
                verify_messages,
                response_format={"type": "json_object"},
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
        resp_extract = await client.chat_completion(
            extract_messages,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.warning("SPO extract failed for {} {}: {}", doc.card.doc_id, provision.anchor_path, exc)
        return _build_extract_failed_result(
            client=client,
            doc=doc,
            provision=provision,
            error_message=str(exc),
            pass1_latency_ms=int((time.monotonic() - t1) * 1000),
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
    )


async def _extract_one_provision_light(
    client: GonkaClient,
    doc: NPADocument,
    provision: ProvisionSpan,
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
        resp = await client.chat_completion(
            messages,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.warning("SPO light extract failed for {} {}: {}", doc.card.doc_id, provision.anchor_path, exc)
        return _build_extract_failed_result(
            client=client,
            doc=doc,
            provision=provision,
            error_message=str(exc),
            pass1_latency_ms=int((time.monotonic() - t1) * 1000),
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
) -> list[SPOExtractionResult]:
    if extract_mode == "light":
        tasks = [
            asyncio.create_task(
                _extract_one_provision_light(client, entry.doc, entry.provision),
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
        return await _run_single_extractions(client, entries, verify_mode=verify_mode)

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
        resp_extract = await client.chat_completion(
            extract_messages,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.warning(
            "SPO batched extract failed for {} provisions; fallback to single requests: {}",
            len(entries),
            exc,
        )
        return await _run_single_extractions(client, entries, verify_mode=verify_mode)

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
        return await _run_single_extractions(client, entries, verify_mode=verify_mode)

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
        )
        results_by_id[entry.item_id] = fallback[0]

    return [results_by_id[entry.item_id] for entry in entries]


async def _extract_batch_provisions_light(
    client: GonkaClient,
    batch_items: list[tuple[NPADocument, ProvisionSpan]],
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
        return await _run_single_extractions(client, entries, extract_mode="light")

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
        single_results = await _run_single_extractions(client, uncached_entries, extract_mode="light")
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
        resp = await client.chat_completion(
            messages,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.warning(
            "SPO batched light extract failed for {} provisions; fallback to singles: {}",
            len(uncached_entries),
            exc,
        )
        fallback = await _run_single_extractions(client, uncached_entries, extract_mode="light")
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
        fallback = await _run_single_extractions(client, uncached_entries, extract_mode="light")
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
            fallback = await _run_single_extractions(client, [entry], extract_mode="light")
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
) -> list[SPOExtractionResult]:
    if not group:
        return []

    if extract_mode == "light":
        if len(group) == 1:
            doc, provision = group[0]
            return [await _extract_one_provision_light(client, doc, provision)]
        return await _extract_batch_provisions_light(client, group)

    if len(group) == 1:
        doc, provision = group[0]
        return [
            await _extract_one_provision(
                client,
                doc,
                provision,
                verify_mode=verify_mode,
            ),
        ]
    return await _extract_batch_provisions(client, group, verify_mode=verify_mode)


async def _extract_provision_group_with_timeout(
    client: GonkaClient,
    group: list[tuple[NPADocument, ProvisionSpan]],
    *,
    verify_mode: str,
    extract_mode: str,
    group_timeout_seconds: float | None,
) -> list[SPOExtractionResult]:
    coroutine = _extract_provision_group(
        client,
        group,
        verify_mode=verify_mode,
        extract_mode=extract_mode,
    )
    if group_timeout_seconds is None:
        return await coroutine
    return await asyncio.wait_for(coroutine, timeout=group_timeout_seconds)


def _increment_counter(telemetry: dict[str, int] | None, key: str, amount: int = 1) -> None:
    if telemetry is None:
        return
    telemetry[key] = int(telemetry.get(key, 0) or 0) + amount


async def _retry_timed_out_group(
    client: GonkaClient,
    group: list[tuple[NPADocument, ProvisionSpan]],
    *,
    verify_mode: str,
    extract_mode: str,
    retry_batch_size: int,
    retry_batch_chars: int | None,
    group_timeout_seconds: float | None,
) -> list[SPOExtractionResult]:
    retried_results: list[SPOExtractionResult] = []
    retry_groups = _group_request_items(
        group,
        request_batch_size=max(1, retry_batch_size),
        request_batch_chars=retry_batch_chars,
    )
    for retry_group in retry_groups:
        retried_results.extend(
            await _extract_provision_group_with_timeout(
                client,
                retry_group,
                verify_mode=verify_mode,
                extract_mode=extract_mode,
                group_timeout_seconds=group_timeout_seconds,
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

    for i in range(0, len(work_items), batch_size):
        chunk = work_items[i : i + batch_size]
        request_groups = _group_request_items(
            chunk,
            request_batch_size=request_size,
            request_batch_chars=request_batch_chars,
        )
        tasks = [
            asyncio.create_task(
                _extract_provision_group_with_timeout(
                    client,
                    group,
                    verify_mode=verify_mode,
                    extract_mode=extract_mode,
                    group_timeout_seconds=group_timeout_seconds,
                )
            )
            for group in request_groups
        ]
        group_results = await asyncio.gather(*tasks, return_exceptions=True)

        doc_buffers: dict[str, list[dict[str, Any]]] = {}
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
                            group_timeout_seconds=group_timeout_seconds,
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
                            if result_sink is not None:
                                result_sink(row)
                            doc_buffers.setdefault(doc_id, []).append(row)
                            statements = row.get("statements")
                            total_statements += len(statements) if isinstance(statements, list) else 0
                        continue
                    for doc, _ in group:
                        failed_doc_ids.add(doc.card.doc_id)
                    continue

            for result in group_result:
                if not result.statements and "failed" in result.raw_llm_response.lower():
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
                if result_sink is not None:
                    result_sink(row)
                doc_buffers.setdefault(result.doc_id, []).append(row)
                statements = row.get("statements")
                total_statements += len(statements) if isinstance(statements, list) else 0

        for doc_id, rows in doc_buffers.items():
            out_path = results_dir / _shard_prefix(doc_id) / f"{doc_id}.jsonl"
            with open(out_path, "a", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    if failed_doc_ids:
        logger.warning(
            "{} documents had failed provisions and will NOT be marked as done: {}",
            len(failed_doc_ids),
            ", ".join(sorted(failed_doc_ids)[:10]) + ("..." if len(failed_doc_ids) > 10 else ""),
        )

    return total_statements, failed_doc_ids
