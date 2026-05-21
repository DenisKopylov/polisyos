"""Continuous governance monitor contracts for living decision artifacts."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactRef,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.runtime.http.services.control.artifacts import (
    write_authority_artifact,
    write_runtime_authority_artifact,
)
from polisyos.runtime.quality.authority import (
    EvidenceAuthorityEnvelope,
    GovernanceMetadata,
    SameInputClosure,
)
from polisyos.runtime.quality.diagnostic_events import (
    DIAGNOSTIC_EVENT_SCHEMA_NAME,
    DIAGNOSTIC_EVENT_SCHEMA_VERSION,
    DiagnosticEvent,
    SERIOUS_EXECUTION_PROFILES,
)
from polisyos.runtime.quality.schema_compat import evaluate_schema_compatibility

CONTINUOUS_GOVERNANCE_FLAG = "scientist.best_in_class.wave2.phase2_6.continuous_governance"
ENABLE_REISSUE_WORKFLOW_FLAG = "scientist.best_in_class.wave2.phase2_6.enable_reissue_workflow"
ENABLE_WITHDRAWAL_STATUS_FLAG = "scientist.best_in_class.wave2.phase2_6.enable_withdrawal_status"

MonitorEventType = Literal[
    "source_invalidation",
    "calibration_drift",
    "fairness_drift",
    "policy_context_drift",
    "incident",
]
MonitorSeverity = Literal["info", "warning", "block"]
MonitorAction = Literal[
    "continue_monitoring",
    "mark_stale",
    "human_review",
    "reissue",
    "withdrawal_review",
]
LifecycleDecision = Literal["stale", "reissue", "supersede", "withdraw"]

GOVERNANCE_LIFECYCLE_REPORT_KIND = "governance_lifecycle_report"
GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_NAME = "runtime_quality.governance_lifecycle_report"
GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_VERSION = "1.0"
GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_ID = "policyos.runtime.governance_lifecycle_report.v1"
GOVERNANCE_LIFECYCLE_DIAGNOSTIC_EVENT_TYPE = (
    "polisyos.runtime.diagnostic.governance_lifecycle_decision.v1"
)
GOVERNANCE_LIFECYCLE_RUNTIME_REF_KEYS: dict[LifecycleDecision, str] = {
    "stale": "continuous_governance_stale_report_ref",
    "reissue": "continuous_governance_reissue_report_ref",
    "supersede": "continuous_governance_supersede_report_ref",
    "withdraw": "continuous_governance_withdraw_report_ref",
}


class DecisionValidityStatus(str, Enum):
    """Public validity status for a decision artifact after publication."""

    VALID = "valid"
    MONITORING = "monitoring"
    STALE = "stale"
    REVIEW_REQUIRED = "review_required"
    SUPERSEDED = "superseded"
    REISSUED = "reissued"
    WITHDRAWN = "withdrawn"


_EXPECTED_STATUS_BY_DECISION: dict[LifecycleDecision, DecisionValidityStatus] = {
    "stale": DecisionValidityStatus.STALE,
    "reissue": DecisionValidityStatus.REISSUED,
    "supersede": DecisionValidityStatus.SUPERSEDED,
    "withdraw": DecisionValidityStatus.WITHDRAWN,
}


class GovernanceMonitorEvent(BaseModel):
    """One continuous-governance signal tied to a decision packet."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    event_id: str = Field(min_length=1)
    decision_packet_ref: ArtifactRef
    event_type: MonitorEventType
    severity: MonitorSeverity
    affected_claim_ids: list[str] = Field(default_factory=list)
    affected_dag_node_ids: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_id", "reason")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("governance monitor text fields cannot be blank")
        return value


