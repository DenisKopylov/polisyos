"""Bridge continuous-governance detector events into claim lifecycle state."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core import artifacts as core_artifacts
from polisyos.core import canon
from polisyos.scientist.evidence.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleAction,
    ClaimLifecycleEvent,
    append_lifecycle_event,
    lifecycle_event_id,
)

from .monitors import (
    DecisionValidityStatus,
    GovernanceMonitorEvent,
)
from .reissue import (
    PartialPublicationState,
    PublicRevisionDiff,
    ReissuePacket,
    build_partial_scope_reissue_packet,
)
from .reports import (
    DecisionValidityReport,
    build_validity_report,
    export_public_validity_report,
)

LifecycleBridgeStatus = Literal["pass", "blocked"]
ClaimLifecycleTransition = Literal[
    "stale",
    "blocked",
    "invalidated",
    "superseded",
    "review_required",
    "reissued",
    "withdrawn",
]

LIFECYCLE_BRIDGE_RESULT_KIND = "scientist.lifecycle_bridge_result"
LIFECYCLE_BRIDGE_RESULT_SCHEMA_NAME = "polisyos.scientist.LifecycleBridgeResult"
LIFECYCLE_BRIDGE_RESULT_SCHEMA_VERSION = "1.0"

_BRIDGE_COMPONENT = "polisyos.scientist.governance.continuous.lifecycle_bridge"
_BRIDGE_VERSION = "2026.05.24+w9e"
ArtifactID = core_artifacts.ArtifactID
ArtifactRef = core_artifacts.ArtifactRef
InputRef = core_artifacts.InputRef
PutOptions = core_artifacts.PutOptions
SchemaInfo = core_artifacts.SchemaInfo
_VALID_TRANSITIONS: set[str] = {
    "stale",
    "blocked",
    "invalidated",
    "superseded",
    "review_required",
    "reissued",
    "withdrawn",
}
_TRANSITION_TO_ACTION: dict[ClaimLifecycleTransition, ClaimLifecycleAction] = {
    "stale": ClaimLifecycleAction.MARKED_STALE,
    "blocked": ClaimLifecycleAction.BLOCKED,
    "invalidated": ClaimLifecycleAction.INVALIDATED,
    "superseded": ClaimLifecycleAction.SUPERSEDED,
    "review_required": ClaimLifecycleAction.REVIEW_REQUIRED,
    "reissued": ClaimLifecycleAction.REISSUED,
    "withdrawn": ClaimLifecycleAction.WITHDRAWN,
}
_REVALIDATION_STATUS_BY_TRANSITION: dict[ClaimLifecycleTransition, str] = {
    "stale": "review_required",
    "blocked": "review_required",
    "invalidated": "revalidation_required",
    "superseded": "superseded",
    "review_required": "review_required",
    "reissued": "revalidation_required",
    "withdrawn": "withdrawn",
}


class _JsonArtifactStore(Protocol):
    def put_json(
        self,
        value: object,
        options: PutOptions,
        *,
        canon_spec: canon.CanonSpec,
    ) -> ArtifactRef:
        ...

    def get_bytes(self, artifact_id: ArtifactID | object) -> bytes:
        ...


class LifecycleBridgeBlocker(BaseModel):
    """Fail-closed blocker when a monitor event cannot produce lifecycle state."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    code: Literal["event_missing_lifecycle_bridge"] = "event_missing_lifecycle_bridge"
    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    affected_claim_ids: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    next_action: str = (
        "Map the detector event to closed-case claim ids and emit append-only "
        "claim lifecycle state before public revision or closeout."
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimLifecycleTransitionRecord(BaseModel):
    """Claim-local transition produced from one continuous-governance event."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    schema_version: Literal["1.0"] = "1.0"
    event_id: str = Field(min_length=1)
    monitor_event_ref: ArtifactRef | None = None
    claim_id: str = Field(min_length=1)
    transition: ClaimLifecycleTransition
    claim_lifecycle_action: ClaimLifecycleAction
    lifecycle_event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    public_revision_status: str = Field(min_length=1)
    occurred_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_id", "claim_id", "lifecycle_event_id", "event_type", "reason")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("lifecycle bridge transition text fields cannot be blank")
        return value

    @model_validator(mode="after")
    def _action_matches_transition(self) -> ClaimLifecycleTransitionRecord:
        if _TRANSITION_TO_ACTION[self.transition] is not self.claim_lifecycle_action:
            raise ValueError("claim lifecycle action must match bridge transition")
        return self


class LifecycleBridgeResult(BaseModel):
    """Typed W9.E bridge output over monitor events, claim ledger, and revision state."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    schema_version: Literal["1.0"] = "1.0"
    bridge_id: str = Field(min_length=1)
    status: LifecycleBridgeStatus
    case_id: str | None = None
    decision_packet_ref: ArtifactRef
    original_claim_ledger_ref: ArtifactRef
    monitor_event_refs: list[ArtifactRef] = Field(default_factory=list)
    transition_records: list[ClaimLifecycleTransitionRecord] = Field(default_factory=list)
    blockers: list[LifecycleBridgeBlocker] = Field(default_factory=list)
    updated_ledger: AppendOnlyClaimLedger
    public_revision_state: PartialPublicationState
    reissue_packet: ReissuePacket | None = None
    validity_report: DecisionValidityReport
    public_validity_report: dict[str, Any]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    authority_boundary: dict[str, list[str]] = Field(default_factory=dict)
    capability_reality: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_bridge_result(self) -> LifecycleBridgeResult:
        if self.status == "blocked" and not self.blockers:
            raise ValueError("blocked lifecycle bridge results require blockers")
        if self.status == "pass" and self.blockers:
            raise ValueError("passing lifecycle bridge results cannot carry blockers")
        if not self.authority_boundary:
            self.authority_boundary = lifecycle_bridge_authority_boundary()
        if not self.capability_reality:
            self.capability_reality = lifecycle_bridge_capability_reality()
        return self


def bridge_governance_events_to_claim_lifecycle(
    *,
    ledger: AppendOnlyClaimLedger,
    decision_packet_ref: ArtifactRef,
    original_claim_ledger_ref: ArtifactRef,
    monitor_events: list[GovernanceMonitorEvent],
    monitor_event_refs: list[ArtifactRef],
    actor_id: str,
    case_id: str | None = None,
    occurred_at: datetime | None = None,
    new_decision_packet_ref: ArtifactRef | None = None,
    new_claim_ledger_ref: ArtifactRef | None = None,
    unchanged_records: list[ArtifactRef] | None = None,
    superseded_refs: list[ArtifactRef] | None = None,
    public_diff_refs: list[ArtifactRef] | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> LifecycleBridgeResult:
    """Map detector monitor events into claim lifecycle and public revision state.

    The bridge preserves historical publication authority: old claim records stay
    visible in the append-only ledger, while the public revision state is a
    projection-only surface over the affected claim ids.
    """

    _validate_bridge_inputs(
        ledger=ledger,
        decision_packet_ref=decision_packet_ref,
        monitor_events=monitor_events,
        monitor_event_refs=monitor_event_refs,
        actor_id=actor_id,
    )
    generated_at = (occurred_at or datetime.now(UTC)).astimezone(UTC)
    known_claim_ids = [claim.claim_id for claim in ledger.current_claims]
    event_refs_by_id = {
        event.event_id: monitor_event_refs[index] for index, event in enumerate(monitor_events)
    }

    transitions: list[ClaimLifecycleTransitionRecord] = []
    blockers: list[LifecycleBridgeBlocker] = []
    updated_ledger = ledger
    sequence = len(updated_ledger.events)

    for event in monitor_events:
        transition = _transition_for_event(event)
        if transition is None:
            continue
        raw_claim_ids = _dedupe_texts(event.affected_claim_ids)
        unknown_claim_ids = sorted(set(raw_claim_ids).difference(known_claim_ids))
        if unknown_claim_ids:
            blockers.append(
                _missing_bridge_blocker(
                    event,
                    known_claim_ids=known_claim_ids,
                    reason=(
                        "Detector event references claim ids outside the closed-case "
                        "lifecycle scope."
                    ),
                )
            )
        affected_claim_ids = _affected_known_claim_ids(event, known_claim_ids=known_claim_ids)
        if not affected_claim_ids:
            if not unknown_claim_ids:
                blockers.append(_missing_bridge_blocker(event, known_claim_ids=known_claim_ids))
            continue
        if transition == "superseded" and _superseded_by_claim_id(event) is None:
            blockers.append(
                _missing_bridge_blocker(
                    event,
                    known_claim_ids=known_claim_ids,
                    reason=(
                        "Superseded lifecycle transitions require "
                        "metadata.superseded_by_claim_id or next_claim_ref."
                    ),
                )
            )
            continue
        for claim_id in affected_claim_ids:
            lifecycle_event = _claim_lifecycle_event(
                event,
                run_id=updated_ledger.run_id,
                claim_id=claim_id,
                transition=transition,
                actor_id=actor_id,
                occurred_at=generated_at,
                sequence=sequence,
            )
            updated_ledger = append_lifecycle_event(updated_ledger, lifecycle_event)
            transitions.append(
                ClaimLifecycleTransitionRecord(
                    event_id=event.event_id,
                    monitor_event_ref=event_refs_by_id[event.event_id],
                    claim_id=claim_id,
                    transition=transition,
                    claim_lifecycle_action=lifecycle_event.action,
                    lifecycle_event_id=lifecycle_event.event_id,
                    event_type=event.event_type,
                    severity=event.severity,
                    reason=event.reason,
                    public_revision_status=_public_status_for_transition(transition),
                    occurred_at=generated_at,
                    metadata={
                        "claim_lifecycle_event_metadata": dict(lifecycle_event.metadata),
                    },
                )
            )
            sequence += 1

    public_revision_state = _build_public_revision_state(
        case_id=case_id,
        claim_ids=known_claim_ids,
        transitions=transitions,
        blockers=blockers,
        generated_at=generated_at,
    )
    reissue_packet = _maybe_build_reissue_packet(
        original_decision_packet_ref=decision_packet_ref,
        original_claim_ledger_ref=original_claim_ledger_ref,
        all_claim_ids=known_claim_ids,
        monitor_events=monitor_events,
        monitor_event_refs=monitor_event_refs,
        transitions=transitions,
        new_decision_packet_ref=new_decision_packet_ref,
        new_claim_ledger_ref=new_claim_ledger_ref,
        unchanged_records=unchanged_records,
        superseded_refs=superseded_refs,
        public_diff_refs=public_diff_refs,
        reason=reason or _result_reason(transitions, blockers),
        case_id=case_id,
        generated_at=generated_at,
        metadata=metadata,
    )
    if reissue_packet is not None and reissue_packet.partial_publication_state is not None:
        public_revision_state = reissue_packet.partial_publication_state

    validity_report = build_validity_report(
        decision_packet_ref=decision_packet_ref,
        monitor_events=monitor_events,
        metadata={
            "lifecycle_bridge_id": _bridge_id(
                decision_packet_ref=decision_packet_ref,
                monitor_events=monitor_events,
            ),
            "status": "blocked" if blockers else "pass",
            "transition_count": len(transitions),
            "blocker_codes": [blocker.code for blocker in blockers],
        },
    )

    return LifecycleBridgeResult(
        bridge_id=_bridge_id(
            decision_packet_ref=decision_packet_ref,
            monitor_events=monitor_events,
        ),
        status="blocked" if blockers else "pass",
        case_id=case_id,
        decision_packet_ref=decision_packet_ref,
        original_claim_ledger_ref=original_claim_ledger_ref,
        monitor_event_refs=list(monitor_event_refs),
        transition_records=transitions,
        blockers=blockers,
        updated_ledger=updated_ledger,
        public_revision_state=public_revision_state,
        reissue_packet=reissue_packet,
        validity_report=validity_report,
        public_validity_report=export_public_validity_report(validity_report),
        generated_at=generated_at,
        authority_boundary=lifecycle_bridge_authority_boundary(),
        capability_reality=lifecycle_bridge_capability_reality(),
        metadata=metadata or {},
    )


def lifecycle_bridge_authority_boundary() -> dict[str, list[str]]:
    """Return the W9.E authority boundary for bridge outputs."""

    return {
        "authoritative_for": [
            "claim_lifecycle_transition_projection",
            "public_revision_state",
            "continuous_governance_lifecycle_bridge",
        ],
        "may_not_use_for": [
            "claim_evidence_authority",
            "detector_signal_truth",
            "mandatory_public_revalidation_policy",
            "silent_current_logic_upgrade",
            "scorecard_authority",
        ],
    }


def lifecycle_bridge_capability_reality() -> dict[str, str]:
    """Return the capability reality declaration for W9.E."""

    return {
        "typed_contract": LIFECYCLE_BRIDGE_RESULT_SCHEMA_NAME,
        "producer": _BRIDGE_COMPONENT,
        "artifact": LIFECYCLE_BRIDGE_RESULT_KIND,
        "orchestration_bridge": (
            "GovernanceMonitorEvent -> ClaimLifecycleEvent -> public revision state"
        ),
        "consumer": "continuous governance validity report and scoped reissue packet",
        "verification": (
            "tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py"
        ),
        "surface": "public_validity_report + projection_only public_revision_state",
        "semantic_test": "unscoped detector event emits event_missing_lifecycle_bridge",
    }


def lifecycle_bridge_result_inputs(result: LifecycleBridgeResult) -> list[InputRef]:
    """Return CAS lineage inputs for a lifecycle bridge result."""

    inputs = [
        InputRef(artifact_id=result.decision_packet_ref.artifact_id, role="decision_packet"),
        InputRef(
            artifact_id=result.original_claim_ledger_ref.artifact_id,
            role="original_claim_ledger",
        ),
    ]
    for index, ref in enumerate(result.monitor_event_refs):
        inputs.append(InputRef(artifact_id=ref.artifact_id, role=f"monitor_event[{index}]"))
    return inputs


def persist_lifecycle_bridge_result(
    store: _JsonArtifactStore,
    result: LifecycleBridgeResult,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a lifecycle bridge result as a CAS sidecar."""

    return store.put_json(
        result,
        PutOptions(
            kind=LIFECYCLE_BRIDGE_RESULT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=LIFECYCLE_BRIDGE_RESULT_SCHEMA_NAME,
                version=LIFECYCLE_BRIDGE_RESULT_SCHEMA_VERSION,
            ),
            inputs=list(inputs) if inputs is not None else lifecycle_bridge_result_inputs(result),
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )


def load_lifecycle_bridge_result(
    store: _JsonArtifactStore,
    ref: ArtifactRef,
) -> LifecycleBridgeResult:
    """Load a persisted lifecycle bridge result from CAS."""

    payload = canon.from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return LifecycleBridgeResult.model_validate(payload)


def _validate_bridge_inputs(
    *,
    ledger: AppendOnlyClaimLedger,
    decision_packet_ref: ArtifactRef,
    monitor_events: list[GovernanceMonitorEvent],
    monitor_event_refs: list[ArtifactRef],
    actor_id: str,
) -> None:
    if not actor_id.strip():
        raise ValueError("lifecycle bridge actor_id cannot be blank")
    if not ledger.current_claims:
        raise ValueError("lifecycle bridge requires a closed-case claim ledger")
    if len(monitor_events) != len(monitor_event_refs):
        raise ValueError("monitor_events and monitor_event_refs must have matching lengths")
    for event in monitor_events:
        if event.decision_packet_ref.artifact_id != decision_packet_ref.artifact_id:
            raise ValueError("monitor event decision_packet_ref must match bridge decision ref")


def _transition_for_event(event: GovernanceMonitorEvent) -> ClaimLifecycleTransition | None:
    explicit = _explicit_transition(event.metadata)
    if explicit is not None:
        return explicit
    if event.severity == "info":
        return None
    if event.event_type == "source_invalidation":
        invalidation_type = (
            _metadata_text(event.metadata, "invalidation_type") or ""
        ).casefold()
        if event.severity == "warning":
            return "stale"
        if invalidation_type in {"superseded", "successor_available"}:
            return "superseded"
        return "invalidated"
    if event.event_type == "policy_context_drift":
        context = " ".join(
            value
            for value in (
                _metadata_text(event.metadata, "change_kind"),
                _metadata_text(event.metadata, "context_change_kind"),
                event.reason,
            )
            if value
        ).casefold()
        if "withdraw" in context:
            return "withdrawn"
        if "supersed" in context:
            return "superseded"
        return "blocked" if event.severity == "block" else "review_required"
    if event.event_type in {"calibration_drift", "fairness_drift"}:
        return "blocked" if event.severity == "block" else "review_required"
    if event.event_type == "incident":
        return "withdrawn" if event.severity == "block" else "review_required"
    return "review_required"


def _explicit_transition(metadata: Mapping[str, Any]) -> ClaimLifecycleTransition | None:
    raw = _metadata_text(metadata, "lifecycle_transition") or _metadata_text(
        metadata,
        "claim_lifecycle_transition",
    )
    if raw is None:
        return None
    normalized = raw.replace("-", "_").casefold()
    aliases = {
        "reissue": "reissued",
        "reissue_required": "reissued",
        "partial_reissue": "reissued",
        "review": "review_required",
        "human_review": "review_required",
        "withdraw": "withdrawn",
        "supersede": "superseded",
        "invalidate": "invalidated",
        "mark_stale": "stale",
        "marked_stale": "stale",
    }
    resolved = aliases.get(normalized, normalized)
    if resolved not in _VALID_TRANSITIONS:
        raise ValueError(f"unsupported lifecycle transition: {raw!r}")
    return resolved  # type: ignore[return-value]


def _affected_known_claim_ids(
    event: GovernanceMonitorEvent,
    *,
    known_claim_ids: list[str],
) -> list[str]:
    known = set(known_claim_ids)
    return [claim_id for claim_id in _dedupe_texts(event.affected_claim_ids) if claim_id in known]


def _missing_bridge_blocker(
    event: GovernanceMonitorEvent,
    *,
    known_claim_ids: list[str],
    reason: str | None = None,
) -> LifecycleBridgeBlocker:
    raw_claim_ids = _dedupe_texts(event.affected_claim_ids)
    unknown_claim_ids = sorted(set(raw_claim_ids).difference(known_claim_ids))
    return LifecycleBridgeBlocker(
        event_id=event.event_id,
        event_type=event.event_type,
        severity=event.severity,
        affected_claim_ids=raw_claim_ids,
        reason=reason
        or (
            "Detector event did not map to any closed-case claim lifecycle transition."
        ),
        metadata={
            "monitor_event_reason": event.reason,
            "known_claim_ids": known_claim_ids,
            "unknown_claim_ids": unknown_claim_ids,
        },
    )


def _claim_lifecycle_event(
    event: GovernanceMonitorEvent,
    *,
    run_id: str,
    claim_id: str,
    transition: ClaimLifecycleTransition,
    actor_id: str,
    occurred_at: datetime,
    sequence: int,
) -> ClaimLifecycleEvent:
    action = _TRANSITION_TO_ACTION[transition]
    metadata = {
        "continuous_governance_bridge": "w9e",
        "monitor_event_id": event.event_id,
        "monitor_event_type": event.event_type,
        "monitor_event_severity": event.severity,
        "lifecycle_transition": transition,
        "public_revision_status": _public_status_for_transition(transition),
        "scope": dict(event.scope),
        "event_metadata": dict(event.metadata),
        "authority_boundary": lifecycle_bridge_authority_boundary(),
    }
    superseded_by = _superseded_by_claim_id(event)
    if superseded_by is not None:
        metadata["superseded_by_claim_id"] = superseded_by

    return ClaimLifecycleEvent(
        event_id=lifecycle_event_id(
            run_id=run_id,
            claim_id=claim_id,
            action=action,
            actor_id=actor_id,
            reason=event.reason,
            sequence=sequence,
        ),
        claim_id=claim_id,
        run_id=run_id,
        action=action,
        occurred_at=occurred_at,
        actor_id=actor_id,
        reason=event.reason,
        metadata=metadata,
    )


def _build_public_revision_state(
    *,
    case_id: str | None,
    claim_ids: list[str],
    transitions: list[ClaimLifecycleTransitionRecord],
    blockers: list[LifecycleBridgeBlocker],
    generated_at: datetime,
) -> PartialPublicationState:
    strongest_by_claim: dict[str, ClaimLifecycleTransitionRecord] = {}
    for record in transitions:
        existing = strongest_by_claim.get(record.claim_id)
        if existing is None or _transition_rank(record.transition) > _transition_rank(
            existing.transition
        ):
            strongest_by_claim[record.claim_id] = record

    affected_claim_ids = [claim_id for claim_id in claim_ids if claim_id in strongest_by_claim]
    unaffected_claim_ids = [
        claim_id for claim_id in claim_ids if claim_id not in strongest_by_claim
    ]
    public_diffs = [
        PublicRevisionDiff(
            claim_id=claim_id,
            diff_kind=strongest_by_claim[claim_id].transition,
            public_status=strongest_by_claim[claim_id].public_revision_status,
            reason=strongest_by_claim[claim_id].reason,
        )
        for claim_id in affected_claim_ids
    ]
    revalidation_status = _public_revalidation_status(
        [record.transition for record in strongest_by_claim.values()],
        blockers=blockers,
    )
    return PartialPublicationState(
        case_id=case_id,
        generated_at=generated_at.isoformat(),
        current_case_validity=_public_case_validity(
            affected_count=len(affected_claim_ids),
            claim_count=len(claim_ids),
            revalidation_status=revalidation_status,
            blockers=blockers,
        ),
        affected_claim_ids=affected_claim_ids,
        unaffected_claim_ids=unaffected_claim_ids,
        public_diffs=public_diffs,
        public_diff_required=bool(public_diffs),
        revalidation_status=revalidation_status,
    )


def _maybe_build_reissue_packet(
    *,
    original_decision_packet_ref: ArtifactRef,
    original_claim_ledger_ref: ArtifactRef,
    all_claim_ids: list[str],
    monitor_events: list[GovernanceMonitorEvent],
    monitor_event_refs: list[ArtifactRef],
    transitions: list[ClaimLifecycleTransitionRecord],
    new_decision_packet_ref: ArtifactRef | None,
    new_claim_ledger_ref: ArtifactRef | None,
    unchanged_records: list[ArtifactRef] | None,
    superseded_refs: list[ArtifactRef] | None,
    public_diff_refs: list[ArtifactRef] | None,
    reason: str,
    case_id: str | None,
    generated_at: datetime,
    metadata: dict[str, Any] | None,
) -> ReissuePacket | None:
    if not any(record.transition == "reissued" for record in transitions):
        return None
    if new_decision_packet_ref is None or new_claim_ledger_ref is None:
        raise ValueError("reissued lifecycle bridge results require new decision and ledger refs")
    reissued_event_ids = {
        record.event_id for record in transitions if record.transition == "reissued"
    }
    reissued_events: list[GovernanceMonitorEvent] = []
    reissued_event_refs: list[ArtifactRef] = []
    for index, event in enumerate(monitor_events):
        if event.event_id not in reissued_event_ids:
            continue
        reissued_events.append(event)
        reissued_event_refs.append(monitor_event_refs[index])
    return build_partial_scope_reissue_packet(
        original_decision_packet_ref=original_decision_packet_ref,
        original_claim_ledger_ref=original_claim_ledger_ref,
        all_claim_ids=all_claim_ids,
        monitor_events=reissued_events,
        monitor_event_refs=reissued_event_refs,
        reason=reason,
        new_decision_packet_ref=new_decision_packet_ref,
        new_claim_ledger_ref=new_claim_ledger_ref,
        unchanged_records=unchanged_records,
        superseded_refs=superseded_refs,
        public_diff_refs=public_diff_refs,
        status=DecisionValidityStatus.REISSUED,
        metadata={
            "lifecycle_bridge_component": _BRIDGE_COMPONENT,
            "lifecycle_bridge_version": _BRIDGE_VERSION,
            **(metadata or {}),
        },
        case_id=case_id,
        generated_at=generated_at,
    )


def _bridge_id(
    *,
    decision_packet_ref: ArtifactRef,
    monitor_events: list[GovernanceMonitorEvent],
) -> str:
    event_ids = ".".join(event.event_id for event in monitor_events) or "no-events"
    return f"lifecycle_bridge:{decision_packet_ref.artifact_id}:{event_ids}"


def _result_reason(
    transitions: list[ClaimLifecycleTransitionRecord],
    blockers: list[LifecycleBridgeBlocker],
) -> str:
    if transitions:
        return "; ".join(_dedupe_texts(record.reason for record in transitions))
    if blockers:
        return "; ".join(_dedupe_texts(blocker.reason for blocker in blockers))
    return "No lifecycle transition required."


def _public_case_validity(
    *,
    affected_count: int,
    claim_count: int,
    revalidation_status: str,
    blockers: list[LifecycleBridgeBlocker],
) -> str:
    if affected_count == 0:
        return "review_required" if blockers else "current"
    if affected_count < claim_count:
        return "partially_current"
    return revalidation_status


def _public_revalidation_status(
    transitions: Iterable[ClaimLifecycleTransition],
    *,
    blockers: list[LifecycleBridgeBlocker],
) -> Literal["current", "review_required", "revalidation_required", "superseded", "withdrawn"]:
    if blockers:
        return "review_required"
    strongest = "current"
    rank = 0
    for transition in transitions:
        status = _REVALIDATION_STATUS_BY_TRANSITION[transition]
        status_rank = {
            "current": 0,
            "review_required": 1,
            "revalidation_required": 2,
            "superseded": 3,
            "withdrawn": 4,
        }[status]
        if status_rank > rank:
            strongest = status
            rank = status_rank
    return strongest  # type: ignore[return-value]


def _public_status_for_transition(transition: ClaimLifecycleTransition) -> str:
    return transition


def _transition_rank(transition: ClaimLifecycleTransition) -> int:
    return {
        "review_required": 1,
        "stale": 2,
        "blocked": 3,
        "invalidated": 4,
        "reissued": 5,
        "superseded": 6,
        "withdrawn": 7,
    }[transition]


def _superseded_by_claim_id(event: GovernanceMonitorEvent) -> str | None:
    return _metadata_text(event.metadata, "superseded_by_claim_id") or _metadata_text(
        event.metadata,
        "successor_claim_id",
    )


def _metadata_text(metadata: Mapping[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dedupe_texts(values: Iterable[object] | object | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        iterable: Iterable[object] = [values]
    elif isinstance(values, Iterable):
        iterable = values
    else:
        iterable = [values]
    deduped: list[str] = []
    seen: set[str] = set()
    for value in iterable:
        text = str(value).strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


__all__ = [
    "LIFECYCLE_BRIDGE_RESULT_KIND",
    "LIFECYCLE_BRIDGE_RESULT_SCHEMA_NAME",
    "LIFECYCLE_BRIDGE_RESULT_SCHEMA_VERSION",
    "ClaimLifecycleTransition",
    "ClaimLifecycleTransitionRecord",
    "LifecycleBridgeBlocker",
    "LifecycleBridgeResult",
    "LifecycleBridgeStatus",
    "bridge_governance_events_to_claim_lifecycle",
    "lifecycle_bridge_authority_boundary",
    "lifecycle_bridge_capability_reality",
    "lifecycle_bridge_result_inputs",
    "load_lifecycle_bridge_result",
    "persist_lifecycle_bridge_result",
]
