"""Persist durable control jobs, worker leases, and outbox events in SQLite/PostgreSQL."""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
import threading
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.control import (
    ControlFailureEnvelope,
    ControlJobKind,
    ControlJobResponse,
    ControlJobState,
    ControlQualityFailure,
    ControlQualityGate,
    ExecutionProfile,
    OperatorDiagnostic,
)
from polisyos.core.contracts.runtime import ApiMeta
from polisyos.runtime.http.services.control.response_shapes import (
    _operator_diagnostic_from_failure_payload,
    _operator_diagnostic_from_quality_payload,
    build_control_job_projection_shape,
)
from polisyos.runtime.http.services.scenario_heads import ScenarioHeadRecord
from polisyos.runtime.quality.diagnostic_events import (
    DiagnosticEvent,
    DiagnosticEventContractError,
    classify_duplicate_event,
)
from polisyos.runtime.quality.evidence_spine_handoff import (
    append_evidence_spine_handoff,
    control_plane_handoff,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    return None


def _job_event_topic(event_type: str) -> str:
    normalized = event_type.strip().lower()
    if normalized.startswith("job_"):
        normalized = normalized[4:]
    return f"control.job.{normalized}"


def _progress_carrier_ref(
    *,
    progress: Mapping[str, Any] | None,
    job_id: str,
    payload_ref: str | None = None,
) -> str:
    if isinstance(progress, Mapping):
        handoffs = progress.get("evidence_spine_handoffs")
        if isinstance(handoffs, list):
            for handoff in handoffs:
                if isinstance(handoff, Mapping):
                    carrier_ref = _string_or_none(handoff.get("carrier_ref"))
                    if carrier_ref is not None:
                        return carrier_ref
        carrier_ref = _string_or_none(progress.get("evidence_spine_carrier_ref"))
        if carrier_ref is not None:
            return carrier_ref
    return payload_ref or f"control-job:{job_id}:carrier"


_CONTROL_JOB_KINDS = frozenset({"workflow_run", "natural_language_run", "lex_pipeline"})
_CONTROL_JOB_STATES = frozenset({"pending", "running", "completed", "failed"})
_EXECUTION_PROFILES = frozenset({"dev", "research", "governed", "production"})
_SERIOUS_EXECUTION_PROFILES = frozenset({"research", "governed", "production"})

_RUNTIME_QUALITY_REF_GATES = (
    {
        "ref_key": "normative_applicability_report_ref",
        "gate_name": "normative_evidence_present",
        "stage": "lex",
        "layer": "lex",
        "pass_message": "Normative applicability evidence is present.",
    },
    {
        "ref_key": "fabric_retrieval_trace_ref",
        "gate_name": "fabric_retrieval_trace_present",
        "stage": "fabric",
        "layer": "fabric_retrieval",
        "pass_message": "Fabric source-selection evidence is present.",
    },
    {
        "ref_key": "foundry_method_report_ref",
        "gate_name": "foundry_method_evidence_present",
        "stage": "foundry",
        "layer": "foundry_methods",
        "pass_message": "Foundry method validity evidence is present.",
    },
    {
        "ref_key": "policy_grounding_matrix_ref",
        "gate_name": "policy_grounding_matrix_present",
        "stage": "policy_output",
        "layer": "scientist_policy_artifacts",
        "pass_message": "Policy grounding matrix is present.",
    },
    {
        "ref_key": "conflict_check_ref",
        "gate_name": "conflict_check_present",
        "stage": "lex",
        "layer": "normative_conflict",
        "pass_message": "Policy conflict check is present.",
    },
    {
        "ref_key": "causal_statistical_validity_report_ref",
        "gate_name": "causal_statistical_validity_present",
        "stage": "foundry",
        "layer": "foundry_causal_validity",
        "pass_message": "Causal/statistical validity benchmark evidence is present.",
    },
    {
        "ref_key": "replay_manifest_ref",
        "gate_name": "replay_manifest_present",
        "stage": "ops",
        "layer": "runtime_replay",
        "pass_message": "Deterministic replay manifest is present.",
    },
    {
        "ref_key": "drift_explanation_ref",
        "gate_name": "drift_explanation_present",
        "stage": "ops",
        "layer": "runtime_replay",
        "pass_message": "Replay drift explanation evidence is present.",
    },
    {
        "ref_key": "resilience_report_ref",
        "gate_name": "resilience_matrix_present",
        "stage": "ops",
        "layer": "runtime_resilience",
        "pass_message": "Load, soak, and resilience matrix evidence is present.",
    },
    {
        "ref_key": "human_review_calibration_report_ref",
        "gate_name": "human_review_calibration_present",
        "stage": "ops",
        "layer": "human_review_calibration",
        "pass_message": "Human-review calibration evidence is present.",
    },
    {
        "ref_key": "privacy_compliance_report_ref",
        "gate_name": "privacy_compliance_report_present",
        "stage": "ops",
        "layer": "privacy_compliance",
        "pass_message": "Privacy, licensing, and compliance evidence is present.",
    },
    {
        "ref_key": "decision_artifact_quality_report_ref",
        "gate_name": "decision_artifact_quality_present",
        "stage": "policy_output",
        "layer": "scientist_decision_artifact",
        "pass_message": "Decision-artifact quality evidence is present.",
    },
)
_SCORECARD_PROGRESS_KEYS = (
    "schema_version",
    "generated_at",
    "execution_status",
    "quality_status",
    "performance_status",
    "approval_state",
    "canary_kind",
    "job_id",
    "run_id",
    "quality_scorecard_ref",
    "quality_evidence_bundle_path",
    "overall_score",
    "stage_scores",
    "quality_gates",
    "blocking_quality_failures",
    "warnings",
    "approval_eligibility",
    "approval_decision",
    "approval_next_action",
    "approval_packet",
    "approval_packet_ref",
    "approval_ready",
    "approval_reasons",
    "evidence_refs",
    "override_evidence",
    "source_truth_conflicts",
)


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _operator_next_action(*, layer: str, retryable: bool) -> str:
    if layer == "llm_gateway":
        return (
            "Retry after provider recovery or check gateway credentials, base URL, "
            "model id, and provider status."
        )
    if layer == "fabric_materialization":
        return (
            "Inspect production_data paths, materialization refs, quality diagnostics, "
            "and lineage before retrying."
        )
    if retryable:
        return "Retry the job after the transient dependency or runtime condition recovers."
    return "Inspect the job progress, artifacts, and runtime logs before retrying."


def _derive_failure_envelope(record: ControlJobRecord) -> ControlFailureEnvelope | None:
    failure_payload = record.progress.get("failure")
    if isinstance(failure_payload, Mapping):
        code = _string_or_none(failure_payload.get("code")) or "control_job_failed"
        layer = _string_or_none(failure_payload.get("layer")) or "control_plane"
        phase = _string_or_none(failure_payload.get("phase")) or _string_or_none(
            record.progress.get("phase")
        )
        message = (
            _string_or_none(failure_payload.get("message"))
            or _string_or_none(record.error_message)
            or code
        )
        retryable = bool(failure_payload.get("retryable"))
        artifact_refs = failure_payload.get("artifact_refs")
        variant_failures = failure_payload.get("variant_failures")
        if not isinstance(variant_failures, list):
            variant_failures = failure_payload.get("variants")
        if not isinstance(variant_failures, list):
            variant_failures = []
        operator_diagnostic = _operator_diagnostic_from_failure_payload(
            failure_payload,
            authoritative_runtime_state=record.state,
            fallback_phase=phase,
            fallback_message=message,
            job_id=record.job_id,
        )
        return ControlFailureEnvelope(
            code=code,
            layer=layer,
            phase=phase,
            message=message,
            retryable=retryable,
            next_action=_string_or_none(failure_payload.get("next_action"))
            or _operator_next_action(layer=layer, retryable=retryable),
            model=_string_or_none(failure_payload.get("model")),
            provider=_string_or_none(failure_payload.get("provider")),
            run_id=_string_or_none(failure_payload.get("run_id")) or record.run_id,
            job_id=_string_or_none(failure_payload.get("job_id")) or record.job_id,
            artifact_refs=dict(artifact_refs) if isinstance(artifact_refs, Mapping) else {},
            variant_failures=[
                dict(item)
                for item in variant_failures
                if isinstance(item, Mapping)
            ],
            operator_diagnostic=operator_diagnostic,
        )
    if record.state != "failed" and not record.error_message:
        return None
    message = _string_or_none(record.error_message) or "Control job failed."
    phase = _string_or_none(record.progress.get("phase"))
    return ControlFailureEnvelope(
        code="control_job_failed",
        layer="control_plane",
        phase=phase,
        message=message,
        retryable=False,
        next_action=_operator_next_action(layer="control_plane", retryable=False),
        run_id=record.run_id,
        job_id=record.job_id,
        operator_diagnostic=_operator_diagnostic_from_failure_payload(
            {
                "code": "control_job_failed",
                "layer": "control_plane",
                "phase": phase,
                "message": message,
            },
            authoritative_runtime_state=record.state,
            fallback_phase=phase,
            fallback_message=message,
            job_id=record.job_id,
        ),
    )


def _status_or_none(value: Any) -> str | None:
    status = _string_or_none(value)
    if status is None:
        return None
    normalized = status.lower()
    status_aliases = {
        "passed": "pass",
        "success": "pass",
        "ok": "pass",
        "warning": "warn",
        "degraded": "warn",
        "failed": "fail",
        "error": "fail",
    }
    normalized = status_aliases.get(normalized, normalized)
    if normalized in {"pass", "warn", "fail"}:
        return normalized
    return status


def _quality_scorecard_payload(progress: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in ("quality_scorecard", "quality"):
        payload = progress.get(key)
        if isinstance(payload, Mapping):
            return payload
    if any(
        key in progress
        for key in ("quality_status", "quality_gates", "blocking_quality_failures")
    ):
        return progress
    return None


def _progress_with_quality_scorecard_summary(
    progress: dict[str, Any],
) -> dict[str, Any]:
    existing = progress.get("quality_scorecard")
    has_scorecard_fields = any(key in progress for key in _SCORECARD_PROGRESS_KEYS)
    if not isinstance(existing, Mapping) and not has_scorecard_fields:
        return progress

    normalized = deepcopy(progress)
    summary: dict[str, Any] = dict(existing) if isinstance(existing, Mapping) else {}
    for key in _SCORECARD_PROGRESS_KEYS:
        if key in normalized and key not in summary:
            summary[key] = deepcopy(normalized[key])

    evidence_refs = summary.get("evidence_refs")
    if not isinstance(evidence_refs, Mapping):
        evidence_refs = normalized.get("evidence_refs")
        if isinstance(evidence_refs, Mapping):
            summary["evidence_refs"] = dict(evidence_refs)

    if isinstance(evidence_refs, Mapping):
        scorecard_ref = _string_or_none(
            summary.get("quality_scorecard_ref") or evidence_refs.get("quality_scorecard")
        )
        if scorecard_ref is not None:
            summary["quality_scorecard_ref"] = scorecard_ref
            normalized.setdefault("quality_scorecard_ref", scorecard_ref)

    bundle_path = _string_or_none(
        summary.get("quality_evidence_bundle_path")
        or normalized.get("quality_evidence_bundle_path")
        or normalized.get("evidence_bundle_path")
    )
    if bundle_path is not None:
        summary["quality_evidence_bundle_path"] = bundle_path
        normalized.setdefault("quality_evidence_bundle_path", bundle_path)

    normalized["quality_scorecard"] = summary
    return normalized


def _completion_failure_message(progress: Mapping[str, Any]) -> str | None:
    """Return why this progress must fail instead of being marked completed."""

    authority_path = _string_or_none(progress.get("authority_path"))
    disposition = _string_or_none(progress.get("legacy_path_disposition"))
    authority_result = _string_or_none(progress.get("authority_result"))
    runtime_state = _string_or_none(progress.get("runtime_state"))
    progress_state = _string_or_none(progress.get("state"))
    status = _string_or_none(progress.get("status"))
    failure = progress.get("failure")
    if isinstance(failure, Mapping):
        failure_code = _string_or_none(failure.get("code"))
        failure_message = _string_or_none(failure.get("message"))
    else:
        failure_code = None
        failure_message = None
    if authority_path == "workflow_failure":
        return failure_message or failure_code or "workflow failure cannot complete cleanly"
    if disposition and disposition.startswith("blocked_workflow_failure"):
        return failure_message or failure_code or disposition
    if progress_state == "failed" and authority_result in {"repair_required", "blocked"}:
        return failure_message or failure_code or "failed progress cannot complete cleanly"
    if runtime_state == "blocked" and authority_result in {"repair_required", "blocked"}:
        return failure_message or failure_code or "blocked progress cannot complete cleanly"
    if status in {"fail", "failed", "error"} and authority_result in {
        None,
        "repair_required",
        "blocked",
    }:
        return failure_message or failure_code or "failed workflow status cannot complete cleanly"
    return None


def _coerce_quality_gate(
    payload: Any,
    *,
    record: ControlJobRecord,
    quality_scorecard_ref: str | None = None,
    quality_evidence_bundle_path: str | None = None,
) -> ControlQualityGate | None:
    if not isinstance(payload, Mapping):
        return None
    name = _string_or_none(payload.get("name"))
    status = _status_or_none(payload.get("status"))
    layer = _string_or_none(payload.get("layer")) or "quality_scorecard"
    message = _string_or_none(payload.get("message")) or name or "Quality gate."
    if not name or not status:
        return None
    return ControlQualityGate(
        name=name,
        code=_string_or_none(payload.get("code")),
        status=status,
        layer=layer,
        phase=_string_or_none(payload.get("phase")),
        message=message,
        evidence_ref=_string_or_none(payload.get("evidence_ref")),
        next_action=_string_or_none(payload.get("next_action")),
        next_diagnostic_command=_string_or_none(payload.get("next_diagnostic_command")),
        blocking=bool(payload.get("blocking", True)),
        operator_diagnostic=(
            _operator_diagnostic_from_quality_payload(
                payload,
                authoritative_runtime_state=record.state,
                fallback_phase=_string_or_none(payload.get("phase")),
                job_id=record.job_id,
                quality_scorecard_ref=quality_scorecard_ref,
                quality_evidence_bundle_path=quality_evidence_bundle_path,
            )
            if status == "fail" or bool(payload.get("operator_diagnostic"))
            else None
        ),
    )


def _coerce_quality_failure(
    payload: Any,
    *,
    record: ControlJobRecord,
    quality_scorecard_ref: str | None = None,
    quality_evidence_bundle_path: str | None = None,
) -> ControlQualityFailure | None:
    if not isinstance(payload, Mapping):
        return None
    gate = _string_or_none(payload.get("gate") or payload.get("name"))
    layer = _string_or_none(payload.get("layer")) or "quality_scorecard"
    message = _string_or_none(payload.get("message")) or gate or "Quality failure."
    if not gate:
        return None
    return ControlQualityFailure(
        gate=gate,
        code=_string_or_none(payload.get("code")),
        layer=layer,
        phase=_string_or_none(payload.get("phase")),
        message=message,
        evidence_ref=_string_or_none(payload.get("evidence_ref")),
        next_action=_string_or_none(payload.get("next_action")),
        next_diagnostic_command=_string_or_none(payload.get("next_diagnostic_command")),
        operator_diagnostic=_operator_diagnostic_from_quality_payload(
            payload,
            authoritative_runtime_state=record.state,
            fallback_phase=_string_or_none(payload.get("phase")),
            job_id=record.job_id,
            quality_scorecard_ref=quality_scorecard_ref,
            quality_evidence_bundle_path=quality_evidence_bundle_path,
        ),
    )


def _quality_evidence_missing_gate(record: ControlJobRecord) -> ControlQualityGate:
    payload = {
        "name": "quality_evidence_present",
        "code": "quality_evidence_missing",
        "layer": "quality_scorecard",
        "phase": "scorecard_projection",
        "message": "Completed control job is missing quality scorecard evidence.",
        "upstream_missing_input": "quality_scorecard",
        "downstream_impact": "Readiness, approval, and publication projections remain closed.",
        "next_diagnostic_command": (
            "uv run pytest tests/unit/runtime/http/test_control_plane_store.py -q"
        ),
    }
    return ControlQualityGate(
        name="quality_evidence_present",
        code="quality_evidence_missing",
        status="fail",
        layer="quality_scorecard",
        phase="scorecard_projection",
        message="Completed control job is missing quality scorecard evidence.",
        evidence_ref=None,
        next_action=(
            "Persist quality_status, quality_gates, and blocking_quality_failures "
            "before treating the run as production-successful."
        ),
        blocking=True,
        operator_diagnostic=_operator_diagnostic_from_quality_payload(
            payload,
            authoritative_runtime_state=record.state,
            fallback_phase="scorecard_projection",
            job_id=record.job_id,
        ),
    )


def _nested_get(payload: Any, key: str) -> Any:
    if isinstance(payload, Mapping):
        if key in payload:
            return payload[key]
        for value in payload.values():
            found = _nested_get(value, key)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _nested_get(value, key)
            if found is not None:
                return found
    return None


def _nested_runtime_quality_ref(payload: Any, key: str) -> Any:
    if isinstance(payload, Mapping):
        if key in payload:
            return payload[key]
        for payload_key, value in payload.items():
            if payload_key == "optional_runtime_quality_refs":
                continue
            found = _nested_runtime_quality_ref(value, key)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _nested_runtime_quality_ref(value, key)
            if found is not None:
                return found
    return None


def _runtime_quality_ref_optional_reason(record: ControlJobRecord, ref_key: str) -> str | None:
    optional_refs = _nested_get(record.progress, "optional_runtime_quality_refs")
    if not isinstance(optional_refs, Mapping) or ref_key not in optional_refs:
        return None
    return _string_or_none(optional_refs.get(ref_key)) or "Runtime ref is optional."


def _runtime_quality_ref_missing_gate(
    *,
    record: ControlJobRecord,
    ref_key: str,
    gate_name: str,
    layer: str,
    pass_message: str,
) -> ControlQualityGate | None:
    if _nested_runtime_quality_ref(record.progress, ref_key):
        return None

    optional_reason = _runtime_quality_ref_optional_reason(record, ref_key)
    serious = record.effective_execution_profile in _SERIOUS_EXECUTION_PROFILES
    status = "fail" if serious and optional_reason is None else "warn"
    code_suffix = "missing" if status == "fail" else "optional_missing"
    next_action = f"Persist {ref_key} from the owning runtime layer before production approval."
    if optional_reason is not None:
        next_action = f"Persist {ref_key} when this profile requires it. {optional_reason}"
    return ControlQualityGate(
        name=gate_name,
        code=f"{ref_key}_{code_suffix}",
        status=status,
        layer=layer,
        phase="quality_evidence",
        message=f"{pass_message} Runtime-owned {ref_key} is missing.",
        evidence_ref=None,
        next_action=next_action,
        blocking=status == "fail",
        operator_diagnostic=(
            _operator_diagnostic_from_quality_payload(
                {
                    "name": gate_name,
                    "code": f"{ref_key}_{code_suffix}",
                    "layer": layer,
                    "phase": "quality_evidence",
                    "message": f"{pass_message} Runtime-owned {ref_key} is missing.",
                    "owner": "team-runtime",
                    "upstream_missing_input": ref_key,
                    "downstream_impact": (
                        "Readiness, approval, and publication projections remain closed."
                    ),
                    "next_diagnostic_command": (
                        "uv run pytest tests/unit/runtime/quality/test_scorecard.py -q"
                    ),
                },
                authoritative_runtime_state=record.state,
                fallback_phase="quality_evidence",
                job_id=record.job_id,
            )
            if status == "fail"
            else None
        ),
    )


def _enforce_runtime_quality_refs(
    *,
    record: ControlJobRecord,
    gates: list[ControlQualityGate],
    failures: list[ControlQualityFailure],
) -> tuple[list[ControlQualityGate], list[ControlQualityFailure]]:
    if record.state != "completed":
        return gates, failures

    updated_gates = list(gates)
    by_name = {gate.name: index for index, gate in enumerate(updated_gates)}
    for spec in _RUNTIME_QUALITY_REF_GATES:
        gate_name = str(spec["gate_name"])
        current_gate = updated_gates[by_name[gate_name]] if gate_name in by_name else None
        if current_gate is not None and current_gate.status != "pass":
            continue
        missing_gate = _runtime_quality_ref_missing_gate(
            record=record,
            ref_key=str(spec["ref_key"]),
            gate_name=gate_name,
            layer=str(spec["layer"]),
            pass_message=str(spec["pass_message"]),
        )
        if missing_gate is None:
            continue
        if gate_name in by_name:
            updated_gates[by_name[gate_name]] = missing_gate
        else:
            by_name[gate_name] = len(updated_gates)
            updated_gates.append(missing_gate)

    updated_failures = _blocking_failures_from_gates(updated_gates)
    if not updated_failures:
        updated_failures = failures
    return updated_gates, updated_failures


def _blocking_failures_from_gates(gates: list[ControlQualityGate]) -> list[ControlQualityFailure]:
    return [
        ControlQualityFailure(
            gate=gate.name,
            code=gate.code or gate.name,
            layer=gate.layer,
            phase=gate.phase,
            message=gate.message,
            evidence_ref=gate.evidence_ref,
            next_action=gate.next_action,
            operator_diagnostic=gate.operator_diagnostic,
        )
        for gate in gates
        if gate.blocking and gate.status == "fail"
    ]


def _derive_quality_summary(
    record: ControlJobRecord,
) -> tuple[str | None, list[ControlQualityGate], list[ControlQualityFailure]]:
    scorecard = _quality_scorecard_payload(record.progress)
    if scorecard is not None:
        evidence_refs = scorecard.get("evidence_refs")
        if not isinstance(evidence_refs, Mapping):
            evidence_refs = {}
        quality_scorecard_ref = _string_or_none(
            scorecard.get("quality_scorecard_ref")
            or scorecard.get("scorecard_ref")
            or evidence_refs.get("quality_scorecard")
        )
        quality_evidence_bundle_path = _string_or_none(
            scorecard.get("quality_evidence_bundle_path")
            or scorecard.get("evidence_bundle_path")
            or record.progress.get("quality_evidence_bundle_path")
            or record.progress.get("evidence_bundle_path")
        )
        raw_gates = scorecard.get("quality_gates")
        raw_gates = raw_gates if isinstance(raw_gates, list) else []
        gates = [
            gate
            for gate in (
                _coerce_quality_gate(
                    item,
                    record=record,
                    quality_scorecard_ref=quality_scorecard_ref,
                    quality_evidence_bundle_path=quality_evidence_bundle_path,
                )
                for item in raw_gates
            )
            if gate is not None
        ]
        raw_failures = scorecard.get("blocking_quality_failures")
        raw_failures = raw_failures if isinstance(raw_failures, list) else []
        failures = [
            failure
            for failure in (
                _coerce_quality_failure(
                    item,
                    record=record,
                    quality_scorecard_ref=quality_scorecard_ref,
                    quality_evidence_bundle_path=quality_evidence_bundle_path,
                )
                for item in raw_failures
            )
            if failure is not None
        ]
        if not failures:
            failures = _blocking_failures_from_gates(gates)
        gates, failures = _enforce_runtime_quality_refs(
            record=record,
            gates=gates,
            failures=failures,
        )
        quality_status = _status_or_none(scorecard.get("quality_status"))
        if failures:
            quality_status = "fail"
        elif any(gate.status == "warn" for gate in gates):
            quality_status = "warn"
        elif quality_status is None:
            if failures:
                quality_status = "fail"
            elif any(gate.status == "warn" for gate in gates):
                quality_status = "warn"
            elif gates:
                quality_status = "pass"
        return quality_status, gates, failures

    if record.state == "completed":
        gate = _quality_evidence_missing_gate(record)
        return "fail", [gate], _blocking_failures_from_gates([gate])
    return None, [], []


def _derive_quality_refs(record: ControlJobRecord) -> tuple[str | None, str | None]:
    scorecard = _quality_scorecard_payload(record.progress)
    if scorecard is None:
        return None, None
    evidence_refs = scorecard.get("evidence_refs")
    if not isinstance(evidence_refs, Mapping):
        evidence_refs = {}
    quality_scorecard_ref = _string_or_none(
        scorecard.get("quality_scorecard_ref")
        or scorecard.get("scorecard_ref")
        or evidence_refs.get("quality_scorecard")
    )
    quality_evidence_bundle_path = _string_or_none(
        scorecard.get("quality_evidence_bundle_path")
        or scorecard.get("evidence_bundle_path")
        or record.progress.get("quality_evidence_bundle_path")
        or record.progress.get("evidence_bundle_path")
    )
    return quality_scorecard_ref, quality_evidence_bundle_path


def _derive_operator_diagnostic(
    *,
    record: ControlJobRecord,
    failure: ControlFailureEnvelope | None,
    quality_gates: list[ControlQualityGate],
    blocking_quality_failures: list[ControlQualityFailure],
) -> OperatorDiagnostic | None:
    raw_diagnostic = record.progress.get("operator_diagnostic")
    if isinstance(raw_diagnostic, Mapping):
        try:
            return OperatorDiagnostic.model_validate(raw_diagnostic)
        except Exception:
            raw_diagnostic = None
    if failure is not None and failure.operator_diagnostic is not None:
        return failure.operator_diagnostic
    for failure_item in blocking_quality_failures:
        if failure_item.operator_diagnostic is not None:
            return failure_item.operator_diagnostic
    for gate in quality_gates:
        if gate.operator_diagnostic is not None:
            return gate.operator_diagnostic
    return None


def _coerce_control_job_kind(value: Any) -> ControlJobKind:
    normalized = str(value or "").strip()
    if normalized not in _CONTROL_JOB_KINDS:
        raise ValueError(f"Unsupported control job kind: {normalized!r}")
    return cast(ControlJobKind, normalized)


def _coerce_control_job_state(value: Any) -> ControlJobState:
    normalized = str(value or "").strip()
    if normalized not in _CONTROL_JOB_STATES:
        raise ValueError(f"Unsupported control job state: {normalized!r}")
    return cast(ControlJobState, normalized)


def _coerce_execution_profile(value: Any) -> ExecutionProfile:
    normalized = str(value or "").strip()
    if normalized not in _EXECUTION_PROFILES:
        raise ValueError(f"Unsupported execution profile: {normalized!r}")
    return cast(ExecutionProfile, normalized)


def _coerce_optional_execution_profile(value: Any) -> ExecutionProfile | None:
    if value is None:
        return None
    return _coerce_execution_profile(value)


@dataclass(frozen=True)
class ControlJobRecord:
    """Represent one durable background job and its execution/profile metadata."""

    job_id: str
    kind: ControlJobKind
    state: ControlJobState
    run_id: str | None
    pipeline_id: str | None
    requested_execution_profile: ExecutionProfile | None
    effective_execution_profile: ExecutionProfile
    policy_flags: dict[str, Any]
    capability_manifest_ref: str | None
    payload_ref: str | None
    submitted_by: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    lease_owner: str | None
    lease_expires_at: datetime | None
    attempt: int
    error_message: str | None
    progress: dict[str, Any]

    def to_response(self, *, request_id: str | None = None) -> ControlJobResponse:
        """Convert a durable row snapshot into the public `ControlJobResponse` contract."""
        manifest_ref = None
        if self.capability_manifest_ref:
            manifest_ref = ArtifactRef(
                artifact_id=ArtifactID.model_validate(self.capability_manifest_ref),
                kind="runtime.capability_manifest",
                media_type="application/json",
            )
        quality_status, quality_gates, blocking_quality_failures = _derive_quality_summary(self)
        quality_scorecard_ref, quality_evidence_bundle_path = _derive_quality_refs(self)
        failure = _derive_failure_envelope(self)
        projection_shape = build_control_job_projection_shape(
            record=self,
            quality_status=quality_status,
            quality_scorecard_ref=quality_scorecard_ref,
            quality_gates=quality_gates,
            blocking_quality_failures=blocking_quality_failures,
        )
        projection_operator_diagnostic = projection_shape.pop("operator_diagnostic", None)
        operator_diagnostic = projection_operator_diagnostic or _derive_operator_diagnostic(
            record=self,
            failure=failure,
            quality_gates=quality_gates,
            blocking_quality_failures=blocking_quality_failures,
        )
        return ControlJobResponse(
            meta=ApiMeta(request_id=request_id or "control-job"),
            job_id=self.job_id,
            kind=self.kind,
            state=self.state,
            run_id=self.run_id,
            pipeline_id=self.pipeline_id,
            requested_execution_profile=self.requested_execution_profile,
            effective_execution_profile=self.effective_execution_profile,
            capability_manifest_ref=manifest_ref,
            submitted_at=self.created_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
            error_message=self.error_message,
            failure=failure,
            execution_status=self.state,
            quality_status=quality_status,
            quality_scorecard_ref=quality_scorecard_ref,
            **projection_shape,
            quality_evidence_bundle_path=quality_evidence_bundle_path,
            quality_gates=quality_gates,
            blocking_quality_failures=blocking_quality_failures,
            operator_diagnostic=operator_diagnostic,
            progress=dict(self.progress),
        )


@dataclass(frozen=True)
class ControlWorkerLeaseRecord:
    """Report one worker heartbeat/lease row exposed by control-plane diagnostics."""

    worker_id: str
    state: str
    backend: str | None
    active_job_id: str | None
    metadata: dict[str, Any]
    heartbeat_at: datetime
    lease_expires_at: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ControlOutboxRecord:
    """Represent one deduplicated durable outbox event awaiting publication."""

    event_id: str
    topic: str
    event_key: str | None
    state: str
    job_id: str | None
    run_id: str | None
    payload: dict[str, Any]
    created_at: datetime
    published_at: datetime | None
    attempt: int
    error_message: str | None


@dataclass(frozen=True)
class ControlDiagnosticEventRecord:
    """Represent one durable append-only runtime diagnostic event record."""

    row_id: int
    event: DiagnosticEvent
    payload_ref: str | None
    payload_inline: dict[str, Any] | None
    payload_sha256: str | None
    created_at: datetime


@dataclass(frozen=True)
class ControlDeadLetterRecord:
    """Represent one terminally failed control job requiring operator review."""

    job_id: str
    kind: ControlJobKind
    run_id: str | None
    pipeline_id: str | None
    attempt: int
    error_message: str
    failed_at: datetime
    acknowledged_at: datetime | None
    acknowledged_by: str | None


class ControlPlaneStore:
    """Store control jobs and leases with a backend-specific SQL schema.

    The store appends job lifecycle events, maintains idempotent outbox rows,
    and returns domain records consumed by `ControlPlaneService` and
    `/api/v1/control/*` routes.
    """

    def __init__(
        self,
        *,
        backend: str,
        sqlite_path: str | Path,
        postgres_dsn: str | None = None,
    ) -> None:
        self.backend = backend.strip().lower()
        self._sqlite_path = Path(sqlite_path)
        self._postgres_dsn = postgres_dsn
        self._lock = threading.RLock()
        self._sqlite_timeout_seconds = max(
            float(os.getenv("POLISYOS_CONTROL_SQLITE_TIMEOUT_SECONDS", "0.5")),
            0.05,
        )
        if self.backend == "sqlite":
            self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            self._ensure_sqlite_schema()
        elif self.backend == "postgres":
            if not self._postgres_dsn:
                raise RuntimeError("PostgreSQL control-plane store requires a DSN")
            self._ensure_postgres_schema()
        else:
            raise RuntimeError(f"Unsupported control-plane store backend: {backend!r}")

    def get_scenario_head(self, scenario_id: str) -> ScenarioHeadRecord | None:
        """Return the durable authority row for one scenario id."""
        row = self._fetchone(
            """
            SELECT scenario_id, baseline_run_id, revision, artifact_ref,
                   manifest_hash, updated_at
            FROM runtime_scenario_heads
            WHERE scenario_id = ?
            """,
            (scenario_id,),
        )
        return self._row_to_scenario_head(row) if row is not None else None

    def list_scenario_heads(
        self,
        *,
        baseline_run_id: str | None = None,
    ) -> list[ScenarioHeadRecord]:
        """List durable scenario authority rows in deterministic id order."""
        if baseline_run_id is None:
            rows = self._fetchall(
                """
                SELECT scenario_id, baseline_run_id, revision, artifact_ref,
                       manifest_hash, updated_at
                FROM runtime_scenario_heads
                ORDER BY scenario_id ASC
                """,
                (),
            )
        else:
            rows = self._fetchall(
                """
                SELECT scenario_id, baseline_run_id, revision, artifact_ref,
                       manifest_hash, updated_at
                FROM runtime_scenario_heads
                WHERE baseline_run_id = ?
                ORDER BY scenario_id ASC
                """,
                (baseline_run_id,),
            )
        return [self._row_to_scenario_head(row) for row in rows]

    def compare_and_set_scenario_head(
        self,
        *,
        scenario_id: str,
        baseline_run_id: str,
        expected_revision: int,
        new_revision: int,
        artifact_ref: str,
        manifest_hash: str,
    ) -> bool:
        """Atomically create or advance one scenario authority row.

        Revision zero is an insert-only expectation. Later revisions update only
        the exact existing baseline binding and revision. Every accepted write
        advances the head by exactly one revision.
        """
        if (
            type(expected_revision) is not int
            or type(new_revision) is not int
            or expected_revision < 0
            or new_revision != expected_revision + 1
        ):
            return False

        updated_at = _iso(_utc_now())
        if expected_revision == 0:
            sql = """
                INSERT INTO runtime_scenario_heads (
                    scenario_id, baseline_run_id, revision, artifact_ref,
                    manifest_hash, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (scenario_id) DO NOTHING
            """
            params = (
                scenario_id,
                baseline_run_id,
                new_revision,
                artifact_ref,
                manifest_hash,
                updated_at,
            )
        else:
            sql = """
                UPDATE runtime_scenario_heads
                SET revision = ?, artifact_ref = ?, manifest_hash = ?, updated_at = ?
                WHERE scenario_id = ?
                  AND baseline_run_id = ?
                  AND revision = ?
            """
            params = (
                new_revision,
                artifact_ref,
                manifest_hash,
                updated_at,
                scenario_id,
                baseline_run_id,
                expected_revision,
            )

        if self.backend == "sqlite":
            with self._lock:
                with self._sqlite_connection() as conn:
                    cursor = conn.execute(sql, params)
                    conn.commit()
                    return cursor.rowcount == 1
        with self._postgres_cursor() as cur:
            cur.execute(self._translate_sql(sql), params)
            return cur.rowcount == 1

    def create_job(
        self,
        *,
        job_id: str,
        kind: ControlJobKind,
        run_id: str | None,
        pipeline_id: str | None,
        requested_execution_profile: ExecutionProfile | None,
        effective_execution_profile: ExecutionProfile,
        policy_flags: dict[str, Any],
        capability_manifest_ref: str | None,
        payload_ref: str | None,
        submitted_by: str | None,
    ) -> ControlJobRecord:
        """Insert a pending job, initialize progress/event rows, and enqueue an event."""
        created_at = _utc_now()
        progress: dict[str, Any] = append_evidence_spine_handoff(
            {},
            control_plane_handoff(
                handoff_kind="nl_request_creation",
                job_id=job_id,
                producer_ref="runtime.api.nl_request",
                consumer_ref="runtime.control_plane_store",
                input_refs=tuple(
                    ref
                    for ref in (payload_ref, capability_manifest_ref, "control.request")
                    if ref
                ),
                output_refs=(f"control-job:{job_id}",),
                carrier_ref=payload_ref,
                parent_spine_ref=payload_ref or f"control-job:{job_id}:carrier",
            ),
        )
        sql = """
            INSERT INTO control_jobs (
                job_id, job_kind, state, run_id, pipeline_id,
                requested_profile, effective_profile, policy_flags_json,
                capability_manifest_ref, payload_ref, submitted_by,
                created_at, started_at, finished_at,
                lease_owner, lease_expires_at, attempt, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, 0, NULL)
        """
        params = (
            job_id,
            kind,
            "pending",
            run_id,
            pipeline_id,
            requested_execution_profile,
            effective_execution_profile,
            json.dumps(policy_flags, sort_keys=True),
            capability_manifest_ref,
            payload_ref,
            submitted_by,
            _iso(created_at),
        )
        self._execute(sql, params)
        self.upsert_progress(job_id=job_id, progress=progress)
        self.append_event(job_id=job_id, event_type="job_created", payload={"state": "pending"})
        record = self.get_job(job_id)
        if record is None:
            raise RuntimeError(f"Failed to persist control job {job_id}")
        self._emit_job_outbox_event(
            record=record,
            event_type="job_created",
            payload={"state": "pending"},
        )
        return record

    def get_job(self, job_id: str) -> ControlJobRecord | None:
        """Return one job record by ID or `None` when absent."""
        row = self._fetchone(
            """
            SELECT
                j.job_id,
                j.job_kind,
                j.state,
                j.run_id,
                j.pipeline_id,
                j.requested_profile,
                j.effective_profile,
                j.policy_flags_json,
                j.capability_manifest_ref,
                j.payload_ref,
                j.submitted_by,
                j.created_at,
                j.started_at,
                j.finished_at,
                j.lease_owner,
                j.lease_expires_at,
                j.attempt,
                j.error_message,
                p.progress_json
            FROM control_jobs j
            LEFT JOIN control_job_progress p ON p.job_id = j.job_id
            WHERE j.job_id = ?
            """,
            (job_id,),
        )
        if row is None:
            return None
        return self._row_to_record(row)

    def get_job_by_pipeline(self, pipeline_id: str) -> ControlJobRecord | None:
        """Return the job record associated with one Lex pipeline ID."""
        row = self._fetchone(
            """
            SELECT
                j.job_id,
                j.job_kind,
                j.state,
                j.run_id,
                j.pipeline_id,
                j.requested_profile,
                j.effective_profile,
                j.policy_flags_json,
                j.capability_manifest_ref,
                j.payload_ref,
                j.submitted_by,
                j.created_at,
                j.started_at,
                j.finished_at,
                j.lease_owner,
                j.lease_expires_at,
                j.attempt,
                j.error_message,
                p.progress_json
            FROM control_jobs j
            LEFT JOIN control_job_progress p ON p.job_id = j.job_id
            WHERE j.pipeline_id = ?
            """,
            (pipeline_id,),
        )
        if row is None:
            return None
        return self._row_to_record(row)

    def get_latest_job_by_run(self, run_id: str) -> ControlJobRecord | None:
        """Return the newest durable control job associated with one runtime run."""
        row = self._fetchone(
            """
            SELECT
                j.job_id,
                j.job_kind,
                j.state,
                j.run_id,
                j.pipeline_id,
                j.requested_profile,
                j.effective_profile,
                j.policy_flags_json,
                j.capability_manifest_ref,
                j.payload_ref,
                j.submitted_by,
                j.created_at,
                j.started_at,
                j.finished_at,
                j.lease_owner,
                j.lease_expires_at,
                j.attempt,
                j.error_message,
                p.progress_json
            FROM control_jobs j
            LEFT JOIN control_job_progress p ON p.job_id = j.job_id
            WHERE j.run_id = ?
            ORDER BY (j.finished_at IS NULL) ASC, j.finished_at DESC, j.created_at DESC
            LIMIT 1
            """,
            (run_id,),
        )
        if row is None:
            return None
        return self._row_to_record(row)

    def append_event(self, *, job_id: str, event_type: str, payload: dict[str, Any]) -> None:
        """Append one immutable job lifecycle/progress event row."""
        self._execute(
            """
            INSERT INTO control_job_events (job_id, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (job_id, event_type, json.dumps(payload, sort_keys=True), _iso(_utc_now())),
        )

    def list_job_state_transitions(self, job_id: str) -> list[str]:
        """Return observed lifecycle states from the append-only job event log."""

        rows = self._fetchall(
            """
            SELECT payload_json
            FROM control_job_events
            WHERE job_id = ?
            ORDER BY event_id ASC
            """,
            (job_id,),
        )
        transitions: list[str] = []
        for row in rows:
            raw = row[0] if not isinstance(row, Mapping) else row.get("payload_json")
            try:
                payload = json.loads(str(raw or "{}"))
            except json.JSONDecodeError:
                continue
            state = str(payload.get("state") or "").strip()
            if state and (not transitions or transitions[-1] != state):
                transitions.append(state)
        return transitions

    def upsert_progress(self, *, job_id: str, progress: dict[str, Any]) -> None:
        """Create or replace the latest JSON progress snapshot for one job."""
        now = _iso(_utc_now())
        normalized_progress = _progress_with_quality_scorecard_summary(progress)
        progress_json = json.dumps(normalized_progress, sort_keys=True)
        if self.backend == "sqlite":
            self._execute(
                """
                INSERT INTO control_job_progress (job_id, progress_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    progress_json = excluded.progress_json,
                    updated_at = excluded.updated_at
                """,
                (job_id, progress_json, now),
            )
            return
        self._execute(
            """
            INSERT INTO control_job_progress (job_id, progress_json, updated_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (job_id) DO UPDATE SET
                progress_json = EXCLUDED.progress_json,
                updated_at = EXCLUDED.updated_at
            """,
            (job_id, progress_json, now),
        )

    def lease_next_job(
        self,
        *,
        worker_id: str,
        lease_seconds: int = 60,
    ) -> ControlJobRecord | None:
        """Lease the next pending/expired job for one worker and emit a running event."""
        if self.backend == "sqlite":
            record = self._lease_next_sqlite(worker_id=worker_id, lease_seconds=lease_seconds)
        else:
            record = self._lease_next_postgres(worker_id=worker_id, lease_seconds=lease_seconds)
        if record is not None:
            progress = append_evidence_spine_handoff(
                record.progress,
                control_plane_handoff(
                    handoff_kind="control_plane_job_lease",
                    job_id=record.job_id,
                    producer_ref="runtime.control_plane_store",
                    consumer_ref=f"runtime.control_worker:{worker_id}",
                    input_refs=(f"control-job:{record.job_id}",),
                    output_refs=(f"control-job:{record.job_id}:lease:{record.attempt}",),
                    carrier_ref=_progress_carrier_ref(
                        progress=record.progress,
                        job_id=record.job_id,
                        payload_ref=record.payload_ref,
                    ),
                ),
            )
            self.upsert_progress(job_id=record.job_id, progress=progress)
            record = self.get_job(record.job_id) or record
            payload = {
                "state": "running",
                "lease_owner": worker_id,
                "lease_expires_at": _iso(record.lease_expires_at),
            }
            self.append_event(job_id=record.job_id, event_type="job_running", payload=payload)
            self._emit_job_outbox_event(
                record=record,
                event_type="job_running",
                payload=payload,
            )
        return record

    def mark_running(self, *, job_id: str, worker_id: str, lease_seconds: int = 60) -> None:
        """Force a specific job into `running` state and assign a lease owner."""
        now = _utc_now()
        lease_expires_at = now + timedelta(seconds=max(lease_seconds, 1))
        self._execute(
            """
            UPDATE control_jobs
            SET state = ?, started_at = COALESCE(started_at, ?),
                lease_owner = ?, lease_expires_at = ?, attempt = attempt + 1
            WHERE job_id = ?
            """,
            ("running", _iso(now), worker_id, _iso(lease_expires_at), job_id),
        )
        self.append_event(
            job_id=job_id,
            event_type="job_running",
            payload={
                "state": "running",
                "lease_owner": worker_id,
                "lease_expires_at": _iso(lease_expires_at),
            },
        )
        record = self.get_job(job_id)
        if record is not None:
            self._emit_job_outbox_event(
                record=record,
                event_type="job_running",
                payload={
                    "state": "running",
                    "lease_owner": worker_id,
                    "lease_expires_at": _iso(lease_expires_at),
                },
            )

    def complete_job(
        self,
        *,
        job_id: str,
        run_id: str | None = None,
        pipeline_id: str | None = None,
        capability_manifest_ref: str | None = None,
        progress: dict[str, Any] | None = None,
    ) -> None:
        """Mark one job completed, clear lease/error state, and emit completion events."""
        now = _utc_now()
        if progress is not None:
            progress = _progress_with_quality_scorecard_summary(progress)
            completion_failure_message = _completion_failure_message(progress)
            if completion_failure_message is not None:
                self.fail_job(
                    job_id=job_id,
                    error_message=completion_failure_message,
                    capability_manifest_ref=capability_manifest_ref,
                    progress=progress,
                )
                return
            self.upsert_progress(job_id=job_id, progress=progress)
        self._execute(
            """
            UPDATE control_jobs
            SET state = ?, run_id = COALESCE(?, run_id), pipeline_id = COALESCE(?, pipeline_id),
                capability_manifest_ref = COALESCE(?, capability_manifest_ref),
                finished_at = ?, lease_owner = NULL, lease_expires_at = NULL, error_message = NULL
            WHERE job_id = ?
            """,
            ("completed", run_id, pipeline_id, capability_manifest_ref, _iso(now), job_id),
        )
        self.append_event(job_id=job_id, event_type="job_completed", payload={"state": "completed"})
        record = self.get_job(job_id)
        if record is not None:
            self._emit_job_outbox_event(
                record=record,
                event_type="job_completed",
                payload={"state": "completed", "progress": dict(progress or record.progress)},
            )

    def fail_job(
        self,
        *,
        job_id: str,
        error_message: str,
        capability_manifest_ref: str | None = None,
        progress: dict[str, Any] | None = None,
    ) -> None:
        """Mark one job failed, persist a truncated error message, and emit failure events."""
        now = _utc_now()
        if progress is not None:
            progress = _progress_with_quality_scorecard_summary(progress)
        self._execute(
            """
            UPDATE control_jobs
            SET state = ?, capability_manifest_ref = COALESCE(?, capability_manifest_ref),
                finished_at = ?, lease_owner = NULL, lease_expires_at = NULL, error_message = ?
            WHERE job_id = ?
            """,
            ("failed", capability_manifest_ref, _iso(now), error_message[:2000], job_id),
        )
        if progress is not None:
            self.upsert_progress(job_id=job_id, progress=progress)
        self.append_event(
            job_id=job_id,
            event_type="job_failed",
            payload={"state": "failed", "error_message": error_message[:500]},
        )
        record = self.get_job(job_id)
        if record is not None:
            self._enqueue_dead_letter_job(record=record, failed_at=now)
            self._emit_job_outbox_event(
                record=record,
                event_type="job_failed",
                payload={
                    "state": "failed",
                    "error_message": error_message[:500],
                    "progress": dict(progress or record.progress),
                },
            )

    def list_dead_letter_jobs(
        self,
        *,
        acknowledged: bool | None = False,
        limit: int = 100,
    ) -> list[ControlDeadLetterRecord]:
        """List terminal failed jobs awaiting or already carrying operator acknowledgement."""
        limit = max(1, min(int(limit), 500))
        where = ""
        params: tuple[Any, ...] = (limit,)
        if acknowledged is True:
            where = "WHERE acknowledged_at IS NOT NULL"
        elif acknowledged is False:
            where = "WHERE acknowledged_at IS NULL"
        rows = self._fetchall(
            f"""
            SELECT job_id, job_kind, run_id, pipeline_id, attempt, error_message,
                   failed_at, acknowledged_at, acknowledged_by
            FROM control_dead_letter_jobs
            {where}
            ORDER BY failed_at ASC
            LIMIT ?
            """,
            params,
        )
        return [self._row_to_dead_letter_record(row) for row in rows]

    def acknowledge_dead_letter_job(self, *, job_id: str, acknowledged_by: str) -> None:
        """Mark a dead-lettered job as operator-acknowledged."""
        now = _utc_now()
        self._execute(
            """
            UPDATE control_dead_letter_jobs
            SET acknowledged_at = ?, acknowledged_by = ?
            WHERE job_id = ?
            """,
            (_iso(now), acknowledged_by[:256], job_id),
        )

    def update_manifest_ref(self, *, job_id: str, capability_manifest_ref: str) -> None:
        """Update the persisted capability-manifest ref for an existing job."""
        self._execute(
            "UPDATE control_jobs SET capability_manifest_ref = ? WHERE job_id = ?",
            (capability_manifest_ref, job_id),
        )

    def update_progress_state(
        self,
        *,
        job_id: str,
        state: str,
        progress: dict[str, Any],
        error_message: str | None = None,
    ) -> None:
        """Update progress/error state and emit a `job_progress` event/outbox row."""
        progress = _progress_with_quality_scorecard_summary(progress)
        existing = self.get_job(job_id)
        progress = append_evidence_spine_handoff(
            progress,
            control_plane_handoff(
                handoff_kind="workflow_state_persistence",
                job_id=job_id,
                producer_ref="runtime.control_plane_store",
                consumer_ref="runtime.control_progress_readers",
                input_refs=(f"control-job:{job_id}",),
                output_refs=(f"control-job:{job_id}:progress",),
                carrier_ref=_progress_carrier_ref(
                    progress=(existing.progress if existing is not None else progress),
                    job_id=job_id,
                    payload_ref=(existing.payload_ref if existing is not None else None),
                ),
            ),
        )
        self.upsert_progress(job_id=job_id, progress=progress)
        self._execute(
            "UPDATE control_jobs SET error_message = COALESCE(?, error_message) WHERE job_id = ?",
            (error_message, job_id),
        )
        self.append_event(
            job_id=job_id, event_type="job_progress", payload={"state": state, **progress}
        )
        record = self.get_job(job_id)
        if record is not None:
            self._emit_job_outbox_event(
                record=record,
                event_type="job_progress",
                payload={"state": state, **progress},
            )

    def renew_job_lease(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_seconds: int = 60,
    ) -> None:
        """Extend a running job lease when the heartbeat still matches `worker_id`."""
        lease_expires_at = _utc_now() + timedelta(seconds=max(lease_seconds, 1))
        self._execute(
            """
            UPDATE control_jobs
            SET lease_expires_at = ?
            WHERE job_id = ? AND state = 'running' AND lease_owner = ?
            """,
            (_iso(lease_expires_at), job_id, worker_id),
        )

    def heartbeat_worker(
        self,
        *,
        worker_id: str,
        state: str,
        lease_seconds: int,
        backend: str | None = None,
        active_job_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Upsert the worker heartbeat row and lease expiration metadata."""
        now = _utc_now()
        lease_expires_at = now + timedelta(seconds=max(lease_seconds, 1))
        metadata_json = json.dumps(metadata or {}, sort_keys=True)
        if self.backend == "sqlite":
            self._execute(
                """
                INSERT INTO control_worker_leases (
                    worker_id, state, backend, active_job_id, metadata_json,
                    heartbeat_at, lease_expires_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(worker_id) DO UPDATE SET
                    state = excluded.state,
                    backend = excluded.backend,
                    active_job_id = excluded.active_job_id,
                    metadata_json = excluded.metadata_json,
                    heartbeat_at = excluded.heartbeat_at,
                    lease_expires_at = excluded.lease_expires_at,
                    updated_at = excluded.updated_at
                """,
                (
                    worker_id,
                    state,
                    backend,
                    active_job_id,
                    metadata_json,
                    _iso(now),
                    _iso(lease_expires_at),
                    _iso(now),
                    _iso(now),
                ),
            )
            return
        self._execute(
            """
            INSERT INTO control_worker_leases (
                worker_id, state, backend, active_job_id, metadata_json,
                heartbeat_at, lease_expires_at, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (worker_id) DO UPDATE SET
                state = EXCLUDED.state,
                backend = EXCLUDED.backend,
                active_job_id = EXCLUDED.active_job_id,
                metadata_json = EXCLUDED.metadata_json,
                heartbeat_at = EXCLUDED.heartbeat_at,
                lease_expires_at = EXCLUDED.lease_expires_at,
                updated_at = EXCLUDED.updated_at
            """,
            (
                worker_id,
                state,
                backend,
                active_job_id,
                metadata_json,
                _iso(now),
                _iso(lease_expires_at),
                _iso(now),
                _iso(now),
            ),
        )

    def release_worker(self, *, worker_id: str, state: str = "stopped") -> None:
        """Mark a worker lease inactive and clear its active job binding."""
        now = _utc_now()
        self._execute(
            """
            UPDATE control_worker_leases
            SET state = ?, active_job_id = NULL, heartbeat_at = ?,
                lease_expires_at = ?, updated_at = ?
            WHERE worker_id = ?
            """,
            (state, _iso(now), _iso(now), _iso(now), worker_id),
        )

    def list_worker_leases(self, *, active_only: bool = True) -> list[ControlWorkerLeaseRecord]:
        """List worker leases, optionally filtering to non-expired active leases."""
        sql = """
            SELECT
                worker_id,
                state,
                backend,
                active_job_id,
                metadata_json,
                heartbeat_at,
                lease_expires_at,
                created_at,
                updated_at
            FROM control_worker_leases
        """
        params: tuple[Any, ...] = ()
        if active_only:
            sql += " WHERE lease_expires_at IS NOT NULL AND lease_expires_at > ?"
            params = (_iso(_utc_now()),)
        sql += " ORDER BY worker_id ASC"
        rows = self._fetchall(sql, params)
        return [self._row_to_worker_lease(row) for row in rows]

    def enqueue_outbox_event(
        self,
        *,
        topic: str,
        payload: dict[str, Any],
        job_id: str | None = None,
        run_id: str | None = None,
        event_key: str | None = None,
    ) -> ControlOutboxRecord:
        """Insert a deduplicated pending outbox event keyed by `(topic, event_key)`."""
        if event_key:
            existing = self._get_outbox_event_by_key(topic=topic, event_key=event_key)
            if existing is not None:
                return existing
        event_id = f"outbox_{uuid.uuid4().hex[:16]}"
        created_at = _utc_now()
        self._execute(
            """
            INSERT INTO control_outbox_events (
                event_id, topic, event_key, state, job_id, run_id,
                payload_json, created_at, published_at, attempt, error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 0, NULL)
            """,
            (
                event_id,
                topic,
                event_key,
                "pending",
                job_id,
                run_id,
                json.dumps(payload, sort_keys=True),
                _iso(created_at),
            ),
        )
        record = self.get_outbox_event(event_id)
        if record is None:
            raise RuntimeError(f"Failed to persist control outbox event {event_id}")
        return record

    def get_outbox_event(self, event_id: str) -> ControlOutboxRecord | None:
        """Return one outbox event row by ID."""
        row = self._fetchone(
            """
            SELECT
                event_id,
                topic,
                event_key,
                state,
                job_id,
                run_id,
                payload_json,
                created_at,
                published_at,
                attempt,
                error_message
            FROM control_outbox_events
            WHERE event_id = ?
            """,
            (event_id,),
        )
        if row is None:
            return None
        return self._row_to_outbox_record(row)

    def list_outbox_events(
        self,
        *,
        state: str | None = "pending",
        limit: int = 100,
    ) -> list[ControlOutboxRecord]:
        """List outbox events by state in creation order with a hard page-size cap."""
        page_size = max(1, min(int(limit), 500))
        sql = """
            SELECT
                event_id,
                topic,
                event_key,
                state,
                job_id,
                run_id,
                payload_json,
                created_at,
                published_at,
                attempt,
                error_message
            FROM control_outbox_events
        """
        params: tuple[Any, ...]
        if state is not None:
            sql += " WHERE state = ?"
            params = (state, page_size)
            sql += " ORDER BY created_at ASC LIMIT ?"
        else:
            params = (page_size,)
            sql += " ORDER BY created_at ASC LIMIT ?"
        rows = self._fetchall(sql, params)
        return [self._row_to_outbox_record(row) for row in rows]

    def mark_outbox_published(self, *, event_id: str) -> None:
        """Mark one outbox event published and increment its attempt counter."""
        now = _utc_now()
        self._execute(
            """
            UPDATE control_outbox_events
            SET state = ?, published_at = ?, attempt = attempt + 1, error_message = NULL
            WHERE event_id = ?
            """,
            ("published", _iso(now), event_id),
        )

    def _get_outbox_event_by_key(self, *, topic: str, event_key: str) -> ControlOutboxRecord | None:
        row = self._fetchone(
            """
            SELECT
                event_id,
                topic,
                event_key,
                state,
                job_id,
                run_id,
                payload_json,
                created_at,
                published_at,
                attempt,
                error_message
            FROM control_outbox_events
            WHERE topic = ? AND event_key = ?
            """,
            (topic, event_key),
        )
        if row is None:
            return None
        return self._row_to_outbox_record(row)

    def append_diagnostic_event(
        self,
        *,
        event: DiagnosticEvent | Mapping[str, Any],
        payload_ref: str | None = None,
        payload_inline: dict[str, Any] | None = None,
        payload_sha256: str | None = None,
    ) -> ControlDiagnosticEventRecord:
        """Append one durable runtime diagnostic authority event."""

        diagnostic_event = (
            event if isinstance(event, DiagnosticEvent) else DiagnosticEvent.model_validate(event)
        )
        if (
            payload_ref
            and diagnostic_event.payload_ref
            and payload_ref != diagnostic_event.payload_ref
        ):
            raise DiagnosticEventContractError(
                "authority_payload_mismatch",
                "Diagnostic event payload_ref does not match stored payload_ref.",
                details={
                    "event_id": diagnostic_event.event_id,
                    "event_payload_ref": diagnostic_event.payload_ref,
                    "record_payload_ref": payload_ref,
                },
            )
        stored_payload_ref = payload_ref or diagnostic_event.payload_ref
        existing = self.list_diagnostic_events(
            event_id=diagnostic_event.event_id,
            limit=100,
        )
        duplicate = classify_duplicate_event(
            [record.event for record in existing],
            diagnostic_event,
        )
        if duplicate.status == "idempotent_duplicate":
            existing_payload_sha256 = existing[0].payload_sha256
            if existing_payload_sha256 != payload_sha256:
                raise DiagnosticEventContractError(
                    "authority_event_collision",
                    "Same diagnostic event id points at different payload hashes.",
                    details={
                        "event_id": diagnostic_event.event_id,
                        "existing_payload_sha256": existing_payload_sha256,
                        "incoming_payload_sha256": payload_sha256,
                    },
                )
            return existing[0]

        created_at = _utc_now()
        self._execute(
            """
            INSERT INTO control_diagnostic_events (
                event_id, event_type, run_id, job_id, trace_id, span_id,
                event_json, payload_ref, payload_inline_json, payload_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                diagnostic_event.event_id,
                diagnostic_event.event_type,
                diagnostic_event.run_id,
                diagnostic_event.job_id,
                diagnostic_event.trace_id,
                diagnostic_event.span_id,
                json.dumps(diagnostic_event.model_dump(mode="json"), sort_keys=True),
                stored_payload_ref,
                (
                    json.dumps(payload_inline, sort_keys=True)
                    if payload_inline is not None
                    else None
                ),
                payload_sha256,
                _iso(created_at),
            ),
        )
        record = self.list_diagnostic_events(
            event_id=diagnostic_event.event_id,
            limit=1,
        )
        if not record:
            raise RuntimeError(
                f"Failed to persist diagnostic event {diagnostic_event.event_id}"
            )
        return record[0]

    def list_diagnostic_events(
        self,
        *,
        event_id: str | None = None,
        run_id: str | None = None,
        job_id: str | None = None,
        limit: int = 500,
    ) -> list[ControlDiagnosticEventRecord]:
        """List durable diagnostic events in append order."""

        page_size = max(1, min(int(limit), 1000))
        clauses: list[str] = []
        params_list: list[Any] = []
        if event_id is not None:
            clauses.append("event_id = ?")
            params_list.append(event_id)
        if run_id is not None:
            clauses.append("run_id = ?")
            params_list.append(run_id)
        if job_id is not None:
            clauses.append("job_id = ?")
            params_list.append(job_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._fetchall(
            f"""
            SELECT
                row_id,
                event_json,
                payload_ref,
                payload_inline_json,
                payload_sha256,
                created_at
            FROM control_diagnostic_events
            {where}
            ORDER BY row_id ASC
            LIMIT ?
            """,
            (*params_list, page_size),
        )
        return [self._row_to_diagnostic_event_record(row) for row in rows]

    def _row_to_record(self, row: Any) -> ControlJobRecord:
        progress_json = row["progress_json"] if "progress_json" in row.keys() else "{}"
        policy_flags_json = row["policy_flags_json"] if "policy_flags_json" in row.keys() else "{}"
        return ControlJobRecord(
            job_id=str(row["job_id"]),
            kind=_coerce_control_job_kind(row["job_kind"]),
            state=_coerce_control_job_state(row["state"]),
            run_id=row["run_id"],
            pipeline_id=row["pipeline_id"],
            requested_execution_profile=_coerce_optional_execution_profile(
                row["requested_profile"]
            ),
            effective_execution_profile=_coerce_execution_profile(row["effective_profile"]),
            policy_flags=json.loads(policy_flags_json or "{}"),
            capability_manifest_ref=row["capability_manifest_ref"],
            payload_ref=row["payload_ref"],
            submitted_by=row["submitted_by"],
            created_at=_parse_dt(row["created_at"]) or _utc_now(),
            started_at=_parse_dt(row["started_at"]),
            finished_at=_parse_dt(row["finished_at"]),
            lease_owner=row["lease_owner"],
            lease_expires_at=_parse_dt(row["lease_expires_at"]),
            attempt=int(row["attempt"] or 0),
            error_message=row["error_message"],
            progress=json.loads(progress_json or "{}"),
        )

    def _row_to_worker_lease(self, row: Any) -> ControlWorkerLeaseRecord:
        metadata_json = row["metadata_json"] if "metadata_json" in row.keys() else "{}"
        return ControlWorkerLeaseRecord(
            worker_id=str(row["worker_id"]),
            state=str(row["state"] or "unknown"),
            backend=row["backend"],
            active_job_id=row["active_job_id"],
            metadata=json.loads(metadata_json or "{}"),
            heartbeat_at=_parse_dt(row["heartbeat_at"]) or _utc_now(),
            lease_expires_at=_parse_dt(row["lease_expires_at"]) or _utc_now(),
            created_at=_parse_dt(row["created_at"]) or _utc_now(),
            updated_at=_parse_dt(row["updated_at"]) or _utc_now(),
        )

    def _row_to_scenario_head(self, row: Any) -> ScenarioHeadRecord:
        updated_at = _parse_dt(row["updated_at"])
        if updated_at is None:
            raise RuntimeError("Scenario head has no valid updated_at authority timestamp")
        return ScenarioHeadRecord(
            scenario_id=str(row["scenario_id"]),
            baseline_run_id=str(row["baseline_run_id"]),
            revision=int(row["revision"]),
            artifact_ref=str(row["artifact_ref"]),
            manifest_hash=str(row["manifest_hash"]),
            updated_at=updated_at,
        )

    def _row_to_outbox_record(self, row: Any) -> ControlOutboxRecord:
        payload_json = row["payload_json"] if "payload_json" in row.keys() else "{}"
        return ControlOutboxRecord(
            event_id=str(row["event_id"]),
            topic=str(row["topic"]),
            event_key=row["event_key"],
            state=str(row["state"] or "pending"),
            job_id=row["job_id"],
            run_id=row["run_id"],
            payload=json.loads(payload_json or "{}"),
            created_at=_parse_dt(row["created_at"]) or _utc_now(),
            published_at=_parse_dt(row["published_at"]),
            attempt=int(row["attempt"] or 0),
            error_message=row["error_message"],
        )

    def _row_to_diagnostic_event_record(self, row: Any) -> ControlDiagnosticEventRecord:
        payload_inline_json = (
            row["payload_inline_json"] if "payload_inline_json" in row.keys() else None
        )
        return ControlDiagnosticEventRecord(
            row_id=int(row["row_id"]),
            event=DiagnosticEvent.model_validate_json(row["event_json"]),
            payload_ref=row["payload_ref"],
            payload_inline=(
                json.loads(payload_inline_json)
                if isinstance(payload_inline_json, str) and payload_inline_json
                else None
            ),
            payload_sha256=row["payload_sha256"],
            created_at=_parse_dt(row["created_at"]) or _utc_now(),
        )

    def _row_to_dead_letter_record(self, row: Any) -> ControlDeadLetterRecord:
        return ControlDeadLetterRecord(
            job_id=str(row["job_id"]),
            kind=_coerce_control_job_kind(row["job_kind"]),
            run_id=row["run_id"],
            pipeline_id=row["pipeline_id"],
            attempt=int(row["attempt"] or 0),
            error_message=str(row["error_message"] or ""),
            failed_at=_parse_dt(row["failed_at"]) or _utc_now(),
            acknowledged_at=_parse_dt(row["acknowledged_at"]),
            acknowledged_by=row["acknowledged_by"],
        )

    def _enqueue_dead_letter_job(
        self,
        *,
        record: ControlJobRecord,
        failed_at: datetime,
    ) -> None:
        params = (
            record.job_id,
            record.kind,
            record.run_id,
            record.pipeline_id,
            record.attempt,
            (record.error_message or "control job failed")[:2000],
            _iso(failed_at),
        )
        if self.backend == "sqlite":
            self._execute(
                """
                INSERT INTO control_dead_letter_jobs (
                    job_id, job_kind, run_id, pipeline_id, attempt, error_message, failed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    job_kind = excluded.job_kind,
                    run_id = excluded.run_id,
                    pipeline_id = excluded.pipeline_id,
                    attempt = excluded.attempt,
                    error_message = excluded.error_message,
                    failed_at = excluded.failed_at,
                    acknowledged_at = NULL,
                    acknowledged_by = NULL
                """,
                params,
            )
            return
        self._execute(
            """
            INSERT INTO control_dead_letter_jobs (
                job_id, job_kind, run_id, pipeline_id, attempt, error_message, failed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (job_id) DO UPDATE SET
                job_kind = EXCLUDED.job_kind,
                run_id = EXCLUDED.run_id,
                pipeline_id = EXCLUDED.pipeline_id,
                attempt = EXCLUDED.attempt,
                error_message = EXCLUDED.error_message,
                failed_at = EXCLUDED.failed_at,
                acknowledged_at = NULL,
                acknowledged_by = NULL
            """,
            params,
        )

    def _emit_job_outbox_event(
        self,
        *,
        record: ControlJobRecord,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        topic = _job_event_topic(event_type)
        event_key = None if event_type == "job_progress" else f"{record.job_id}:{event_type}"
        outbox_payload = {
            "job_id": record.job_id,
            "job_kind": record.kind,
            "run_id": record.run_id,
            "pipeline_id": record.pipeline_id,
            "effective_execution_profile": record.effective_execution_profile,
            **payload,
        }
        self.enqueue_outbox_event(
            topic=topic,
            event_key=event_key,
            job_id=record.job_id,
            run_id=record.run_id,
            payload=outbox_payload,
        )

    def _lease_next_sqlite(self, *, worker_id: str, lease_seconds: int) -> ControlJobRecord | None:
        now = _utc_now()
        lease_expires_at = now + timedelta(seconds=max(lease_seconds, 1))
        with self._lock:
            with self._sqlite_connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    row = conn.execute(
                        """
                        SELECT job_id
                        FROM control_jobs
                        WHERE state = 'pending'
                           OR (
                                state = 'running'
                                AND lease_expires_at IS NOT NULL
                                AND lease_expires_at <= ?
                           )
                        ORDER BY created_at ASC
                        LIMIT 1
                        """,
                        (_iso(now),),
                    ).fetchone()
                    if row is None:
                        conn.execute("COMMIT")
                        return None
                    job_id = str(row["job_id"])
                    conn.execute(
                        """
                        UPDATE control_jobs
                        SET state = 'running',
                            started_at = COALESCE(started_at, ?),
                            lease_owner = ?,
                            lease_expires_at = ?,
                            attempt = attempt + 1
                        WHERE job_id = ?
                        """,
                        (_iso(now), worker_id, _iso(lease_expires_at), job_id),
                    )
                    conn.execute("COMMIT")
                except Exception:
                    conn.execute("ROLLBACK")
                    raise
        return self.get_job(job_id)

    def _lease_next_postgres(
        self, *, worker_id: str, lease_seconds: int
    ) -> ControlJobRecord | None:
        now = _utc_now()
        lease_expires_at = now + timedelta(seconds=max(lease_seconds, 1))
        with self._postgres_cursor() as cur:
            cur.execute(
                """
                WITH candidate AS (
                    SELECT job_id
                    FROM control_jobs
                    WHERE state = 'pending'
                       OR (
                            state = 'running'
                            AND lease_expires_at IS NOT NULL
                            AND lease_expires_at <= %s
                       )
                    ORDER BY created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE control_jobs j
                SET state = 'running',
                    started_at = COALESCE(started_at, %s),
                    lease_owner = %s,
                    lease_expires_at = %s,
                    attempt = attempt + 1
                FROM candidate
                WHERE j.job_id = candidate.job_id
                RETURNING j.job_id
                """,
                (_iso(now), _iso(now), worker_id, _iso(lease_expires_at)),
            )
            row = cur.fetchone()
            if row is None:
                return None
            job_id = row[0]
        return self.get_job(str(job_id))

    def _ensure_sqlite_schema(self) -> None:
        with self._lock:
            with self._sqlite_connection() as conn:
                conn.executescript(
                    """
                    PRAGMA journal_mode=WAL;
                    PRAGMA synchronous=NORMAL;
                    PRAGMA temp_store=MEMORY;
                    PRAGMA busy_timeout=5000;
                    PRAGMA foreign_keys=ON;
                    CREATE TABLE IF NOT EXISTS control_jobs (
                        job_id TEXT PRIMARY KEY,
                        job_kind TEXT NOT NULL,
                        state TEXT NOT NULL,
                        run_id TEXT,
                        pipeline_id TEXT,
                        requested_profile TEXT,
                        effective_profile TEXT NOT NULL,
                        policy_flags_json TEXT NOT NULL,
                        capability_manifest_ref TEXT,
                        payload_ref TEXT,
                        submitted_by TEXT,
                        created_at TEXT NOT NULL,
                        started_at TEXT,
                        finished_at TEXT,
                        lease_owner TEXT,
                        lease_expires_at TEXT,
                        attempt INTEGER NOT NULL DEFAULT 0,
                        error_message TEXT
                    );
                    CREATE TABLE IF NOT EXISTS control_job_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS control_job_progress (
                        job_id TEXT PRIMARY KEY,
                        progress_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS control_worker_leases (
                        worker_id TEXT PRIMARY KEY,
                        state TEXT NOT NULL,
                        backend TEXT,
                        active_job_id TEXT,
                        metadata_json TEXT NOT NULL,
                        heartbeat_at TEXT NOT NULL,
                        lease_expires_at TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS control_outbox_events (
                        event_id TEXT PRIMARY KEY,
                        topic TEXT NOT NULL,
                        event_key TEXT,
                        state TEXT NOT NULL,
                        job_id TEXT,
                        run_id TEXT,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        published_at TEXT,
                        attempt INTEGER NOT NULL DEFAULT 0,
                        error_message TEXT
                    );
                    CREATE TABLE IF NOT EXISTS control_diagnostic_events (
                        row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        job_id TEXT NOT NULL,
                        trace_id TEXT NOT NULL,
                        span_id TEXT NOT NULL,
                        event_json TEXT NOT NULL,
                        payload_ref TEXT,
                        payload_inline_json TEXT,
                        payload_sha256 TEXT,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS control_dead_letter_jobs (
                        job_id TEXT PRIMARY KEY,
                        job_kind TEXT NOT NULL,
                        run_id TEXT,
                        pipeline_id TEXT,
                        attempt INTEGER NOT NULL DEFAULT 0,
                        error_message TEXT NOT NULL,
                        failed_at TEXT NOT NULL,
                        acknowledged_at TEXT,
                        acknowledged_by TEXT
                    );
                    CREATE TABLE IF NOT EXISTS runtime_scenario_heads (
                        scenario_id TEXT PRIMARY KEY,
                        baseline_run_id TEXT NOT NULL,
                        revision INTEGER NOT NULL CHECK (revision > 0),
                        artifact_ref TEXT NOT NULL,
                        manifest_hash TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_control_jobs_state_created_at
                        ON control_jobs(state, created_at);
                    CREATE INDEX IF NOT EXISTS idx_control_jobs_pipeline_id
                        ON control_jobs(pipeline_id);
                    CREATE INDEX IF NOT EXISTS idx_control_worker_leases_expires_at
                        ON control_worker_leases(lease_expires_at);
                    CREATE INDEX IF NOT EXISTS idx_control_outbox_state_created_at
                        ON control_outbox_events(state, created_at);
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_control_outbox_topic_event_key
                        ON control_outbox_events(topic, event_key)
                        WHERE event_key IS NOT NULL;
                    CREATE INDEX IF NOT EXISTS idx_control_diagnostic_events_event_id
                        ON control_diagnostic_events(event_id);
                    CREATE INDEX IF NOT EXISTS idx_control_diagnostic_events_run_job
                        ON control_diagnostic_events(run_id, job_id, row_id);
                    CREATE INDEX IF NOT EXISTS idx_control_dead_letter_ack_failed_at
                        ON control_dead_letter_jobs(acknowledged_at, failed_at);
                    CREATE INDEX IF NOT EXISTS idx_runtime_scenario_heads_baseline_run
                        ON runtime_scenario_heads(baseline_run_id, scenario_id);
                    """
                )
                conn.commit()

    def _ensure_postgres_schema(self) -> None:
        with self._postgres_cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS control_jobs (
                    job_id TEXT PRIMARY KEY,
                    job_kind TEXT NOT NULL,
                    state TEXT NOT NULL,
                    run_id TEXT,
                    pipeline_id TEXT,
                    requested_profile TEXT,
                    effective_profile TEXT NOT NULL,
                    policy_flags_json TEXT NOT NULL,
                    capability_manifest_ref TEXT,
                    payload_ref TEXT,
                    submitted_by TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    started_at TIMESTAMPTZ,
                    finished_at TIMESTAMPTZ,
                    lease_owner TEXT,
                    lease_expires_at TIMESTAMPTZ,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS control_job_events (
                    event_id BIGSERIAL PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS control_job_progress (
                    job_id TEXT PRIMARY KEY,
                    progress_json TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS control_worker_leases (
                    worker_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    backend TEXT,
                    active_job_id TEXT,
                    metadata_json TEXT NOT NULL,
                    heartbeat_at TIMESTAMPTZ NOT NULL,
                    lease_expires_at TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS control_outbox_events (
                    event_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    event_key TEXT,
                    state TEXT NOT NULL,
                    job_id TEXT,
                    run_id TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    published_at TIMESTAMPTZ,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS control_diagnostic_events (
                    row_id BIGSERIAL PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    span_id TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    payload_ref TEXT,
                    payload_inline_json TEXT,
                    payload_sha256 TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS control_dead_letter_jobs (
                    job_id TEXT PRIMARY KEY,
                    job_kind TEXT NOT NULL,
                    run_id TEXT,
                    pipeline_id TEXT,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT NOT NULL,
                    failed_at TIMESTAMPTZ NOT NULL,
                    acknowledged_at TIMESTAMPTZ,
                    acknowledged_by TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_scenario_heads (
                    scenario_id TEXT PRIMARY KEY,
                    baseline_run_id TEXT NOT NULL,
                    revision INTEGER NOT NULL CHECK (revision > 0),
                    artifact_ref TEXT NOT NULL,
                    manifest_hash TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_control_worker_leases_expires_at
                ON control_worker_leases(lease_expires_at)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_control_outbox_state_created_at
                ON control_outbox_events(state, created_at)
                """
            )
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_control_outbox_topic_event_key
                ON control_outbox_events(topic, event_key)
                WHERE event_key IS NOT NULL
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_control_diagnostic_events_event_id
                ON control_diagnostic_events(event_id)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_control_diagnostic_events_run_job
                ON control_diagnostic_events(run_id, job_id, row_id)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_control_dead_letter_ack_failed_at
                ON control_dead_letter_jobs(acknowledged_at, failed_at)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_runtime_scenario_heads_baseline_run
                ON runtime_scenario_heads(baseline_run_id, scenario_id)
                """
            )

    def _execute(self, sql: str, params: tuple[Any, ...]) -> None:
        if self.backend == "sqlite":
            with self._lock:
                with self._sqlite_connection() as conn:
                    conn.execute(sql, params)
                    conn.commit()
            return
        with self._postgres_cursor() as cur:
            cur.execute(self._translate_sql(sql), params)

    def _fetchone(self, sql: str, params: tuple[Any, ...]) -> Any:
        if self.backend == "sqlite":
            with self._lock:
                with self._sqlite_connection() as conn:
                    return conn.execute(sql, params).fetchone()
        with self._postgres_cursor() as cur:
            cur.execute(self._translate_sql(sql), params)
            row = cur.fetchone()
            if row is None:
                return None
            columns = [desc[0] for desc in (cur.description or ())]
            return {column: value for column, value in zip(columns, row, strict=False)}

    def _fetchall(self, sql: str, params: tuple[Any, ...]) -> list[Any]:
        if self.backend == "sqlite":
            with self._lock:
                with self._sqlite_connection() as conn:
                    return list(conn.execute(sql, params).fetchall())
        with self._postgres_cursor() as cur:
            cur.execute(self._translate_sql(sql), params)
            rows = cur.fetchall()
            columns = [desc[0] for desc in (cur.description or ())]
            return [
                {column: value for column, value in zip(columns, row, strict=False)} for row in rows
            ]

    @staticmethod
    def _translate_sql(sql: str) -> str:
        return sql.replace("?", "%s")

    @contextmanager
    def _postgres_cursor(self) -> Iterator[Any]:
        if not self._postgres_dsn:
            raise RuntimeError("PostgreSQL control-plane store requires a DSN")
        try:
            psycopg = importlib.import_module("psycopg")
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgreSQL control-plane store") from exc
        with psycopg.connect(self._postgres_dsn, autocommit=False) as conn:
            with conn.cursor() as cur:
                try:
                    yield cur
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise

    @contextmanager
    def _sqlite_connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(
            str(self._sqlite_path),
            timeout=self._sqlite_timeout_seconds,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            yield conn
        finally:
            conn.close()

    def close(self) -> None:
        """Release backend resources. SQLite uses short-lived connections, so this is a no-op."""
        return None


__all__ = [
    "ControlDeadLetterRecord",
    "ControlDiagnosticEventRecord",
    "ControlJobRecord",
    "ControlOutboxRecord",
    "ControlPlaneStore",
    "ControlWorkerLeaseRecord",
]