class GovernanceMonitorRecommendation(BaseModel):
    """Action recommendation produced from a monitor event."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    event_id: str = Field(min_length=1)
    status: DecisionValidityStatus
    recommended_action: MonitorAction
    human_review_required: bool = False
    reissue_recommended: bool = False
    withdrawal_review_required: bool = False
    reason: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_recommendation_semantics(self) -> GovernanceMonitorRecommendation:
        if self.recommended_action == "human_review" and not self.human_review_required:
            raise ValueError("human_review recommendation must require human review")
        if self.recommended_action == "reissue" and not self.reissue_recommended:
            raise ValueError("reissue recommendation must set reissue_recommended")
        if self.recommended_action == "withdrawal_review" and not self.withdrawal_review_required:
            raise ValueError("withdrawal_review recommendation must require withdrawal review")
        if self.status is DecisionValidityStatus.WITHDRAWN:
            raise ValueError("monitor recommendations cannot directly withdraw artifacts")
        return self


class GovernanceLifecycleEvidence(BaseModel):
    """Runtime-owned evidence emitted for one post-publication lifecycle decision."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    schema_version: Literal["1.0"] = "1.0"
    lifecycle_decision: LifecycleDecision
    runtime_quality_ref_key: str
    runtime_quality_refs: dict[str, str]
    report_ref: ArtifactRef
    payload_sha256: str
    manifest_ref: str
    diagnostic_event_ref: ArtifactRef
    authority_envelope_ref: ArtifactRef
    report: dict[str, Any]
    diagnostic_event: dict[str, Any]
    authority_envelope: dict[str, Any]


