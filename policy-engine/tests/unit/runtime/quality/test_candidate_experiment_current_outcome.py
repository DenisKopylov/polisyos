"""Current-action projection over upstream owner adapters, without effects or authority.

These structural rows replace the upstream verification boundary for unit tests;
their construction does not establish signed history, source rights, or N5 work.
The served generation scenario remains the end-to-end authority/numerical test.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
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


def _record_operation_adapter(monkeypatch, bridge, context):
    """Expose the dispatch lifetime; the deep replay is an explicit upstream adapter."""
    state = {"active": None, "starts": 0, "closes": 0, "records": []}

    @contextmanager
    def read_operation(*_args):
        assert state["active"] is None
        state["starts"] += 1
        state["active"] = context
        try:
            yield context
        finally:
            state["active"] = None
            state["closes"] += 1

    def native_context(**_kwargs):
        assert state["active"] is None
        context = SimpleNamespace(controller=object())
        state["native_context"] = context
        return context

    def outside_operation(*_args):
        assert state["active"] is None

    monkeypatch.setattr(actions, "_candidate_experiment_reentry_read_operation", read_operation)
    monkeypatch.setattr(bridge, "_prepare_candidate_n5_native_context", native_context)
    monkeypatch.setattr(
        dispatch.CandidateExperimentEvaluationCurrentOwner, "revalidate", outside_operation
    )
    return state


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


def _selection_case_after_v2_prefix():
    """Build an exact owner-history prefix ending in V2, then a pending C phase."""
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
    )
    from tests.unit.runtime.quality.test_acquisition_route_loop import (
        _reuse_effective_source_case,
    )

    origin, _generation_run, _source_cycle, _last_history, _frontier = _reuse_effective_source_case(
        "candidate_evaluation_retained"
    )
    base_chain = origin.candidate_terminal_history_chain
    normalized_chain = []
    outcomes = []
    for generation, history in enumerate(base_chain, start=1):
        parent = replace(origin, candidate_terminal_history_chain=tuple(normalized_chain))
        history = replace(history, origin=parent)
        outcome = _outcome(history.terminal, generation)
        history = replace(history, head=outcome.head, phase_chain=outcome.phase_chain)
        outcomes.append(replace(outcome, candidate_experiment_terminal_history=history))
        normalized_chain.append(history)
    origin = replace(origin, candidate_terminal_history_chain=tuple(normalized_chain))

    predecessor = normalized_chain[-1]
    terminal = predecessor.terminal
    action_ref = _ref("runtime_quality.acquisition_candidate_action_receipt", "c")
    phase_values = {
        name: getattr(terminal, name)
        for name in AcquisitionCandidateExperimentPhaseReceipt.model_fields
        if hasattr(terminal, name)
    }
    phase_values.update(
        {
            "schema_version": "AcquisitionCandidateExperimentPhaseReceipt@1.0",
            "receipt_id": "component-pending-c",
            "job_id": "component-action-c",
            "action_generation": len(normalized_chain) + 1,
            "predecessor_receipt_ref": str(predecessor.terminal_ref.artifact_id),
            "owner_receipt_refs": (str(action_ref.artifact_id),),
            "coarse_phase": "candidate_input_prepared",
            "receipt_phase": "candidate_input_reentry_pending",
            "recovery_state": "reentry_recovery_required",
            "candidate_receipt_ref": action_ref,
        }
    )
    pending = AcquisitionCandidateExperimentPhaseReceipt.model_validate(phase_values)
    outcomes.append(_outcome(pending, len(normalized_chain) + 1))
    return origin, tuple(outcomes)


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


def test_current_outcome_accepts_exact_owner_replayed_v2_prefix_for_new_c() -> None:
    origin, outcomes = _selection_case_after_v2_prefix()

    assert len(origin.candidate_terminal_history_chain) == 2
    assert origin.candidate_terminal_history_chain[-1].terminal.schema_version == (
        "AcquisitionCandidateExperimentTerminalReceipt@2.0"
    )
    assert _select(origin, outcomes) is outcomes[-1]


def test_current_outcome_rejects_v2_terminal_with_an_unbound_reuse_profile() -> None:
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceiptV2,
    )

    origin, outcomes = _selection_case_after_v2_prefix()
    history = origin.candidate_terminal_history_chain[-1]
    assert type(history.terminal) is AcquisitionCandidateExperimentTerminalReceiptV2
    wrong_occurrence = _ref("runtime_quality.candidate_experiment_reuse_occurrence", "f")
    terminal = history.terminal.model_copy(update={"reuse_occurrence_ref": wrong_occurrence})
    history = replace(history, terminal=terminal)
    chain = (*origin.candidate_terminal_history_chain[:-1], history)
    origin = replace(origin, candidate_terminal_history_chain=chain)
    outcome = outcomes[-2]
    phase = replace(outcome.phase_chain[-1], receipt=terminal)
    outcome = replace(
        outcome,
        latest_receipt=terminal,
        phase_chain=(*outcome.phase_chain[:-1], phase),
        candidate_experiment_terminal_history=history,
    )
    outcomes = (*outcomes[:-2], outcome, outcomes[-1])

    with pytest.raises(ValueError, match="candidate_experiment_action_prefix_changed"):
        _select(origin, outcomes)


def test_current_outcome_rejects_v2_terminal_subclass() -> None:
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceiptV2,
    )

    class ExtendedTerminal(AcquisitionCandidateExperimentTerminalReceiptV2):
        extension: str

    origin, outcomes = _selection_case_after_v2_prefix()
    terminal = outcomes[-2].latest_receipt
    assert type(terminal) is AcquisitionCandidateExperimentTerminalReceiptV2
    extended = ExtendedTerminal.model_validate(
        {**terminal.model_dump(mode="python"), "extension": "unrecognized"}
    )
    outcomes = (*outcomes[:-2], replace(outcomes[-2], latest_receipt=extended), outcomes[-1])

    with pytest.raises(ValueError, match="candidate_experiment_action_prefix_changed"):
        _select(origin, outcomes)


@pytest.mark.parametrize(
    "stale_owner", ["head_ref", "head_scope", "phase_scope", "missing_profile"]
)
def test_candidate_dispatch_rejects_locator_that_differs_from_canonical_owner(
    monkeypatch: pytest.MonkeyPatch,
    stale_owner: str,
) -> None:
    """The head locator supplies a phase candidate; the full owner remains binding."""
    origin, outcomes = _selection_case(1)
    pending_ref = outcomes[-1].head.receipt_ref
    pending_phase = outcomes[-1].latest_receipt
    selection = object()
    action = SimpleNamespace(selection=selection)
    head = outcomes[-1].head
    phase = pending_phase
    if stale_owner == "head_ref":
        head = replace(head, receipt_ref=_hash("0"))
    elif stale_owner == "head_scope":
        head = replace(head, tenant_id="foreign-tenant")
    elif stale_owner == "phase_scope":
        phase = pending_phase.model_copy(update={"tenant_id": "foreign-tenant"})
    else:
        head = replace(head, receipt_manifest_profile_sha256=None)
    canonical_context = SimpleNamespace(
        head=head,
        phase=phase,
        action=action,
        selection=selection,
        outcome=outcomes[-1],
    )
    phase_reads = []
    full_outcome_reads = []
    sink = SimpleNamespace(
        _read_verified_action_phase=lambda receipt_ref: (
            phase_reads.append(receipt_ref) or outcomes[-1].phase_chain[-1]
        ),
        experiment_action_outcomes=lambda **kwargs: full_outcome_reads.append(kwargs),
    )
    store, event_log = object(), object()
    control_store = SimpleNamespace()
    service = object.__new__(ControlPlaneService)
    service._artifact_store, service._control_store = store, control_store
    bridge = object.__new__(AcquisitionWorldGrowthBridge)
    bridge.artifact_store, bridge.event_log = store, event_log
    bridge.control_store, bridge.action_head_sink = control_store, sink
    bridge._source_control_service = service
    monkeypatch.setattr(
        bridge,
        "_candidate_experiment_pending_reentry_locator_ref",
        lambda **_kwargs: pending_ref,
    )
    context_reads = []

    def canonical_replay(*args):
        context_reads.append(args)
        return canonical_context

    monkeypatch.setattr(
        actions, "_current_candidate_experiment_reentry_action_context", canonical_replay
    )
    monkeypatch.setattr(
        bridge,
        "_candidate_experiment_prior_owner",
        lambda **_kwargs: pytest.fail("stale pending owner reached prior-owner resolution"),
    )

    with pytest.raises(
        ValueError, match="candidate_experiment_evaluation_pending_action_not_current"
    ):
        dispatch.dispatch_candidate_experiment_evaluation(bridge=bridge, origin=origin)

    assert phase_reads == [pending_ref]
    assert len(context_reads) == 1
    assert context_reads[0][1:] == (origin, pending_ref, pending_phase.candidate_receipt_ref)
    assert full_outcome_reads == []


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
    full_outcome_reads = []

    def read_full_outcomes(**kwargs):
        full_outcome_reads.append(kwargs)
        return outcomes

    phase_record = outcomes[-1].phase_chain[-1]
    sink = SimpleNamespace(
        experiment_action_outcomes=read_full_outcomes,
        _read_verified_action_phase=lambda receipt_ref: phase_record,
    )
    service = object.__new__(ControlPlaneService)
    service._artifact_store, service._control_store = store, control_store
    bridge = object.__new__(AcquisitionWorldGrowthBridge)
    bridge.artifact_store, bridge.event_log = store, event_log
    bridge.control_store, bridge.action_head_sink = control_store, sink
    bridge._source_control_service = service
    pending_phase_ref = outcomes[-1].head.receipt_ref
    locator_calls = []

    def pending_locator(**kwargs):
        locator_calls.append(kwargs)
        return pending_phase_ref

    monkeypatch.setattr(
        bridge, "_candidate_experiment_pending_reentry_locator_ref", pending_locator
    )
    selection = object()
    action = SimpleNamespace(
        selection=selection,
        action_job_id=pending.job_id,
        action_generation=1,
        candidate_source_ref=_ref("runtime.quality.candidate_acquisition_source", "6"),
        limitations=("component_only_no_authority",),
        action_phase_ref=_hash("7"),
    )
    canonical_context = SimpleNamespace(
        head=outcomes[-1].head,
        phase=pending,
        action=action,
        selection=selection,
        outcome=outcomes[-1],
    )
    canonical_context_calls = []

    def current_reentry_context(*args):
        canonical_context_calls.append(args)
        return canonical_context

    monkeypatch.setattr(
        actions,
        "_current_candidate_experiment_reentry_action_context",
        current_reentry_context,
    )
    operation = _record_operation_adapter(monkeypatch, bridge, canonical_context)
    inputs = SimpleNamespace(configured_profile=SimpleNamespace(limitations=("candidate_only",)))
    prior_owner = SimpleNamespace(selected_evaluation=source_evaluation)
    window = SimpleNamespace(fresh_limit_usd=Decimal("1"), global_limit_usd=Decimal("5"))
    source_basis_calls = []

    def prepare_source_basis(**kwargs):
        source_basis_calls.append(kwargs)
        return (
            SimpleNamespace(predicate_provenance="recomputed", reason_codes=(), inputs=inputs),
            _ref("runtime_quality.acquisition_candidate_world_intent", "8"),
            object(),
        )

    monkeypatch.setattr(bridge, "_candidate_experiment_prior_owner", lambda **_kwargs: prior_owner)
    monkeypatch.setattr(
        bridge, "resolve_candidate_experiment_reentry_budget_window", lambda **_kwargs: window
    )
    monkeypatch.setattr(
        preparation,
        "prepare_live_candidate_experiment_source_basis_values",
        prepare_source_basis,
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

    def select_record(**kwargs):
        assert kwargs["_read_context"] is operation["active"] is canonical_context
        operation["records"].append(kwargs["record"])
        return _ref("component-record", "9")

    monkeypatch.setattr(dispatch, "_select_candidate_experiment_evaluation_artifact", select_record)
    monkeypatch.setattr(
        dispatch, "_candidate_experiment_decision_for_recovery", lambda **_kwargs: None
    )

    class FreshReentryDemandedError(Exception):
        pass

    def fresh_reentry(**kwargs):
        assert operation["active"] is None
        fresh_calls.append(kwargs)
        raise FreshReentryDemandedError

    monkeypatch.setattr(bridge, "_prepare_candidate_source_reentry_with_evaluation", fresh_reentry)
    assert origin.source_cycle.simulation.candidate_simulation_n5_input_ref is not None
    assert origin.candidate_terminal_history_chain == ()
    with pytest.raises(FreshReentryDemandedError):
        dispatch.dispatch_candidate_experiment_evaluation(bridge=bridge, origin=origin)
    assert locator_calls == [
        {
            "origin": origin,
            "unavailable_reason": "candidate_experiment_action_history_not_current",
        }
    ]
    assert len(canonical_context_calls) == 1
    assert canonical_context_calls[0] == (
        bridge,
        origin,
        pending_phase_ref,
        pending.candidate_receipt_ref,
    )
    assert full_outcome_reads == []
    assert source_basis_calls[0]["initial_reentry_context"] is canonical_context
    assert numerical_inputs == [source_evaluation]
    assert operation["starts"] == operation["closes"] == 1
    assert len(operation["records"]) == 2
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
            "native_context": operation["native_context"],
        }
    ]


def test_evaluation_owner_closes_shared_prefix_before_live_budget_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real owner keeps its pure-prefix lifetime out of the budget boundary.

    Upstream source/record producers are component adapters here; their actual
    CAS and carrier refusal controls live in the sibling record/read tests.
    No ledger observation or numerical result is fabricated by this test.
    """
    from polisyos.runtime.quality import substrate_registry
    from polisyos.runtime.quality.acquisition_world_growth import CandidateExperimentPriorOwner
    from polisyos.runtime.quality.cycle_substrate import (
        ConfiguredCandidateSimulationContextAdmissionOwner,
    )
    from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes
    from tests.unit.runtime.quality.test_candidate_experiment_read_operation import _Row

    @dataclass(frozen=True)
    class ComponentGenerationRun:
        cycles: tuple[object, ...]

    origin, outcomes = _selection_case(1)
    source_cycle = _Row("source-cycle")
    origin = replace(
        origin,
        source_cycle=source_cycle,
        generation_run=ComponentGenerationRun((source_cycle,)),
    )
    phase = outcomes[-1].latest_receipt
    selected = object()
    action = SimpleNamespace(candidate_source_ref=_ref("candidate-source", "6"))
    store = object()
    control = SimpleNamespace(read_acquisition_evaluation_frontier=lambda _key: None)
    service = object.__new__(ControlPlaneService)
    service._artifact_store, service._control_store = store, control
    bridge = object.__new__(AcquisitionWorldGrowthBridge)
    bridge.artifact_store, bridge.control_store = store, control
    bridge._source_control_service = service
    prepared = configuration.prepare_joint_simulation_configuration()
    prior_owner = CandidateExperimentPriorOwner(
        profile=None,
        model_declaration=None,
        context_owner=ConfiguredCandidateSimulationContextAdmissionOwner(
            profiles=(), model_declarations=(), store=store
        ),
        generation_run=origin.generation_run,
        source_cycle=origin.source_cycle,
        selected_evaluation=None,
        first_n4_source=None,
    )
    intent_ref = _ref("candidate-intent", "7")
    action_ref = _ref("candidate-action", "8")
    window = SimpleNamespace(fresh_limit_usd=Decimal("1"), global_limit_usd=Decimal("5"))
    context = SimpleNamespace(
        selection=selected,
        phase=phase,
        admission=SimpleNamespace(job=object()),
        action=action,
        budget_window=window,
    )
    operation = _record_operation_adapter(monkeypatch, bridge, context)
    inputs = object()
    current = SimpleNamespace(
        basis_role="prospective",
        preparation_inputs=inputs,
        prepared_n5_configuration=prepared,
        candidate_world_intent_ref=intent_ref,
        candidate_source_ref=action.candidate_source_ref,
        predicate_provenance="recomputed",
        reason_codes=(),
        effective_native_values_hex=exact_n5_content_bytes({"basis": "current"}).hex(),
        limitations=("component_only",),
    )
    decision = SimpleNamespace(
        candidate_action_ref=action_ref,
        candidate_world_intent_ref=intent_ref,
        candidate_source_ref=action.candidate_source_ref,
        comparison_result="not_established",
        predicate_provenance="not_established",
        reason_codes=("candidate_evaluation_prior_basis_not_established",),
        prior_basis_ref=None,
        prior_evaluation=None,
        expected_frontier_revision=0,
        expected_frontier_ref=None,
    )
    action.limitations = ()
    owner = dispatch.CandidateExperimentEvaluationCurrentOwner(
        bridge=bridge,
        origin=origin,
        selection=selected,
        pending_phase_ref=outcomes[-1].head.receipt_ref,
        action_phase_ref=_hash("9"),
        candidate_action_ref=action_ref,
        candidate_world_intent_ref=intent_ref,
        current_basis_ref=_ref("candidate-basis", "a"),
        decision_ref=_ref("candidate-decision", "b"),
        prior_owner=prior_owner,
        prepared_n5_configuration=prepared,
        budget_window=window,
        comparison="not_established",
    )
    monkeypatch.setattr(
        dispatch, "_candidate_experiment_reentry_execution_matches", lambda **_kwargs: True
    )
    monkeypatch.setattr(bridge, "_candidate_experiment_prior_owner", lambda **_kwargs: prior_owner)
    monkeypatch.setattr(
        dispatch, "_candidate_experiment_verified_prior_history", lambda **_kwargs: None
    )
    monkeypatch.setattr(dispatch, "_candidate_experiment_inherited_limitations", lambda _origin: ())

    def intent(**kwargs):
        assert kwargs["_read_context"] is operation["active"] is context
        return intent_ref, "same-intent"

    def source_values(**kwargs):
        assert kwargs["initial_reentry_context"] is operation["active"] is context
        return (
            SimpleNamespace(predicate_provenance="recomputed", reason_codes=(), inputs=inputs),
            intent_ref,
            "same-intent",
        )

    def record_pair(_owner, **kwargs):
        assert kwargs["_read_context"] is operation["active"] is context
        return current, decision

    monkeypatch.setattr(bridge, "_candidate_world_materialization_intent", intent)
    monkeypatch.setattr(
        preparation, "prepare_live_candidate_experiment_source_basis_values", source_values
    )
    monkeypatch.setattr(
        preparation,
        "_candidate_source_predecessors_for_verified_experiment_origin",
        lambda **_kwargs: (),
    )
    monkeypatch.setattr(
        dispatch, "_read_current_candidate_experiment_evaluation_records", record_pair
    )
    monkeypatch.setattr(
        dispatch,
        "recompute_candidate_acquisition_basis_values",
        lambda **_kwargs: ({"basis": "current"}, ()),
    )

    class BudgetBoundaryReachedError(Exception):
        pass

    def observe_budget(_owner):
        assert operation["active"] is None
        assert operation["starts"] == operation["closes"] == 1
        raise BudgetBoundaryReachedError

    monkeypatch.setattr(dispatch, "_candidate_experiment_budget_snapshot", observe_budget)
    # No catalog or final action read is reached after the deliberate boundary.
    monkeypatch.setattr(
        substrate_registry,
        "current_catalog_serving_source",
        lambda: pytest.fail("budget boundary escaped"),
    )
    with pytest.raises(BudgetBoundaryReachedError):
        dispatch._revalidate_candidate_experiment_evaluation_owner(owner)


