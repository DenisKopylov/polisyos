"""Runtime control-plane response-shaping helpers."""

from __future__ import annotations

import json
from datetime import UTC
from decimal import Decimal
from typing import Any

from polisyos.core.contracts.control import DecisionValidityEventRequest
from polisyos.runtime.http.services._control_contracts import _build_api_meta


def _sum_call_events(events: list[dict[str, Any]]) -> dict[str, float]:
    prompt_tokens = 0.0
    completion_tokens = 0.0
    latency_ms = 0.0
    cost_usd = 0.0
    estimated_cost_usd = 0.0
    cost_delta_usd = 0.0
    for event in events:
        prompt_tokens += float(event.get("prompt_tokens") or 0)
        completion_tokens += float(event.get("completion_tokens") or 0)
        latency_ms += float(event.get("latency_ms") or 0)
        cost_usd += float(event.get("cost_usd") or 0.0)
        estimated_cost_usd += float(event.get("estimated_cost_usd") or 0.0)
        cost_delta_usd += float(event.get("cost_delta_usd") or 0.0)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
        "estimated_cost_usd": estimated_cost_usd,
        "cost_delta_usd": cost_delta_usd,
    }


def _delta_usage(
    before: dict[str, float],
    after: dict[str, float],
) -> tuple[int, int, int, float]:
    prompt = max(0, int(after["prompt_tokens"] - before["prompt_tokens"]))
    completion = max(0, int(after["completion_tokens"] - before["completion_tokens"]))
    latency = max(0, int(after["latency_ms"] - before["latency_ms"]))
    cost = max(0.0, float(after["cost_usd"] - before["cost_usd"]))
    return prompt, completion, latency, cost


def _build_scientist_v2_shadow_comparison(
    *,
    legacy_status: str,
    legacy_verdict: str | None,
    legacy_issue_count: int,
    legacy_cost_usd: float,
    legacy_prompt_tokens: int,
    legacy_completion_tokens: int,
    shadow_result: Any | None,
) -> dict[str, Any] | None:
    if shadow_result is None:
        return None
    shadow_metrics = dict(getattr(shadow_result, "metrics", {}) or {})
    shadow_result_payload = dict(getattr(shadow_result, "result", {}) or {})
    shadow_grounding = dict(shadow_result_payload.get("grounding") or {})
    claim_links = shadow_grounding.get("claim_links")
    supported_claims = 0
    total_claims = 0
    if isinstance(claim_links, list):
        total_claims = len(claim_links)
        supported_claims = sum(
            1
            for item in claim_links
            if isinstance(item, dict) and item.get("support_state") == "supported"
        )
    shadow_citation_coverage = float(shadow_metrics.get("citation_coverage") or 0.0)
    return {
        "legacy_status": legacy_status,
        "legacy_verdict": legacy_verdict,
        "shadow_verdict": shadow_result_payload.get("verdict"),
        "verdict_match": legacy_verdict == shadow_result_payload.get("verdict"),
        "legacy_issue_count": int(legacy_issue_count),
        "shadow_issue_count": int(shadow_result_payload.get("issue_count") or 0),
        "issue_count_delta": int(shadow_result_payload.get("issue_count") or 0)
        - int(legacy_issue_count),
        "legacy_cost_usd": float(legacy_cost_usd),
        "shadow_final_score": float(shadow_metrics.get("final_score") or 0.0),
        "legacy_total_tokens": int(legacy_prompt_tokens) + int(legacy_completion_tokens),
        "shadow_citation_coverage": shadow_citation_coverage,
        "shadow_supported_claims": supported_claims,
        "shadow_total_claims": total_claims,
        "default_on_candidate": bool(
            shadow_result_payload.get("verdict") == "APPROVE" and shadow_citation_coverage >= 0.85
        ),
    }


def _canonicalize_numeric_payload(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _canonicalize_numeric_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonicalize_numeric_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_canonicalize_numeric_payload(item) for item in value]
    return value


def _decision_validity_dedupe_payload(
    request: DecisionValidityEventRequest,
    *,
    dependency_keys: list[str],
) -> str:
    return json.dumps(
        {
            "trigger_type": request.trigger_type.value,
            "status": request.status.value,
            "reason": request.reason,
            "dependency_keys": sorted(dependency_keys),
            "source_ref": request.source_ref,
            "payload": request.payload,
            "occurred_at": (
                request.occurred_at.astimezone(UTC).replace(microsecond=0).isoformat()
                if request.occurred_at is not None
                else None
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


__all__ = [
    "_build_api_meta",
    "_build_scientist_v2_shadow_comparison",
    "_canonicalize_numeric_payload",
    "_decision_validity_dedupe_payload",
    "_delta_usage",
    "_sum_call_events",
]
