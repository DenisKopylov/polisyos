"""ADR-0148 serious-run authority state machine."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .phase_barriers import (
    PhaseBarrierId,
    PhaseBarrierRecord,
    PhaseBarrierViolation,
    assert_barrier_passed,
)

if TYPE_CHECKING:
    from collections.abc import Iterable


RunStateTransitionError = PhaseBarrierViolation

SERIOUS_PROFILES = frozenset({"research", "governed", "production"})


class RunState(StrEnum):
    """Authority states accepted by ADR-0148."""

    INITIALIZED = "initialized"
    INTENT_BOUND = "intent_bound"
    EVIDENCE_EMITTING = "evidence_emitting"
    BLOCKED = "blocked"
    READY_FOR_SCORECARD = "ready_for_scorecard"
    SCORED = "scored"
    READINESS_CLOSED = "readiness_closed"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED_BLOCKED = "published_blocked"


TERMINAL_RUN_STATES = frozenset(
    {
        RunState.APPROVED,
        RunState.REJECTED,
        RunState.PUBLISHED_BLOCKED,
    }
)
FAILED_RUN_STATES = frozenset(
    {
        RunState.BLOCKED,
        RunState.REJECTED,
        RunState.PUBLISHED_BLOCKED,
    }
)
VALID_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.INITIALIZED: frozenset({RunState.INTENT_BOUND, RunState.BLOCKED}),
    RunState.INTENT_BOUND: frozenset({RunState.EVIDENCE_EMITTING, RunState.BLOCKED}),
    RunState.EVIDENCE_EMITTING: frozenset(
        {RunState.READY_FOR_SCORECARD, RunState.BLOCKED}
    ),
    RunState.BLOCKED: frozenset({RunState.EVIDENCE_EMITTING}),
    RunState.READY_FOR_SCORECARD: frozenset({RunState.SCORED, RunState.BLOCKED}),
    RunState.SCORED: frozenset({RunState.READINESS_CLOSED, RunState.BLOCKED}),
    RunState.READINESS_CLOSED: frozenset(
        {
            RunState.APPROVED,
            RunState.REJECTED,
            RunState.PUBLISHED_BLOCKED,
        }
    ),
    RunState.APPROVED: frozenset(),
    RunState.REJECTED: frozenset(),
    RunState.PUBLISHED_BLOCKED: frozenset(),
}


class RunIntentBinding(BaseModel):
    """Authority-bearing input identity required before `intent_bound`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    requested_profile: str = Field(min_length=1)
    policy_intent_ref: str | None = None
    time_context_ref: str | None = None
    same_input_closure_ref: str | None = None

    @field_validator("run_id", "tenant_id", "requested_profile")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("policy_intent_ref", "time_context_ref", "same_input_closure_ref")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    def require_complete(self) -> None:
        """Fail closed unless all ADR-0148 intent identity fields are bound."""

        required = {
            "tenant_id": self.tenant_id,
            "requested_profile": self.requested_profile,
            "run_id": self.run_id,
            "policy_intent_ref": self.policy_intent_ref,
            "time_context_ref": self.time_context_ref,
            "same_input_closure_ref": self.same_input_closure_ref,
        }
        for field, value in required.items():
            if value is None or str(value).strip() == "":
                raise RunStateTransitionError(
                    "run_intent_binding_incomplete",
                    f"Intent binding is missing {field}.",
                    field=field,
                )


