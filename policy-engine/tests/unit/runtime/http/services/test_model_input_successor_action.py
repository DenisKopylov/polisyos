from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.http.services.model_input_successor_action import (
    ModelInputUseActionCheckpoint,
    model_input_use_terminal_progress,
)


def _selected_ref(kind: str, digit: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{digit * 64}",
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "f" * 64,
    )


def _checkpoint(**kwargs: object) -> ModelInputUseActionCheckpoint:
    return ModelInputUseActionCheckpoint(
        phase_ref=_selected_ref("runtime.quality.model_input_use_action_phase", "1"),
        semantic_successor_ref=_selected_ref(
            "runtime.quality.model_input_successor_selection", "2"
        ),
        **kwargs,
    )


def test_legacy_checkpoint_remains_readable_and_uses_its_execution_locator() -> None:
    checkpoint = _checkpoint(
        execution_ref=_selected_ref("runtime.quality.generic_cycle_simulation_n5_execution", "3"),
        result_ref=_selected_ref("polisyos.runtime.joint_simulation_result", "4"),
    )

    terminal = model_input_use_terminal_progress(checkpoint)

    assert "schema_version" not in terminal["model_input_use"]
    assert terminal["terminal_receipt_ref"] == str(checkpoint.execution_ref.artifact_id)


def test_retained_v2_checkpoint_uses_current_decision_locator_not_original_n5() -> None:
    checkpoint = _checkpoint(
        schema_version="polisyos.runtime.ModelInputUseActionCheckpoint@2.0",
        evaluation_decision_ref=_selected_ref(
            "runtime_quality.acquisition_evaluation_decision", "5"
        ),
        evaluation_current_basis_ref=_selected_ref(
            "runtime_quality.acquisition_evaluation_basis", "6"
        ),
    )

    terminal = model_input_use_terminal_progress(checkpoint)

    assert terminal["terminal_receipt_ref"] == str(checkpoint.evaluation_decision_ref.artifact_id)
    assert checkpoint.execution_ref is None
    assert checkpoint.result_ref is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "evaluation_decision_ref": _selected_ref(
                "runtime_quality.acquisition_evaluation_decision", "7"
            )
        },
        {
            "schema_version": "polisyos.runtime.ModelInputUseActionCheckpoint@2.0",
            "evaluation_decision_ref": _selected_ref(
                "runtime_quality.acquisition_evaluation_decision", "8"
            ),
        },
    ],
)
def test_checkpoint_does_not_promote_partial_evaluation_refs(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="model_input_use_checkpoint_selected_refs_invalid"):
        _checkpoint(**kwargs)


def test_retained_terminal_requires_a_decision_ref() -> None:
    checkpoint = _checkpoint()

    with pytest.raises(ValueError, match="model_input_use_result_not_established"):
        model_input_use_terminal_progress(checkpoint)


