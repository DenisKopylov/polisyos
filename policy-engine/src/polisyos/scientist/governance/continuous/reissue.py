"""Reissue packet contracts for superseded living decision artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes

from .monitors import (
    DecisionValidityStatus,
    GovernanceLifecycleEvidence,
    GovernanceMonitorEvent,
    LifecycleDecision,
    emit_governance_lifecycle_evidence,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

REISSUE_PACKET_KIND = "scientist.reissue_packet"
REISSUE_PACKET_SCHEMA_NAME = "polisyos.scientist.ReissuePacket"
REISSUE_PACKET_SCHEMA_VERSION = "1.1"
PUBLIC_REVISION_STATE_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.public_revision_state.v1"
)


class _JsonArtifactStore(Protocol):
    def put_json(
        self,
        value: object,
        options: PutOptions,
        *,
        canon_spec: CanonSpec,
    ) -> ArtifactRef:
        ...

    def get_bytes(self, artifact_id: object) -> bytes:
        ...


class PublicRevisionDiff(BaseModel):
    """Public claim-local diff summary for scoped reissue projection."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1)
    diff_kind: str = Field(min_length=1)
    public_status: str = Field(min_length=1)
    reason: str = Field(min_length=1)

    @field_validator("claim_id", "diff_kind", "public_status", "reason")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("public revision diff text fields cannot be blank")
        return value


class PartialPublicationState(BaseModel):
    """Projection-only public state for a scoped reissue."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["policyos.runtime.policy_design_case.public_revision_state.v1"] = (
        PUBLIC_REVISION_STATE_SCHEMA_VERSION
    )
    case_id: str | None = None
    generated_at: str | None = None
    current_case_validity: Literal[
        "current",
        "partially_current",
        "review_required",
        "revalidation_required",
        "superseded",
        "withdrawn",
    ] = "partially_current"
    closed_case_historical_meaning: Literal["preserved"] = "preserved"
    affected_claim_ids: list[str] = Field(default_factory=list)
    unaffected_claim_ids: list[str] = Field(default_factory=list)
    public_diffs: list[PublicRevisionDiff] = Field(default_factory=list)
    public_diff_required: bool = True
    silent_upgrade_allowed: Literal[False] = False
    revalidation_status: Literal[
        "current",
        "review_required",
        "revalidation_required",
        "superseded",
        "withdrawn",
    ] = "revalidation_required"
    rule_evolution_public_annotation: dict[str, Any] = Field(default_factory=dict)
    blocked_structural_policy_ref: str | None = None
    authority_role: Literal["projection_only"] = "projection_only"
    provenance_kind: Literal["runtime_projection"] = "runtime_projection"
    authoritative_for: list[str] = Field(
        default_factory=lambda: ["public_revision_state", "partial_publication_state"]
    )
    may_not_use_for: list[str] = Field(
        default_factory=lambda: [
            "claim_evidence_authority",
            "mandatory_public_revalidation_policy",
            "scorecard_authority",
            "silent_current_logic_upgrade",
        ]
    )

    @field_validator("case_id")
    @classmethod
    def _non_blank_optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("partial publication state case_id cannot be blank")
        return value

    @field_validator("affected_claim_ids", "unaffected_claim_ids")
    @classmethod
    def _claim_ids_are_unique(cls, values: list[str]) -> list[str]:
        return _dedupe_claim_ids(values)

    @model_validator(mode="after")
    def _validate_projection_boundary(self) -> PartialPublicationState:
        overlap = set(self.affected_claim_ids).intersection(self.unaffected_claim_ids)
        if overlap:
            raise ValueError("partial publication affected/unaffected claim ids must be disjoint")
        if self.current_case_validity == "partially_current" and (
            not self.affected_claim_ids or not self.unaffected_claim_ids
        ):
            raise ValueError(
                "partially_current publication state requires affected and unaffected claims"
            )
        if self.public_diff_required and not self.public_diffs:
            raise ValueError("partial publication state requires public diffs")
        if "silent_current_logic_upgrade" not in set(self.may_not_use_for):
            raise ValueError("partial publication state must forbid silent current-logic upgrades")
        return self


class ReissuePacket(BaseModel):
    """Auditable old/new linkage for a reissued or review-required decision."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "1.1"] = "1.1"
    original_decision_packet_ref: ArtifactRef
    new_decision_packet_ref: ArtifactRef | None = None
    original_claim_ledger_ref: ArtifactRef
    new_claim_ledger_ref: ArtifactRef | None = None
    original_scorecard_ref: ArtifactRef | None = None
    new_evidence_refs: list[ArtifactRef] = Field(default_factory=list)
    scope_to_revise: list[str] = Field(default_factory=list)
    unchanged_records: list[ArtifactRef] = Field(default_factory=list)
    superseded_refs: list[ArtifactRef] = Field(default_factory=list)
    public_diff_refs: list[ArtifactRef] = Field(default_factory=list)
    partial_publication_state: PartialPublicationState | None = None
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

    @field_validator("scope_to_revise")
    @classmethod
    def _scope_to_revise_is_unique(cls, values: list[str]) -> list[str]:
        return _dedupe_claim_ids(values)

    @model_validator(mode="after")
    def _validate_reissue_links(self) -> ReissuePacket:
        if self.status is DecisionValidityStatus.REISSUED and (
            self.new_decision_packet_ref is None or self.new_claim_ledger_ref is None
        ):
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
        if self.scope_to_revise and self.partial_publication_state is None:
            raise ValueError("partial-scope reissue packets require partial_publication_state")
        if self.partial_publication_state is not None:
            if not self.scope_to_revise:
                raise ValueError("partial_publication_state requires scope_to_revise")
            affected = set(self.partial_publication_state.affected_claim_ids)
            if affected != set(self.scope_to_revise):
                raise ValueError("scope_to_revise must match partial publication affected claims")
            if (
                self.partial_publication_state.unaffected_claim_ids
                and not self.unchanged_records
            ):
                raise ValueError("partial-scope reissue packets require unchanged_records")
            if (
                self.status is DecisionValidityStatus.REISSUED
                and self.scope_to_revise
                and not self.superseded_refs
            ):
                raise ValueError("partial reissued packets require superseded_refs")
            if self.partial_publication_state.public_diff_required and not self.public_diff_refs:
                raise ValueError("partial-scope reissue packets require public_diff_refs")
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
    scope_to_revise: list[str] | None = None,
    unchanged_records: list[ArtifactRef] | None = None,
    superseded_refs: list[ArtifactRef] | None = None,
    public_diff_refs: list[ArtifactRef] | None = None,
    partial_publication_state: PartialPublicationState | dict[str, Any] | None = None,
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
        scope_to_revise=list(scope_to_revise or []),
        unchanged_records=list(unchanged_records or []),
        superseded_refs=list(superseded_refs or []),
        public_diff_refs=list(public_diff_refs or []),
        partial_publication_state=partial_publication_state,
        status=status,
        monitor_event_refs=list(monitor_event_refs),
        human_review_ref=human_review_ref,
        reason=reason,
        change_reason=change_reason,
        metadata=metadata or {},
    )