class RunStateSnapshot(BaseModel):
    """Persistable serious-run state snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    requested_profile: str = Field(min_length=1)
    state: RunState = RunState.INITIALIZED
    intent_binding: RunIntentBinding | None = None
    barrier_ids: tuple[str, ...] = Field(default=())
    blocker_codes: tuple[str, ...] = Field(default=())
    scorecard_identity_ref: str | None = None
    scorecard_identity_verified: bool = False
    readiness_decision: str | None = None
    publication_policy: str | None = None

    @field_validator("run_id", "tenant_id", "requested_profile")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("scorecard_identity_ref", "readiness_decision", "publication_policy")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("barrier_ids", "blocker_codes")
    @classmethod
    def _strip_tuple_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_non_empty(value) for value in values)

    @model_validator(mode="after")
    def _validate_projection_state_names(self) -> Self:
        if self.state.value in {"approval_ready", "published"}:
            raise ValueError(f"{self.state.value} is a projection, not authority state")
        return self

    def with_state(self, state: RunState, **updates: object) -> RunStateSnapshot:
        """Return a copy with an updated state."""

        return self.model_copy(update={"state": state, **updates})


class RunStateMachine:
    """Small fail-closed transition helper for serious runs."""

    def __init__(self, snapshot: RunStateSnapshot) -> None:
        self.snapshot = snapshot

    def transition_to(
        self,
        target: RunState | str,
        *,
        intent_binding: RunIntentBinding | None = None,
        barriers: Iterable[PhaseBarrierRecord] = (),
        scorecard_identity_ref: str | None = None,
        scorecard_identity_verified: bool = False,
        readiness_decision: str | None = None,
        publication_policy: str | None = None,
        blocker_code: str | None = None,
    ) -> RunStateSnapshot:
        """Validate and apply one ADR-0148 state transition."""

        target_state = RunState(target)
        _assert_transition_allowed(self.snapshot.state, target_state)

        if target_state is RunState.INTENT_BOUND:
            binding = intent_binding or self.snapshot.intent_binding
            _assert_binding_matches_snapshot(binding, self.snapshot)
            binding.require_complete()
            self.snapshot = self.snapshot.with_state(
                target_state,
                intent_binding=binding,
            )
            return self.snapshot

        if target_state is RunState.EVIDENCE_EMITTING:
            binding = intent_binding or self.snapshot.intent_binding
            _assert_binding_matches_snapshot(binding, self.snapshot)
            binding.require_complete()
            self.snapshot = self.snapshot.with_state(
                target_state,
                intent_binding=binding,
            )
            return self.snapshot

        if target_state is RunState.READY_FOR_SCORECARD:
            _assert_snapshot_intent_bound(self.snapshot)
            passed = _assert_scorecard_barriers_passed(barriers)
            self.snapshot = self.snapshot.with_state(
                target_state,
                barrier_ids=tuple(record.barrier_id.value for record in passed),
            )
            return self.snapshot

        if target_state is RunState.SCORED:
            _assert_scorecard_identity_verified(
                scorecard_identity_verified=scorecard_identity_verified,
                scorecard_identity_ref=scorecard_identity_ref,
            )
            self.snapshot = self.snapshot.with_state(
                target_state,
                scorecard_identity_ref=scorecard_identity_ref,
                scorecard_identity_verified=True,
            )
            return self.snapshot

        if target_state is RunState.READINESS_CLOSED:
            if not (
                scorecard_identity_verified
                or self.snapshot.scorecard_identity_verified
            ):
                raise RunStateTransitionError(
                    "scorecard_identity_not_verified",
                    "Readiness cannot close before scorecard identity is verified.",
                    barrier_id=PhaseBarrierId.SCORECARD_IDENTITY_VERIFIED.value,
                )
            if readiness_decision is None:
                raise RunStateTransitionError(
                    "readiness_decision_missing",
                    "Readiness closeout requires a persisted readiness decision.",
                    field="readiness_decision",
                )
            self.snapshot = self.snapshot.with_state(
                target_state,
                scorecard_identity_verified=True,
                readiness_decision=readiness_decision,
            )
            return self.snapshot

        if target_state in TERMINAL_RUN_STATES:
            _assert_terminal_projection_allowed(
                target_state,
                readiness_decision=readiness_decision
                or self.snapshot.readiness_decision,
                publication_policy=publication_policy,
            )
            self.snapshot = self.snapshot.with_state(
                target_state,
                readiness_decision=readiness_decision or self.snapshot.readiness_decision,
                publication_policy=publication_policy,
            )
            return self.snapshot

        if target_state is RunState.BLOCKED:
            blockers = self.snapshot.blocker_codes
            if blocker_code is not None:
                blockers = (*blockers, _non_empty(blocker_code))
            self.snapshot = self.snapshot.with_state(target_state, blocker_codes=blockers)
            return self.snapshot

        raise RunStateTransitionError(
            "run_state_transition_guard_missing",
            f"No transition guard implemented for {target_state.value}.",
        )


def assert_final_decision_artifact_allowed(
    snapshot: RunStateSnapshot,
    *,
    barriers: Iterable[PhaseBarrierRecord],
) -> None:
    """Block final artifact compilation until state and barriers permit it."""

    if snapshot.state in {
        RunState.INITIALIZED,
        RunState.INTENT_BOUND,
        RunState.EVIDENCE_EMITTING,
        RunState.READY_FOR_SCORECARD,
    }:
        raise RunStateTransitionError(
            "final_artifact_compilation_too_early",
            "Final decision artifacts require scored readiness authority first.",
            barrier_id=PhaseBarrierId.FINAL_DECISION_ARTIFACT.value,
        )
    if snapshot.state in FAILED_RUN_STATES:
        raise RunStateTransitionError(
            "final_artifact_compilation_blocked",
            f"Final decision artifact compilation is blocked in {snapshot.state.value}.",
            barrier_id=PhaseBarrierId.FINAL_DECISION_ARTIFACT.value,
        )
    for barrier in PhaseBarrierId.final_artifact_required():
        assert_barrier_passed(barrier, barriers=barriers)


def assert_approval_readiness_projection_allowed(snapshot: RunStateSnapshot) -> None:
    """Approval readiness is a projection over verified scorecard identity."""

    if snapshot.state is not RunState.READINESS_CLOSED:
        raise RunStateTransitionError(
            "approval_readiness_projection_too_early",
            "Approval readiness requires readiness_closed authority state.",
        )
    if not snapshot.scorecard_identity_verified:
        raise RunStateTransitionError(
            "scorecard_identity_not_verified",
            "Approval readiness requires verified scorecard identity.",
            barrier_id=PhaseBarrierId.SCORECARD_IDENTITY_VERIFIED.value,
        )


def assert_public_artifact_allowed(
    snapshot: RunStateSnapshot,
    *,
    barriers: Iterable[PhaseBarrierRecord],
) -> None:
    """Public/exportable artifacts require approval plus compiler gates."""

    if snapshot.state is not RunState.APPROVED:
        raise RunStateTransitionError(
            "public_artifact_not_approved",
            "Public artifacts require approved runtime authority state.",
            barrier_id=PhaseBarrierId.FINAL_COMPILER_GATES.value,
        )
    for barrier in PhaseBarrierId.public_artifact_required():
        assert_barrier_passed(barrier, barriers=barriers)


def assert_canary_bundle_closeout_allowed(
    snapshot: RunStateSnapshot,
    *,
    barriers: Iterable[PhaseBarrierRecord],
) -> None:
    """Canary bundles can preserve runtime truth but cannot mint closeout authority."""

    if snapshot.state in FAILED_RUN_STATES:
        raise RunStateTransitionError(
            "canary_bundle_closeout_state_blocked",
            f"Canary bundle closeout cannot upgrade {snapshot.state.value}.",
            barrier_id=PhaseBarrierId.CANARY_BUNDLE_CLOSEOUT.value,
        )
    assert_barrier_passed(PhaseBarrierId.CANARY_BUNDLE_CLOSEOUT, barriers=barriers)


def _assert_scorecard_barriers_passed(
    barriers: Iterable[PhaseBarrierRecord],
) -> tuple[PhaseBarrierRecord, ...]:
    records = tuple(barriers)
    return tuple(
        assert_barrier_passed(barrier_id, barriers=records)
        for barrier_id in PhaseBarrierId.scorecard_required()
    )


def _assert_transition_allowed(current: RunState, target: RunState) -> None:
    if target not in VALID_TRANSITIONS[current]:
        raise RunStateTransitionError(
            "run_state_transition_invalid",
            f"Cannot transition from {current.value} to {target.value}.",
        )


def _assert_binding_matches_snapshot(
    binding: RunIntentBinding | None,
    snapshot: RunStateSnapshot,
) -> RunIntentBinding:
    if binding is None:
        raise RunStateTransitionError(
            "run_intent_binding_missing",
            "Intent binding is required before evidence or scorecard authority.",
            field="intent_binding",
        )
    if binding.run_id != snapshot.run_id:
        raise RunStateTransitionError(
            "run_intent_binding_run_mismatch",
            "Intent binding run_id does not match state snapshot.",
            field="run_id",
        )
    if binding.tenant_id != snapshot.tenant_id:
        raise RunStateTransitionError(
            "run_intent_binding_tenant_mismatch",
            "Intent binding tenant_id does not match state snapshot.",
            field="tenant_id",
        )
    if binding.requested_profile != snapshot.requested_profile:
        raise RunStateTransitionError(
            "run_intent_binding_profile_mismatch",
            "Intent binding requested_profile does not match state snapshot.",
            field="requested_profile",
        )
    return binding


def _assert_snapshot_intent_bound(snapshot: RunStateSnapshot) -> None:
    binding = _assert_binding_matches_snapshot(snapshot.intent_binding, snapshot)
    binding.require_complete()


def _assert_scorecard_identity_verified(
    *,
    scorecard_identity_verified: bool,
    scorecard_identity_ref: str | None,
) -> None:
    if not scorecard_identity_verified:
        raise RunStateTransitionError(
            "scorecard_identity_not_verified",
            "Scored state requires verified scorecard ref and payload identity.",
            barrier_id=PhaseBarrierId.SCORECARD_IDENTITY_VERIFIED.value,
        )
    if scorecard_identity_ref is None or not scorecard_identity_ref.strip():
        raise RunStateTransitionError(
            "scorecard_identity_ref_missing",
            "Scored state requires a persisted scorecard identity ref.",
            field="scorecard_identity_ref",
        )


def _assert_terminal_projection_allowed(
    target_state: RunState,
    *,
    readiness_decision: str | None,
    publication_policy: str | None,
) -> None:
    normalized = (readiness_decision or "").strip().casefold()
    if target_state is RunState.APPROVED and normalized not in {"accepted", "approved"}:
        raise RunStateTransitionError(
            "terminal_projection_readiness_mismatch",
            "Approved authority requires accepted readiness decision.",
            field="readiness_decision",
        )
    if target_state is RunState.REJECTED and normalized != "rejected":
        raise RunStateTransitionError(
            "terminal_projection_readiness_mismatch",
            "Rejected authority requires rejected readiness decision.",
            field="readiness_decision",
        )
    if target_state is RunState.PUBLISHED_BLOCKED:
        policy = (publication_policy or "").strip().casefold()
        if normalized not in {
            "blocked",
            "publication_blocked",
            "publish_blocked",
        } and policy not in {
            "blocked",
            "not_public_exportable",
            "publish_blocked",
        }:
            raise RunStateTransitionError(
                "terminal_projection_readiness_mismatch",
                "published_blocked requires readiness or publication policy blocker.",
                field="publication_policy",
            )


def _non_empty(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("value must be non-empty")
    return text


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


__all__ = [
    "FAILED_RUN_STATES",
    "TERMINAL_RUN_STATES",
    "VALID_TRANSITIONS",
    "RunIntentBinding",
    "RunState",
    "RunStateMachine",
    "RunStateSnapshot",
    "RunStateTransitionError",
    "assert_approval_readiness_projection_allowed",
    "assert_canary_bundle_closeout_allowed",
    "assert_final_decision_artifact_allowed",
    "assert_public_artifact_allowed",
]
