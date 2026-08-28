"""Bridge Research DAG invalidation into continuous governance controls."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef, CanonInfo, InputRef, SchemaInfo
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.scientist.evidence.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleEvent,
)
from polisyos.scientist.methods.research_dag.invalidation import (
    SourceInvalidationImpact,
    append_invalidation_events_to_ledger,
)

from .monitors import (
    CorrectionPerturbation,
    GovernanceMonitorEvent,
    GovernanceMonitorRecommendation,
    MonitorSeverity,
    RetractionPerturbation,
    monitor_event_id,
    recommend_validity_action,
)

EVIDENCE_VALIDITY_EVENT_KIND = "scientist.evidence_validity_event"
EVIDENCE_VALIDITY_EVENT_SCHEMA_NAME = "polisyos.scientist.EvidenceValidityEvent"
EVIDENCE_VALIDITY_EVENT_SCHEMA_VERSION = "1.0"


class EvidenceValidityEvent(BaseModel):
    """Bind a correction/retraction across the complete published evidence path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    event_id: str = Field(min_length=1)
    event_class: Literal["correction", "retraction"]
    source_event_ref: ArtifactRef
    evidence_line_ref: ArtifactRef
    claim_ref: ArtifactRef
    claim_id: str = Field(min_length=1)
    publication_ref: ArtifactRef
    reason: str = Field(min_length=1)
    replacement_refs: tuple[ArtifactRef, ...] = ()
    logic_relation: Literal["unchanged", "changed", "not_established"]
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _validate_complete_path(self) -> EvidenceValidityEvent:
        refs = (
            self.source_event_ref,
            self.evidence_line_ref,
            self.claim_ref,
            self.publication_ref,
        )
        identities = tuple(str(ref.artifact_id) for ref in refs)
        if len(set(identities)) != len(identities):
            raise ValueError("evidence validity path roles require distinct artifacts")
        if self.event_class == "correction" and not self.replacement_refs:
            raise ValueError("correction requires replacement evidence")
        if self.event_class == "retraction" and self.replacement_refs:
            raise ValueError("retraction cannot carry replacement evidence")
        return self


class PersistedEvidenceValidityEvent(BaseModel):
    """Exact content-bound handle for one evidence validity event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_ref: ArtifactRef
    event_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    event: EvidenceValidityEvent


def evidence_validity_event_inputs(event: EvidenceValidityEvent) -> list[InputRef]:
    """Return the complete source-to-publication lineage carried by the event."""

    inputs = [
        InputRef(artifact_id=event.source_event_ref.artifact_id, role="source_event"),
        InputRef(artifact_id=event.evidence_line_ref.artifact_id, role="evidence_line"),
        InputRef(artifact_id=event.claim_ref.artifact_id, role="claim"),
        InputRef(artifact_id=event.publication_ref.artifact_id, role="publication"),
    ]
    inputs.extend(
        InputRef(artifact_id=ref.artifact_id, role=f"replacement[{index}]")
        for index, ref in enumerate(event.replacement_refs)
    )
    return inputs


def persist_evidence_validity_event(
    store: ArtifactStore,
    event: EvidenceValidityEvent,
) -> PersistedEvidenceValidityEvent:
    """Persist and exact-read one correction/retraction event."""

    ref = store.put_json(
        event,
        PutOptions(
            kind=EVIDENCE_VALIDITY_EVENT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=EVIDENCE_VALIDITY_EVENT_SCHEMA_NAME,
                version=EVIDENCE_VALIDITY_EVENT_SCHEMA_VERSION,
            ),
            inputs=evidence_validity_event_inputs(event),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    persisted = resolve_evidence_validity_event(store, ref)
    if persisted.event != event:
        raise ValueError("evidence validity event readback mismatch")
    return persisted


def resolve_evidence_validity_event(
    store: ArtifactStore,
    ref: ArtifactRef,
) -> PersistedEvidenceValidityEvent:
    """Resolve exact bytes, manifest profile, and lineage for one event."""

    raw = store.get_bytes(ref.artifact_id)
    report = store.verify(ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    observed_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
    event = EvidenceValidityEvent.model_validate(from_canonical_bytes(raw))
    expected_inputs = evidence_validity_event_inputs(event)
    if (
        not report.ok
        or observed_hash != str(ref.artifact_id)
        or ref.kind != EVIDENCE_VALIDITY_EVENT_KIND
        or ref.media_type != "application/json"
        or manifest.artifact_id != ref.artifact_id
        or manifest.kind != EVIDENCE_VALIDITY_EVENT_KIND
        or manifest.media_type != "application/json"
        or manifest.artifact_schema
        != SchemaInfo(
            name=EVIDENCE_VALIDITY_EVENT_SCHEMA_NAME,
            version=EVIDENCE_VALIDITY_EVENT_SCHEMA_VERSION,
        )
        or manifest.canon != CanonInfo.from_spec(CanonSpec(forbid_floats=False))
        or manifest.inputs != expected_inputs
        or to_canonical_bytes(event, CanonSpec(forbid_floats=False)) != raw
    ):
        raise ValueError("evidence validity event artifact binding mismatch")
    return PersistedEvidenceValidityEvent(
        event_ref=ref,
        event_content_hash=observed_hash,
        event=event,
    )


def governance_event_from_evidence_validity(
    *,
    persisted: PersistedEvidenceValidityEvent,
) -> GovernanceMonitorEvent:
    """Project a verified evidence event into one downgrade-only monitor signal."""

    event = persisted.event
    perturbation = (
        CorrectionPerturbation(
            evidence_validity_event_ref=persisted.event_ref,
            replacement_refs=event.replacement_refs,
        )
        if event.event_class == "correction"
        else RetractionPerturbation(evidence_validity_event_ref=persisted.event_ref)
    )
    return GovernanceMonitorEvent(
        event_id=monitor_event_id(
            decision_packet_ref=event.publication_ref,
            event_type="source_invalidation",
            reason=event.reason,
        ),
        decision_packet_ref=event.publication_ref,
        event_type="source_invalidation",
        severity="warning" if event.event_class == "correction" else "block",
        affected_claim_ids=[event.claim_id],
        reason=event.reason,
        occurred_at=event.occurred_at,
        perturbation=perturbation,
        advisory_posture=(
            "annotation_only"
            if event.event_class == "correction" and event.logic_relation == "unchanged"
            else "review_required"
        ),
        metadata={"logic_relation": event.logic_relation},
    )


class ContinuousInvalidationResult(BaseModel):
    """Continuous-governance result for one propagated source invalidation."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    schema_version: Literal["1.0"] = "1.0"
    governance_event: GovernanceMonitorEvent
    recommendation: GovernanceMonitorRecommendation
    lifecycle_events: list[ClaimLifecycleEvent] = Field(default_factory=list)
    updated_ledger: AppendOnlyClaimLedger
    affected_claim_ids: list[str] = Field(default_factory=list)
    affected_dag_node_ids: list[str] = Field(default_factory=list)