def monitor_event_id(
    *,
    decision_packet_ref: ArtifactRef,
    event_type: MonitorEventType,
    reason: str,
    sequence: int = 0,
) -> str:
    """Return a stable event id for repeatable monitor fixtures."""

    digest = hashlib.sha256(
        json.dumps(
            {
                "decision_packet_ref": str(decision_packet_ref.artifact_id),
                "event_type": event_type,
                "reason": reason,
                "sequence": sequence,
            },
            ensure_ascii=True,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"governance_monitor_{digest}"


def lifecycle_decision_id(
    *,
    decision_packet_ref: ArtifactRef,
    lifecycle_decision: LifecycleDecision,
    reason: str,
    sequence: int = 0,
) -> str:
    """Return a stable id for runtime lifecycle evidence records."""

    digest = hashlib.sha256(
        json.dumps(
            {
                "decision_packet_ref": str(decision_packet_ref.artifact_id),
                "lifecycle_decision": lifecycle_decision,
                "reason": reason,
                "sequence": sequence,
            },
            ensure_ascii=True,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"governance_lifecycle_{digest}"


def emit_governance_lifecycle_evidence(
    store: Any,
    *,
    lifecycle_decision: LifecycleDecision,
    decision_packet_ref: ArtifactRef,
    status: DecisionValidityStatus,
    reason: str,
    monitor_event_refs: list[ArtifactRef],
    run_id: str,
    job_id: str,
    tenant_id: str,
    cell_id: str | None,
    trace_id: str,
    span_id: str,
    effective_mode_ref: str,
    fallback_degradation_ref: str,
    cas_artifact_refs: dict[str, str] | None = None,
    requested_execution_profile: str = "production",
    effective_execution_profile: str = "production",
    producer_component: str = "polisyos.scientist.governance.continuous",
    producer_version: str = "2026.05.15+hds-phase2.7",
    owner: str = "team-runtime",
    state_before: str | None = None,
    occurred_at: datetime | None = None,
    sequence: int = 0,
    event_log: Any | None = None,
) -> GovernanceLifecycleEvidence:
    """Persist runtime-owned authority evidence for a lifecycle decision.

    The returned report is the scorecard/readiness payload. The CAS report ref
    points at the immutable report body, while the diagnostic event and authority
    envelope are persisted as sibling CAS sidecars linked by refs.
    """

    _validate_lifecycle_decision(
        lifecycle_decision=lifecycle_decision,
        status=status,
        monitor_event_refs=monitor_event_refs,
        reason=reason,
    )
    generated_at = occurred_at or datetime.now(UTC)
    report_id = lifecycle_decision_id(
        decision_packet_ref=decision_packet_ref,
        lifecycle_decision=lifecycle_decision,
        reason=reason,
        sequence=sequence,
    )
    runtime_ref_key = GOVERNANCE_LIFECYCLE_RUNTIME_REF_KEYS[lifecycle_decision]
    input_ref_values = [
        str(decision_packet_ref.artifact_id),
        *(str(ref.artifact_id) for ref in monitor_event_refs),
    ]
    closure_sha256 = _sha256_text(
        json.dumps(
            {
                "run_id": run_id,
                "job_id": job_id,
                "tenant_id": tenant_id,
                "cell_id": cell_id,
                "decision_packet_ref": str(decision_packet_ref.artifact_id),
                "monitor_event_refs": [str(ref.artifact_id) for ref in monitor_event_refs],
                "effective_mode_ref": effective_mode_ref,
                "fallback_degradation_ref": fallback_degradation_ref,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    schema_compatibility = evaluate_schema_compatibility(
        {"schema_version": GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_ID},
        reader="scorecard",
        expected_schema_family="policyos.runtime.governance_lifecycle_report",
    ).to_gate_details()
    report_cas_refs = dict(cas_artifact_refs or {})
    report: dict[str, Any] = {
        "schema_version": GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_ID,
        "status": "pass",
        "report_id": report_id,
        "lifecycle_decision": lifecycle_decision,
        "decision_status": status.value,
        "decision_packet_ref": str(decision_packet_ref.artifact_id),
        "reason": reason,
        "monitor_event_refs": [str(ref.artifact_id) for ref in monitor_event_refs],
        "cas_artifact_refs": report_cas_refs,
        "schema_compatibility": schema_compatibility,
        "effective_mode_ref": effective_mode_ref,
        "fallback_degradation_ref": fallback_degradation_ref,
        "degradation_ledger_ref": fallback_degradation_ref,
        "generated_at": generated_at.isoformat(),
        "runtime_quality_ref_key": runtime_ref_key,
        "authority_requirements": {
            "diagnostic_event_required": True,
            "cas_artifact_required": True,
            "authority_envelope_required": True,
            "schema_compatibility_required": True,
            "effective_mode_ref_required": True,
            "fallback_degradation_ref_required": True,
        },
    }
    serious = effective_execution_profile.casefold() in SERIOUS_EXECUTION_PROFILES
    if serious and event_log is None:
        raise ValueError("event_log is required for serious governance lifecycle authority")

    write_options = PutOptions(
        kind=GOVERNANCE_LIFECYCLE_REPORT_KIND,
        media_type="application/json",
        schema=SchemaInfo(
            name=GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_NAME,
            version=GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_VERSION,
        ),
        producer=ProducerInfo(
            component=producer_component,
            version=producer_version,
        ),
        governance=ArtifactGovernanceInfo(classification="internal"),
        inputs=_lifecycle_input_refs(
            decision_packet_ref=decision_packet_ref,
            monitor_event_refs=monitor_event_refs,
        ),
    )
    authority_fields = {
        "evidence_id": report_id,
        "evidence_class": "authority_bearing",
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "owner": owner,
        "reader_contract": GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_NAME,
        "reader_contract_version": GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "run_id": run_id,
        "job_id": job_id,
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": None,
        "requested_execution_profile": requested_execution_profile,
        "effective_execution_profile": effective_execution_profile,
        "phase": "continuous_governance_lifecycle",
        "generated_at": generated_at.isoformat(),
        "as_of_time": generated_at.isoformat(),
        "same_input_closure": SameInputClosure(
            closure_id=f"{report_id}:same_input_closure",
            status="closed",
            run_id=run_id,
            job_id=job_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            evidence_input_refs=input_ref_values,
            closure_sha256=closure_sha256.removeprefix("sha256:"),
        ),
        "input_refs": input_ref_values,
        "effective_mode_ref": effective_mode_ref,
        "degradation_ledger_ref": fallback_degradation_ref,
        "schema_compatibility_ref": _schema_compatibility_ref(schema_compatibility),
        "validation_status": "pass",
        "blocking_status": "non_overridable" if lifecycle_decision == "withdraw" else "blocking",
        "governance": GovernanceMetadata(
            classification="internal",
            authority_boundary="runtime_continuous_governance_lifecycle",
            pii="none",
            retention_policy="runtime_quality_retention",
            review_status=status.value,
            override_policy="not_overridable",
            approval_policy="requires_verified_scorecard",
        ),
        "event_source": "polisyos.runtime",
        "event_type": GOVERNANCE_LIFECYCLE_DIAGNOSTIC_EVENT_TYPE,
        "event_subject": (
            f"run/{run_id}/job/{job_id}/phase/continuous_governance_lifecycle/"
            f"decision/{lifecycle_decision}/report/{report_id}"
        ),
        "state_before": state_before,
        "state_after": status.value,
        "canon_spec": CanonSpec(forbid_floats=False),
    }
    if event_log is not None:
        result = write_runtime_authority_artifact(
            store,
            event_log,
            report,
            write_options,
            **authority_fields,
        )
    else:
        result = write_authority_artifact(
            store,
            report,
            write_options,
            **authority_fields,
        )
    report_ref_value = str(result.cas_ref.artifact_id)
    diagnostic_payload = from_canonical_bytes(
        store.get_bytes(result.diagnostic_event_ref.artifact_id)
    )
    authority_payload = from_canonical_bytes(
        store.get_bytes(result.authority_envelope_ref.artifact_id)
    )

    return GovernanceLifecycleEvidence(
        lifecycle_decision=lifecycle_decision,
        runtime_quality_ref_key=runtime_ref_key,
        runtime_quality_refs={runtime_ref_key: report_ref_value},
        report_ref=result.cas_ref,
        payload_sha256=result.payload_sha256,
        manifest_ref=result.manifest_ref,
        diagnostic_event_ref=result.diagnostic_event_ref,
        authority_envelope_ref=result.authority_envelope_ref,
        report=report,
        diagnostic_event=diagnostic_payload,
        authority_envelope=authority_payload,
    )


def build_drift_monitor_event(
    *,
    decision_packet_ref: ArtifactRef,
    event_type: Literal[
        "calibration_drift",
        "fairness_drift",
        "policy_context_drift",
    ],
    severity: MonitorSeverity,
    reason: str,
    affected_claim_ids: list[str] | None = None,
    metric_name: str | None = None,
    observed_value: float | None = None,
    threshold: float | None = None,
    sequence: int = 0,
) -> GovernanceMonitorEvent:
    """Build a typed drift event with optional metric diagnostics."""

    metadata: dict[str, Any] = {}
    if metric_name is not None:
        metadata["metric_name"] = metric_name
    if observed_value is not None:
        metadata["observed_value"] = observed_value
    if threshold is not None:
        metadata["threshold"] = threshold
    return GovernanceMonitorEvent(
        event_id=monitor_event_id(
            decision_packet_ref=decision_packet_ref,
            event_type=event_type,
            reason=reason,
            sequence=sequence,
        ),
        decision_packet_ref=decision_packet_ref,
        event_type=event_type,
        severity=severity,
        affected_claim_ids=affected_claim_ids or [],
        reason=reason,
        metadata=metadata,
    )


def _validate_lifecycle_decision(
    *,
    lifecycle_decision: LifecycleDecision,
    status: DecisionValidityStatus,
    monitor_event_refs: list[ArtifactRef],
    reason: str,
) -> None:
    if lifecycle_decision not in GOVERNANCE_LIFECYCLE_RUNTIME_REF_KEYS:
        raise ValueError(f"unsupported lifecycle decision: {lifecycle_decision}")
    expected_status = _EXPECTED_STATUS_BY_DECISION[lifecycle_decision]
    if status is not expected_status:
        raise ValueError(
            f"{lifecycle_decision} lifecycle evidence requires status {expected_status.value}"
        )
    if not monitor_event_refs:
        raise ValueError("lifecycle evidence requires monitor_event_refs")
    if not reason.strip():
        raise ValueError("lifecycle evidence reason cannot be blank")


def _lifecycle_input_refs(
    *,
    decision_packet_ref: ArtifactRef,
    monitor_event_refs: list[ArtifactRef],
) -> list[InputRef]:
    inputs = [InputRef(artifact_id=decision_packet_ref.artifact_id, role="decision_packet")]
    for index, ref in enumerate(monitor_event_refs):
        inputs.append(InputRef(artifact_id=ref.artifact_id, role=f"monitor_event[{index}]"))
    return inputs


def _build_lifecycle_diagnostic_event(
    *,
    lifecycle_decision: LifecycleDecision,
    status: DecisionValidityStatus,
    report_id: str,
    report_ref: str,
    decision_packet_ref: ArtifactRef,
    monitor_event_refs: list[ArtifactRef],
    run_id: str,
    job_id: str,
    tenant_id: str,
    cell_id: str | None,
    trace_id: str,
    span_id: str,
    producer_component: str,
    producer_version: str,
    execution_profile: str,
    state_before: str | None,
    event_time: datetime,
) -> DiagnosticEvent:
    return DiagnosticEvent(
        event_id=f"event_{report_id}",
        event_source="polisyos.runtime.scientist.governance.continuous",
        event_type=GOVERNANCE_LIFECYCLE_DIAGNOSTIC_EVENT_TYPE,
        event_time=event_time,
        event_subject=f"decision_packet:{decision_packet_ref.artifact_id}",
        schema_name=DIAGNOSTIC_EVENT_SCHEMA_NAME,
        schema_version=DIAGNOSTIC_EVENT_SCHEMA_VERSION,
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=None,
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        cell_id=cell_id or "unknown",
        producer_component=producer_component,
        producer_version=producer_version,
        execution_profile=execution_profile,
        phase="continuous_governance_lifecycle",
        state_before=state_before,
        state_after=status.value,
        payload_ref=report_ref,
        artifact_refs=(report_ref,),
        input_refs=tuple(str(ref.artifact_id) for ref in monitor_event_refs),
        blocking_status=(
            "blocking"
            if lifecycle_decision in {"reissue", "supersede", "withdraw"}
            else "non_blocking"
        ),
        redaction_policy_ref=None,
        duplicate_of=None,
        dedupe_key=f"{run_id}:{job_id}:{decision_packet_ref.artifact_id}:{lifecycle_decision}",
        sampling_decision="always_record",
        sampling_rate=1.0,
    )


def _build_lifecycle_authority_envelope(
    *,
    lifecycle_decision: LifecycleDecision,
    report_id: str,
    report_ref: str,
    diagnostic_event_ref: str,
    payload_sha256: str,
    schema_compatibility_ref: str,
    run_id: str,
    job_id: str,
    tenant_id: str,
    cell_id: str | None,
    trace_id: str,
    span_id: str,
    requested_execution_profile: str,
    effective_execution_profile: str,
    state_before: str | None,
    state_after: str,
    generated_at: datetime,
    input_refs: list[str],
    effective_mode_ref: str,
    fallback_degradation_ref: str,
    closure_sha256: str,
    owner: str,
    producer_component: str,
    producer_version: str,
) -> EvidenceAuthorityEnvelope:
    closure = SameInputClosure(
        closure_id=f"closure_{report_id}",
        status="closed",
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        effective_mode_ref=effective_mode_ref,
        degradation_ledger_ref=fallback_degradation_ref,
        evidence_input_refs=tuple(input_refs),
        closure_sha256=closure_sha256,
    )
    return EvidenceAuthorityEnvelope(
        evidence_id=report_id,
        artifact_ref=report_ref,
        artifact_kind=GOVERNANCE_LIFECYCLE_REPORT_KIND,
        evidence_class="authority_bearing",
        authority_role="producer_authority",
        provenance_kind="runtime_emitted",
        producer_component=producer_component,
        producer_version=producer_version,
        owner=owner,
        runtime_event_ref=diagnostic_event_ref,
        cas_ref=report_ref,
        payload_sha256=payload_sha256,
        schema_name=GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_NAME,
        schema_version=GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_VERSION,
        reader_contract="runtime.scorecard",
        reader_contract_version="1.0",
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        job_id=job_id,
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=None,
        requested_execution_profile=requested_execution_profile,
        effective_execution_profile=effective_execution_profile,
        phase="continuous_governance_lifecycle",
        state_before=state_before,
        state_after=state_after,
        generated_at=generated_at.isoformat(),
        as_of_time=generated_at.isoformat(),
        same_input_closure=closure,
        input_refs=tuple(input_refs),
        output_refs=(report_ref,),
        effective_mode_ref=effective_mode_ref,
        degradation_ledger_ref=fallback_degradation_ref,
        schema_compatibility_ref=schema_compatibility_ref,
        semantic_binding_ref=None,
        attestation_ref=None,
        redaction_policy_ref=None,
        duplicate_of=None,
        validation_status="pass",
        blocking_status=("non_overridable" if lifecycle_decision == "withdraw" else "blocking"),
        governance=GovernanceMetadata(
            classification="internal",
            authority_boundary="runtime_continuous_governance_lifecycle",
            pii="none",
            retention_policy="runtime_quality_retention",
            review_status=state_after,
            override_policy="not_overridable",
            approval_policy="requires_verified_scorecard",
        ),
    )


def _schema_compatibility_ref(schema_compatibility: dict[str, Any]) -> str:
    decision = str(schema_compatibility.get("decision") or "unknown")
    schema_family = str(
        schema_compatibility.get("schema_family") or "policyos.runtime.governance_lifecycle_report"
    )
    return f"schema-compat://scorecard/{schema_family}/{decision}"


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def recommend_validity_action(
    event: GovernanceMonitorEvent,
) -> GovernanceMonitorRecommendation:
    """Convert a monitor event into an auditable review/reissue recommendation."""

    if event.severity == "info":
        return GovernanceMonitorRecommendation(
            event_id=event.event_id,
            status=DecisionValidityStatus.MONITORING,
            recommended_action="continue_monitoring",
            reason=f"{event.event_type} is informational; continue monitoring.",
            metadata={"event_type": event.event_type, "severity": event.severity},
        )

    if event.event_type == "source_invalidation":
        if event.severity == "warning":
            return GovernanceMonitorRecommendation(
                event_id=event.event_id,
                status=DecisionValidityStatus.STALE,
                recommended_action="mark_stale",
                reason="Source invalidation marked dependent claims stale.",
                metadata={"event_type": event.event_type, "severity": event.severity},
            )
        return GovernanceMonitorRecommendation(
            event_id=event.event_id,
            status=DecisionValidityStatus.REVIEW_REQUIRED,
            recommended_action="reissue",
            human_review_required=True,
            reissue_recommended=True,
            reason="Blocking source invalidation requires review and possible reissue.",
            metadata={"event_type": event.event_type, "severity": event.severity},
        )

    if event.event_type in {
        "calibration_drift",
        "fairness_drift",
        "policy_context_drift",
    }:
        if event.severity == "warning":
            return GovernanceMonitorRecommendation(
                event_id=event.event_id,
                status=DecisionValidityStatus.REVIEW_REQUIRED,
                recommended_action="human_review",
                human_review_required=True,
                reason=f"{event.event_type} trigger requires reviewer triage.",
                metadata={"event_type": event.event_type, "severity": event.severity},
            )
        return GovernanceMonitorRecommendation(
            event_id=event.event_id,
            status=DecisionValidityStatus.REVIEW_REQUIRED,
            recommended_action="reissue",
            human_review_required=True,
            reissue_recommended=True,
            reason=f"Blocking {event.event_type} requires review and reissue assessment.",
            metadata={"event_type": event.event_type, "severity": event.severity},
        )

    if event.severity == "block":
        return GovernanceMonitorRecommendation(
            event_id=event.event_id,
            status=DecisionValidityStatus.REVIEW_REQUIRED,
            recommended_action="withdrawal_review",
            human_review_required=True,
            withdrawal_review_required=True,
            reason="Blocking incident requires explicit withdrawal review.",
            metadata={"event_type": event.event_type, "severity": event.severity},
        )
    return GovernanceMonitorRecommendation(
        event_id=event.event_id,
        status=DecisionValidityStatus.REVIEW_REQUIRED,
        recommended_action="human_review",
        human_review_required=True,
        reason="Incident requires reviewer triage.",
        metadata={"event_type": event.event_type, "severity": event.severity},
    )


def aggregate_validity_status(
    recommendations: list[GovernanceMonitorRecommendation],
) -> DecisionValidityStatus:
    """Collapse event-level recommendations into one decision validity status."""

    if not recommendations:
        return DecisionValidityStatus.VALID
    if any(item.withdrawal_review_required for item in recommendations):
        return DecisionValidityStatus.REVIEW_REQUIRED
    if any(item.reissue_recommended for item in recommendations):
        return DecisionValidityStatus.REVIEW_REQUIRED
    if any(item.human_review_required for item in recommendations):
        return DecisionValidityStatus.REVIEW_REQUIRED
    if any(item.status is DecisionValidityStatus.STALE for item in recommendations):
        return DecisionValidityStatus.STALE
    return DecisionValidityStatus.MONITORING


__all__ = [
    "CONTINUOUS_GOVERNANCE_FLAG",
    "ENABLE_REISSUE_WORKFLOW_FLAG",
    "ENABLE_WITHDRAWAL_STATUS_FLAG",
    "DecisionValidityStatus",
    "GOVERNANCE_LIFECYCLE_DIAGNOSTIC_EVENT_TYPE",
    "GOVERNANCE_LIFECYCLE_REPORT_KIND",
    "GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_ID",
    "GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_NAME",
    "GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_VERSION",
    "GOVERNANCE_LIFECYCLE_RUNTIME_REF_KEYS",
    "GovernanceLifecycleEvidence",
    "GovernanceMonitorEvent",
    "GovernanceMonitorRecommendation",
    "LifecycleDecision",
    "MonitorAction",
    "MonitorEventType",
    "MonitorSeverity",
    "aggregate_validity_status",
    "build_drift_monitor_event",
    "emit_governance_lifecycle_evidence",
    "lifecycle_decision_id",
    "monitor_event_id",
    "recommend_validity_action",
]