def test_existing_equivalent_frontier_completes_without_calling_n5(monkeypatch) -> None:
    from polisyos.runtime.http.services import model_input_successor_action as action
    from polisyos.runtime.quality import acquisition_evaluation

    original_input = _selected_ref("runtime.quality.generic_cycle_simulation_n5_input", "a")
    original_execution = _selected_ref("runtime.quality.generic_cycle_simulation_n5_execution", "b")
    original_result = _selected_ref("polisyos.runtime.joint_simulation_result", "c")
    original_semantic = _selected_ref("runtime.quality.model_input_successor_selection", "d")
    current_semantic = _selected_ref("runtime.quality.model_input_successor_selection", "e")
    original_action_job_id = "original-n5-action"
    current_action_job_id = "current-use-action"
    origin = SimpleNamespace(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="source-job",
        source_cycle=SimpleNamespace(
            design_problem_ref="sha256:" + "1" * 64,
            selected_candidate_ref="candidate-a",
        ),
        n5_expectation=SimpleNamespace(input_ref=original_input),
    )
    selection = SimpleNamespace(
        origin=origin,
        job_id=current_action_job_id,
        route_id="sha256:" + "2" * 64,
    )
    original_evaluation = SimpleNamespace(
        input_ref=original_input,
        execution_ref=original_execution,
        result_ref=original_result,
        semantic_successor_ref=original_semantic,
        action_job_id=original_action_job_id,
    )
    frontier = SimpleNamespace(
        selected_evaluation=original_evaluation,
        basis_ref=_selected_ref("runtime_quality.acquisition_evaluation_basis", "f"),
        revision=1,
        frontier_ref="sha256:" + "3" * 64,
    )

    class _JobStore:
        def __init__(self):
            self.record = SimpleNamespace(
                job_id=current_action_job_id,
                payload_ref="sha256:" + "4" * 64,
                progress={},
            )
            admitted_job = SimpleNamespace(
                job_id=current_action_job_id,
                payload_ref=self.record.payload_ref,
                progress={},
            )
            self.admission = SimpleNamespace(
                job=admitted_job,
                same_execution_identity=lambda _other: True,
            )

        def current_execution_job_admission(self):
            return self.admission

        def current_execution_job_record(self):
            return self.record

        def read_generic_model_input_frontier(self, key):
            assert key.source_job_id == "source-job"
            assert key.candidate_id == "candidate-a"
            return frontier

        def update_progress_state(self, *, progress, **_kwargs):
            self.record.progress = progress

    job_store = _JobStore()
    control = SimpleNamespace(
        _artifact_store=object(),
        _control_store=job_store,
        _diagnostic_event_log=object(),
        _llm_producer_settlement_store=object(),
    )
    counted = {"n5": 0}
    decision_inputs = []
    monkeypatch.setattr(action, "matches_artifact_store_protocol", lambda *_: True)
    monkeypatch.setattr(action, "_expected_phase", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        action,
        "persist_model_input_use_action_phase",
        lambda *_: _selected_ref("runtime.quality.model_input_use_action_phase", "5"),
    )
    monkeypatch.setattr(action, "_resolve_action_budget_window", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        action,
        "_materialize_semantic_successor",
        lambda *_args, **_kwargs: current_semantic,
    )
    monkeypatch.setattr(
        action,
        "_build_model_input_use_n5_port",
        lambda *_args, **_kwargs: SimpleNamespace(_controller=object()),
    )
    monkeypatch.setattr(action, "_read_generic_model_input_basis", lambda *_args: object())
    monkeypatch.setattr(
        action,
        "_run_model_input_use_n5",
        lambda *_args, **_kwargs: counted.__setitem__("n5", counted["n5"] + 1),
    )
    monkeypatch.setattr(
        acquisition_evaluation,
        "issue_generic_model_input_evaluation_basis",
        lambda **kwargs: SimpleNamespace(
            basis_role=kwargs["basis_role"],
            evaluation=kwargs.get("evaluation"),
            action_job_id=current_action_job_id,
        ),
    )
    monkeypatch.setattr(
        acquisition_evaluation,
        "compare_generic_model_input_evaluation_bases",
        lambda **_kwargs: ("equivalent", ()),
    )
    monkeypatch.setattr(
        acquisition_evaluation,
        "issue_generic_model_input_evaluation_decision",
        lambda **kwargs: decision_inputs.append(kwargs)
        or SimpleNamespace(
            decision_kind=kwargs["decision_kind"], action_job_id=current_action_job_id
        ),
    )
    basis_ref = _selected_ref("runtime_quality.acquisition_evaluation_basis", "6")
    decision_ref = _selected_ref("runtime_quality.acquisition_evaluation_decision", "7")
    monkeypatch.setattr(
        action,
        "_persist_generic_model_input_record",
        lambda _store, _events, record: basis_ref
        if getattr(record, "basis_role", None) == "prospective"
        else decision_ref,
    )
    monkeypatch.setattr(
        action,
        "read_model_input_successor_selection",
        lambda *_args: SimpleNamespace(),
    )
    monkeypatch.setattr(action, "_verify_selected_routing_use_decision_current", lambda *_: None)

    checkpoint = action.run_model_input_use_action(
        control,
        selection=selection,
        admission=job_store.admission,
        decision_ref="sha256:" + "8" * 64,
        currentness_resolver=lambda: True,
    )

    assert counted["n5"] == 0
    assert checkpoint.execution_ref is None
    assert checkpoint.evaluation_decision_ref == decision_ref
    assert checkpoint.evaluation_replacement_basis_ref is None
    assert decision_inputs[0]["comparison_result"] == "equivalent"
    assert decision_inputs[0]["semantic_successor_ref"] == current_semantic
    assert decision_inputs[0]["prior_evaluation"].action_job_id == original_action_job_id
    assert decision_inputs[0]["prior_evaluation"].execution_ref == original_execution
    assert frontier.selected_evaluation.action_job_id == original_action_job_id
    assert frontier.selected_evaluation.execution_ref == original_execution


