"""Runtime control-plane response-shaping helpers."""

from __future__ import annotations

import json
from datetime import UTC
from decimal import Decimal
from typing import Any, Mapping

from polisyos.core.contracts.control import (
    ControlApprovalProjection,
    ControlAuthorityGap,
    ControlProjectionSource,
    DecisionValidityEventRequest,
    OperatorDiagnostic,
    OperatorProjectionState,
    OperatorProjectionStateLabel,
)
from polisyos.runtime.http.services._control_contracts import _build_api_meta
from polisyos.runtime.quality.authority import authority_surface_decision
from polisyos.runtime.quality.projection_semantics import (
    PolicyDesignCaseProjectionError,
    build_policy_design_case_projection_from_runtime_graph,
    build_policy_design_case_projection_semantics,
)
from polisyos.runtime.quality.source_truth import (
    SourceTruthContractError,
    detect_source_truth_conflict,
)

_SERIOUS_EXECUTION_PROFILES = frozenset({"research", "governed", "production"})


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


_DEFAULT_PROJECTION_LABELS: tuple[tuple[OperatorProjectionState, str, str], ...] = (
    ("draft", "draft", "projection_only"),
    ("projection_only", "projection only", "projection_only"),
    ("redacted", "redacted", "projection_only"),
    ("stale", "stale", "projection_only"),
    ("contested", "contested", "projection_only"),
    ("projected", "projected", "projection_only"),
    ("blocked", "blocked", "runtime_authority"),
    ("readiness_closed", "readiness-closed", "runtime_authority"),
    ("approved", "approved", "projection_only"),
    ("rejected", "rejected", "projection_only"),
    ("published_blocked", "published-blocked", "runtime_authority"),
    ("publishable", "publishable", "projection_only"),
)

_LAYER_OWNER_DEFAULTS = {
    "fabric_materialization": "team-runtime-ops",
    "fabric_retrieval": "team-fabric",
    "foundry_methods": "team-foundry",
    "foundry_causal_validity": "team-foundry",
    "human_review_calibration": "team-quality-closeout",
    "llm_gateway": "team-runtime-ops",
    "lex": "team-policy-semantics",
    "normative_conflict": "team-policy-semantics",
    "privacy_compliance": "team-assurance",
    "quality_scorecard": "team-quality-closeout",
    "runtime_replay": "team-runtime-ops",
    "runtime_resilience": "team-runtime-ops",
    "scientist_decision_artifact": "team-policy-semantics",
    "scientist_policy_artifacts": "team-policy-semantics",
}


def _text_or_none(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, str] = {}
    for key, item in value.items():
        key_text = _text_or_none(key)
        item_text = _text_or_none(item)
        if key_text and item_text:
            result[key_text] = item_text
    return result


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        item_text = _text_or_none(item)
        if item_text and item_text not in result:
            result.append(item_text)
    return result


def build_control_job_projection_shape(
    *,
    record: Any,
    quality_status: str | None,
    quality_scorecard_ref: str | None,
    quality_gates: list[Any],
    blocking_quality_failures: list[Any],
) -> dict[str, Any]:
    """Build fail-closed dashboard projection fields for a control-job response."""

    progress = _dict_or_empty(getattr(record, "progress", None))
    projection_source = ControlProjectionSource(
        source_surface="runtime.control_job",
        source_detail="control_store_progress",
        authority_level="projection_only",
        projection_policy="projection_only",
    )
    authority_gaps = _authority_gaps(
        quality_gates=quality_gates,
        blocking_quality_failures=blocking_quality_failures,
    )
    surface_gap = _authority_surface_gap(progress)
    if surface_gap is not None and surface_gap.code not in {gap.code for gap in authority_gaps}:
        authority_gaps = [*authority_gaps, surface_gap]
    authoritative_scorecard_ref = _authoritative_scorecard_ref(
        progress=progress,
        quality_scorecard_ref=quality_scorecard_ref,
    )
    approval_projection = _approval_projection(
        progress=progress,
        record=record,
        quality_status=quality_status,
        authority_gaps=authority_gaps,
        projection_source=projection_source,
    )
    source_truth_conflict = _api_projection_source_truth_conflict(
        progress=progress,
        quality_status=quality_status,
        authoritative_scorecard_ref=authoritative_scorecard_ref,
        approval_projection=approval_projection,
    )
    policy_design_case_projection = _policy_design_projection(progress)
    operator_diagnostic = None
    if source_truth_conflict is not None:
        conflict_gap = _authority_gap_from_source_truth_conflict(source_truth_conflict)
        authority_gaps = [*authority_gaps, conflict_gap]
        approval_projection = _approval_projection(
            progress=progress,
            record=record,
            quality_status=quality_status,
            authority_gaps=authority_gaps,
            projection_source=projection_source,
        )
        operator_diagnostic = _operator_diagnostic_from_source_truth_conflict(
            source_truth_conflict,
            record=record,
            authoritative_scorecard_ref=authoritative_scorecard_ref,
        )
    return {
        "authoritative_scorecard_ref": authoritative_scorecard_ref,
        "projection_source": projection_source,
        "runtime_state": _text_or_none(progress.get("runtime_state"))
        or _text_or_none(getattr(record, "state", None)),
        "approval_projection": approval_projection,
        "unresolved_authority_gaps": authority_gaps,
        "next_diagnostic_commands": _unique_strings(
            gap.next_diagnostic_command for gap in authority_gaps
        ),
        "policy_design_case_projection": policy_design_case_projection,
        "operator_diagnostic": operator_diagnostic,
    }


