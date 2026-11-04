"""Candidate terminal crash recovery through the real event and SQL owners.

Candidate evaluation/history semantics are adapted in this component fixture;
the selected parent bytes are not a genuine N5 or protected candidate route.
The durable marker, receipt writer, event, action head, job lease and frontier
transaction are real.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from polisyos.core.artifacts import ArtifactWriteOptions, FileSystemCAS, ProducerInfo
from polisyos.runtime.http.services.control.run_lifecycle import AcquisitionRouteLoopAuthoritySink
from polisyos.runtime.http.services.control_plane_store import (
    AcquisitionEvaluationFrontierCAS,
    AcquisitionEvaluationFrontierValue,
    ControlPlaneStore,
)
from polisyos.runtime.quality import acquisition_evaluation_dispatch as dispatch
from polisyos.runtime.quality import acquisition_evaluation_history as history
from polisyos.runtime.quality.acquisition_evaluation import AcquisitionSelectedEvaluation
from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
    CandidateAcquisitionEvaluationReentryOwner,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateRouteLoopReceipt,
    AcquisitionRoutePhaseReceipt,
)
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.generation_cycle import JointSimulationPort
from tests._helpers.candidate_terminal_recovery import candidate_terminal_writer_inputs
from tests.unit.runtime.http.test_control_plane_store_evaluation_frontier import (
    _bootstrap,
    _create_action_job,
    _sha,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.joint_simulation_horizon import (
        PreparedJointSimulationConfiguration,
    )


def test_complete_marker_recovers_event_and_atomic_sql_without_n5(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stale frontier leaves the event recoverable, then commits its exact view once."""
    db = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    _, prior_frontier, _ = _bootstrap(db, tmp_path)
    job, worker, attempt = _create_action_job(db, job_id="candidate-action")
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    events = RuntimeDiagnosticEventLog(store=db, artifact_store=store)
    sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=store, event_log=events, control_store=db
    )

    def parent(kind: str, label: str) -> ArtifactRef:
        return store.put_json(
            {"controlled_parent": label},
            ArtifactWriteOptions(
                kind=kind,
                media_type="application/json",
                producer=ProducerInfo(component="test.candidate-terminal-parent", version="1"),
            ),
            return_selected_profile=True,
        )

    action_ref = parent("runtime_quality.acquisition_candidate_action_receipt", "action")
    intent_ref = parent("runtime_quality.acquisition_candidate_world_intent", "intent")
    decision_ref = parent("runtime_quality.acquisition_evaluation_decision", "decision")
    basis_ref = parent("runtime_quality.acquisition_evaluation_basis", "basis")
    reentry_ref = parent("runtime_quality.candidate_source_reentry_receipt", "reentry")
    execution_ref = parent("runtime.quality.candidate_simulation_execution", "execution")
    evaluation = AcquisitionSelectedEvaluation(
        candidate_id=prior_frontier.key.candidate_id,
        candidate_content_hash=_sha("candidate-content"),
        design_problem_ref=prior_frontier.key.design_problem_ref,
        world_model_record_hash=_sha("world"),
        evaluation_job_id=job.job_id,
        evaluation_run_id="run-a",
        generation_run_id="controlled-generation",
        cycle_index=0,
        n4_source_ref=parent("runtime.quality.n4_candidate_scenario_source", "n4"),
        context_job_ref=parent("runtime.quality.cycle_substrate_context_job", "context"),
        n5_input_ref=parent("runtime.quality.candidate_simulation_n5_input", "n5-input"),
        n5_execution_ref=execution_ref,
        n5_result_ref=parent("polisyos.runtime.joint_simulation_result", "n5-result"),
        basis_ref=basis_ref,
    )
    monkeypatch.setattr(
        AcquisitionRouteLoopAuthoritySink,
        "_verified_current_action_outcome_ref",
        lambda _self, _executing, _ref, refs, **_kwargs: refs[0],
    )
    monkeypatch.setattr(
        AcquisitionRouteLoopAuthoritySink,
        "_require_candidate_terminal_history_owner",
        lambda *_: None,
    )
    monkeypatch.setattr(
        AcquisitionRouteLoopAuthoritySink, "_verify_candidate_reentry_terminal", lambda *_: None
    )
    monkeypatch.setattr(history, "verify_candidate_terminal_history", lambda **_: object())

    def no_n5(*_args: object, **_kwargs: object) -> object:
        pytest.fail("terminal recovery must not run N5")

    monkeypatch.setattr(JointSimulationPort, "__call__", no_n5)
    common = {
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "run_id": "run-a",
        "source_job_id": "source-nl",
        "route_id": _sha("route"),
        "action_generation": 1,
        "job_id": job.job_id,
        "compiled_ref": _sha("compiled"),
        "planner_report_hash": _sha("planner"),
        "cost_basis_hash": _sha("cost"),
        "decision_ref": _sha("route-decision"),
    }
    with db.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        requested = AcquisitionRoutePhaseReceipt(
            **common,
            receipt_id="candidate.requested",
            coarse_phase="requested",
            receipt_phase="requested",
            recovery_state="none",
            generated_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        first = sink.persist_phase(requested)
        executing = requested.model_copy(
            update={
                "receipt_id": "candidate.executing",
                "coarse_phase": "executing",
                "receipt_phase": "executing",
                "predecessor_receipt_ref": first.receipt_ref,
            }
        )
        second = sink.persist_phase(executing)
        selected = sink.persist_action_outcome_selection(
            second.receipt_ref, (str(action_ref.artifact_id),), candidate_receipt_ref=action_ref
        )
        pending = AcquisitionRoutePhaseReceipt(
            **common,
            schema_version="AcquisitionRoutePhaseReceipt@1.2",
            receipt_id="candidate.pending",
            coarse_phase="candidate_input_prepared",
            receipt_phase="candidate_input_reentry_pending",
            recovery_state="reentry_recovery_required",
            predecessor_receipt_ref=selected.receipt_ref,
            owner_receipt_refs=(str(action_ref.artifact_id),),
            candidate_receipt_ref=action_ref,
            generated_at=datetime.now(UTC) + timedelta(seconds=1),
        )
        pending_head = sink.persist_phase(pending)
        terminal = AcquisitionCandidateRouteLoopReceipt(
            **common,
            receipt_id="candidate.terminal",
            terminal_outcome="candidate_reentry_completed",
            predecessor_receipt_ref=pending_head.receipt_ref,
            owner_receipt_refs=(str(action_ref.artifact_id), str(decision_ref.artifact_id)),
            candidate_action_ref=action_ref,
            candidate_reentry_ref=reentry_ref,
            evaluation_decision_ref=decision_ref,
            selected_basis_ref=basis_ref,
            selected_evaluation_witness_ref=execution_ref,
            selected_evaluation=evaluation,
            generated_at=pending.generated_at + timedelta(seconds=1),
        )
        bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
        bridge.artifact_store = store
        bridge.control_store = db
        bridge.event_log = events
        monkeypatch.setattr(bridge, "candidate_source_selection", lambda _closure: object())
        monkeypatch.setattr(
            bridge, "_paths", lambda *_args, **_kwargs: (tmp_path / "overlay", None)
        )
        owner = CandidateAcquisitionEvaluationReentryOwner(
            bridge=bridge,
            closure=SimpleNamespace(),
            candidate_action_ref=action_ref,
            candidate_world_intent_ref=intent_ref,
            current_basis_ref=basis_ref,
            decision_ref=decision_ref,
            prior=None,
            prepared_n5_configuration=cast("PreparedJointSimulationConfiguration", None),
        )
        marker = dispatch._candidate_terminal_marker(owner)
        dispatch._write_candidate_terminal_intent(marker, terminal)
        _, event_fields = candidate_terminal_writer_inputs(terminal)
        assert events.list_events(event_id=event_fields["event_id"], limit=2) == []
        saved = dispatch._candidate_terminal_intent_for_publication(
            marker=marker, expected=terminal, event_log=events, sink=sink
        )
        replacement = AcquisitionEvaluationFrontierValue(
            selected_evaluation_witness_ref=str(execution_ref.artifact_id),
            selected_evaluation_content_hash=_sha("controlled-execution-content"),
            basis_ref=str(basis_ref.artifact_id),
            basis_content_hash=_sha("controlled-basis-content"),
            decision_ref=str(decision_ref.artifact_id),
        )
        correct = AcquisitionEvaluationFrontierCAS(
            key=prior_frontier.key,
            expected_revision=prior_frontier.revision,
            expected_frontier_ref=prior_frontier.frontier_ref,
            replacement=replacement,
        )
        stale = AcquisitionEvaluationFrontierCAS(
            key=prior_frontier.key,
            expected_revision=prior_frontier.revision + 1,
            expected_frontier_ref=prior_frontier.frontier_ref,
            replacement=replacement,
        )
        selected_cas = [stale]
        monkeypatch.setattr(
            dispatch, "candidate_terminal_frontier_cas", lambda *_a, **_k: selected_cas[0]
        )
        with dispatch._candidate_terminal_scope(dispatch._CandidateTerminalScope(owner, saved)):
            with pytest.raises(ValueError, match="acquisition_evaluation_frontier_conflict"):
                sink.persist_terminal(saved)
            assert sink.get_head(saved) == pending_head
            assert db.read_acquisition_evaluation_frontier(prior_frontier.key) == prior_frontier
            assert len(events.list_events(event_id=event_fields["event_id"], limit=2)) == 1
            selected_cas[0] = correct
            committed = sink.persist_terminal(saved)
        assert committed.head_generation == pending_head.head_generation + 1
        assert committed.receipt_manifest_profile_sha256 is not None
        assert committed.evaluation_frontier_before_ref == prior_frontier.frontier_ref
        frontier = db.read_acquisition_evaluation_frontier(prior_frontier.key)
        assert frontier is not None and frontier.revision == prior_frontier.revision + 1
        assert frontier.frontier_ref == committed.evaluation_frontier_ref
        assert sink.verify_action_head(committed).latest_receipt == saved
        assert len(events.list_events(event_id=event_fields["event_id"], limit=2)) == 1
        assert dispatch._read_candidate_terminal_intent(marker) == terminal