@pytest.mark.parametrize("pointer_persisted", [True, False])
def test_paid_v2_pending_checkpoint_recovers_initial_selection_without_second_n5(
    monkeypatch, pointer_persisted: bool
) -> None:
    from polisyos.runtime.http.services import model_input_successor_action as action
    from polisyos.runtime.quality import acquisition_evaluation

    current_action_job_id = "current-use-action"
    phase_ref = _selected_ref("runtime.quality.model_input_use_action_phase", "1")
    semantic_ref = _selected_ref("runtime.quality.model_input_successor_selection", "2")
    execution_ref = _selected_ref("runtime.quality.generic_cycle_simulation_n5_execution", "3")
    result_ref = _selected_ref("polisyos.runtime.joint_simulation_result", "4")
    checkpoint = _checkpoint(
        execution_ref=execution_ref,
        result_ref=result_ref,
        schema_version="polisyos.runtime.ModelInputUseActionCheckpoint@2.0",
        evaluation_expected_frontier_revision=0,
    )
    durable_checkpoint = checkpoint
    if not pointer_persisted:
        checkpoint = ModelInputUseActionCheckpoint.model_validate(
            {**checkpoint.model_dump(mode="python"), "execution_ref": None, "result_ref": None}
        )
    record = SimpleNamespace(
        job_id=current_action_job_id,
        run_id="run-a",
        payload_ref="sha256:" + "5" * 64,
        state="running",
        progress={"model_input_use": checkpoint.model_dump(mode="json")},
    )

    class _JobStore:
        def __init__(self):
            self.admission = SimpleNamespace(
                job=record,
                same_execution_identity=lambda _other: True,
            )

        def current_execution_job_admission(self):
            return self.admission

        def current_execution_job_record(self):
            return record

        def update_progress_state(self, *, progress, **_kwargs):
            record.progress = progress

    job_store = _JobStore()
    original_input = _selected_ref("runtime.quality.generic_cycle_simulation_n5_input", "a")
    origin = SimpleNamespace(
        run_id="run-a",
        tenant_id="tenant-a",
        cell_id="cell-a",
        n5_expectation=SimpleNamespace(input_ref=original_input),
    )
    selection = SimpleNamespace(origin=origin, job_id=current_action_job_id)
    admission = job_store.admission
    window = SimpleNamespace(window_id="window-a", record_digest="sha256:" + "9" * 64)
    previous_selection = SimpleNamespace(
        reentry_budget_window_id=window.window_id,
        reentry_budget_window_digest=window.record_digest,
    )
    control = SimpleNamespace(
        _artifact_store=object(),
        _control_store=job_store,
        _diagnostic_event_log=object(),
    )
    n5_calls = {"count": 0}
    evaluated_inputs = []
    recovered_inputs = []
    basis_ref = _selected_ref("runtime_quality.acquisition_evaluation_basis", "6")
    decision_ref = _selected_ref("runtime_quality.acquisition_evaluation_decision", "7")
    basis = SimpleNamespace(basis_role="evaluated", evaluation=None)
    decision = SimpleNamespace(decision_kind="initial", action_job_id=current_action_job_id)

    monkeypatch.setattr(action, "matches_artifact_store_protocol", lambda *_: True)
    monkeypatch.setattr(action, "_expected_phase", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        action,
        "_read_checkpoint_selection",
        lambda *_args, **_kwargs: previous_selection,
    )
    monkeypatch.setattr(action, "_verify_selected_routing_use_decision_current", lambda *_: None)
    monkeypatch.setattr(
        action,
        "_resolve_action_budget_window",
        lambda *_args, **_kwargs: window,
    )
    monkeypatch.setattr(
        action,
        "verify_model_input_use_result",
        lambda *_args, **_kwargs: SimpleNamespace(result="verified-original-result"),
    )
    monkeypatch.setattr(
        action,
        "_build_model_input_use_n5_port",
        lambda *_args, **_kwargs: SimpleNamespace(_controller=object()),
    )
    monkeypatch.setattr(
        action,
        "_issue_model_input_basis",
        lambda *_args, **kwargs: evaluated_inputs.append(kwargs["evaluation"]) or basis,
    )
    monkeypatch.setattr(
        action,
        "_persist_generic_model_input_record",
        lambda _store, _events, value: (basis_ref if value is basis else decision_ref),
    )
    monkeypatch.setattr(
        acquisition_evaluation,
        "issue_generic_model_input_evaluation_decision",
        lambda **kwargs: decision
        if kwargs["expected_frontier_revision"] == 0
        else pytest.fail("recovery must preserve the initially observed empty frontier"),
    )
    monkeypatch.setattr(
        action,
        "_run_model_input_use_n5",
        lambda *_args, **_kwargs: n5_calls.__setitem__("count", n5_calls["count"] + 1),
    )
    monkeypatch.setattr(
        action,
        "_recover_model_input_use_n5",
        lambda *_args, **kwargs: recovered_inputs.append(kwargs) or durable_checkpoint,
    )

    recovered = action.run_model_input_use_action(
        control,
        selection=selection,
        admission=admission,
        decision_ref="sha256:" + "8" * 64,
        currentness_resolver=lambda: True,
    )

    assert n5_calls["count"] == 0
    assert len(recovered_inputs) == (0 if pointer_persisted else 1)
    assert recovered.execution_ref == execution_ref
    assert recovered.result_ref == result_ref
    assert recovered.evaluation_decision_ref == decision_ref
    assert recovered.evaluation_replacement_basis_ref == basis_ref
    assert evaluated_inputs[0].action_job_id == current_action_job_id
    assert evaluated_inputs[0].input_ref == original_input
    assert evaluated_inputs[0].execution_ref == execution_ref
    assert record.progress["model_input_use"]["execution_ref"] == execution_ref.model_dump(
        mode="json"
    )