def _approval_projection(
    *,
    progress: dict[str, Any],
    record: Any,
    quality_status: str | None,
    authority_gaps: list[ControlAuthorityGap],
    projection_source: ControlProjectionSource,
) -> ControlApprovalProjection:
    progress_projection = _dict_or_empty(progress.get("approval_projection"))
    scorecard = _quality_scorecard(progress)
    eligibility = _dict_or_empty(scorecard.get("approval_eligibility") if scorecard else None)
    state = (
        _text_or_none(progress_projection.get("state"))
        or _text_or_none(eligibility.get("state"))
        or _text_or_none(scorecard.get("approval_state") if scorecard else None)
    )
    eligible = _bool_or_none(progress_projection.get("eligible"))
    if eligible is None:
        eligible = _bool_or_none(eligibility.get("eligible"))
    if eligible is None and scorecard is not None:
        eligible = _bool_or_none(scorecard.get("approval_ready"))
    if eligible is None:
        eligible = state == "approval_ready" if state else False

    reasons = _unique_strings(
        [
            *_string_list(progress_projection.get("reasons")),
            *_string_list(eligibility.get("reasons")),
            *[gap.code for gap in authority_gaps],
        ]
    )
    serious = getattr(record, "effective_execution_profile", None) in (_SERIOUS_EXECUTION_PROFILES)
    if serious and (quality_status == "fail" or authority_gaps):
        eligible = False
        if state in {None, "approval_ready"}:
            state = "quality_failed"
        if quality_status == "fail" and not reasons:
            reasons.append("quality_not_passing")
    return ControlApprovalProjection(
        state=state,
        eligible=bool(eligible),
        reasons=reasons,
        source_surface=projection_source.source_surface,
        authority_level=projection_source.authority_level,
    )


def _authority_gaps(
    *,
    quality_gates: list[Any],
    blocking_quality_failures: list[Any],
) -> list[ControlAuthorityGap]:
    gaps: list[ControlAuthorityGap] = []
    seen: set[tuple[str, str, str | None]] = set()
    quality_gate_ids = {id(item) for item in quality_gates}
    for item in [*blocking_quality_failures, *quality_gates]:
        payload = _model_or_mapping(item)
        if id(item) in quality_gate_ids:
            status = _text_or_none(payload.get("status"))
            blocking = bool(payload.get("blocking", True))
            if not (blocking and status == "fail"):
                continue
        code = _text_or_none(payload.get("code")) or _text_or_none(
            payload.get("gate") or payload.get("name")
        )
        layer = _text_or_none(payload.get("layer")) or "runtime"
        message = _text_or_none(payload.get("message")) or code
        if code is None or message is None:
            continue
        phase = _text_or_none(payload.get("phase"))
        key = (code, layer, phase)
        if key in seen:
            continue
        seen.add(key)
        operator_diagnostic = _dict_or_empty(payload.get("operator_diagnostic"))
        gaps.append(
            ControlAuthorityGap(
                code=code,
                layer=layer,
                phase=phase,
                message=message,
                owner=_text_or_none(operator_diagnostic.get("owner")),
                evidence_ref=_text_or_none(payload.get("evidence_ref")),
                next_action=_text_or_none(payload.get("next_action")),
                next_diagnostic_command=(
                    _text_or_none(payload.get("next_diagnostic_command"))
                    or _text_or_none(operator_diagnostic.get("next_diagnostic_command"))
                ),
            )
        )
    return gaps