def build_partial_scope_reissue_packet(
    *,
    original_decision_packet_ref: ArtifactRef,
    original_claim_ledger_ref: ArtifactRef,
    all_claim_ids: list[str],
    monitor_events: list[GovernanceMonitorEvent],
    monitor_event_refs: list[ArtifactRef],
    reason: str,
    new_decision_packet_ref: ArtifactRef | None = None,
    new_claim_ledger_ref: ArtifactRef | None = None,
    original_scorecard_ref: ArtifactRef | None = None,
    new_evidence_refs: list[ArtifactRef] | None = None,
    unchanged_records: list[ArtifactRef] | None = None,
    superseded_refs: list[ArtifactRef] | None = None,
    public_diff_refs: list[ArtifactRef] | None = None,
    status: DecisionValidityStatus = DecisionValidityStatus.REISSUED,
    human_review_ref: ArtifactRef | None = None,
    change_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
    case_id: str | None = None,
    generated_at: datetime | None = None,
) -> ReissuePacket:
    """Build a partial-scope packet from monitor events with affected claims.

    This is the W9.B producer for the scoped packet contract. It treats monitor
    events as detector output, maps their affected claim ids to a reissue scope,
    and keeps unaffected claim records append-only via `unchanged_records`.
    """

    known_claim_ids = _dedupe_claim_ids(all_claim_ids)
    if not known_claim_ids:
        raise ValueError("partial-scope reissue requires closed case claim ids")
    scope_to_revise = reissue_scope_from_monitor_events(
        monitor_events,
        all_claim_ids=known_claim_ids,
    )
    unaffected_claim_ids = [
        claim_id for claim_id in known_claim_ids if claim_id not in scope_to_revise
    ]
    if not unaffected_claim_ids:
        raise ValueError("partial-scope reissue requires at least one unaffected claim")
    if not unchanged_records:
        raise ValueError("partial-scope reissue requires unchanged_records")
    if status is DecisionValidityStatus.REISSUED and not superseded_refs:
        raise ValueError("partial reissued packets require superseded_refs")
    if not public_diff_refs:
        raise ValueError("partial-scope reissue requires public_diff_refs")
    partial_state = PartialPublicationState(
        case_id=case_id,
        generated_at=(generated_at or datetime.now(UTC)).isoformat(),
        current_case_validity="partially_current",
        affected_claim_ids=scope_to_revise,
        unaffected_claim_ids=unaffected_claim_ids,
        public_diffs=_public_diffs_for_scope(scope_to_revise, monitor_events),
        public_diff_required=True,
        revalidation_status="revalidation_required",
    )
    resolved_metadata = dict(metadata or {})
    resolved_metadata.setdefault("partial_scope", True)
    resolved_metadata.setdefault("all_claim_ids", known_claim_ids)
    resolved_metadata.setdefault("unaffected_claim_ids", unaffected_claim_ids)
    resolved_metadata.setdefault(
        "monitor_event_ids",
        [event.event_id for event in monitor_events],
    )
    return build_reissue_packet(
        original_decision_packet_ref=original_decision_packet_ref,
        original_claim_ledger_ref=original_claim_ledger_ref,
        new_decision_packet_ref=new_decision_packet_ref,
        new_claim_ledger_ref=new_claim_ledger_ref,
        original_scorecard_ref=original_scorecard_ref,
        new_evidence_refs=new_evidence_refs,
        scope_to_revise=scope_to_revise,
        unchanged_records=unchanged_records,
        superseded_refs=superseded_refs,
        public_diff_refs=public_diff_refs,
        partial_publication_state=partial_state,
        status=status,
        monitor_event_refs=monitor_event_refs,
        human_review_ref=human_review_ref,
        reason=reason,
        change_reason=change_reason,
        metadata=resolved_metadata,
    )