def governance_event_from_source_invalidation(
    *,
    decision_packet_ref: ArtifactRef,
    impact: SourceInvalidationImpact,
    severity: MonitorSeverity | None = None,
    sequence: int = 0,
) -> GovernanceMonitorEvent:
    """Create a monitor event from DAG invalidation impact.

    A source invalidation without dependent claim or DAG lineage is ambiguous;
    it must be rejected rather than silently passing the monitoring loop.
    """

    if not impact.stale_claim_ids and not impact.affected_node_ids:
        raise ValueError("source invalidation must identify affected claim or DAG lineage")
    resolved_severity = severity
    if resolved_severity is None:
        resolved_severity = (
            "block"
            if impact.event.invalidation_type in {"withdrawn", "contradicted"}
            else "warning"
        )
    return GovernanceMonitorEvent(
        event_id=monitor_event_id(
            decision_packet_ref=decision_packet_ref,
            event_type="source_invalidation",
            reason=impact.event.reason,
            sequence=sequence,
        ),
        decision_packet_ref=decision_packet_ref,
        event_type="source_invalidation",
        severity=resolved_severity,
        affected_claim_ids=list(impact.stale_claim_ids),
        affected_dag_node_ids=list(impact.affected_node_ids),
        reason=impact.event.reason,
        occurred_at=impact.event.occurred_at,
        metadata={
            "source_invalidation_event_id": impact.event.event_id,
            "source_ref": str(impact.event.source_ref.artifact_id),
            "invalidation_type": impact.event.invalidation_type,
            "workflow_id": impact.workflow_id,
            "claim_lifecycle_action": impact.claim_lifecycle_action.value,
        },
    )


def mark_dependent_claims_stale(
    *,
    ledger: AppendOnlyClaimLedger,
    decision_packet_ref: ArtifactRef,
    impact: SourceInvalidationImpact,
    actor_id: str,
    occurred_at: datetime | None = None,
    severity: MonitorSeverity | None = None,
) -> ContinuousInvalidationResult:
    """Append lifecycle events and return the monitor recommendation."""

    timestamp = occurred_at or impact.event.occurred_at or datetime.now(UTC)
    before = len(ledger.events)
    updated_ledger = append_invalidation_events_to_ledger(
        ledger,
        impact,
        actor_id=actor_id,
        occurred_at=timestamp,
    )
    lifecycle_events = list(updated_ledger.events[before:])
    governance_event = governance_event_from_source_invalidation(
        decision_packet_ref=decision_packet_ref,
        impact=impact,
        severity=severity,
    )
    return ContinuousInvalidationResult(
        governance_event=governance_event,
        recommendation=recommend_validity_action(governance_event),
        lifecycle_events=lifecycle_events,
        updated_ledger=updated_ledger,
        affected_claim_ids=list(impact.stale_claim_ids),
        affected_dag_node_ids=list(impact.affected_node_ids),
    )


__all__ = [
    "ContinuousInvalidationResult",
    "EVIDENCE_VALIDITY_EVENT_KIND",
    "EVIDENCE_VALIDITY_EVENT_SCHEMA_NAME",
    "EVIDENCE_VALIDITY_EVENT_SCHEMA_VERSION",
    "EvidenceValidityEvent",
    "PersistedEvidenceValidityEvent",
    "evidence_validity_event_inputs",
    "governance_event_from_evidence_validity",
    "governance_event_from_source_invalidation",
    "mark_dependent_claims_stale",
    "persist_evidence_validity_event",
    "resolve_evidence_validity_event",
]