def _authority_surface_gap(progress: dict[str, Any]) -> ControlAuthorityGap | None:
    decision = authority_surface_decision(progress, surface="run")
    if not (decision.blocking or decision.visible_downgrade):
        return None
    return ControlAuthorityGap(
        code=decision.reason,
        layer="runtime_authority_surface",
        phase="run_status",
        message=(
            "Run status consumed AuthorityBoundary and cannot be treated as "
            f"authority for {decision.purpose}: {decision.status}."
        ),
        owner="team-runtime-quality",
        next_action="Repair workflow failure or rerun through the workspace loop authority path.",
        next_diagnostic_command=(
            "python3 tools/quality/validation/"
            "check_layer3_workflow_failure_authority.py --check --repo-root ."
        ),
    )


def _api_projection_source_truth_conflict(
    *,
    progress: dict[str, Any],
    quality_status: str | None,
    authoritative_scorecard_ref: str | None,
    approval_projection: ControlApprovalProjection,
) -> dict[str, Any] | None:
    scorecard = _quality_scorecard(progress)
    if scorecard is None:
        return None
    scorecard_ref = (
        authoritative_scorecard_ref
        or _text_or_none(scorecard.get("quality_scorecard_ref"))
        or _text_or_none(scorecard.get("authoritative_scorecard_ref"))
    )
    if scorecard_ref is None:
        return None
    authoritative_approval_state = _scorecard_approval_state(scorecard)
    try:
        return detect_source_truth_conflict(
            field_family="approval_readiness_public_status",
            authoritative_source="runtime.scorecard",
            authoritative_surface="runtime.scorecard",
            authoritative_values={
                "quality_status": _text_or_none(scorecard.get("quality_status")),
                "approval_state": authoritative_approval_state,
                "authoritative_scorecard_ref": scorecard_ref,
            },
            conflicting_source="runtime.api",
            conflicting_surface="runtime.api",
            conflicting_values={
                "quality_status": quality_status,
                "approval_state": approval_projection.state,
                "authoritative_scorecard_ref": authoritative_scorecard_ref,
            },
            fields=(
                "quality_status",
                "approval_state",
                "authoritative_scorecard_ref",
            ),
            downstream_impact=(
                "API projection remains non-approval-ready until runtime scorecard "
                "authority and projection values agree."
            ),
            cas_refs=[scorecard_ref],
            authoritative_ref=scorecard_ref,
            conflicting_ref=authoritative_scorecard_ref,
            details={
                "reader": "runtime.control_api",
                "projection_source": "runtime.api",
            },
        )
    except SourceTruthContractError:
        return None


def _scorecard_approval_state(scorecard: Mapping[str, Any]) -> str | None:
    eligibility = _dict_or_empty(scorecard.get("approval_eligibility"))
    return (
        _text_or_none(eligibility.get("state"))
        or _text_or_none(scorecard.get("approval_state"))
        or _text_or_none(scorecard.get("approval_decision"))
    )


def _authority_gap_from_source_truth_conflict(
    conflict: Mapping[str, Any],
) -> ControlAuthorityGap:
    failure_code = _text_or_none(conflict.get("failure_code"))
    message = "API projection conflicts with runtime scorecard authority." + (
        f" Lattice code: {failure_code}." if failure_code else ""
    )
    return ControlAuthorityGap(
        code="hds_source_truth_conflict",
        layer="source_truth",
        phase=_text_or_none(conflict.get("field_family")),
        message=message,
        owner=_text_or_none(conflict.get("owner")),
        evidence_ref=_text_or_none(conflict.get("authoritative_ref")),
        next_action="Use the runtime scorecard authority values before approval.",
        next_diagnostic_command=_text_or_none(conflict.get("next_diagnostic_command")),
    )


def _authoritative_scorecard_ref(
    *,
    progress: dict[str, Any],
    quality_scorecard_ref: str | None,
) -> str | None:
    scorecard = _quality_scorecard(progress)
    candidates: list[str | None] = [
        quality_scorecard_ref,
        _text_or_none(progress.get("authoritative_scorecard_ref")),
    ]
    if scorecard is not None:
        evidence_refs = _dict_or_empty(scorecard.get("evidence_refs"))
        candidates.extend(
            [
                _text_or_none(scorecard.get("authoritative_scorecard_ref")),
                _text_or_none(scorecard.get("scorecard_identity_ref")),
                _text_or_none(scorecard.get("quality_scorecard_ref")),
                _text_or_none(evidence_refs.get("quality_scorecard")),
            ]
        )
    return next((candidate for candidate in candidates if candidate), None)