@pytest.mark.parametrize(
    "case",
    [
        "configured",
        "unconfigured",
        "missing_unit",
        "unknown_unit",
        "late_scope_loss",
        "missing_output",
        "replay_removed",
        "missing_work",
        "foreign_window",
    ],
)
def test_recovery_reconciles_real_ledger_before_pointer_write(tmp_path, monkeypatch, case) -> None:
    """Exercise the ledger/currentness seam; numerical source replay is isolated.

    The work value is an explicit typed fixture, not measured physical work.
    Genuine durable V5/result recovery belongs to the served worker scenario.
    """
    from datetime import UTC, datetime
    from decimal import Decimal

    from polisyos.runtime.http.services import model_input_successor_action as action
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextOwnerError
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        PhysicalSimulationWorkObservation,
        _physical_invocation_binding,
    )
    from polisyos.scientist.orchestration.engine import (
        BudgetInvocationQuotaPolicy,
        BudgetLedgerInvocationProfile,
        BudgetLedgerReentryBudgetScope,
        ProducerBudgetObserver,
    )
    from tests.unit.scientist.orchestration.engine.test_producer_budget_c49 import _owner, _settle

    middleware, binding, state = _owner(tmp_path)
    _settle(middleware, binding, "fixture-source", "0")
    scope = BudgetLedgerReentryBudgetScope(
        run_binding=binding,
        action_job_id="current-use-action",
        route_id="sha256:" + "a" * 64,
        action_generation=1,
        action_phase_ref="sha256:" + "b" * 64,
        source_payload_ref="sha256:" + "c" * 64,
        profile_selection_ref="sha256:" + "d" * 64,
    )
    window = middleware.open_reentry_budget_window_safe(
        scope, fresh_limit_usd=Decimal("1"), global_limit_usd=Decimal("1")
    )
    profile = (
        None
        if case == "unconfigured"
        else BudgetLedgerInvocationProfile.from_policy(
            binding,
            BudgetInvocationQuotaPolicy(
                allocation_id="recovery-fixture", total_units=3, protected_units=1
            ),
        )
    )
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
        invocation_quota_profile=profile,
        reentry_budget_scope=scope,
    )
    basis = observer.observe()
    invocation_id, physical_spec, seed = "a" * 32, "b" * 64, 7
    operation_id, request_digest = _physical_invocation_binding(invocation_id, physical_spec, seed)
    if case != "missing_unit":
        reservation = observer.reserve_invocation(operation_id, request_digest)
        if reservation is not None:
            observer.finish_invocation(
                operation_id, request_digest, "unknown" if case == "unknown_unit" else "completed"
            )
    at = datetime.now(UTC)
    work = PhysicalSimulationWorkObservation(
        invocation_id=invocation_id,
        event_id="c" * 32,
        physical_spec_ref=physical_spec,
        effective_seed=seed,
        status="completed",
        started_at=at,
        completed_at=at,
        duration_seconds=0,
        budget_status="current_owner_checked",
        budget_source_basis_digest=basis.source_basis_digest,
        invocation_quota_operation_id=operation_id if profile is not None else None,
        invocation_quota_request_digest=request_digest if profile is not None else None,
        invocation_quota_profile_digest=profile.profile_digest if profile is not None else None,
        invocation_quota_purpose="standard" if profile is not None else None,
        invocation_quota_status=("unknown" if case == "unknown_unit" else "completed")
        if profile is not None
        else None,
    )
    result = SimpleNamespace(
        physical_work_observations=() if case == "missing_work" else (work,),
        diagnostics={
            "producer_budget_observations": {
                basis.source_basis_digest: basis.model_dump(mode="python")
            }
        },
    )
    checkpoint = _checkpoint(
        schema_version="polisyos.runtime.ModelInputUseActionCheckpoint@2.0",
        evaluation_expected_frontier_revision=0,
    )
    execution_ref = _selected_ref("runtime.quality.generic_cycle_simulation_n5_execution", "3")
    result_ref = _selected_ref("polisyos.runtime.joint_simulation_result", "4")
    record = SimpleNamespace(progress={"model_input_use": checkpoint.model_dump(mode="json")})
    updates = []
    control = SimpleNamespace(
        _llm_producer_settlement_store=middleware,
        _control_store=SimpleNamespace(
            current_execution_job_record=lambda: record,
            update_progress_state=lambda **kwargs: updates.append(kwargs),
        ),
    )
    selection = SimpleNamespace(
        job_id=scope.action_job_id, origin=SimpleNamespace(n5_expectation=1)
    )

    def lookup(_owner, **kwargs):
        assert kwargs["action_job_id"] == scope.action_job_id
        assert kwargs["semantic_successor_ref"] == checkpoint.semantic_successor_ref
        if case == "missing_output":
            raise CycleSubstrateContextOwnerError("generic_n5_recovery_output_not_established")
        return execution_ref, SimpleNamespace(result_ref=result_ref)

    def verify(*_args, **kwargs):
        assert kwargs["checkpoint"].execution_ref == execution_ref
        if case == "replay_removed":
            raise ValueError("selected_result_missing")
        return SimpleNamespace(result=result)

    monkeypatch.setattr(
        GenericCycleSimulationAdmissionOwner, "recover_semantic_successor_execution", lookup
    )
    monkeypatch.setattr(action, "verify_model_input_use_result", verify)
    monkeypatch.setattr(
        action, "_run_model_input_use_n5", lambda *_a, **_k: pytest.fail("recovery repeated N5")
    )
    reads = []

    def currentness():
        reads.append(True)
        return not (case == "late_scope_loss" and len(reads) > 1)

    before = middleware.snapshot_safe()
    args = {
        "selection": selection,
        "checkpoint": checkpoint,
        "window": window,
        "action_payload_ref": "sha256:" + "5" * 64,
        "authority_decision_ref": "sha256:" + "6" * 64,
        "currentness_resolver": currentness,
    }
    if case == "foreign_window":
        args["window"] = type(window).model_validate(
            {**window.model_dump(mode="python"), "fresh_limit_usd": Decimal("2")}
        )
    if case in {"configured", "unconfigured"}:
        recovered = action._recover_model_input_use_n5(control, object(), **args)
        assert recovered.execution_ref == execution_ref and recovered.result_ref == result_ref
        assert len(updates) == 1 and len(reads) == 2
        assert updates[0]["progress"]["model_input_use"]["execution_ref"] == (
            execution_ref.model_dump(mode="json")
        )
    else:
        with pytest.raises(
            action.ModelInputSuccessorActionError,
            match="scope_not_current" if case == "late_scope_loss" else "recovery_required",
        ):
            action._recover_model_input_use_n5(control, object(), **args)
        assert updates == []
    assert middleware.snapshot_safe() == before


