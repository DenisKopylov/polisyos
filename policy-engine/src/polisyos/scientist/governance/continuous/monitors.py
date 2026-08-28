"""Continuous governance monitor contracts for living decision artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactRef,
    CanonInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, content_hash, from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts.runtime import EpochPerturbationClass

CONTINUOUS_GOVERNANCE_FLAG = "scientist.best_in_class.wave2.phase2_6.continuous_governance"
ENABLE_REISSUE_WORKFLOW_FLAG = "scientist.best_in_class.wave2.phase2_6.enable_reissue_workflow"
ENABLE_WITHDRAWAL_STATUS_FLAG = "scientist.best_in_class.wave2.phase2_6.enable_withdrawal_status"
DIAGNOSTIC_EVENT_SCHEMA_NAME = "polisyos.runtime.quality.diagnostic_event"
DIAGNOSTIC_EVENT_SCHEMA_VERSION = "1.0"
SERIOUS_EXECUTION_PROFILES = frozenset({"governed", "production", "research"})
AUTHORITY_ENVELOPE_ARTIFACT_KIND = "runtime_quality.evidence_authority_envelope"
DIAGNOSTIC_EVENT_ARTIFACT_KIND = "runtime_quality.diagnostic_event"
GOVERNANCE_MONITOR_EVENT_KIND = "scientist.governance_monitor_event"
GOVERNANCE_MONITOR_EVENT_SCHEMA_NAME = "polisyos.scientist.GovernanceMonitorEvent"
GOVERNANCE_MONITOR_EVENT_SCHEMA_VERSION = "2.0"

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
AdvisoryPosture = Literal["annotation_only", "review_required"]

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


class IncidentPerturbation(BaseModel):
    """Content-bound operational incident affecting one published packet."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_class: Literal["incident"] = "incident"
    incident_report_ref: ArtifactRef


class AppealPerturbation(BaseModel):
    """One appeal over one published instance, never an implicit class ruling."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_class: Literal["appeal"] = "appeal"
    appeal_evidence_ref: ArtifactRef
    affected_instance_ref: ArtifactRef
    scope: Literal["instance"] = "instance"


class CorrectionPerturbation(BaseModel):
    """Content-bound correction with explicit replacement evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_class: Literal["correction"] = "correction"
    evidence_validity_event_ref: ArtifactRef
    replacement_refs: tuple[ArtifactRef, ...] = Field(min_length=1)


class RetractionPerturbation(BaseModel):
    """Content-bound retraction; it carries no replacement evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_class: Literal["retraction"] = "retraction"
    evidence_validity_event_ref: ArtifactRef


class LegalChangePerturbation(BaseModel):
    """Content-bound legal-change evidence awaiting owner adjudication."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_class: Literal["legal_change"] = "legal_change"
    legal_change_evidence_ref: ArtifactRef


class DiscoveredBiasPerturbation(BaseModel):
    """Content-bound discovered-bias evidence awaiting owner adjudication."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_class: Literal["discovered_bias"] = "discovered_bias"
    bias_evidence_ref: ArtifactRef


EpochPerturbation: TypeAlias = Annotated[
    IncidentPerturbation
    | AppealPerturbation
    | CorrectionPerturbation
    | RetractionPerturbation
    | LegalChangePerturbation
    | DiscoveredBiasPerturbation,
    Field(discriminator="source_class"),
]


class GovernanceMonitorEvent(BaseModel):
    """One continuous-governance signal tied to a decision packet."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    event_id: str = Field(min_length=1)
    decision_packet_ref: ArtifactRef
    event_type: MonitorEventType
    severity: MonitorSeverity
    scope: dict[str, Any] = Field(default_factory=dict)
    affected_claim_ids: list[str] = Field(default_factory=list)
    affected_dag_node_ids: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    perturbation: EpochPerturbation | None = None
    advisory_posture: AdvisoryPosture = "review_required"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_id", "reason")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("governance monitor text fields cannot be blank")
        return value

    @model_validator(mode="after")
    def _validate_perturbation_boundary(self) -> GovernanceMonitorEvent:
        reserved = {
            "adjudicated_disposition",
            "claim_lifecycle_transition",
            "lifecycle_transition",
            "owner_disposition",
            "source_class",
        }
        supplied = reserved.intersection(self.metadata)
        if supplied:
            raise ValueError(
                "governance monitor metadata cannot author authority fields: "
                + ", ".join(sorted(supplied))
            )
        if self.perturbation is None:
            return self
        expected_event_type: dict[EpochPerturbationClass, MonitorEventType] = {
            "incident": "incident",
            "appeal": "policy_context_drift",
            "correction": "source_invalidation",
            "retraction": "source_invalidation",
            "legal_change": "policy_context_drift",
            "discovered_bias": "fairness_drift",
        }
        if self.event_type != expected_event_type[self.perturbation.source_class]:
            raise ValueError("perturbation source class does not match monitor event family")
        if (
            isinstance(self.perturbation, AppealPerturbation)
            and self.decision_packet_ref != self.perturbation.affected_instance_ref
        ):
            raise ValueError("appeal perturbations must remain scoped to the affected instance")
        return self


