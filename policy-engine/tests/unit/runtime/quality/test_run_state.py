# ruff: noqa: S101

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from polisyos.runtime.quality.phase_barriers import (
    PhaseBarrierId,
    PhaseBarrierLedger,
    PhaseBarrierRecord,
    assert_barrier_closed,
)
from polisyos.runtime.quality.run_state import (
    RunIntentBinding,
    RunState,
    RunStateMachine,
    RunStateSnapshot,
    RunStateTransitionError,
    assert_final_decision_artifact_allowed,
)

if TYPE_CHECKING:
    from pathlib import Path


def _cas(char: str) -> str:
    return "cas://sha256/" + char * 64


def _intent_binding() -> RunIntentBinding:
    return RunIntentBinding(
        run_id="run_serious_1",
        tenant_id="tenant_a",
        requested_profile="production",
        policy_intent_ref=_cas("1"),
        time_context_ref=_cas("2"),
        same_input_closure_ref=_cas("3"),
    )


def _snapshot(state: RunState = RunState.EVIDENCE_EMITTING) -> RunStateSnapshot:
    return RunStateSnapshot(
        run_id="run_serious_1",
        tenant_id="tenant_a",
        requested_profile="production",
        state=state,
        intent_binding=_intent_binding(),
    )


def _passed_barrier(barrier_id: PhaseBarrierId) -> PhaseBarrierRecord:
    return PhaseBarrierRecord.pass_record(
        barrier_id=barrier_id,
        run_id="run_serious_1",
        tenant_id="tenant_a",
        profile="production",
        evidence_refs=(f"event://diagnostic/{barrier_id.value}", _cas("a")),
    )


def _scorecard_ready_barriers() -> tuple[PhaseBarrierRecord, ...]:
    return tuple(_passed_barrier(barrier_id) for barrier_id in PhaseBarrierId.scorecard_required())


def test_run_authority_states_exclude_projection_only_states() -> None:
    assert {state.value for state in RunState} == {
        "initialized",
        "intent_bound",
        "evidence_emitting",
        "blocked",
        "ready_for_scorecard",
        "scored",
        "readiness_closed",
        "approved",
        "rejected",
        "published_blocked",
    }

    with pytest.raises(ValueError, match="approval_ready"):
        RunState("approval_ready")
    with pytest.raises(ValueError, match="published"):
        RunState("published")


def test_invalid_transition_fails_closed_before_scorecard() -> None:
    machine = RunStateMachine(
        RunStateSnapshot(
            run_id="run_serious_1",
            tenant_id="tenant_a",
            requested_profile="production",
            state=RunState.INITIALIZED,
        )
    )

    with pytest.raises(RunStateTransitionError) as error:
        machine.transition_to(
            RunState.READY_FOR_SCORECARD,
            barriers=_scorecard_ready_barriers(),
        )

    assert error.value.code == "run_state_transition_invalid"


def test_intent_binding_requires_same_input_closure_before_intent_bound() -> None:
    machine = RunStateMachine(
        RunStateSnapshot(
            run_id="run_serious_1",
            tenant_id="tenant_a",
            requested_profile="production",
            state=RunState.INITIALIZED,
        )
    )
    incomplete = RunIntentBinding(
        run_id="run_serious_1",
        tenant_id="tenant_a",
        requested_profile="production",
        policy_intent_ref=_cas("1"),
        time_context_ref=_cas("2"),
        same_input_closure_ref=None,
    )

    with pytest.raises(RunStateTransitionError) as error:
        machine.transition_to(RunState.INTENT_BOUND, intent_binding=incomplete)

    assert error.value.code == "run_intent_binding_incomplete"
    assert error.value.field == "same_input_closure_ref"


def test_missing_phase_barrier_record_blocks_scorecard_readiness() -> None:
    barriers = tuple(
        barrier
        for barrier in _scorecard_ready_barriers()
        if barrier.barrier_id is not PhaseBarrierId.RUNTIME_REFS_FOR_SCORECARD
    )
    machine = RunStateMachine(_snapshot())

    with pytest.raises(RunStateTransitionError) as error:
        machine.transition_to(RunState.READY_FOR_SCORECARD, barriers=barriers)

    assert error.value.code == "phase_barrier_missing"
    assert error.value.barrier_id == PhaseBarrierId.RUNTIME_REFS_FOR_SCORECARD.value


def test_skipped_phase_barrier_does_not_satisfy_serious_closeout() -> None:
    skipped = PhaseBarrierRecord.skipped_record(
        barrier_id=PhaseBarrierId.LEX_LEGAL_COMPATIBILITY,
        run_id="run_serious_1",
        tenant_id="tenant_a",
        profile="production",
        reason="lex retrieval shortcut in fixture",
    )

    with pytest.raises(RunStateTransitionError) as error:
        assert_barrier_closed(
            PhaseBarrierId.LEX_LEGAL_COMPATIBILITY,
            barriers=(skipped,),
        )

    assert error.value.code == "phase_barrier_skipped"
    assert error.value.barrier_id == PhaseBarrierId.LEX_LEGAL_COMPATIBILITY.value


def test_too_early_final_artifact_compilation_is_blocked() -> None:
    snapshot = _snapshot(state=RunState.READY_FOR_SCORECARD)

    with pytest.raises(RunStateTransitionError) as error:
        assert_final_decision_artifact_allowed(
            snapshot,
            barriers=_scorecard_ready_barriers(),
        )

    assert error.value.code == "final_artifact_compilation_too_early"


def test_phase_barrier_records_are_persisted_as_runtime_ledger(tmp_path: Path) -> None:
    ledger = PhaseBarrierLedger(tmp_path / "phase_barriers.jsonl")
    record = _passed_barrier(PhaseBarrierId.POLICY_INTENT_CANONICALIZATION)

    ledger.append(record)
    reloaded = PhaseBarrierLedger(ledger.path)

    assert reloaded.records_for_run("run_serious_1") == (record,)
    assert (
        reloaded.latest(
            run_id="run_serious_1",
            barrier_id=PhaseBarrierId.POLICY_INTENT_CANONICALIZATION,
        )
        == record
    )