def reissue_scope_from_monitor_events(
    monitor_events: list[GovernanceMonitorEvent],
    *,
    all_claim_ids: list[str],
) -> list[str]:
    """Return scoped affected claim ids from detector monitor events."""

    known_claim_ids = _dedupe_claim_ids(all_claim_ids)
    known = set(known_claim_ids)
    if not monitor_events:
        raise ValueError("partial-scope reissue requires monitor events")
    scope: list[str] = []
    for event in monitor_events:
        event_claim_ids = _dedupe_claim_ids(event.affected_claim_ids)
        if not event_claim_ids:
            raise ValueError("partial-scope reissue requires affected claim ids on monitor events")
        unknown = set(event_claim_ids).difference(known)
        if unknown:
            raise ValueError(
                "partial-scope reissue monitor event references claims outside closed case: "
                + ", ".join(sorted(unknown))
            )
        scope.extend(event_claim_ids)
    return _dedupe_claim_ids(scope)


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
    for index, ref in enumerate(packet.unchanged_records):
        add(ref, f"unchanged_record[{index}]")
    for index, ref in enumerate(packet.superseded_refs):
        add(ref, f"superseded_ref[{index}]")
    for index, ref in enumerate(packet.public_diff_refs):
        add(ref, f"public_diff[{index}]")
    return inputs


def persist_reissue_packet(
    store: _JsonArtifactStore,
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


def load_reissue_packet(store: _JsonArtifactStore, ref: ArtifactRef) -> ReissuePacket:
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
    store: _JsonArtifactStore,
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
    for index, ref in enumerate(packet.unchanged_records):
        cas_artifact_refs[f"unchanged_record[{index}]"] = str(ref.artifact_id)
    for index, ref in enumerate(packet.superseded_refs):
        cas_artifact_refs[f"superseded_ref[{index}]"] = str(ref.artifact_id)
    for index, ref in enumerate(packet.public_diff_refs):
        cas_artifact_refs[f"public_diff[{index}]"] = str(ref.artifact_id)

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


def _public_diffs_for_scope(
    scope_to_revise: list[str],
    monitor_events: list[GovernanceMonitorEvent],
) -> list[PublicRevisionDiff]:
    reasons_by_claim: dict[str, list[str]] = {claim_id: [] for claim_id in scope_to_revise}
    for event in monitor_events:
        for claim_id in event.affected_claim_ids:
            if claim_id in reasons_by_claim:
                reasons_by_claim[claim_id].append(event.reason)
    diffs: list[PublicRevisionDiff] = []
    for claim_id in scope_to_revise:
        reasons = _dedupe_claim_ids(reasons_by_claim.get(claim_id, []))
        diffs.append(
            PublicRevisionDiff(
                claim_id=claim_id,
                diff_kind="partial_reissue",
                public_status="revalidation_required",
                reason="; ".join(reasons) if reasons else "Scoped reissue requires revalidation.",
            )
        )
    return diffs


def _dedupe_claim_ids(values: Iterable[object] | str | None) -> list[str]:
    if values is None:
        return []
    iterable = [values] if isinstance(values, str) else values
    deduped: list[str] = []
    seen: set[str] = set()
    for value in iterable:
        text = str(value).strip()
        if not text:
            raise ValueError("claim ids cannot be blank")
        if text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


__all__ = [
    "PUBLIC_REVISION_STATE_SCHEMA_VERSION",
    "REISSUE_PACKET_KIND",
    "REISSUE_PACKET_SCHEMA_NAME",
    "REISSUE_PACKET_SCHEMA_VERSION",
    "PartialPublicationState",
    "PublicRevisionDiff",
    "ReissuePacket",
    "build_partial_scope_reissue_packet",
    "build_reissue_packet",
    "emit_reissue_lifecycle_evidence",
    "lifecycle_decision_for_reissue_status",
    "load_reissue_packet",
    "persist_reissue_packet",
    "reissue_packet_inputs",
    "reissue_scope_from_monitor_events",
]
