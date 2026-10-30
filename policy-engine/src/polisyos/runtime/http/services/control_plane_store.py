"""Persist durable control jobs, worker leases, and outbox events in SQLite/PostgreSQL."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import sqlite3
import threading
import uuid
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, ContextManager, Literal, cast, get_args

from polisyos.runtime.http.services.run_operation_idempotency import (
    RuntimeOperationIntentClaim,
    RuntimeOperationIntentKey,
    RuntimeOperationIntentRecord,
    RuntimeOperationIntentSnapshot,
    RuntimeOperationIntentStatus,
)

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
from polisyos.core.contracts import (
    CONTROL_PRE_ADMISSION_SETTLEMENT_REQUIRED_PROFILES,
    NO_CALL_REASON_VALUES,
    PRODUCER_CALL_STATE_VALUES,
    validate_producer_call_observation,
)
from polisyos.core.contracts.runtime import ApiMeta

if TYPE_CHECKING:
    from polisyos.runtime.http.services.control.child_execution_budget import (
        ChildBudgetClaimLocator,
        ChildExecutionBudgetPolicy,
    )
    from polisyos.common.borrowed_execution import _BorrowedExecutionGrant
    from polisyos.core.artifacts.child_release import (
        ChildJobReleaseClaim,
        ChildJobReleaseLocator,
        ChildJobSessionClaim,
        ChildJobScopeClaim,
    )
    from polisyos.core.run.child_custody import (
        _ChildControlOperation,
        ChildComputationBinding,
        ChildJobReleaseCandidate,
        ChildJobSessionIntent,
        ChildPreparedScope,
        ChildScopeAdmissionUnknown,
        ChildStagingScope,
    )
    from polisyos.core.contracts import (
        ControlPreAdmissionAttemptStatus,
        ProducerCallState,
        NoCallReason,
    )
    from polisyos.core.contracts.owned_attempt_anchor import OwnedAttemptAnchorRef

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
from polisyos.runtime.quality.event_log import _PreparedDiagnosticEvent, _payload_bytes
from polisyos.runtime.http.services._control_contracts import _ControlJobAdmissionDiagnosticBinding
from polisyos.runtime.quality.evidence_spine_handoff import (
    append_evidence_spine_handoff,
    control_plane_handoff,
)


_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC = "control.decision_validity.hte_source_update"


def _completed_hte_source_invalidation_dedupe_key(
    *,
    source_run_id: str,
    source_job_id: str,
    source_attempt: int,
    completed_event_id: int,
    completed_event_payload_sha256: str,
) -> str:
    """Return the stable key for one owner-selected HTE completion binding."""
    if (
        type(source_run_id) is not str
        or not source_run_id
        or type(source_job_id) is not str
        or not source_job_id
        or type(source_attempt) is not int
        or source_attempt < 1
        or type(completed_event_id) is not int
        or completed_event_id < 1
        or type(completed_event_payload_sha256) is not str
        or not completed_event_payload_sha256.startswith("sha256:")
        or len(completed_event_payload_sha256) != len("sha256:") + 64
        or any(
            character not in "0123456789abcdef"
            for character in completed_event_payload_sha256.removeprefix("sha256:")
        )
    ):
        raise ValueError("completed_hte_source_event_identity_invalid")
    binding = {
        "schema_version": "polisyos.runtime.completed_hte_source_invalidation.v1",
        "source_run_id": source_run_id,
        "source_job_id": source_job_id,
        "source_attempt": source_attempt,
        "completed_event_id": completed_event_id,
        "completed_event_payload_sha256": completed_event_payload_sha256,
    }
    raw = json.dumps(binding, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"hte_completed_source_run_update:{hashlib.sha256(raw).hexdigest()}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _human_decision_iso(dt: datetime) -> str:
    """Serialize DS9 reservation time without collapsing CAS boundaries."""

    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    return None


def _required_aware_datetime(value: datetime, *, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise TypeError(f"{field_name} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _is_sha256_ref(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value[7:]
    return len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)


def _is_unique_constraint_violation(exc: BaseException) -> bool:
    """Recognize unique-index conflicts across the supported SQL drivers."""
    if isinstance(exc, sqlite3.IntegrityError):
        return "unique constraint failed" in str(exc).casefold()
    return getattr(exc, "sqlstate", None) == "23505" or getattr(exc, "pgcode", None) == "23505"


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


_CONTROL_JOB_KINDS = frozenset(get_args(ControlJobKind))
_CONTROL_JOB_STATES = frozenset({"pending", "running", "completed", "failed", "cancelled"})
_EXECUTION_PROFILES = frozenset({"dev", "research", "governed", "production"})
_SERIOUS_EXECUTION_PROFILES = frozenset({"research", "governed", "production"})
# Backward-compatible name for consumers; the Literal contract above is canonical.
CONTROL_PRE_ADMISSION_NO_CALL_FAILURE_CODES = NO_CALL_REASON_VALUES
_CONTROL_EXECUTION_SCOPE_SCHEMA_VERSION = "polisyos.runtime.control_execution_scope.v1"
_CONTROL_EXECUTION_SCOPE_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "tenant_id",
        "cell_id",
        "actor_subject",
        "actor_authenticated",
        "actor_roles",
    }
)
_CONTROL_EXECUTION_SCOPE_SENTINELS = frozenset(
    {
        "",
        "anonymous",
        "cell-unknown",
        "none",
        "not-established",
        "null",
        "tenant-unknown",
        "unknown",
    }
)
_CONTROL_JOB_ADMISSION_STABLE_FIELDS = (
    "job_id",
    "run_id",
    "job_kind",
    "pipeline_id",
    "payload_ref",
    "submitted_by",
    "requested_execution_profile",
    "effective_execution_profile",
    "policy_flags",
    "capability_manifest_ref",
)
_CONTROL_OUTBOX_ENVELOPE_FIELDS = frozenset(
    {"job_id", "job_kind", "run_id", "pipeline_id", "effective_execution_profile"}
)


def _json_values_equal_strict(left: object, right: object) -> bool:
    """Compare decoded JSON values with exact primitive types and order-free objects."""

    if type(left) is not type(right):
        return False
    if isinstance(left, dict) and isinstance(right, dict):
        if any(not isinstance(key, str) for key in left) or any(
            not isinstance(key, str) for key in right
        ):
            return False
        if left.keys() != right.keys():
            return False
        return all(_json_values_equal_strict(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _json_values_equal_strict(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    return left == right


ExecutionScopeStatus = Literal["established", "not_established"]
ManifestPointerState = Literal["admission_current", "refreshed_current", "missing_current"]

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
            variant_failures=[dict(item) for item in variant_failures if isinstance(item, Mapping)],
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
        key in progress for key in ("quality_status", "quality_gates", "blocking_quality_failures")
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
        reason_code = _string_or_none(failure.get("code"))
        failure_message = _string_or_none(failure.get("message"))
    else:
        reason_code = None
        failure_message = None
    if authority_path == "workflow_failure":
        return failure_message or reason_code or "workflow failure cannot complete cleanly"
    if disposition and disposition.startswith("blocked_workflow_failure"):
        return failure_message or reason_code or disposition
    if progress_state == "failed" and authority_result in {
        "repair_required",
        "blocked",
    }:
        return failure_message or reason_code or "failed progress cannot complete cleanly"
    if runtime_state == "blocked" and authority_result in {
        "repair_required",
        "blocked",
    }:
        return failure_message or reason_code or "blocked progress cannot complete cleanly"
    if status in {"fail", "failed", "error"} and authority_result in {
        None,
        "repair_required",
        "blocked",
    }:
        return failure_message or reason_code or "failed workflow status cannot complete cleanly"
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


def _blocking_failures_from_gates(
    gates: list[ControlQualityGate],
) -> list[ControlQualityFailure]:
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
    method_execution_selection: dict[str, Any] | None = None

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
            cancellation_disposition=("publication_fenced" if self.state == "cancelled" else None),
            physical_stop_status=("not_established" if self.state == "cancelled" else None),
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
            runtime_quality_artifact_refs=self.progress.get(
                "runtime_quality_artifact_refs",
                {},
            ),
        )


def _control_job_outbox_identity_envelope(
    record: ControlJobRecord,
) -> dict[str, str | None]:
    """Project the producer-owned identity envelope from one durable job row."""
    return {
        "job_id": record.job_id,
        "job_kind": record.kind,
        "run_id": record.run_id,
        "pipeline_id": record.pipeline_id,
        "effective_execution_profile": record.effective_execution_profile,
    }


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
class ControlPreAdmissionAttemptEventRecord:
    """Represent one immutable pre-admission attempt observation."""

    event_id: str
    sequence: int
    event_type: ControlPreAdmissionAttemptStatus
    observed_at: datetime
    producer_event_ids: tuple[str, ...]
    producer_event_observation: ProducerCallState
    producer_no_call_reason: NoCallReason | None
    failure_code: str | None
    job_id: str | None


@dataclass(frozen=True)
class ControlPreAdmissionAttemptRecord:
    """Represent one immutable launch intent and its latest durable observation."""

    attempt_id: str
    intent_sha256: str
    intent_binding: dict[str, Any]
    producer_run_binding: dict[str, Any] | None
    idempotency_key_sha256: str | None
    request_id: str
    run_id: str
    candidate_job_id: str
    job_id: str | None
    tenant_id: str | None
    cell_id: str | None
    actor_subject: str | None
    effective_execution_profile: str
    status: ControlPreAdmissionAttemptStatus
    producer_event_ids: tuple[str, ...]
    producer_event_observation: ProducerCallState
    producer_no_call_reason: NoCallReason | None
    failure_code: str | None
    created_at: datetime
    updated_at: datetime
    history: tuple[ControlPreAdmissionAttemptEventRecord, ...]
    shared_owner: RuntimeOperationIntentRecord


class ControlPreAdmissionIdempotencyConflictError(RuntimeError):
    """Report reuse of one client key for a different immutable intent."""

    def __init__(self, attempt_id: str) -> None:
        self.attempt_id = attempt_id
        super().__init__("control_pre_admission_idempotency_intent_conflict")


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
class ControlJobExecutionScope:
    """Carry tenant/cell and actor identity admitted by one job-created event."""

    status: ExecutionScopeStatus
    tenant_id: str | None
    cell_id: str | None
    actor_subject: str | None
    actor_authenticated: bool
    actor_roles: tuple[str, ...]


@dataclass(frozen=True)
class ControlJobExecutionAdmission:
    """Bind one live leased job to its immutable creation-time execution scope."""

    job: ControlJobRecord
    scope: ControlJobExecutionScope
    admission_capability_manifest_ref: str | None
    attempt: int
    manifest_pointer_state: ManifestPointerState


def _unknown_child_scope_admission(
    claim: ChildJobScopeClaim, locator: ChildJobReleaseLocator | None
) -> ChildScopeAdmissionUnknown:
    from polisyos.core.run.child_custody import ChildRecoveryLocator, ChildScopeAdmissionUnknown

    session = claim.session
    recovery = ChildRecoveryLocator(
        release_id=session.release_id,
        root_run_id=session.root_run_id,
        parent_attempt_id=session.parent_attempt_id,
        parent_basis_json=json.dumps(
            session.parent_basis_ref.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii"),
        job_intent_locator=claim.session_intent,
    )
    return ChildScopeAdmissionUnknown(
        recovery,
        scope_claim_json=json.dumps(
            claim.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode(),
        scope_locator=locator,
    )


class _ChildComputationPublicationFence:
    """Job-owner fence for a short final child-release head transition."""

    def __init__(
        self,
        store: ControlPlaneStore,
        admission: ControlJobExecutionAdmission,
        *,
        grant: _BorrowedExecutionGrant | None = None,
        binding: ChildComputationBinding | None = None,
    ) -> None:
        scope = admission.scope
        job = admission.job
        if (
            scope.status != "established"
            or not scope.tenant_id
            or not scope.cell_id
            or not scope.actor_authenticated
            or not scope.actor_subject
            or not job.run_id
            or not job.lease_owner
        ):
            raise ControlJobExecutionAdmissionError("child_publication_scope_not_established")
        self._store = store
        self._admission = admission
        self.root_run_id = job.run_id
        self.control_job_id = job.job_id
        self.tenant_id = scope.tenant_id
        self.cell_id = scope.cell_id
        self._grant = grant
        self._binding = binding
        if (grant is None) != (binding is None):
            raise ControlJobExecutionAdmissionError("child_publication_resource_binding_missing")
        if grant is not None:
            from polisyos.common.borrowed_execution import _BorrowedExecutionGrant
            from polisyos.core.run.child_custody import ChildComputationBinding

            if (
                type(grant) is not _BorrowedExecutionGrant
                or type(binding) is not ChildComputationBinding
            ):
                raise ControlJobExecutionAdmissionError(
                    "child_publication_resource_binding_invalid"
                )
            if (
                binding.root_run_id,
                binding.control_job_id,
                binding.tenant_id,
                binding.cell_id,
            ) != (self.root_run_id, self.control_job_id, self.tenant_id, self.cell_id):
                raise ControlJobExecutionAdmissionError(
                    "child_publication_resource_identity_mismatch"
                )
            grant.require_parent(**store._child_grant_binding(binding))
            self._binding = binding.model_copy(deep=True)

    def _reconcile(self) -> None:
        current = self._store.current_execution_job_admission()
        expected = self._admission
        if (
            current.job.job_id != expected.job.job_id
            or current.job.run_id != expected.job.run_id
            or current.job.lease_owner != expected.job.lease_owner
            or current.attempt != expected.attempt
            or current.scope != expected.scope
            or current.job.effective_execution_profile != expected.job.effective_execution_profile
            or current.admission_capability_manifest_ref
            != expected.admission_capability_manifest_ref
        ):
            raise ControlJobLeaseLostError("child_publication_admission_changed")

    def check_active(self) -> None:
        """Reconcile the handler binding and persisted lease before work."""
        with self._store._job_transaction():
            self._reconcile()
            if self._grant is not None:
                self._grant.require_parent(**self._store._child_grant_binding(self._binding))

    @contextmanager
    def local_consumption(self) -> Iterator[None]:
        """Fence one local Core consumption against the original parent grant."""
        if self._grant is None or self._binding is None:
            raise ControlJobExecutionAdmissionError("child_resource_grant_required")
        with self._grant.publication():
            self._grant.require_parent(**self._store._child_grant_binding(self._binding))
            yield

    def _install_scope_resource_predicate(self) -> None:
        """Install the same ordered actual-row predicate for scope and producer decisions."""
        if self._grant is None or self._binding is None:
            raise ControlJobExecutionAdmissionError("child_resource_grant_required")
        conn = self._store._human_decision_transaction.sqlite_connection
        if conn is None:
            raise ControlJobExecutionAdmissionError("child_scope_sqlite_required")
        binding = self._binding
        resource_binding = self._store._child_grant_binding(binding)

        def resource_current(lease_expiry: str) -> int:
            wall_at_decision = datetime.now(timezone.utc)
            try:
                if type(lease_expiry) is not str:
                    return 0
                expiry = datetime.fromisoformat(lease_expiry.replace("Z", "+00:00"))
                if (
                    expiry.tzinfo is None
                    or expiry.utcoffset() is None
                    or expiry <= wall_at_decision
                    or binding.deadline <= wall_at_decision
                ):
                    return 0
                grant = self._grant
                if grant is None:
                    return 0
                grant.require_parent(**resource_binding)
            except (RuntimeError, ValueError, TypeError):
                return 0
            return 1

        conn.create_function("child_owner_resource_current", 1, resource_current)

    def admit_prepared_scope(self, prepared: ChildPreparedScope) -> ChildStagingScope:
        """Commit one exact scope decision before transferring the private scope."""
        from polisyos.core.artifacts.child_release import ChildReleaseUnavailableError

        if self._grant is None or self._binding is None:
            raise ControlJobExecutionAdmissionError("child_resource_grant_required")
        locator, claim = self._store._record_child_scope(
            prepared=prepared, grant=self._grant, fence=self
        )
        try:
            return prepared.complete(locator)
        except (
            OSError,
            sqlite3.Error,
            ControlJobExecutionAdmissionError,
            ChildReleaseUnavailableError,
        ) as exc:
            raise _unknown_child_scope_admission(claim, locator) from exc

    def admit_producer(self) -> None:
        """Make a short actual-job and borrowed-capacity producer decision."""
        if self._grant is None or self._binding is None:
            raise ControlJobExecutionAdmissionError("child_resource_grant_required")
        with self._store._job_transaction():
            self._reconcile()
            current = self._store.current_execution_job_admission()
            self._install_scope_resource_predicate()
            with self._grant.admission():
                row = self._store._fetchone(
                    "SELECT job_id FROM control_jobs WHERE job_id = ? AND state = 'running' "
                    "AND lease_owner = ? AND attempt = ? AND lease_expires_at IS NOT NULL "
                    "AND child_owner_resource_current(lease_expires_at) = 1",
                    (self.control_job_id, current.job.lease_owner, current.attempt),
                )
                if row is None:
                    raise ControlJobLeaseLostError("child_producer_admission_refused")

    def begin_session(self, intent: ChildJobSessionIntent) -> ChildJobReleaseLocator:
        if self._grant is None:
            raise ControlJobExecutionAdmissionError("child_resource_grant_required")
        from polisyos.core.run.child_custody import (
            ChildRecoveryLocator,
            ChildSessionAdmissionUnknown,
        )

        claim = intent.recompute()
        recovery = ChildRecoveryLocator(
            release_id=claim.release_id,
            root_run_id=claim.root_run_id,
            parent_attempt_id=claim.parent_attempt_id,
            parent_basis_json=json.dumps(
                claim.parent_basis_ref.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("ascii"),
            job_intent_locator=None,
        )
        attempted = False
        committed = False

        def mark_attempted() -> None:
            nonlocal attempted
            attempted = True

        def mark_committed() -> None:
            nonlocal committed
            committed = True

        try:
            return self._store._record_child_job_event(
                intent,
                self._grant,
                self,
                kind="session",
                on_transaction_attempt=mark_attempted,
                on_transaction_committed=mark_committed,
            )
        except (OSError, sqlite3.Error) as exc:
            if not attempted:
                raise
            raise ChildSessionAdmissionUnknown(recovery) from exc
        except ControlJobExecutionAdmissionError as exc:
            if not committed:
                raise
            raise ChildSessionAdmissionUnknown(recovery) from exc
        except (TypeError, ValueError) as exc:
            if not committed:
                raise
            raise ChildSessionAdmissionUnknown(recovery) from exc

    def authorize_release(self, candidate: ChildJobReleaseCandidate) -> ChildJobReleaseLocator:
        if self._grant is None:
            raise ControlJobExecutionAdmissionError("child_resource_grant_required")
        return self._store._record_child_job_event(
            candidate, self._grant, self, kind="authorization"
        )

    def publish_head(
        self,
        candidate: ChildJobReleaseCandidate,
        locator: ChildJobReleaseLocator,
        claim: ChildJobReleaseClaim,
    ) -> None:
        """Commit the selected head inside the actual current-job transaction."""
        with self.publication():
            self._store._verify_child_job_event(locator, claim, kind="authorization")
            current = self._store.current_execution_job_admission()
            lease_expires_at = current.job.lease_expires_at
            if lease_expires_at is None:
                raise ControlJobLeaseLostError("child_publication_lease_missing")
            candidate._commit_head_local(locator, claim, lease_expires_at)

    @contextmanager
    def publication(self) -> Iterator[None]:
        """Hold the real job row fence for only the release head transition."""
        with self._store._job_transaction():
            self._reconcile()
            if self._grant is None:
                yield
            else:
                with self._grant.publication():
                    self._grant.require_parent(**self._store._child_grant_binding(self._binding))
                    yield


@dataclass(frozen=True)
class _ControlJobLifecycleSourceEventRecord:
    """Reconcile one persisted lifecycle event row and its exact stored payload."""

    event_id: int
    job_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: datetime
    payload_sha256: str


@dataclass(frozen=True)
class _ControlJobExecutionLifecycleProof:
    """Bind one worker attempt to its persisted lifecycle event under a store transaction."""

    record: ControlJobRecord
    proof_phase: Literal["job_admission", "running", "completed", "failed"]
    worker_id: str | None
    attempt: int | None
    source_event: _ControlJobLifecycleSourceEventRecord


@dataclass(frozen=True)
class ControlDiagnosticEventRecord:
    """Represent one durable append-only runtime diagnostic event record."""

    row_id: int
    event: DiagnosticEvent
    payload_ref: str | None
    payload_inline: dict[str, Any] | None
    payload_sha256: str | None
    created_at: datetime


class ControlJobLeaseLostError(RuntimeError):
    """Raised when a worker attempts to write outside its live job lease."""


class ControlJobCancellationConflictError(ControlJobLeaseLostError):
    """A cancellation request's optimistic identity conflicts with durable job state.

    This excludes worker publication lease loss and post-write integrity failures.
    """


class ControlJobExecutionAdmissionError(RuntimeError):
    """Raised when a leased job's creation record cannot establish its identity."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _unknown_control_job_execution_scope() -> ControlJobExecutionScope:
    return ControlJobExecutionScope(
        status="not_established",
        tenant_id=None,
        cell_id=None,
        actor_subject=None,
        actor_authenticated=False,
        actor_roles=(),
    )


def _control_job_execution_scope_from_event(
    payload: dict[str, Any],
) -> ControlJobExecutionScope:
    if "execution_scope" not in payload:
        return _unknown_control_job_execution_scope()
    raw = payload.get("execution_scope")
    if not isinstance(raw, dict) or set(raw) != _CONTROL_EXECUTION_SCOPE_KEYS:
        raise ControlJobExecutionAdmissionError("control_job_execution_scope_malformed")
    if raw.get("schema_version") != _CONTROL_EXECUTION_SCOPE_SCHEMA_VERSION:
        raise ControlJobExecutionAdmissionError("control_job_execution_scope_malformed")
    status = raw.get("status")
    tenant_id = raw.get("tenant_id")
    cell_id = raw.get("cell_id")
    actor_subject = raw.get("actor_subject")
    actor_authenticated = raw.get("actor_authenticated")
    actor_roles = raw.get("actor_roles")
    if (
        not isinstance(status, str)
        or status not in {"established", "not_established"}
        or (tenant_id is not None and not isinstance(tenant_id, str))
        or (cell_id is not None and not isinstance(cell_id, str))
        or (actor_subject is not None and not isinstance(actor_subject, str))
        or type(actor_authenticated) is not bool
        or not isinstance(actor_roles, list)
        or any(not isinstance(role, str) for role in actor_roles)
    ):
        raise ControlJobExecutionAdmissionError("control_job_execution_scope_malformed")
    if status == "not_established":
        if (
            tenant_id is not None
            or cell_id is not None
            or actor_subject is not None
            or actor_authenticated
            or actor_roles
        ):
            raise ControlJobExecutionAdmissionError("control_job_execution_scope_malformed")
        return _unknown_control_job_execution_scope()

    identities = (tenant_id, cell_id, actor_subject)
    if (
        any(
            value is None
            or not value
            or value != value.strip()
            or value.casefold() in _CONTROL_EXECUTION_SCOPE_SENTINELS
            for value in identities
        )
        or not actor_authenticated
    ):
        raise ControlJobExecutionAdmissionError("control_job_execution_scope_incomplete")
    if any(not role or role != role.strip() for role in actor_roles) or actor_roles != sorted(
        set(actor_roles)
    ):
        raise ControlJobExecutionAdmissionError("control_job_execution_scope_malformed")
    return ControlJobExecutionScope(
        status="established",
        tenant_id=tenant_id,
        cell_id=cell_id,
        actor_subject=actor_subject,
        actor_authenticated=True,
        actor_roles=tuple(actor_roles),
    )


@dataclass(frozen=True)
class AcquisitionActionHeadRecord:
    """Pointer-only durable head for one acquisition action generation."""

    tenant_id: str
    cell_id: str
    run_id: str
    source_job_id: str
    route_id: str
    action_generation: int
    head_generation: int
    receipt_ref: str
    receipt_sha256: str
    durable_event_id: str
    coarse_phase: str
    receipt_phase: str
    recovery_state: str
    job_id: str
    predecessor_receipt_ref: str | None
    created_at: datetime

    evaluation_frontier_before_ref: str | None = None
    evaluation_frontier_ref: str | None = None


@dataclass(frozen=True)
class AcquisitionEvaluationFrontierKey:
    """Owner-resolved identity for one candidate/task evaluation selector."""

    tenant_id: str
    cell_id: str
    source_job_id: str
    design_problem_ref: str
    candidate_id: str


@dataclass(frozen=True)
class AcquisitionEvaluationFrontierValue:
    """Content-bound selected evaluation admitted by its source owner."""

    selected_evaluation_witness_ref: str
    selected_evaluation_content_hash: str
    basis_ref: str | None = None
    basis_content_hash: str | None = None
    decision_ref: str | None = None


@dataclass(frozen=True)
class AcquisitionEvaluationFrontierCAS:
    """Expected frontier revision plus optional new selected evaluation."""

    key: AcquisitionEvaluationFrontierKey
    expected_revision: int
    expected_frontier_ref: str | None
    replacement: AcquisitionEvaluationFrontierValue | None


@dataclass(frozen=True)
class AcquisitionEvaluationFrontierRecord:
    """Immutable historical selector version returned by ControlPlaneStore."""

    key: AcquisitionEvaluationFrontierKey
    revision: int
    selected_evaluation_witness_ref: str
    selected_evaluation_content_hash: str
    basis_ref: str | None
    basis_content_hash: str | None
    decision_ref: str | None
    frontier_ref: str


@dataclass(frozen=True)
class AcquisitionActionHeadFrontierCommit:
    """Action-head append and the exact shared frontier version selected with it."""

    head: AcquisitionActionHeadRecord
    frontier: AcquisitionEvaluationFrontierRecord


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


def _validate_acquisition_evaluation_frontier_key(
    key: AcquisitionEvaluationFrontierKey,
) -> None:
    if type(key) is not AcquisitionEvaluationFrontierKey:
        raise TypeError("acquisition_evaluation_frontier_key_untyped")
    identities = (key.tenant_id, key.cell_id, key.source_job_id, key.candidate_id)
    if any(type(value) is not str or not value or value != value.strip() for value in identities):
        raise ValueError("acquisition_evaluation_frontier_key_invalid")
    if not _is_sha256_ref(key.design_problem_ref):
        raise ValueError("acquisition_evaluation_frontier_design_problem_ref_invalid")


def _validate_acquisition_evaluation_frontier_value(
    value: AcquisitionEvaluationFrontierValue,
) -> None:
    if type(value) is not AcquisitionEvaluationFrontierValue:
        raise TypeError("acquisition_evaluation_frontier_value_untyped")
    if not _is_sha256_ref(value.selected_evaluation_witness_ref) or not _is_sha256_ref(
        value.selected_evaluation_content_hash
    ):
        raise ValueError("acquisition_evaluation_frontier_witness_invalid")
    if (value.basis_ref is None) != (value.basis_content_hash is None):
        raise ValueError("acquisition_evaluation_frontier_basis_binding_incomplete")
    if value.basis_ref is not None and (
        not _is_sha256_ref(value.basis_ref) or not _is_sha256_ref(value.basis_content_hash)
    ):
        raise ValueError("acquisition_evaluation_frontier_basis_invalid")
    if value.decision_ref is not None and not _is_sha256_ref(value.decision_ref):
        raise ValueError("acquisition_evaluation_frontier_decision_ref_invalid")


def _validate_acquisition_evaluation_frontier_cas(
    frontier_cas: AcquisitionEvaluationFrontierCAS,
    *,
    require_replacement: bool = False,
) -> None:
    if type(frontier_cas) is not AcquisitionEvaluationFrontierCAS:
        raise TypeError("acquisition_evaluation_frontier_cas_untyped")
    _validate_acquisition_evaluation_frontier_key(frontier_cas.key)
    if type(frontier_cas.expected_revision) is not int or frontier_cas.expected_revision < 0:
        raise ValueError("acquisition_evaluation_frontier_revision_invalid")
    if frontier_cas.expected_revision == 0:
        if frontier_cas.expected_frontier_ref is not None:
            raise ValueError("acquisition_evaluation_frontier_expected_ref_invalid")
    elif not _is_sha256_ref(frontier_cas.expected_frontier_ref):
        raise ValueError("acquisition_evaluation_frontier_expected_ref_invalid")
    if frontier_cas.replacement is not None:
        _validate_acquisition_evaluation_frontier_value(frontier_cas.replacement)
    elif require_replacement:
        raise ValueError("acquisition_evaluation_frontier_replacement_required")
    elif frontier_cas.expected_revision == 0:
        raise ValueError("acquisition_evaluation_frontier_not_established")


def _acquisition_evaluation_frontier_ref(
    *,
    key: AcquisitionEvaluationFrontierKey,
    revision: int,
    value: AcquisitionEvaluationFrontierValue,
) -> str:
    payload = {
        "schema_version": "polisyos.control.acquisition_evaluation_frontier.v1",
        "tenant_id": key.tenant_id,
        "cell_id": key.cell_id,
        "source_job_id": key.source_job_id,
        "design_problem_ref": key.design_problem_ref,
        "candidate_id": key.candidate_id,
        "revision": revision,
        "selected_evaluation_witness_ref": value.selected_evaluation_witness_ref,
        "selected_evaluation_content_hash": value.selected_evaluation_content_hash,
        "basis_ref": value.basis_ref,
        "basis_content_hash": value.basis_content_hash,
        "decision_ref": value.decision_ref,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _acquisition_evaluation_frontier_record(
    *,
    key: AcquisitionEvaluationFrontierKey,
    revision: int,
    value: AcquisitionEvaluationFrontierValue,
) -> AcquisitionEvaluationFrontierRecord:
    return AcquisitionEvaluationFrontierRecord(
        key=key,
        revision=revision,
        selected_evaluation_witness_ref=value.selected_evaluation_witness_ref,
        selected_evaluation_content_hash=value.selected_evaluation_content_hash,
        basis_ref=value.basis_ref,
        basis_content_hash=value.basis_content_hash,
        decision_ref=value.decision_ref,
        frontier_ref=_acquisition_evaluation_frontier_ref(
            key=key,
            revision=revision,
            value=value,
        ),
    )


HumanDecisionReservationState = Literal[
    "reserved",
    "committed",
    "recovery_required",
    "reconciled_empty",
    "reconciled_orphan",
    "expired",
]


@dataclass(frozen=True)
class HumanDecisionReservationRecord:
    """One immutable-generation reservation for a governed action."""

    tenant_id: str
    governed_action_key: str
    reservation_id: str
    reservation_version: int
    binding_sha256: str
    state: HumanDecisionReservationState
    reserved_at: datetime
    lease_expires_at: datetime
    record_valid_until: datetime
    record_ref: str | None
    record_sha256: str | None
    durable_event_id: str | None
    committed_at: datetime | None
    reconciled_at: datetime | None


@dataclass(frozen=True)
class HumanDecisionReservationResult:
    """Return a reservation winner or one typed fail-closed disposition."""

    acquired: bool
    issue_code: (
        Literal[
            "DS9-OVERLAPPING-REISSUE",
            "DS9-RESERVATION-RECOVERY-REQUIRED",
        ]
        | None
    )
    reservation: HumanDecisionReservationRecord


@dataclass
class HumanDecisionWriteFence:
    """Transaction-scoped CAS for one exact reserved decision generation."""

    reservation: HumanDecisionReservationRecord
    _execute: Callable[[str, tuple[Any, ...]], Any]
    _load: Callable[[], Any]
    _finalized: bool = False

    def commit(
        self,
        *,
        record_ref: str,
        record_sha256: str,
        durable_event_id: str,
        committed_at: datetime,
    ) -> HumanDecisionReservationRecord:
        """Commit exact record/event refs while the generation remains fenced."""

        if self._finalized:
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        if not _is_sha256_ref(record_ref) or record_ref != record_sha256:
            raise ValueError("human-decision record ref/digest binding is invalid")
        if not durable_event_id.strip():
            raise ValueError("human-decision durable event id is required")
        committed = _required_aware_datetime(committed_at, field_name="committed_at")
        row = self.reservation
        cursor = self._execute(
            """
            UPDATE runtime_human_decision_reservations
            SET state = 'committed', record_ref = ?, record_sha256 = ?,
                durable_event_id = ?, committed_at = ?
            WHERE tenant_id = ? AND governed_action_key = ?
              AND reservation_id = ? AND reservation_version = ?
              AND binding_sha256 = ? AND state = 'reserved'
              AND record_ref IS NULL AND record_sha256 IS NULL
              AND durable_event_id IS NULL AND committed_at IS NULL
              AND reconciled_at IS NULL
              AND lease_expires_at > ? AND record_valid_until > ?
              AND record_valid_until = ?
            """,
            (
                record_ref,
                record_sha256,
                durable_event_id,
                _human_decision_iso(committed),
                row.tenant_id,
                row.governed_action_key,
                row.reservation_id,
                row.reservation_version,
                row.binding_sha256,
                _human_decision_iso(committed),
                _human_decision_iso(committed),
                _human_decision_iso(row.record_valid_until),
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        loaded = self._load()
        if loaded is None:
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        result = ControlPlaneStore._row_to_human_decision_reservation(loaded)
        if (
            result.state != "committed"
            or result.record_ref != record_ref
            or result.record_sha256 != record_sha256
            or result.durable_event_id != durable_event_id
        ):
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        self._finalized = True
        return result

    def recover(
        self,
        *,
        record_ref: str | None,
        record_sha256: str | None,
        durable_event_id: str | None,
    ) -> HumanDecisionReservationRecord:
        """Persist exact partial refs as recovery-required before releasing the fence."""

        if self._finalized:
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        supplied = (record_ref, record_sha256, durable_event_id)
        if any(value is not None for value in supplied) and (
            not all(isinstance(value, str) and value for value in supplied)
            or not _is_sha256_ref(record_ref)
            or record_ref != record_sha256
        ):
            raise ValueError("human-decision orphan record binding is invalid")
        row = self.reservation
        cursor = self._execute(
            """
            UPDATE runtime_human_decision_reservations
            SET state = 'recovery_required', record_ref = ?, record_sha256 = ?,
                durable_event_id = ?
            WHERE tenant_id = ? AND governed_action_key = ?
              AND reservation_id = ? AND reservation_version = ?
              AND binding_sha256 = ? AND state = 'reserved'
              AND record_ref IS NULL AND record_sha256 IS NULL
              AND durable_event_id IS NULL AND committed_at IS NULL
              AND reconciled_at IS NULL
            """,
            (
                record_ref,
                record_sha256,
                durable_event_id,
                row.tenant_id,
                row.governed_action_key,
                row.reservation_id,
                row.reservation_version,
                row.binding_sha256,
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        loaded = self._load()
        if loaded is None:
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        result = ControlPlaneStore._row_to_human_decision_reservation(loaded)
        if (
            result.state != "recovery_required"
            or result.record_ref != record_ref
            or result.record_sha256 != record_sha256
            or result.durable_event_id != durable_event_id
        ):
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        self._finalized = True
        return result


@dataclass
class HumanDecisionRecoveryFence:
    """Transaction-scoped CAS for one exact null-ref crashed generation."""

    reservation: HumanDecisionReservationRecord
    _execute: Callable[[str, tuple[Any, ...]], Any]
    _load: Callable[[], Any]
    _finalized: bool = False

    def reconcile_orphan(
        self,
        *,
        record_ref: str,
        record_sha256: str,
        durable_event_id: str,
        reconciled_at: datetime,
    ) -> HumanDecisionReservationRecord:
        """Attach verified refs and classify the crashed generation as historical."""

        if self._finalized:
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        if not _is_sha256_ref(record_ref) or record_ref != record_sha256:
            raise ValueError("human-decision orphan record binding is invalid")
        if not durable_event_id.strip():
            raise ValueError("human-decision durable event id is required")
        reconciled = _required_aware_datetime(
            reconciled_at,
            field_name="reconciled_at",
        )
        row = self.reservation
        cursor = self._execute(
            """
            UPDATE runtime_human_decision_reservations
            SET state = 'reconciled_orphan', record_ref = ?, record_sha256 = ?,
                durable_event_id = ?, reconciled_at = ?
            WHERE tenant_id = ? AND governed_action_key = ?
              AND reservation_id = ? AND reservation_version = ?
              AND binding_sha256 = ? AND record_valid_until = ?
              AND state = 'recovery_required'
              AND record_ref IS NULL AND record_sha256 IS NULL
              AND durable_event_id IS NULL AND committed_at IS NULL
              AND reconciled_at IS NULL
            """,
            (
                record_ref,
                record_sha256,
                durable_event_id,
                _human_decision_iso(reconciled),
                row.tenant_id,
                row.governed_action_key,
                row.reservation_id,
                row.reservation_version,
                row.binding_sha256,
                _human_decision_iso(row.record_valid_until),
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        loaded = self._load()
        if loaded is None:
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        result = ControlPlaneStore._row_to_human_decision_reservation(loaded)
        if (
            result.state != "reconciled_orphan"
            or result.record_ref != record_ref
            or result.record_sha256 != record_sha256
            or result.durable_event_id != durable_event_id
            or result.committed_at is not None
            or result.reconciled_at != reconciled
        ):
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        self._finalized = True
        return result


@dataclass(slots=True)
class _ControlJobTransactionAdmission:
    """Actual bound job evidence held only by the admitting SQL transaction."""

    resource: Any
    identity: tuple[str, str, int]
    lease_expires_at: datetime | None
    terminal_state: Literal["completed", "failed", "cancelled"] | None = None


@dataclass(frozen=True, slots=True)
class _ControlJobCreationBasis:
    """Unpublished immutable preparation basis, never an event/authorization receipt."""

    job_id: str
    initial_state: Literal["pending", "failed"]
    prepared_at: datetime
    source_payload_json: str
    source_payload_sha256: str
    creation_owner: object


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
        self._human_decision_transaction = threading.local()
        self._creation_plan_owner = object()
        self._job_execution_fence: ContextVar[tuple[str, str, int] | None] = ContextVar(
            "control_job_execution_fence", default=None
        )
        # Controlled documentation fixtures may provide stable event IDs. The
        # production path keeps UUIDv4 IDs unless this private seam is set.
        self._pre_admission_event_id_factory: Callable[[], str] | None = None
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

    def job_execution_fence(
        self,
        *,
        job_id: str,
        worker_id: str,
        attempt: int,
    ) -> ContextManager[None]:
        """Bind one handler context to a live ``(job, owner, attempt)`` lease.

        Lifecycle writes made by the bound handler inherit this fence. The
        persisted lease check happens while this method is invoked. When the
        caller uses ``GuardedDependencyProxy``, that lookup therefore runs
        inside the dependency guard. Entering the returned context manager
        only binds the already-checked identity to this handler context; each
        fenced SQL mutation still rechecks the persisted lease.
        """
        if not job_id.strip() or not worker_id.strip() or type(attempt) is not int:
            raise ValueError("control job execution fence identity is invalid")
        if self._job_execution_fence.get() is not None:
            raise RuntimeError("nested control job execution fences are forbidden")
        self._require_current_job_execution_record(
            job_id=job_id,
            worker_id=worker_id,
            attempt=attempt,
        )

        @contextmanager
        def _bind_execution_identity() -> Iterator[None]:
            token = self._job_execution_fence.set((job_id, worker_id, attempt))
            try:
                yield
            finally:
                self._job_execution_fence.reset(token)

        return _bind_execution_identity()

    def current_execution_job_record(self) -> ControlJobRecord:
        """Resolve the persisted job authorized by this handler's active lease.

        Callers cannot choose an arbitrary job ID and ask for a matching record:
        the job, worker, and attempt come from the active execution fence, then
        the persisted row is re-read and its live lease is checked.
        """

        bound = self._job_execution_fence.get()
        if bound is None:
            raise ControlJobLeaseLostError(
                "control job execution identity is not bound to this handler"
            )
        job_id, worker_id, attempt = bound
        return self._require_current_job_execution_record(
            job_id=job_id,
            worker_id=worker_id,
            attempt=attempt,
        )

    def _current_execution_running_job_proof(
        self,
    ) -> _ControlJobExecutionLifecycleProof:
        """Reconcile the live worker lease with its latest persisted running event."""
        with self._job_transaction():
            bound = self._job_execution_fence.get()
            if bound is None:
                raise ControlJobLeaseLostError(
                    "control job execution identity is not bound to this handler"
                )
            job_id, worker_id, attempt = bound
            record = self._require_current_job_execution_record(
                job_id=job_id,
                worker_id=worker_id,
                attempt=attempt,
            )
            source_event = self._latest_control_job_lifecycle_event_record(
                job_id=job_id,
                event_type="job_running",
            )
            if (
                source_event.payload.get("state") != "running"
                or source_event.payload.get("lease_owner") != worker_id
                or type(source_event.payload.get("attempt")) is not int
                or source_event.payload["attempt"] != attempt
            ):
                raise ControlJobLeaseLostError("control job running event does not bind handler")
            return _ControlJobExecutionLifecycleProof(
                record=record,
                proof_phase="running",
                worker_id=worker_id,
                attempt=attempt,
                source_event=source_event,
            )

    def _reconcile_control_job_creation_envelope(
        self,
        job: ControlJobRecord,
    ) -> tuple[ControlJobExecutionScope, str | None]:
        """Reconcile a persisted job with its unique creation event and outbox copy.

        This is the shared durable owner predicate for live and historical reads.
        It never derives scope from caller payload, progress, ambient context, or a
        mutable manifest pointer.
        """
        try:
            event_payload = self.get_job_created_event_payload(job.job_id)
        except RuntimeError as exc:
            raise ControlJobExecutionAdmissionError(
                "control_job_created_event_unavailable"
            ) from exc
        try:
            outbox_event = self.get_job_created_outbox_event(job.job_id)
        except (RuntimeError, TypeError, json.JSONDecodeError) as exc:
            raise ControlJobExecutionAdmissionError(
                "control_job_created_outbox_unavailable"
            ) from exc
        if outbox_event is None:
            raise ControlJobExecutionAdmissionError("control_job_created_outbox_unavailable")
        if (
            outbox_event.topic != "control.job.created"
            or outbox_event.job_id != job.job_id
            or outbox_event.run_id != job.run_id
        ):
            raise ControlJobExecutionAdmissionError("control_job_created_event_outbox_mismatch")

        outbox_payload = outbox_event.payload
        if not isinstance(outbox_payload, dict):
            raise ControlJobExecutionAdmissionError("control_job_created_event_outbox_mismatch")
        if ("execution_scope" in event_payload) != ("execution_scope" in outbox_payload):
            raise ControlJobExecutionAdmissionError("control_job_created_event_outbox_mismatch")
        for key, value in event_payload.items():
            if key not in outbox_payload or not _json_values_equal_strict(
                outbox_payload[key], value
            ):
                raise ControlJobExecutionAdmissionError("control_job_created_event_outbox_mismatch")
        outbox_only_fields = set(outbox_payload).difference(event_payload)
        if not outbox_only_fields.issubset(_CONTROL_OUTBOX_ENVELOPE_FIELDS):
            raise ControlJobExecutionAdmissionError("control_job_created_event_outbox_mismatch")

        has_typed_scope = "execution_scope" in event_payload
        scope = _control_job_execution_scope_from_event(event_payload)
        outbox_scope = _control_job_execution_scope_from_event(outbox_payload)
        if outbox_scope != scope:
            raise ControlJobExecutionAdmissionError("control_job_created_event_outbox_mismatch")
        expected_fields: dict[str, Any] = {
            "job_id": job.job_id,
            "run_id": job.run_id,
            "job_kind": job.kind,
            "pipeline_id": job.pipeline_id,
            "payload_ref": job.payload_ref,
            "submitted_by": job.submitted_by,
            "requested_execution_profile": job.requested_execution_profile,
            "effective_execution_profile": job.effective_execution_profile,
            "policy_flags": job.policy_flags,
        }
        if has_typed_scope:
            missing_fields = set(_CONTROL_JOB_ADMISSION_STABLE_FIELDS).difference(event_payload)
            if missing_fields:
                raise ControlJobExecutionAdmissionError("control_job_created_stable_field_missing")
        for field_name, expected_value in expected_fields.items():
            if field_name not in event_payload and field_name not in outbox_payload:
                if has_typed_scope:
                    raise ControlJobExecutionAdmissionError(
                        "control_job_created_stable_field_missing"
                    )
                continue
            admitted_value = event_payload.get(field_name, outbox_payload.get(field_name))
            if not _json_values_equal_strict(admitted_value, expected_value):
                raise ControlJobExecutionAdmissionError("control_job_created_stable_field_mismatch")

        if scope.status == "established" and scope.actor_subject != job.submitted_by:
            raise ControlJobExecutionAdmissionError("control_job_execution_actor_subject_mismatch")

        admission_manifest_ref = event_payload.get(
            "capability_manifest_ref",
            outbox_payload.get("capability_manifest_ref"),
        )
        if admission_manifest_ref is not None and not isinstance(admission_manifest_ref, str):
            raise ControlJobExecutionAdmissionError("control_job_created_stable_field_mismatch")
        if has_typed_scope:
            if not _json_values_equal_strict(outbox_payload, event_payload):
                raise ControlJobExecutionAdmissionError("control_job_created_event_outbox_mismatch")
            for field_name in _CONTROL_JOB_ADMISSION_STABLE_FIELDS:
                if field_name not in event_payload:
                    raise ControlJobExecutionAdmissionError(
                        "control_job_created_stable_field_missing"
                    )

        return scope, admission_manifest_ref

    def historical_completed_job_execution_scope(
        self,
        *,
        job_id: str,
        expected_run_id: str,
    ) -> ControlJobExecutionScope:
        """Resolve a completed job's trusted creation-time tenant scope.

        Historical consumers run after the worker lease and ambient tenant context
        have been cleared. This read requires the exact completed job/run identity
        and reuses the durable creation-envelope reconciliation used by live worker
        admission. Unknown legacy scopes remain unusable for owner-scoped reads.
        """
        if (
            type(job_id) is not str
            or not job_id
            or job_id != job_id.strip()
            or type(expected_run_id) is not str
            or not expected_run_id
            or expected_run_id != expected_run_id.strip()
        ):
            raise ControlJobExecutionAdmissionError(
                "control_job_historical_execution_identity_invalid"
            )
        job = self.get_job(job_id)
        if job is None or job.job_id != job_id:
            raise ControlJobExecutionAdmissionError(
                "control_job_historical_execution_job_unavailable"
            )
        if job.state != "completed":
            raise ControlJobExecutionAdmissionError(
                "control_job_historical_execution_job_not_completed"
            )
        if job.run_id != expected_run_id:
            raise ControlJobExecutionAdmissionError("control_job_historical_execution_run_mismatch")
        scope, _ = self._reconcile_control_job_creation_envelope(job)
        if scope.status != "established":
            raise ControlJobExecutionAdmissionError("control_job_execution_scope_not_established")
        return scope

    def current_execution_job_admission(self) -> ControlJobExecutionAdmission:
        """Resolve the leased job's creation-time tenant/cell admission envelope.

        The creation event owns the admitted scope. Legacy events without the
        typed scope remain explicitly unknown; payload, progress, ambient
        context, and the mutable current manifest pointer cannot fill it in.
        """
        job = self.current_execution_job_record()
        scope, admission_manifest_ref = self._reconcile_control_job_creation_envelope(job)

        if job.capability_manifest_ref is None:
            pointer_state: ManifestPointerState = "missing_current"
        elif job.capability_manifest_ref == admission_manifest_ref:
            pointer_state = "admission_current"
        else:
            pointer_state = "refreshed_current"
        return ControlJobExecutionAdmission(
            job=job,
            scope=scope,
            admission_capability_manifest_ref=admission_manifest_ref,
            attempt=job.attempt,
            manifest_pointer_state=pointer_state,
        )

    def claim_child_attempt_budget(
        self, policy: ChildExecutionBudgetPolicy
    ) -> ChildBudgetClaimLocator:
        """Claim one actual job attempt once; a restarted process cannot renew it."""
        from polisyos.runtime.http.services.control.child_execution_budget import (
            ChildExecutionBudgetPolicy,
        )

        if type(policy) is not ChildExecutionBudgetPolicy:
            raise ControlJobExecutionAdmissionError("child_budget_policy_invalid")
        if self.backend != "sqlite":
            raise ControlJobExecutionAdmissionError("child_budget_backend_unsupported")
        with self._job_transaction():
            current = self.current_execution_job_admission()
            job = current.job
            if (
                job.kind != "workflow_run"
                or not job.run_id
                or current.scope.status != "established"
            ):
                raise ControlJobExecutionAdmissionError("child_budget_job_scope_invalid")
            event_type = f"child.budget.attempt.{current.attempt}"
            if self._child_event_row(job.job_id, event_type) is not None:
                raise ControlJobExecutionAdmissionError("child_budget_attempt_already_issued")
            payload = json.dumps(
                {
                    "schema_version": "1.0",
                    "job_id": job.job_id,
                    "run_id": job.run_id,
                    "attempt": current.attempt,
                    "worker_id": job.lease_owner,
                    "policy_id": policy.policy_id,
                    "policy_version": policy.version,
                    "duration_seconds": float(policy.duration_seconds),
                },
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            if len(payload.encode("utf-8")) > 256 * 1024:
                raise ControlJobExecutionAdmissionError("child_budget_event_oversized")
            inserted = self._execute(
                "INSERT INTO control_job_events (job_id, event_type, payload_json, created_at) "
                "VALUES (?, ?, ?, ?)",
                (job.job_id, event_type, payload, _iso(_utc_now())),
            )
            if inserted != 1:
                raise ControlJobExecutionAdmissionError("child_budget_event_write_failed")
        locator = self.read_child_attempt_budget(job.job_id, current.attempt)
        if (
            locator is None
            or locator.run_id != job.run_id
            or locator.worker_id != job.lease_owner
            or (locator.policy_id, locator.policy_version, locator.duration_seconds)
            != (policy.policy_id, policy.version, float(policy.duration_seconds))
        ):
            raise ControlJobExecutionAdmissionError("child_budget_claim_readback_mismatch")
        return locator

    def read_child_attempt_budget(
        self, job_id: str, attempt: int
    ) -> ChildBudgetClaimLocator | None:
        """Freshly resolve one historical committed budget claim and owner scope."""
        from polisyos.runtime.http.services.control.child_execution_budget import (
            ChildBudgetClaimLocator,
            ChildExecutionBudgetPolicy,
        )

        if self._has_active_job_transaction():
            raise ControlJobExecutionAdmissionError("child_budget_fresh_read_required")
        if type(job_id) is not str or not job_id or type(attempt) is not int or attempt < 1:
            raise ControlJobExecutionAdmissionError("child_budget_claim_identity_invalid")
        row = self._child_event_row(job_id, f"child.budget.attempt.{attempt}")
        if row is None:
            return None
        try:
            payload = json.loads(str(row["payload_json"]))
            if (
                type(payload) is not dict
                or set(payload)
                != {
                    "schema_version",
                    "job_id",
                    "run_id",
                    "attempt",
                    "worker_id",
                    "policy_id",
                    "policy_version",
                    "duration_seconds",
                }
                or payload["schema_version"] != "1.0"
                or payload["job_id"] != job_id
                or type(payload["attempt"]) is not int
                or payload["attempt"] != attempt
                or type(payload["run_id"]) is not str
                or not payload["run_id"]
                or type(payload["worker_id"]) is not str
                or not payload["worker_id"]
            ):
                raise ValueError("child_budget_claim_payload_invalid")
            policy = ChildExecutionBudgetPolicy(
                payload["policy_id"], payload["policy_version"], payload["duration_seconds"]
            )
            job = self.get_job(job_id)
            if job is None or job.run_id != payload["run_id"] or job.kind != "workflow_run":
                raise ValueError("child_budget_claim_job_invalid")
            scope, _ = self._reconcile_control_job_creation_envelope(job)
            if scope.status != "established" or not scope.tenant_id or not scope.cell_id:
                raise ValueError("child_budget_claim_scope_invalid")
            return ChildBudgetClaimLocator(
                job_id=job_id,
                run_id=payload["run_id"],
                attempt=attempt,
                worker_id=payload["worker_id"],
                event_id=int(row["event_id"]),
                policy_id=policy.policy_id,
                policy_version=policy.version,
                duration_seconds=float(policy.duration_seconds),
            )
        except (TypeError, ValueError, KeyError, RecursionError) as exc:
            raise ControlJobExecutionAdmissionError("child_budget_claim_event_invalid") from exc

    def child_computation_publication_fence(
        self,
        *,
        grant: _BorrowedExecutionGrant | None = None,
        binding: ChildComputationBinding | None = None,
    ) -> _ChildComputationPublicationFence:
        """Capture the current job's established scope for a bounded child release.

        This is called by trusted lifecycle bootstrap, not with request-selected
        identities. Each later check reconciles the persisted live admission.
        """
        with self._job_transaction():
            admission = self.current_execution_job_admission()
            return _ChildComputationPublicationFence(self, admission, grant=grant, binding=binding)

    @staticmethod
    def _child_job_event_type(kind: str, claim: ChildJobSessionClaim | ChildJobReleaseClaim) -> str:
        """Derive a bounded locator from the complete owner-bound parent basis."""
        if kind not in {"session", "authorization"}:
            raise ValueError("child_release_event_kind_invalid")
        identity = {
            "job_id": claim.control_job_id,
            "run_id": claim.root_run_id,
            "attempt_id": claim.parent_attempt_id,
            "basis_ref": claim.parent_basis_ref.model_dump(mode="json"),
        }
        raw = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return f"child.release.{kind}.{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"

    @staticmethod
    def _child_grant_binding(
        claim: ChildComputationBinding | ChildJobSessionClaim | ChildJobReleaseClaim,
    ) -> dict[str, Any]:
        return {
            "run_id": claim.root_run_id,
            "job_id": claim.control_job_id,
            "attempt_id": claim.parent_attempt_id,
            "basis_ref": json.dumps(
                claim.parent_basis_ref.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
        }

    def _child_event_row(self, job_id: str, event_type: str) -> Any | None:
        length_sql = (
            "length(CAST(payload_json AS BLOB))"
            if self.backend == "sqlite"
            else "octet_length(payload_json)"
        )
        rows = self._fetchall(
            f"SELECT event_id, job_id, event_type, {length_sql} AS payload_bytes, "
            f"CASE WHEN {length_sql} <= 262144 THEN payload_json ELSE NULL END AS payload_json "
            "FROM control_job_events WHERE job_id = ? AND event_type = ? "
            "ORDER BY event_id LIMIT 2",
            (job_id, event_type),
        )
        if len(rows) > 1:
            raise ControlJobExecutionAdmissionError("child_release_event_ambiguous")
        if rows and (rows[0]["payload_json"] is None or int(rows[0]["payload_bytes"]) > 262144):
            raise ControlJobExecutionAdmissionError("child_release_event_payload_oversized")
        return rows[0] if rows else None

    def _verify_child_job_event(
        self,
        locator: ChildJobReleaseLocator,
        claim: ChildJobSessionClaim | ChildJobReleaseClaim,
        *,
        kind: str,
    ) -> None:
        """Fresh-read one committed reserved row and compare the complete claim."""
        from polisyos.core.artifacts.child_release import (
            ChildJobReleaseClaim,
            ChildJobReleaseLocator,
            ChildJobSessionClaim,
        )

        expected_type = ChildJobSessionClaim if kind == "session" else ChildJobReleaseClaim
        if type(locator) is not ChildJobReleaseLocator or type(claim) is not expected_type:
            raise ControlJobExecutionAdmissionError("child_release_event_type_invalid")
        if locator.job_id != claim.control_job_id:
            raise ControlJobExecutionAdmissionError("child_release_event_job_mismatch")
        event_type = self._child_job_event_type(kind, claim)
        row = self._child_event_row(locator.job_id, event_type)
        if row is None or int(row["event_id"]) != locator.event_id:
            raise ControlJobExecutionAdmissionError("child_release_event_unavailable")
        payload_text = str(row["payload_json"])
        if len(payload_text.encode("utf-8")) > 256 * 1024:
            raise ControlJobExecutionAdmissionError("child_release_event_payload_oversized")
        try:
            payload = json.loads(payload_text)
        except (TypeError, ValueError, RecursionError) as exc:
            raise ControlJobExecutionAdmissionError("child_release_event_payload_invalid") from exc
        if (
            type(payload) is not dict
            or set(payload)
            != {"schema_version", "claim", "job_attempt", "lease_owner", "admission_ref"}
            or payload["schema_version"] != "1.0"
            or payload["claim"] != claim.model_dump(mode="json")
            or type(payload["job_attempt"]) is not int
            or payload["job_attempt"] < 1
            or type(payload["lease_owner"]) is not str
            or not payload["lease_owner"]
        ):
            raise ControlJobExecutionAdmissionError("child_release_event_claim_mismatch")
        job = self.get_job(locator.job_id)
        if job is None or job.run_id != claim.root_run_id:
            raise ControlJobExecutionAdmissionError("child_release_event_run_mismatch")
        scope, admission_ref = self._reconcile_control_job_creation_envelope(job)
        if (
            scope.status != "established"
            or scope.tenant_id != claim.tenant_id
            or scope.cell_id != claim.cell_id
            or admission_ref != payload["admission_ref"]
        ):
            raise ControlJobExecutionAdmissionError("child_release_event_scope_mismatch")
        if kind == "authorization":
            session_data = claim.model_dump(
                mode="json",
                exclude={"release_ref", "projection_ref", "released_refs", "parent_effects_sha256"},
            )
            session_claim = ChildJobSessionClaim.model_validate(session_data)
            session_row = self._child_event_row(
                locator.job_id, self._child_job_event_type("session", session_claim)
            )
            if session_row is None:
                raise ControlJobExecutionAdmissionError("child_release_intent_missing")
            self._verify_child_job_event(
                ChildJobReleaseLocator(
                    job_id=locator.job_id, event_id=int(session_row["event_id"])
                ),
                session_claim,
                kind="session",
            )
            session_payload = json.loads(str(session_row["payload_json"]))
            if (session_payload["job_attempt"], session_payload["lease_owner"]) != (
                payload["job_attempt"],
                payload["lease_owner"],
            ):
                raise ControlJobExecutionAdmissionError("child_release_event_lease_mismatch")

    def verify_intent(self, locator: ChildJobReleaseLocator, claim: ChildJobSessionClaim) -> None:
        """Verify an exact committed Core session intent through this actual DB owner."""
        if self._has_active_job_transaction():
            raise ControlJobExecutionAdmissionError("child_release_fresh_read_required")
        self._verify_child_job_event(locator, claim, kind="session")

    def verify_scope(self, locator: ChildJobReleaseLocator, claim: ChildJobScopeClaim) -> None:
        """Fresh-read an exact committed child scope decision and its session."""
        from polisyos.core.artifacts.child_release import ChildJobReleaseLocator, ChildJobScopeClaim

        if self._has_active_job_transaction():
            raise ControlJobExecutionAdmissionError("child_release_fresh_read_required")
        if type(locator) is not ChildJobReleaseLocator or type(claim) is not ChildJobScopeClaim:
            raise ControlJobExecutionAdmissionError("child_scope_claim_invalid")
        if locator.job_id != claim.session.control_job_id:
            raise ControlJobExecutionAdmissionError("child_scope_job_mismatch")
        event_type = f"child.release.scope.{claim.scope_id}"
        row = self._child_event_row(locator.job_id, event_type)
        if row is None or int(row["event_id"]) != locator.event_id:
            raise ControlJobExecutionAdmissionError("child_scope_event_unavailable")
        payload_text = str(row["payload_json"])
        if len(payload_text.encode("utf-8")) > 256 * 1024:
            raise ControlJobExecutionAdmissionError("child_scope_payload_oversized")
        try:
            payload = json.loads(payload_text)
        except (TypeError, ValueError, RecursionError) as exc:
            raise ControlJobExecutionAdmissionError("child_scope_payload_invalid") from exc
        if (
            type(payload) is not dict
            or json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            != payload_text
            or set(payload) != {"schema_version", "claim", "job_attempt", "lease_owner"}
            or payload["schema_version"] != "1.0"
            or payload["claim"] != claim.model_dump(mode="json")
            or type(payload["job_attempt"]) is not int
            or payload["job_attempt"] < 1
            or type(payload["lease_owner"]) is not str
            or not payload["lease_owner"]
        ):
            raise ControlJobExecutionAdmissionError("child_scope_event_mismatch")
        self._verify_child_job_event(claim.session_intent, claim.session, kind="session")
        session = self._child_event_row(
            locator.job_id, self._child_job_event_type("session", claim.session)
        )
        if session is None:
            raise ControlJobExecutionAdmissionError("child_release_intent_missing")
        session_payload = json.loads(str(session["payload_json"]))
        if (payload["job_attempt"], payload["lease_owner"]) != (
            session_payload["job_attempt"],
            session_payload["lease_owner"],
        ):
            raise ControlJobExecutionAdmissionError("child_scope_event_lease_mismatch")

    def verify_release(self, locator: ChildJobReleaseLocator, claim: ChildJobReleaseClaim) -> None:
        """Verify an exact committed Core release authorization through this DB owner."""
        if self._has_active_job_transaction():
            raise ControlJobExecutionAdmissionError("child_release_fresh_read_required")
        self._verify_child_job_event(locator, claim, kind="authorization")

    def _publish_child_release_head(self, *, control_operation: _ChildControlOperation) -> None:
        """Fence one Core-owned head write with the actual SQLite job row."""
        from polisyos.core.artifacts.child_release import ChildJobReleaseClaim
        from polisyos.core.run.child_custody import _ChildControlOperation

        if type(control_operation) is not _ChildControlOperation:
            raise ControlJobExecutionAdmissionError("child_publication_operation_invalid")
        if self.backend != "sqlite" or self._has_active_job_transaction():
            raise ControlJobExecutionAdmissionError("child_publication_backend_unsupported")
        preview = control_operation._preview()
        if type(preview) is not ChildJobReleaseClaim:
            raise ControlJobExecutionAdmissionError("child_publication_claim_invalid")
        with self._job_transaction():
            current = self.current_execution_job_admission()
            control_operation._check_admission(current)
            with control_operation._decision():
                locator, claim = control_operation._publication_parameters()
                if claim != preview:
                    raise ControlJobExecutionAdmissionError("child_publication_claim_changed")
                self._verify_child_job_event(locator, claim, kind="authorization")
                current = self.current_execution_job_admission()
                control_operation._check_admission(current)
                lease_expires_at = current.job.lease_expires_at
                if lease_expires_at is None:
                    raise ControlJobLeaseLostError("child_publication_lease_missing")
                control_operation._commit_publication(locator, claim, lease_expires_at)

    def _record_child_scope(
        self,
        *,
        prepared: ChildPreparedScope | None = None,
        grant: _BorrowedExecutionGrant | None = None,
        fence: _ChildComputationPublicationFence | None = None,
        control_operation: _ChildControlOperation | None = None,
    ) -> tuple[ChildJobReleaseLocator, ChildJobScopeClaim]:
        """Commit one owner-derived scope decision on the actual job transaction."""
        from polisyos.common.borrowed_execution import _BorrowedExecutionGrant
        from polisyos.core.artifacts.child_release import (
            ChildJobReleaseLocator,
            ChildJobScopeClaim,
            ChildReleaseUnavailableError,
        )
        from polisyos.core.run.child_custody import _ChildControlOperation, ChildPreparedScope

        if control_operation is None:
            if (
                type(prepared) is not ChildPreparedScope
                or type(grant) is not _BorrowedExecutionGrant
                or type(fence) is not _ChildComputationPublicationFence
                or fence._store is not self
                or fence._grant is not grant
                or fence._binding is None
            ):
                raise ControlJobExecutionAdmissionError("child_scope_owner_invalid")
            claim = prepared.recompute()
        else:
            if (
                type(control_operation) is not _ChildControlOperation
                or prepared is not None
                or grant is not None
                or fence is not None
            ):
                raise ControlJobExecutionAdmissionError("child_scope_owner_invalid")
            claim = control_operation._preview()
        if type(claim) is not ChildJobScopeClaim:
            raise ControlJobExecutionAdmissionError("child_scope_claim_invalid")

        def require_raw_grant() -> _BorrowedExecutionGrant:
            if grant is None:
                raise ControlJobExecutionAdmissionError("child_scope_owner_invalid")
            return grant

        def admit_raw_scope(owner_claim: ChildJobScopeClaim) -> bytes:
            if prepared is None or fence is None or fence._binding is None:
                raise ControlJobExecutionAdmissionError("child_scope_owner_invalid")
            return prepared.admit(owner_claim, expected_parent=fence._binding)

        commit_started = False

        def mark_commit() -> None:
            nonlocal commit_started
            commit_started = True

        owner_bytes: bytes | None = None
        locator: ChildJobReleaseLocator | None = None
        try:
            with self._job_transaction(commit_admission=mark_commit):
                if fence is not None:
                    fence._reconcile()
                current = self.current_execution_job_admission()
                if control_operation is not None:
                    control_operation._check_admission(current)
                session = claim.session
                resource_binding = self._child_grant_binding(session)
                conn = self._human_decision_transaction.sqlite_connection
                if conn is None:
                    raise ControlJobExecutionAdmissionError("child_scope_sqlite_required")

                def resource_current(lease_expiry: str) -> int:
                    wall_at_decision = datetime.now(timezone.utc)
                    try:
                        if type(lease_expiry) is not str:
                            return 0
                        expiry = datetime.fromisoformat(lease_expiry.replace("Z", "+00:00"))
                        if (
                            expiry.tzinfo is None
                            or expiry.utcoffset() is None
                            or expiry <= wall_at_decision
                            or session.deadline <= wall_at_decision
                        ):
                            return 0
                        if control_operation is not None:
                            control_operation._require_active()
                        else:
                            require_raw_grant().require_parent(**resource_binding)
                    except (RuntimeError, ValueError, TypeError):
                        return 0
                    return 1

                conn.create_function("child_owner_resource_current", 1, resource_current)
                decision = (
                    control_operation._decision()
                    if control_operation is not None
                    else require_raw_grant().admission()
                )
                with decision:
                    owner_bytes = (
                        control_operation._admit(claim)
                        if control_operation is not None
                        else admit_raw_scope(claim)
                    )
                    owner_claim = ChildJobScopeClaim.model_validate_json(owner_bytes)
                    if owner_claim.session.control_job_id != current.job.job_id:
                        raise ControlJobExecutionAdmissionError("child_scope_job_mismatch")
                    self._verify_child_job_event(
                        owner_claim.session_intent, owner_claim.session, kind="session"
                    )
                    session_row = self._child_event_row(
                        current.job.job_id,
                        self._child_job_event_type("session", owner_claim.session),
                    )
                    if session_row is None:
                        raise ControlJobExecutionAdmissionError("child_release_intent_missing")
                    session_payload = json.loads(str(session_row["payload_json"]))
                    if (session_payload["job_attempt"], session_payload["lease_owner"]) != (
                        current.attempt,
                        current.job.lease_owner,
                    ):
                        raise ControlJobExecutionAdmissionError("child_scope_session_lease_changed")
                    event_type = f"child.release.scope.{owner_claim.scope_id}"
                    payload = json.dumps(
                        {
                            "schema_version": "1.0",
                            "claim": owner_claim.model_dump(mode="json"),
                            "job_attempt": current.attempt,
                            "lease_owner": current.job.lease_owner,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                    )
                    if len(payload.encode("utf-8")) > 256 * 1024:
                        raise ControlJobExecutionAdmissionError("child_scope_payload_oversized")
                    inserted = self._execute(
                        "INSERT INTO control_job_events (job_id, event_type, payload_json, created_at) "
                        "SELECT job_id, ?, ?, ? FROM control_jobs WHERE job_id = ? AND state = 'running' "
                        "AND lease_owner = ? AND attempt = ? AND lease_expires_at IS NOT NULL "
                        "AND child_owner_resource_current(lease_expires_at) = 1",
                        (
                            event_type,
                            payload,
                            _iso(_utc_now()),
                            current.job.job_id,
                            current.job.lease_owner,
                            current.attempt,
                        ),
                    )
                    if inserted != 1:
                        raise ControlJobLeaseLostError("child_scope_conditional_admission_refused")
                    row = self._child_event_row(current.job.job_id, event_type)
                    if row is None or str(row["payload_json"]) != payload:
                        raise ControlJobExecutionAdmissionError("child_scope_event_unavailable")
                    locator = ChildJobReleaseLocator(
                        job_id=current.job.job_id, event_id=int(row["event_id"])
                    )
            self.verify_scope(locator, owner_claim)
            return locator, owner_claim
        except (
            OSError,
            sqlite3.Error,
            ControlJobExecutionAdmissionError,
            ChildReleaseUnavailableError,
        ) as exc:
            if not commit_started or owner_bytes is None:
                raise
            raise _unknown_child_scope_admission(
                ChildJobScopeClaim.model_validate_json(owner_bytes), locator
            ) from exc

    def _record_child_job_event(
        self,
        handle: ChildJobSessionIntent | ChildJobReleaseCandidate | None,
        grant: _BorrowedExecutionGrant | None,
        fence: _ChildComputationPublicationFence | None,
        *,
        kind: str,
        control_operation: _ChildControlOperation | None = None,
        on_transaction_attempt: Callable[[], None] | None = None,
        on_transaction_committed: Callable[[], None] | None = None,
    ) -> ChildJobReleaseLocator:
        """Commit an owner-recomputed claim while the actual lease is current."""
        from polisyos.common.borrowed_execution import _BorrowedExecutionGrant
        from polisyos.core.artifacts.child_release import (
            ChildJobReleaseClaim,
            ChildJobReleaseLocator,
            ChildJobSessionClaim,
        )
        from polisyos.core.run.child_custody import (
            _ChildControlOperation,
            ChildJobReleaseCandidate,
            ChildJobSessionIntent,
        )

        handle_type = ChildJobSessionIntent if kind == "session" else ChildJobReleaseCandidate
        claim_type = ChildJobSessionClaim if kind == "session" else ChildJobReleaseClaim
        if control_operation is None:
            if (
                type(handle) is not handle_type
                or type(grant) is not _BorrowedExecutionGrant
                or type(fence) is not _ChildComputationPublicationFence
                or fence._store is not self
                or fence._grant is not grant
            ):
                raise ControlJobExecutionAdmissionError("child_release_authority_handle_invalid")
        elif (
            type(control_operation) is not _ChildControlOperation
            or kind not in {"session", "authorization"}
            or handle is not None
            or grant is not None
            or fence is not None
        ):
            raise ControlJobExecutionAdmissionError("child_release_authority_handle_invalid")
        if self.backend != "sqlite":
            raise ControlJobExecutionAdmissionError(
                "child_release_backend_clock_binding_unsupported"
            )
        if self._has_active_job_transaction():
            raise ControlJobExecutionAdmissionError("child_release_nested_transaction_forbidden")

        def require_raw_grant() -> _BorrowedExecutionGrant:
            if grant is None:
                raise ControlJobExecutionAdmissionError("child_release_authority_handle_invalid")
            return grant

        def require_raw_handle() -> ChildJobSessionIntent | ChildJobReleaseCandidate:
            if handle is None:
                raise ControlJobExecutionAdmissionError("child_release_authority_handle_invalid")
            return handle

        def admit_raw_claim(owner_claim: object) -> bytes:
            if type(handle) is ChildJobSessionIntent and type(owner_claim) is ChildJobSessionClaim:
                return handle.admission(owner_claim)
            if (
                type(handle) is ChildJobReleaseCandidate
                and type(owner_claim) is ChildJobReleaseClaim
            ):
                return handle.admission(owner_claim)
            raise ControlJobExecutionAdmissionError("child_release_authority_claim_invalid")

        claim = (
            require_raw_handle().recompute()
            if control_operation is None
            else control_operation._preview()
        )
        if type(claim) is not claim_type:
            raise ControlJobExecutionAdmissionError("child_release_authority_claim_invalid")
        binding = fence._binding if fence is not None else None
        if control_operation is None and (
            binding is None
            or (
                claim.root_run_id,
                claim.control_job_id,
                claim.parent_attempt_id,
                claim.parent_basis_ref,
                claim.tenant_id,
                claim.cell_id,
                claim.admission_generation,
                claim.deadline,
            )
            != (
                binding.root_run_id,
                binding.control_job_id,
                binding.parent_attempt_id,
                binding.parent_basis_ref,
                binding.tenant_id,
                binding.cell_id,
                binding.admission_generation,
                binding.deadline,
            )
        ):
            raise ControlJobExecutionAdmissionError("child_release_fence_claim_mismatch")
        event_type = self._child_job_event_type(kind, claim)
        resource_binding = self._child_grant_binding(claim)
        if grant is not None:
            grant.require_parent(**resource_binding)
        if on_transaction_attempt is not None:
            on_transaction_attempt()
        with self._job_transaction():
            if fence is not None:
                fence._reconcile()
            current = self.current_execution_job_admission()
            if control_operation is not None:
                control_operation._check_admission(current)
            if (
                current.scope.status != "established"
                or current.job.job_id != claim.control_job_id
                or current.job.run_id != claim.root_run_id
                or current.scope.tenant_id != claim.tenant_id
                or current.scope.cell_id != claim.cell_id
                or not current.scope.actor_authenticated
                or not current.scope.actor_subject
                or not current.job.lease_owner
            ):
                raise ControlJobExecutionAdmissionError("child_release_actual_job_mismatch")
            if (
                kind == "session"
                and self._fetchone(
                    "SELECT 1 FROM control_job_events WHERE job_id = ? "
                    "AND event_type LIKE 'child.budget.attempt.%' AND event_type <> ? LIMIT 1",
                    (claim.control_job_id, f"child.budget.attempt.{current.attempt}"),
                )
                is not None
            ):
                raise ControlJobExecutionAdmissionError("child_prior_budget_attempt_unresolved")
            if (
                kind == "session"
                and self._fetchone(
                    "SELECT 1 FROM child_computation_reissue_sources WHERE source_run_id = ? AND ("
                    "source_tenant_id IS NULL OR source_cell_id IS NULL OR "
                    "(source_tenant_id = ? AND source_cell_id = ?)) LIMIT 1",
                    (claim.root_run_id, claim.tenant_id, claim.cell_id),
                )
                is not None
            ):
                raise ControlJobExecutionAdmissionError("child_session_source_already_reissued")
            payload = {
                "schema_version": "1.0",
                "claim": claim.model_dump(mode="json"),
                "job_attempt": current.attempt,
                "lease_owner": current.job.lease_owner,
                "admission_ref": current.admission_capability_manifest_ref,
            }
            payload_text = json.dumps(
                payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            )
            if len(payload_text.encode("utf-8")) > 256 * 1024:
                raise ControlJobExecutionAdmissionError("child_release_event_payload_oversized")
            if kind == "authorization":
                session_data = claim.model_dump(
                    mode="json",
                    exclude={
                        "release_ref",
                        "projection_ref",
                        "released_refs",
                        "parent_effects_sha256",
                    },
                )
                session_claim = ChildJobSessionClaim.model_validate(session_data)
                session_row = self._child_event_row(
                    claim.control_job_id, self._child_job_event_type("session", session_claim)
                )
                if session_row is None:
                    raise ControlJobExecutionAdmissionError("child_release_intent_missing")
                session_locator = ChildJobReleaseLocator(
                    job_id=claim.control_job_id, event_id=int(session_row["event_id"])
                )
                self._verify_child_job_event(session_locator, session_claim, kind="session")
                session_payload = json.loads(str(session_row["payload_json"]))
                if (session_payload["job_attempt"], session_payload["lease_owner"]) != (
                    current.attempt,
                    current.job.lease_owner,
                ):
                    raise ControlJobExecutionAdmissionError("child_release_intent_lease_changed")
            existing = self._child_event_row(claim.control_job_id, event_type)
            if existing is not None:
                decision = (
                    control_operation._decision()
                    if control_operation is not None
                    else require_raw_grant().publication()
                )
                with decision:
                    owner_claim_bytes = (
                        control_operation._admit(claim)
                        if control_operation is not None
                        else admit_raw_claim(claim)
                    )
                    owner_claim = claim_type.model_validate_json(owner_claim_bytes)
                    owner_event_type = self._child_job_event_type(kind, owner_claim)
                    payload["claim"] = owner_claim.model_dump(mode="json")
                    owner_payload = json.dumps(
                        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                    )
                    if (
                        owner_event_type != event_type
                        or owner_payload != payload_text
                        or str(existing["payload_json"]) != owner_payload
                    ):
                        raise ControlJobExecutionAdmissionError("child_release_event_conflict")
                    claim = owner_claim
            else:
                conn = self._human_decision_transaction.sqlite_connection

                def resource_current(lease_expiry: str) -> int:
                    # The earlier wall sample is the logical owner admission point.
                    # Grant monotonic currentness is checked after that sample;
                    # monotonic non-regression then covers the earlier instant.
                    wall_at_decision = datetime.now(timezone.utc)
                    try:
                        if type(lease_expiry) is not str:
                            return 0
                        expiry = datetime.fromisoformat(lease_expiry.replace("Z", "+00:00"))
                        if (
                            expiry.tzinfo is None
                            or expiry.utcoffset() is None
                            or expiry <= wall_at_decision
                            or claim.deadline <= wall_at_decision
                        ):
                            return 0
                        if control_operation is not None:
                            control_operation._require_active()
                        else:
                            require_raw_grant().require_parent(**resource_binding)
                    except (RuntimeError, ValueError, TypeError):
                        return 0
                    return 1

                # SQLite invokes this owner-bound UDF with the actual locked row.
                # A positive result is a decision, not yet a committed receipt.
                conn.create_function("child_resource_current", 1, resource_current)
                sql = (
                    "INSERT INTO control_job_events (job_id, event_type, payload_json, created_at) "
                    "SELECT job_id, ?, ?, ? FROM control_jobs WHERE job_id = ? AND state = 'running' "
                    "AND lease_owner = ? AND attempt = ? AND lease_expires_at IS NOT NULL "
                    "AND child_resource_current(lease_expires_at) = 1"
                )
                decision = (
                    control_operation._decision()
                    if control_operation is not None
                    else require_raw_grant().publication()
                )
                with decision:
                    owner_claim_bytes = (
                        control_operation._admit(claim)
                        if control_operation is not None
                        else admit_raw_claim(claim)
                    )
                    owner_claim = claim_type.model_validate_json(owner_claim_bytes)
                    owner_event_type = self._child_job_event_type(kind, owner_claim)
                    payload["claim"] = owner_claim.model_dump(mode="json")
                    owner_payload = json.dumps(
                        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                    )
                    if owner_event_type != event_type or owner_payload != payload_text:
                        raise ControlJobExecutionAdmissionError("child_release_event_claim_changed")
                    claim = owner_claim
                    resource_binding = self._child_grant_binding(owner_claim)
                    inserted = self._execute(
                        sql,
                        (
                            owner_event_type,
                            owner_payload,
                            _iso(_utc_now()),
                            owner_claim.control_job_id,
                            current.job.lease_owner,
                            current.attempt,
                        ),
                    )
                    if inserted != 1:
                        raise ControlJobLeaseLostError(
                            "child_release_conditional_admission_refused"
                        )
        # Read on a new transaction/connection after commit; never use an uncommitted row as proof.
        if on_transaction_committed is not None:
            on_transaction_committed()
        row = self._child_event_row(claim.control_job_id, event_type)
        if row is None:
            raise ControlJobExecutionAdmissionError("child_release_commit_not_readable")
        locator = ChildJobReleaseLocator(job_id=claim.control_job_id, event_id=int(row["event_id"]))
        self._verify_child_job_event(locator, claim, kind=kind)
        return locator

    def find_child_job_session(
        self,
        *,
        job_id: str,
        run_id: str,
        parent_attempt_id: str,
        parent_basis_ref: ArtifactRef,
        admission_generation: int | None = None,
    ) -> tuple[ChildJobReleaseLocator, ChildJobSessionClaim] | None:
        """Recover a committed session locator from the exact owner basis."""
        if self._has_active_job_transaction():
            raise ControlJobExecutionAdmissionError("child_release_fresh_read_required")
        from polisyos.core.artifacts.child_release import (
            ChildJobReleaseLocator,
            ChildJobSessionClaim,
        )

        if (
            type(parent_basis_ref) is not ArtifactRef
            or parent_basis_ref.manifest_profile_sha256 is None
            or (
                admission_generation is not None
                and (type(admission_generation) is not int or admission_generation < 0)
            )
        ):
            raise ControlJobExecutionAdmissionError("child_release_lookup_basis_invalid")
        identity = {
            "job_id": job_id,
            "run_id": run_id,
            "attempt_id": parent_attempt_id,
            "basis_ref": parent_basis_ref.model_dump(mode="json"),
        }
        raw = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        event_type = f"child.release.session.{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"
        row = self._child_event_row(job_id, event_type)
        if row is None:
            return None
        text = str(row["payload_json"])
        if len(text.encode("utf-8")) > 256 * 1024:
            raise ControlJobExecutionAdmissionError("child_release_event_payload_oversized")
        try:
            payload = json.loads(text)
            claim = ChildJobSessionClaim.model_validate(payload["claim"])
        except (TypeError, ValueError, KeyError, RecursionError) as exc:
            raise ControlJobExecutionAdmissionError("child_release_event_payload_invalid") from exc
        if (
            claim.control_job_id,
            claim.root_run_id,
            claim.parent_attempt_id,
            claim.parent_basis_ref,
        ) != (job_id, run_id, parent_attempt_id, parent_basis_ref) or (
            admission_generation is not None and claim.admission_generation != admission_generation
        ):
            raise ControlJobExecutionAdmissionError("child_release_lookup_claim_mismatch")
        locator = ChildJobReleaseLocator(job_id=job_id, event_id=int(row["event_id"]))
        self.verify_intent(locator, claim)
        return locator, claim

    def record_child_release_unknown(
        self,
        *,
        locator: ChildJobReleaseLocator,
        run_id: str,
        parent_attempt_id: str,
        parent_basis_ref: ArtifactRef,
        sibling_error_types: tuple[str, ...] = (),
    ) -> None:
        """Expose a verified uncertain child session without terminalizing the job."""
        if (
            type(sibling_error_types) is not tuple
            or len(sibling_error_types) > 32
            or any(
                type(item) is not str or not item or len(item) > 160 for item in sibling_error_types
            )
        ):
            raise ControlJobExecutionAdmissionError("child_release_sibling_diagnostic_invalid")
        recovered = self.find_child_job_session(
            job_id=locator.job_id,
            run_id=run_id,
            parent_attempt_id=parent_attempt_id,
            parent_basis_ref=parent_basis_ref,
        )
        if recovered is None or recovered[0] != locator:
            raise ControlJobExecutionAdmissionError("child_release_unknown_locator_invalid")
        with self._job_transaction():
            current = self.current_execution_job_admission()
            if current.job.job_id != locator.job_id or current.job.run_id != run_id:
                raise ControlJobExecutionAdmissionError("child_release_unknown_job_mismatch")
            row = self._child_event_row(
                locator.job_id, self._child_job_event_type("session", recovered[1])
            )
            if row is None:
                raise ControlJobExecutionAdmissionError("child_release_unknown_locator_invalid")
            recorded = json.loads(str(row["payload_json"]))
            if (recorded["job_attempt"], recorded["lease_owner"]) != (
                current.attempt,
                current.job.lease_owner,
            ):
                raise ControlJobExecutionAdmissionError("child_release_unknown_attempt_mismatch")
            progress = dict(current.job.progress or {})
            reconciliation = progress.get("child_release_reconciliation")
            if reconciliation is None:
                intents: list[dict[str, Any]] = []
            elif (
                type(reconciliation) is dict
                and reconciliation.get("status") == "reconciliation_required"
                and type(reconciliation.get("intents")) is list
                and all(type(item) is dict for item in reconciliation["intents"])
            ):
                intents = list(reconciliation["intents"])
            else:
                raise ControlJobExecutionAdmissionError("child_release_unknown_progress_invalid")
            item = {
                "intent_event_id": locator.event_id,
                "job_id": locator.job_id,
                "root_run_id": run_id,
                "parent_attempt_id": parent_attempt_id,
                "parent_basis_ref": parent_basis_ref.model_dump(mode="json"),
            }
            if item not in intents:
                intents.append(item)
            if len(intents) > 256 or len(json.dumps(intents).encode("utf-8")) > 256 * 1024:
                raise ControlJobExecutionAdmissionError("child_release_unknown_progress_oversized")
            previous_types = (
                reconciliation.get("sibling_error_types", [])
                if type(reconciliation) is dict
                else []
            )
            if (
                type(previous_types) is not list
                or len(previous_types) > 32
                or any(
                    type(item) is not str or not item or len(item) > 160 for item in previous_types
                )
            ):
                raise ControlJobExecutionAdmissionError("child_release_unknown_progress_invalid")
            merged_types = list(dict.fromkeys([*previous_types, *sibling_error_types]))
            if len(merged_types) > 32:
                raise ControlJobExecutionAdmissionError("child_release_sibling_diagnostic_invalid")
            progress["child_release_reconciliation"] = {
                "status": "reconciliation_required",
                "intents": intents,
                "sibling_error_types": merged_types,
            }
            self._upsert_progress_unchecked(job_id=locator.job_id, progress=progress)

    def _source_has_unresolved_child_budget(
        self, run_id: str, tenant_id: str | None, cell_id: str | None
    ) -> bool:
        """Conservatively gate reissue on each actual persisted budget claim."""
        from polisyos.runtime.http.services.control.child_execution_budget import (
            ChildExecutionBudgetPolicy,
        )

        rows = self._fetchall(
            "SELECT e.event_id, e.job_id, e.event_type, "
            "CASE WHEN length(CAST(e.payload_json AS BLOB)) <= 262144 "
            "THEN e.payload_json ELSE NULL END AS payload_json "
            "FROM control_job_events e JOIN control_jobs j ON j.job_id = e.job_id "
            "WHERE j.run_id = ? AND e.event_type LIKE 'child.budget.attempt.%' "
            "ORDER BY e.event_id LIMIT 33",
            (run_id,),
        )
        if len(rows) > 32:
            raise ControlJobExecutionAdmissionError("child_budget_claim_set_oversized")
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
                if (
                    type(payload) is not dict
                    or set(payload)
                    != {
                        "schema_version",
                        "job_id",
                        "run_id",
                        "attempt",
                        "worker_id",
                        "policy_id",
                        "policy_version",
                        "duration_seconds",
                    }
                    or payload["schema_version"] != "1.0"
                    or payload["job_id"] != row["job_id"]
                    or payload["run_id"] != run_id
                    or type(payload["attempt"]) is not int
                    or payload["attempt"] < 1
                    or row["event_type"] != f"child.budget.attempt.{payload['attempt']}"
                    or type(payload["worker_id"]) is not str
                    or not payload["worker_id"]
                ):
                    raise ValueError("child_budget_claim_invalid")
                ChildExecutionBudgetPolicy(
                    payload["policy_id"], payload["policy_version"], payload["duration_seconds"]
                )
                selected = self._child_event_row(row["job_id"], row["event_type"])
                if selected is None or selected["event_id"] != row["event_id"]:
                    raise ValueError("child_budget_claim_identity_invalid")
                job = self.get_job(row["job_id"])
                if job is None or job.run_id != run_id or job.kind != "workflow_run":
                    raise ValueError("child_budget_job_invalid")
                scope, _ = self._reconcile_control_job_creation_envelope(job)
                if scope.status != "established" or not scope.tenant_id or not scope.cell_id:
                    raise ValueError("child_budget_scope_invalid")
            except (TypeError, ValueError, KeyError, RecursionError) as exc:
                raise ControlJobExecutionAdmissionError("child_budget_claim_event_invalid") from exc
            if (
                tenant_id is None
                or cell_id is None
                or (scope.tenant_id, scope.cell_id) == (tenant_id, cell_id)
            ):
                return True
        return False

    def _source_has_conflicting_child_session(
        self, run_id: str, tenant_id: str | None, cell_id: str | None
    ) -> bool:
        """Reconcile a bounded complete source session set before scoped reissue."""
        from polisyos.core.artifacts.child_release import (
            ChildJobReleaseLocator,
            ChildJobSessionClaim,
        )

        rows = self._fetchall(
            "SELECT e.event_id, e.job_id, CASE WHEN length(CAST(e.payload_json AS BLOB)) "
            "<= 262144 THEN e.payload_json ELSE NULL END AS payload_json "
            "FROM control_job_events e JOIN control_jobs j ON j.job_id = e.job_id "
            "WHERE j.run_id = ? AND e.event_type LIKE 'child.release.session.%' "
            "ORDER BY e.event_id LIMIT 33",
            (run_id,),
        )
        if len(rows) > 32:
            raise ControlJobExecutionAdmissionError("child_reissue_session_set_oversized")
        for row in rows:
            try:
                if type(row["payload_json"]) is not str:
                    raise ValueError("bounded_payload_missing")
                payload = json.loads(row["payload_json"])
                claim = ChildJobSessionClaim.model_validate(payload["claim"])
                locator = ChildJobReleaseLocator(job_id=row["job_id"], event_id=row["event_id"])
                self._verify_child_job_event(locator, claim, kind="session")
            except (TypeError, ValueError, KeyError, RecursionError) as exc:
                raise ControlJobExecutionAdmissionError(
                    "child_reissue_session_event_invalid"
                ) from exc
            if (
                claim.root_run_id != run_id
                or tenant_id is None
                or cell_id is None
                or (claim.tenant_id, claim.cell_id) == (tenant_id, cell_id)
            ):
                return True
        return False

    def find_child_job_authorization(
        self, session_claim: ChildJobSessionClaim
    ) -> tuple[ChildJobReleaseLocator, ChildJobReleaseClaim] | None:
        """Recover one exact committed authorization, or return None if absent."""
        if self._has_active_job_transaction():
            raise ControlJobExecutionAdmissionError("child_release_fresh_read_required")
        from polisyos.core.artifacts.child_release import (
            ChildJobReleaseClaim,
            ChildJobReleaseLocator,
            ChildJobSessionClaim,
        )

        if type(session_claim) is not ChildJobSessionClaim:
            raise ControlJobExecutionAdmissionError("child_release_lookup_basis_invalid")
        event_type = self._child_job_event_type("authorization", session_claim)
        row = self._child_event_row(session_claim.control_job_id, event_type)
        if row is None:
            return None
        text = str(row["payload_json"])
        if len(text.encode("utf-8")) > 256 * 1024:
            raise ControlJobExecutionAdmissionError("child_release_event_payload_oversized")
        try:
            payload = json.loads(text)
            claim = ChildJobReleaseClaim.model_validate(payload["claim"])
        except (TypeError, ValueError, KeyError, RecursionError) as exc:
            raise ControlJobExecutionAdmissionError("child_release_event_payload_invalid") from exc
        if (
            ChildJobSessionClaim.model_validate(
                claim.model_dump(
                    mode="json",
                    exclude={
                        "release_ref",
                        "projection_ref",
                        "released_refs",
                        "parent_effects_sha256",
                    },
                )
            )
            != session_claim
        ):
            raise ControlJobExecutionAdmissionError("child_release_lookup_claim_mismatch")
        locator = ChildJobReleaseLocator(
            job_id=session_claim.control_job_id, event_id=int(row["event_id"])
        )
        self.verify_release(locator, claim)
        return locator, claim

    def begin_child_job_session(
        self,
        intent: ChildJobSessionIntent,
        grant: _BorrowedExecutionGrant,
        fence: _ChildComputationPublicationFence,
    ) -> ChildJobReleaseLocator:
        """Persist the exact parent-basis to release-ID locator before child work."""
        return self._record_child_job_event(intent, grant, fence, kind="session")

    def authorize_child_job_release(
        self,
        candidate: ChildJobReleaseCandidate,
        grant: _BorrowedExecutionGrant,
        fence: _ChildComputationPublicationFence,
    ) -> ChildJobReleaseLocator:
        """Authorize the exact selected release at the actual conditional DB decision."""
        return self._record_child_job_event(candidate, grant, fence, kind="authorization")

    def verify_llm_producer_admission(
        self,
        *,
        expected: ControlJobExecutionAdmission,
    ) -> ControlJobExecutionAdmission:
        """Verify a current admission in a short database-only transaction."""
        if type(expected) is not ControlJobExecutionAdmission:
            raise TypeError("llm_producer_job_admission_untyped")
        with self._job_transaction():
            current = self.current_execution_job_admission()
            if (
                current.job.kind != "natural_language_run"
                or current.scope.status != "established"
                or current.scope.actor_authenticated is not True
                or not current.scope.actor_subject
                or current.job.job_id != expected.job.job_id
                or current.job.run_id != expected.job.run_id
                or current.job.lease_owner != expected.job.lease_owner
                or current.attempt != expected.attempt
                or current.scope != expected.scope
                or current.job.effective_execution_profile
                != expected.job.effective_execution_profile
                or current.admission_capability_manifest_ref
                != expected.admission_capability_manifest_ref
            ):
                raise ControlJobLeaseLostError("llm_producer_job_admission_changed")
            return current

    def _require_current_job_execution_record(
        self,
        *,
        job_id: str,
        worker_id: str,
        attempt: int,
    ) -> ControlJobRecord:
        """Re-read and validate one exact persisted running lease."""

        record = self.get_job(job_id)
        now = _utc_now()
        if (
            record is None
            or record.state != "running"
            or record.lease_owner != worker_id
            or record.attempt != attempt
            or record.lease_expires_at is None
            or record.lease_expires_at <= now
        ):
            raise ControlJobLeaseLostError(f"control job lease is not current for {job_id}")
        return record

    def _resolve_job_execution_fence(
        self,
        *,
        job_id: str,
        expected_lease_owner: str | None,
        expected_attempt: int | None,
    ) -> tuple[str, int] | None:
        """Resolve explicit or handler-bound fencing identity for one job write."""
        bound = self._job_execution_fence.get()
        if bound is not None:
            bound_job_id, bound_owner, bound_attempt = bound
            if bound_job_id != job_id:
                raise ControlJobLeaseLostError(
                    f"control job fence is bound to {bound_job_id}, not {job_id}"
                )
            if expected_lease_owner is not None and expected_lease_owner != bound_owner:
                raise ControlJobLeaseLostError("control job owner fence disagrees with handler")
            if expected_attempt is not None and expected_attempt != bound_attempt:
                raise ControlJobLeaseLostError("control job attempt fence disagrees with handler")
            return bound_owner, bound_attempt
        if expected_lease_owner is None and expected_attempt is None:
            return None
        if not expected_lease_owner or type(expected_attempt) is not int or expected_attempt < 1:
            raise ValueError("control job owner and attempt must be supplied together")
        return expected_lease_owner, expected_attempt

    @staticmethod
    def _job_fence_where(
        *,
        job_id: str,
        fence: tuple[str, int] | None,
        now: datetime,
    ) -> tuple[str, tuple[Any, ...]]:
        """Build a parameterized lifecycle-write predicate."""
        if fence is None:
            return "job_id = ? AND state IN ('pending', 'running')", (job_id,)
        owner, attempt = fence
        return (
            "job_id = ? AND state = 'running' AND lease_owner = ? "
            "AND attempt = ? AND lease_expires_at IS NOT NULL AND lease_expires_at > ?",
            (job_id, owner, attempt, _iso(now)),
        )

    @staticmethod
    def _require_fenced_write(
        *,
        job_id: str,
        fence: tuple[str, int] | None,
        affected_rows: int,
    ) -> None:
        """Reject a lost generation instead of silently accepting a no-op."""
        if affected_rows != 1:
            raise ControlJobLeaseLostError(
                f"control job lease no longer permits write for {job_id}"
            )

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
                with self._sqlite_mutation_connection() as conn:
                    cursor = conn.execute(sql, params)
                    return cursor.rowcount == 1
        with self._postgres_mutation_cursor() as cur:
            cur.execute(self._translate_sql(sql), params)
            return cur.rowcount == 1

    def consume_step_up_assertion(
        self,
        *,
        assertion_id: str,
        expires_at: int,
    ) -> bool:
        """Atomically consume one external assertion identifier until expiry."""
        if not isinstance(assertion_id, str) or not assertion_id.strip():
            raise ValueError("assertion_id must be a non-empty string")
        if type(expires_at) is not int:
            raise TypeError("expires_at must be an integer epoch timestamp")
        now = int(_utc_now().timestamp())
        if expires_at <= now:
            return False
        assertion_digest = hashlib.sha256(assertion_id.encode("utf-8")).hexdigest()
        insert_sql = """
            INSERT INTO runtime_step_up_replays (
                assertion_digest, expires_at, consumed_at
            ) VALUES (?, ?, ?)
            ON CONFLICT (assertion_digest) DO NOTHING
        """
        params = (assertion_digest, expires_at, now)
        if self.backend == "sqlite":
            with self._lock:
                with self._sqlite_mutation_connection() as conn:
                    conn.execute(
                        "DELETE FROM runtime_step_up_replays WHERE expires_at <= ?",
                        (now,),
                    )
                    cursor = conn.execute(insert_sql, params)
                    return cursor.rowcount == 1
        with self._postgres_mutation_cursor() as cur:
            cur.execute(
                "DELETE FROM runtime_step_up_replays WHERE expires_at <= %s",
                (now,),
            )
            cur.execute(self._translate_sql(insert_sql), params)
            return cur.rowcount == 1

    def reserve_human_decision_action(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        binding_sha256: str,
        now: datetime,
        lease_seconds: int,
        record_valid_until: datetime,
    ) -> HumanDecisionReservationResult:
        """Atomically reserve the sole live record for one governed action.

        An expired partial attempt is moved to ``recovery_required`` and never
        replaced in the same call.  A committed generation can be replaced only
        after its record validity ends.  The generation number is stable across
        state transitions and advances only for a new reservation.
        """

        self._validate_human_decision_reservation_input(
            tenant_id=tenant_id,
            governed_action_key=governed_action_key,
            reservation_id=reservation_id,
            binding_sha256=binding_sha256,
            now=now,
            lease_seconds=lease_seconds,
            record_valid_until=record_valid_until,
        )
        instant = now.astimezone(timezone.utc)
        lease_expires_at = instant + timedelta(seconds=lease_seconds)
        valid_until = record_valid_until.astimezone(timezone.utc)
        if self.backend == "sqlite":
            return self._reserve_human_decision_sqlite(
                tenant_id=tenant_id,
                governed_action_key=governed_action_key,
                reservation_id=reservation_id,
                binding_sha256=binding_sha256,
                now=instant,
                lease_expires_at=lease_expires_at,
                record_valid_until=valid_until,
            )
        return self._reserve_human_decision_postgres(
            tenant_id=tenant_id,
            governed_action_key=governed_action_key,
            reservation_id=reservation_id,
            binding_sha256=binding_sha256,
            now=instant,
            lease_expires_at=lease_expires_at,
            record_valid_until=valid_until,
        )

    def get_human_decision_reservation(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
    ) -> HumanDecisionReservationRecord | None:
        """Derive the newest reservation generation without a mutable latest row."""

        row = self._fetchone(
            self._human_decision_reservation_select_sql(),
            (tenant_id, governed_action_key),
        )
        return self._row_to_human_decision_reservation(row) if row is not None else None

    def get_human_decision_reservation_generation(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_version: int,
    ) -> HumanDecisionReservationRecord | None:
        """Return one exact historical generation by its immutable version."""

        row = self._fetchone(
            self._human_decision_reservation_generation_select_sql(),
            (tenant_id, governed_action_key, reservation_version),
        )
        return self._row_to_human_decision_reservation(row) if row is not None else None

    @contextmanager
    def hold_human_decision_write_fence(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        reservation_version: int,
        binding_sha256: str,
        acquired_at: datetime,
        expected_record_valid_until: datetime,
    ) -> Iterator[HumanDecisionWriteFence]:
        """Lock one exact empty reservation through artifact/event finalization."""

        acquired = _required_aware_datetime(acquired_at, field_name="acquired_at")
        expected_valid_until = _required_aware_datetime(
            expected_record_valid_until,
            field_name="expected_record_valid_until",
        )
        if getattr(self._human_decision_transaction, "active", False):
            raise RuntimeError("nested human-decision write fence is forbidden")

        def _validate(row: Any) -> HumanDecisionReservationRecord:
            if row is None:
                raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
            record = self._row_to_human_decision_reservation(row)
            if (
                record.tenant_id != tenant_id
                or record.governed_action_key != governed_action_key
                or record.reservation_id != reservation_id
                or record.reservation_version != reservation_version
                or record.binding_sha256 != binding_sha256
                or record.state != "reserved"
                or record.record_ref is not None
                or record.record_sha256 is not None
                or record.durable_event_id is not None
                or record.committed_at is not None
                or record.reconciled_at is not None
                or record.lease_expires_at <= acquired
                or record.record_valid_until != expected_valid_until
                or record.record_valid_until <= acquired
            ):
                raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
            return record

        params = (tenant_id, governed_action_key, reservation_version)
        if self.backend == "sqlite":
            with self._lock, self._sqlite_mutation_connection() as conn:
                try:
                    reservation = _validate(
                        conn.execute(
                            self._human_decision_reservation_generation_select_sql(),
                            params,
                        ).fetchone()
                    )
                    self._human_decision_transaction.active = True
                    fence = HumanDecisionWriteFence(
                        reservation=reservation,
                        _execute=conn.execute,
                        _load=lambda: conn.execute(
                            self._human_decision_reservation_generation_select_sql(),
                            params,
                        ).fetchone(),
                    )
                    yield fence
                    if not fence._finalized:
                        raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
                except Exception:
                    raise
                finally:
                    self._human_decision_transaction.active = False
            return

        with self._postgres_mutation_cursor() as cur:
            reservation = _validate(
                self._postgres_reservation_row(
                    cur,
                    tenant_id=tenant_id,
                    governed_action_key=governed_action_key,
                    reservation_version=reservation_version,
                    for_update=True,
                )
            )
            self._human_decision_transaction.active = True
            try:
                fence = HumanDecisionWriteFence(
                    reservation=reservation,
                    _execute=lambda sql, values: cur.execute(self._translate_sql(sql), values),
                    _load=lambda: self._postgres_reservation_row(
                        cur,
                        tenant_id=tenant_id,
                        governed_action_key=governed_action_key,
                        reservation_version=reservation_version,
                        for_update=False,
                    ),
                )
                yield fence
                if not fence._finalized:
                    raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
            finally:
                self._human_decision_transaction.active = False

    @contextmanager
    def hold_human_decision_recovery_fence(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        reservation_version: int,
    ) -> Iterator[HumanDecisionRecoveryFence]:
        """Lock one exact null-ref recovery generation through event restoration."""

        if getattr(self._human_decision_transaction, "active", False):
            raise RuntimeError("nested human-decision recovery fence is forbidden")

        def _validate(row: Any) -> HumanDecisionReservationRecord:
            if row is None:
                raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
            record = self._row_to_human_decision_reservation(row)
            if (
                record.tenant_id != tenant_id
                or record.governed_action_key != governed_action_key
                or record.reservation_id != reservation_id
                or record.reservation_version != reservation_version
                or record.state != "recovery_required"
                or record.record_ref is not None
                or record.record_sha256 is not None
                or record.durable_event_id is not None
                or record.committed_at is not None
                or record.reconciled_at is not None
            ):
                raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
            return record

        params = (tenant_id, governed_action_key, reservation_version)
        if self.backend == "sqlite":
            with self._lock, self._sqlite_mutation_connection() as conn:
                try:
                    reservation = _validate(
                        conn.execute(
                            self._human_decision_reservation_generation_select_sql(),
                            params,
                        ).fetchone()
                    )
                    self._human_decision_transaction.active = True
                    fence = HumanDecisionRecoveryFence(
                        reservation=reservation,
                        _execute=conn.execute,
                        _load=lambda: conn.execute(
                            self._human_decision_reservation_generation_select_sql(),
                            params,
                        ).fetchone(),
                    )
                    yield fence
                    if not fence._finalized:
                        raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
                except BaseException:
                    raise
                finally:
                    self._human_decision_transaction.active = False
            return

        with self._postgres_mutation_cursor() as cur:
            reservation = _validate(
                self._postgres_reservation_row(
                    cur,
                    tenant_id=tenant_id,
                    governed_action_key=governed_action_key,
                    reservation_version=reservation_version,
                    for_update=True,
                )
            )
            self._human_decision_transaction.active = True
            try:
                fence = HumanDecisionRecoveryFence(
                    reservation=reservation,
                    _execute=lambda sql, values: cur.execute(self._translate_sql(sql), values),
                    _load=lambda: self._postgres_reservation_row(
                        cur,
                        tenant_id=tenant_id,
                        governed_action_key=governed_action_key,
                        reservation_version=reservation_version,
                        for_update=False,
                    ),
                )
                yield fence
                if not fence._finalized:
                    raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
            finally:
                self._human_decision_transaction.active = False

    def mark_human_decision_recovery_required(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        reservation_version: int,
        record_ref: str | None = None,
        record_sha256: str | None = None,
        durable_event_id: str | None = None,
    ) -> HumanDecisionReservationRecord:
        """Freeze a partial attempt for explicit artifact/event reconciliation."""

        supplied_record = (record_ref, record_sha256, durable_event_id)
        if any(value is not None for value in supplied_record) and (
            not all(isinstance(value, str) and value for value in supplied_record)
            or not _is_sha256_ref(record_ref)
            or record_ref != record_sha256
        ):
            raise ValueError("human-decision orphan record binding is invalid")
        sql = """
            UPDATE runtime_human_decision_reservations
            SET state = 'recovery_required', record_ref = ?, record_sha256 = ?,
                durable_event_id = ?
            WHERE tenant_id = ? AND governed_action_key = ?
              AND reservation_id = ? AND reservation_version = ?
              AND state = 'reserved'
              AND record_ref IS NULL AND record_sha256 IS NULL
              AND durable_event_id IS NULL AND committed_at IS NULL
              AND reconciled_at IS NULL
        """
        params = (
            record_ref,
            record_sha256,
            durable_event_id,
            tenant_id,
            governed_action_key,
            reservation_id,
            reservation_version,
        )
        if self.backend == "sqlite":
            with self._lock, self._sqlite_mutation_connection() as conn:
                cursor = conn.execute(sql, params)
                if cursor.rowcount != 1:
                    raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
                row = conn.execute(
                    self._human_decision_reservation_generation_select_sql(),
                    (tenant_id, governed_action_key, reservation_version),
                ).fetchone()
        else:
            with self._postgres_mutation_cursor() as cur:
                cur.execute(self._translate_sql(sql), params)
                if cur.rowcount != 1:
                    raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
                row = self._postgres_reservation_row(
                    cur,
                    tenant_id=tenant_id,
                    governed_action_key=governed_action_key,
                    reservation_version=reservation_version,
                    for_update=False,
                )
        record = self._row_to_human_decision_reservation(row) if row is not None else None
        if (
            record is None
            or record.reservation_id != reservation_id
            or record.reservation_version != reservation_version
            or record.state != "recovery_required"
            or record.record_ref != record_ref
            or record.record_sha256 != record_sha256
            or record.durable_event_id != durable_event_id
        ):
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        return record

    def _reconcile_orphan_human_decision_reservation(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        reservation_version: int,
        reconciled_at: datetime,
    ) -> HumanDecisionReservationRecord:
        """Mark one independently verified signed orphan as historical."""

        reconciled = _required_aware_datetime(reconciled_at, field_name="reconciled_at")
        sql = """
            UPDATE runtime_human_decision_reservations
            SET state = 'reconciled_orphan', reconciled_at = ?
            WHERE tenant_id = ? AND governed_action_key = ?
              AND reservation_id = ? AND reservation_version = ?
              AND state = 'recovery_required'
              AND record_ref IS NOT NULL AND record_sha256 IS NOT NULL
              AND durable_event_id IS NOT NULL
        """
        self._execute(
            sql,
            (
                _human_decision_iso(reconciled),
                tenant_id,
                governed_action_key,
                reservation_id,
                reservation_version,
            ),
        )
        record = self.get_human_decision_reservation_generation(
            tenant_id=tenant_id,
            governed_action_key=governed_action_key,
            reservation_version=reservation_version,
        )
        if (
            record is None
            or record.reservation_id != reservation_id
            or record.state != "reconciled_orphan"
        ):
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        return record

    def _reconcile_empty_human_decision_reservation(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        reservation_version: int,
        reconciled_at: datetime,
    ) -> HumanDecisionReservationRecord:
        """Admit a proven-empty crashed generation so a later call may replace it."""

        reconciled = _required_aware_datetime(reconciled_at, field_name="reconciled_at")
        sql = """
            UPDATE runtime_human_decision_reservations
            SET state = 'reconciled_empty', reconciled_at = ?,
                record_ref = NULL, record_sha256 = NULL,
                durable_event_id = NULL, committed_at = NULL
            WHERE tenant_id = ? AND governed_action_key = ?
              AND reservation_id = ? AND reservation_version = ?
              AND state = 'recovery_required'
              AND record_ref IS NULL AND record_sha256 IS NULL
              AND durable_event_id IS NULL AND committed_at IS NULL
              AND reconciled_at IS NULL
        """
        params = (
            _human_decision_iso(reconciled),
            tenant_id,
            governed_action_key,
            reservation_id,
            reservation_version,
        )
        if self.backend == "sqlite":
            with self._lock, self._sqlite_mutation_connection() as conn:
                cursor = conn.execute(sql, params)
                if cursor.rowcount != 1:
                    raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
                row = conn.execute(
                    self._human_decision_reservation_generation_select_sql(),
                    (tenant_id, governed_action_key, reservation_version),
                ).fetchone()
        else:
            with self._postgres_mutation_cursor() as cur:
                cur.execute(self._translate_sql(sql), params)
                if cur.rowcount != 1:
                    raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
                row = self._postgres_reservation_row(
                    cur,
                    tenant_id=tenant_id,
                    governed_action_key=governed_action_key,
                    reservation_version=reservation_version,
                    for_update=False,
                )
        if row is None:  # pragma: no cover - exact update and transaction invariant
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        return self._row_to_human_decision_reservation(row)

    def _reserve_human_decision_sqlite(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        binding_sha256: str,
        now: datetime,
        lease_expires_at: datetime,
        record_valid_until: datetime,
    ) -> HumanDecisionReservationResult:
        with self._lock, self._sqlite_mutation_connection() as conn:
            row = conn.execute(
                self._human_decision_reservation_select_sql(),
                (tenant_id, governed_action_key),
            ).fetchone()
            if row is None:
                self._insert_human_decision_reservation(
                    conn.execute,
                    tenant_id=tenant_id,
                    governed_action_key=governed_action_key,
                    reservation_id=reservation_id,
                    reservation_version=1,
                    binding_sha256=binding_sha256,
                    now=now,
                    lease_expires_at=lease_expires_at,
                    record_valid_until=record_valid_until,
                    postgres=False,
                )
                row = conn.execute(
                    self._human_decision_reservation_select_sql(),
                    (tenant_id, governed_action_key),
                ).fetchone()
                return HumanDecisionReservationResult(
                    acquired=True,
                    issue_code=None,
                    reservation=self._row_to_human_decision_reservation(row),
                )
            current = self._row_to_human_decision_reservation(row)
            result = self._classify_or_replace_human_decision_reservation(
                execute=conn.execute,
                load=lambda: conn.execute(
                    self._human_decision_reservation_select_sql(),
                    (tenant_id, governed_action_key),
                ).fetchone(),
                current=current,
                reservation_id=reservation_id,
                binding_sha256=binding_sha256,
                now=now,
                lease_expires_at=lease_expires_at,
                record_valid_until=record_valid_until,
                postgres=False,
            )
            return result

    def _reserve_human_decision_postgres(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        binding_sha256: str,
        now: datetime,
        lease_expires_at: datetime,
        record_valid_until: datetime,
    ) -> HumanDecisionReservationResult:
        with self._postgres_mutation_cursor() as cur:
            insert_sql = self._human_decision_reservation_insert_sql(
                on_conflict=True,
            )
            cur.execute(
                self._translate_sql(insert_sql),
                self._human_decision_reservation_insert_params(
                    tenant_id=tenant_id,
                    governed_action_key=governed_action_key,
                    reservation_id=reservation_id,
                    reservation_version=1,
                    binding_sha256=binding_sha256,
                    now=now,
                    lease_expires_at=lease_expires_at,
                    record_valid_until=record_valid_until,
                ),
            )
            if cur.rowcount == 1:
                row = self._postgres_reservation_row(
                    cur,
                    tenant_id=tenant_id,
                    governed_action_key=governed_action_key,
                    for_update=False,
                )
                return HumanDecisionReservationResult(
                    acquired=True,
                    issue_code=None,
                    reservation=self._row_to_human_decision_reservation(row),
                )
            row = self._postgres_reservation_row(
                cur,
                tenant_id=tenant_id,
                governed_action_key=governed_action_key,
                for_update=True,
            )
            if row is None:  # pragma: no cover - ON CONFLICT owner row invariant
                raise RuntimeError("human-decision reservation conflict row disappeared")
            current = self._row_to_human_decision_reservation(row)
            return self._classify_or_replace_human_decision_reservation(
                execute=cur.execute,
                load=lambda: self._postgres_reservation_row(
                    cur,
                    tenant_id=tenant_id,
                    governed_action_key=governed_action_key,
                    for_update=False,
                ),
                current=current,
                reservation_id=reservation_id,
                binding_sha256=binding_sha256,
                now=now,
                lease_expires_at=lease_expires_at,
                record_valid_until=record_valid_until,
                postgres=True,
            )

    def _classify_or_replace_human_decision_reservation(
        self,
        *,
        execute: Any,
        load: Any,
        current: HumanDecisionReservationRecord,
        reservation_id: str,
        binding_sha256: str,
        now: datetime,
        lease_expires_at: datetime,
        record_valid_until: datetime,
        postgres: bool,
    ) -> HumanDecisionReservationResult:
        if current.state == "reserved":
            if current.lease_expires_at > now:
                return HumanDecisionReservationResult(
                    acquired=False,
                    issue_code="DS9-OVERLAPPING-REISSUE",
                    reservation=current,
                )
            recovery_sql = """
                UPDATE runtime_human_decision_reservations
                SET state = 'recovery_required'
                WHERE tenant_id = ? AND governed_action_key = ?
                  AND reservation_id = ? AND reservation_version = ?
                  AND state = 'reserved' AND lease_expires_at <= ?
            """
            execute(
                self._translate_sql(recovery_sql) if postgres else recovery_sql,
                (
                    current.tenant_id,
                    current.governed_action_key,
                    current.reservation_id,
                    current.reservation_version,
                    _human_decision_iso(now),
                ),
            )
            recovered = self._row_to_human_decision_reservation(load())
            return HumanDecisionReservationResult(
                acquired=False,
                issue_code="DS9-RESERVATION-RECOVERY-REQUIRED",
                reservation=recovered,
            )
        if current.state == "recovery_required":
            return HumanDecisionReservationResult(
                acquired=False,
                issue_code="DS9-RESERVATION-RECOVERY-REQUIRED",
                reservation=current,
            )
        if current.state == "committed" and current.record_valid_until > now:
            return HumanDecisionReservationResult(
                acquired=False,
                issue_code="DS9-OVERLAPPING-REISSUE",
                reservation=current,
            )
        next_version = current.reservation_version + 1
        if current.state == "committed":
            expire_sql = """
                UPDATE runtime_human_decision_reservations
                SET state = 'expired'
                WHERE tenant_id = ? AND governed_action_key = ?
                  AND reservation_version = ? AND state = 'committed'
                  AND record_valid_until <= ?
            """
            cursor = execute(
                self._translate_sql(expire_sql) if postgres else expire_sql,
                (
                    current.tenant_id,
                    current.governed_action_key,
                    current.reservation_version,
                    _human_decision_iso(now),
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("human-decision committed generation expiry CAS failed")
        cursor = self._insert_human_decision_reservation(
            execute,
            tenant_id=current.tenant_id,
            governed_action_key=current.governed_action_key,
            reservation_id=reservation_id,
            reservation_version=next_version,
            binding_sha256=binding_sha256,
            now=now,
            lease_expires_at=lease_expires_at,
            record_valid_until=record_valid_until,
            postgres=postgres,
        )
        if cursor.rowcount != 1:
            if not postgres:
                raise RuntimeError("human-decision reservation generation insert lost its CAS")
            winner = self._row_to_human_decision_reservation(load())
            return HumanDecisionReservationResult(
                acquired=False,
                issue_code=(
                    "DS9-RESERVATION-RECOVERY-REQUIRED"
                    if winner.state == "recovery_required"
                    else "DS9-OVERLAPPING-REISSUE"
                ),
                reservation=winner,
            )
        replacement = self._row_to_human_decision_reservation(load())
        return HumanDecisionReservationResult(
            acquired=True,
            issue_code=None,
            reservation=replacement,
        )

    @staticmethod
    def _human_decision_reservation_select_sql() -> str:
        return """
            SELECT tenant_id, governed_action_key, reservation_id,
                   reservation_version, binding_sha256, state, reserved_at,
                   lease_expires_at, record_valid_until, record_ref,
                   record_sha256, durable_event_id, committed_at, reconciled_at
            FROM runtime_human_decision_reservations
            WHERE tenant_id = ? AND governed_action_key = ?
            ORDER BY reservation_version DESC
            LIMIT 1
        """

    @staticmethod
    def _human_decision_reservation_generation_select_sql() -> str:
        return """
            SELECT tenant_id, governed_action_key, reservation_id,
                   reservation_version, binding_sha256, state, reserved_at,
                   lease_expires_at, record_valid_until, record_ref,
                   record_sha256, durable_event_id, committed_at, reconciled_at
            FROM runtime_human_decision_reservations
            WHERE tenant_id = ? AND governed_action_key = ?
              AND reservation_version = ?
        """

    @staticmethod
    def _human_decision_reservation_insert_sql(*, on_conflict: bool) -> str:
        suffix = " ON CONFLICT DO NOTHING" if on_conflict else ""
        return (
            "INSERT INTO runtime_human_decision_reservations ("
            "tenant_id, governed_action_key, reservation_id, reservation_version, "
            "binding_sha256, state, reserved_at, lease_expires_at, record_valid_until, "
            "record_ref, record_sha256, durable_event_id, committed_at, reconciled_at"
            ") VALUES (?, ?, ?, ?, ?, 'reserved', ?, ?, ?, NULL, NULL, NULL, NULL, NULL)" + suffix
        )

    @staticmethod
    def _human_decision_reservation_insert_params(
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        reservation_version: int,
        binding_sha256: str,
        now: datetime,
        lease_expires_at: datetime,
        record_valid_until: datetime,
    ) -> tuple[Any, ...]:
        return (
            tenant_id,
            governed_action_key,
            reservation_id,
            reservation_version,
            binding_sha256,
            _human_decision_iso(now),
            _human_decision_iso(lease_expires_at),
            _human_decision_iso(record_valid_until),
        )

    def _insert_human_decision_reservation(
        self,
        execute: Any,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        reservation_version: int,
        binding_sha256: str,
        now: datetime,
        lease_expires_at: datetime,
        record_valid_until: datetime,
        postgres: bool,
    ) -> Any:
        sql = self._human_decision_reservation_insert_sql(on_conflict=postgres)
        if postgres:
            sql = self._translate_sql(sql)
        return execute(
            sql,
            self._human_decision_reservation_insert_params(
                tenant_id=tenant_id,
                governed_action_key=governed_action_key,
                reservation_id=reservation_id,
                reservation_version=reservation_version,
                binding_sha256=binding_sha256,
                now=now,
                lease_expires_at=lease_expires_at,
                record_valid_until=record_valid_until,
            ),
        )

    def _postgres_reservation_row(
        self,
        cur: Any,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_version: int | None = None,
        for_update: bool,
    ) -> dict[str, Any] | None:
        if reservation_version is None:
            sql = self._human_decision_reservation_select_sql()
            params: tuple[Any, ...] = (tenant_id, governed_action_key)
        else:
            sql = self._human_decision_reservation_generation_select_sql()
            params = (tenant_id, governed_action_key, reservation_version)
        if for_update:
            sql += " FOR UPDATE"
        cur.execute(self._translate_sql(sql), params)
        row = cur.fetchone()
        if row is None:
            return None
        columns = [description[0] for description in (cur.description or ())]
        return dict(zip(columns, row, strict=True))

    @staticmethod
    def _row_to_human_decision_reservation(row: Any) -> HumanDecisionReservationRecord:
        return HumanDecisionReservationRecord(
            tenant_id=str(row["tenant_id"]),
            governed_action_key=str(row["governed_action_key"]),
            reservation_id=str(row["reservation_id"]),
            reservation_version=int(row["reservation_version"]),
            binding_sha256=str(row["binding_sha256"]),
            state=cast("HumanDecisionReservationState", str(row["state"])),
            reserved_at=cast("datetime", _parse_dt(row["reserved_at"])),
            lease_expires_at=cast("datetime", _parse_dt(row["lease_expires_at"])),
            record_valid_until=cast("datetime", _parse_dt(row["record_valid_until"])),
            record_ref=_string_or_none(row["record_ref"]),
            record_sha256=_string_or_none(row["record_sha256"]),
            durable_event_id=_string_or_none(row["durable_event_id"]),
            committed_at=_parse_dt(row["committed_at"]),
            reconciled_at=_parse_dt(row["reconciled_at"]),
        )

    @staticmethod
    def _validate_human_decision_reservation_input(
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        binding_sha256: str,
        now: datetime,
        lease_seconds: int,
        record_valid_until: datetime,
    ) -> None:
        if not tenant_id.strip() or not reservation_id.strip():
            raise ValueError("human-decision reservation identity fields are required")
        if not _is_sha256_ref(governed_action_key) or not _is_sha256_ref(binding_sha256):
            raise ValueError("human-decision reservation hashes are invalid")
        instant = _required_aware_datetime(now, field_name="now")
        valid_until = _required_aware_datetime(
            record_valid_until,
            field_name="record_valid_until",
        )
        if type(lease_seconds) is not int or lease_seconds < 1:
            raise ValueError("human-decision reservation lease must be positive")
        if valid_until <= instant:
            raise ValueError("human-decision record validity must end after reservation")

    def start_pre_admission_attempt(
        self,
        *,
        attempt_id: str,
        request_id: str,
        run_id: str,
        candidate_job_id: str,
        effective_execution_profile: str,
        intent_binding: Mapping[str, Any],
        producer_run_binding: Mapping[str, Any] | None,
        idempotency_key_sha256: str | None,
    ) -> tuple[ControlPreAdmissionAttemptRecord, bool]:
        """Claim the shared route-scoped intent before a billable provider preflight.

        The R3 row is a typed read model and append-only observation stream. Its
        idempotency authority is the shared runtime operation intent identity.
        """
        if len(attempt_id) != 32 or any(c not in "0123456789abcdef" for c in attempt_id):
            raise ValueError("control_pre_admission_attempt_id_invalid")
        if not all(
            value and value == value.strip() for value in (request_id, run_id, candidate_job_id)
        ):
            raise ValueError("control_pre_admission_identity_not_established")
        if (
            idempotency_key_sha256 is None
            or len(idempotency_key_sha256) != 64
            or any(c not in "0123456789abcdef" for c in idempotency_key_sha256)
        ):
            raise ValueError("control_pre_admission_idempotency_key_required")
        normalized_intent = json.loads(
            json.dumps(
                dict(intent_binding),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
        expected_intent_keys = {
            "schema_version",
            "request_content_sha256",
            "tenant_id",
            "cell_id",
            "actor_subject",
            "effective_execution_profile",
            "authorization_permission",
            "authorization_resource_sha256",
        }
        if (
            set(normalized_intent) != expected_intent_keys
            or normalized_intent.get("schema_version")
            != "polisyos.runtime.control_pre_admission_intent.v1"
        ):
            raise ValueError("control_pre_admission_intent_schema_invalid")
        if normalized_intent.get("effective_execution_profile") != effective_execution_profile:
            raise ValueError("control_pre_admission_intent_profile_mismatch")
        request_digest = normalized_intent.get("request_content_sha256")
        resource_digest = normalized_intent.get("authorization_resource_sha256")
        if (
            not isinstance(request_digest, str)
            or len(request_digest) != 71
            or not request_digest.startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in request_digest[7:])
            or normalized_intent.get("authorization_permission") != "runs.launch"
            or not isinstance(resource_digest, str)
            or len(resource_digest) != 71
            or not resource_digest.startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in resource_digest[7:])
        ):
            raise ValueError("control_pre_admission_intent_authorization_basis_invalid")
        tenant_id = normalized_intent.get("tenant_id")
        cell_id = normalized_intent.get("cell_id")
        actor_subject = normalized_intent.get("actor_subject")
        scope_sentinels = {
            "unknown",
            "tenant-unknown",
            "cell-unknown",
            "anonymous",
            "none",
            "null",
        }
        if any(
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or value.casefold() in scope_sentinels
            for value in (tenant_id, cell_id, actor_subject)
        ):
            raise ValueError("control_pre_admission_scope_not_established")
        expected_attempt = hashlib.sha256(
            f"control.nl_pre_admission.v1\0control.runs.nl\0{tenant_id}\0{cell_id}\0{actor_subject}\0{idempotency_key_sha256}".encode()
        ).hexdigest()[:32]
        if attempt_id != expected_attempt:
            raise ValueError("control_pre_admission_attempt_id_not_bound_to_scoped_key")
        normalized_binding = (
            json.loads(
                json.dumps(
                    dict(producer_run_binding),
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
            )
            if producer_run_binding is not None
            else None
        )
        if normalized_binding is not None and (
            set(normalized_binding)
            != {
                "schema_version",
                "run_id",
                "tenant_id",
                "cell_id",
                "profile_id",
                "control_job_id",
            }
            or normalized_binding.get("schema_version")
            != "polisyos.scientist.budget_ledger.producer_run_binding.v1"
            or normalized_binding.get("run_id") != run_id
            or normalized_binding.get("control_job_id") != candidate_job_id
            or normalized_binding.get("profile_id") != effective_execution_profile
            or normalized_binding.get("tenant_id") != tenant_id
            or normalized_binding.get("cell_id") != cell_id
        ):
            raise ValueError("control_pre_admission_producer_binding_mismatch")
        canonical_intent = json.dumps(
            normalized_intent, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        intent_sha256 = hashlib.sha256(canonical_intent.encode("utf-8")).hexdigest()
        operation_key = RuntimeOperationIntentKey(
            purpose="control.nl_pre_admission.v1",
            tenant_id=str(tenant_id),
            cell_id=str(cell_id),
            actor_subject_sha256=hashlib.sha256(str(actor_subject).encode("utf-8")).hexdigest(),
            run_id=run_id,
            intent_id=attempt_id,
            body_sha256=intent_sha256,
            scope_kind="route",
            scope_id="control.runs.nl",
        )
        now = _utc_now()
        with self._job_transaction():
            claim = self.begin_runtime_operation_intent(operation_key)
            if claim.disposition == "body_conflict":
                raise ControlPreAdmissionIdempotencyConflictError(claim.record.intent_id)
            if claim.disposition != "owner":
                record = self.get_pre_admission_attempt(claim.record.intent_id)
                if record is None:
                    raise RuntimeError(
                        "shared runtime intent has no typed pre-admission projection"
                    )
                if record.intent_sha256 != intent_sha256:
                    raise ControlPreAdmissionIdempotencyConflictError(record.attempt_id)
                return record, False
            if claim.owner_token is None:
                raise RuntimeError("shared runtime operation owner credential is absent")
            self._execute(
                """
                INSERT INTO control_pre_admission_attempts (
                    attempt_id, intent_sha256, intent_binding_json,
                    producer_run_binding_json, idempotency_key_sha256, owner_token,
                    request_id, run_id, candidate_job_id, job_id, tenant_id,
                    cell_id, actor_subject, effective_execution_profile, status,
                    producer_event_ids_json, producer_event_observation,
                    failure_code, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, 'started', '[]',
                    'not_applicable', NULL, ?, ?)
                """,
                (
                    attempt_id,
                    intent_sha256,
                    canonical_intent,
                    json.dumps(normalized_binding, sort_keys=True, separators=(",", ":"))
                    if normalized_binding is not None
                    else None,
                    idempotency_key_sha256,
                    claim.owner_token,
                    request_id,
                    run_id,
                    candidate_job_id,
                    tenant_id,
                    cell_id,
                    actor_subject,
                    effective_execution_profile,
                    _iso(now),
                    _iso(now),
                ),
            )
            self._append_pre_admission_attempt_event(
                attempt_id=attempt_id,
                sequence=1,
                event_type="started",
                producer_event_ids=(),
                producer_event_observation="not_applicable",
                producer_no_call_reason=None,
                failure_code=None,
                job_id=None,
                observed_at=now,
                run_id=run_id,
            )
            record = self.get_pre_admission_attempt(attempt_id)
            if record is None:
                raise RuntimeError("control_pre_admission_attempt_start_not_observed")
            return record, True

    def observe_pre_admission_attempt(
        self,
        *,
        attempt_id: str,
        event_type: ControlPreAdmissionAttemptStatus,
        producer_event_ids: tuple[str, ...] = (),
        producer_event_observation: ProducerCallState = "not_applicable",
        producer_no_call_reason: NoCallReason | None = None,
        failure_code: str | None = None,
        job_id: str | None = None,
    ) -> ControlPreAdmissionAttemptRecord:
        """Append a typed observation and project it atomically to outbox/history."""
        if event_type not in {"settled", "admitted", "refused", "cancelled", "failed"}:
            raise ValueError("control_pre_admission_event_type_invalid")
        if not isinstance(producer_event_ids, tuple) or any(
            not isinstance(ref, str) or not ref or ref != ref.strip() for ref in producer_event_ids
        ):
            raise ValueError("control_pre_admission_producer_event_ref_invalid")
        if len(set(producer_event_ids)) != len(producer_event_ids):
            raise ValueError("control_pre_admission_producer_event_ref_duplicate")
        normalized_refs = tuple(sorted(producer_event_ids))
        validate_producer_call_observation(producer_event_observation, producer_no_call_reason)
        if producer_no_call_reason is not None and failure_code != producer_no_call_reason:
            raise ValueError("control_pre_admission_no_call_reason_failure_code_mismatch")
        if failure_code is not None and (
            not failure_code
            or len(failure_code) > 96
            or any(
                c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
                for c in failure_code
            )
        ):
            raise ValueError("control_pre_admission_failure_code_invalid")
        now = _utc_now()
        with self._job_transaction():
            suffix = " FOR UPDATE" if self.backend == "postgres" else ""
            row = self._fetchone(
                f"SELECT * FROM control_pre_admission_attempts WHERE attempt_id = ?{suffix}",
                (attempt_id,),
            )
            if row is None:
                raise KeyError(attempt_id)
            current = str(row["status"])
            raw_old_refs = row["producer_event_ids_json"]
            if not isinstance(raw_old_refs, str) or not raw_old_refs:
                raise RuntimeError("control_pre_admission_stored_producer_refs_missing")
            old_refs_json = json.loads(raw_old_refs)
            if not isinstance(old_refs_json, list):
                raise RuntimeError("control_pre_admission_stored_producer_refs_invalid")
            old_refs = tuple(old_refs_json)
            if old_refs != tuple(sorted(set(old_refs))) or any(
                not isinstance(ref, str) or not ref or ref != ref.strip() for ref in old_refs
            ):
                raise RuntimeError("control_pre_admission_stored_producer_refs_invalid")
            all_refs = tuple(sorted(set(old_refs).union(normalized_refs)))
            old_observation = row["producer_event_observation"]
            old_reason = row["failure_code"] if old_observation == "no_call" else None
            try:
                validate_producer_call_observation(old_observation, old_reason)
            except (TypeError, ValueError) as exc:
                raise RuntimeError("control_pre_admission_stored_observation_invalid") from exc
            if producer_event_observation not in PRODUCER_CALL_STATE_VALUES:
                raise ValueError("control_pre_admission_observation_invalid")
            observation = (
                "unavailable"
                if "unavailable" in {old_observation, producer_event_observation}
                else "complete"
                if "complete" in {old_observation, producer_event_observation}
                else "no_call"
                if "no_call" in {old_observation, producer_event_observation}
                else "not_applicable"
            )
            profile = str(row["effective_execution_profile"])
            if producer_event_observation == "no_call" and (
                event_type != "refused"
                or current != "started"
                or old_observation != "not_applicable"
                or old_refs
                or normalized_refs
                or producer_no_call_reason not in NO_CALL_REASON_VALUES
                or failure_code != producer_no_call_reason
            ):
                raise ValueError("control_pre_admission_no_call_basis_invalid")
            allowed = {
                "started": {"settled", "refused", "cancelled", "failed"},
                "settled": {"admitted", "refused", "cancelled", "failed"},
            }
            if event_type == "admitted" and current == "started" and profile == "dev":
                allowed["started"].add("admitted")
            if event_type not in allowed.get(current, set()):
                raise ValueError("control_pre_admission_transition_invalid")
            if event_type == "settled" and (
                profile not in CONTROL_PRE_ADMISSION_SETTLEMENT_REQUIRED_PROFILES
                or producer_event_observation != "complete"
                or not normalized_refs
            ):
                raise ValueError("control_pre_admission_settlement_evidence_incomplete")
            if current == "started" and event_type in {
                "refused",
                "cancelled",
                "failed",
            }:
                safe_no_call_refusal = (
                    event_type == "refused" and producer_event_observation == "no_call"
                )
                unresolved_provider_call = (
                    event_type in {"cancelled", "failed"}
                    and producer_event_observation == "unavailable"
                )
                if not safe_no_call_refusal and not unresolved_provider_call:
                    raise ValueError(
                        "control_pre_admission_terminal_requires_settlement_or_no_call"
                    )
            if event_type == "admitted":
                if current == "started" and (
                    profile != "dev"
                    or old_observation != "not_applicable"
                    or producer_event_observation != "not_applicable"
                    or old_refs
                    or normalized_refs
                ):
                    raise ValueError("control_pre_admission_direct_admission_unproven")
                if current == "settled" and (
                    profile not in CONTROL_PRE_ADMISSION_SETTLEMENT_REQUIRED_PROFILES
                    or observation != "complete"
                    or not all_refs
                ):
                    raise ValueError("control_pre_admission_admission_settlement_unproven")
            sequence_row = self._fetchone(
                """SELECT COALESCE(MAX(sequence_no), 0) + 1 AS next_sequence
                   FROM control_pre_admission_attempt_events WHERE attempt_id = ?""",
                (attempt_id,),
            )
            sequence = int(sequence_row["next_sequence"])
            event_job_id = job_id or row["job_id"]
            if event_type == "admitted" and (
                not isinstance(event_job_id, str)
                or not event_job_id
                or event_job_id != event_job_id.strip()
            ):
                raise ValueError("control_pre_admission_admission_job_not_established")
            if producer_event_observation == "complete" and not all_refs:
                raise ValueError("control_pre_admission_complete_observation_without_events")
            if producer_event_observation in {"not_applicable", "no_call"} and normalized_refs:
                raise ValueError("control_pre_admission_non_call_observation_with_event_refs")
            changed = self._execute(
                """
                UPDATE control_pre_admission_attempts
                SET status = ?, producer_event_ids_json = ?,
                    producer_event_observation = ?, failure_code = COALESCE(?, failure_code),
                    job_id = COALESCE(?, job_id), updated_at = ?
                WHERE attempt_id = ? AND status = ?
                """,
                (
                    event_type,
                    json.dumps(all_refs, separators=(",", ":")),
                    observation,
                    failure_code,
                    job_id,
                    _iso(now),
                    attempt_id,
                    current,
                ),
            )
            if changed != 1:
                raise ValueError("control_pre_admission_transition_conflict")
            event_id = self._append_pre_admission_attempt_event(
                attempt_id=attempt_id,
                sequence=sequence,
                event_type=event_type,
                producer_event_ids=all_refs,
                producer_event_observation=observation,
                producer_no_call_reason=producer_no_call_reason,
                failure_code=failure_code,
                job_id=event_job_id,
                observed_at=now,
                run_id=str(row["run_id"]),
            )
            operation_key = self._pre_admission_operation_key(row)
            owner_token = _string_or_none(row["owner_token"])
            if owner_token is None:
                raise RuntimeError("pre-admission projection lost its shared owner credential")
            if event_type == "admitted":
                self.complete_runtime_operation_intent_with_observation(
                    key=operation_key,
                    owner_token=owner_token,
                    result_ref_json=json.dumps(
                        {
                            "attempt_id": attempt_id,
                            "run_id": str(row["run_id"]),
                            "job_id": event_job_id,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    event_id=event_id,
                )
                self._execute(
                    "UPDATE control_pre_admission_attempts SET owner_token = NULL WHERE attempt_id = ?",
                    (attempt_id,),
                )
            elif event_type == "refused":
                transition = (
                    self.require_runtime_operation_recovery
                    if observation == "unavailable"
                    else self.refuse_runtime_operation_intent
                )
                transition(
                    key=operation_key,
                    owner_token=owner_token,
                    reason_code=failure_code or "control_pre_admission_refused",
                )
                self._execute(
                    "UPDATE control_pre_admission_attempts SET owner_token = NULL WHERE attempt_id = ?",
                    (attempt_id,),
                )
            elif event_type in {"cancelled", "failed"}:
                self.require_runtime_operation_recovery(
                    key=operation_key,
                    owner_token=owner_token,
                    reason_code=failure_code or f"control_pre_admission_{event_type}",
                )
                self._execute(
                    "UPDATE control_pre_admission_attempts SET owner_token = NULL WHERE attempt_id = ?",
                    (attempt_id,),
                )
            record = self.get_pre_admission_attempt(attempt_id)
            if record is None:
                raise RuntimeError("control_pre_admission_attempt_update_not_observed")
            return record

    def get_pre_admission_attempt_by_idempotency_key(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        actor_subject: str,
        idempotency_key_sha256: str,
    ) -> ControlPreAdmissionAttemptRecord | None:
        """Resolve a route-scoped intent only within the complete authenticated scope."""
        scope = (tenant_id, cell_id, actor_subject)
        if any(
            not isinstance(value, str) or not value or value != value.strip() for value in scope
        ):
            raise ValueError("control_pre_admission_scope_not_established")
        if len(idempotency_key_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in idempotency_key_sha256
        ):
            raise ValueError("control_pre_admission_idempotency_digest_invalid")
        attempt_id = hashlib.sha256(
            f"control.nl_pre_admission.v1\0control.runs.nl\0{tenant_id}\0{cell_id}\0{actor_subject}\0{idempotency_key_sha256}".encode()
        ).hexdigest()[:32]
        record = self.get_pre_admission_attempt(attempt_id)
        if record is None:
            return None
        if (
            record.tenant_id,
            record.cell_id,
            record.actor_subject,
            record.idempotency_key_sha256,
        ) != (tenant_id, cell_id, actor_subject, idempotency_key_sha256):
            return None
        return record

    def get_pre_admission_attempt(
        self,
        attempt_id: str,
    ) -> ControlPreAdmissionAttemptRecord | None:
        """Return the exact durable pre-admission attempt and append-only history."""
        row = self._fetchone(
            "SELECT * FROM control_pre_admission_attempts WHERE attempt_id = ?",
            (attempt_id,),
        )
        if row is None:
            return None
        events = self._fetchall(
            """SELECT * FROM control_pre_admission_attempt_events
               WHERE attempt_id = ? ORDER BY sequence_no""",
            (attempt_id,),
        )
        operation_key = self._pre_admission_operation_key(row)
        shared = self.get_runtime_operation_intent(operation_key)
        if shared.record is None:
            raise RuntimeError("typed pre-admission projection has no shared runtime intent")
        owner = shared.record
        persisted_observation = row["producer_event_observation"]
        persisted_reason = row["failure_code"] if persisted_observation == "no_call" else None
        try:
            validate_producer_call_observation(persisted_observation, persisted_reason)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("pre-admission aggregate observation is invalid") from exc
        expected_state = {
            "started": "pending",
            "settled": "pending",
            "admitted": "completed",
            "refused": (
                "recovery_required" if persisted_observation == "unavailable" else "refused"
            ),
            "cancelled": "recovery_required",
            "failed": "recovery_required",
        }.get(str(row["status"]))
        if expected_state != shared.status:
            raise RuntimeError("typed pre-admission projection diverged from shared owner state")
        owner_token = row["owner_token"]
        if expected_state == "pending":
            if not isinstance(owner_token, str) or not owner_token:
                raise RuntimeError("pending pre-admission projection lost its shared owner token")
        elif owner_token is not None:
            raise RuntimeError("terminal pre-admission projection retained its shared owner token")
        if (
            owner.purpose != operation_key.purpose
            or owner.scope_kind != "route"
            or owner.scope_id != "control.runs.nl"
            or owner.tenant_id != str(row["tenant_id"])
            or owner.cell_id != str(row["cell_id"])
            or owner.actor_subject_sha256 != operation_key.actor_subject_sha256
            or owner.run_id != str(row["run_id"])
            or owner.intent_id != str(row["attempt_id"])
            or owner.body_sha256 != str(row["intent_sha256"])
        ):
            raise RuntimeError("typed pre-admission projection owner binding mismatch")
        try:
            key_digest = str(row["idempotency_key_sha256"])
            if len(key_digest) != 64 or any(
                character not in "0123456789abcdef" for character in key_digest
            ):
                raise ValueError("pre-admission idempotency digest is malformed")
            raw_intent_binding = row["intent_binding_json"]
            if not isinstance(raw_intent_binding, str) or not raw_intent_binding:
                raise ValueError("intent binding is missing")
            intent_binding = json.loads(raw_intent_binding)
            if not isinstance(intent_binding, dict):
                raise ValueError("intent binding must be a JSON object")
            canonical_intent = json.dumps(
                intent_binding, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
            content_sha256 = intent_binding.get("request_content_sha256")
            expected_intent_keys = {
                "schema_version",
                "request_content_sha256",
                "tenant_id",
                "cell_id",
                "actor_subject",
                "effective_execution_profile",
                "authorization_permission",
                "authorization_resource_sha256",
            }
            permission = intent_binding.get("authorization_permission")
            resource_sha256 = intent_binding.get("authorization_resource_sha256")
            binding_is_exact = (
                set(intent_binding) == expected_intent_keys
                and permission == "runs.launch"
                and isinstance(resource_sha256, str)
                and len(resource_sha256) == 71
                and resource_sha256.startswith("sha256:")
                and all(character in "0123456789abcdef" for character in resource_sha256[7:])
                and hashlib.sha256(canonical_intent.encode("utf-8")).hexdigest()
                == str(row["intent_sha256"])
                and intent_binding.get("schema_version")
                == "polisyos.runtime.control_pre_admission_intent.v1"
                and intent_binding.get("tenant_id") == str(row["tenant_id"])
                and intent_binding.get("cell_id") == str(row["cell_id"])
                and intent_binding.get("actor_subject") == str(row["actor_subject"])
                and intent_binding.get("effective_execution_profile")
                == str(row["effective_execution_profile"])
                and isinstance(content_sha256, str)
                and len(content_sha256) == 71
                and content_sha256.startswith("sha256:")
                and all(character in "0123456789abcdef" for character in content_sha256[7:])
            )
            expected_attempt_id = hashlib.sha256(
                f"control.nl_pre_admission.v1\0control.runs.nl\0{row['tenant_id']}\0{row['cell_id']}\0{row['actor_subject']}\0{key_digest}".encode()
            ).hexdigest()[:32]
            if (
                not binding_is_exact
                or expected_attempt_id != str(row["attempt_id"])
                or str(row["effective_execution_profile"]) not in _EXECUTION_PROFILES
            ):
                raise ValueError("pre-admission binding does not match its route owner")
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("typed pre-admission request binding is malformed") from exc
        record = self._row_to_pre_admission_attempt(row, events, owner)
        self._validate_pre_admission_attempt_history(record)
        return record

    @staticmethod
    def _validate_pre_admission_attempt_history(
        record: ControlPreAdmissionAttemptRecord,
    ) -> None:
        """Reconcile every status/event projection before exposing recovery evidence."""
        history = record.history
        if not history or [event.sequence for event in history] != list(range(1, len(history) + 1)):
            raise RuntimeError("pre-admission event history sequence is incomplete")
        if len({event.event_id for event in history}) != len(history):
            raise RuntimeError("pre-admission event history contains duplicate IDs")
        status = ""
        refs: set[str] = set()
        saw_complete = False
        saw_unavailable = False
        saw_no_call = False
        for index, event in enumerate(history):
            if event.event_type not in {
                "started",
                "settled",
                "admitted",
                "refused",
                "cancelled",
                "failed",
            }:
                raise RuntimeError("pre-admission event history has an unknown status")
            try:
                validate_producer_call_observation(
                    event.producer_event_observation, event.producer_no_call_reason
                )
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    "pre-admission event history has an unknown observation"
                ) from exc
            event_refs = tuple(event.producer_event_ids)
            if event_refs != tuple(sorted(set(event_refs))) or any(
                not isinstance(ref, str) or not ref or ref != ref.strip() for ref in event_refs
            ):
                raise RuntimeError("pre-admission event history refs are malformed")
            if event.producer_event_observation == "complete" and not event_refs:
                raise RuntimeError("pre-admission complete observation has no event refs")
            if event.producer_event_observation in {"not_applicable", "no_call"} and event_refs:
                raise RuntimeError("pre-admission no-call observation has event refs")
            if event.producer_event_observation == "no_call" and (
                event.failure_code != event.producer_no_call_reason
                or event.event_type != "refused"
                or status != "started"
                or saw_complete
                or saw_unavailable
                or saw_no_call
                or event.failure_code not in CONTROL_PRE_ADMISSION_NO_CALL_FAILURE_CODES
            ):
                raise RuntimeError(
                    "pre-admission no-call event lacks a trusted pre-call refusal basis"
                )
            if event.job_id is not None and event.job_id != record.candidate_job_id:
                raise RuntimeError("pre-admission event job does not match the immutable candidate")
            if not refs.issubset(set(event_refs)):
                raise RuntimeError("pre-admission event refs are not append-only")
            refs.update(event_refs)
            expected_observation = (
                "unavailable"
                if saw_unavailable or event.producer_event_observation == "unavailable"
                else "complete"
                if saw_complete or event.producer_event_observation == "complete"
                else "no_call"
                if saw_no_call or event.producer_event_observation == "no_call"
                else "not_applicable"
            )
            if event.producer_event_observation != expected_observation:
                raise RuntimeError("pre-admission event observation is not cumulative")
            saw_complete = saw_complete or event.producer_event_observation == "complete"
            saw_unavailable = saw_unavailable or event.producer_event_observation == "unavailable"
            saw_no_call = saw_no_call or event.producer_event_observation == "no_call"
            if index == 0:
                if (
                    event.event_type != "started"
                    or event.producer_event_observation != "not_applicable"
                    or event_refs
                    or event.failure_code is not None
                    or event.producer_no_call_reason is not None
                    or event.job_id is not None
                ):
                    raise RuntimeError("pre-admission history does not begin with an empty start")
            else:
                allowed = {
                    "started": {"settled", "refused", "cancelled", "failed"},
                    "settled": {"admitted", "refused", "cancelled", "failed"},
                }
                if (
                    event.event_type == "admitted"
                    and status == "started"
                    and record.effective_execution_profile == "dev"
                ):
                    allowed["started"].add("admitted")
                if event.event_type not in allowed.get(status, set()):
                    raise RuntimeError("pre-admission event history transition is invalid")
                if event.event_type == "settled" and (
                    record.effective_execution_profile
                    not in CONTROL_PRE_ADMISSION_SETTLEMENT_REQUIRED_PROFILES
                    or event.producer_event_observation != "complete"
                    or not event_refs
                ):
                    raise RuntimeError("pre-admission settled event lacks complete refs")
                if status == "started" and event.event_type in {
                    "refused",
                    "cancelled",
                    "failed",
                }:
                    safe_no_call_refusal = (
                        event.event_type == "refused"
                        and event.producer_event_observation == "no_call"
                    )
                    unresolved_provider_call = (
                        event.event_type in {"cancelled", "failed"}
                        and event.producer_event_observation == "unavailable"
                    )
                    if not safe_no_call_refusal and not unresolved_provider_call:
                        raise RuntimeError(
                            "pre-admission terminal event lacks settlement, no-call, or unresolved evidence"
                        )
                if event.event_type == "admitted":
                    if event.job_id != record.candidate_job_id:
                        raise RuntimeError("pre-admission admission lacks its exact created job")
                    if status == "started" and (
                        record.effective_execution_profile != "dev"
                        or event.producer_event_observation != "not_applicable"
                        or event_refs
                    ):
                        raise RuntimeError(
                            "pre-admission direct admission lacks a dev no-preflight basis"
                        )
                    if status == "settled" and (
                        record.effective_execution_profile
                        not in CONTROL_PRE_ADMISSION_SETTLEMENT_REQUIRED_PROFILES
                        or not saw_complete
                        or not refs
                    ):
                        raise RuntimeError(
                            "pre-admission admission lacks settled producer evidence"
                        )
            if (
                event.event_type in {"refused", "cancelled", "failed"}
                and event.producer_event_observation == "complete"
                and not event_refs
            ):
                raise RuntimeError("pre-admission terminal event lacks its complete producer refs")
            status = event.event_type
        aggregate_observation = (
            "unavailable"
            if saw_unavailable
            else "complete"
            if saw_complete
            else "no_call"
            if saw_no_call
            else "not_applicable"
        )
        if (
            history[-1].event_type != record.status
            or tuple(sorted(refs)) != record.producer_event_ids
            or aggregate_observation != record.producer_event_observation
            or history[-1].producer_no_call_reason != record.producer_no_call_reason
            or (
                record.producer_event_observation == "no_call"
                and record.failure_code != record.producer_no_call_reason
            )
            or history[-1].job_id != record.job_id
            or (record.job_id is not None and record.job_id != record.candidate_job_id)
        ):
            raise RuntimeError("pre-admission attempt and append-only history diverged")
        if record.status in {"refused", "cancelled", "failed"}:
            expected_reason = history[-1].failure_code or f"control_pre_admission_{record.status}"
            if record.shared_owner.reason_code != expected_reason:
                raise RuntimeError("terminal shared owner reason is not joined to its status event")
        if record.status == "admitted":
            if record.shared_owner.event_id != history[-1].event_id:
                raise RuntimeError("completed shared owner is not joined to the admitted event")
            raw_result_ref = record.shared_owner.result_ref_json
            if not isinstance(raw_result_ref, str) or not raw_result_ref:
                raise RuntimeError("completed shared owner result is missing")
            try:
                result_ref = json.loads(raw_result_ref)
            except json.JSONDecodeError as exc:
                raise RuntimeError("completed shared owner result is malformed") from exc
            if result_ref != {
                "attempt_id": record.attempt_id,
                "run_id": record.run_id,
                "job_id": record.job_id,
            }:
                raise RuntimeError(
                    "completed shared owner result does not bind the admitted attempt"
                )

    @staticmethod
    def _pre_admission_operation_key(row: Any) -> RuntimeOperationIntentKey:
        """Reconstruct only the exact route scope stored with this typed projection."""
        return RuntimeOperationIntentKey(
            purpose="control.nl_pre_admission.v1",
            tenant_id=str(row["tenant_id"]),
            cell_id=str(row["cell_id"]),
            actor_subject_sha256=hashlib.sha256(
                str(row["actor_subject"]).encode("utf-8")
            ).hexdigest(),
            run_id=str(row["run_id"]),
            intent_id=str(row["attempt_id"]),
            body_sha256=str(row["intent_sha256"]),
            scope_kind="route",
            scope_id="control.runs.nl",
        )

    def _append_pre_admission_attempt_event(
        self,
        *,
        attempt_id: str,
        sequence: int,
        event_type: ControlPreAdmissionAttemptStatus,
        producer_event_ids: tuple[str, ...],
        producer_event_observation: ProducerCallState,
        producer_no_call_reason: NoCallReason | None,
        failure_code: str | None,
        job_id: str | None,
        observed_at: datetime,
        run_id: str,
    ) -> str:
        event_id = (
            self._pre_admission_event_id_factory()
            if self._pre_admission_event_id_factory is not None
            else uuid.uuid4().hex
        )
        if len(event_id) != 32 or any(
            character not in "0123456789abcdef" for character in event_id
        ):
            raise ValueError("control_pre_admission_event_id_invalid")
        event_payload = {
            "attempt_id": attempt_id,
            "event_id": event_id,
            "sequence": sequence,
            "event_type": event_type,
            "producer_event_ids": list(producer_event_ids),
            "producer_event_observation": producer_event_observation,
            "producer_no_call_reason": producer_no_call_reason,
            "failure_code": failure_code,
            "job_id": job_id,
        }
        self._execute(
            """INSERT INTO control_pre_admission_attempt_events (
                   event_id, attempt_id, sequence_no, event_type, payload_json, created_at
               ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                attempt_id,
                sequence,
                event_type,
                json.dumps(event_payload, sort_keys=True, separators=(",", ":")),
                _iso(observed_at),
            ),
        )
        self.enqueue_outbox_event(
            topic="control.pre_admission_attempt.observed",
            event_key=f"{attempt_id}:{sequence}",
            run_id=run_id,
            payload=event_payload,
        )
        return event_id

    def _has_active_job_transaction(self) -> bool:
        """Report this Store worker's actual transaction ownership without database I/O."""
        return (
            getattr(self._human_decision_transaction, "sqlite_connection", None) is not None
            or getattr(self._human_decision_transaction, "postgres_cursor", None) is not None
        )

    def prepare_job_creation(
        self,
        *,
        job_id: str,
        initial_state: Literal["pending", "failed"],
        creation_event_payload: dict[str, Any],
    ) -> _ControlJobCreationBasis:
        """Freeze a creation basis without a SQL row, event ID or recorded timestamp.

        Diagnostic CAS work can use this candidate basis outside a writer lock.
        Only create_job can reconcile the subsequently recorded source event and
        outbox before publishing diagnostics/progress. The basis grants no lease,
        current-source admission, authorization or permission.
        """
        if initial_state not in {"pending", "failed"}:
            raise ValueError("control_job_initial_state_invalid")
        payload = {**creation_event_payload, "state": initial_state}
        if payload.get("job_id") != job_id:
            raise ValueError("control_job_creation_basis_job_mismatch")
        payload_json = json.dumps(payload, sort_keys=True)
        return _ControlJobCreationBasis(
            job_id=job_id,
            initial_state=initial_state,
            prepared_at=_utc_now(),
            source_payload_json=payload_json,
            source_payload_sha256="sha256:" + hashlib.sha256(payload_json.encode()).hexdigest(),
            creation_owner=self._creation_plan_owner,
        )

    def _reconcile_admission_diagnostic_basis(
        self,
        *,
        record: ControlJobRecord,
        source: _ControlJobLifecycleSourceEventRecord,
        event: DiagnosticEvent,
        payload: dict[str, Any],
        binding: _ControlJobAdmissionDiagnosticBinding,
    ) -> None:
        """Bind v2 candidate bytes to actual unique creation/outbox rows with SQL only."""
        scope, _ = self._reconcile_control_job_creation_envelope(record)
        source_refs = tuple(
            source.payload[key]
            for key in ("payload_ref", "capability_manifest_ref")
            if source.payload.get(key) is not None
        )
        expected_scope = {
            "schema_version": "polisyos.runtime.control_execution_scope.v1",
            "status": scope.status,
            "source": "job_admission",
            "limitation_code": (
                None
                if scope.status == "established"
                else "control_job_execution_scope_not_established"
            ),
        }
        allowed_types = {
            "polisyos.runtime.diagnostic.cas_write.v1",
            "polisyos.runtime.diagnostic.phase_transition.v1",
            "polisyos.runtime.diagnostic.scope_limited.v1",
        }
        if (
            binding.control_job_id != record.job_id
            or binding.control_run_id != record.run_id
            or binding.source_event_job_state != source.payload.get("state")
            or binding.source_event_payload_sha256 != source.payload_sha256
            or binding.bound_job_record_refs != source_refs
            or source.job_id != record.job_id
            or source.event_type != "job_created"
            or source.event_id < 1
            or source.created_at.tzinfo is None
            or event.job_id != record.job_id
            or event.run_id != str(record.run_id or "run-unknown")
            or event.phase != "job_admission"
            or event.event_type not in allowed_types
            or event.producer_component != "polisyos.runtime.control"
            or (
                event.event_type == "polisyos.runtime.diagnostic.phase_transition.v1"
                and (
                    event.state_after != binding.source_event_job_state
                    or event.event_time != source.created_at
                )
            )
            or event.execution_profile != record.effective_execution_profile
            or event.tenant_id != (scope.tenant_id or "tenant-unknown")
            or event.cell_id != (scope.cell_id or "cell-unknown")
            or "attempt" in payload
            or not _json_values_equal_strict(payload.get("execution_scope"), expected_scope)
        ):
            raise ControlJobExecutionAdmissionError(
                "control_job_admission_diagnostic_basis_mismatch"
            )

    def get_job_admission_diagnostic_source_event_record(
        self, *, event_id: str, payload: dict[str, Any]
    ) -> _ControlJobLifecycleSourceEventRecord:
        """Resolve actual event ID/time from a content-bound v2 diagnostic payload.

        The event-log owner resolves CAS bytes before this DB-only read. This
        result describes historical admission, never a current worker proof.
        """
        digest = "sha256:" + hashlib.sha256(_payload_bytes(payload)).hexdigest()
        binding = _ControlJobAdmissionDiagnosticBinding.model_validate_json(
            json.dumps(payload.get("control_job_execution_binding"), sort_keys=True)
        )
        with self._job_transaction():
            diagnostics = self.list_diagnostic_events(event_id=event_id, limit=2)
            if len(diagnostics) != 1 or diagnostics[0].payload_sha256 != digest:
                raise ControlJobExecutionAdmissionError(
                    "control_job_admission_diagnostic_not_bound"
                )
            diagnostic = diagnostics[0]
            record = self.get_job(diagnostic.event.job_id)
            if record is None:
                raise ControlJobExecutionAdmissionError("control_job_admission_job_missing")
            source = self._get_job_created_source_event_record(record.job_id)
            self._reconcile_admission_diagnostic_basis(
                record=record,
                source=source,
                event=diagnostic.event,
                payload=payload,
                binding=binding,
            )
            return source

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
        creation_event_payload: dict[str, Any] | None = None,
        initial_state: Literal["pending", "failed"] = "pending",
        initial_error_message: str | None = None,
        initial_progress: dict[str, Any] | None = None,
        creation_basis: _ControlJobCreationBasis | None = None,
        prepared_admission_diagnostics: tuple[_PreparedDiagnosticEvent, ...] = (),
        diagnostic_preparation_failed: bool = False,
        pre_admission_attempt_id: str | None = None,
        pre_admission_outcome: Literal["admitted", "refused"] | None = None,
        pre_admission_producer_event_observation: ProducerCallState | None = None,
        pre_admission_no_call_reason: NoCallReason | None = None,
        pre_admission_failure_code: str | None = None,
        child_reissue_source_run_id: str | None = None,
        child_reissue_source_tenant_id: str | None = None,
        child_reissue_source_cell_id: str | None = None,
    ) -> ControlJobRecord:
        """Publish one job and prepared admission diagnostics atomically with SQL only.

        Snapshot/registry validation and CAS I/O precede the writer transaction.
        The v2 creation basis never supplies actual event IDs or recorded times;
        this owner records them normally, reconciles the actual source/outbox,
        then appends prepared diagnostics and their initial progress links.
        """
        if child_reissue_source_run_id is not None and (
            type(child_reissue_source_run_id) is not str
            or not child_reissue_source_run_id
            or len(child_reissue_source_run_id) > 512
            or kind != "workflow_run"
            or not run_id
            or run_id == child_reissue_source_run_id
        ):
            raise ValueError("child_reissue_source_invalid")
        if child_reissue_source_run_id is None and (
            child_reissue_source_tenant_id is not None or child_reissue_source_cell_id is not None
        ):
            raise ValueError("child_reissue_source_scope_without_run")
        if any(
            value is not None and (type(value) is not str or not value or len(value) > 512)
            for value in (child_reissue_source_tenant_id, child_reissue_source_cell_id)
        ):
            raise ValueError("child_reissue_source_scope_invalid")
        if initial_state not in {"pending", "failed"}:
            raise ValueError("control_job_initial_state_invalid")
        if initial_state == "failed" and not initial_error_message:
            raise ValueError("control_job_initial_failure_missing")
        if initial_state == "pending" and initial_error_message is not None:
            raise ValueError("control_job_pending_has_initial_failure")
        if (pre_admission_attempt_id is None) != (pre_admission_outcome is None):
            raise ValueError("control_job_pre_admission_link_incomplete")
        if pre_admission_attempt_id is not None and (
            (initial_state == "pending") != (pre_admission_outcome == "admitted")
        ):
            raise ValueError("control_job_pre_admission_outcome_mismatch")
        if creation_basis is not None and self._has_active_job_transaction():
            raise ControlJobExecutionAdmissionError(
                "control_job_prepared_creation_nested_transaction"
            )
        if type(diagnostic_preparation_failed) is not bool:
            raise TypeError("control_job_diagnostic_preparation_status_invalid")
        if creation_basis is None and (
            prepared_admission_diagnostics or diagnostic_preparation_failed
        ):
            raise ValueError("control_job_diagnostics_require_creation_basis")
        if creation_basis is not None and (
            type(creation_basis) is not _ControlJobCreationBasis
            or creation_basis.creation_owner is not self._creation_plan_owner
            or creation_basis.job_id != job_id
            or creation_basis.initial_state != initial_state
            or creation_basis.source_payload_json
            != json.dumps(
                {**dict(creation_event_payload or {}), "state": initial_state}, sort_keys=True
            )
        ):
            raise ValueError("control_job_creation_basis_mismatch")
        # Registry/filesystem reads, parsing and complete payload hashing happen
        # before the SQL lock. No provider callback enters the transaction.
        prepared_values = []
        for prepared in prepared_admission_diagnostics:
            if type(prepared) is not _PreparedDiagnosticEvent:
                raise TypeError("control_job_diagnostic_preparation_type_invalid")
            event, payload = prepared.publication_values()
            if payload is None:
                raise ValueError("control_job_diagnostic_preparation_payload_missing")
            binding = _ControlJobAdmissionDiagnosticBinding.model_validate_json(
                json.dumps(payload.get("control_job_execution_binding"), sort_keys=True)
            )
            prepared_values.append((prepared, event, payload, binding))
        created_at = _utc_now()
        progress: dict[str, Any] = append_evidence_spine_handoff(
            dict(initial_progress or {}),
            control_plane_handoff(
                handoff_kind="nl_request_creation",
                job_id=job_id,
                producer_ref="runtime.api.nl_request",
                consumer_ref="runtime.control_plane_store",
                input_refs=tuple(
                    ref for ref in (payload_ref, capability_manifest_ref, "control.request") if ref
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL, 0, ?)
        """
        params = (
            job_id,
            kind,
            initial_state,
            run_id,
            pipeline_id,
            requested_execution_profile,
            effective_execution_profile,
            json.dumps(policy_flags, sort_keys=True),
            capability_manifest_ref,
            payload_ref,
            submitted_by,
            _iso(created_at),
            _iso(created_at) if initial_state == "failed" else None,
            initial_error_message,
        )
        created_event_payload = dict(creation_event_payload or {})
        created_event_payload["state"] = initial_state
        with self._job_transaction():
            if child_reissue_source_run_id is not None and self.backend == "sqlite":
                if self._source_has_conflicting_child_session(
                    child_reissue_source_run_id,
                    child_reissue_source_tenant_id,
                    child_reissue_source_cell_id,
                ) or self._source_has_unresolved_child_budget(
                    child_reissue_source_run_id,
                    child_reissue_source_tenant_id,
                    child_reissue_source_cell_id,
                ):
                    raise ControlJobExecutionAdmissionError(
                        "child_reissue_source_reconciliation_required"
                    )
                self._execute(
                    "INSERT INTO child_computation_reissue_sources "
                    "(source_run_id, source_tenant_id, source_cell_id, reissue_job_id) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        child_reissue_source_run_id,
                        child_reissue_source_tenant_id,
                        child_reissue_source_cell_id,
                        job_id,
                    ),
                )
            self._execute(sql, params)
            self.upsert_progress(job_id=job_id, progress=progress)
            self.append_event(
                job_id=job_id,
                event_type="job_created",
                payload=created_event_payload,
            )
            record = self.get_job(job_id)
            if record is None:
                raise RuntimeError(f"Failed to persist control job {job_id}")
            self._emit_job_outbox_event(
                record=record,
                event_type="job_created",
                payload=created_event_payload,
            )
            if creation_basis is not None:
                source = self._get_job_created_source_event_record(job_id)
                if source.payload_sha256 != creation_basis.source_payload_sha256:
                    raise ControlJobExecutionAdmissionError(
                        "control_job_creation_basis_content_mismatch"
                    )
                scope, _ = self._reconcile_control_job_creation_envelope(record)
                diagnostic_ids: list[str] = []
                authority_withheld = False
                for prepared, event, payload, binding in prepared_values:
                    if event.event_type == "polisyos.runtime.diagnostic.phase_transition.v1":
                        # event_time is outside the CAS payload hash. The job
                        # transition occurs now, not at candidate preparation.
                        event = event.model_copy(update={"event_time": source.created_at})
                    self._reconcile_admission_diagnostic_basis(
                        record=record, source=source, event=event, payload=payload, binding=binding
                    )
                    if event.event_id in diagnostic_ids or self.list_diagnostic_events(
                        event_id=event.event_id, limit=1
                    ):
                        raise ControlJobExecutionAdmissionError(
                            "control_job_prepared_diagnostic_already_exists"
                        )
                    self.append_diagnostic_event(
                        event=event,
                        payload_ref=prepared.payload_ref,
                        payload_inline=payload if prepared.inline_payload else None,
                        payload_sha256=prepared.payload_sha256,
                    )
                    diagnostic_ids.append(event.event_id)
                    authority_withheld |= (
                        event.event_type == "polisyos.runtime.diagnostic.scope_limited.v1"
                    )
                diagnostic_progress: dict[str, Any] = {
                    "diagnostic_event_ids": diagnostic_ids,
                    "diagnostic_event_authority": (
                        "scope_limited" if authority_withheld else "progress_reference_only"
                    ),
                    "diagnostic_event_scope_status": scope.status,
                }
                if scope.status == "not_established":
                    diagnostic_progress["diagnostic_event_limitation_code"] = (
                        "control_job_execution_scope_not_established"
                    )
                if diagnostic_preparation_failed:
                    diagnostic_progress["diagnostic_event_preparation_status"] = "limited"
                    diagnostic_progress["diagnostic_event_preparation_limitation_code"] = (
                        "runtime_diagnostic_event_persistence_failed"
                    )
                self._upsert_progress_unchecked(
                    job_id=job_id, progress={**record.progress, **diagnostic_progress}
                )
                record = self.get_job(job_id)
                if record is None:
                    raise RuntimeError(f"Failed to initialize control job {job_id}")
            if pre_admission_attempt_id is not None and pre_admission_outcome is not None:
                self.observe_pre_admission_attempt(
                    attempt_id=pre_admission_attempt_id,
                    event_type=pre_admission_outcome,
                    producer_event_observation=(
                        pre_admission_producer_event_observation or "not_applicable"
                    ),
                    producer_no_call_reason=pre_admission_no_call_reason,
                    failure_code=pre_admission_failure_code,
                    job_id=job_id,
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
                j.method_execution_selection_json,
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
                j.method_execution_selection_json,
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
                j.method_execution_selection_json,
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

    def get_unique_completed_job_by_run_and_kind(
        self,
        *,
        run_id: str,
        kind: ControlJobKind,
    ) -> ControlJobRecord | None:
        """Return the sole completed job for an exact run/kind closure."""

        normalized_kind = _coerce_control_job_kind(kind)
        rows = self._fetchall(
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
                j.method_execution_selection_json,
                p.progress_json
            FROM control_jobs j
            LEFT JOIN control_job_progress p ON p.job_id = j.job_id
            WHERE j.run_id = ? AND j.job_kind = ? AND j.state = 'completed'
            ORDER BY j.finished_at DESC, j.created_at DESC
            LIMIT 2
            """,
            (run_id, normalized_kind),
        )
        if not rows:
            return None
        if len(rows) != 1:
            raise ValueError("control_job_completion_ambiguous")
        return self._row_to_record(rows[0])

    def _row_to_acquisition_evaluation_frontier(
        self, row: Any
    ) -> AcquisitionEvaluationFrontierRecord:
        key = AcquisitionEvaluationFrontierKey(
            tenant_id=str(row["tenant_id"]),
            cell_id=str(row["cell_id"]),
            source_job_id=str(row["source_job_id"]),
            design_problem_ref=str(row["design_problem_ref"]),
            candidate_id=str(row["candidate_id"]),
        )
        value = AcquisitionEvaluationFrontierValue(
            selected_evaluation_witness_ref=str(row["selected_evaluation_witness_ref"]),
            selected_evaluation_content_hash=str(row["selected_evaluation_content_hash"]),
            basis_ref=(str(row["basis_ref"]) if row["basis_ref"] is not None else None),
            basis_content_hash=(
                str(row["basis_content_hash"]) if row["basis_content_hash"] is not None else None
            ),
            decision_ref=(str(row["decision_ref"]) if row["decision_ref"] is not None else None),
        )
        _validate_acquisition_evaluation_frontier_key(key)
        _validate_acquisition_evaluation_frontier_value(value)
        revision = int(row["revision"])
        record = _acquisition_evaluation_frontier_record(
            key=key,
            revision=revision,
            value=value,
        )
        if revision < 1 or record.frontier_ref != str(row["frontier_ref"]):
            raise RuntimeError("acquisition_evaluation_frontier_record_corrupt")
        return record

    def get_acquisition_evaluation_frontier_by_ref(
        self, frontier_ref: str
    ) -> AcquisitionEvaluationFrontierRecord | None:
        """Resolve one immutable historical frontier by its store-issued content ref."""

        if not _is_sha256_ref(frontier_ref):
            raise ValueError("acquisition_evaluation_frontier_ref_invalid")
        row = self._fetchone(
            """
            SELECT tenant_id, cell_id, source_job_id, design_problem_ref, candidate_id,
                   revision, frontier_ref, selected_evaluation_witness_ref,
                   selected_evaluation_content_hash, basis_ref, basis_content_hash,
                   decision_ref
            FROM runtime_acquisition_evaluation_frontier_versions
            WHERE frontier_ref = ?
            """,
            (frontier_ref,),
        )
        if row is None:
            return None
        return self._row_to_acquisition_evaluation_frontier(row)

    def read_acquisition_evaluation_frontier(
        self, key: AcquisitionEvaluationFrontierKey
    ) -> AcquisitionEvaluationFrontierRecord | None:
        """Read the current owner selector; missing state stays not established."""

        _validate_acquisition_evaluation_frontier_key(key)
        row = self._fetchone(
            """
            SELECT revision, frontier_ref
            FROM runtime_acquisition_evaluation_frontier_heads
            WHERE tenant_id = ? AND cell_id = ? AND source_job_id = ?
              AND design_problem_ref = ? AND candidate_id = ?
            """,
            (
                key.tenant_id,
                key.cell_id,
                key.source_job_id,
                key.design_problem_ref,
                key.candidate_id,
            ),
        )
        if row is None:
            return None
        revision = int(row["revision"])
        frontier_ref = row["frontier_ref"]
        if revision == 0 and frontier_ref is None:
            return None
        if revision < 1 or not _is_sha256_ref(frontier_ref):
            raise RuntimeError("acquisition_evaluation_frontier_head_corrupt")
        record = self.get_acquisition_evaluation_frontier_by_ref(str(frontier_ref))
        if record is None or record.key != key or record.revision != revision:
            raise RuntimeError("acquisition_evaluation_frontier_head_history_mismatch")
        return record

    def _advance_acquisition_evaluation_frontier_in_transaction(
        self,
        frontier_cas: AcquisitionEvaluationFrontierCAS,
        *,
        require_replacement: bool = False,
    ) -> AcquisitionEvaluationFrontierRecord:
        """Compare and append one selected evaluation under the owning SQL transaction."""

        _validate_acquisition_evaluation_frontier_cas(
            frontier_cas,
            require_replacement=require_replacement,
        )
        key = frontier_cas.key
        key_values = (
            key.tenant_id,
            key.cell_id,
            key.source_job_id,
            key.design_problem_ref,
            key.candidate_id,
        )
        self._execute(
            """
            INSERT INTO runtime_acquisition_evaluation_frontier_heads (
                tenant_id, cell_id, source_job_id, design_problem_ref, candidate_id,
                revision, frontier_ref
            ) VALUES (?, ?, ?, ?, ?, 0, NULL)
            ON CONFLICT (
                tenant_id, cell_id, source_job_id, design_problem_ref, candidate_id
            ) DO NOTHING
            """,
            key_values,
        )
        lock_suffix = " FOR UPDATE" if self.backend == "postgres" else ""
        current = self._fetchone(
            """
            SELECT revision, frontier_ref
            FROM runtime_acquisition_evaluation_frontier_heads
            WHERE tenant_id = ? AND cell_id = ? AND source_job_id = ?
              AND design_problem_ref = ? AND candidate_id = ?
            """
            + lock_suffix,
            key_values,
        )
        if current is None:
            raise RuntimeError("acquisition_evaluation_frontier_head_not_created")
        current_revision = int(current["revision"])
        current_ref = str(current["frontier_ref"]) if current["frontier_ref"] is not None else None
        if (
            current_revision != frontier_cas.expected_revision
            or current_ref != frontier_cas.expected_frontier_ref
        ):
            raise ValueError("acquisition_evaluation_frontier_conflict")
        if frontier_cas.replacement is None:
            if current_revision < 1 or current_ref is None:
                raise ValueError("acquisition_evaluation_frontier_not_established")
            record = self.get_acquisition_evaluation_frontier_by_ref(current_ref)
            if record is None or record.key != key or record.revision != current_revision:
                raise RuntimeError("acquisition_evaluation_frontier_head_history_mismatch")
            return record

        next_revision = current_revision + 1
        record = _acquisition_evaluation_frontier_record(
            key=key,
            revision=next_revision,
            value=frontier_cas.replacement,
        )
        try:
            self._execute(
                """
                INSERT INTO runtime_acquisition_evaluation_frontier_versions (
                    tenant_id, cell_id, source_job_id, design_problem_ref, candidate_id,
                    revision, frontier_ref, selected_evaluation_witness_ref,
                    selected_evaluation_content_hash, basis_ref, basis_content_hash,
                    decision_ref, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    *key_values,
                    next_revision,
                    record.frontier_ref,
                    record.selected_evaluation_witness_ref,
                    record.selected_evaluation_content_hash,
                    record.basis_ref,
                    record.basis_content_hash,
                    record.decision_ref,
                    _iso(_utc_now()),
                ),
            )
        except Exception as exc:
            if _is_unique_constraint_violation(exc):
                raise ValueError("acquisition_evaluation_frontier_conflict") from exc
            raise
        if current_ref is None:
            update_sql = """
                UPDATE runtime_acquisition_evaluation_frontier_heads
                SET revision = ?, frontier_ref = ?
                WHERE tenant_id = ? AND cell_id = ? AND source_job_id = ?
                  AND design_problem_ref = ? AND candidate_id = ?
                  AND revision = ? AND frontier_ref IS NULL
            """
            update_values = (next_revision, record.frontier_ref, *key_values, current_revision)
        else:
            update_sql = """
                UPDATE runtime_acquisition_evaluation_frontier_heads
                SET revision = ?, frontier_ref = ?
                WHERE tenant_id = ? AND cell_id = ? AND source_job_id = ?
                  AND design_problem_ref = ? AND candidate_id = ?
                  AND revision = ? AND frontier_ref = ?
            """
            update_values = (
                next_revision,
                record.frontier_ref,
                *key_values,
                current_revision,
                current_ref,
            )
        if self._execute(update_sql, update_values) != 1:
            raise ValueError("acquisition_evaluation_frontier_conflict")
        return record

    def _require_frontier_action_owner(
        self,
        *,
        key: AcquisitionEvaluationFrontierKey,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        source_job_id: str,
        action_job_id: str,
        fence: tuple[str, int] | None,
    ) -> None:
        if (
            key.tenant_id != tenant_id
            or key.cell_id != cell_id
            or key.source_job_id != source_job_id
            or action_job_id == source_job_id
        ):
            raise ValueError("acquisition_evaluation_frontier_action_scope_mismatch")
        bound = self._job_execution_fence.get()
        if (
            fence is None
            or bound is None
            or bound[0] != action_job_id
            or bound[1] != fence[0]
            or bound[2] != fence[1]
        ):
            raise ControlJobLeaseLostError(
                "acquisition_evaluation_frontier_requires_current_job_fence"
            )
        current_job = self.current_execution_job_record()
        if (
            current_job.job_id != action_job_id
            or current_job.kind != "acquisition"
            or current_job.state != "running"
            or current_job.run_id != run_id
        ):
            raise ControlJobLeaseLostError("acquisition_evaluation_frontier_action_job_mismatch")
        action_admission = self.current_execution_job_admission()
        if (
            action_admission.scope.status != "established"
            or action_admission.scope.tenant_id != tenant_id
            or action_admission.scope.cell_id != cell_id
        ):
            raise ControlJobExecutionAdmissionError(
                "acquisition_evaluation_frontier_action_scope_not_established"
            )
        source_job = self.get_job(source_job_id)
        if (
            source_job is None
            or source_job.job_id != source_job_id
            or source_job.kind != "natural_language_run"
            or source_job.state != "completed"
            or source_job.run_id != run_id
        ):
            raise ControlJobExecutionAdmissionError(
                "acquisition_evaluation_frontier_source_job_not_completed"
            )
        source_scope = self.historical_completed_job_execution_scope(
            job_id=source_job_id,
            expected_run_id=run_id,
        )
        if (
            source_scope.status != "established"
            or source_scope.tenant_id != tenant_id
            or source_scope.cell_id != cell_id
        ):
            raise ControlJobExecutionAdmissionError(
                "acquisition_evaluation_frontier_source_scope_mismatch"
            )

    def get_acquisition_action_head(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        source_job_id: str,
        route_id: str,
        action_generation: int,
    ) -> AcquisitionActionHeadRecord | None:
        """Return the latest phase pointer for one exact action generation."""

        row = self._fetchone(
            """
            SELECT tenant_id, cell_id, run_id, source_job_id, route_id,
                   action_generation, head_generation, receipt_ref, receipt_sha256,
                   durable_event_id, coarse_phase, receipt_phase, recovery_state,
                   job_id, predecessor_receipt_ref, created_at,
                   evaluation_frontier_before_ref, evaluation_frontier_ref
            FROM runtime_acquisition_action_heads
            WHERE tenant_id = ? AND cell_id = ? AND run_id = ?
              AND source_job_id = ? AND route_id = ? AND action_generation = ?
            ORDER BY head_generation DESC
            LIMIT 1
            """,
            (tenant_id, cell_id, run_id, source_job_id, route_id, action_generation),
        )
        return self._row_to_acquisition_action_head(row) if row is not None else None

    def get_acquisition_action_head_by_receipt(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        source_job_id: str,
        route_id: str,
        action_generation: int,
        receipt_ref: str,
    ) -> AcquisitionActionHeadRecord | None:
        """Return one exact historical action head for a receipt, if unambiguous.

        Receipt lookup is scoped to the complete action identity. Missing,
        ambiguous, or internally misbound rows produce no accepted result.
        """
        rows = self._fetchall(
            """
            SELECT tenant_id, cell_id, run_id, source_job_id, route_id,
                   action_generation, head_generation, receipt_ref, receipt_sha256,
                   durable_event_id, coarse_phase, receipt_phase, recovery_state,
                   job_id, predecessor_receipt_ref, created_at,
                   evaluation_frontier_before_ref, evaluation_frontier_ref
            FROM runtime_acquisition_action_heads
            WHERE tenant_id = ? AND cell_id = ? AND run_id = ?
              AND source_job_id = ? AND route_id = ? AND action_generation = ?
              AND receipt_ref = ?
            ORDER BY head_generation
            """,
            (
                tenant_id,
                cell_id,
                run_id,
                source_job_id,
                route_id,
                action_generation,
                receipt_ref,
            ),
        )
        if len(rows) != 1:
            return None
        row = rows[0]
        if (
            row["receipt_ref"] != receipt_ref
            or row["receipt_sha256"] != receipt_ref
            or not _is_sha256_ref(row["receipt_ref"])
        ):
            return None
        return self._row_to_acquisition_action_head(row)

    def list_acquisition_action_heads(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        source_job_id: str,
        route_id: str,
    ) -> tuple[AcquisitionActionHeadRecord, ...]:
        """Read every current generation head in one exact route/source scope."""

        rows = self._fetchall(
            """
            SELECT heads.tenant_id, heads.cell_id, heads.run_id, heads.source_job_id,
                   heads.route_id, heads.action_generation, heads.head_generation,
                   heads.receipt_ref, heads.receipt_sha256, heads.durable_event_id,
                   heads.coarse_phase, heads.receipt_phase, heads.recovery_state,
                   heads.job_id, heads.predecessor_receipt_ref, heads.created_at,
                   heads.evaluation_frontier_before_ref, heads.evaluation_frontier_ref
            FROM runtime_acquisition_action_heads AS heads
            WHERE heads.tenant_id = ? AND heads.cell_id = ? AND heads.run_id = ?
              AND heads.source_job_id = ? AND heads.route_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM runtime_acquisition_action_heads AS later
                  WHERE later.tenant_id = heads.tenant_id
                    AND later.cell_id = heads.cell_id AND later.run_id = heads.run_id
                    AND later.source_job_id = heads.source_job_id
                    AND later.route_id = heads.route_id
                    AND later.action_generation = heads.action_generation
                    AND later.head_generation > heads.head_generation
              )
            ORDER BY heads.action_generation
            """,
            (tenant_id, cell_id, run_id, source_job_id, route_id),
        )
        return tuple(self._row_to_acquisition_action_head(row) for row in rows)

    def list_acquisition_action_heads_for_source(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        source_job_id: str,
    ) -> tuple[AcquisitionActionHeadRecord, ...]:
        """Read current action heads under one exact source-job scope.

        Route ids are selected only from rows already bound to the supplied
        tenant, cell, run, and source job. This is a history locator; it does
        not select or certify a currently admissible route.
        """
        if not all(
            isinstance(value, str) and value.strip()
            for value in (tenant_id, cell_id, run_id, source_job_id)
        ):
            raise ValueError("acquisition_action_source_scope_invalid")
        rows = self._fetchall(
            """
            SELECT heads.tenant_id, heads.cell_id, heads.run_id, heads.source_job_id,
                   heads.route_id, heads.action_generation, heads.head_generation,
                   heads.receipt_ref, heads.receipt_sha256, heads.durable_event_id,
                   heads.coarse_phase, heads.receipt_phase, heads.recovery_state,
                   heads.job_id, heads.predecessor_receipt_ref, heads.created_at,
                   heads.evaluation_frontier_before_ref, heads.evaluation_frontier_ref
            FROM runtime_acquisition_action_heads AS heads
            WHERE heads.tenant_id = ? AND heads.cell_id = ? AND heads.run_id = ?
              AND heads.source_job_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM runtime_acquisition_action_heads AS later
                  WHERE later.tenant_id = heads.tenant_id
                    AND later.cell_id = heads.cell_id AND later.run_id = heads.run_id
                    AND later.source_job_id = heads.source_job_id
                    AND later.route_id = heads.route_id
                    AND later.action_generation = heads.action_generation
                    AND later.head_generation > heads.head_generation
              )
            ORDER BY heads.route_id, heads.action_generation
            """,
            (tenant_id, cell_id, run_id, source_job_id),
        )
        return tuple(self._row_to_acquisition_action_head(row) for row in rows)

    def advance_acquisition_action_head(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        source_job_id: str,
        route_id: str,
        action_generation: int,
        expected_head_generation: int,
        receipt_ref: str,
        receipt_sha256: str,
        durable_event_id: str,
        coarse_phase: str,
        receipt_phase: str,
        recovery_state: str,
        job_id: str,
        predecessor_receipt_ref: str | None,
        frontier_cas: AcquisitionEvaluationFrontierCAS | None = None,
    ) -> AcquisitionActionHeadRecord:
        """Append one predecessor-consistent action head under the job lease.

        When a frontier CAS is supplied, its shared candidate/task selector
        transition is part of this same SQL transaction. Legacy callers retain
        the original route-only behavior and must not emit B09 source-retained
        terminals.
        """

        if action_generation < 1 or expected_head_generation < 0:
            raise ValueError("acquisition_action_generation_invalid")
        if receipt_ref != receipt_sha256 or not _is_sha256_ref(receipt_ref):
            raise ValueError("acquisition_action_receipt_binding_invalid")
        if frontier_cas is not None:
            _validate_acquisition_evaluation_frontier_cas(frontier_cas)
            if (
                frontier_cas.key.tenant_id != tenant_id
                or frontier_cas.key.cell_id != cell_id
                or frontier_cas.key.source_job_id != source_job_id
            ):
                raise ValueError("acquisition_evaluation_frontier_action_scope_mismatch")
        fence = self._resolve_job_execution_fence(
            job_id=job_id,
            expected_lease_owner=None,
            expected_attempt=None,
        )
        with self._job_transaction():
            if fence is not None:
                where, where_params = self._job_fence_where(
                    job_id=job_id,
                    fence=fence,
                    now=_utc_now(),
                )
                lock_suffix = " FOR UPDATE" if self.backend == "postgres" else ""
                current_job = self._fetchone(
                    f"SELECT job_id FROM control_jobs WHERE {where}{lock_suffix}",
                    where_params,
                )
                if current_job is None:
                    raise ControlJobLeaseLostError(
                        f"control job lease no longer permits action-head write for {job_id}"
                    )
            if frontier_cas is not None:
                self._require_frontier_action_owner(
                    key=frontier_cas.key,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    run_id=run_id,
                    source_job_id=source_job_id,
                    action_job_id=job_id,
                    fence=fence,
                )
                committed_frontier = self._advance_acquisition_evaluation_frontier_in_transaction(
                    frontier_cas
                )
            else:
                committed_frontier = None
            current = self.get_acquisition_action_head(
                tenant_id=tenant_id,
                cell_id=cell_id,
                run_id=run_id,
                source_job_id=source_job_id,
                route_id=route_id,
                action_generation=action_generation,
            )
            if (
                (current is None and expected_head_generation != 0)
                or (current is not None and current.head_generation != expected_head_generation)
                or (current is not None and predecessor_receipt_ref != current.receipt_ref)
                or (current is None and predecessor_receipt_ref is not None)
            ):
                raise ValueError("acquisition_action_predecessor_conflict")
            next_generation = expected_head_generation + 1
            created_at = _utc_now()
            insert_columns = """tenant_id, cell_id, run_id, source_job_id, route_id,
                action_generation, head_generation, receipt_ref, receipt_sha256,
                durable_event_id, coarse_phase, receipt_phase, recovery_state,
                job_id, predecessor_receipt_ref, created_at,
                evaluation_frontier_before_ref, evaluation_frontier_ref"""
            values = (
                tenant_id,
                cell_id,
                run_id,
                source_job_id,
                route_id,
                action_generation,
                next_generation,
                receipt_ref,
                receipt_sha256,
                durable_event_id,
                coarse_phase,
                receipt_phase,
                recovery_state,
                job_id,
                predecessor_receipt_ref,
                _iso(created_at),
                frontier_cas.expected_frontier_ref if frontier_cas is not None else None,
                committed_frontier.frontier_ref if committed_frontier is not None else None,
            )
            try:
                if fence is None:
                    affected_rows = self._execute(
                        "INSERT INTO runtime_acquisition_action_heads "
                        f"({insert_columns}) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        values,
                    )
                else:
                    where, where_params = self._job_fence_where(
                        job_id=job_id,
                        fence=fence,
                        now=_utc_now(),
                    )
                    affected_rows = self._execute(
                        "INSERT INTO runtime_acquisition_action_heads "
                        f"({insert_columns}) "
                        f"SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? "
                        f"WHERE EXISTS (SELECT 1 FROM control_jobs WHERE {where})",
                        (*values, *where_params),
                    )
                self._require_fenced_write(
                    job_id=job_id,
                    fence=fence,
                    affected_rows=affected_rows,
                )
            except Exception as exc:
                if _is_unique_constraint_violation(exc):
                    raise ValueError("acquisition_action_predecessor_conflict") from exc
                raise
            loaded = self.get_acquisition_action_head(
                tenant_id=tenant_id,
                cell_id=cell_id,
                run_id=run_id,
                source_job_id=source_job_id,
                route_id=route_id,
                action_generation=action_generation,
            )
            if (
                loaded is None
                or loaded.head_generation != next_generation
                or loaded.evaluation_frontier_ref
                != (committed_frontier.frontier_ref if committed_frontier is not None else None)
                or loaded.evaluation_frontier_before_ref
                != (frontier_cas.expected_frontier_ref if frontier_cas is not None else None)
            ):
                raise RuntimeError("acquisition_action_head_readback_failed")
            return loaded

    def advance_acquisition_action_head_with_frontier(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        source_job_id: str,
        route_id: str,
        action_generation: int,
        expected_head_generation: int,
        receipt_ref: str,
        receipt_sha256: str,
        durable_event_id: str,
        coarse_phase: str,
        receipt_phase: str,
        recovery_state: str,
        job_id: str,
        predecessor_receipt_ref: str | None,
        frontier_cas: AcquisitionEvaluationFrontierCAS,
    ) -> AcquisitionActionHeadFrontierCommit:
        """Append an action head and condition the shared evaluation frontier atomically."""

        _validate_acquisition_evaluation_frontier_cas(frontier_cas)
        head = self.advance_acquisition_action_head(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            source_job_id=source_job_id,
            route_id=route_id,
            action_generation=action_generation,
            expected_head_generation=expected_head_generation,
            receipt_ref=receipt_ref,
            receipt_sha256=receipt_sha256,
            durable_event_id=durable_event_id,
            coarse_phase=coarse_phase,
            receipt_phase=receipt_phase,
            recovery_state=recovery_state,
            job_id=job_id,
            predecessor_receipt_ref=predecessor_receipt_ref,
            frontier_cas=frontier_cas,
        )
        if frontier_cas.replacement is None:
            frontier_ref = frontier_cas.expected_frontier_ref
        else:
            frontier_ref = _acquisition_evaluation_frontier_ref(
                key=frontier_cas.key,
                revision=frontier_cas.expected_revision + 1,
                value=frontier_cas.replacement,
            )
        if frontier_ref is None:
            raise RuntimeError("acquisition_evaluation_frontier_result_ref_missing")
        frontier = self.get_acquisition_evaluation_frontier_by_ref(frontier_ref)
        if frontier is None or frontier.key != frontier_cas.key:
            raise RuntimeError("acquisition_evaluation_frontier_result_not_observed")
        return AcquisitionActionHeadFrontierCommit(head=head, frontier=frontier)

    def get_normative_evidence_head(self, job_id: str) -> dict[str, Any] | None:
        """Resolve the latest immutable normative admission event for one exact job."""
        row = self._fetchone(
            "SELECT payload_json FROM control_job_events "
            "WHERE job_id = ? AND event_type = 'normative_evidence_admitted' "
            "ORDER BY event_id DESC LIMIT 1",
            (job_id,),
        )
        if row is None:
            return None
        payload = json.loads(str(row["payload_json"] if isinstance(row, Mapping) else row[0]))
        if not isinstance(payload, dict) or not _is_sha256_ref(payload.get("head_ref")):
            raise ValueError("normative_head_event_invalid")
        return payload

    def append_normative_evidence_head(
        self,
        *,
        job_id: str,
        run_id: str,
        compiled_run_ref: str,
        expected_prior_head_ref: str | None,
        head_ref: str,
    ) -> bool:
        """Compare and append under the owning-job transaction; never rewrite job progress."""
        if not _is_sha256_ref(head_ref) or not _is_sha256_ref(compiled_run_ref):
            raise ValueError("normative_head_ref_invalid")
        if expected_prior_head_ref is not None and not _is_sha256_ref(expected_prior_head_ref):
            raise ValueError("normative_head_predecessor_invalid")

        def append(cur: Any, *, postgres: bool) -> bool:
            def execute(sql: str, params: tuple[object, ...]) -> Any:
                return cur.execute(self._translate_sql(sql) if postgres else sql, params)

            execute(
                "SELECT run_id, job_kind, state FROM control_jobs WHERE job_id = ?"
                + (" FOR UPDATE" if postgres else ""),
                (job_id,),
            )
            job = cur.fetchone()
            if job is None or tuple(job) != (
                run_id,
                "natural_language_run",
                "completed",
            ):
                raise ValueError("normative_evidence_job_mismatch")
            execute(
                "SELECT progress_json FROM control_job_progress WHERE job_id = ?",
                (job_id,),
            )
            progress = cur.fetchone()
            if (
                progress is None
                or json.loads(str(progress[0])).get("compiled_recursive_generation_cycle_ref")
                != compiled_run_ref
            ):
                raise ValueError("normative_evidence_job_source_mismatch")
            execute(
                "SELECT payload_json FROM control_job_events "
                "WHERE job_id = ? AND event_type = 'normative_evidence_admitted' "
                "ORDER BY event_id DESC LIMIT 1",
                (job_id,),
            )
            current = cur.fetchone()
            prior = None if current is None else json.loads(str(current[0]))["head_ref"]
            if prior != expected_prior_head_ref:
                return False
            payload = {
                "head_ref": head_ref,
                "previous_head_ref": expected_prior_head_ref,
                "job_id": job_id,
                "run_id": run_id,
                "compiled_run_ref": compiled_run_ref,
            }
            execute(
                "INSERT INTO control_job_events (job_id, event_type, payload_json, created_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    job_id,
                    "normative_evidence_admitted",
                    json.dumps(payload, sort_keys=True),
                    _iso(_utc_now()),
                ),
            )
            return True

        if self.backend == "sqlite":
            with self._lock, self._sqlite_mutation_connection() as conn:
                try:
                    admitted = append(conn.cursor(), postgres=False)
                    return admitted
                except Exception:
                    raise
        with self._postgres_mutation_cursor() as cur:
            return append(cur, postgres=True)

    def append_event(self, *, job_id: str, event_type: str, payload: dict[str, Any]) -> None:
        """Append one immutable job lifecycle/progress event row."""
        if event_type.startswith(("child.release.", "child.budget.")):
            raise ValueError("child_release_event_reserved_for_owner")
        self._execute(
            """
            INSERT INTO control_job_events (job_id, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                job_id,
                event_type,
                json.dumps(payload, sort_keys=True),
                datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            ),
        )

    def get_job_created_event_payload(self, job_id: str) -> dict[str, Any]:
        """Read exactly one typed job-created event payload from the durable event owner."""
        rows = self._fetchall(
            """
            SELECT payload_json
            FROM control_job_events
            WHERE job_id = ? AND event_type = ?
            ORDER BY event_id ASC
            """,
            (job_id, "job_created"),
        )
        if len(rows) != 1:
            raise RuntimeError("control_job_created_event_count_not_one")
        row = rows[0]
        raw = row[0] if not isinstance(row, Mapping) else row.get("payload_json")
        try:
            payload = json.loads(str(raw))
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("control_job_created_event_payload_malformed") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("control_job_created_event_payload_not_object")
        return dict(payload)

    def _get_job_created_source_event_record(
        self,
        job_id: str,
    ) -> _ControlJobLifecycleSourceEventRecord:
        """Read the unique job-created event with its immutable row identity and digest."""
        rows = self._fetchall(
            """
            SELECT event_id, job_id, event_type, payload_json, created_at
            FROM control_job_events
            WHERE job_id = ? AND event_type = ?
            ORDER BY event_id ASC
            """,
            (job_id, "job_created"),
        )
        if len(rows) != 1:
            raise ControlJobLeaseLostError("control job created event count is not one")
        return self._control_job_lifecycle_event_record_from_row(
            rows[0],
            expected_job_id=job_id,
            expected_event_type="job_created",
        )

    def _latest_control_job_lifecycle_event_record(
        self,
        *,
        job_id: str,
        event_type: Literal["job_running", "job_completed", "job_failed"],
    ) -> _ControlJobLifecycleSourceEventRecord:
        """Read the newest exact lifecycle event row for one job and event type."""
        row = self._fetchone(
            """
            SELECT event_id, job_id, event_type, payload_json, created_at
            FROM control_job_events
            WHERE job_id = ? AND event_type = ?
            ORDER BY event_id DESC LIMIT 1
            """,
            (job_id, event_type),
        )
        if row is None:
            raise ControlJobLeaseLostError(
                f"control job {event_type.removeprefix('job_')} event is unavailable"
            )
        try:
            return self._control_job_lifecycle_event_record_from_row(
                row,
                expected_job_id=job_id,
                expected_event_type=event_type,
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ControlJobLeaseLostError(
                f"control job {event_type.removeprefix('job_')} event is malformed"
            ) from exc

    def get_job_terminal_source_event_record(
        self,
        job_id: str,
    ) -> _ControlJobLifecycleSourceEventRecord:
        """Read the latest persisted completion/failure event for one job."""
        row = self._fetchone(
            """
            SELECT event_id, job_id, event_type, payload_json, created_at
            FROM control_job_events
            WHERE job_id = ? AND event_type IN (?, ?)
            ORDER BY event_id DESC LIMIT 1
            """,
            (job_id, "job_completed", "job_failed"),
        )
        if row is None:
            raise ControlJobLeaseLostError("control job terminal event is unavailable")
        event_type = row.get("event_type") if isinstance(row, Mapping) else row[2]
        if event_type not in {"job_completed", "job_failed"}:
            raise ControlJobLeaseLostError("control job terminal event type is invalid")
        try:
            return self._control_job_lifecycle_event_record_from_row(
                row,
                expected_job_id=job_id,
                expected_event_type=event_type,
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ControlJobLeaseLostError("control job terminal event is malformed") from exc

    def get_cancelled_job_verified_record(self, job_id: str) -> ControlJobRecord:
        """Reconcile a cancelled row, its creation scope, event, and outbox."""
        with self._job_transaction():
            self._lock_job_state(job_id)
            record = self.get_job(job_id)
            if (
                record is None
                or record.state != "cancelled"
                or record.lease_owner is not None
                or record.lease_expires_at is not None
                or record.finished_at is None
            ):
                raise ControlJobLeaseLostError("cancelled job row not established")
            scope, _ = self._reconcile_control_job_creation_envelope(record)
            cancellation = record.progress.get("cancellation")
            if (
                not isinstance(cancellation, dict)
                or scope.status != "established"
                or cancellation.get("tenant_id") != scope.tenant_id
                or cancellation.get("cell_id") != scope.cell_id
                or cancellation.get("cancelled_attempt") != record.attempt
                or cancellation.get("disposition") != "publication_fenced"
                or cancellation.get("physical_stop_status") != "not_established"
                or not isinstance(cancellation.get("authorized_actor"), str)
                or not cancellation["authorized_actor"]
                or not isinstance(cancellation.get("operation_id"), str)
                or not cancellation["operation_id"]
                or not isinstance(cancellation.get("body_sha256"), str)
                or not cancellation["body_sha256"].startswith("sha256:")
                or len(cancellation["body_sha256"]) != 71
            ):
                raise ControlJobLeaseLostError("cancelled job disposition not established")
            cancelled_owner = cancellation.get("cancelled_lease_owner")
            if cancelled_owner is None:
                if (
                    cancellation.get("expected_lease_owner") is not None
                    or cancellation.get("expected_attempt") is not None
                ):
                    raise ControlJobLeaseLostError("pending cancellation has a lease precondition")
            elif (
                not isinstance(cancelled_owner, str)
                or not cancelled_owner
                or cancellation.get("expected_lease_owner") != cancelled_owner
                or cancellation.get("expected_attempt") != record.attempt
            ):
                raise ControlJobLeaseLostError("cancelled job attempt identity disagrees")
            event_rows = self._fetchall(
                """
                SELECT event_id, job_id, event_type, payload_json, created_at
                FROM control_job_events WHERE job_id = ? AND event_type = ?
                ORDER BY event_id ASC
                """,
                (job_id, "job_cancelled"),
            )
            if len(event_rows) != 1:
                raise ControlJobLeaseLostError("cancelled job source event not unique")
            try:
                event = self._control_job_lifecycle_event_record_from_row(
                    event_rows[0],
                    expected_job_id=job_id,
                    expected_event_type="job_cancelled",
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ControlJobLeaseLostError("cancelled job source event malformed") from exc
            payload = {**cancellation, "state": "cancelled"}
            if event.payload != payload:
                raise ControlJobLeaseLostError("cancelled job source event disagrees")
            outbox_rows = self._fetchall(
                """
                SELECT event_id, topic, event_key, state, job_id, run_id,
                       payload_json, created_at, published_at, attempt, error_message
                FROM control_outbox_events WHERE topic = ? AND event_key = ? AND job_id = ?
                """,
                ("control.job.cancelled", f"{job_id}:job_cancelled", job_id),
            )
            if len(outbox_rows) != 1:
                raise ControlJobLeaseLostError("cancelled job outbox not unique")
            try:
                outbox = self._row_to_outbox_record(outbox_rows[0])
            except (TypeError, ValueError, KeyError) as exc:
                raise ControlJobLeaseLostError("cancelled job outbox malformed") from exc
            expected_payload = {**_control_job_outbox_identity_envelope(record), **payload}
            if outbox.run_id != record.run_id or outbox.payload != expected_payload:
                raise ControlJobLeaseLostError("cancelled job outbox disagrees")
            return record

    def get_job_lifecycle_event_record(
        self,
        *,
        job_id: str,
        event_id: int,
        expected_event_type: Literal["job_running", "job_completed"],
    ) -> _ControlJobLifecycleSourceEventRecord:
        """Read one exact immutable lifecycle row for historical reconciliation."""
        if type(event_id) is not int or event_id < 1:
            raise ValueError("control_job_lifecycle_event_id_invalid")
        row = self._fetchone(
            """
            SELECT event_id, job_id, event_type, payload_json, created_at
            FROM control_job_events
            WHERE job_id = ? AND event_id = ?
            """,
            (job_id, event_id),
        )
        if row is None:
            raise ControlJobLeaseLostError("control job lifecycle event is unavailable")
        try:
            return self._control_job_lifecycle_event_record_from_row(
                row,
                expected_job_id=job_id,
                expected_event_type=expected_event_type,
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ControlJobLeaseLostError("control job lifecycle event is malformed") from exc

    def list_pending_search_hte_completion_events(
        self,
        *,
        limit: int = 50,
        after_created_at: str | None = None,
        after_event_id: str | None = None,
    ) -> list[ControlOutboxRecord]:
        """Read one stable timestamp/identity cursor page of Search deliveries."""
        page_size = max(1, min(int(limit), 100))
        if (after_created_at is None) != (after_event_id is None):
            raise ValueError("control_search_hte_outbox_cursor_incomplete")
        if after_created_at is None:
            cursor_sql = ""
            cursor_params: tuple[Any, ...] = ()
        else:
            cursor_sql = " AND (created_at > ? OR (created_at = ? AND event_id > ?))"
            cursor_params = (after_created_at, after_created_at, after_event_id)
        rows = self._fetchall(
            f"""
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
            WHERE topic = ? AND state = ?{cursor_sql}
            ORDER BY created_at ASC, event_id ASC
            LIMIT ?
            """,
            ("control.search.hte_completed", "pending", *cursor_params, page_size),
        )
        return [self._row_to_outbox_record(row) for row in rows]

    def get_outbox_topic_delivery_watermark(self, *, topic: str) -> int:
        """Return the frozen monotonic outbox sequence for one exact topic."""
        if type(topic) is not str or not topic.strip():
            raise ValueError("control_outbox_topic_invalid")
        row = self._fetchone(
            "SELECT COALESCE(MAX(delivery.sequence_id), 0) AS watermark "
            "FROM control_search_hte_delivery_order AS delivery "
            "JOIN control_outbox_events AS event ON event.event_id = delivery.event_id "
            "WHERE event.topic = ?",
            (topic,),
        )
        value = row["watermark"] if isinstance(row, Mapping) else row[0]
        if type(value) is not int or value < 0:
            raise RuntimeError("control_outbox_topic_watermark_invalid")
        return value

    def list_pending_outbox_topic_delivery_page(
        self,
        *,
        topic: str,
        limit: int = 25,
        after_sequence_id: int = 0,
        through_sequence_id: int,
    ) -> list[tuple[int, ControlOutboxRecord]]:
        """Read a pending topic page bounded by one durable sequence watermark."""
        if (
            type(topic) is not str
            or not topic.strip()
            or type(limit) is not int
            or type(after_sequence_id) is not int
            or type(through_sequence_id) is not int
            or limit < 1
            or after_sequence_id < 0
            or through_sequence_id < after_sequence_id
        ):
            raise ValueError("control_outbox_topic_page_bounds_invalid")
        rows = self._fetchall(
            """
            SELECT
                event.event_id,
                event.topic,
                event.event_key,
                event.state,
                event.job_id,
                event.run_id,
                event.payload_json,
                event.created_at,
                event.published_at,
                event.attempt,
                event.error_message,
                delivery.sequence_id
            FROM control_search_hte_delivery_order AS delivery
            JOIN control_outbox_events AS event ON event.event_id = delivery.event_id
            WHERE event.topic = ?
              AND event.state = ?
              AND delivery.sequence_id > ?
              AND delivery.sequence_id <= ?
            ORDER BY delivery.sequence_id ASC
            LIMIT ?
            """,
            (topic, "pending", after_sequence_id, through_sequence_id, min(limit, 100)),
        )
        return [(int(row["sequence_id"]), self._row_to_outbox_record(row)) for row in rows]

    def get_outbox_topic_event(
        self,
        *,
        topic: str,
        event_key: str,
        job_id: str,
    ) -> ControlOutboxRecord | None:
        """Read one outbox row by its exact topic, event key, and owning job."""
        rows = self._fetchall(
            """
            SELECT
                event_id, topic, event_key, state, job_id, run_id, payload_json,
                created_at, published_at, attempt, error_message
            FROM control_outbox_events
            WHERE topic = ? AND event_key = ? AND job_id = ?
            ORDER BY created_at ASC, event_id ASC
            """,
            (topic, event_key, job_id),
        )
        if len(rows) > 1:
            raise RuntimeError("control_outbox_topic_event_count_invalid")
        return self._row_to_outbox_record(rows[0]) if rows else None

    def get_search_hte_completion_delivery_watermark(self) -> int:
        """Return the highest durable delivery sequence at a retry-cycle boundary."""
        row = self._fetchone(
            "SELECT COALESCE(MAX(delivery.sequence_id), 0) AS watermark "
            "FROM control_search_hte_delivery_order AS delivery "
            "JOIN control_outbox_events AS event ON event.event_id = delivery.event_id "
            "WHERE event.topic = ?",
            ("control.search.hte_completed",),
        )
        value = row["watermark"] if isinstance(row, Mapping) else row[0]
        if type(value) is not int or value < 0:
            raise RuntimeError("control_search_hte_delivery_watermark_invalid")
        return value

    def list_pending_search_hte_completion_delivery_page(
        self,
        *,
        limit: int = 50,
        after_sequence_id: int = 0,
        through_sequence_id: int,
    ) -> list[tuple[int, ControlOutboxRecord]]:
        """Read a Search-only pending page bounded by one frozen sequence watermark."""
        if (
            type(limit) is not int
            or type(after_sequence_id) is not int
            or type(through_sequence_id) is not int
            or limit < 1
            or after_sequence_id < 0
            or through_sequence_id < after_sequence_id
        ):
            raise ValueError("control_search_hte_delivery_page_bounds_invalid")
        page_size = min(limit, 100)
        rows = self._fetchall(
            """
            SELECT
                event.event_id,
                event.topic,
                event.event_key,
                event.state,
                event.job_id,
                event.run_id,
                event.payload_json,
                event.created_at,
                event.published_at,
                event.attempt,
                event.error_message,
                delivery.sequence_id
            FROM control_search_hte_delivery_order AS delivery
            JOIN control_outbox_events AS event
              ON event.event_id = delivery.event_id
            WHERE event.topic = ?
              AND event.state = ?
              AND delivery.sequence_id > ?
              AND delivery.sequence_id <= ?
            ORDER BY delivery.sequence_id ASC
            LIMIT ?
            """,
            (
                "control.search.hte_completed",
                "pending",
                after_sequence_id,
                through_sequence_id,
                page_size,
            ),
        )
        return [(int(row["sequence_id"]), self._row_to_outbox_record(row)) for row in rows]

    def get_search_hte_completion_outbox_event(
        self,
        *,
        job_id: str,
        completed_event_id: int,
    ) -> ControlOutboxRecord | None:
        """Read the one Search delivery row for an exact completed source event."""
        if type(completed_event_id) is not int or completed_event_id < 1:
            raise ValueError("control_search_hte_completed_event_id_invalid")
        rows = self._fetchall(
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
            WHERE topic = ? AND event_key = ? AND job_id = ?
            ORDER BY created_at ASC
            """,
            (
                "control.search.hte_completed",
                f"{job_id}:job_completed:{completed_event_id}",
                job_id,
            ),
        )
        if len(rows) > 1:
            raise RuntimeError("control_search_hte_completion_outbox_count_invalid")
        return self._row_to_outbox_record(rows[0]) if rows else None

    def get_job_completed_outbox_event(self, job_id: str) -> ControlOutboxRecord | None:
        """Read exactly one completion outbox row keyed to one ControlJob."""
        rows = self._fetchall(
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
            WHERE topic = ? AND event_key = ? AND job_id = ?
            ORDER BY created_at ASC
            """,
            ("control.job.completed", f"{job_id}:job_completed", job_id),
        )
        if len(rows) != 1:
            raise RuntimeError("control_job_completed_outbox_count_not_one")
        return self._row_to_outbox_record(rows[0])

    @staticmethod
    def _control_job_lifecycle_event_record_from_row(
        row: Any,
        *,
        expected_job_id: str,
        expected_event_type: str,
    ) -> _ControlJobLifecycleSourceEventRecord:
        """Parse a lifecycle row without normalizing its raw payload bytes."""
        if isinstance(row, Mapping):
            event_id = row.get("event_id")
            job_id = row.get("job_id")
            event_type = row.get("event_type")
            raw_payload = row.get("payload_json")
            raw_created_at = row.get("created_at")
        else:
            event_id, job_id, event_type, raw_payload, raw_created_at = row[:5]
        if (
            type(event_id) is not int
            or event_id < 1
            or job_id != expected_job_id
            or event_type != expected_event_type
            or not isinstance(raw_payload, str)
        ):
            raise ValueError("control_job_lifecycle_event_identity_invalid")
        payload = json.loads(raw_payload)
        if not isinstance(payload, dict):
            raise ValueError("control_job_lifecycle_event_payload_not_object")
        created_at = _parse_dt(raw_created_at)
        if created_at is None or created_at.tzinfo is None:
            raise ValueError("control_job_lifecycle_event_created_at_invalid")
        return _ControlJobLifecycleSourceEventRecord(
            event_id=event_id,
            job_id=job_id,
            event_type=event_type,
            payload=dict(payload),
            created_at=created_at.astimezone(timezone.utc),
            payload_sha256="sha256:" + hashlib.sha256(raw_payload.encode("utf-8")).hexdigest(),
        )

    def get_job_created_outbox_event(self, job_id: str) -> ControlOutboxRecord | None:
        """Read exactly one matching job-created event from the durable outbox owner."""
        rows = self._fetchall(
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
            WHERE topic = ? AND event_key = ? AND job_id = ?
            ORDER BY created_at ASC
            """,
            ("control.job.created", f"{job_id}:job_created", job_id),
        )
        if len(rows) != 1:
            raise RuntimeError("control_job_created_outbox_count_not_one")
        return self._row_to_outbox_record(rows[0])

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

    def _lock_job_state(self, job_id: str) -> str:
        """Lock the shared job row before any transaction mutates its progress."""
        sqlite = getattr(self._human_decision_transaction, "sqlite_connection", None)
        postgres = getattr(self._human_decision_transaction, "postgres_cursor", None)
        if sqlite is None and postgres is None:
            raise RuntimeError("control_job_row_lock_requires_transaction")
        suffix = " FOR UPDATE" if self.backend == "postgres" else ""
        row = self._fetchone(f"SELECT state FROM control_jobs WHERE job_id = ?{suffix}", (job_id,))
        if row is None:
            raise KeyError(job_id)
        return str(row[0] if not isinstance(row, Mapping) else row.get("state"))

    def upsert_progress(self, *, job_id: str, progress: dict[str, Any]) -> None:
        """Replace progress only while the authoritative job permits publication."""
        with self._job_transaction():
            state = self._lock_job_state(job_id)
            if state == "cancelled":
                raise ControlJobLeaseLostError("cancelled control job rejects progress publication")
            self._upsert_progress_unchecked(job_id=job_id, progress=progress)

    def _upsert_progress_unchecked(self, *, job_id: str, progress: dict[str, Any]) -> None:
        """Write progress inside an owner transaction that already admitted the mutation."""
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

    def current_execution_completed_job_record(self) -> ControlJobRecord:
        """Resolve this handler's exact completed attempt without granting a new lease."""
        return self._current_execution_completed_job_proof().record

    def _current_execution_completed_job_proof(
        self,
    ) -> _ControlJobExecutionLifecycleProof:
        """Resolve the exact completed attempt and durable event under transaction."""
        with self._job_transaction(purpose="completed_proof"):
            return self._require_current_job_completion_proof()

    def current_execution_failed_job_record(self) -> ControlJobRecord:
        """Resolve this handler's exact failed attempt without granting a new lease."""
        return self._current_execution_failed_job_proof().record

    def _current_execution_failed_job_proof(self) -> _ControlJobExecutionLifecycleProof:
        """Resolve the exact failed attempt and durable event under transaction."""
        with self._job_transaction(purpose="failed_proof"):
            return self._require_current_job_failure_proof()

    def _require_current_job_completion_record(self) -> ControlJobRecord:
        """Reconcile the bound attempt with its durable completion event under transaction."""
        return self._require_current_job_terminal_record(state="completed")

    def _require_current_job_failure_record(self) -> ControlJobRecord:
        """Reconcile the bound attempt with its durable failure event under transaction."""
        return self._require_current_job_terminal_record(state="failed")

    def _require_current_job_completion_proof(
        self,
    ) -> _ControlJobExecutionLifecycleProof:
        """Return the exact completion source event and its bound worker attempt."""
        return self._require_current_job_terminal_proof(state="completed")

    def _require_current_job_failure_proof(self) -> _ControlJobExecutionLifecycleProof:
        """Return the exact failure source event and its bound worker attempt."""
        return self._require_current_job_terminal_proof(state="failed")

    def _require_current_job_terminal_record(
        self,
        *,
        state: Literal["completed", "failed"],
    ) -> ControlJobRecord:
        """Reconcile one bound terminal attempt with its exact durable event."""
        return self._require_current_job_terminal_proof(state=state).record

    def _require_current_job_terminal_proof(
        self,
        *,
        state: Literal["completed", "failed"],
    ) -> _ControlJobExecutionLifecycleProof:
        """Return the event-bound worker proof for one exact terminal attempt."""
        bound = self._job_execution_fence.get()
        terminal_name = "completion" if state == "completed" else "failure"
        event_type = "job_completed" if state == "completed" else "job_failed"
        if bound is None:
            raise ControlJobLeaseLostError(f"control job {terminal_name} identity is not bound")
        job_id, worker_id, attempt = bound
        lock_suffix = " FOR UPDATE" if self.backend == "postgres" else ""
        row = self._fetchone(
            f"SELECT job_id FROM control_jobs WHERE job_id = ?{lock_suffix}", (job_id,)
        )
        record = self.get_job(job_id) if row is not None else None
        if (
            record is None
            or record.state != state
            or record.attempt != attempt
            or record.lease_owner is not None
            or record.lease_expires_at is not None
        ):
            raise ControlJobLeaseLostError(f"control job {state} attempt no longer matches handler")
        try:
            source_event = self._latest_control_job_lifecycle_event_record(
                job_id=job_id,
                event_type=event_type,
            )
        except ControlJobLeaseLostError as exc:
            raise ControlJobLeaseLostError(
                f"control job {terminal_name} event is unavailable"
            ) from exc
        payload = source_event.payload
        if (
            payload.get("state") != state
            or payload.get("lease_owner") != worker_id
            or type(payload.get("attempt")) is not int
            or payload["attempt"] != attempt
        ):
            raise ControlJobLeaseLostError(
                f"control job {terminal_name} event does not bind handler"
            )
        return _ControlJobExecutionLifecycleProof(
            record=record,
            proof_phase=state,
            worker_id=worker_id,
            attempt=attempt,
            source_event=source_event,
        )

    def publish_completed_job_proof(
        self,
        *,
        job_id: str,
        expected_progress: dict[str, Any],
        proof_payload: dict[str, Any],
        proof_ref: str,
    ) -> None:
        """Publish only proof-owned fields for the bound completed attempt.

        Completion clears the running lease. This transition instead checks the
        retained handler identity against the exact completion event, then
        compares the progress snapshot before publishing. A stale handler or a
        concurrent progress writer cannot overwrite a later state.
        """
        if not _is_sha256_ref(proof_ref):
            raise ValueError("control job final proof reference is invalid")
        with self._job_transaction(purpose="completed_proof"):
            record = self._require_current_job_completion_record()
            if record.job_id != job_id:
                raise ControlJobLeaseLostError("control job final proof progress changed")
            bound = self._job_execution_fence.get()
            if bound is None:
                raise ControlJobLeaseLostError("control job completion identity is not bound")
            if (
                proof_payload.get("job_id") != job_id
                or proof_payload.get("run_id") != record.run_id
                or proof_payload.get("worker_id") != bound[1]
            ):
                raise ValueError("control job final proof does not bind completed handler")
            row = self._fetchone(
                "SELECT progress_json FROM control_job_progress WHERE job_id = ?"
                + (" FOR UPDATE" if self.backend == "postgres" else ""),
                (job_id,),
            )
            raw_progress = (
                row[0]
                if row is not None and not isinstance(row, Mapping)
                else (row.get("progress_json") if row is not None else None)
            )
            try:
                progress = json.loads(str(raw_progress or "{}"))
            except (TypeError, json.JSONDecodeError) as exc:
                raise ControlJobLeaseLostError(
                    "control job final proof progress is unavailable"
                ) from exc
            proof_basis_fields = (
                "production_loop_run_proof",
                "production_loop_run_proof_ref",
                "search_exit_contract",
                "search_exit_contract_ref",
                "authority_path",
                "authority_result",
            )
            if not isinstance(progress, dict) or any(
                (key in progress) != (key in expected_progress)
                or not _json_values_equal_strict(progress.get(key), expected_progress.get(key))
                for key in proof_basis_fields
            ):
                raise ControlJobLeaseLostError("control job final proof progress changed")
            if proof_payload.get(
                "control_store_state_transitions"
            ) != self.list_job_state_transitions(job_id):
                raise ControlJobLeaseLostError("control job final proof transition history changed")
            progress["production_loop_run_proof"] = proof_payload
            progress["production_loop_run_proof_ref"] = proof_ref
            artifacts_index = progress.get("artifacts_index")
            if isinstance(artifacts_index, Mapping):
                progress["artifacts_index"] = {
                    **dict(artifacts_index),
                    "production_loop_run_proof_ref": proof_ref,
                }
            quality_scorecard = progress.get("quality_scorecard")
            if isinstance(quality_scorecard, Mapping):
                scorecard = dict(quality_scorecard)
                evidence_refs = scorecard.get("evidence_refs")
                evidence_refs = dict(evidence_refs) if isinstance(evidence_refs, Mapping) else {}
                evidence_refs["production_loop_run_proof_ref"] = proof_ref
                scorecard["evidence_refs"] = evidence_refs
                progress["quality_scorecard"] = scorecard
            progress_json = json.dumps(
                _progress_with_quality_scorecard_summary(progress), sort_keys=True
            )
            affected = self._execute(
                """
                UPDATE control_job_progress SET progress_json = ?, updated_at = ?
                WHERE job_id = ? AND progress_json = ?
                """,
                (progress_json, _iso(_utc_now()), job_id, raw_progress),
            )
            if affected != 1:
                raise ControlJobLeaseLostError("control job final proof progress changed")
            event_payload = {
                "attempt": record.attempt,
                "lease_owner": bound[1],
                "proof_ref": proof_ref,
            }
            self.append_event(
                job_id=job_id,
                event_type="job_proof_finalized",
                payload=event_payload,
            )
            self.enqueue_outbox_event(
                topic="control.job.proof_finalized",
                event_key=f"{job_id}:{record.attempt}:proof_finalized:{proof_ref}",
                job_id=job_id,
                run_id=record.run_id,
                payload={"job_id": job_id, "run_id": record.run_id, **event_payload},
            )

    def lease_next_job(
        self,
        *,
        worker_id: str,
        lease_seconds: int = 60,
    ) -> ControlJobRecord | None:
        """Lease the next pending/expired job for one worker and emit a running event."""
        with self._job_transaction():
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
                    "attempt": record.attempt,
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
        with self._job_transaction():
            now = _utc_now()
            lease_expires_at = now + timedelta(seconds=max(lease_seconds, 1))
            affected = self._execute(
                """
                UPDATE control_jobs
                SET state = ?, started_at = COALESCE(started_at, ?),
                    lease_owner = ?, lease_expires_at = ?, attempt = attempt + 1
                WHERE job_id = ? AND (state = 'pending' OR
                    (state = 'running' AND lease_expires_at <= ?))
                AND NOT EXISTS (
                    SELECT 1 FROM control_job_events AS child_intent
                    WHERE child_intent.job_id = control_jobs.job_id
                      AND child_intent.event_type LIKE 'child.release.session.%'
                )
                AND NOT EXISTS (
                    SELECT 1 FROM control_job_events AS child_budget
                    WHERE child_budget.job_id = control_jobs.job_id
                      AND child_budget.event_type LIKE 'child.budget.attempt.%'
                )
                """,
                (
                    "running",
                    _iso(now),
                    worker_id,
                    _iso(lease_expires_at),
                    job_id,
                    _iso(now),
                ),
            )
            if affected != 1:
                raise ControlJobLeaseLostError(f"control job cannot be marked running: {job_id}")
            record = self.get_job(job_id)
            if record is None or record.state != "running" or record.lease_owner != worker_id:
                raise ControlJobLeaseLostError(f"control job cannot be marked running: {job_id}")
            payload = {
                "state": "running",
                "lease_owner": worker_id,
                "lease_expires_at": _iso(record.lease_expires_at),
                "attempt": record.attempt,
            }
            self.append_event(job_id=job_id, event_type="job_running", payload=payload)
            self._emit_job_outbox_event(
                record=record,
                event_type="job_running",
                payload=payload,
            )

    def complete_job(
        self,
        *,
        job_id: str,
        run_id: str | None = None,
        pipeline_id: str | None = None,
        capability_manifest_ref: str | None = None,
        progress: dict[str, Any] | None = None,
        method_execution_selection: object | None = None,
        method_metric_projection_admission: object | None = None,
        selected_evaluation_frontier_cas: AcquisitionEvaluationFrontierCAS | None = None,
        expected_lease_owner: str | None = None,
        expected_attempt: int | None = None,
    ) -> AcquisitionEvaluationFrontierRecord | None:
        """Complete one job and optionally select its owner-verified evaluation atomically."""
        fence = self._resolve_job_execution_fence(
            job_id=job_id,
            expected_lease_owner=expected_lease_owner,
            expected_attempt=expected_attempt,
        )
        if selected_evaluation_frontier_cas is not None:
            _validate_acquisition_evaluation_frontier_cas(
                selected_evaluation_frontier_cas,
                require_replacement=True,
            )
            if selected_evaluation_frontier_cas.key.source_job_id != job_id:
                raise ValueError("acquisition_evaluation_frontier_completion_source_mismatch")
        with self._job_transaction():
            return self._complete_job_in_transaction(
                job_id=job_id,
                run_id=run_id,
                pipeline_id=pipeline_id,
                capability_manifest_ref=capability_manifest_ref,
                progress=progress,
                method_execution_selection=method_execution_selection,
                method_metric_projection_admission=method_metric_projection_admission,
                selected_evaluation_frontier_cas=selected_evaluation_frontier_cas,
                fence=fence,
            )

    def _terminal_progress_with_current_source_projection(
        self,
        *,
        job_id: str,
        progress: dict[str, Any],
        fence: tuple[str, int] | None,
    ) -> dict[str, Any]:
        """Carry one current fenced row's typed candidate projections at termination.

        Terminal progress replaces the running snapshot. The owner is rederived
        from the creation admission and worker fence; adjacent typed candidate
        projections are copied only from that same current row. With no owner
        derivable, progress stays unowned and owner-bearing values fail closed.
        This preserves projections, not authority: downstream consumers still
        validate refs, attestations, and phase-barrier evidence.
        """
        from polisyos.runtime.quality.phase_barriers import (
            _execution_owner_binding_from_admission,
            _validated_execution_owner_binding,
        )
        from polisyos.runtime.quality.refs import RuntimeQualityAuthorityRefs
        from polisyos.runtime.quality.report_registry import QUALITY_REPORT_REF_KEYS
        from polisyos.runtime.quality.run_state import RunIntentBinding

        admission = None
        if fence is not None:
            try:
                admission = self.current_execution_job_admission()
            except ControlJobExecutionAdmissionError:
                admission = None
            except ControlJobLeaseLostError:
                admission = None

        admitted_job = admission.job if admission is not None else None
        admission_matches_fence = (
            (
                admitted_job is not None
                and admitted_job.job_id == job_id
                and admitted_job.state == "running"
                and admitted_job.attempt == fence[1]
                and admission.attempt == fence[1]
                and admitted_job.lease_owner == fence[0]
            )
            if fence is not None
            else False
        )

        current_owner_binding: dict[str, object] | None = None
        if admission_matches_fence and admission is not None and admitted_job is not None:
            current_job = admitted_job
            current_progress = current_job.progress
            current_owner_binding = _execution_owner_binding_from_admission(
                admission,
                expected_job_id=job_id,
                expected_run_id=str(current_job.run_id or ""),
                expected_effective_profile=current_job.effective_execution_profile,
                expected_scope={
                    "tenant_id": admission.scope.tenant_id,
                    "cell_id": admission.scope.cell_id,
                },
            )
        else:
            # This read lets every unavailable-fence/admission path inspect the
            # target row for owner-bearing projections. It does not establish a
            # current worker identity and is never an owner derivation source.
            current_record = self.get_job(job_id)
            current_progress = current_record.progress if current_record is not None else {}

        owner_projection_keys = ("execution_owner_binding", "run_intent_binding")
        if current_owner_binding is None:
            if any(
                key in source
                for source in (current_progress, progress)
                for key in owner_projection_keys
            ):
                raise ControlJobLeaseLostError("control_job_terminal_owner_binding_not_current")
            return progress

        # The exact current owner is recomputable from the immutable creation
        # admission and live worker fence. A prior progress snapshot is not the
        # source of truth, but a present projection must agree with that source.
        if "execution_owner_binding" in current_progress:
            persisted_owner_binding = _validated_execution_owner_binding(
                current_progress["execution_owner_binding"],
                expected=current_owner_binding,
            )
            if persisted_owner_binding != current_owner_binding:
                raise ControlJobLeaseLostError("control_job_terminal_owner_binding_not_current")

        if "execution_owner_binding" in progress:
            supplied_owner_binding = _validated_execution_owner_binding(
                progress["execution_owner_binding"],
                expected=current_owner_binding,
            )
            if supplied_owner_binding != current_owner_binding:
                raise ControlJobLeaseLostError(
                    "control_job_terminal_progress_owner_binding_conflict"
                )

        current_intent_binding: RunIntentBinding | None = None
        if "run_intent_binding" in current_progress:
            try:
                parsed_intent = RunIntentBinding.model_validate(
                    current_progress["run_intent_binding"]
                )
            except (TypeError, ValueError) as exc:
                raise ControlJobLeaseLostError(
                    "control_job_terminal_progress_source_projection_conflict"
                ) from exc
            if (
                parsed_intent.run_id != current_owner_binding["run_id"]
                or parsed_intent.tenant_id != current_owner_binding["tenant_id"]
                or parsed_intent.requested_profile
                != current_owner_binding["requested_execution_profile"]
            ):
                raise ControlJobLeaseLostError(
                    "control_job_terminal_progress_source_projection_conflict"
                )
            current_intent_binding = parsed_intent

        if "run_intent_binding" in progress:
            try:
                supplied_intent = RunIntentBinding.model_validate(progress["run_intent_binding"])
            except (TypeError, ValueError) as exc:
                raise ControlJobLeaseLostError(
                    "control_job_terminal_progress_source_projection_conflict"
                ) from exc
            if current_intent_binding is None or supplied_intent != current_intent_binding:
                raise ControlJobLeaseLostError(
                    "control_job_terminal_progress_source_projection_conflict"
                )

        terminal_progress = dict(progress)
        terminal_progress["execution_owner_binding"] = current_owner_binding
        if current_intent_binding is not None:
            terminal_progress["run_intent_binding"] = current_intent_binding.model_dump(mode="json")

        current_projection_keys = (
            "temporal_scope_request_binding",
            "temporal_scope_context_world_read_bindings",
            "runtime_quality_refs",
            "runtime_quality_artifact_refs",
            "runtime_quality_projection",
            "diagnostic_event_log_ref",
            "diagnostic_events",
            "trust_boundary_attestations",
        )
        current_quality_refs = current_progress.get("runtime_quality_refs")
        current_quality_ref_keys: tuple[str, ...] = ()
        if "runtime_quality_refs" in current_progress:
            current_quality_ref_resolution = RuntimeQualityAuthorityRefs.from_runtime_payloads(
                job_payload={"runtime_quality_refs": current_quality_refs}
            )
            if current_quality_ref_resolution.rejections:
                raise ControlJobLeaseLostError(
                    "control_job_terminal_progress_source_projection_conflict"
                )
            if isinstance(current_quality_refs, Mapping):
                current_quality_ref_keys = tuple(sorted(current_quality_ref_resolution.refs))
                for key in current_quality_ref_keys:
                    if (
                        key in current_progress
                        and current_progress[key] != current_quality_refs[key]
                    ):
                        raise ControlJobLeaseLostError(
                            "control_job_terminal_progress_source_projection_conflict"
                        )
        for key in (
            *current_projection_keys,
            *QUALITY_REPORT_REF_KEYS,
            *current_quality_ref_keys,
        ):
            source_present = key in current_progress
            supplied_present = key in progress
            if supplied_present and (not source_present or progress[key] != current_progress[key]):
                raise ControlJobLeaseLostError(
                    "control_job_terminal_progress_source_projection_conflict"
                )
            if source_present:
                terminal_progress[key] = deepcopy(current_progress[key])

        phase_projection_only_keys = (
            "runtime_quality_diagnostic_events",
            "runtime_diagnostic_event_status",
            "diagnostic_event_scope_status",
            "runtime_diagnostic_event_limitation_code",
            "diagnostic_event_ids",
            "diagnostic_event_authority",
            "scientist_workflow",
        )
        for key in phase_projection_only_keys:
            terminal_progress.pop(key, None)

        return terminal_progress

    def _complete_job_in_transaction(
        self,
        *,
        job_id: str,
        run_id: str | None,
        pipeline_id: str | None,
        capability_manifest_ref: str | None,
        progress: dict[str, Any] | None,
        method_execution_selection: object | None,
        method_metric_projection_admission: object | None,
        selected_evaluation_frontier_cas: AcquisitionEvaluationFrontierCAS | None,
        fence: tuple[str, int] | None,
    ) -> AcquisitionEvaluationFrontierRecord | None:
        """Apply one completion and all of its evidence rows in one transaction."""
        if self._lock_job_state(job_id) not in {"pending", "running"}:
            raise ControlJobLeaseLostError("control job cannot complete from terminal state")
        now = _utc_now()
        selection_payload: dict[str, Any] | None = None
        if method_execution_selection is not None:
            from pydantic import TypeAdapter

            from polisyos.core.contracts.runtime import (
                DirectMethodExecutionSelection,
                GraphMethodExecutionSelection,
                MethodExecutionSelection,
            )

            if fence is None:
                raise ControlJobLeaseLostError(
                    "method_execution_selection_requires_current_job_fence"
                )
            selection = TypeAdapter(MethodExecutionSelection).validate_python(
                method_execution_selection
            )
            if not isinstance(
                selection,
                (DirectMethodExecutionSelection, GraphMethodExecutionSelection),
            ):
                raise ValueError("method_execution_selection_discriminator_invalid")
            if (
                selection.job_id != job_id
                or selection.run_id != str(run_id or "")
                or selection.attempt != fence[1]
            ):
                raise ValueError("method_execution_selection_fence_tuple_mismatch")
            current = self._fetchone(
                """
                SELECT job_kind, state, run_id, attempt, lease_owner, lease_expires_at
                FROM control_jobs WHERE job_id = ?
                """,
                (job_id,),
            )
            if current is None:
                raise ControlJobLeaseLostError("method_execution_selection_job_missing")
            if isinstance(current, Mapping):
                current_values = (
                    current.get("job_kind"),
                    current.get("state"),
                    current.get("run_id"),
                    current.get("attempt"),
                    current.get("lease_owner"),
                    current.get("lease_expires_at"),
                )
            else:
                current_values = (
                    current[0],
                    current[1],
                    current[2],
                    current[3],
                    current[4],
                    current[5],
                )
            current_expires_at = _parse_dt(current_values[5])
            if (
                current_values[0] != "workflow_run"
                or current_values[1] != "running"
                or current_values[2] != selection.run_id
                or int(current_values[3] or 0) != fence[1]
                or current_values[4] != fence[0]
                or current_expires_at is None
                or current_expires_at <= now
            ):
                raise ControlJobLeaseLostError("method_execution_selection_current_fence_mismatch")
            if isinstance(selection, GraphMethodExecutionSelection):
                if selection.metric_verification_status == "verified":
                    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
                        is_verified_method_metric_projection_admission,
                    )

                    if not is_verified_method_metric_projection_admission(
                        method_metric_projection_admission
                    ):
                        raise ValueError("method_metric_projection_admission_not_verified")
                    source_tuple = method_metric_projection_admission.source_tuple
                    source_candidate_ref = getattr(
                        method_metric_projection_admission,
                        "source_candidate_ref",
                        None,
                    )
                    projection = selection.method_metric_projection
                    if projection is None:
                        raise ValueError("method_metric_projection_selection_missing")
                    if (
                        source_tuple.job_id != selection.job_id
                        or source_tuple.run_id != selection.run_id
                        or source_tuple.attempt != selection.attempt
                        or source_tuple.method_result_ref != selection.method_result_ref
                        or source_tuple.simulation_result_ref != selection.simulation_result_ref
                        or source_tuple.method_execution_bundle_ref
                        != selection.method_execution_bundle_ref
                        or source_tuple.method_metric_binding_set_ref
                        != selection.method_metric_binding_set_ref
                        or source_candidate_ref != selection.source_candidate_ref
                        or method_metric_projection_admission.vector_ref != projection.vector_ref
                        or method_metric_projection_admission.verifier_revision
                        != projection.verifier_revision
                        or method_metric_projection_admission.verifier_implementation_sha256
                        != projection.verifier_implementation_sha256
                    ):
                        raise ValueError("method_metric_projection_source_tuple_mismatch")
                elif method_metric_projection_admission is not None:
                    raise ValueError("unselected_method_metric_projection_admission")
            elif method_metric_projection_admission is not None:
                raise ValueError("direct_method_has_graph_metric_projection_admission")
            selection_payload = selection.model_dump(mode="json")
            existing = self._fetchone(
                "SELECT method_execution_selection_json FROM control_jobs WHERE job_id = ?",
                (job_id,),
            )
            existing_raw = (
                existing[0]
                if existing is not None and not isinstance(existing, Mapping)
                else (existing.get("method_execution_selection_json") if existing else None)
            )
            if existing_raw is not None:
                try:
                    existing_payload = json.loads(str(existing_raw))
                except (TypeError, json.JSONDecodeError) as exc:
                    raise RuntimeError("method_execution_selection_existing_malformed") from exc
                if existing_payload != selection_payload:
                    raise ValueError("method_execution_selection_immutable_conflict")
        if progress is not None:
            progress = _progress_with_quality_scorecard_summary(progress)
            progress = self._terminal_progress_with_current_source_projection(
                job_id=job_id,
                progress=progress,
                fence=fence,
            )
            completion_failure_message = _completion_failure_message(progress)
            if completion_failure_message is not None:
                if selected_evaluation_frontier_cas is not None:
                    raise ValueError("acquisition_evaluation_frontier_completion_not_successful")
                self._fail_job_in_transaction(
                    job_id=job_id,
                    error_message=completion_failure_message,
                    capability_manifest_ref=capability_manifest_ref,
                    progress=progress,
                    fence=fence,
                )
                return
            self._upsert_progress_unchecked(job_id=job_id, progress=progress)
        where, where_params = self._job_fence_where(
            job_id=job_id,
            fence=fence,
            now=now,
        )
        affected_rows = self._execute(
            f"""
            UPDATE control_jobs
            SET state = ?, run_id = COALESCE(?, run_id), pipeline_id = COALESCE(?, pipeline_id),
                capability_manifest_ref = COALESCE(?, capability_manifest_ref),
                method_execution_selection_json = COALESCE(method_execution_selection_json, ?),
                finished_at = ?, lease_owner = NULL, lease_expires_at = NULL, error_message = NULL
            WHERE {where}
            """,
            (
                "completed",
                run_id,
                pipeline_id,
                capability_manifest_ref,
                json.dumps(selection_payload, sort_keys=True)
                if selection_payload is not None
                else None,
                _iso(now),
                *where_params,
            ),
        )
        self._require_fenced_write(job_id=job_id, fence=fence, affected_rows=affected_rows)
        self._admit_terminal_publication(job_id=job_id, fence=fence, state="completed")
        event_payload: dict[str, Any] = {"state": "completed"}
        if selection_payload is not None:
            event_payload["method_execution_selection"] = selection_payload
        if fence is not None:
            event_payload.update({"lease_owner": fence[0], "attempt": fence[1]})
        self.append_event(job_id=job_id, event_type="job_completed", payload=event_payload)
        completed_event = self.get_job_terminal_source_event_record(job_id)
        record = self.get_job(job_id)
        if record is not None:
            self._emit_job_outbox_event(
                record=record,
                event_type="job_completed",
                payload={
                    **event_payload,
                    "progress": dict(progress or record.progress),
                },
            )
        if selection_payload is not None:
            from polisyos.core.contracts.runtime import (
                DirectMethodExecutionSelection,
                MethodExecutionSelection,
                RuntimeSearchHTECompletionDeliveryV1,
                _validate_method_execution_selection_wire_payload,
            )

            try:
                selected = _validate_method_execution_selection_wire_payload(selection_payload)
            except (TypeError, ValueError) as exc:
                raise ValueError("runtime_search_hte_completion_selection_invalid") from exc
            if (
                type(selected) is DirectMethodExecutionSelection
                and selected.method_version == "2.0.0"
                and selected.hte is not None
                and selected.hte.search_uncertainty_task_binding_ref is not None
            ):
                delivery = RuntimeSearchHTECompletionDeliveryV1(
                    job_id=selected.job_id,
                    run_id=selected.run_id,
                    attempt=selected.attempt,
                    completed_event_id=completed_event.event_id,
                    completed_event_payload_sha256=completed_event.payload_sha256,
                    search_uncertainty_task_binding_ref=(
                        selected.hte.search_uncertainty_task_binding_ref
                    ),
                )
                self.enqueue_outbox_event(
                    topic="control.search.hte_completed",
                    event_key=f"{job_id}:job_completed:{completed_event.event_id}",
                    job_id=job_id,
                    run_id=selected.run_id,
                    payload=delivery.model_dump(mode="json"),
                )
            if (
                type(selected) is DirectMethodExecutionSelection
                and selected.method_version == "2.0.0"
                and selected.hte is not None
            ):
                from polisyos.core.contracts.control import DecisionValidityEventRequest
                from polisyos.core.contracts.decision_validity import (
                    DecisionTriggerType,
                    DecisionValidityStatus,
                )

                source_run_id = selected.run_id
                source_job_id = selected.job_id
                source_attempt = selected.attempt
                completed_event_id = completed_event.event_id
                completed_event_payload_sha256 = completed_event.payload_sha256
                dedupe_key = _completed_hte_source_invalidation_dedupe_key(
                    source_run_id=source_run_id,
                    source_job_id=source_job_id,
                    source_attempt=source_attempt,
                    completed_event_id=completed_event_id,
                    completed_event_payload_sha256=completed_event_payload_sha256,
                )
                dependency_key = f"hte_completed_source_run:{source_run_id}"
                request = DecisionValidityEventRequest(
                    trigger_type=DecisionTriggerType.METRIC_INVALIDATION,
                    status=DecisionValidityStatus.STALE,
                    reason="completed_hte_source_owner_selection_updated",
                    dependency_keys=[dependency_key],
                    source_ref=(
                        f"control-job-event:{source_job_id}:{completed_event_id}:"
                        f"{completed_event_payload_sha256}"
                    ),
                    dedupe_key=dedupe_key,
                    occurred_at=completed_event.created_at,
                    payload={
                        "source_run_id": source_run_id,
                        "source_job_id": source_job_id,
                        "source_attempt": source_attempt,
                        "completed_event_id": completed_event_id,
                        "completed_event_payload_sha256": completed_event_payload_sha256,
                    },
                )
                self.enqueue_outbox_event(
                    topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
                    event_key=f"{source_job_id}:job_completed:{completed_event_id}",
                    job_id=source_job_id,
                    run_id=source_run_id,
                    payload=request.model_dump(mode="json"),
                )

        if selected_evaluation_frontier_cas is None:
            return None
        cas = selected_evaluation_frontier_cas
        if fence is None or self._job_execution_fence.get() != (job_id, fence[0], fence[1]):
            raise ControlJobLeaseLostError(
                "acquisition_evaluation_frontier_requires_current_job_fence"
            )
        proof = self._require_current_job_completion_proof()
        completed = proof.record
        if (
            proof.proof_phase != "completed"
            or proof.source_event.event_type != "job_completed"
            or completed.job_id != job_id
            or completed.kind != "natural_language_run"
            or completed.state != "completed"
            or completed.run_id != run_id
            or run_id is None
        ):
            raise ControlJobExecutionAdmissionError(
                "acquisition_evaluation_frontier_completion_source_not_verified"
            )
        scope = self.historical_completed_job_execution_scope(
            job_id=job_id,
            expected_run_id=run_id,
        )
        if (
            scope.status != "established"
            or scope.tenant_id != cas.key.tenant_id
            or scope.cell_id != cas.key.cell_id
        ):
            raise ControlJobExecutionAdmissionError(
                "acquisition_evaluation_frontier_completion_scope_mismatch"
            )
        compiled_id = completed.progress.get("compiled_recursive_generation_cycle_ref")
        try:
            compiled_ref = ArtifactRef.model_validate(
                completed.progress.get("compiled_recursive_generation_cycle_artifact_ref")
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "acquisition_evaluation_frontier_completed_output_not_selected"
            ) from exc
        selected_value = cas.replacement
        if (
            selected_value is None
            or compiled_ref.kind != "runtime.compiled_recursive_generation_cycle"
            or str(compiled_ref.artifact_id) != compiled_id
            or selected_value.selected_evaluation_witness_ref != str(compiled_ref.artifact_id)
        ):
            raise ValueError("acquisition_evaluation_frontier_completed_output_mismatch")
        return self._advance_acquisition_evaluation_frontier_in_transaction(
            cas,
            require_replacement=True,
        )

    def cancel_job(
        self,
        *,
        job_id: str,
        authorization_proof: object,
        operation_id: str,
        expected_lease_owner: str | None = None,
        expected_attempt: int | None = None,
    ) -> ControlJobRecord:
        """Fence publication for one job using its verified immutable scope.

        Cancellation is a durable authority revocation.  It deliberately makes
        no claim that an executing thread, process, provider call, or external
        side effect has physically stopped.
        """
        from polisyos.runtime.http.authorization import BoundActionPermissionVerification
        from polisyos.runtime.http.cancellation_admission import is_current_cancellation_authority
        from polisyos.runtime.http.permissions import RuntimePermission
        from polisyos.runtime.http.resource_binding import (
            BindingAuthority,
            BoundAuthorizationResource,
        )

        if type(
            authorization_proof
        ) is not BoundActionPermissionVerification or not is_current_cancellation_authority(
            authorization_proof
        ):
            raise ControlJobExecutionAdmissionError("control_job_cancellation_proof_invalid")
        verification = authorization_proof.verification
        bound = authorization_proof.bound_resource
        if (
            verification.requirement.permission is not RuntimePermission.JOBS_CANCEL
            or type(bound) is not BoundAuthorizationResource
            or bound.authority is not BindingAuthority.OWNERSHIP_VERIFIED
            or bound.requirement is not verification.requirement
            or not operation_id.strip()
        ):
            raise ControlJobExecutionAdmissionError("control_job_cancellation_proof_invalid")
        from polisyos.core.contracts.control import ControlJobCancellationRequest

        try:
            if (
                bound.resolved_context_kind != "runtime.control_job.cancellation.v1"
                or bound.resolved_context is None
            ):
                raise ValueError("cancellation context missing")
            authorized_request = ControlJobCancellationRequest.model_validate_json(
                bound.resolved_context
            )
        except (TypeError, ValueError) as exc:
            raise ControlJobExecutionAdmissionError(
                "control_job_cancellation_body_not_established"
            ) from exc
        if (
            authorized_request.operation_id != operation_id
            or authorized_request.expected_lease_owner != expected_lease_owner
            or authorized_request.expected_attempt != expected_attempt
        ):
            raise ControlJobExecutionAdmissionError("control_job_cancellation_body_mismatch")

        authorized_actor = verification.subject
        authorized_tenant_id = verification.tenant_id
        bound_selectors = dict(bound.canonical_selectors)
        if bound_selectors.get("job_id") != json.dumps(job_id):
            raise ControlJobExecutionAdmissionError("control_job_cancellation_job_mismatch")
        if (expected_lease_owner is None) != (expected_attempt is None):
            raise ValueError("control_job_cancellation_precondition_incomplete")
        if (
            getattr(self._human_decision_transaction, "sqlite_connection", None) is not None
            or getattr(self._human_decision_transaction, "postgres_cursor", None) is not None
        ):
            raise ControlJobExecutionAdmissionError("control_job_cancellation_nested_transaction")

        def admit_cancellation_commit() -> None:
            if not is_current_cancellation_authority(authorization_proof):
                raise ControlJobExecutionAdmissionError("control_job_cancellation_scope_expired")

        with self._job_transaction(commit_admission=admit_cancellation_commit):
            # Progress and cancellation must serialize on the same authoritative row.
            # Taking it before reading progress also lets an identical retry observe
            # the winning transaction rather than racing a stale snapshot.
            self._lock_job_state(job_id)
            record = self.get_job(job_id)
            if record is None:
                raise KeyError(job_id)
            scope, _ = self._reconcile_control_job_creation_envelope(record)
            if (
                scope.status != "established"
                or scope.tenant_id != authorized_tenant_id
                or not scope.cell_id
                or bound_selectors.get("cell_id") != json.dumps(scope.cell_id)
                or not authorized_actor.strip()
            ):
                raise ControlJobExecutionAdmissionError(
                    "control_job_cancellation_scope_not_established"
                )
            if record.state == "cancelled":
                # Classify client conflict only against a fully established
                # durable receipt, including source event and outbox. Integrity
                # failures remain internal even when the new request differs.
                verified = self.get_cancelled_job_verified_record(job_id)
                cancellation = verified.progress["cancellation"]
                if (
                    cancellation.get("authorized_actor") != authorized_actor
                    or cancellation.get("tenant_id") != authorized_tenant_id
                    or cancellation.get("operation_id") != operation_id
                    or cancellation.get("body_sha256") != bound.body_sha256
                    or cancellation.get("expected_attempt") != expected_attempt
                    or cancellation.get("expected_lease_owner") != expected_lease_owner
                ):
                    raise ControlJobCancellationConflictError(
                        "control job cancellation identity changed"
                    )
                if not is_current_cancellation_authority(authorization_proof):
                    raise ControlJobExecutionAdmissionError(
                        "control_job_cancellation_scope_expired"
                    )
                return verified
            if record.state in {"completed", "failed"}:
                raise ControlJobCancellationConflictError(
                    "control job already has a terminal disposition"
                )
            if record.state == "running" and (
                expected_lease_owner != record.lease_owner or expected_attempt != record.attempt
            ):
                raise ControlJobCancellationConflictError(
                    "control job cancellation attempt is stale"
                )
            if record.state == "pending" and expected_lease_owner is not None:
                raise ControlJobCancellationConflictError(
                    "pending control job has no leased attempt"
                )
            if not is_current_cancellation_authority(authorization_proof):
                raise ControlJobExecutionAdmissionError("control_job_cancellation_scope_expired")
            now = _utc_now()
            affected = self._execute(
                """
                UPDATE control_jobs SET state = 'cancelled', finished_at = ?,
                    lease_owner = NULL, lease_expires_at = NULL
                WHERE job_id = ? AND state = ? AND attempt = ?
                  AND ((? IS NULL AND lease_owner IS NULL) OR lease_owner = ?)
                """,
                (
                    _iso(now),
                    job_id,
                    record.state,
                    record.attempt,
                    record.lease_owner,
                    record.lease_owner,
                ),
            )
            if affected != 1:
                raise ControlJobCancellationConflictError("control job changed during cancellation")
            progress = dict(record.progress)
            progress["cancellation"] = {
                "authorized_actor": authorized_actor,
                "tenant_id": authorized_tenant_id,
                "cell_id": scope.cell_id,
                "operation_id": operation_id,
                "body_sha256": bound.body_sha256,
                "expected_attempt": expected_attempt,
                "expected_lease_owner": expected_lease_owner,
                "disposition": "publication_fenced",
                "physical_stop_status": "not_established",
                "cancelled_attempt": record.attempt,
                "cancelled_lease_owner": record.lease_owner,
            }
            self._upsert_progress_unchecked(job_id=job_id, progress=progress)
            payload = dict(progress["cancellation"])
            payload["state"] = "cancelled"
            self.append_event(job_id=job_id, event_type="job_cancelled", payload=payload)
            cancelled = self.get_job(job_id)
            if cancelled is None:
                raise ControlJobLeaseLostError("cancelled control job disappeared")
            self._emit_job_outbox_event(
                record=cancelled, event_type="job_cancelled", payload=payload
            )
            # The outbox owner deduplicates by key: validate its persisted
            # payload in this transaction before allowing the row to commit.
            verified = self.get_cancelled_job_verified_record(job_id)
            if not is_current_cancellation_authority(authorization_proof):
                raise ControlJobExecutionAdmissionError("control_job_cancellation_scope_expired")
            return verified

    def fail_job(
        self,
        *,
        job_id: str,
        error_message: str,
        capability_manifest_ref: str | None = None,
        progress: dict[str, Any] | None = None,
        expected_lease_owner: str | None = None,
        expected_attempt: int | None = None,
        owned_attempt_failure_disposition: Literal["input_refused"] | None = None,
        owned_attempt_anchor_ref: OwnedAttemptAnchorRef | None = None,
    ) -> None:
        """Mark one job failed, persist a truncated error message, and emit failure events."""
        fence = self._resolve_job_execution_fence(
            job_id=job_id,
            expected_lease_owner=expected_lease_owner,
            expected_attempt=expected_attempt,
        )
        with self._job_transaction():
            self._fail_job_in_transaction(
                job_id=job_id,
                error_message=error_message,
                capability_manifest_ref=capability_manifest_ref,
                progress=progress,
                fence=fence,
                owned_attempt_failure_disposition=owned_attempt_failure_disposition,
                owned_attempt_anchor_ref=owned_attempt_anchor_ref,
            )

    def _fail_job_in_transaction(
        self,
        *,
        job_id: str,
        error_message: str,
        capability_manifest_ref: str | None,
        progress: dict[str, Any] | None,
        fence: tuple[str, int] | None,
        owned_attempt_failure_disposition: Literal["input_refused"] | None = None,
        owned_attempt_anchor_ref: OwnedAttemptAnchorRef | None = None,
    ) -> None:
        """Apply one failure and its dead-letter/event rows in one transaction."""
        if (owned_attempt_failure_disposition is None) != (owned_attempt_anchor_ref is None):
            raise ValueError("control_job_owned_attempt_failure_binding_incomplete")
        if owned_attempt_failure_disposition is not None:
            from polisyos.core.contracts.owned_attempt_anchor import OwnedAttemptAnchorRef

            if (
                fence is None
                or owned_attempt_failure_disposition != "input_refused"
                or type(owned_attempt_anchor_ref) is not OwnedAttemptAnchorRef
                or owned_attempt_anchor_ref.kind != "runtime.owned_attempt_anchor"
                or owned_attempt_anchor_ref.media_type != "application/json"
                or owned_attempt_anchor_ref.manifest_profile_sha256 is None
            ):
                raise ValueError("control_job_owned_attempt_failure_binding_invalid")
        now = _utc_now()
        if progress is not None:
            progress = _progress_with_quality_scorecard_summary(progress)
            progress = self._terminal_progress_with_current_source_projection(
                job_id=job_id,
                progress=progress,
                fence=fence,
            )
        where, where_params = self._job_fence_where(
            job_id=job_id,
            fence=fence,
            now=now,
        )
        affected_rows = self._execute(
            f"""
            UPDATE control_jobs
            SET state = ?, capability_manifest_ref = COALESCE(?, capability_manifest_ref),
                finished_at = ?, lease_owner = NULL, lease_expires_at = NULL, error_message = ?
            WHERE {where}
            """,
            (
                "failed",
                capability_manifest_ref,
                _iso(now),
                error_message[:2000],
                *where_params,
            ),
        )
        self._require_fenced_write(job_id=job_id, fence=fence, affected_rows=affected_rows)
        self._admit_terminal_publication(job_id=job_id, fence=fence, state="failed")
        if progress is not None:
            self.upsert_progress(job_id=job_id, progress=progress)
        event_payload: dict[str, Any] = {
            "state": "failed",
            "error_message": error_message[:500],
        }
        if fence is not None:
            event_payload.update({"lease_owner": fence[0], "attempt": fence[1]})
        if owned_attempt_failure_disposition is not None:
            event_payload["owned_attempt_failure_disposition"] = owned_attempt_failure_disposition
            event_payload["owned_attempt_anchor_ref"] = owned_attempt_anchor_ref.model_dump(
                mode="json"
            )
        self.append_event(
            job_id=job_id,
            event_type="job_failed",
            payload=event_payload,
        )
        record = self.get_job(job_id)
        if record is not None:
            self._enqueue_dead_letter_job(record=record, failed_at=now)
            self._emit_job_outbox_event(
                record=record,
                event_type="job_failed",
                payload={
                    **event_payload,
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
        """Update a job manifest ref only while its bound lease remains current."""
        fence = self._resolve_job_execution_fence(
            job_id=job_id,
            expected_lease_owner=None,
            expected_attempt=None,
        )
        if fence is None:
            raise ControlJobLeaseLostError(
                "control job manifest update requires an active execution fence"
            )
        with self._job_transaction():
            where, where_params = self._job_fence_where(
                job_id=job_id,
                fence=fence,
                now=_utc_now(),
            )
            affected_rows = self._execute(
                f"UPDATE control_jobs SET capability_manifest_ref = ? WHERE {where}",
                (capability_manifest_ref, *where_params),
            )
            self._require_fenced_write(
                job_id=job_id,
                fence=fence,
                affected_rows=affected_rows,
            )

    def update_progress_state(
        self,
        *,
        job_id: str,
        state: str,
        progress: dict[str, Any],
        error_message: str | None = None,
        expected_lease_owner: str | None = None,
        expected_attempt: int | None = None,
    ) -> None:
        """Update progress/error state and emit a `job_progress` event/outbox row."""
        fence = self._resolve_job_execution_fence(
            job_id=job_id,
            expected_lease_owner=expected_lease_owner,
            expected_attempt=expected_attempt,
        )
        with self._job_transaction():
            progress = _progress_with_quality_scorecard_summary(progress)
            existing = self.get_job(job_id)
            if existing is not None and "temporal_scope_request_binding" in existing.progress:
                source_binding = existing.progress["temporal_scope_request_binding"]
                if (
                    "temporal_scope_request_binding" in progress
                    and progress["temporal_scope_request_binding"] != source_binding
                ):
                    raise ControlJobLeaseLostError("nl_temporal_scope_progress_binding_conflict")
                progress = {**progress, "temporal_scope_request_binding": source_binding}
                source_refs = existing.progress.get("runtime_quality_artifact_refs")
                if not isinstance(source_refs, Mapping) or "time_context_ref" not in source_refs:
                    raise ControlJobLeaseLostError("nl_temporal_scope_progress_ref_missing")
                updated_refs = progress.get("runtime_quality_artifact_refs", {})
                if not isinstance(updated_refs, Mapping):
                    raise ControlJobLeaseLostError("nl_temporal_scope_progress_ref_invalid")
                if (
                    "time_context_ref" in updated_refs
                    and updated_refs["time_context_ref"] != source_refs["time_context_ref"]
                ):
                    raise ControlJobLeaseLostError("nl_temporal_scope_progress_ref_conflict")
                progress["runtime_quality_artifact_refs"] = {
                    **updated_refs,
                    "time_context_ref": source_refs["time_context_ref"],
                }
            binding_set_key = "temporal_scope_context_world_read_bindings"
            existing_bindings = existing.progress.get(binding_set_key, {}) if existing else {}
            incoming_bindings = progress.get(binding_set_key, {})
            if not isinstance(existing_bindings, Mapping) or not isinstance(
                incoming_bindings, Mapping
            ):
                raise ControlJobLeaseLostError("nl_temporal_scope_context_world_read_set_invalid")
            if existing_bindings or incoming_bindings:
                retained = dict(existing_bindings)
                for invocation_key, value in incoming_bindings.items():
                    if invocation_key in retained and retained[invocation_key] != value:
                        raise ControlJobLeaseLostError(
                            "nl_temporal_scope_context_world_read_progress_binding_conflict"
                        )
                    retained[invocation_key] = value
                source_refs = (
                    existing.progress.get("runtime_quality_artifact_refs", {}) if existing else {}
                )
                updated_refs = progress.get("runtime_quality_artifact_refs", {})
                if not isinstance(source_refs, Mapping) or not isinstance(updated_refs, Mapping):
                    raise ControlJobLeaseLostError(
                        "nl_temporal_scope_context_world_read_refs_invalid"
                    )
                retained_refs = dict(updated_refs)
                for invocation_key, value in retained.items():
                    if (
                        not isinstance(invocation_key, str)
                        or not isinstance(value, Mapping)
                        or value.get("invocation_key") != invocation_key
                        or not isinstance(value.get("context_job_ref"), Mapping)
                    ):
                        raise ControlJobLeaseLostError(
                            "nl_temporal_scope_context_world_read_entry_invalid"
                        )
                    ref_key = "temporal_context_candidate:" + invocation_key
                    declared_ref = value["context_job_ref"]
                    if invocation_key in existing_bindings:
                        if source_refs.get(ref_key) != declared_ref:
                            raise ControlJobLeaseLostError(
                                "nl_temporal_scope_context_world_read_ref_missing"
                            )
                        if ref_key in retained_refs and retained_refs[ref_key] != declared_ref:
                            raise ControlJobLeaseLostError(
                                "nl_temporal_scope_context_world_read_ref_conflict"
                            )
                    elif retained_refs.get(ref_key) != declared_ref:
                        raise ControlJobLeaseLostError(
                            "nl_temporal_scope_context_world_read_ref_missing"
                        )
                    retained_refs[ref_key] = declared_ref
                progress = {
                    **progress,
                    binding_set_key: retained,
                    "runtime_quality_artifact_refs": retained_refs,
                }
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
            where, where_params = self._job_fence_where(
                job_id=job_id,
                fence=fence,
                now=_utc_now(),
            )
            affected_rows = self._execute(
                f"UPDATE control_jobs SET error_message = COALESCE(?, error_message) WHERE {where}",
                (error_message, *where_params),
            )
            self._require_fenced_write(
                job_id=job_id,
                fence=fence,
                affected_rows=affected_rows,
            )
            event_payload: dict[str, Any] = {"state": state, **progress}
            if fence is not None:
                event_payload.update({"lease_owner": fence[0], "attempt": fence[1]})
            self.append_event(
                job_id=job_id,
                event_type="job_progress",
                payload=event_payload,
            )
            record = self.get_job(job_id)
            if record is not None:
                self._emit_job_outbox_event(
                    record=record,
                    event_type="job_progress",
                    payload=event_payload,
                )

    def renew_job_lease(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_seconds: int = 60,
        expected_attempt: int | None = None,
    ) -> bool:
        """Extend a running job lease when the heartbeat still matches `worker_id`."""
        now = _utc_now()
        lease_expires_at = now + timedelta(seconds=max(lease_seconds, 1))
        attempt_clause = ""
        attempt_params: tuple[Any, ...] = ()
        if expected_attempt is not None:
            if type(expected_attempt) is not int or expected_attempt < 1:
                raise ValueError("control job attempt must be a positive integer")
            attempt_clause = " AND attempt = ?"
            attempt_params = (expected_attempt,)
        try:
            affected_rows = self._execute(
                f"""
                UPDATE control_jobs
                SET lease_expires_at = ?
                WHERE job_id = ? AND state = 'running' AND lease_owner = ?
                  AND lease_expires_at IS NOT NULL AND lease_expires_at > ?{attempt_clause}
                """,
                (_iso(lease_expires_at), job_id, worker_id, _iso(now), *attempt_params),
            )
        except ControlJobLeaseLostError:
            return False
        return affected_rows == 1

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
        require_new: bool = False,
    ) -> ControlOutboxRecord:
        """Insert a keyed outbox event, optionally refusing any prior winner."""
        if topic.startswith(("control.child.release.", "control.child.budget.")):
            raise ValueError("child_release_outbox_reserved_for_owner")
        if require_new and not event_key:
            raise ValueError("control_job_outbox_new_requires_key")
        if topic == "control.search.hte_completed":
            resource = getattr(self._human_decision_transaction, "sqlite_connection", None)
            if resource is None:
                resource = getattr(self._human_decision_transaction, "postgres_cursor", None)
            if resource is None:
                with self._job_transaction():
                    return self.enqueue_outbox_event(
                        topic=topic,
                        payload=payload,
                        job_id=job_id,
                        run_id=run_id,
                        event_key=event_key,
                        require_new=require_new,
                    )
        if event_key:
            existing = self._get_outbox_event_by_key(topic=topic, event_key=event_key)
            if existing is not None:
                if require_new:
                    raise ControlJobLeaseLostError("control_job_outbox_already_exists")
                if topic == _COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC and (
                    existing.job_id != job_id
                    or existing.run_id != run_id
                    or existing.payload != payload
                ):
                    raise ValueError("completed_hte_validity_outbox_immutable_conflict")
                if topic in {
                    "control.search.hte_completed",
                    _COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
                }:
                    self._ensure_control_outbox_delivery_order(existing)
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
        if topic in {"control.search.hte_completed", _COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC}:
            self._ensure_control_outbox_delivery_order(record)
        return record

    def _ensure_control_outbox_delivery_order(self, record: ControlOutboxRecord) -> None:
        """Bind one selected outbox topic row to a monotonic order in its transaction."""
        parameters = (record.event_id, _iso(record.created_at))
        if self.backend == "sqlite":
            self._execute(
                "INSERT OR IGNORE INTO control_search_hte_delivery_order "
                "(event_id, created_at) VALUES (?, ?)",
                parameters,
            )
        else:
            self._execute(
                "INSERT INTO control_search_hte_delivery_order (event_id, created_at) "
                "VALUES (?, ?) ON CONFLICT (event_id) DO NOTHING",
                parameters,
            )

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
        """Publish one pending outbox event and increment its counter only once."""
        now = _utc_now()
        self._execute(
            """
            UPDATE control_outbox_events
            SET state = ?, published_at = ?, attempt = attempt + 1, error_message = NULL
            WHERE event_id = ? AND state = ?
            """,
            ("published", _iso(now), event_id, "pending"),
        )

    def record_outbox_delivery_failure(self, *, event_id: str, reason_code: str) -> None:
        """Retain a typed delivery failure while keeping its outbox row retryable."""
        normalized = str(reason_code).strip()
        if not normalized or len(normalized) > 160:
            raise ValueError("control_outbox_delivery_failure_reason_invalid")
        self._execute(
            """
            UPDATE control_outbox_events
            SET attempt = attempt + 1, error_message = ?
            WHERE event_id = ? AND state = ?
            """,
            (normalized, event_id, "pending"),
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

    def begin_runtime_operation_intent(
        self,
        key: RuntimeOperationIntentKey,
    ) -> RuntimeOperationIntentClaim:
        """Atomically admit one owner for a purpose-scoped request intent."""

        if type(key) is not RuntimeOperationIntentKey:
            raise TypeError("key must be a RuntimeOperationIntentKey")
        owner_token = uuid.uuid4().hex
        now = _iso(_utc_now())
        with self._job_transaction():
            self._execute(
                """
                INSERT INTO runtime_operation_intents (
                    purpose, tenant_id, cell_id, actor_subject_sha256, scope_kind, scope_id, run_id, intent_id,
                    body_sha256, state, owner_token, result_ref_json, event_id,
                    reason_code, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, NULL, NULL, NULL, ?, ?)
                ON CONFLICT (
                    purpose, tenant_id, cell_id, actor_subject_sha256, scope_kind, scope_id, intent_id
                ) DO NOTHING
                """,
                (
                    *key.scope_identity[:4],
                    key.scope_kind,
                    key.scope_id,
                    key.run_id,
                    key.intent_id,
                    key.body_sha256,
                    owner_token,
                    now,
                    now,
                ),
            )
            row = self._fetchone(
                self._runtime_operation_intent_select()
                + self._runtime_operation_intent_where()
                + self._runtime_operation_intent_lock_suffix(),
                key.scope_identity,
            )
        if row is None:
            raise RuntimeError("runtime operation intent insert/readback did not resolve")
        record = self._runtime_operation_intent_record(row)
        if record.body_sha256 != key.body_sha256:
            return RuntimeOperationIntentClaim("body_conflict", record)
        if record.status == "pending" and str(row["owner_token"]) == owner_token:
            return RuntimeOperationIntentClaim("owner", record, owner_token)
        return RuntimeOperationIntentClaim(record.status, record)

    def get_runtime_operation_intent(
        self,
        key: RuntimeOperationIntentKey,
    ) -> RuntimeOperationIntentSnapshot:
        """Read exact scoped intent state, returning unknown only for no row."""

        if type(key) is not RuntimeOperationIntentKey:
            raise TypeError("key must be a RuntimeOperationIntentKey")
        row = self._fetchone(
            self._runtime_operation_intent_select() + self._runtime_operation_intent_where(),
            key.scope_identity,
        )
        if row is None:
            return RuntimeOperationIntentSnapshot("unknown", None)
        record = self._runtime_operation_intent_record(row)
        return RuntimeOperationIntentSnapshot(record.status, record)

    def complete_runtime_operation_intent(
        self,
        *,
        key: RuntimeOperationIntentKey,
        owner_token: str,
        result_ref_json: str,
        event_id: str,
        publish: Callable[[], object],
    ) -> RuntimeOperationIntentRecord:
        """Commit the association event and completed intent in one store transaction.

        The writer and completed owner record share this store transaction, so a
        visible completed row always has the event that names its exact result.
        """

        if type(key) is not RuntimeOperationIntentKey:
            raise TypeError("key must be a RuntimeOperationIntentKey")
        if not isinstance(owner_token, str) or not owner_token:
            raise ValueError("owner_token is required")
        if not isinstance(result_ref_json, str) or not result_ref_json:
            raise ValueError("result_ref_json is required")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("event_id is required")
        with self._job_transaction():
            row = self._fetchone(
                self._runtime_operation_intent_select()
                + self._runtime_operation_intent_where()
                + self._runtime_operation_intent_lock_suffix(),
                key.scope_identity,
            )
            if row is None:
                raise RuntimeError("runtime operation intent is absent during completion")
            record = self._runtime_operation_intent_record(row)
            if record.body_sha256 != key.body_sha256:
                raise RuntimeError("runtime operation request body changed during completion")
            if record.status == "completed":
                if record.result_ref_json != result_ref_json or record.event_id != event_id:
                    raise RuntimeError("completed runtime operation intent changed its result")
                return record
            if record.status != "pending" or str(row["owner_token"]) != owner_token:
                raise RuntimeError("runtime operation intent is not owned by this producer")
            published = publish()
            published_event = getattr(getattr(published, "event", None), "event_id", None)
            if published_event != event_id:
                raise RuntimeError("published event does not match the operation intent")
            updated = _iso(_utc_now())
            count = self._execute(
                """
                UPDATE runtime_operation_intents
                SET state = 'completed', owner_token = NULL, result_ref_json = ?, event_id = ?,
                    reason_code = NULL, updated_at = ?
                WHERE purpose = ? AND tenant_id = ? AND cell_id = ?
                    AND actor_subject_sha256 = ? AND scope_kind = ? AND scope_id = ? AND intent_id = ?
                    AND body_sha256 = ? AND owner_token = ? AND state = 'pending'
                """,
                (
                    result_ref_json,
                    event_id,
                    updated,
                    *key.scope_identity,
                    key.body_sha256,
                    owner_token,
                ),
            )
            if count != 1:
                raise RuntimeError("runtime operation intent completion lost its owner row")
            final_row = self._fetchone(
                self._runtime_operation_intent_select() + self._runtime_operation_intent_where(),
                key.scope_identity,
            )
            if final_row is None:
                raise RuntimeError("completed runtime operation intent did not read back")
            return self._runtime_operation_intent_record(final_row)

    def complete_runtime_operation_intent_with_observation(
        self,
        *,
        key: RuntimeOperationIntentKey,
        owner_token: str,
        result_ref_json: str,
        event_id: str,
    ) -> RuntimeOperationIntentRecord:
        """Complete a shared owner after its domain event was inserted in this transaction."""

        if type(key) is not RuntimeOperationIntentKey:
            raise TypeError("key must be a RuntimeOperationIntentKey")
        if not owner_token or not result_ref_json or not event_id:
            raise ValueError("owner, result reference, and durable event are required")
        with self._job_transaction():
            row = self._fetchone(
                self._runtime_operation_intent_select()
                + self._runtime_operation_intent_where()
                + self._runtime_operation_intent_lock_suffix(),
                key.scope_identity,
            )
            if row is None:
                raise RuntimeError(
                    "runtime operation intent is absent during observation completion"
                )
            record = self._runtime_operation_intent_record(row)
            if record.body_sha256 != key.body_sha256:
                raise RuntimeError("runtime operation request body changed during completion")
            if record.status == "completed":
                if record.result_ref_json != result_ref_json or record.event_id != event_id:
                    raise RuntimeError("completed runtime operation intent changed its result")
                return record
            if record.status != "pending" or str(row["owner_token"]) != owner_token:
                raise RuntimeError("runtime operation intent is not owned by this observer")
            count = self._execute(
                """
                UPDATE runtime_operation_intents
                SET state = 'completed', owner_token = NULL, result_ref_json = ?, event_id = ?,
                    reason_code = NULL, updated_at = ?
                WHERE purpose = ? AND tenant_id = ? AND cell_id = ?
                    AND actor_subject_sha256 = ? AND scope_kind = ? AND scope_id = ? AND intent_id = ?
                    AND body_sha256 = ? AND owner_token = ? AND state = 'pending'
                """,
                (
                    result_ref_json,
                    event_id,
                    _iso(_utc_now()),
                    *key.scope_identity,
                    key.body_sha256,
                    owner_token,
                ),
            )
            if count != 1:
                raise RuntimeError("runtime operation intent completion lost its owner row")
            final_row = self._fetchone(
                self._runtime_operation_intent_select() + self._runtime_operation_intent_where(),
                key.scope_identity,
            )
            if final_row is None:
                raise RuntimeError("completed runtime operation intent did not read back")
            return self._runtime_operation_intent_record(final_row)

    def refuse_runtime_operation_intent(
        self,
        *,
        key: RuntimeOperationIntentKey,
        owner_token: str,
        reason_code: str,
    ) -> RuntimeOperationIntentRecord:
        """Record an owner refusal proven to precede all producer side effects."""

        return self._transition_runtime_operation_intent(
            key=key,
            owner_token=owner_token,
            target="refused",
            reason_code=reason_code,
        )

    def require_runtime_operation_recovery(
        self,
        *,
        key: RuntimeOperationIntentKey,
        owner_token: str,
        reason_code: str,
    ) -> RuntimeOperationIntentRecord:
        """Freeze an ambiguous partial attempt for reconciliation, never auto-replay."""

        return self._transition_runtime_operation_intent(
            key=key,
            owner_token=owner_token,
            target="recovery_required",
            reason_code=reason_code,
        )

    def _transition_runtime_operation_intent(
        self,
        *,
        key: RuntimeOperationIntentKey,
        owner_token: str,
        target: Literal["refused", "recovery_required"],
        reason_code: str,
    ) -> RuntimeOperationIntentRecord:
        if type(key) is not RuntimeOperationIntentKey:
            raise TypeError("key must be a RuntimeOperationIntentKey")
        if not isinstance(owner_token, str) or not owner_token:
            raise ValueError("owner_token is required")
        if (
            not isinstance(reason_code, str)
            or not reason_code
            or reason_code != reason_code.strip()
            or len(reason_code) > 120
        ):
            raise ValueError("reason_code must be a bounded typed code")
        with self._job_transaction():
            row = self._fetchone(
                self._runtime_operation_intent_select()
                + self._runtime_operation_intent_where()
                + self._runtime_operation_intent_lock_suffix(),
                key.scope_identity,
            )
            if row is None:
                raise RuntimeError("runtime operation intent is absent during transition")
            record = self._runtime_operation_intent_record(row)
            if record.body_sha256 != key.body_sha256:
                raise RuntimeError("runtime operation request body changed during transition")
            if record.status == target and record.reason_code == reason_code:
                return record
            if record.status != "pending" or str(row["owner_token"]) != owner_token:
                raise RuntimeError("runtime operation intent transition is not owned")
            count = self._execute(
                """
                UPDATE runtime_operation_intents
                SET state = ?, owner_token = NULL, reason_code = ?, updated_at = ?
                WHERE purpose = ? AND tenant_id = ? AND cell_id = ?
                    AND actor_subject_sha256 = ? AND scope_kind = ? AND scope_id = ? AND intent_id = ?
                    AND body_sha256 = ? AND owner_token = ? AND state = 'pending'
                """,
                (
                    target,
                    reason_code,
                    _iso(_utc_now()),
                    *key.scope_identity,
                    key.body_sha256,
                    owner_token,
                ),
            )
            if count != 1:
                raise RuntimeError("runtime operation intent transition lost its owner row")
            final_row = self._fetchone(
                self._runtime_operation_intent_select() + self._runtime_operation_intent_where(),
                key.scope_identity,
            )
            if final_row is None:
                raise RuntimeError("runtime operation intent did not read back after transition")
            return self._runtime_operation_intent_record(final_row)

    @staticmethod
    def _runtime_operation_intent_select() -> str:
        return (
            "SELECT purpose, tenant_id, cell_id, actor_subject_sha256, scope_kind, scope_id, run_id, intent_id, "
            "body_sha256, state, owner_token, result_ref_json, event_id, reason_code, "
            "created_at, updated_at FROM runtime_operation_intents"
        )

    @staticmethod
    def _runtime_operation_intent_where() -> str:
        return (
            " WHERE purpose = ? AND tenant_id = ? AND cell_id = ? "
            "AND actor_subject_sha256 = ? AND scope_kind = ? AND scope_id = ? AND intent_id = ?"
        )

    def _runtime_operation_intent_lock_suffix(self) -> str:
        return " FOR UPDATE" if self.backend == "postgres" else ""

    @staticmethod
    def _runtime_operation_intent_record(row: Any) -> RuntimeOperationIntentRecord:
        state = str(row["state"])
        if state not in {"pending", "completed", "refused", "recovery_required"}:
            raise RuntimeError("runtime operation intent has an unknown persisted state")
        return RuntimeOperationIntentRecord(
            purpose=str(row["purpose"]),
            tenant_id=str(row["tenant_id"]),
            cell_id=str(row["cell_id"]),
            actor_subject_sha256=str(row["actor_subject_sha256"]),
            run_id=str(row["run_id"]),
            intent_id=str(row["intent_id"]),
            body_sha256=str(row["body_sha256"]),
            status=cast(RuntimeOperationIntentStatus, state),
            result_ref_json=(
                str(row["result_ref_json"]) if row["result_ref_json"] is not None else None
            ),
            event_id=str(row["event_id"]) if row["event_id"] is not None else None,
            reason_code=(str(row["reason_code"]) if row["reason_code"] is not None else None),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            scope_kind=cast(Literal["run", "route"], str(row["scope_kind"])),
            scope_id=str(row["scope_id"]),
        )

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
            raise RuntimeError(f"Failed to persist diagnostic event {diagnostic_event.event_id}")
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
        selection_json = (
            row["method_execution_selection_json"]
            if "method_execution_selection_json" in row.keys()
            else None
        )
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
            method_execution_selection=(
                json.loads(selection_json) if selection_json is not None else None
            ),
        )

    def _row_to_acquisition_action_head(self, row: Any) -> AcquisitionActionHeadRecord:
        return AcquisitionActionHeadRecord(
            tenant_id=str(row["tenant_id"]),
            cell_id=str(row["cell_id"]),
            run_id=str(row["run_id"]),
            source_job_id=str(row["source_job_id"]),
            route_id=str(row["route_id"]),
            action_generation=int(row["action_generation"]),
            head_generation=int(row["head_generation"]),
            receipt_ref=str(row["receipt_ref"]),
            receipt_sha256=str(row["receipt_sha256"]),
            durable_event_id=str(row["durable_event_id"]),
            coarse_phase=str(row["coarse_phase"]),
            receipt_phase=str(row["receipt_phase"]),
            recovery_state=str(row["recovery_state"]),
            job_id=str(row["job_id"]),
            predecessor_receipt_ref=(
                str(row["predecessor_receipt_ref"])
                if row["predecessor_receipt_ref"] is not None
                else None
            ),
            created_at=_parse_dt(row["created_at"]) or _utc_now(),
            evaluation_frontier_before_ref=(
                str(row["evaluation_frontier_before_ref"])
                if row["evaluation_frontier_before_ref"] is not None
                else None
            ),
            evaluation_frontier_ref=(
                str(row["evaluation_frontier_ref"])
                if row["evaluation_frontier_ref"] is not None
                else None
            ),
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

    def _row_to_pre_admission_attempt(
        self,
        row: Any,
        event_rows: list[Any],
        shared_owner: RuntimeOperationIntentRecord,
    ) -> ControlPreAdmissionAttemptRecord:
        history: list[ControlPreAdmissionAttemptEventRecord] = []

        def parse_bound_timestamp(value: Any) -> datetime:
            if isinstance(value, datetime):
                if value.tzinfo is None or value.utcoffset() is None:
                    raise RuntimeError("pre-admission event timestamp is not timezone-bound")
                return value.astimezone(timezone.utc)
            if isinstance(value, str) and value:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None or parsed.utcoffset() is None:
                    raise RuntimeError("pre-admission event timestamp is not timezone-bound")
                return parsed.astimezone(timezone.utc)
            raise RuntimeError("pre-admission event timestamp is missing")

        attempt_id = row["attempt_id"]
        if not isinstance(attempt_id, str) or not attempt_id:
            raise RuntimeError("pre-admission attempt identity is missing")
        for event_row in event_rows:
            raw_payload = event_row["payload_json"]
            if not isinstance(raw_payload, str) or not raw_payload:
                raise RuntimeError("pre-admission event payload is missing")
            payload = json.loads(raw_payload)
            legacy_payload_keys = {
                "attempt_id",
                "event_id",
                "sequence",
                "event_type",
                "producer_event_ids",
                "producer_event_observation",
                "failure_code",
                "job_id",
            }
            canonical_payload_keys = legacy_payload_keys | {"producer_no_call_reason"}
            if not isinstance(payload, dict) or frozenset(payload) not in {
                frozenset(legacy_payload_keys),
                frozenset(canonical_payload_keys),
            }:
                raise RuntimeError("pre-admission event payload shape is malformed")
            event_id = event_row["event_id"]
            sequence = event_row["sequence_no"]
            event_type = event_row["event_type"]
            if (
                not isinstance(event_id, str)
                or not event_id
                or type(sequence) is not int
                or not isinstance(event_type, str)
                or payload["attempt_id"] != attempt_id
                or payload["event_id"] != event_id
                or type(payload["sequence"]) is not int
                or payload["sequence"] != sequence
                or payload["event_type"] != event_type
            ):
                raise RuntimeError("pre-admission event payload identity diverged from its row")
            refs = payload["producer_event_ids"]
            observation = payload["producer_event_observation"]
            failure_code = payload["failure_code"]
            no_call_reason = payload.get("producer_no_call_reason")
            job_id = payload["job_id"]
            try:
                validate_producer_call_observation(observation, no_call_reason)
            except (TypeError, ValueError) as exc:
                raise RuntimeError("pre-admission event call-state evidence is malformed") from exc
            if no_call_reason is not None and failure_code != no_call_reason:
                raise RuntimeError("pre-admission no-call reason diverges from its failure code")
            if (
                not isinstance(refs, list)
                or any(not isinstance(ref, str) or not ref or ref != ref.strip() for ref in refs)
                or refs != sorted(set(refs))
                or observation not in PRODUCER_CALL_STATE_VALUES
                or (
                    failure_code is not None
                    and (
                        not isinstance(failure_code, str)
                        or not failure_code
                        or len(failure_code) > 96
                        or any(
                            character
                            not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
                            for character in failure_code
                        )
                    )
                )
                or (
                    job_id is not None
                    and (not isinstance(job_id, str) or not job_id or job_id != job_id.strip())
                )
            ):
                raise RuntimeError("pre-admission event payload evidence is malformed")
            observed_at = parse_bound_timestamp(event_row["created_at"])
            history.append(
                ControlPreAdmissionAttemptEventRecord(
                    event_id=event_id,
                    sequence=int(sequence),
                    event_type=event_type,
                    observed_at=observed_at,
                    producer_event_ids=tuple(refs),
                    producer_event_observation=observation,
                    producer_no_call_reason=no_call_reason,
                    failure_code=failure_code,
                    job_id=job_id,
                )
            )
        raw_intent = row["intent_binding_json"]
        if not isinstance(raw_intent, str) or not raw_intent:
            raise RuntimeError("pre-admission request binding is missing")
        intent = json.loads(raw_intent)
        if not isinstance(intent, dict):
            raise RuntimeError("pre-admission request binding is malformed")
        producer_binding_json = row["producer_run_binding_json"]
        if producer_binding_json is None:
            producer_binding = None
        elif isinstance(producer_binding_json, str) and producer_binding_json:
            producer_binding = json.loads(producer_binding_json)
            if (
                not isinstance(producer_binding, dict)
                or set(producer_binding)
                != {
                    "schema_version",
                    "run_id",
                    "tenant_id",
                    "cell_id",
                    "profile_id",
                    "control_job_id",
                }
                or producer_binding.get("schema_version")
                != "polisyos.scientist.budget_ledger.producer_run_binding.v1"
                or producer_binding.get("run_id") != row["run_id"]
                or producer_binding.get("control_job_id") != row["candidate_job_id"]
                or producer_binding.get("tenant_id") != row["tenant_id"]
                or producer_binding.get("cell_id") != row["cell_id"]
                or producer_binding.get("profile_id") != row["effective_execution_profile"]
            ):
                raise RuntimeError("pre-admission producer binding is malformed")
        else:
            raise RuntimeError("pre-admission producer binding is malformed")
        raw_refs = row["producer_event_ids_json"]
        if not isinstance(raw_refs, str) or not raw_refs:
            raise RuntimeError("pre-admission aggregate producer refs are missing")
        aggregate_refs = json.loads(raw_refs)
        if (
            not isinstance(aggregate_refs, list)
            or any(
                not isinstance(ref, str) or not ref or ref != ref.strip() for ref in aggregate_refs
            )
            or aggregate_refs != sorted(set(aggregate_refs))
        ):
            raise RuntimeError("pre-admission aggregate producer refs are malformed")
        aggregate_observation = row["producer_event_observation"]
        if aggregate_observation not in PRODUCER_CALL_STATE_VALUES:
            raise RuntimeError("pre-admission aggregate observation is missing or malformed")
        status = row["status"]
        required_text = {
            "intent_sha256": row["intent_sha256"],
            "request_id": row["request_id"],
            "run_id": row["run_id"],
            "candidate_job_id": row["candidate_job_id"],
            "tenant_id": row["tenant_id"],
            "cell_id": row["cell_id"],
            "actor_subject": row["actor_subject"],
            "effective_execution_profile": row["effective_execution_profile"],
        }
        if any(
            not isinstance(value, str) or not value or value != value.strip()
            for value in required_text.values()
        ) or not isinstance(status, str):
            raise RuntimeError("pre-admission owner identity or status is missing")
        if (
            len(required_text["intent_sha256"]) != 64
            or any(
                character not in "0123456789abcdef" for character in required_text["intent_sha256"]
            )
            or required_text["effective_execution_profile"] not in _EXECUTION_PROFILES
        ):
            raise RuntimeError("pre-admission owner identity is malformed")
        row_job_id = row["job_id"]
        if row_job_id is not None and (
            not isinstance(row_job_id, str)
            or not row_job_id
            or row_job_id != row_job_id.strip()
            or row_job_id != required_text["candidate_job_id"]
        ):
            raise RuntimeError("pre-admission job binding is malformed")
        row_failure_code = row["failure_code"]
        aggregate_no_call_reason = row_failure_code if aggregate_observation == "no_call" else None
        try:
            validate_producer_call_observation(aggregate_observation, aggregate_no_call_reason)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("pre-admission aggregate call-state evidence is malformed") from exc
        if row_failure_code is not None and (
            not isinstance(row_failure_code, str)
            or not row_failure_code
            or len(row_failure_code) > 96
            or any(
                character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
                for character in row_failure_code
            )
        ):
            raise RuntimeError("pre-admission failure code is malformed")
        created_at = parse_bound_timestamp(row["created_at"])
        updated_at = parse_bound_timestamp(row["updated_at"])
        return ControlPreAdmissionAttemptRecord(
            attempt_id=attempt_id,
            intent_sha256=str(row["intent_sha256"]),
            intent_binding=intent,
            producer_run_binding=producer_binding,
            idempotency_key_sha256=row["idempotency_key_sha256"],
            request_id=str(row["request_id"]),
            run_id=str(row["run_id"]),
            candidate_job_id=str(row["candidate_job_id"]),
            job_id=row["job_id"],
            tenant_id=row["tenant_id"],
            cell_id=row["cell_id"],
            actor_subject=row["actor_subject"],
            effective_execution_profile=str(row["effective_execution_profile"]),
            status=status,
            producer_event_ids=tuple(aggregate_refs),
            producer_event_observation=aggregate_observation,
            producer_no_call_reason=aggregate_no_call_reason,
            failure_code=row["failure_code"],
            created_at=created_at,
            updated_at=updated_at,
            history=tuple(history),
            shared_owner=shared_owner,
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
            **_control_job_outbox_identity_envelope(record),
            **payload,
        }
        self.enqueue_outbox_event(
            topic=topic,
            event_key=event_key,
            job_id=record.job_id,
            run_id=record.run_id,
            payload=outbox_payload,
            **({"require_new": True} if event_type == "job_cancelled" else {}),
        )

    def _lease_next_sqlite(self, *, worker_id: str, lease_seconds: int) -> ControlJobRecord | None:
        now = _utc_now()
        lease_expires_at = now + timedelta(seconds=max(lease_seconds, 1))
        with self._lock:
            with self._sqlite_mutation_connection() as conn:
                try:
                    row = conn.execute(
                        """
                        SELECT job_id
                        FROM control_jobs
                        WHERE (state = 'pending'
                           OR (
                                state = 'running'
                                AND lease_expires_at IS NOT NULL
                                AND lease_expires_at <= ?
                           ))
                          AND NOT EXISTS (
                              SELECT 1 FROM control_job_events AS child_intent
                              WHERE child_intent.job_id = control_jobs.job_id
                                AND child_intent.event_type LIKE 'child.release.session.%'
                          )
                          AND NOT EXISTS (
                              SELECT 1 FROM control_job_events AS child_budget
                              WHERE child_budget.job_id = control_jobs.job_id
                                AND child_budget.event_type LIKE 'child.budget.attempt.%'
                          )
                        ORDER BY created_at ASC
                        LIMIT 1
                        """,
                        (_iso(now),),
                    ).fetchone()
                    if row is None:
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
                except Exception:
                    raise
        return self.get_job(job_id)

    def _lease_next_postgres(
        self, *, worker_id: str, lease_seconds: int
    ) -> ControlJobRecord | None:
        now = _utc_now()
        lease_expires_at = now + timedelta(seconds=max(lease_seconds, 1))
        with self._postgres_mutation_cursor() as cur:
            cur.execute(
                """
                WITH candidate AS (
                    SELECT job_id
                    FROM control_jobs
                    WHERE (state = 'pending'
                       OR (
                            state = 'running'
                            AND lease_expires_at IS NOT NULL
                            AND lease_expires_at <= %s
                       ))
                      AND NOT EXISTS (
                          SELECT 1 FROM control_job_events AS child_intent
                          WHERE child_intent.job_id = control_jobs.job_id
                            AND child_intent.event_type LIKE 'child.release.session.%'
                      )
                      AND NOT EXISTS (
                          SELECT 1 FROM control_job_events AS child_budget
                          WHERE child_budget.job_id = control_jobs.job_id
                            AND child_budget.event_type LIKE 'child.budget.attempt.%'
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
                        error_message TEXT,
                        method_execution_selection_json TEXT
                    );
                    CREATE TABLE IF NOT EXISTS control_job_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS control_job_events_by_job_type
                    ON control_job_events (job_id, event_type);
                    CREATE TABLE IF NOT EXISTS child_computation_reissue_sources (
                        source_run_id TEXT NOT NULL,
                        source_tenant_id TEXT,
                        source_cell_id TEXT,
                        reissue_job_id TEXT PRIMARY KEY
                    );
                    CREATE INDEX IF NOT EXISTS child_computation_reissue_by_source
                    ON child_computation_reissue_sources (source_run_id);
                    CREATE TABLE IF NOT EXISTS control_pre_admission_attempts (
                        attempt_id TEXT PRIMARY KEY, intent_sha256 TEXT NOT NULL,
                        intent_binding_json TEXT NOT NULL, producer_run_binding_json TEXT,
                        idempotency_key_sha256 TEXT, owner_token TEXT, request_id TEXT NOT NULL,
                        run_id TEXT NOT NULL, candidate_job_id TEXT NOT NULL, job_id TEXT,
                        tenant_id TEXT, cell_id TEXT, actor_subject TEXT,
                        effective_execution_profile TEXT NOT NULL, status TEXT NOT NULL,
                        producer_event_ids_json TEXT NOT NULL,
                        producer_event_observation TEXT NOT NULL, failure_code TEXT,
                        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS control_pre_admission_attempt_events (
                        event_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL,
                        sequence_no INTEGER NOT NULL, event_type TEXT NOT NULL,
                        payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
                        FOREIGN KEY(attempt_id) REFERENCES control_pre_admission_attempts(attempt_id),
                        UNIQUE(attempt_id, sequence_no)
                    );
                    CREATE TABLE IF NOT EXISTS control_job_progress (
                        job_id TEXT PRIMARY KEY,
                        progress_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS runtime_acquisition_action_heads (
                        tenant_id TEXT NOT NULL,
                        cell_id TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        source_job_id TEXT NOT NULL,
                        route_id TEXT NOT NULL,
                        action_generation INTEGER NOT NULL,
                        head_generation INTEGER NOT NULL,
                        receipt_ref TEXT NOT NULL,
                        receipt_sha256 TEXT NOT NULL,
                        durable_event_id TEXT NOT NULL,
                        coarse_phase TEXT NOT NULL,
                        receipt_phase TEXT NOT NULL,
                        recovery_state TEXT NOT NULL,
                        job_id TEXT NOT NULL,
                        predecessor_receipt_ref TEXT,
                        evaluation_frontier_before_ref TEXT,
                        evaluation_frontier_ref TEXT,
                        created_at TEXT NOT NULL,
                        PRIMARY KEY (
                            tenant_id, cell_id, run_id, source_job_id, route_id,
                            action_generation, head_generation
                        )
                    );
                    CREATE TABLE IF NOT EXISTS runtime_acquisition_evaluation_frontier_heads (
                        tenant_id TEXT NOT NULL,
                        cell_id TEXT NOT NULL,
                        source_job_id TEXT NOT NULL,
                        design_problem_ref TEXT NOT NULL,
                        candidate_id TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        frontier_ref TEXT,
                        PRIMARY KEY (
                            tenant_id, cell_id, source_job_id, design_problem_ref, candidate_id
                        )
                    );
                    CREATE TABLE IF NOT EXISTS runtime_acquisition_evaluation_frontier_versions (
                        tenant_id TEXT NOT NULL,
                        cell_id TEXT NOT NULL,
                        source_job_id TEXT NOT NULL,
                        design_problem_ref TEXT NOT NULL,
                        candidate_id TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        frontier_ref TEXT NOT NULL UNIQUE,
                        selected_evaluation_witness_ref TEXT NOT NULL,
                        selected_evaluation_content_hash TEXT NOT NULL,
                        basis_ref TEXT,
                        basis_content_hash TEXT,
                        decision_ref TEXT,
                        created_at TEXT NOT NULL,
                        PRIMARY KEY (
                            tenant_id, cell_id, source_job_id, design_problem_ref,
                            candidate_id, revision
                        )
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
                    CREATE TABLE IF NOT EXISTS control_search_hte_delivery_order (
                        sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT NOT NULL UNIQUE,
                        created_at TEXT NOT NULL
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
                    CREATE TABLE IF NOT EXISTS runtime_operation_intents (
                        purpose TEXT NOT NULL,
                        tenant_id TEXT NOT NULL,
                        cell_id TEXT NOT NULL,
                        actor_subject_sha256 TEXT NOT NULL,
                        scope_kind TEXT NOT NULL DEFAULT 'run',
                        scope_id TEXT NOT NULL DEFAULT '',
                        run_id TEXT NOT NULL,
                        intent_id TEXT NOT NULL,
                        body_sha256 TEXT NOT NULL,
                        state TEXT NOT NULL CHECK (
                            state IN ('pending', 'completed', 'refused', 'recovery_required')
                        ),
                        owner_token TEXT,
                        result_ref_json TEXT,
                        event_id TEXT UNIQUE,
                        reason_code TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (
                            purpose, tenant_id, cell_id, actor_subject_sha256,
                            scope_kind, scope_id, intent_id
                        ),
                        CHECK (
                            (state IN ('pending', 'completed') AND reason_code IS NULL)
                            OR (state IN ('refused', 'recovery_required') AND reason_code IS NOT NULL)
                        ),
                        CHECK (
                            (state = 'completed' AND result_ref_json IS NOT NULL AND event_id IS NOT NULL)
                            OR (state <> 'completed' AND result_ref_json IS NULL AND event_id IS NULL)
                        ),
                        CHECK ((state = 'pending') = (owner_token IS NOT NULL))
                    );
                    CREATE INDEX IF NOT EXISTS idx_runtime_operation_intents_run_state
                        ON runtime_operation_intents(run_id, purpose, state);
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
                    CREATE TABLE IF NOT EXISTS runtime_step_up_replays (
                        assertion_digest TEXT PRIMARY KEY,
                        expires_at INTEGER NOT NULL,
                        consumed_at INTEGER NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS runtime_human_decision_reservations (
                        tenant_id TEXT NOT NULL,
                        governed_action_key TEXT NOT NULL,
                        reservation_id TEXT NOT NULL UNIQUE,
                        reservation_version INTEGER NOT NULL CHECK (reservation_version > 0),
                        binding_sha256 TEXT NOT NULL,
                        state TEXT NOT NULL CHECK (
                            state IN (
                                'reserved', 'committed',
                                'recovery_required', 'reconciled_empty',
                                'reconciled_orphan', 'expired'
                            )
                        ),
                        reserved_at TEXT NOT NULL,
                        lease_expires_at TEXT NOT NULL,
                        record_valid_until TEXT NOT NULL,
                        record_ref TEXT,
                        record_sha256 TEXT,
                        durable_event_id TEXT,
                        committed_at TEXT,
                        reconciled_at TEXT,
                        PRIMARY KEY (
                            tenant_id, governed_action_key, reservation_version
                        )
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
                    CREATE INDEX IF NOT EXISTS idx_control_pre_admission_events_attempt_sequence
                        ON control_pre_admission_attempt_events(attempt_id, sequence_no);
                    CREATE INDEX IF NOT EXISTS idx_control_diagnostic_events_event_id
                        ON control_diagnostic_events(event_id);
                    CREATE INDEX IF NOT EXISTS idx_control_diagnostic_events_run_job
                        ON control_diagnostic_events(run_id, job_id, row_id);
                    CREATE INDEX IF NOT EXISTS idx_control_dead_letter_ack_failed_at
                        ON control_dead_letter_jobs(acknowledged_at, failed_at);
                    CREATE INDEX IF NOT EXISTS idx_runtime_scenario_heads_baseline_run
                        ON runtime_scenario_heads(baseline_run_id, scenario_id);
                    CREATE INDEX IF NOT EXISTS idx_runtime_step_up_replays_expires_at
                        ON runtime_step_up_replays(expires_at);
                    CREATE INDEX IF NOT EXISTS idx_runtime_human_decision_reservation_state
                        ON runtime_human_decision_reservations(state, lease_expires_at);
                    CREATE UNIQUE INDEX IF NOT EXISTS
                        uq_runtime_human_decision_live_action
                        ON runtime_human_decision_reservations(
                            tenant_id, governed_action_key
                        )
                        WHERE state IN ('reserved', 'recovery_required', 'committed');
                    """
                )
                conn.execute("BEGIN IMMEDIATE")
                try:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO control_search_hte_delivery_order (
                            event_id, created_at
                        )
                        SELECT event_id, created_at
                        FROM control_outbox_events
                        WHERE topic = 'control.search.hte_completed'
                        ORDER BY created_at ASC, event_id ASC
                        """
                    )
                    action_head_columns = {
                        str(row[1])
                        for row in conn.execute(
                            "PRAGMA table_info(runtime_acquisition_action_heads)"
                        )
                    }
                    for column in ("evaluation_frontier_before_ref", "evaluation_frontier_ref"):
                        if column not in action_head_columns:
                            conn.execute(
                                "ALTER TABLE runtime_acquisition_action_heads ADD COLUMN "
                                + column
                                + " TEXT"
                            )
                    operation_columns = {
                        str(row[1])
                        for row in conn.execute("PRAGMA table_info(runtime_operation_intents)")
                    }
                    if "scope_kind" not in operation_columns:
                        conn.execute(
                            "ALTER TABLE runtime_operation_intents ADD COLUMN scope_kind TEXT"
                        )
                    if "scope_id" not in operation_columns:
                        conn.execute(
                            "ALTER TABLE runtime_operation_intents ADD COLUMN scope_id TEXT"
                        )
                    conn.execute(
                        "UPDATE runtime_operation_intents SET scope_kind = 'run', scope_id = run_id "
                        "WHERE purpose = 'run.predictive_calibration.v1' "
                        "AND scope_id IS NULL AND scope_kind IS NULL"
                    )
                    conn.execute(
                        "UPDATE runtime_operation_intents SET scope_kind = 'route', scope_id = 'control.runs.nl' "
                        "WHERE purpose = 'control.nl_pre_admission.v1' "
                        "AND scope_id IS NULL AND scope_kind IS NULL"
                    )
                    invalid_scope = conn.execute(
                        "SELECT COUNT(*) FROM runtime_operation_intents WHERE "
                        "scope_id IS NULL OR scope_kind IS NULL OR scope_id = '' "
                        "OR scope_kind NOT IN ('run', 'route') "
                        "OR (scope_kind = 'run' AND scope_id <> run_id) "
                        "OR (purpose = 'run.predictive_calibration.v1' AND scope_kind <> 'run') "
                        "OR (purpose = 'control.nl_pre_admission.v1' AND "
                        "(scope_kind <> 'route' OR scope_id <> 'control.runs.nl'))"
                    ).fetchone()[0]
                    if int(invalid_scope):
                        raise RuntimeError(
                            "runtime_operation_scope_migration_has_unclassified_rows"
                        )
                    control_job_columns = {
                        str(row[1]) for row in conn.execute("PRAGMA table_info(control_jobs)")
                    }
                    if "method_execution_selection_json" not in control_job_columns:
                        conn.execute(
                            "ALTER TABLE control_jobs ADD COLUMN method_execution_selection_json TEXT"
                        )
                    attempt_columns = {
                        str(row[1])
                        for row in conn.execute("PRAGMA table_info(control_pre_admission_attempts)")
                    }
                    if "owner_token" not in attempt_columns:
                        conn.execute(
                            "ALTER TABLE control_pre_admission_attempts ADD COLUMN owner_token TEXT"
                        )
                    conn.execute("DROP INDEX IF EXISTS idx_control_pre_admission_idempotency_scope")
                    conn.execute(
                        "DROP INDEX IF EXISTS idx_runtime_operation_intents_scope_identity"
                    )
                    operation_pk = tuple(
                        str(row[1])
                        for row in sorted(
                            (
                                row
                                for row in conn.execute(
                                    "PRAGMA table_info(runtime_operation_intents)"
                                )
                                if int(row[5])
                            ),
                            key=lambda row: int(row[5]),
                        )
                    )
                    expected_operation_pk = (
                        "purpose",
                        "tenant_id",
                        "cell_id",
                        "actor_subject_sha256",
                        "scope_kind",
                        "scope_id",
                        "intent_id",
                    )
                    if operation_pk != expected_operation_pk:
                        conn.execute(
                            """CREATE TABLE runtime_operation_intents_scope_migrating (
                                purpose TEXT NOT NULL,
                                tenant_id TEXT NOT NULL,
                                cell_id TEXT NOT NULL,
                                actor_subject_sha256 TEXT NOT NULL,
                                scope_kind TEXT NOT NULL,
                                scope_id TEXT NOT NULL,
                                run_id TEXT NOT NULL,
                                intent_id TEXT NOT NULL,
                                body_sha256 TEXT NOT NULL,
                                state TEXT NOT NULL CHECK (
                                    state IN ('pending', 'completed', 'refused', 'recovery_required')
                                ),
                                owner_token TEXT,
                                result_ref_json TEXT,
                                event_id TEXT UNIQUE,
                                reason_code TEXT,
                                created_at TEXT NOT NULL,
                                updated_at TEXT NOT NULL,
                                PRIMARY KEY (
                                    purpose, tenant_id, cell_id, actor_subject_sha256,
                                    scope_kind, scope_id, intent_id
                                ),
                                CHECK (
                                    (state IN ('pending', 'completed') AND reason_code IS NULL)
                                    OR (state IN ('refused', 'recovery_required') AND reason_code IS NOT NULL)
                                ),
                                CHECK (
                                    (state = 'completed' AND result_ref_json IS NOT NULL AND event_id IS NOT NULL)
                                    OR (state <> 'completed' AND result_ref_json IS NULL AND event_id IS NULL)
                                ),
                                CHECK ((state = 'pending') = (owner_token IS NOT NULL))
                            )"""
                        )
                        conn.execute(
                            """INSERT INTO runtime_operation_intents_scope_migrating (
                                purpose, tenant_id, cell_id, actor_subject_sha256, scope_kind, scope_id,
                                run_id, intent_id, body_sha256, state, owner_token, result_ref_json,
                                event_id, reason_code, created_at, updated_at
                            ) SELECT purpose, tenant_id, cell_id, actor_subject_sha256, scope_kind, scope_id,
                                run_id, intent_id, body_sha256, state, owner_token, result_ref_json,
                                event_id, reason_code, created_at, updated_at
                              FROM runtime_operation_intents"""
                        )
                        conn.execute("DROP TABLE runtime_operation_intents")
                        conn.execute(
                            "ALTER TABLE runtime_operation_intents_scope_migrating "
                            "RENAME TO runtime_operation_intents"
                        )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_runtime_operation_intents_run_state "
                        "ON runtime_operation_intents(run_id, purpose, state)"
                    )
                    conn.commit()
                except BaseException:
                    conn.rollback()
                    raise

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
                    error_message TEXT,
                    method_execution_selection_json TEXT
                )
                """
            )
            cur.execute(
                "ALTER TABLE control_jobs ADD COLUMN IF NOT EXISTS method_execution_selection_json TEXT"
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
                "CREATE INDEX IF NOT EXISTS control_job_events_by_job_type "
                "ON control_job_events (job_id, event_type)"
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS control_pre_admission_attempts (
                    attempt_id TEXT PRIMARY KEY, intent_sha256 TEXT NOT NULL,
                    intent_binding_json TEXT NOT NULL, producer_run_binding_json TEXT,
                    idempotency_key_sha256 TEXT, owner_token TEXT, request_id TEXT NOT NULL,
                    run_id TEXT NOT NULL, candidate_job_id TEXT NOT NULL, job_id TEXT,
                    tenant_id TEXT, cell_id TEXT, actor_subject TEXT,
                    effective_execution_profile TEXT NOT NULL, status TEXT NOT NULL,
                    producer_event_ids_json TEXT NOT NULL,
                    producer_event_observation TEXT NOT NULL, failure_code TEXT,
                    created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS control_pre_admission_attempt_events (
                    event_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL,
                    sequence_no INTEGER NOT NULL, event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL,
                    FOREIGN KEY(attempt_id) REFERENCES control_pre_admission_attempts(attempt_id),
                    UNIQUE(attempt_id, sequence_no)
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
                CREATE TABLE IF NOT EXISTS runtime_acquisition_action_heads (
                    tenant_id TEXT NOT NULL,
                    cell_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    source_job_id TEXT NOT NULL,
                    route_id TEXT NOT NULL,
                    action_generation INTEGER NOT NULL,
                    head_generation INTEGER NOT NULL,
                    receipt_ref TEXT NOT NULL,
                    receipt_sha256 TEXT NOT NULL,
                    durable_event_id TEXT NOT NULL,
                    coarse_phase TEXT NOT NULL,
                    receipt_phase TEXT NOT NULL,
                    recovery_state TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    predecessor_receipt_ref TEXT,
                        evaluation_frontier_before_ref TEXT,
                        evaluation_frontier_ref TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (
                        tenant_id, cell_id, run_id, source_job_id, route_id,
                        action_generation, head_generation
                    )
                )
                """
            )
            cur.execute(
                "ALTER TABLE runtime_acquisition_action_heads "
                "ADD COLUMN IF NOT EXISTS evaluation_frontier_before_ref TEXT"
            )
            cur.execute(
                "ALTER TABLE runtime_acquisition_action_heads "
                "ADD COLUMN IF NOT EXISTS evaluation_frontier_ref TEXT"
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_acquisition_evaluation_frontier_heads (
                    tenant_id TEXT NOT NULL,
                    cell_id TEXT NOT NULL,
                    source_job_id TEXT NOT NULL,
                    design_problem_ref TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    frontier_ref TEXT,
                    PRIMARY KEY (
                        tenant_id, cell_id, source_job_id, design_problem_ref, candidate_id
                    )
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_acquisition_evaluation_frontier_versions (
                    tenant_id TEXT NOT NULL,
                    cell_id TEXT NOT NULL,
                    source_job_id TEXT NOT NULL,
                    design_problem_ref TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    frontier_ref TEXT NOT NULL UNIQUE,
                    selected_evaluation_witness_ref TEXT NOT NULL,
                    selected_evaluation_content_hash TEXT NOT NULL,
                    basis_ref TEXT,
                    basis_content_hash TEXT,
                    decision_ref TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (
                        tenant_id, cell_id, source_job_id, design_problem_ref,
                        candidate_id, revision
                    )
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
                CREATE TABLE IF NOT EXISTS control_search_hte_delivery_order (
                    sequence_id BIGSERIAL PRIMARY KEY,
                    event_id TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                INSERT INTO control_search_hte_delivery_order (event_id, created_at)
                SELECT event_id, created_at
                FROM control_outbox_events
                WHERE topic = 'control.search.hte_completed'
                ORDER BY created_at ASC, event_id ASC
                ON CONFLICT (event_id) DO NOTHING
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
                CREATE TABLE IF NOT EXISTS runtime_operation_intents (
                    purpose TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    cell_id TEXT NOT NULL,
                    actor_subject_sha256 TEXT NOT NULL,
                    scope_kind TEXT NOT NULL DEFAULT 'run',
                    scope_id TEXT NOT NULL DEFAULT '',
                    run_id TEXT NOT NULL,
                    intent_id TEXT NOT NULL,
                    body_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (
                        state IN ('pending', 'completed', 'refused', 'recovery_required')
                    ),
                    owner_token TEXT,
                    result_ref_json TEXT,
                    event_id TEXT UNIQUE,
                    reason_code TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (
                        purpose, tenant_id, cell_id, actor_subject_sha256,
                        scope_kind, scope_id, intent_id
                    ),
                    CHECK (
                        (state IN ('pending', 'completed') AND reason_code IS NULL)
                        OR (state IN ('refused', 'recovery_required') AND reason_code IS NOT NULL)
                    ),
                    CHECK (
                        (state = 'completed' AND result_ref_json IS NOT NULL AND event_id IS NOT NULL)
                        OR (state <> 'completed' AND result_ref_json IS NULL AND event_id IS NULL)
                    ),
                    CHECK ((state = 'pending') = (owner_token IS NOT NULL))
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
                CREATE TABLE IF NOT EXISTS runtime_step_up_replays (
                    assertion_digest TEXT PRIMARY KEY,
                    expires_at BIGINT NOT NULL,
                    consumed_at BIGINT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_human_decision_reservations (
                    tenant_id TEXT NOT NULL,
                    governed_action_key TEXT NOT NULL,
                    reservation_id TEXT NOT NULL UNIQUE,
                    reservation_version INTEGER NOT NULL CHECK (reservation_version > 0),
                    binding_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (
                        state IN (
                            'reserved', 'committed',
                            'recovery_required', 'reconciled_empty',
                            'reconciled_orphan', 'expired'
                        )
                    ),
                    reserved_at TIMESTAMPTZ NOT NULL,
                    lease_expires_at TIMESTAMPTZ NOT NULL,
                    record_valid_until TIMESTAMPTZ NOT NULL,
                    record_ref TEXT,
                    record_sha256 TEXT,
                    durable_event_id TEXT,
                    committed_at TIMESTAMPTZ,
                    reconciled_at TIMESTAMPTZ,
                    PRIMARY KEY (
                        tenant_id, governed_action_key, reservation_version
                    )
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
                "ALTER TABLE runtime_operation_intents ADD COLUMN IF NOT EXISTS scope_kind TEXT"
            )
            cur.execute(
                "ALTER TABLE runtime_operation_intents ADD COLUMN IF NOT EXISTS scope_id TEXT"
            )
            cur.execute(
                "UPDATE runtime_operation_intents SET scope_kind = 'run', scope_id = run_id "
                "WHERE purpose = 'run.predictive_calibration.v1' "
                "AND scope_id IS NULL AND scope_kind IS NULL"
            )
            cur.execute(
                "UPDATE runtime_operation_intents SET scope_kind = 'route', scope_id = 'control.runs.nl' "
                "WHERE purpose = 'control.nl_pre_admission.v1' "
                "AND scope_id IS NULL AND scope_kind IS NULL"
            )
            cur.execute(
                "SELECT COUNT(*) FROM runtime_operation_intents WHERE "
                "scope_id IS NULL OR scope_kind IS NULL OR scope_id = '' "
                "OR scope_kind NOT IN ('run', 'route') "
                "OR (scope_kind = 'run' AND scope_id <> run_id) "
                "OR (purpose = 'run.predictive_calibration.v1' AND scope_kind <> 'run') "
                "OR (purpose = 'control.nl_pre_admission.v1' AND "
                "(scope_kind <> 'route' OR scope_id <> 'control.runs.nl'))"
            )
            invalid_scope = cur.fetchone()[0]
            if int(invalid_scope):
                raise RuntimeError("runtime_operation_scope_migration_has_unclassified_rows")
            cur.execute(
                "ALTER TABLE runtime_operation_intents ALTER COLUMN scope_kind SET NOT NULL"
            )
            cur.execute("ALTER TABLE runtime_operation_intents ALTER COLUMN scope_id SET NOT NULL")
            cur.execute(
                """DO $runtime_operation_intent_scope_pkey$
                DECLARE existing_pkey_name TEXT;
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint AS constraint_row
                        WHERE constraint_row.conrelid = 'runtime_operation_intents'::regclass
                          AND constraint_row.contype = 'p'
                          AND (
                              SELECT array_agg(
                                  attribute_row.attname::TEXT ORDER BY key_column.ordinality
                              )
                              FROM unnest(constraint_row.conkey) WITH ORDINALITY
                                   AS key_column(attnum, ordinality)
                              JOIN pg_attribute AS attribute_row
                                ON attribute_row.attrelid = constraint_row.conrelid
                               AND attribute_row.attnum = key_column.attnum
                          ) = ARRAY[
                              'purpose', 'tenant_id', 'cell_id', 'actor_subject_sha256',
                              'scope_kind', 'scope_id', 'intent_id'
                          ]::TEXT[]
                    ) THEN
                        FOR existing_pkey_name IN
                            SELECT conname FROM pg_constraint
                            WHERE conrelid = 'runtime_operation_intents'::regclass AND contype = 'p'
                        LOOP
                            EXECUTE format(
                                'ALTER TABLE runtime_operation_intents DROP CONSTRAINT %I',
                                existing_pkey_name
                            );
                        END LOOP;
                        ALTER TABLE runtime_operation_intents
                            ADD CONSTRAINT runtime_operation_intents_pkey PRIMARY KEY (
                                purpose, tenant_id, cell_id, actor_subject_sha256,
                                scope_kind, scope_id, intent_id
                            );
                    END IF;
                END
                $runtime_operation_intent_scope_pkey$"""
            )
            cur.execute("DROP INDEX IF EXISTS idx_runtime_operation_intents_scope_identity")
            cur.execute(
                "ALTER TABLE control_pre_admission_attempts ADD COLUMN IF NOT EXISTS owner_token TEXT"
            )
            cur.execute("DROP INDEX IF EXISTS idx_control_pre_admission_idempotency_scope")
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_control_outbox_topic_event_key
                ON control_outbox_events(topic, event_key)
                WHERE event_key IS NOT NULL
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_control_pre_admission_events_attempt_sequence
                ON control_pre_admission_attempt_events(attempt_id, sequence_no)
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
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_runtime_step_up_replays_expires_at
                ON runtime_step_up_replays(expires_at)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_runtime_human_decision_reservation_state
                ON runtime_human_decision_reservations(state, lease_expires_at)
                """
            )
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                    uq_runtime_human_decision_live_action
                ON runtime_human_decision_reservations(
                    tenant_id, governed_action_key
                )
                WHERE state IN ('reserved', 'recovery_required', 'committed')
                """
            )

    def _admit_terminal_publication(
        self,
        *,
        job_id: str,
        fence: tuple[str, int] | None,
        state: Literal["completed", "failed"],
    ) -> None:
        """Carry an already affected-row-checked terminal write within its transaction."""
        admission = getattr(self._human_decision_transaction, "job_admission", None)
        if admission is None:
            return
        if admission.identity != (job_id, *(fence or (None, None))):
            raise ControlJobLeaseLostError("terminal publication does not bind admitted owner")
        record = self.get_job(job_id)
        if (
            record is None
            or record.state != state
            or record.attempt != admission.identity[2]
            or record.lease_owner is not None
            or record.lease_expires_at is not None
        ):
            raise ControlJobLeaseLostError("terminal publication row is not the admitted attempt")
        admission.terminal_state = state

    def _validate_transaction_admission(self, admission: _ControlJobTransactionAdmission) -> None:
        """Re-read the locked source lease, including a legitimate same-attempt renewal."""
        if admission.lease_expires_at is None:
            return
        job_id, worker_id, attempt = admission.identity
        record = self.get_job(job_id)
        if record is None or record.attempt != attempt:
            raise ControlJobLeaseLostError("control job transaction generation changed")
        if record.state == "running" and record.lease_owner == worker_id:
            expires_at = record.lease_expires_at
        elif (
            admission.terminal_state is not None
            and record.state == admission.terminal_state
            and record.lease_owner is None
            and record.lease_expires_at is None
        ):
            expires_at = admission.lease_expires_at
        else:
            raise ControlJobLeaseLostError("control job transaction owner changed")
        if expires_at is None or expires_at <= _utc_now():
            raise ControlJobLeaseLostError("control job lease expired during publication")

    @contextmanager
    def _bound_transaction_admission(
        self,
        resource: Any,
        *,
        purpose: Literal["execution", "completed_proof", "failed_proof"],
    ) -> Iterator[None]:
        """Resolve the bound source job while holding the publication transaction.

        The admission belongs to this exact connection/cursor and handler identity.
        Its internal terminal writes may clear the lease and still publish their
        progress, event and outbox rows atomically. A later public call admits
        again; completed proof has its existing, narrower completion-owner law.
        """
        bound = self._job_execution_fence.get()
        prior = getattr(self._human_decision_transaction, "job_admission", None)
        if prior is not None:
            if prior.resource is not resource or prior.identity != bound:
                raise ControlJobLeaseLostError("control job transaction identity changed")
            self._validate_transaction_admission(prior)
            yield
            return
        if bound is None:
            yield
            return
        job_id, worker_id, attempt = bound
        if purpose in {"completed_proof", "failed_proof"}:
            state: Literal["completed", "failed"] = (
                "completed" if purpose == "completed_proof" else "failed"
            )
            self._require_current_job_terminal_record(state=state)
            expires_at = None
        else:
            where, params = self._job_fence_where(
                job_id=job_id, fence=(worker_id, attempt), now=_utc_now()
            )
            lock_suffix = " FOR UPDATE" if self.backend == "postgres" else ""
            row = self._fetchone(
                f"SELECT job_id FROM control_jobs WHERE {where}{lock_suffix}", params
            )
            if row is None:
                raise ControlJobLeaseLostError(f"control job lease is not current for {job_id}")
            expires_at = self._require_current_job_execution_record(
                job_id=job_id, worker_id=worker_id, attempt=attempt
            ).lease_expires_at
        admission = _ControlJobTransactionAdmission(resource, bound, expires_at)
        self._human_decision_transaction.job_admission = admission
        try:
            yield
            self._validate_transaction_admission(admission)
        finally:
            self._human_decision_transaction.job_admission = prior

    @contextmanager
    def _job_transaction(
        self,
        *,
        purpose: Literal["execution", "completed_proof", "failed_proof"] = "execution",
        commit_admission: Callable[[], None] | None = None,
    ) -> Iterator[None]:
        """Admit bound-source effects and publish all SQL rows atomically."""
        existing_sqlite = getattr(self._human_decision_transaction, "sqlite_connection", None)
        existing_postgres = getattr(self._human_decision_transaction, "postgres_cursor", None)
        resource = existing_sqlite if existing_sqlite is not None else existing_postgres
        if resource is not None:
            if commit_admission is not None:
                raise ControlJobExecutionAdmissionError(
                    "control_job_cancellation_nested_transaction"
                )
            with self._bound_transaction_admission(resource, purpose=purpose):
                yield
            return
        if self.backend == "sqlite":
            with self._lock, self._sqlite_connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                self._human_decision_transaction.sqlite_connection = conn
                try:
                    with self._bound_transaction_admission(conn, purpose=purpose):
                        yield
                    if commit_admission is not None:
                        commit_admission()
                    conn.commit()
                except BaseException:
                    conn.rollback()
                    raise
                finally:
                    self._human_decision_transaction.sqlite_connection = None
            return
        with self._postgres_cursor() as cur:
            self._human_decision_transaction.postgres_cursor = cur
            try:
                with self._bound_transaction_admission(cur, purpose=purpose):
                    yield
                if commit_admission is not None:
                    commit_admission()
            finally:
                self._human_decision_transaction.postgres_cursor = None

    @contextmanager
    def _sqlite_mutation_connection(self) -> Iterator[sqlite3.Connection]:
        """Join the canonical admitted transaction for direct SQLite mutations."""
        with self._job_transaction():
            yield self._human_decision_transaction.sqlite_connection

    @contextmanager
    def _postgres_mutation_cursor(self) -> Iterator[Any]:
        """Join the canonical admitted transaction for direct PostgreSQL mutations."""
        with self._job_transaction():
            yield self._human_decision_transaction.postgres_cursor

    def _execute(self, sql: str, params: tuple[Any, ...]) -> int:
        """Write only through the actual transaction-bound publication admission."""
        with self._job_transaction():
            if self.backend == "sqlite":
                conn = self._human_decision_transaction.sqlite_connection
                return int(conn.execute(sql, params).rowcount)
            cur = self._human_decision_transaction.postgres_cursor
            cur.execute(self._translate_sql(sql), params)
            return int(cur.rowcount)

    def _fetchone(self, sql: str, params: tuple[Any, ...]) -> Any:
        if self.backend == "sqlite":
            lane = getattr(
                self._human_decision_transaction,
                "sqlite_connection",
                None,
            )
            if lane is not None:
                return lane.execute(sql, params).fetchone()
            with self._lock:
                with self._sqlite_connection() as conn:
                    return conn.execute(sql, params).fetchone()
        lane = getattr(self._human_decision_transaction, "postgres_cursor", None)
        if lane is not None:
            lane.execute(self._translate_sql(sql), params)
            row = lane.fetchone()
            if row is None:
                return None
            columns = [desc[0] for desc in (lane.description or ())]
            return {column: value for column, value in zip(columns, row, strict=False)}
        with self._postgres_cursor() as cur:
            cur.execute(self._translate_sql(sql), params)
            row = cur.fetchone()
            if row is None:
                return None
            columns = [desc[0] for desc in (cur.description or ())]
            return {column: value for column, value in zip(columns, row, strict=False)}

    def _fetchall(self, sql: str, params: tuple[Any, ...]) -> list[Any]:
        if self.backend == "sqlite":
            lane = getattr(
                self._human_decision_transaction,
                "sqlite_connection",
                None,
            )
            if lane is not None:
                return list(lane.execute(sql, params).fetchall())
            with self._lock:
                with self._sqlite_connection() as conn:
                    return list(conn.execute(sql, params).fetchall())
        lane = getattr(self._human_decision_transaction, "postgres_cursor", None)
        if lane is not None:
            lane.execute(self._translate_sql(sql), params)
            rows = lane.fetchall()
            columns = [desc[0] for desc in (lane.description or ())]
            return [
                {column: value for column, value in zip(columns, row, strict=False)} for row in rows
            ]
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
    "ControlJobCancellationConflictError",
    "ControlJobExecutionAdmission",
    "ControlJobExecutionAdmissionError",
    "ControlJobExecutionScope",
    "ControlJobLeaseLostError",
    "ControlJobRecord",
    "ControlOutboxRecord",
    "ControlPlaneStore",
    "ControlPreAdmissionAttemptEventRecord",
    "ControlPreAdmissionAttemptRecord",
    "ControlPreAdmissionIdempotencyConflictError",
    "ControlWorkerLeaseRecord",
    "ExecutionScopeStatus",
    "HumanDecisionRecoveryFence",
    "HumanDecisionReservationRecord",
    "HumanDecisionReservationResult",
    "HumanDecisionReservationState",
    "HumanDecisionWriteFence",
    "ManifestPointerState",
]