@pytest.mark.parametrize("stale_fence_read", [None, "head", "phase"])
@pytest.mark.parametrize("reentry_evaluation_mode", ["not_simulated", "verified", "fallback"])
def test_candidate_experiment_dispatch_rechecks_typed_pending_head_before_terminal_write(
    monkeypatch: pytest.MonkeyPatch,
    stale_fence_read: str | None,
    reentry_evaluation_mode: str,
) -> None:
    """Use the exact current context at admission and both terminal fences.

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
        selection=selection,
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
        if len(reads) != 2 or stale_fence_read is None:
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
    pending_phase_ref = predecessor.receipt_ref
    phase_record = outcomes[-1].phase_chain[-1]
    monkeypatch.setattr(
        sink,
        "_read_verified_action_phase",
        lambda receipt_ref: phase_record,
        raising=False,
    )
    monkeypatch.setattr(
        bridge,
        "_candidate_experiment_pending_reentry_locator_ref",
        lambda **_kwargs: pending_phase_ref,
    )
    source_evaluation = object()
    prior_owner = SimpleNamespace(selected_evaluation=source_evaluation)
    window = SimpleNamespace(
        fresh_limit_usd=Decimal("1"),
        global_limit_usd=Decimal("5"),
        effective_limit_usd=Decimal("5"),
        scope=SimpleNamespace(run_binding="run-binding"),
    )
    current_context = SimpleNamespace(
        head=predecessor,
        phase=pending,
        admission=admission,
        action=action,
        selection=selection,
        outcome=outcomes[-1],
        budget_window=window,
    )
    monkeypatch.setattr(
        actions,
        "_current_candidate_experiment_reentry_action_context",
        lambda *_args: current_context,
    )
    operation = _record_operation_adapter(monkeypatch, bridge, current_context)

    def persist_terminal(terminal):
        assert operation["active"] is None
        persisted.append(terminal)
        return "terminal-head"

    sink.persist_terminal = persist_terminal
    inputs = SimpleNamespace(configured_profile=SimpleNamespace(limitations=("candidate_only",)))
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
    monkeypatch.setattr(configuration, "prepare_joint_simulation_configuration", lambda: object())
    monkeypatch.setattr(
        dispatch, "_candidate_experiment_verified_prior_history", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        preparation,
        "_candidate_source_predecessors_for_verified_experiment_origin",
        lambda **_kwargs: (),
    )

    recomputations = 0
    reentry_priors: list[object] = []

    def recompute(**kwargs):
        nonlocal recomputations
        recomputations += 1
        if recomputations == 1:
            return {"basis": "current"}, ()
        reentry_priors.append(kwargs["prior"])
        return {"basis": "reentry"}, ("candidate_reentry_n5_not_established",)

    monkeypatch.setattr(dispatch, "recompute_candidate_acquisition_basis_values", recompute)
    monkeypatch.setattr(
        records,
        "issue_candidate_acquisition_evaluation_basis",
        lambda **kwargs: SimpleNamespace(record_kind="basis", limitations=kwargs["limitations"]),
    )
    monkeypatch.setattr(
        records,
        "issue_candidate_acquisition_evaluation_decision",
        lambda **_kwargs: SimpleNamespace(record_kind="decision"),
    )

    def selected_record_ref(**kwargs):
        if kwargs.get("_read_context") is not None:
            assert kwargs["_read_context"] is operation["active"] is current_context
            operation["records"].append(kwargs["record"])
        else:
            assert operation["active"] is None
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
    budget_state = SimpleNamespace(limits={"run": SimpleNamespace(max_usd=Decimal("5"))})
    budget_observation = SimpleNamespace(run_binding="run-binding")

    def budget_snapshot(_owner):
        assert operation["active"] is None
        return budget_state, budget_observation

    monkeypatch.setattr(
        dispatch.CandidateExperimentEvaluationCurrentOwner,
        "current_budget_snapshot",
        budget_snapshot,
    )
    continued_generation_run = object()
    reentry = SimpleNamespace(
        continued_generation_run=continued_generation_run,
        new_cycle=SimpleNamespace(
            simulation=SimpleNamespace(
                status=(
                    "not_simulated"
                    if reentry_evaluation_mode == "not_simulated"
                    else "joint_simulated"
                )
            )
        ),
        data_snapshot_ref=_ref("runtime.data_snapshot", "a"),
        world_model_ref=_ref("runtime.world_model", "b"),
        limitations=("component_only_no_n5",),
    )
    reentry_ref = _ref("runtime_quality.candidate_source_reentry_receipt", "c")
    resolved_reentry_evaluation = SimpleNamespace(result=SimpleNamespace(diagnostics={}))
    fallback_reentry_evaluation = SimpleNamespace(result=SimpleNamespace(diagnostics={}))
    resolution_calls: list[object] = []
    preparation_calls: list[dict[str, object]] = []

    def resolve_fallback(**kwargs: object) -> object:
        resolution_calls.append(kwargs)
        return fallback_reentry_evaluation

    def prepare_reentry(**kwargs: object) -> tuple[object, object, object | None]:
        assert operation["active"] is None
        preparation_calls.append(kwargs)
        return (
            reentry_ref,
            reentry,
            resolved_reentry_evaluation if reentry_evaluation_mode == "verified" else None,
        )

    monkeypatch.setattr(records, "resolve_selected_acquisition_evaluation_parts", resolve_fallback)
    monkeypatch.setattr(
        bridge,
        "_prepare_candidate_source_reentry_with_evaluation",
        prepare_reentry,
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

    assert len(reads) == 2
    assert operation["starts"] == operation["closes"] == 1
    assert len(operation["records"]) == 2
    assert all(read["verified_origin"] is origin for read in reads)
    assert len(owner_checks) == 2
    assert len(preparation_calls) == 1
    assert reentry_priors == [
        resolved_reentry_evaluation
        if reentry_evaluation_mode == "verified"
        else fallback_reentry_evaluation
        if reentry_evaluation_mode == "fallback"
        else None
    ]
    assert len(resolution_calls) == (1 if reentry_evaluation_mode == "fallback" else 0)
    if reentry_evaluation_mode != "fallback":
        assert resolution_calls == []
    else:
        assert resolution_calls == [
            {
                "artifact_store": bridge.artifact_store,
                "control_store": bridge.control_store,
                "tenant_id": origin.tenant_id,
                "cell_id": origin.cell_id,
                "run_id": origin.run_id,
                "generation_run": continued_generation_run,
                "source_cycle": reentry.new_cycle,
                "design_problem_ref": origin.policy_scope.design_problem_ref,
            }
        ]