def _quality_scorecard(progress: Mapping[str, Any]) -> dict[str, Any] | None:
    for key in ("quality_scorecard", "quality"):
        value = progress.get(key)
        if isinstance(value, Mapping):
            return dict(value)
    if any(
        key in progress for key in ("quality_status", "quality_gates", "blocking_quality_failures")
    ):
        return dict(progress)
    return None


def _policy_design_projection(progress: Mapping[str, Any]) -> dict[str, Any] | None:
    runtime_graph = _first_nested_mapping(
        progress,
        (
            ("runtime_pdc_graph",),
            ("details", "runtime_pdc_graph"),
            ("runtime_quality_evidence", "runtime_pdc_graph"),
            ("details", "runtime_quality_evidence", "runtime_pdc_graph"),
        ),
    )
    if runtime_graph is not None:
        try:
            return build_policy_design_case_projection_from_runtime_graph(
                runtime_pdc_graph=runtime_graph,
                surface="runtime.api",
            )
        except (PolicyDesignCaseProjectionError, ValueError, TypeError):
            return None
    case = _first_nested_mapping(
        progress,
        (
            ("policy_design_case",),
            ("details", "policy_design_case"),
            ("runtime_quality_evidence", "policy_design_case"),
            ("details", "runtime_quality_evidence", "policy_design_case"),
        ),
    )
    if case is None:
        return None
    source_payload = _first_nested_mapping(
        progress,
        (
            ("final_decision_artifact",),
            ("compiled_decision_artifact",),
            ("decision_artifact",),
            ("public_export",),
            ("quality_scorecard",),
            ("quality",),
            ("details", "final_decision_artifact"),
            ("details", "compiled_decision_artifact"),
            ("details", "decision_artifact"),
            ("details", "public_export"),
        ),
    )
    source_ref = _text_or_none(
        _first_nested_value(
            progress,
            (
                ("final_decision_artifact_ref",),
                ("decision_artifact_ref",),
                ("compiled_decision_artifact_ref",),
                ("public_export_ref",),
                ("details", "final_decision_artifact_ref"),
                ("details", "decision_artifact_ref"),
                ("details", "public_export_ref"),
            ),
        )
    )
    try:
        return build_policy_design_case_projection_semantics(
            policy_design_case=case,
            surface="runtime.api",
            source_payload=source_payload or {},
            source_ref=source_ref,
        )
    except (PolicyDesignCaseProjectionError, ValueError, TypeError):
        return None


def _first_nested_mapping(
    payload: Mapping[str, Any],
    paths: tuple[tuple[str, ...], ...],
) -> dict[str, Any] | None:
    value = _first_nested_value(payload, paths)
    return dict(value) if isinstance(value, Mapping) else None


def _first_nested_value(
    payload: Mapping[str, Any],
    paths: tuple[tuple[str, ...], ...],
) -> Any | None:
    for path in paths:
        value: Any = payload
        for key in path:
            if not isinstance(value, Mapping):
                value = None
                break
            value = value.get(key)
        if value is not None:
            return value
    return None