@pytest.mark.parametrize("comparison", ["different", "not_established"])
def test_comparison_recovers_missing_output_pointer_before_evaluated_replacement(
    tmp_path, monkeypatch, comparison
) -> None:
    """Keep the selected prospective/decision refs across the isolated recovery seam."""
    from dataclasses import replace

    from polisyos.runtime.http.services import model_input_successor_action as action
    from polisyos.runtime.quality import acquisition_evaluation
    from tests.unit.runtime.http.services.control.test_job_diagnostics import _comparison
    from tests.unit.runtime.http.services.test_acquisition_action_service import (
        _model_input_completion_case,
    )

    case = _model_input_completion_case(tmp_path)
    _comparison(case, tmp_path, comparison)
    paid = case.checkpoint
    pending = ModelInputUseActionCheckpoint.model_validate(
        {
            **paid.model_dump(mode="python"),
            "execution_ref": None,
            "result_ref": None,
            "evaluation_replacement_basis_ref": None,
        }
    )
    origin = SimpleNamespace(
        n5_expectation=SimpleNamespace(input_ref=case.cas.replacement.selected_evaluation.input_ref)
    )
    selection = replace(case.selection, origin=origin)
    window = SimpleNamespace(window_id="retained-window", record_digest="sha256:" + "9" * 64)
    previous = SimpleNamespace(
        reentry_budget_window_id=window.window_id,
        reentry_budget_window_digest=window.record_digest,
    )
    recovered = []
    evaluated = []
    replacement_ref = _selected_ref("runtime_quality.acquisition_evaluation_basis", "e")
    monkeypatch.setattr(action, "_expected_phase", lambda *_a, **_k: object())
    monkeypatch.setattr(action, "_read_checkpoint_selection", lambda *_a, **_k: previous)
    monkeypatch.setattr(action, "_verify_selected_routing_use_decision_current", lambda *_a: None)
    monkeypatch.setattr(action, "_resolve_action_budget_window", lambda *_a, **_k: window)
    monkeypatch.setattr(
        action,
        "_recover_model_input_use_n5",
        lambda *_a, **kwargs: recovered.append(kwargs)
        or ModelInputUseActionCheckpoint.model_validate(
            {
                **pending.model_dump(mode="python"),
                "execution_ref": paid.execution_ref,
                "result_ref": paid.result_ref,
            }
        ),
    )
    monkeypatch.setattr(action, "verify_model_input_use_result", lambda *_a, **_k: object())
    monkeypatch.setattr(
        action,
        "_build_model_input_use_n5_port",
        lambda *_a, **_k: SimpleNamespace(_controller=object()),
    )
    monkeypatch.setattr(
        acquisition_evaluation,
        "read_acquisition_evaluation_artifact",
        lambda **_k: case.cas.decision,
    )
    monkeypatch.setattr(
        acquisition_evaluation,
        "issue_generic_model_input_evaluation_basis",
        lambda **kwargs: evaluated.append(kwargs) or object(),
    )
    monkeypatch.setattr(action, "_persist_generic_model_input_record", lambda *_a: replacement_ref)
    monkeypatch.setattr(
        acquisition_evaluation,
        "reconcile_generic_model_input_evaluation_completion",
        lambda **_k: object(),
    )
    monkeypatch.setattr(
        action, "_run_model_input_use_n5", lambda *_a, **_k: pytest.fail("recovery repeated N5")
    )
    with case.database.job_execution_fence(
        job_id=case.job.job_id, worker_id=case.worker, attempt=case.attempt
    ):
        case.database.update_progress_state(
            job_id=case.job.job_id,
            state="running",
            progress={"model_input_use": pending.model_dump(mode="json", exclude_none=True)},
        )
        completed = action.run_model_input_use_action(
            case.control,
            selection=selection,
            admission=case.database.current_execution_job_admission(),
            decision_ref=str(case.cas.decision.authority_decision_ref.artifact_id),
            currentness_resolver=lambda: True,
        )
    assert len(recovered) == len(evaluated) == 1
    assert recovered[0]["checkpoint"] == pending
    assert completed.execution_ref == paid.execution_ref and completed.result_ref == paid.result_ref
    assert completed.evaluation_decision_ref == pending.evaluation_decision_ref
    assert completed.evaluation_current_basis_ref == pending.evaluation_current_basis_ref
    assert completed.evaluation_replacement_basis_ref == replacement_ref
    assert evaluated[0]["basis_role"] == "evaluated"
    assert evaluated[0]["prospective_basis_ref"] == pending.evaluation_current_basis_ref
    assert evaluated[0]["comparison_decision_ref"] == pending.evaluation_decision_ref


