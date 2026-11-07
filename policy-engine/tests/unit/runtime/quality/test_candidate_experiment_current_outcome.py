"""Current-action projection over upstream owner adapters, without effects or authority.

These structural rows replace the upstream verification boundary for unit tests;
their construction does not establish signed history, source rights, or N5 work.
The served generation scenario remains the end-to-end authority/numerical test.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from polisyos.runtime.http.services.control.run_lifecycle import (
    ControlPlaneService,
    VerifiedAcquisitionActionOutcome,
    VerifiedAcquisitionActionPhase,
)
from polisyos.runtime.http.services.control_plane_store import AcquisitionActionHeadRecord
from polisyos.runtime.quality import acquisition_evaluation as records
from polisyos.runtime.quality import acquisition_evaluation_dispatch as dispatch
from polisyos.runtime.quality import candidate_acquisition_action as actions
from polisyos.runtime.quality import candidate_source_basis as preparation
from polisyos.runtime.quality import joint_simulation_horizon as configuration
from polisyos.runtime.quality.acquisition_evaluation import CandidateExperimentTerminalHistory
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentPhaseReceipt,
    AcquisitionCandidateExperimentTerminalReceipt,
    VerifiedCandidateExperimentOrigin,
)
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
from tests.unit.runtime.quality.test_candidate_experiment_terminal_history import (
    _hash,
    _ref,
    _requested_phase,
)


def _outcome(phase, generation: int) -> VerifiedAcquisitionActionOutcome:
    receipt_ref = _hash(str(generation))
    head = AcquisitionActionHeadRecord(
        tenant_id=phase.tenant_id,
        cell_id=phase.cell_id,
        run_id=phase.run_id,
        source_job_id=phase.source_job_id,
        route_id=phase.route_id,
        action_generation=generation,
        head_generation=5 if phase.receipt_phase == "terminal" else 4,
        receipt_ref=receipt_ref,
        receipt_sha256=receipt_ref,
        durable_event_id=f"component-event-{generation}",
        coarse_phase=phase.coarse_phase,
        receipt_phase=phase.receipt_phase,
        recovery_state=phase.recovery_state,
        job_id=phase.job_id,
        predecessor_receipt_ref=phase.predecessor_receipt_ref,
        created_at=datetime(2026, 11, 5, tzinfo=UTC),
        receipt_manifest_profile_sha256=_hash("f"),
    )
    row = VerifiedAcquisitionActionPhase(
        receipt_ref=receipt_ref,
        receipt=phase,
        durable_event_id=head.durable_event_id,
        event=None,
    )
    return VerifiedAcquisitionActionOutcome(
        head=head,
        latest_receipt=phase,
        executing_phase_ref=None,
        executing_phase=None,
        selection_phase_ref=None,
        selection_phase=None,
        phase_chain=(row,),
    )


def _selection_case(generation: int):
    requested = _requested_phase()
    root_cycle = SimpleNamespace(
        selected_candidate_ref=requested.policy_scope.candidate_id,
        selected_candidate_content_hash=requested.policy_scope.candidate_content_hash,
        simulation=SimpleNamespace(candidate_simulation_n5_input_ref=_ref("source-n5", "a")),
    )
    origin = VerifiedCandidateExperimentOrigin(
        schema_version="polisyos.runtime.candidate_experiment_origin.v1",
        tenant_id=requested.tenant_id,
        cell_id=requested.cell_id,
        run_id=requested.run_id,
        source_job_id=requested.source_job_id,
        source_payload_ref=requested.source_payload_ref,
        capability_manifest_ref=requested.capability_manifest_ref,
        request_content_hash=requested.request_content_hash,
        route_id=requested.route_id,
        policy_ref=requested.policy_ref,
        policy_scope=requested.policy_scope,
        generation_run=SimpleNamespace(cycles=(root_cycle,)),
        source_cycle=root_cycle,
        design_problem_basis=SimpleNamespace(),
        planner_report=None,
        planner_record=None,
    )
    action_ref = _ref("runtime_quality.acquisition_candidate_action_receipt", "a")
    reentry_ref = _ref("runtime_quality.candidate_source_reentry_receipt", "b")
    decision_ref = _ref("runtime_quality.acquisition_evaluation_decision", "c")
    basis_ref = _ref("runtime_quality.acquisition_evaluation_basis", "d")
    identity = requested.model_dump(
        exclude={
            "schema_version",
            "coarse_phase",
            "receipt_phase",
            "recovery_state",
            "candidate_receipt_ref",
        }
    )
    outcomes = []
    history_chain = []
    for prior_generation in range(1, generation):
        terminal = AcquisitionCandidateExperimentTerminalReceipt(
            **{
                **identity,
                "receipt_id": f"component-terminal-{prior_generation}",
                "job_id": f"component-action-{prior_generation}",
                "action_generation": prior_generation,
                "predecessor_receipt_ref": _hash("e"),
                "owner_receipt_refs": (str(action_ref.artifact_id), str(decision_ref.artifact_id)),
            },
            terminal_outcome="candidate_reentry_completed",
            candidate_action_ref=action_ref,
            candidate_reentry_ref=reentry_ref,
            evaluation_decision_ref=decision_ref,
            selected_basis_ref=basis_ref,
            selected_evaluation_witness_ref=reentry_ref,
        )
        outcome = _outcome(terminal, prior_generation)
        history = CandidateExperimentTerminalHistory(
            head=outcome.head,
            terminal_ref=_ref(
                "runtime_quality.acquisition_route_loop_receipt", str(prior_generation)
            ),
            terminal=terminal,
            origin=replace(origin, candidate_terminal_history_chain=tuple(history_chain)),
            phase_chain=outcome.phase_chain,
            action=None,
            source=None,
            budget_window=None,
            decision=None,
            current_basis=None,
            selected_basis=None,
            evaluation=None,
            reentry=None,
            continuation=None,
            frontier_before=None,
            frontier_after=None,
        )
        outcomes.append(replace(outcome, candidate_experiment_terminal_history=history))
        history_chain.append(history)
    origin = replace(origin, candidate_terminal_history_chain=tuple(history_chain))
    pending = AcquisitionCandidateExperimentPhaseReceipt(
        **{
            **identity,
            "receipt_id": f"component-pending-{generation}",
            "job_id": f"component-action-{generation}",
            "action_generation": generation,
            "predecessor_receipt_ref": _hash("e"),
            "owner_receipt_refs": (str(action_ref.artifact_id),),
        },
        coarse_phase="candidate_input_prepared",
        receipt_phase="candidate_input_reentry_pending",
        recovery_state="reentry_recovery_required",
        candidate_receipt_ref=action_ref,
    )
    outcomes.append(_outcome(pending, generation))
    return origin, tuple(outcomes)


def _select(origin, outcomes):
    last = outcomes[-1]
    return actions._select_current_candidate_experiment_outcome(
        outcomes,
        origin=origin,
        action_job_id=last.head.job_id,
        action_generation=len(origin.candidate_terminal_history_chain) + 1,
        receipt_ref=last.head.receipt_ref,
        required_phase="candidate_input_reentry_pending",
    )


@pytest.mark.parametrize("generation", [1, 2, 4])
def test_current_outcome_selects_latest_exact_generation_without_effects(
    generation: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )

    def no_effect(*_args, **_kwargs):
        pytest.fail("current action selection attempted physical work")

    monkeypatch.setattr(configuration.JointSimulationHorizonController, "run", no_effect)
    monkeypatch.setattr(
        WorldBankWDIAcquisitionExecutionPort, "execute_candidate_experiment", no_effect
    )
    origin, outcomes = _selection_case(generation)
    assert _select(origin, outcomes) is outcomes[-1]


@pytest.mark.parametrize("corruption", ["missing", "duplicate", "order", "foreign", "prefix"])
def test_current_outcome_refuses_changed_complete_prefix(corruption: str) -> None:
    origin, outcomes = _selection_case(4)
    if corruption == "missing":
        outcomes = outcomes[1:]
    elif corruption == "duplicate":
        outcomes = (*outcomes[:2], outcomes[1], outcomes[-1])
    elif corruption == "order":
        outcomes = (outcomes[1], outcomes[0], *outcomes[2:])
    elif corruption == "foreign":
        outcomes = (
            *outcomes[:-1],
            replace(outcomes[-1], head=replace(outcomes[-1].head, cell_id="foreign")),
        )
    else:
        outcomes = (replace(outcomes[0], candidate_experiment_terminal_history=None), *outcomes[1:])
    with pytest.raises(ValueError, match="candidate_experiment_action_"):
        _select(origin, outcomes)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("action_job_id", "stale-job"),
        ("receipt_ref", _hash("0")),
        ("required_phase", "executing"),
        ("action_generation", 2),
    ],
)
def test_current_outcome_refuses_stale_current_action(field: str, value: object) -> None:
    origin, outcomes = _selection_case(4)
    expected = {
        "origin": origin,
        "action_job_id": outcomes[-1].head.job_id,
        "action_generation": 4,
        "receipt_ref": outcomes[-1].head.receipt_ref,
        "required_phase": "candidate_input_reentry_pending",
    }
    expected[field] = value
    with pytest.raises(ValueError, match="candidate_experiment_action_"):
        actions._select_current_candidate_experiment_outcome(outcomes, **expected)


def test_original_source_n5_does_not_retain_first_experiment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatch demands fresh reentry; the numerical boundary is not simulated here."""
    origin, outcomes = _selection_case(1)
    pending = outcomes[-1].latest_receipt
    source_evaluation = object()
    configuration_value = object()
    records_seen = []
    numerical_inputs = []
    fresh_calls = []
    store, event_log = object(), object()
    control_store = SimpleNamespace(
        current_execution_job_admission=lambda: SimpleNamespace(
            job=SimpleNamespace(job_id=pending.job_id)
        ),
        read_acquisition_evaluation_frontier=lambda _key: None,
    )
    sink = SimpleNamespace(experiment_action_outcomes=lambda **_kwargs: outcomes)
    service = object.__new__(ControlPlaneService)
    service._artifact_store, service._control_store = store, control_store
    bridge = object.__new__(AcquisitionWorldGrowthBridge)
    bridge.artifact_store, bridge.event_log = store, event_log
    bridge.control_store, bridge.action_head_sink = control_store, sink
    bridge._source_control_service = service
    action = SimpleNamespace(
        action_job_id=pending.job_id,
        action_generation=1,
        candidate_source_ref=_ref("runtime.quality.candidate_acquisition_source", "6"),
        limitations=("component_only_no_authority",),
        action_phase_ref=_hash("7"),
    )
    inputs = SimpleNamespace(configured_profile=SimpleNamespace(limitations=("candidate_only",)))
    prior_owner = SimpleNamespace(selected_evaluation=source_evaluation)
    window = SimpleNamespace(fresh_limit_usd=Decimal("1"), global_limit_usd=Decimal("5"))
    monkeypatch.setattr(bridge, "_candidate_experiment_prior_owner", lambda **_kwargs: prior_owner)
    monkeypatch.setattr(
        bridge, "resolve_candidate_experiment_reentry_budget_window", lambda **_kwargs: window
    )
    monkeypatch.setattr(
        actions,
        "_current_candidate_experiment_reentry_action",
        lambda *_args: (object(), pending, None, action),
    )
    monkeypatch.setattr(
        preparation,
        "prepare_live_candidate_experiment_source_basis_values",
        lambda **_kwargs: (
            SimpleNamespace(predicate_provenance="recomputed", reason_codes=(), inputs=inputs),
            _ref("runtime_quality.acquisition_candidate_world_intent", "8"),
            object(),
        ),
    )
    monkeypatch.setattr(
        configuration, "prepare_joint_simulation_configuration", lambda: configuration_value
    )
    monkeypatch.setattr(
        dispatch, "_candidate_experiment_verified_prior_history", lambda **_kwargs: None
    )

    def recompute(**kwargs):
        numerical_inputs.append(kwargs["prior"])
        return {"source_numeric_context": "preserved"}, ()

    def issue_basis(**kwargs):
        records_seen.append(("basis", kwargs))
        return SimpleNamespace(limitations=kwargs["limitations"])

    def issue_decision(**kwargs):
        records_seen.append(("decision", kwargs))
        return SimpleNamespace()

    monkeypatch.setattr(dispatch, "recompute_candidate_acquisition_basis_values", recompute)
    monkeypatch.setattr(records, "issue_candidate_acquisition_evaluation_basis", issue_basis)
    monkeypatch.setattr(records, "issue_candidate_acquisition_evaluation_decision", issue_decision)
    monkeypatch.setattr(
        dispatch,
        "_select_candidate_experiment_evaluation_artifact",
        lambda **_kwargs: _ref("component-record", "9"),
    )
    monkeypatch.setattr(
        dispatch, "_candidate_experiment_decision_for_recovery", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        dispatch.CandidateExperimentEvaluationCurrentOwner, "revalidate", lambda _self: None
    )

    class FreshReentryDemandedError(Exception):
        pass

    def fresh_reentry(**kwargs):
        fresh_calls.append(kwargs)
        raise FreshReentryDemandedError

    monkeypatch.setattr(bridge, "prepare_candidate_experiment_source_reentry", fresh_reentry)
    assert origin.source_cycle.simulation.candidate_simulation_n5_input_ref is not None
    assert origin.candidate_terminal_history_chain == ()
    with pytest.raises(FreshReentryDemandedError):
        dispatch.dispatch_candidate_experiment_evaluation(bridge=bridge, origin=origin)
    assert numerical_inputs == [source_evaluation]
    decision = next(values for kind, values in records_seen if kind == "decision")
    assert decision["comparison_result"] == "not_established"
    assert decision["prior_basis_ref"] is None
    assert decision["prior_evaluation"] is None
    assert decision["expected_frontier_revision"] == 0
    assert fresh_calls == [
        {
            "origin": origin,
            "candidate_action_ref": pending.candidate_receipt_ref,
            "prepared_n5_configuration": configuration_value,
        }
    ]


