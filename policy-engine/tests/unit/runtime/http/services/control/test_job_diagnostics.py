"""Acquisition completion relay and real SQL atomicity, with replay isolated.

The selected-record fixture is deliberately unreplayed. Canonical producer,
signed PA2 and numerical retention are not established by these seam tests;
the served model-input-use integration exercises those owners together.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.runtime.http.services import control_plane_store as store_module
from polisyos.runtime.http.services import model_input_successor_action as model_owner
from polisyos.runtime.http.services.acquisition_action_service import AcquisitionActionService
from polisyos.runtime.http.services.control.job_diagnostics import _ModelInputUseJobCompletion
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobLeaseLostError,
    ControlPlaneStore,
)
from polisyos.runtime.quality.agent_action_authority import MODEL_INPUT_USE_ACTION_KIND
from tests.unit.runtime.http.services.test_acquisition_action_service import (
    _install_model_input_completion_producer,
    _model_input_completion_case,
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