def _model_or_mapping(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json", exclude_none=True)
        return payload if isinstance(payload, dict) else {}
    return dict(value) if isinstance(value, Mapping) else {}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return None


def _unique_strings(values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _text_or_none(value)
        if text is not None and text not in result:
            result.append(text)
    return result


def _owner_for_layer(layer: str | None) -> str:
    if layer is None:
        return "team-runtime"
    return _LAYER_OWNER_DEFAULTS.get(layer, "team-runtime")


def _infer_missing_input(cause: str, message: str | None = None) -> str | None:
    for source in (cause, message or ""):
        normalized = source.lower()
        if "missing" not in normalized:
            continue
        if "_ref_missing" in normalized:
            return source.split("_ref_missing", 1)[0] + "_ref"
        if normalized.endswith("_missing"):
            return source.rsplit("_missing", 1)[0]
    return None


def _default_downstream_impact(projection_source: str) -> str:
    if projection_source == "runtime_control_job_failure":
        return "Serious run closeout cannot advance until the runtime failure is resolved."
    if projection_source == "runtime_quality_scorecard":
        return "Readiness, approval, and publication projections remain closed."
    return "Downstream operator projections remain blocked."


def _default_next_diagnostic_command(
    *,
    job_id: str | None,
    layer: str | None,
    phase: str | None,
) -> str:
    if layer == "llm_gateway":
        return (
            "uv run pytest tests/unit/scientist/orchestration/llm/test_provider_verification.py -q"
        )
    if layer == "quality_scorecard":
        return "uv run pytest tests/unit/runtime/quality/test_scorecard.py -q"
    if job_id:
        return "uv run pytest tests/unit/runtime/http/test_control_plane_store.py -q --tb=short"
    if phase:
        return "uv run pytest tests/unit/runtime/quality/test_scorecard.py -q"
    return "uv run pytest tests/unit/runtime/http/test_control_plane_store.py -q"


def _projection_labels_from_payload(value: Any) -> list[OperatorProjectionStateLabel]:
    if not isinstance(value, list):
        return [
            OperatorProjectionStateLabel(state=state, label=label, authority=authority)
            for state, label, authority in _DEFAULT_PROJECTION_LABELS
        ]
    labels: list[OperatorProjectionStateLabel] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        raw_state = _text_or_none(item.get("state"))
        label = _text_or_none(item.get("label")) or raw_state
        authority = _text_or_none(item.get("authority")) or "projection_only"
        if raw_state is None or label is None:
            continue
        state = raw_state.replace("-", "_")
        if state not in {entry[0] for entry in _DEFAULT_PROJECTION_LABELS}:
            continue
        if authority not in {"runtime_authority", "projection_only"}:
            authority = "projection_only"
        labels.append(
            OperatorProjectionStateLabel(
                state=state,  # type: ignore[arg-type]
                label=label,
                authority=authority,  # type: ignore[arg-type]
            )
        )
    return labels


def _build_operator_diagnostic(
    payload: Mapping[str, Any],
    *,
    authoritative_runtime_state: str,
    projection_source: str,
    fallback_phase: str | None,
    fallback_cause: str,
    fallback_message: str | None = None,
    fallback_owner: str | None = None,
    fallback_next_action: str | None = None,
    job_id: str | None = None,
    extra_authority_refs: Mapping[str, Any] | None = None,
    extra_evidence_refs: list[str] | None = None,
) -> OperatorDiagnostic:
    layer = _text_or_none(payload.get("layer"))
    phase = _text_or_none(payload.get("phase")) or fallback_phase or "unknown"
    cause = (
        _text_or_none(payload.get("first_blocking_cause"))
        or _text_or_none(payload.get("code"))
        or _text_or_none(payload.get("gate"))
        or _text_or_none(payload.get("name"))
        or fallback_cause
    )
    authority_refs = _string_map(payload.get("authority_refs"))
    authority_refs.update(_string_map(extra_authority_refs))
    artifact_refs = _string_map(payload.get("artifact_refs"))
    authority_refs.update({key: value for key, value in artifact_refs.items() if key})

    evidence_refs = _string_list(payload.get("evidence_refs"))
    evidence_ref = _text_or_none(payload.get("evidence_ref"))
    if evidence_ref:
        evidence_refs.append(evidence_ref)
    for value in authority_refs.values():
        if value not in evidence_refs:
            evidence_refs.append(value)
    for value in extra_evidence_refs or []:
        if value and value not in evidence_refs:
            evidence_refs.append(value)

    return OperatorDiagnostic(
        authoritative_runtime_state=authoritative_runtime_state,
        projection_source=projection_source,
        owner=(
            _text_or_none(payload.get("owner"))
            or _text_or_none(payload.get("responsible_owner"))
            or fallback_owner
            or _owner_for_layer(layer)
        ),
        phase=phase,
        first_blocking_cause=cause,
        upstream_missing_input=(
            _text_or_none(payload.get("upstream_missing_input"))
            or _infer_missing_input(cause, fallback_message)
        ),
        downstream_impact=(
            _text_or_none(payload.get("downstream_impact"))
            or _default_downstream_impact(projection_source)
        ),
        authority_refs=authority_refs,
        blocker_overridable=bool(payload.get("blocker_overridable", False)),
        evidence_refs=evidence_refs,
        next_diagnostic_command=(
            _text_or_none(payload.get("next_diagnostic_command"))
            or _text_or_none(payload.get("next_command"))
            or _text_or_none(payload.get("diagnostic_command"))
            or fallback_next_action
            or _default_next_diagnostic_command(job_id=job_id, layer=layer, phase=phase)
        ),
        projection_labels=_projection_labels_from_payload(payload.get("projection_labels")),
    )


def _operator_diagnostic_from_failure_payload(
    failure_payload: Mapping[str, Any],
    *,
    authoritative_runtime_state: str,
    fallback_phase: str | None,
    fallback_message: str | None,
    job_id: str | None,
) -> OperatorDiagnostic:
    return _build_operator_diagnostic(
        failure_payload,
        authoritative_runtime_state=authoritative_runtime_state,
        projection_source="runtime_control_job_failure",
        fallback_phase=fallback_phase,
        fallback_cause=_text_or_none(failure_payload.get("code")) or "control_job_failed",
        fallback_message=fallback_message,
        job_id=job_id,
    )


def _operator_diagnostic_from_quality_payload(
    quality_payload: Mapping[str, Any],
    *,
    authoritative_runtime_state: str,
    fallback_phase: str | None,
    job_id: str | None,
    quality_scorecard_ref: str | None = None,
    quality_evidence_bundle_path: str | None = None,
) -> OperatorDiagnostic:
    authority_refs = _string_map(quality_payload.get("authority_refs"))
    evidence_refs = _string_map(quality_payload.get("evidence_refs"))
    if quality_scorecard_ref:
        authority_refs.setdefault("quality_scorecard", quality_scorecard_ref)
    for key in ("quality_scorecard", "policy_grounding_matrix", "runtime_event_log"):
        value = evidence_refs.get(key)
        if isinstance(value, str):
            authority_refs.setdefault(key, value)
    extra_evidence_refs = []
    if quality_evidence_bundle_path:
        extra_evidence_refs.append(quality_evidence_bundle_path)
    return _build_operator_diagnostic(
        quality_payload,
        authoritative_runtime_state=authoritative_runtime_state,
        projection_source="runtime_quality_scorecard",
        fallback_phase=fallback_phase,
        fallback_cause=(
            _text_or_none(quality_payload.get("code"))
            or _text_or_none(quality_payload.get("gate"))
            or _text_or_none(quality_payload.get("name"))
            or "quality_failure"
        ),
        fallback_message=_text_or_none(quality_payload.get("message")),
        fallback_owner=_owner_for_layer(_text_or_none(quality_payload.get("layer"))),
        job_id=job_id,
        extra_authority_refs=authority_refs,
        extra_evidence_refs=extra_evidence_refs,
    )


def _operator_diagnostic_from_source_truth_conflict(
    conflict: Mapping[str, Any],
    *,
    record: Any,
    authoritative_scorecard_ref: str | None,
) -> OperatorDiagnostic:
    evidence_refs = _string_list(conflict.get("cas_refs"))
    authoritative_ref = _text_or_none(conflict.get("authoritative_ref"))
    if authoritative_ref and authoritative_ref not in evidence_refs:
        evidence_refs.append(authoritative_ref)
    payload = {
        "code": "hds_source_truth_conflict",
        "layer": "source_truth",
        "phase": _text_or_none(conflict.get("field_family")),
        "message": ("API projection conflicts with runtime scorecard authority."),
        "owner": _text_or_none(conflict.get("owner")),
        "downstream_impact": _text_or_none(conflict.get("downstream_impact")),
        "next_diagnostic_command": _text_or_none(conflict.get("next_diagnostic_command")),
        "authority_refs": {
            key: value
            for key, value in {
                "authoritative_scorecard_ref": authoritative_scorecard_ref,
                "source_truth_conflict_ref": authoritative_ref,
            }.items()
            if value
        },
        "evidence_refs": evidence_refs,
        "blocker_overridable": False,
    }
    return _build_operator_diagnostic(
        payload,
        authoritative_runtime_state=_text_or_none(getattr(record, "state", None)) or "unknown",
        projection_source="runtime_api_projection",
        fallback_phase=_text_or_none(conflict.get("field_family")),
        fallback_cause="hds_source_truth_conflict",
        fallback_message="API projection conflicts with runtime scorecard authority.",
        fallback_owner=_text_or_none(conflict.get("owner")),
        fallback_next_action=_text_or_none(conflict.get("next_diagnostic_command")),
        job_id=_text_or_none(getattr(record, "job_id", None)),
    )


__all__ = [
    "_build_api_meta",
    "_build_scientist_v2_shadow_comparison",
    "_canonicalize_numeric_payload",
    "_decision_validity_dedupe_payload",
    "_delta_usage",
    "_operator_diagnostic_from_failure_payload",
    "_operator_diagnostic_from_quality_payload",
    "_sum_call_events",
    "build_control_job_projection_shape",
]
