"""Reissue packet contracts for superseded living decision artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes

from .monitors import (
    DecisionValidityStatus,
    GovernanceLifecycleEvidence,
    LifecycleDecision,
    emit_governance_lifecycle_evidence,
)

REISSUE_PACKET_KIND = "scientist.reissue_packet"
REISSUE_PACKET_SCHEMA_NAME = "polisyos.scientist.ReissuePacket"
REISSUE_PACKET_SCHEMA_VERSION = "1.0"


class ReissuePacket(BaseModel):
    """Auditable old/new linkage for a reissued or review-required decision."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    original_decision_packet_ref: ArtifactRef
    new_decision_packet_ref: ArtifactRef | None = None
    original_claim_ledger_ref: ArtifactRef
    new_claim_ledger_ref: ArtifactRef | None = None
    original_scorecard_ref: ArtifactRef | None = None
    new_evidence_refs: list[ArtifactRef] = Field(default_factory=list)
    status: DecisionValidityStatus
    monitor_event_refs: list[ArtifactRef] = Field(default_factory=list)
    human_review_ref: ArtifactRef | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reason: str = Field(min_length=1)
    change_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("reason", "change_reason")
    @classmethod
    def _non_blank_reason(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("reissue reason cannot be blank")
        return value

    @model_validator(mode="after")
    def _validate_reissue_links(self) -> ReissuePacket:
        if self.status is DecisionValidityStatus.REISSUED:
            if self.new_decision_packet_ref is None or self.new_claim_ledger_ref is None:
                raise ValueError("reissued packets require new decision and claim ledger refs")
        if (
            self.status
            in {
                DecisionValidityStatus.STALE,
                DecisionValidityStatus.REVIEW_REQUIRED,
                DecisionValidityStatus.SUPERSEDED,
                DecisionValidityStatus.REISSUED,
                DecisionValidityStatus.WITHDRAWN,
            }
            and not self.monitor_event_refs
        ):
            raise ValueError("non-valid reissue packets require monitor_event_refs")
        if self.status is DecisionValidityStatus.WITHDRAWN and self.human_review_ref is None:
            raise ValueError("withdrawn reissue packets require human_review_ref")
        if self.change_reason is None:
            self.change_reason = self.reason
        return self


def build_reissue_packet(
    *,
    original_decision_packet_ref: ArtifactRef,
    original_claim_ledger_ref: ArtifactRef,
    status: DecisionValidityStatus,
    reason: str,
    monitor_event_refs: list[ArtifactRef],
    new_decision_packet_ref: ArtifactRef | None = None,
    new_claim_ledger_ref: ArtifactRef | None = None,
    original_scorecard_ref: ArtifactRef | None = None,
    new_evidence_refs: list[ArtifactRef] | None = None,
    human_review_ref: ArtifactRef | None = None,
    change_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ReissuePacket:
    """Build a validated reissue packet without mutating old artifacts."""

    return ReissuePacket(
        original_decision_packet_ref=original_decision_packet_ref,
        new_decision_packet_ref=new_decision_packet_ref,
        original_claim_ledger_ref=original_claim_ledger_ref,
        new_claim_ledger_ref=new_claim_ledger_ref,
        original_scorecard_ref=original_scorecard_ref,
        new_evidence_refs=list(new_evidence_refs or []),
        status=status,
        monitor_event_refs=list(monitor_event_refs),
        human_review_ref=human_review_ref,
        reason=reason,
        change_reason=change_reason,
        metadata=metadata or {},
    )


def reissue_packet_inputs(packet: ReissuePacket) -> list[InputRef]:
    """Return CAS lineage inputs for a reissue packet."""

    inputs: list[InputRef] = []

    def add(ref: ArtifactRef | None, role: str) -> None:
        if ref is not None:
            inputs.append(InputRef(artifact_id=ref.artifact_id, role=role))

    add(packet.original_decision_packet_ref, "original_decision_packet")
    add(packet.new_decision_packet_ref, "new_decision_packet")
    add(packet.original_claim_ledger_ref, "original_claim_ledger")
    add(packet.new_claim_ledger_ref, "new_claim_ledger")
    add(packet.original_scorecard_ref, "original_scorecard")
    add(packet.human_review_ref, "human_review")
    for index, ref in enumerate(packet.monitor_event_refs):
        add(ref, f"monitor_event[{index}]")
    for index, ref in enumerate(packet.new_evidence_refs):
        add(ref, f"new_evidence[{index}]")
    return inputs


def persist_reissue_packet(
    store: Any,
    packet: ReissuePacket,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a ReissuePacket as a CAS sidecar."""

    return store.put_json(
        packet,
        PutOptions(
            kind=REISSUE_PACKET_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=REISSUE_PACKET_SCHEMA_NAME,
                version=REISSUE_PACKET_SCHEMA_VERSION,
            ),
            inputs=list(inputs) if inputs is not None else reissue_packet_inputs(packet),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_reissue_packet(store: Any, ref: ArtifactRef) -> ReissuePacket:
    """Load a persisted ReissuePacket from CAS."""

    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return ReissuePacket.model_validate(payload)


def lifecycle_decision_for_reissue_status(
    status: DecisionValidityStatus,
) -> LifecycleDecision:
    """Map reissue-packet statuses to runtime lifecycle evidence decisions."""

    if status is DecisionValidityStatus.REISSUED:
        return "reissue"
    if status is DecisionValidityStatus.SUPERSEDED:
        return "supersede"
    if status is DecisionValidityStatus.WITHDRAWN:
        return "withdraw"
    raise ValueError(f"status {status.value!r} does not emit reissue lifecycle evidence")


def emit_reissue_lifecycle_evidence(
    store: Any,
    *,
    packet: ReissuePacket,
    packet_ref: ArtifactRef,
    run_id: str,
    job_id: str,
    tenant_id: str,
    cell_id: str | None,
    trace_id: str,
    span_id: str,
    effective_mode_ref: str,
    fallback_degradation_ref: str,
    requested_execution_profile: str = "production",
    effective_execution_profile: str = "production",
    producer_component: str = "polisyos.scientist.governance.continuous.reissue",
    producer_version: str = "2026.05.15+hds-phase2.7",
    owner: str = "team-runtime",
    event_log: object | None = None,
) -> GovernanceLifecycleEvidence:
    """Emit runtime-owned evidence for reissue, supersede, and withdraw decisions."""

    lifecycle_decision = lifecycle_decision_for_reissue_status(packet.status)
    cas_artifact_refs = {
        "reissue_packet_ref": str(packet_ref.artifact_id),
        "original_decision_packet_ref": str(packet.original_decision_packet_ref.artifact_id),
        "original_claim_ledger_ref": str(packet.original_claim_ledger_ref.artifact_id),
    }
    if packet.new_decision_packet_ref is not None:
        cas_artifact_refs["new_decision_packet_ref"] = str(
            packet.new_decision_packet_ref.artifact_id
        )
    if packet.new_claim_ledger_ref is not None:
        cas_artifact_refs["new_claim_ledger_ref"] = str(packet.new_claim_ledger_ref.artifact_id)
    if packet.human_review_ref is not None:
        cas_artifact_refs["human_review_ref"] = str(packet.human_review_ref.artifact_id)

    return emit_governance_lifecycle_evidence(
        store,
        lifecycle_decision=lifecycle_decision,
        decision_packet_ref=packet.original_decision_packet_ref,
        status=packet.status,
        reason=packet.reason,
        monitor_event_refs=list(packet.monitor_event_refs),
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        trace_id=trace_id,
        span_id=span_id,
        effective_mode_ref=effective_mode_ref,
        fallback_degradation_ref=fallback_degradation_ref,
        cas_artifact_refs=cas_artifact_refs,
        requested_execution_profile=requested_execution_profile,
        effective_execution_profile=effective_execution_profile,
        producer_component=producer_component,
        producer_version=producer_version,
        owner=owner,
        state_before="review_required",
        occurred_at=packet.created_at,
        event_log=event_log,
    )


__all__ = [
    "REISSUE_PACKET_KIND",
    "REISSUE_PACKET_SCHEMA_NAME",
    "REISSUE_PACKET_SCHEMA_VERSION",
    "ReissuePacket",
    "build_reissue_packet",
    "emit_reissue_lifecycle_evidence",
    "lifecycle_decision_for_reissue_status",
    "load_reissue_packet",
    "persist_reissue_packet",
    "reissue_packet_inputs",
]