@pytest.mark.parametrize("has_prior", [False, True])
def test_fresh_initial_and_replacement_keep_pa2_separate_from_evaluation_decision(
    tmp_path, monkeypatch, has_prior
) -> None:
    """Use the real CAS kind join at both fresh branches' terminal verification.

    Producer and signed permission replay remain isolated. The authority-kind
    fixture supplies no grant; this check distinguishes its selector from the
    separately persisted evaluation selector through the actual Core reader.
    """
    from dataclasses import replace

    from polisyos.core import artifacts, canon
    from polisyos.runtime.http.services import model_input_successor_action as action
    from polisyos.runtime.quality import acquisition_evaluation
    from tests.unit.runtime.http.services.control.test_job_diagnostics import _comparison
    from tests.unit.runtime.http.services.test_acquisition_action_service import (
        _model_input_completion_case,
    )
    from tests.unit.runtime.quality.test_cycle_substrate import _authenticated_tenant_scope

    case = _model_input_completion_case(tmp_path)
    if has_prior:
        _comparison(case, tmp_path, "different")
    paid = case.checkpoint
    evaluation = (
        case.cas.replacement.selected_evaluation if has_prior else case.cas.current_basis.evaluation
    )
    origin = SimpleNamespace(
        tenant_id=case.key.tenant_id,
        cell_id=case.key.cell_id,
        run_id="run-a",
        source_job_id=case.key.source_job_id,
        source_cycle=SimpleNamespace(
            design_problem_ref=case.key.design_problem_ref,
            selected_candidate_ref=case.key.candidate_id,
        ),
        n5_expectation=SimpleNamespace(input_ref=evaluation.input_ref),
    )
    selection = replace(case.selection, origin=origin)
    store = case.control._artifact_store

    def fixture_ref(label, kind):
        return store.put_json(
            {"fixture": label},
            artifacts.ArtifactWriteOptions(
                kind=kind,
                media_type="application/json",
                schema=artifacts.SchemaInfo(name=kind, version="1.0"),
            ),
            canon_spec=canon.CanonSpec(),
            return_selected_profile=True,
        )

    with _authenticated_tenant_scope(tenant_id=case.key.tenant_id, cell_id=case.key.cell_id):
        pa2_ref = fixture_ref("permission-kind-only", action._DECISION_KIND)
        evaluation_ref = fixture_ref(
            "evaluation-kind-only", "runtime_quality.acquisition_evaluation_decision"
        )
        basis_ref = fixture_ref("evaluated-basis", "runtime_quality.acquisition_evaluation_basis")
        prospective_ref = fixture_ref(
            "prospective-basis", "runtime_quality.acquisition_evaluation_basis"
        )
        pa2_selector = str(pa2_ref.artifact_id)
        prospective, evaluated, decision = object(), object(), object()
        calls = []
        monkeypatch.setattr(action, "_expected_phase", lambda *_a, **_k: object())
        monkeypatch.setattr(
            action, "persist_model_input_use_action_phase", lambda *_a: paid.phase_ref
        )
        monkeypatch.setattr(action, "_resolve_action_budget_window", lambda *_a, **_k: object())
        monkeypatch.setattr(
            action, "_materialize_semantic_successor", lambda *_a, **_k: paid.semantic_successor_ref
        )
        monkeypatch.setattr(
            action,
            "_build_model_input_use_n5_port",
            lambda *_a, **_k: SimpleNamespace(_controller=object()),
        )
        monkeypatch.setattr(action, "_read_generic_model_input_basis", lambda *_a: object())
        monkeypatch.setattr(action, "_run_model_input_use_n5", lambda *_a, **_k: paid)
        monkeypatch.setattr(action, "_issue_model_input_basis", lambda *_a, **_k: evaluated)
        monkeypatch.setattr(
            acquisition_evaluation,
            "issue_generic_model_input_evaluation_basis",
            lambda **kwargs: evaluated if kwargs["basis_role"] == "evaluated" else prospective,
        )
        monkeypatch.setattr(
            acquisition_evaluation,
            "compare_generic_model_input_evaluation_bases",
            lambda **_k: ("different", ()),
        )
        monkeypatch.setattr(
            acquisition_evaluation,
            "issue_generic_model_input_evaluation_decision",
            lambda **_k: decision,
        )
        monkeypatch.setattr(
            action,
            "_persist_generic_model_input_record",
            lambda _s, _e, value: evaluation_ref
            if value is decision
            else prospective_ref
            if value is prospective
            else basis_ref,
        )
        monkeypatch.setattr(
            acquisition_evaluation,
            "reconcile_generic_model_input_evaluation_completion",
            lambda **_k: evaluated,
        )

        def verify(selected_store, **kwargs):
            assert selected_store is store
            assert type(kwargs["authority_decision_ref"]) is str
            selected = action._selected_json_ref(
                store, kwargs["authority_decision_ref"], kind=action._DECISION_KIND
            )
            assert selected == pa2_ref
            calls.append(kwargs["authority_decision_ref"])
            return object()

        monkeypatch.setattr(action, "verify_model_input_use_result", verify)
        monkeypatch.setattr(action, "read_model_input_successor_selection", lambda *_a: object())
        monkeypatch.setattr(
            action, "_verify_selected_routing_use_decision_current", lambda *_a: None
        )
        with case.database.job_execution_fence(
            job_id=case.job.job_id, worker_id=case.worker, attempt=case.attempt
        ):
            completed = action.run_model_input_use_action(
                case.control,
                selection=selection,
                admission=case.database.current_execution_job_admission(),
                decision_ref=pa2_selector,
                currentness_resolver=lambda: True,
            )
        assert completed.evaluation_decision_ref == evaluation_ref
        assert calls == [pa2_selector]
        with pytest.raises(action.ModelInputSuccessorActionError, match="manifest_mismatch"):
            action._selected_json_ref(
                store, str(evaluation_ref.artifact_id), kind=action._DECISION_KIND
            )
