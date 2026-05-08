"""Decision-packet validation and degraded-path helpers."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import content_hash, from_canonical_bytes
from polisyos.core.contracts.decision_validity import (
    DecisionBasisSection,
    DecisionTriggerRecord,
    DecisionTriggerSpec,
    DecisionTriggerType,
    DecisionValidityEnvelope,
    DecisionValidityEvaluation,
    DecisionValidityStatus,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet_support import (
    ReplayReadiness,
    _dedupe_strings,
    _extract_context_payload,
    _fingerprint_payload,
    _path_get,
    _recommended_action,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_JUDGE_VERDICT_REF,
    ARTIFACT_LOWERED_IR_REF,
    ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_COMPILE_REPORT_REF,
    REPORT_LINK_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.state import ExperimentState

logger = get_logger(__name__)

_DECISION_PACKET_LOAD_ERRORS = (
    OSError,
    ValueError,
    TypeError,
    KeyError,
    ValidationError,
)


def _phase5_validation_summary(report: Any) -> dict[str, Any]:
    """Return the compact in-packet Phase-5 validation summary."""

    return {
        "schema_version": getattr(report, "schema_version", "2.0"),
        "verdict": report.verdict,
        "readiness": report.readiness,
        "gate_failures": list(report.gate_failures),
        "components": [
            {
                "name": component.name,
                "status": component.status,
                "required": component.required,
            }
            for component in report.phase5_components
        ],
    }


def _should_run_phase5_publication_preflight(state: ExperimentState) -> bool:
    """Return whether this packet is explicitly opted into Phase-5 publication checks."""

    params = state.params
    if state.artifacts_index.get(ARTIFACT_JUDGE_VERDICT_REF) is not None:
        return True
    return any(
        bool(params.get(key))
        for key in (
            "phase5_enforce_publication",
            "phase5_require_judge_verdict",
            "phase5_require_advisor_consensus",
            "phase5_requires_fairness",
            "phase5_judge_input_bundle",
            "judge_input_bundle",
            "judge_verdict",
            "high_impact",
        )
    )


def _missing_serious_decision_contracts(
    *,
    state: ExperimentState,
    monitoring_contract_ref: str | None,
) -> list[str]:
    profile = (
        str(state.execution_profile or state.params.get("execution_profile") or "").strip().lower()
    )
    if profile not in {"research", "governed", "production"}:
        return []
    missing: list[str] = []
    if state.capability_manifest_ref is None:
        missing.append("capability_manifest_ref")
    if ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF not in state.artifacts_index:
        missing.append(ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF)
    if ARTIFACT_TRANSPORTABILITY_RESULT_REF not in state.artifacts_index:
        missing.append(ARTIFACT_TRANSPORTABILITY_RESULT_REF)
    if ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF not in state.artifacts_index:
        missing.append(ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF)
    if not monitoring_contract_ref:
        missing.append("monitoring_contract_ref")
    return missing


def _decision_packet_degraded(
    *,
    operation: str,
    reason: str,
    exc: BaseException,
    ref: ArtifactRef | None = None,
    artifact_id: str | None = None,
    artifact_key: str | None = None,
) -> dict[str, Any]:
    details: dict[str, Any] = {}
    if ref is not None:
        details["artifact_id"] = str(ref.artifact_id)
    elif isinstance(artifact_id, str) and artifact_id:
        details["artifact_id"] = artifact_id
    if artifact_key is not None:
        details["artifact_key"] = artifact_key
    return emit_degraded_path(
        component="scientist.build_decision_packet",
        operation=operation,
        reason=reason,
        exc=exc,
        details=details,
        log=logger,
    )


def _record_decision_packet_degraded(
    packet_payload: dict[str, object],
    envelope: dict[str, Any],
) -> None:
    degraded_paths = packet_payload.setdefault("degraded_paths", [])
    if isinstance(degraded_paths, list):
        degraded_paths.append(envelope)
    notes = packet_payload.setdefault("notes", [])
    if isinstance(notes, list):
        reason = str(envelope.get("reason", "decision_packet_degraded"))
        message = str(envelope.get("message", reason))
        notes.append(f"{reason}: {message}")


def _record_decision_packet_section_degraded(
    packet_payload: dict[str, object] | None,
    *,
    operation: str,
    reason: str,
    exc: BaseException,
    ref: ArtifactRef | None = None,
    artifact_id: str | None = None,
    artifact_key: str | None = None,
) -> None:
    if packet_payload is None:
        return
    _record_decision_packet_degraded(
        packet_payload,
        _decision_packet_degraded(
            operation=operation,
            reason=reason,
            exc=exc,
            ref=ref,
            artifact_id=artifact_id,
            artifact_key=artifact_key,
        ),
    )


def _build_analysis_limits(packet_payload: dict[str, object]) -> dict[str, object]:
    diagnostics = packet_payload.get("diagnostics_summary")
    diagnostics_dict = diagnostics if isinstance(diagnostics, dict) else {}
    labels: list[str] = []
    contract_warnings = diagnostics_dict.get("contract_warnings")
    normalized_contract_warnings = (
        [str(item) for item in contract_warnings if isinstance(item, str)]
        if isinstance(contract_warnings, list)
        else []
    )

    transport_engine = diagnostics_dict.get("transport_engine")
    if isinstance(transport_engine, str) and transport_engine.startswith("simplified"):
        labels.append("transportability_simplified_engine")
    if diagnostics_dict.get("legal_executed") is False:
        labels.append("legal_not_run")
    if diagnostics_dict.get("requires_expert_review") is True:
        labels.append("expert_review_required")

    replay_readiness = diagnostics_dict.get("replay_readiness")
    if replay_readiness == ReplayReadiness.PARTIAL.value:
        labels.append("partial_replay_readiness")
    elif replay_readiness == ReplayReadiness.INCOMPLETE.value:
        labels.append("incomplete_replay_readiness")

    if diagnostics_dict.get("uncertainty_available") is False:
        labels.append("missing_uncertainty_artifact")
    if diagnostics_dict.get("sensitivity_is_robust") is False:
        labels.append("causal_sensitivity_fragile")
    if packet_payload.get("causal") is None:
        labels.append("causal_not_run")
    if packet_payload.get("distributional") is None:
        labels.append("distributional_not_run")
    if packet_payload.get("abm_alignment") is None:
        labels.append("abm_alignment_not_run")
    if any(
        warning.startswith("missing_runtime_mechanism_support:")
        for warning in normalized_contract_warnings
    ):
        labels.append("missing_runtime_mechanism_support")
    if diagnostics_dict.get("has_degraded_paths") is True:
        labels.append("decision_packet_degraded")

    return {
        "labels": labels,
        "transportability_simplified_engine": "transportability_simplified_engine" in labels,
        "legal_not_run": "legal_not_run" in labels,
        "expert_review_required": "expert_review_required" in labels,
        "partial_replay_readiness": "partial_replay_readiness" in labels,
        "incomplete_replay_readiness": "incomplete_replay_readiness" in labels,
        "missing_uncertainty_artifact": "missing_uncertainty_artifact" in labels,
        "missing_runtime_mechanism_support": "missing_runtime_mechanism_support" in labels,
        "causal_sensitivity_fragile": "causal_sensitivity_fragile" in labels,
        "decision_packet_degraded": "decision_packet_degraded" in labels,
    }


def _nested_status(payload: dict[str, object], key: str) -> str | None:
    nested = payload.get(key)
    nested_dict = nested if isinstance(nested, dict) else {}
    status = nested_dict.get("status")
    return str(status) if isinstance(status, str) else None


def _build_decision_validity_envelope(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    packet_payload: dict[str, object],
    build_normative_basis: Callable[[dict[str, object]], DecisionBasisSection],
    build_data_basis: Callable[[ExecutionContext, dict[str, object]], DecisionBasisSection],
    build_knowledge_basis: Callable[[ExecutionContext, dict[str, object]], DecisionBasisSection],
    build_transportability_basis: Callable[..., DecisionBasisSection],
    build_watched_triggers: Callable[..., list[DecisionTriggerSpec]],
    load_normative_frame_payload: Callable[
        [ExecutionContext, dict[str, object]], dict[str, Any] | None
    ],
) -> DecisionValidityEnvelope:
    source_context = _extract_context_payload(
        state,
        "source_context",
        "source_context_profile",
    )
    target_context = _extract_context_payload(
        state,
        "target_context",
        "target_context_profile",
        "context_profile",
    )
    source_context_fingerprint = _fingerprint_payload(source_context)
    target_context_fingerprint = _fingerprint_payload(target_context)

    normative_basis = build_normative_basis(packet_payload)
    data_basis = build_data_basis(ctx, packet_payload)
    knowledge_basis = build_knowledge_basis(ctx, packet_payload)
    transportability_basis = build_transportability_basis(
        state=state,
        packet_payload=packet_payload,
        source_context_fingerprint=source_context_fingerprint,
        target_context_fingerprint=target_context_fingerprint,
    )
    normative_frame_payload = load_normative_frame_payload(ctx, packet_payload)
    normative_policy = _path_get(packet_payload, ("tradeoff_certificate", "selected_policy"))

    policy_fingerprint = content_hash(
        json.dumps(
            {
                "trinity_bundle_ref": _path_get(
                    packet_payload, ("inputs", INPUT_TRINITY_BUNDLE_REF)
                ),
                "policy_summary": packet_payload.get("policy_summary"),
                "intervention_count": packet_payload.get("intervention_count"),
                "target_context_fingerprint": target_context_fingerprint,
                "normative_frame": normative_frame_payload,
                "normative_policy": normative_policy,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    decision_lineage_key = content_hash(
        json.dumps(
            {
                "trinity_bundle_ref": _path_get(
                    packet_payload, ("inputs", INPUT_TRINITY_BUNDLE_REF)
                ),
                "policy_summary": packet_payload.get("policy_summary"),
                "intervention_count": packet_payload.get("intervention_count"),
                "target_context_fingerprint": target_context_fingerprint,
                "normative_frame": normative_frame_payload,
                "normative_policy": normative_policy,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )

    return DecisionValidityEnvelope(
        decision_lineage_key=decision_lineage_key,
        policy_fingerprint=policy_fingerprint,
        source_context_fingerprint=source_context_fingerprint,
        target_context_fingerprint=target_context_fingerprint,
        normative_basis=normative_basis,
        data_basis=data_basis,
        knowledge_basis=knowledge_basis,
        transportability_basis=transportability_basis,
        watched_triggers=build_watched_triggers(
            normative_basis=normative_basis,
            data_basis=data_basis,
            knowledge_basis=knowledge_basis,
            transportability_basis=transportability_basis,
        ),
    )


def _build_decision_validity_baseline(
    *,
    packet_payload: dict[str, object],
    envelope: DecisionValidityEnvelope,
) -> DecisionValidityEvaluation:
    triggers: list[DecisionTriggerRecord] = []
    reasons: list[str] = []

    diagnostics = packet_payload.get("diagnostics_summary")
    diagnostics_dict = diagnostics if isinstance(diagnostics, dict) else {}
    governance = packet_payload.get("governance")
    governance_dict = governance if isinstance(governance, dict) else {}

    if bool(diagnostics_dict.get("human_review_needed")) or bool(
        diagnostics_dict.get("requires_expert_review")
    ):
        triggers.append(
            DecisionTriggerRecord(
                trigger_type=DecisionTriggerType.EXPERT_REVIEW,
                status=DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
                reason="human_or_expert_review_required",
                details={
                    "human_review_needed": bool(diagnostics_dict.get("human_review_needed")),
                    "requires_expert_review": bool(diagnostics_dict.get("requires_expert_review")),
                },
            )
        )
        reasons.append("human_or_expert_review_required")

    if str(governance_dict.get("verdict", "")).strip().lower() == "human_gate":
        triggers.append(
            DecisionTriggerRecord(
                trigger_type=DecisionTriggerType.HUMAN_GATE,
                status=DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
                reason="governance_verdict_human_gate",
            )
        )
        reasons.append("governance_verdict_human_gate")

    data_summary = envelope.data_basis.summary
    freshness_level = str(data_summary.get("freshness_level", "")).strip().lower()
    if freshness_level and freshness_level != "fresh":
        triggers.append(
            DecisionTriggerRecord(
                trigger_type=DecisionTriggerType.DATASET_SUPERSEDED,
                status=DecisionValidityStatus.STALE,
                reason=f"data_freshness_{freshness_level}",
                dependency_key=data_summary.get("dataset_dependency_key"),
                details={"freshness_level": freshness_level},
            )
        )
        reasons.append(f"data_freshness_{freshness_level}")
    if bool(data_summary.get("schema_drift")) or bool(data_summary.get("contract_drift")):
        drift_reason = (
            "schema_drift_detected"
            if bool(data_summary.get("schema_drift"))
            else "contract_drift_detected"
        )
        triggers.append(
            DecisionTriggerRecord(
                trigger_type=DecisionTriggerType.HISTORICAL_SEMANTIC_REVISION,
                status=DecisionValidityStatus.STALE,
                reason=drift_reason,
            )
        )
        reasons.append(drift_reason)

    knowledge_summary = envelope.knowledge_basis.summary
    knowledge_freshness = str(knowledge_summary.get("freshness_status", "")).strip().lower()
    if knowledge_freshness in {"stale", "expired"}:
        triggers.append(
            DecisionTriggerRecord(
                trigger_type=DecisionTriggerType.CONTRADICTING_EVIDENCE,
                status=DecisionValidityStatus.WARNING,
                reason=f"knowledge_bundle_{knowledge_freshness}",
                dependency_key=knowledge_summary.get("knowledge_dependency_key"),
                details={"freshness_status": knowledge_freshness},
            )
        )
        reasons.append(f"knowledge_bundle_{knowledge_freshness}")

    status = DecisionValidityStatus.ACTIVE
    for trigger in triggers:
        status = _max_validity_status(status, trigger.status)
    normative_summary = envelope.normative_basis.summary
    if str(normative_summary.get("normative_model_completeness", "")).strip().lower() == "partial":
        status = _max_validity_status(status, DecisionValidityStatus.WARNING)
        reasons.append("normative_model_partial")
    residual_dissent_count = normative_summary.get("normative_residual_dissent_count")
    if isinstance(residual_dissent_count, int) and residual_dissent_count > 0:
        status = _max_validity_status(status, DecisionValidityStatus.WARNING)
        reasons.append("normative_residual_dissent")

    return DecisionValidityEvaluation(
        decision_lineage_key=envelope.decision_lineage_key,
        status=status,
        reasons=_dedupe_strings(reasons),
        triggers=triggers,
        dependency_keys=envelope.dependency_keys(),
        recommended_action=_recommended_action(status),
        review_required=status == DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
    )


def _max_validity_status(
    left: DecisionValidityStatus,
    right: DecisionValidityStatus,
) -> DecisionValidityStatus:
    order = {
        DecisionValidityStatus.ACTIVE: 0,
        DecisionValidityStatus.WARNING: 1,
        DecisionValidityStatus.STALE: 2,
        DecisionValidityStatus.REQUIRES_HUMAN_REVIEW: 3,
        DecisionValidityStatus.SUPERSEDED: 4,
        DecisionValidityStatus.REVOKED: 5,
    }
    return right if order[right] > order[left] else left


def _summarize_governance_issues(issues: list[dict[str, object]]) -> dict[str, int]:
    blocker_count = 0
    warning_count = 0
    info_count = 0
    for issue in issues:
        severity = str(issue.get("severity", "")).strip().lower()
        if severity == "blocker":
            blocker_count += 1
        elif severity == "warning":
            warning_count += 1
        elif severity == "info":
            info_count += 1
    return {
        "blocker_count": blocker_count,
        "warning_count": warning_count,
        "info_count": info_count,
    }


def _has_governance_issue_code(issues: list[dict[str, object]], *, code: str) -> bool:
    for issue in issues:
        if str(issue.get("code", "")).strip() == code:
            return True
    return False


def _collect_contract_warnings(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> list[str]:
    warnings: list[str] = []
    link_report_ref = state.reports_index.get(REPORT_LINK_REPORT_REF)
    if link_report_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(link_report_ref.artifact_id))
        except _DECISION_PACKET_LOAD_ERRORS:
            payload = None
        if isinstance(payload, dict):
            for issue in payload.get("issues", []):
                if not isinstance(issue, dict):
                    continue
                if str(issue.get("severity", "")).strip().lower() != "warning":
                    continue
                code = issue.get("code")
                if isinstance(code, str):
                    _append_unique(warnings, code)

    compile_report_ref = state.reports_index.get(REPORT_COMPILE_REPORT_REF)
    if compile_report_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(compile_report_ref.artifact_id))
        except _DECISION_PACKET_LOAD_ERRORS:
            payload = None
        if isinstance(payload, dict):
            for note in payload.get("notes", []):
                if not isinstance(note, str):
                    continue
                normalized = _normalize_compile_warning(note)
                if normalized is not None:
                    _append_unique(warnings, normalized)

    return warnings


def _normalize_compile_warning(note: str) -> str | None:
    if note.startswith("link_warning:"):
        return note.split(":", 1)[1]
    if note.startswith("missing_runtime_mechanism_support:"):
        return note
    return None


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _load_resolved_fidelity_level(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> str | None:
    lowered_ir_ref = state.artifacts_index.get(ARTIFACT_LOWERED_IR_REF)
    if lowered_ir_ref is None:
        return None
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(lowered_ir_ref.artifact_id))
    except _DECISION_PACKET_LOAD_ERRORS:
        return None
    if not isinstance(payload, dict):
        return None
    fidelity = payload.get("policy_fidelity_level")
    return fidelity if isinstance(fidelity, str) else None


__all__ = [
    "_DECISION_PACKET_LOAD_ERRORS",
    "_append_unique",
    "_build_analysis_limits",
    "_build_decision_validity_baseline",
    "_build_decision_validity_envelope",
    "_collect_contract_warnings",
    "_decision_packet_degraded",
    "_has_governance_issue_code",
    "_load_resolved_fidelity_level",
    "_max_validity_status",
    "_missing_serious_decision_contracts",
    "_nested_status",
    "_normalize_compile_warning",
    "_phase5_validation_summary",
    "_record_decision_packet_degraded",
    "_record_decision_packet_section_degraded",
    "_should_run_phase5_publication_preflight",
    "_summarize_governance_issues",
]