@pytest.mark.parametrize("stale_fence_read", [None, "head", "phase"])
def test_candidate_experiment_dispatch_rechecks_typed_pending_head_before_terminal_write(
    monkeypatch: pytest.MonkeyPatch,
    stale_fence_read: str | None,
) -> None:
    """Use the experiment reader at admission and both terminal fences.

    The synthetic owner below scopes this test to dispatch selection and the final
    writer boundary. Numerical source reentry and deep live-owner replay remain
    covered by the served terminal-recovery integration test.
    """
    origin, outcomes = _selection_case(1)
    pending = outcomes[-1].latest_receipt
    assert type(pending) is AcquisitionCandidateExperimentPhaseReceipt
    predecessor = outcomes[-1].head
    store, event_log = object(), object()
    selection = SimpleNamespace()
    action = SimpleNamespace(
        action_job_id=pending.job_id,
        action_generation=pending.action_generation,
        candidate_source_ref=_ref("runtime.quality.candidate_acquisition_source", "6"),
        limitations=("component_only_no_authority",),
        action_phase_ref=_hash("7"),
    )
    admission = SimpleNamespace(job=SimpleNamespace(job_id=pending.job_id))
    control_store = SimpleNamespace(
        current_execution_job_admission=lambda: admission,
        read_acquisition_evaluation_frontier=lambda _key: None,
    )

    reads: list[dict[str, object]] = []
    persisted: list[object] = []

    def experiment_action_outcomes(**kwargs):
        reads.append(kwargs)
        if len(reads) != 3 or stale_fence_read is None:
            return outcomes
        if stale_fence_read == "head":
            return (
                *outcomes[:-1],
                replace(
                    outcomes[-1],
                    head=replace(
                        outcomes[-1].head,
                        receipt_ref=_hash("0"),
                        receipt_sha256=_hash("0"),
                    ),
                ),
            )
        return (
            *outcomes[:-1],
            replace(
                outcomes[-1],
                head=replace(outcomes[-1].head, receipt_phase="outcome_selected"),
            ),
        )

    def forbidden_costed_reader(**_kwargs):
        pytest.fail("candidate experiment dispatch used the costed action reader")

    sink = SimpleNamespace(
        experiment_action_outcomes=experiment_action_outcomes,
        current_action_outcome=forbidden_costed_reader,
        get_head=lambda _terminal: predecessor,
        recover_candidate_experiment_terminal=lambda *_args, **_kwargs: None,
        persist_terminal=lambda terminal: persisted.append(terminal) or "terminal-head",
    )
    service = object.__new__(ControlPlaneService)
    service._artifact_store, service._control_store = store, control_store
    bridge = object.__new__(AcquisitionWorldGrowthBridge)
    bridge.artifact_store, bridge.event_log = store, event_log
    bridge.control_store, bridge.action_head_sink = control_store, sink
    bridge._source_control_service = service
    source_evaluation = object()
    prior_owner = SimpleNamespace(selected_evaluation=source_evaluation)
    window = SimpleNamespace(
        fresh_limit_usd=Decimal("1"),
        global_limit_usd=Decimal("5"),
        effective_limit_usd=Decimal("5"),
        scope=SimpleNamespace(run_binding="run-binding"),
    )
    inputs = SimpleNamespace(
        configured_profile=SimpleNamespace(limitations=("candidate_only",))
    )
    monkeypatch.setattr(bridge, "_candidate_experiment_prior_owner", lambda **_kwargs: prior_owner)
    monkeypatch.setattr(
        bridge,
        "resolve_candidate_experiment_reentry_budget_window",
        lambda **_kwargs: window,
    )
    monkeypatch.setattr(
        actions,
        "_current_candidate_experiment_reentry_action",
        lambda *_args: (selection, pending, admission, action),
    )
    monkeypatch.setattr(
        preparation,
        "prepare_live_candidate_experiment_source_basis_values",
        lambda **_kwargs: (
            SimpleNamespace(predicate_provenance="recomputed", reason_codes=(), inputs=inputs),
            _ref("runtime_quality.acquisition_candidate_world_intent", "8"),
            object(),
        ),
    )
    monkeypatch.setattr(
        configuration, "prepare_joint_simulation_configuration", lambda: object()
    )
    monkeypatch.setattr(
        dispatch, "_candidate_experiment_verified_prior_history", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        preparation,
        "_candidate_source_predecessors_for_verified_experiment_origin",
        lambda **_kwargs: (),
    )

    recomputations = 0

    def recompute(**_kwargs):
        nonlocal recomputations
        recomputations += 1
        if recomputations == 1:
            return {"basis": "current"}, ()
        return {"basis": "reentry"}, ("candidate_reentry_n5_not_established",)

    monkeypatch.setattr(dispatch, "recompute_candidate_acquisition_basis_values", recompute)
    monkeypatch.setattr(
        records,
        "issue_candidate_acquisition_evaluation_basis",
        lambda **kwargs: SimpleNamespace(
            record_kind="basis", limitations=kwargs["limitations"]
        ),
    )
    monkeypatch.setattr(
        records,
        "issue_candidate_acquisition_evaluation_decision",
        lambda **_kwargs: SimpleNamespace(record_kind="decision"),
    )

    def selected_record_ref(**kwargs):
        kind = (
            "runtime_quality.acquisition_evaluation_decision"
            if kwargs["record"].record_kind == "decision"
            else "runtime_quality.acquisition_evaluation_basis"
        )
        return _ref(kind, "9")

    monkeypatch.setattr(
        dispatch,
        "_select_candidate_experiment_evaluation_artifact",
        selected_record_ref,
    )
    monkeypatch.setattr(
        dispatch, "_candidate_experiment_decision_for_recovery", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        dispatch.CandidateExperimentEvaluationCurrentOwner, "revalidate", lambda _self: None
    )
    budget_state = SimpleNamespace(limits={"run": SimpleNamespace(max_usd=Decimal("5"))})
    budget_observation = SimpleNamespace(run_binding="run-binding")
    monkeypatch.setattr(
        dispatch.CandidateExperimentEvaluationCurrentOwner,
        "current_budget_snapshot",
        lambda _self: (budget_state, budget_observation),
    )
    reentry = SimpleNamespace(
        new_cycle=SimpleNamespace(simulation=SimpleNamespace(status="not_simulated")),
        data_snapshot_ref=_ref("runtime.data_snapshot", "a"),
        world_model_ref=_ref("runtime.world_model", "b"),
        limitations=("component_only_no_n5",),
    )
    reentry_ref = _ref("runtime_quality.candidate_source_reentry_receipt", "c")
    monkeypatch.setattr(
        bridge,
        "prepare_candidate_experiment_source_reentry",
        lambda **_kwargs: (reentry_ref, reentry),
    )

    owner_checks: list[object] = []

    def scoped_owner_revalidation(owner):
        assert type(owner) is dispatch.CandidateExperimentReentryOwner
        assert owner.predecessor_head == predecessor
        assert owner.terminal.predecessor_receipt_ref == predecessor.receipt_ref
        owner_checks.append(owner)

    monkeypatch.setattr(
        dispatch, "_revalidate_candidate_experiment_reentry_owner", scoped_owner_revalidation
    )

    assert origin.candidate_terminal_history_chain == ()
    if stale_fence_read is None:
        assert dispatch.dispatch_candidate_experiment_evaluation(bridge=bridge, origin=origin) == (
            "terminal-head"
        )
        assert len(persisted) == 1
        assert type(persisted[0]) is AcquisitionCandidateExperimentTerminalReceipt
    else:
        with pytest.raises(ValueError, match="candidate_experiment_action_phase_not_current"):
            dispatch.dispatch_candidate_experiment_evaluation(bridge=bridge, origin=origin)
        assert persisted == []

    assert len(reads) == 3
    assert all(read["verified_origin"] is origin for read in reads)
    assert len(owner_checks) == 2