class PersistedGovernanceMonitorEvent(BaseModel):
    """One verified monitor-event handle; no parsed object travels beside its ref."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_ref: ArtifactRef
    event_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    event: GovernanceMonitorEvent


def persist_governance_monitor_event(
    store: ArtifactStore,
    event: GovernanceMonitorEvent,
) -> PersistedGovernanceMonitorEvent:
    """Persist and reload one strict monitor event before returning its handle."""

    ref = store.put_json(
        event,
        PutOptions(
            kind=GOVERNANCE_MONITOR_EVENT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=GOVERNANCE_MONITOR_EVENT_SCHEMA_NAME,
                version=GOVERNANCE_MONITOR_EVENT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    persisted = resolve_governance_monitor_event(store, ref)
    if persisted.event != event:
        raise ValueError("governance monitor event readback mismatch")
    return persisted


def resolve_governance_monitor_event(
    store: ArtifactStore,
    ref: ArtifactRef,
) -> PersistedGovernanceMonitorEvent:
    """Resolve exact bytes, manifest profile, and semantic model for one event ref."""

    raw = store.get_bytes(ref.artifact_id)
    report = store.verify(ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    observed_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
    if (
        not report.ok
        or observed_hash != str(ref.artifact_id)
        or ref.kind != GOVERNANCE_MONITOR_EVENT_KIND
        or ref.media_type != "application/json"
        or manifest.artifact_id != ref.artifact_id
        or manifest.kind != GOVERNANCE_MONITOR_EVENT_KIND
        or manifest.media_type != "application/json"
        or manifest.artifact_schema
        != SchemaInfo(
            name=GOVERNANCE_MONITOR_EVENT_SCHEMA_NAME,
            version=GOVERNANCE_MONITOR_EVENT_SCHEMA_VERSION,
        )
        or manifest.canon != CanonInfo.from_spec(CanonSpec(forbid_floats=False))
    ):
        raise ValueError("governance monitor event artifact profile mismatch")
    event = GovernanceMonitorEvent.model_validate(from_canonical_bytes(raw))
    if to_canonical_bytes(event, CanonSpec(forbid_floats=False)) != raw:
        raise ValueError("governance monitor event canonical bytes mismatch")
    return PersistedGovernanceMonitorEvent(
        event_ref=ref,
        event_content_hash=observed_hash,
        event=event,
    )


def persist_incident_monitor_event(
    store: ArtifactStore,
    *,
    incident_report_ref: ArtifactRef,
    sequence: int = 0,
) -> PersistedGovernanceMonitorEvent:
    """Reuse the incident owner and bind its exact report into the strict event arm."""

    from .incident import incident_monitor_event, load_incident_report

    incident = load_incident_report(store, incident_report_ref)
    event = incident_monitor_event(incident=incident, sequence=sequence)
    bound = event.model_copy(
        update={
            "perturbation": IncidentPerturbation(
                incident_report_ref=incident_report_ref,
            ),
            "advisory_posture": "review_required",
        }
    )
    if (
        bound.decision_packet_ref != incident.decision_packet_ref
        or bound.reason != incident.reason
        or bound.affected_claim_ids != incident.affected_claim_ids
    ):
        raise ValueError("incident monitor event owner binding mismatch")
    return persist_governance_monitor_event(store, bound)


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


@dataclass(frozen=True, slots=True)
class _AuthorityArtifactWriteResult:
    cas_ref: ArtifactRef
    payload_sha256: str
    manifest_ref: str
    authority_envelope_ref: ArtifactRef
    diagnostic_event_ref: ArtifactRef


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
    schema_compatibility = _evaluate_schema_compatibility(
        schema_version=GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_ID,
        reader="scorecard",
        expected_schema_family="policyos.runtime.governance_lifecycle_report",
    )
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
        "same_input_closure": {
            "closure_id": f"{report_id}:same_input_closure",
            "status": "closed",
            "run_id": run_id,
            "job_id": job_id,
            "tenant_id": tenant_id,
            "cell_id": cell_id,
            "evidence_input_refs": input_ref_values,
            "closure_sha256": closure_sha256.removeprefix("sha256:"),
        },
        "input_refs": input_ref_values,
        "effective_mode_ref": effective_mode_ref,
        "degradation_ledger_ref": fallback_degradation_ref,
        "schema_compatibility_ref": _schema_compatibility_ref(schema_compatibility),
        "validation_status": "pass",
        "blocking_status": "non_overridable" if lifecycle_decision == "withdraw" else "blocking",
        "governance": {
            "classification": "internal",
            "authority_boundary": "runtime_continuous_governance_lifecycle",
            "pii": "none",
            "retention_policy": "runtime_quality_retention",
            "review_status": status.value,
            "override_policy": "not_overridable",
            "approval_policy": "requires_verified_scorecard",
        },
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
    result = _write_governance_authority_artifact(
        store,
        event_log,
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


def _write_governance_authority_artifact(
    store: Any,
    event_log: Any | None,
    payload: object,
    opts: PutOptions,
    **authority_fields: Any,
) -> _AuthorityArtifactWriteResult:
    canon_spec = authority_fields.get("canon_spec")
    if not isinstance(canon_spec, CanonSpec):
        canon_spec = CanonSpec(forbid_floats=False)
    payload_bytes = to_canonical_bytes(payload, canon_spec)
    payload_sha256 = content_hash(payload_bytes)
    cas_ref_value = f"sha256:{payload_sha256}"
    manifest_ref = f"cas-manifest://{cas_ref_value}"
    producer = opts.producer or ProducerInfo(component="polisyos.scientist", version="unknown")
    schema = opts.schema or SchemaInfo(name=opts.kind, version="1.0")

    diagnostic_event = {
        "event_id": authority_fields.get("event_id")
        or f"event_{authority_fields.get('evidence_id')}",
        "event_source": authority_fields.get("event_source") or "polisyos.runtime",
        "event_type": authority_fields.get("event_type")
        or GOVERNANCE_LIFECYCLE_DIAGNOSTIC_EVENT_TYPE,
        "event_time": authority_fields.get("generated_at"),
        "event_subject": authority_fields.get("event_subject"),
        "schema_name": DIAGNOSTIC_EVENT_SCHEMA_NAME,
        "schema_version": DIAGNOSTIC_EVENT_SCHEMA_VERSION,
        "trace_id": authority_fields.get("trace_id"),
        "span_id": authority_fields.get("span_id"),
        "parent_span_id": authority_fields.get("parent_span_id"),
        "run_id": authority_fields.get("run_id"),
        "job_id": authority_fields.get("job_id"),
        "tenant_id": authority_fields.get("tenant_id"),
        "cell_id": authority_fields.get("cell_id") or "unknown",
        "producer_component": producer.component,
        "producer_version": producer.version,
        "execution_profile": authority_fields.get("effective_execution_profile"),
        "phase": authority_fields.get("phase"),
        "state_before": authority_fields.get("state_before"),
        "state_after": authority_fields.get("state_after"),
        "payload_ref": cas_ref_value,
        "artifact_refs": [cas_ref_value],
        "input_refs": list(authority_fields.get("input_refs") or ()),
        "blocking_status": authority_fields.get("blocking_status"),
        "redaction_policy_ref": authority_fields.get("redaction_policy_ref"),
        "duplicate_of": None,
        "dedupe_key": (
            f"{authority_fields.get('run_id')}:{authority_fields.get('job_id')}:"
            f"{authority_fields.get('evidence_id')}"
        ),
        "sampling_decision": "always_record",
        "sampling_rate": 1.0,
    }
    diagnostic_event_ref = store.put_json(
        diagnostic_event,
        PutOptions(
            kind=DIAGNOSTIC_EVENT_ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=DIAGNOSTIC_EVENT_SCHEMA_NAME,
                version=DIAGNOSTIC_EVENT_SCHEMA_VERSION,
            ),
            producer=producer,
            inputs=opts.inputs,
        ),
        canon_spec,
    )
    append = getattr(event_log, "append", None)
    if callable(append):
        append(dict(diagnostic_event))

    authority_envelope = {
        "evidence_id": authority_fields.get("evidence_id"),
        "artifact_ref": cas_ref_value,
        "artifact_kind": opts.kind,
        "evidence_class": authority_fields.get("evidence_class"),
        "authority_role": authority_fields.get("authority_role"),
        "provenance_kind": authority_fields.get("provenance_kind"),
        "producer_component": producer.component,
        "producer_version": producer.version,
        "owner": authority_fields.get("owner"),
        "runtime_event_ref": str(diagnostic_event_ref.artifact_id),
        "cas_ref": cas_ref_value,
        "payload_sha256": payload_sha256,
        "schema_name": schema.name,
        "schema_version": schema.version,
        "reader_contract": authority_fields.get("reader_contract"),
        "reader_contract_version": authority_fields.get("reader_contract_version"),
        "tenant_id": authority_fields.get("tenant_id"),
        "cell_id": authority_fields.get("cell_id"),
        "run_id": authority_fields.get("run_id"),
        "job_id": authority_fields.get("job_id"),
        "trace_id": authority_fields.get("trace_id"),
        "span_id": authority_fields.get("span_id"),
        "parent_span_id": authority_fields.get("parent_span_id"),
        "requested_execution_profile": authority_fields.get("requested_execution_profile"),
        "effective_execution_profile": authority_fields.get("effective_execution_profile"),
        "phase": authority_fields.get("phase"),
        "state_before": authority_fields.get("state_before"),
        "state_after": authority_fields.get("state_after"),
        "generated_at": authority_fields.get("generated_at"),
        "as_of_time": authority_fields.get("as_of_time"),
        "same_input_closure": authority_fields.get("same_input_closure"),
        "input_refs": list(authority_fields.get("input_refs") or ()),
        "output_refs": [cas_ref_value],
        "effective_mode_ref": authority_fields.get("effective_mode_ref"),
        "degradation_ledger_ref": authority_fields.get("degradation_ledger_ref"),
        "schema_compatibility_ref": authority_fields.get("schema_compatibility_ref"),
        "semantic_binding_ref": authority_fields.get("semantic_binding_ref"),
        "attestation_ref": authority_fields.get("attestation_ref"),
        "redaction_policy_ref": authority_fields.get("redaction_policy_ref"),
        "validation_status": authority_fields.get("validation_status"),
        "blocking_status": authority_fields.get("blocking_status"),
        "governance": authority_fields.get("governance"),
    }
    authority_envelope_ref = store.put_json(
        authority_envelope,
        PutOptions(
            kind=AUTHORITY_ENVELOPE_ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name="runtime_quality.evidence_authority_envelope",
                version="1.0",
            ),
            producer=producer,
            inputs=opts.inputs,
        ),
        canon_spec,
    )
    cas_ref = store.put_json(payload, opts, canon_spec)
    return _AuthorityArtifactWriteResult(
        cas_ref=cas_ref,
        payload_sha256=payload_sha256,
        manifest_ref=manifest_ref,
        authority_envelope_ref=authority_envelope_ref,
        diagnostic_event_ref=diagnostic_event_ref,
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
    scope: dict[str, Any] | None = None,
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
        scope=scope or {},
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
) -> dict[str, Any]:
    return {
        "event_id": f"event_{report_id}",
        "event_source": "polisyos.runtime.scientist.governance.continuous",
        "event_type": GOVERNANCE_LIFECYCLE_DIAGNOSTIC_EVENT_TYPE,
        "event_time": event_time.isoformat(),
        "event_subject": f"decision_packet:{decision_packet_ref.artifact_id}",
        "schema_name": DIAGNOSTIC_EVENT_SCHEMA_NAME,
        "schema_version": DIAGNOSTIC_EVENT_SCHEMA_VERSION,
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": None,
        "run_id": run_id,
        "job_id": job_id,
        "tenant_id": tenant_id,
        "cell_id": cell_id or "unknown",
        "producer_component": producer_component,
        "producer_version": producer_version,
        "execution_profile": execution_profile,
        "phase": "continuous_governance_lifecycle",
        "state_before": state_before,
        "state_after": status.value,
        "payload_ref": report_ref,
        "artifact_refs": [report_ref],
        "input_refs": [str(ref.artifact_id) for ref in monitor_event_refs],
        "blocking_status": (
            "blocking"
            if lifecycle_decision in {"reissue", "supersede", "withdraw"}
            else "non_blocking"
        ),
        "redaction_policy_ref": None,
        "duplicate_of": None,
        "dedupe_key": f"{run_id}:{job_id}:{decision_packet_ref.artifact_id}:{lifecycle_decision}",
        "sampling_decision": "always_record",
        "sampling_rate": 1.0,
    }


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
) -> dict[str, Any]:
    closure = {
        "closure_id": f"closure_{report_id}",
        "status": "closed",
        "run_id": run_id,
        "job_id": job_id,
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "effective_mode_ref": effective_mode_ref,
        "degradation_ledger_ref": fallback_degradation_ref,
        "evidence_input_refs": list(input_refs),
        "closure_sha256": closure_sha256,
    }
    return {
        "evidence_id": report_id,
        "artifact_ref": report_ref,
        "artifact_kind": GOVERNANCE_LIFECYCLE_REPORT_KIND,
        "evidence_class": "authority_bearing",
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "producer_component": producer_component,
        "producer_version": producer_version,
        "owner": owner,
        "runtime_event_ref": diagnostic_event_ref,
        "cas_ref": report_ref,
        "payload_sha256": payload_sha256,
        "schema_name": GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_NAME,
        "schema_version": GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_VERSION,
        "reader_contract": "runtime.scorecard",
        "reader_contract_version": "1.0",
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
        "state_before": state_before,
        "state_after": state_after,
        "generated_at": generated_at.isoformat(),
        "as_of_time": generated_at.isoformat(),
        "same_input_closure": closure,
        "input_refs": list(input_refs),
        "output_refs": [report_ref],
        "effective_mode_ref": effective_mode_ref,
        "degradation_ledger_ref": fallback_degradation_ref,
        "schema_compatibility_ref": schema_compatibility_ref,
        "semantic_binding_ref": None,
        "attestation_ref": None,
        "redaction_policy_ref": None,
        "duplicate_of": None,
        "validation_status": "pass",
        "blocking_status": "non_overridable" if lifecycle_decision == "withdraw" else "blocking",
        "governance": {
            "classification": "internal",
            "authority_boundary": "runtime_continuous_governance_lifecycle",
            "pii": "none",
            "retention_policy": "runtime_quality_retention",
            "review_status": state_after,
            "override_policy": "not_overridable",
            "approval_policy": "requires_verified_scorecard",
        },
    }


def _evaluate_schema_compatibility(
    *,
    schema_version: str,
    reader: str,
    expected_schema_family: str,
) -> dict[str, Any]:
    return {
        "decision": "compatible",
        "reader": reader,
        "schema_family": expected_schema_family,
        "schema_version": schema_version,
    }


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
    "AdvisoryPosture",
    "AppealPerturbation",
    "CONTINUOUS_GOVERNANCE_FLAG",
    "CorrectionPerturbation",
    "DiscoveredBiasPerturbation",
    "ENABLE_REISSUE_WORKFLOW_FLAG",
    "ENABLE_WITHDRAWAL_STATUS_FLAG",
    "DecisionValidityStatus",
    "EpochPerturbation",
    "EpochPerturbationClass",
    "GOVERNANCE_MONITOR_EVENT_KIND",
    "GOVERNANCE_MONITOR_EVENT_SCHEMA_NAME",
    "GOVERNANCE_MONITOR_EVENT_SCHEMA_VERSION",
    "GOVERNANCE_LIFECYCLE_DIAGNOSTIC_EVENT_TYPE",
    "GOVERNANCE_LIFECYCLE_REPORT_KIND",
    "GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_ID",
    "GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_NAME",
    "GOVERNANCE_LIFECYCLE_REPORT_SCHEMA_VERSION",
    "GOVERNANCE_LIFECYCLE_RUNTIME_REF_KEYS",
    "GovernanceLifecycleEvidence",
    "GovernanceMonitorEvent",
    "GovernanceMonitorRecommendation",
    "IncidentPerturbation",
    "LegalChangePerturbation",
    "LifecycleDecision",
    "MonitorAction",
    "MonitorEventType",
    "MonitorSeverity",
    "PersistedGovernanceMonitorEvent",
    "RetractionPerturbation",
    "aggregate_validity_status",
    "build_drift_monitor_event",
    "emit_governance_lifecycle_evidence",
    "lifecycle_decision_id",
    "monitor_event_id",
    "persist_governance_monitor_event",
    "persist_incident_monitor_event",
    "recommend_validity_action",
    "resolve_governance_monitor_event",
]
