"""Acquisition completion relay and real SQL atomicity, with replay isolated.

The selected-record fixture is deliberately unreplayed. Canonical producer,
signed PA2 and numerical retention are not established by these seam tests;
the served model-input-use integration exercises those owners together.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.runtime.http.services import control_plane_store as store_module
from polisyos.runtime.http.services import model_input_successor_action as model_owner
from polisyos.runtime.http.services.acquisition_action_service import AcquisitionActionService
from polisyos.runtime.http.services.control.job_diagnostics import (
    _closed_native_model_input_use_checkpoint,
    _failed_native_model_input_use_stage,
    _ModelInputUseJobCompletion,
    _verify_native_model_input_use_completed_work,
)
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobLeaseLostError,
    ControlPlaneStore,
)
from polisyos.runtime.quality.agent_action_authority import MODEL_INPUT_USE_ACTION_KIND
from tests.unit.runtime.http.services.test_acquisition_action_service import (
    _install_model_input_completion_producer,
    _model_input_completion_case,
)
from tests.unit.runtime.http.services.test_acquisition_admission_bundle import (
    _model_input_use_request,
    _selected_ref,
)
from tests.unit.runtime.http.test_control_plane_store_evaluation_frontier import (
    _prepare_generic_comparison,
)


def _complete(case: SimpleNamespace) -> None:
    admission = case.database.current_execution_job_admission()
    case.control._complete_acquisition_control_job(
        job=admission.job,
        payload={"action_kind": MODEL_INPUT_USE_ACTION_KIND},
        execution_scope=admission.scope,
        capability_manifest_ref=admission.job.capability_manifest_ref,
    )


def _native_request() -> model_owner.NativeModelInputSuccessorActionRequest:
    return model_owner.NativeModelInputSuccessorActionRequest.model_validate(
        {
            **_model_input_use_request().model_dump(mode="json"),
            "native_use": {
                "predecessor_terminal_ref": _selected_ref(
                    "runtime_quality.acquisition_route_loop_receipt", 5
                ),
                "world_checkpoint_ref": _selected_ref(
                    "runtime_quality.acquisition_candidate_world_checkpoint", 6
                ),
                "fresh_budget_usd": "0.50",
            },
        }
    )


def _install_reconciler(
    case: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    *,
    after_replay: Any = None,
) -> list[str]:
    calls = _install_model_input_completion_producer(case, monkeypatch)

    def replay(control: Any, **kwargs: Any) -> Any:
        assert control is case.control
        assert kwargs["selection"] is case.selection
        assert kwargs["checkpoint"] is case.checkpoint
        admission = case.database.current_execution_job_admission()
        assert kwargs["action_payload_ref"] == admission.job.payload_ref
        assert kwargs["authority_decision_ref"] == str(
            case.cas.decision.authority_decision_ref.artifact_id
        )
        calls.append("prepare")
        if after_replay is not None:
            after_replay()
        return case.cas

    monkeypatch.setattr(model_owner, "prepare_model_input_use_frontier_completion", replay)
    # The transactional job event/outbox remain real. This separate, later
    # observational diagnostic is isolated from its authority-artifact writer.
    monkeypatch.setattr(
        type(case.control), "_emit_runtime_diagnostic_event", lambda *_a, **_k: None
    )
    return calls


def _assert_not_completed(case: SimpleNamespace) -> None:
    assert case.database.get_job(case.job.job_id).state == "running"
    assert "completed" not in case.database.list_job_state_transitions(case.job.job_id)
    assert not any(
        row.job_id == case.job.job_id and row.topic == "control.job.completed"
        for row in case.database.list_outbox_events(state=None, limit=500)
    )
    assert (
        case.database.get_generic_model_input_use(key=case.key, action_job_id=case.job.job_id)
        is None
    )


def _comparison(case: SimpleNamespace, tmp_path: Path, result: str, **kwargs: Any) -> Any:
    with case.database.job_execution_fence(
        job_id=case.job.job_id, worker_id=case.worker, attempt=case.attempt
    ):
        case.database.complete_job(
            job_id=case.job.job_id,
            run_id="run-a",
            progress={},
            generic_model_input_frontier_cas=case.cas,
        )
    initial = case.database.read_generic_model_input_frontier(case.key)
    bundle = _prepare_generic_comparison(
        case.database,
        tmp_path,
        source_job_id=case.source.job_id,
        prior=initial,
        action_job_id="comparison-action",
        result=result,
        **kwargs,
    )
    case.job, case.worker, case.attempt = bundle[:3]
    case.cas = bundle[7]
    case.selection = replace(
        case.selection, job_id=case.job.job_id, route_id=case.cas.decision.route_id
    )
    evaluation = (
        case.cas.replacement.selected_evaluation if case.cas.replacement is not None else None
    )
    case.checkpoint = model_owner.ModelInputUseActionCheckpoint(
        schema_version="polisyos.runtime.ModelInputUseActionCheckpoint@2.0",
        phase_ref=case.cas.decision.action_phase_ref,
        semantic_successor_ref=case.cas.decision.semantic_successor_ref,
        execution_ref=evaluation.execution_ref if evaluation is not None else None,
        result_ref=evaluation.result_ref if evaluation is not None else None,
        evaluation_decision_ref=case.cas.decision_ref,
        evaluation_current_basis_ref=case.cas.decision.current_basis_ref,
        evaluation_replacement_basis_ref=(
            case.cas.replacement.basis_ref if case.cas.replacement is not None else None
        ),
    )
    return initial


@pytest.mark.parametrize("comparison", [None, "equivalent", "different"])
def test_completion_replays_then_atomically_commits_use_and_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, comparison: str | None
) -> None:
    case = _model_input_completion_case(tmp_path)
    prior = _comparison(case, tmp_path, comparison) if comparison else None
    calls = _install_reconciler(case, monkeypatch)
    with case.database.job_execution_fence(
        job_id=case.job.job_id, worker_id=case.worker, attempt=case.attempt
    ):
        _complete(case)
    final = case.database.get_job(case.job.job_id)
    use = case.database.get_generic_model_input_use(key=case.key, action_job_id=case.job.job_id)
    frontier = case.database.read_generic_model_input_frontier(case.key)
    assert final.state == "completed" and use is not None
    assert calls[-2:] == ["prepare", "worker"]
    snapshot = final.progress["generic_model_input_current_use"]
    terminal = case.database.get_job_terminal_source_event_record(case.job.job_id)
    outbox = next(
        row
        for row in case.database.list_outbox_events(state=None, limit=500)
        if row.job_id == case.job.job_id and row.topic == "control.job.completed"
    )
    assert terminal.payload["generic_model_input_current_use"] == snapshot
    assert outbox.payload["generic_model_input_current_use"] == snapshot
    assert snapshot["action_job_id"] == case.job.job_id
    assert snapshot["frontier_ref"] == frontier.frontier_ref
    if comparison == "equivalent":
        assert frontier == prior
        assert case.checkpoint.execution_ref is None
        assert final.progress["terminal_receipt_ref"] == str(case.cas.decision_ref.artifact_id)
    else:
        assert frontier.selected_evaluation.action_job_id == case.job.job_id
    assert "generic_model_input_frontier_cas" not in final.progress


@pytest.mark.parametrize(
    "marker",
    ["generic_model_input_current_use", "generic_model_input_frontier_cas", "model_input_use"],
)
def test_plain_progress_cannot_claim_owner_verified_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, marker: str
) -> None:
    case = _model_input_completion_case(tmp_path)
    value = (
        case.checkpoint.model_dump(mode="json", exclude_none=True)
        if marker == "model_input_use"
        else {}
    )
    monkeypatch.setattr(
        AcquisitionActionService, "_handle_model_input_use_job", lambda *_a, **_k: {marker: value}
    )
    with (
        case.database.job_execution_fence(
            job_id=case.job.job_id, worker_id=case.worker, attempt=case.attempt
        ),
        pytest.raises(ValueError, match="model_input_use_completion_"),
    ):
        _complete(case)
    _assert_not_completed(case)


@pytest.mark.parametrize(
    "fault",
    [
        "replay_refused",
        "missing_reconciler_result",
        "current_authority_changed",
        "progress_mismatch",
        "foreign_handler",
        "same_owner_foreign_handler",
        "spoofed_canonical_handler",
    ],
)
def test_completion_carrier_is_not_constructor_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    case = _model_input_completion_case(tmp_path)
    calls = _install_reconciler(case, monkeypatch)
    if fault == "replay_refused":

        def refuse(*_args: Any, **_kwargs: Any) -> Any:
            raise model_owner.ModelInputSuccessorActionError("selected_owner_replay_refused")

        monkeypatch.setattr(model_owner, "prepare_model_input_use_frontier_completion", refuse)
    elif fault == "missing_reconciler_result":
        monkeypatch.setattr(
            model_owner, "prepare_model_input_use_frontier_completion", lambda *_a, **_k: None
        )
    elif fault == "current_authority_changed":

        def changed() -> None:
            case.selection = replace(
                case.selection, observation_content_sha256="sha256:" + "b" * 64
            )

        calls = _install_reconciler(case, monkeypatch, after_replay=changed)
    elif fault == "progress_mismatch":
        from polisyos.runtime.http.services import acquisition_action_service as action_module

        canonical = action_module.model_input_use_terminal_progress
        monkeypatch.setattr(
            action_module,
            "model_input_use_terminal_progress",
            lambda cp: {**canonical(cp), "terminal_receipt_ref": "sha256:" + "0" * 64},
        )
    else:

        def foreign(*_args: Any, **_kwargs: Any) -> Any:
            return _ModelInputUseJobCompletion(
                progress=model_owner.model_input_use_terminal_progress(case.checkpoint),
                selection=case.selection,
                checkpoint=case.checkpoint,
                action_payload_ref=case.job.payload_ref,
                authority_decision_ref=str(case.cas.decision.authority_decision_ref.artifact_id),
                currentness_resolver=lambda: True,
            )

        if fault == "same_owner_foreign_handler":
            from types import MethodType

            selected_handler = MethodType(foreign, case.service)
        elif fault == "spoofed_canonical_handler":

            class SpoofedHandler:
                def __init__(self) -> None:
                    self.__self__ = case.service
                    self.__func__ = AcquisitionActionService.handle_job

                def __call__(self, *_args: Any, **_kwargs: Any) -> Any:
                    return foreign()

            selected_handler = SpoofedHandler()
        else:
            selected_handler = foreign
        monkeypatch.setattr(case.control, "_acquisition_job_handler", selected_handler)
    with (
        case.database.job_execution_fence(
            job_id=case.job.job_id, worker_id=case.worker, attempt=case.attempt
        ),
        pytest.raises((ValueError, TypeError), match=r"replay_refused|model_input_use_completion_"),
    ):
        _complete(case)
    _assert_not_completed(case)
    assert case.database.read_generic_model_input_frontier(case.key) is None
    if fault == "current_authority_changed":
        assert calls[-2:] == ["prepare", "worker"]


@pytest.mark.parametrize(
    "fault", ["stale_revision", "stale_ref", "lost_lease", "insert_interrupted"]
)
def test_completion_failure_preserves_prior_frontier_and_selected_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    case = _model_input_completion_case(tmp_path)
    kwargs: dict[str, Any] = {}
    if fault == "stale_revision":
        kwargs["expected_revision"] = 2
    if fault == "stale_ref":
        kwargs["expected_ref"] = "sha256:" + "0" * 64
    prior = _comparison(case, tmp_path, "different", **kwargs)
    after_replay = None
    if fault == "lost_lease":

        def expire() -> None:
            expires_at = case.database.get_job(case.job.job_id).lease_expires_at
            assert expires_at is not None
            monkeypatch.setattr(store_module, "_utc_now", lambda: expires_at + timedelta(seconds=1))

        after_replay = expire
    _install_reconciler(case, monkeypatch, after_replay=after_replay)
    if fault == "insert_interrupted":
        execute = ControlPlaneStore._execute

        def interrupt(store: Any, sql: str, params: Any) -> int:
            if "INSERT INTO runtime_generic_model_input_evaluation_uses" in sql:
                raise RuntimeError("current_use_insert_interrupted")
            return execute(store, sql, params)

        monkeypatch.setattr(ControlPlaneStore, "_execute", interrupt)
    with case.database.job_execution_fence(
        job_id=case.job.job_id, worker_id=case.worker, attempt=case.attempt
    ):
        paid = {"model_input_use": case.checkpoint.model_dump(mode="json", exclude_none=True)}
        case.database.update_progress_state(job_id=case.job.job_id, state="running", progress=paid)
        expected_error = (
            ControlJobLeaseLostError
            if fault == "lost_lease"
            else RuntimeError
            if fault == "insert_interrupted"
            else ValueError
        )
        expected_reason = (
            "lease"
            if fault == "lost_lease"
            else "current_use_insert_interrupted"
            if fault == "insert_interrupted"
            else "generic_model_input_frontier_conflict"
        )
        with pytest.raises(expected_error, match=expected_reason):
            _complete(case)
    _assert_not_completed(case)
    assert (
        case.database.get_job(case.job.job_id).progress["model_input_use"]
        == paid["model_input_use"]
    )
    assert case.database.read_generic_model_input_frontier(case.key) == prior


def test_legacy_dictionary_completion_preserves_ordinary_handler_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _model_input_completion_case(tmp_path)
    progress = {"receipt_phase": "terminal", "state": "completed", "ordinary": "preserved"}
    monkeypatch.setattr(
        AcquisitionActionService, "_handle_model_input_use_job", lambda *_a, **_k: progress
    )
    monkeypatch.setattr(
        type(case.control), "_emit_runtime_diagnostic_event", lambda *_a, **_k: None
    )
    with case.database.job_execution_fence(
        job_id=case.job.job_id, worker_id=case.worker, attempt=case.attempt
    ):
        _complete(case)
    assert case.database.get_job(case.job.job_id).progress["ordinary"] == "preserved"
    assert (
        case.database.get_generic_model_input_use(key=case.key, action_job_id=case.job.job_id)
        is None
    )


def test_native_closed_checkpoint_reopens_terminal_outbox_and_original_lease(
    tmp_path: Path,
) -> None:
    case = _model_input_completion_case(tmp_path)
    checkpoint = model_owner.ModelInputUseActionCheckpoint(
        phase_ref=case.checkpoint.phase_ref,
        semantic_successor_ref=case.checkpoint.semantic_successor_ref,
        execution_ref=case.checkpoint.execution_ref,
        result_ref=case.checkpoint.result_ref,
    )
    payload = model_owner.model_input_use_terminal_progress(checkpoint)
    with case.database.job_execution_fence(
        job_id=case.job.job_id, worker_id=case.worker, attempt=case.attempt
    ):
        case.database.complete_job(
            job_id=case.job.job_id,
            run_id=case.job.run_id,
            progress=payload,
            expected_lease_owner=case.worker,
            expected_attempt=case.attempt,
        )

    completed = case.database.get_job(case.job.job_id)
    readback, terminal, started = _closed_native_model_input_use_checkpoint(
        case.database, completed
    )
    assert readback == checkpoint
    assert terminal.payload["lease_owner"] == case.worker
    assert terminal.payload["attempt"] == case.attempt
    assert started <= terminal.created_at
    assert completed.lease_owner is None
    outbox = case.database.get_job_completed_outbox_event(case.job.job_id)
    assert (
        case.database.get_generic_model_input_use(key=case.key, action_job_id=case.job.job_id)
        is None
    )

    altered = json.loads(json.dumps(outbox.payload))
    altered["progress"]["model_input_use"]["execution_ref"]["manifest_profile_sha256"] = (
        "sha256:" + "0" * 64
    )
    case.database._execute(
        "UPDATE control_outbox_events SET payload_json = ? WHERE event_id = ?",
        (json.dumps(altered), outbox.event_id),
    )
    assert (
        case.database.get_job(case.job.job_id).progress["model_input_use"]
        == payload["model_input_use"]
    )
    with pytest.raises(
        model_owner.ModelInputSuccessorActionError,
        match="native_model_input_use_terminal_checkpoint_mismatch",
    ):
        _closed_native_model_input_use_checkpoint(case.database, completed)

    case.database._execute(
        "DELETE FROM control_outbox_events WHERE event_id = ?", (outbox.event_id,)
    )
    with pytest.raises(RuntimeError, match="control_job_completed_outbox_count_not_one"):
        _closed_native_model_input_use_checkpoint(case.database, completed)


def test_native_failed_stage_requires_the_original_failure_outbox(tmp_path: Path) -> None:
    case = _model_input_completion_case(tmp_path)
    stage = model_owner.ModelInputUseActionCheckpoint(
        phase_ref=case.checkpoint.phase_ref,
        semantic_successor_ref=case.checkpoint.semantic_successor_ref,
    )
    with case.database.job_execution_fence(
        job_id=case.job.job_id, worker_id=case.worker, attempt=case.attempt
    ):
        case.database.fail_job(
            job_id=case.job.job_id,
            error_message="test_native_post_effect_readback_failed",
            progress={"model_input_use": stage.model_dump(mode="json", exclude_none=True)},
        )
    failed = case.database.get_job(case.job.job_id)
    selected, running, failure = _failed_native_model_input_use_stage(
        case.database, failed, expected_attempt=case.attempt
    )
    assert selected == stage
    assert running.created_at < failure.created_at
    assert running.payload["lease_owner"] == failure.payload["lease_owner"] == case.worker
    assert failure.payload["attempt"] == case.attempt
    outbox = case.database._get_outbox_event_by_key(
        topic="control.job.failed", event_key=f"{failed.job_id}:job_failed:attempt:{case.attempt}"
    ) or case.database._get_outbox_event_by_key(
        topic="control.job.failed", event_key=f"{failed.job_id}:job_failed"
    )
    assert outbox is not None
    case.database._execute(
        "DELETE FROM control_outbox_events WHERE event_id = ?", (outbox.event_id,)
    )
    assert case.database.get_job(failed.job_id) == failed
    with pytest.raises(
        model_owner.ModelInputSuccessorActionError,
        match="native_model_input_use_custody_failed_attempt_not_established",
    ):
        _failed_native_model_input_use_stage(case.database, failed, expected_attempt=case.attempt)


def test_native_closed_result_reopens_the_same_window_and_one_durable_unit(tmp_path: Path) -> None:
    from polisyos.runtime.quality.joint_simulation_horizon import (
        PhysicalSimulationWorkObservation,
        _physical_invocation_binding,
    )
    from polisyos.scientist.orchestration.engine import (
        BudgetLedgerInvocationProfile,
        BudgetLimit,
        BudgetMiddleware,
        BudgetState,
        ProducerBudgetObserver,
    )
    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
    from tests.unit.scientist.orchestration.engine.test_producer_budget_c49 import (
        _diagnostic_owner,
        _settle,
    )

    ledger, settlement, binding, policy, old_observer = _diagnostic_owner(
        tmp_path, total=4, protected=1, purpose="standard"
    )
    _settle(settlement, binding, "native-failed-cut-original-cost", "0.01")
    old_operation, old_digest = _physical_invocation_binding("d" * 32, "b" * 64, 42)
    with old_observer.invocation_purpose_scope_from_selected_owner(policy, purpose="standard"):
        assert old_observer.reserve_invocation(old_operation, old_digest) is not None
        old_observer.finish_invocation(old_operation, old_digest, "completed")
    phase_ref = _selected_ref("runtime.quality.model_input_use_action_phase", 8)
    identity = model_owner.ModelInputSuccessorIdentity(
        origin=SimpleNamespace(
            source_payload_ref="sha256:" + "a" * 64,
            n5_expectation=SimpleNamespace(profile_selection_ref="sha256:" + "b" * 64),
        ),
        request=_native_request(),
        passport_ref=_selected_ref("epoch.acquisition_passport_snapshot", 4),
        observation_content_sha256="sha256:" + "c" * 64,
        route_id="sha256:" + "d" * 64,
        job_id="model-input-use.current",
    )
    control = SimpleNamespace(
        _llm_producer_settlement_store=settlement,
        verify_acquisition_source_budget_owner=lambda *, closure: binding,
        verify_candidate_unpriced_budget_scope=lambda *, closure: SimpleNamespace(
            run_budget_usd=Decimal("1")
        ),
    )
    window = model_owner._resolve_action_budget_window(
        control, selection=identity, phase_ref=phase_ref, open_if_missing=True
    )
    assert window.baseline_total_usd == Decimal("0.01")
    observer = ProducerBudgetObserver(
        settlement_store=settlement,
        producer_run_binding=binding,
        budget_state=BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=window.effective_limit_usd)}
        ),
        invocation_selection_pending=True,
        reentry_budget_scope=window.scope,
    )
    observer.bind_existing_invocation_policy_from_selected_owner(policy, purpose="standard")
    invocation_id, physical_spec, seed = "a" * 32, "b" * 64, 42
    operation, digest = _physical_invocation_binding(invocation_id, physical_spec, seed)
    started = datetime.now(UTC)
    with observer.invocation_purpose_scope_from_selected_owner(policy, purpose="standard"):
        basis = observer.admit()
        reserved = observer.reserve_invocation(operation, digest)
        observer.finish_invocation(operation, digest, "completed")
    assert reserved is not None
    finished = datetime.now(UTC)
    work = PhysicalSimulationWorkObservation(
        invocation_id=invocation_id,
        event_id="e" * 32,
        physical_spec_ref=physical_spec,
        effective_seed=seed,
        status="completed",
        started_at=started,
        completed_at=finished,
        duration_seconds=(finished - started).total_seconds(),
        budget_status="current_owner_checked",
        budget_source_basis_digest=basis.source_basis_digest,
        invocation_quota_operation_id=operation,
        invocation_quota_request_digest=digest,
        invocation_quota_profile_digest=reserved.profile_digest,
        invocation_quota_purpose="standard",
        invocation_quota_status="completed",
    )
    # This component supplies the result shape. The served read must exercise
    # canonical ProgramGraph output and its numerical result owner together.
    resolution = SimpleNamespace(
        request=SimpleNamespace(replications=1, program_graph_comparator_profile=None),
        result=SimpleNamespace(
            physical_work_observations=(work,),
            trajectories=(object(),),
            receipt=SimpleNamespace(engine_kind="program_graph"),
            diagnostics={
                "physical_work_capture_status": "observed",
                "producer_budget_observations": {
                    basis.source_basis_digest: basis.model_dump(mode="json")
                },
            },
        ),
    )
    source = tmp_path / "diagnostic-ledger.json"
    before = source.read_bytes()
    control._llm_producer_settlement_store = BudgetMiddleware(
        BudgetState(), ledger=FileBudgetLedger(source)
    )
    selected = model_owner._resolve_action_budget_window(
        control, selection=identity, phase_ref=phase_ref, open_if_missing=False
    )
    assert selected == window

    def verify_finished_cut(
        failed_at: datetime, *, original_work_cut_revision: int | None = None
    ) -> int:
        return _verify_native_model_input_use_completed_work(
            control,
            resolved=resolution,
            input_record=SimpleNamespace(n5=SimpleNamespace(invocation_quota_policy=policy)),
            window=selected,
            started_at=started,
            finished_at=failed_at,
            require_failed_attempt_cut=True,
            original_work_cut_revision=original_work_cut_revision,
        )

    original_work_cut_revision = verify_finished_cut(finished)
    assert original_work_cut_revision == ledger.snapshot().revision
    with pytest.raises(ValueError, match="custody_cut_not_established"):
        verify_finished_cut(finished, original_work_cut_revision=original_work_cut_revision + 1)
    assert source.read_bytes() == before
    assert set(ledger.snapshot().invocation_reservations) == {operation, old_operation}

    moved = tmp_path / "same-bytes-different-owner.json"
    moved.write_bytes(before)
    control._llm_producer_settlement_store = BudgetMiddleware(
        BudgetState(), ledger=FileBudgetLedger(moved)
    )
    with pytest.raises(ValueError, match="reentry_budget_window_conflict"):
        model_owner._resolve_action_budget_window(
            control, selection=identity, phase_ref=phase_ref, open_if_missing=False
        )
    assert moved.read_bytes() == before == source.read_bytes()

    control._llm_producer_settlement_store = settlement
    different_run = binding.model_copy(
        update={"run_id": "independent-run", "control_job_id": "independent-job"}
    )
    different_profile = BudgetLedgerInvocationProfile.from_policy(different_run, policy)
    ledger.configure_invocation_profile(different_profile)
    unrelated_operation, unrelated_digest = _physical_invocation_binding(
        "e" * 32, physical_spec, seed
    )
    _, created = ledger.reserve_invocation(
        unrelated_operation, unrelated_digest, profile=different_profile, purpose="standard"
    )
    assert created
    verify_finished_cut(finished)

    # The later reservation is indistinguishable from work of this same
    # action because only its run identity was retained.
    another_operation, another_digest = _physical_invocation_binding("c" * 32, physical_spec, seed)
    with observer.invocation_purpose_scope_from_selected_owner(policy, purpose="standard"):
        assert observer.reserve_invocation(another_operation, another_digest) is not None
        pending = source.read_bytes()
        with pytest.raises(ValueError, match="custody_physical_denominator_not_established"):
            verify_finished_cut(finished)
        assert (
            verify_finished_cut(finished, original_work_cut_revision=original_work_cut_revision)
            == original_work_cut_revision
        )
        assert source.read_bytes() == pending
        observer.finish_invocation(another_operation, another_digest, "completed")
    completed = source.read_bytes()
    with pytest.raises(ValueError, match="custody_physical_denominator_not_established"):
        verify_finished_cut(finished)
    assert (
        verify_finished_cut(finished, original_work_cut_revision=original_work_cut_revision)
        == original_work_cut_revision
    )
    assert source.read_bytes() == completed


@pytest.mark.parametrize(
    ("fault", "reason", "expected_calls"),
    [
        (None, None, ["handler", "check-current"]),
        (
            "currentness",
            "native_model_input_use_completion_authority_not_current",
            ["handler", "check-current"],
        ),
        ("stage", "native_model_input_use_completion_checkpoint_mismatch", ["handler"]),
        ("plain", "native_model_input_use_completion_owner_not_established", ["handler"]),
        ("foreign", "model_input_use_completion_owner_not_established", []),
    ],
)
def test_native_completion_uses_canonical_handler_stage_and_last_authority_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault, reason, expected_calls
) -> None:
    case = _model_input_completion_case(tmp_path)
    calls = []
    stage = model_owner.ModelInputUseActionCheckpoint(
        phase_ref=case.checkpoint.phase_ref,
        semantic_successor_ref=case.checkpoint.semantic_successor_ref,
    )
    checkpoint = model_owner.ModelInputUseActionCheckpoint(
        phase_ref=stage.phase_ref,
        semantic_successor_ref=stage.semantic_successor_ref,
        execution_ref=case.checkpoint.execution_ref,
        result_ref=case.checkpoint.result_ref,
    )
    finish = model_owner.model_input_use_terminal_progress(checkpoint)

    def still_current() -> bool:
        calls.append("check-current")
        current = case.database.current_execution_job_admission()
        assert current.job.job_id == case.job.job_id
        assert current.job.lease_owner == case.worker
        return fault != "currentness"

    def result(*_args, **_kwargs):
        calls.append("handler")
        if fault == "plain":
            return finish
        return model_owner.NativeModelInputUseJobCompletion(
            progress=finish,
            checkpoint=checkpoint,
            admission=case.database.current_execution_job_admission(),
            currentness_resolver=still_current,
        )

    monkeypatch.setattr(AcquisitionActionService, "_handle_native_model_input_use_job", result)
    if fault == "foreign":
        monkeypatch.setattr(case.control, "_acquisition_job_handler", result)
    monkeypatch.setattr(
        type(case.control), "_emit_runtime_diagnostic_event", lambda *_a, **_k: None
    )
    with case.database.job_execution_fence(
        job_id=case.job.job_id, worker_id=case.worker, attempt=case.attempt
    ):
        prepared = stage.model_dump(mode="json", exclude_none=True)
        if fault == "stage":
            prepared["phase_ref"]["manifest_profile_sha256"] = "sha256:" + "0" * 64
        case.database.update_progress_state(
            job_id=case.job.job_id, state="running", progress={"model_input_use": prepared}
        )
        admission = case.database.current_execution_job_admission()

        def publish() -> None:
            case.control._complete_acquisition_control_job(
                job=admission.job,
                payload={
                    "action_kind": MODEL_INPUT_USE_ACTION_KIND,
                    "request": _native_request().model_dump(mode="json"),
                },
                execution_scope=admission.scope,
                capability_manifest_ref=admission.job.capability_manifest_ref,
            )

        if reason is None:
            publish()
        else:
            with pytest.raises(ValueError, match=reason):
                publish()
    assert calls == expected_calls
    if reason is None:
        completed = case.database.get_job(case.job.job_id)
        selected, terminal, _ = _closed_native_model_input_use_checkpoint(case.database, completed)
        assert selected == checkpoint
        assert terminal.payload["lease_owner"] == case.worker
        assert terminal.payload["attempt"] == case.attempt
        assert (
            case.database.get_generic_model_input_use(key=case.key, action_job_id=case.job.job_id)
            is None
        )
    else:
        _assert_not_completed(case)
