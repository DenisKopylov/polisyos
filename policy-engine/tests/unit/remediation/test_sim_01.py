"""Behavioral witnesses for SIM-01 engine selection and execution binding."""

from __future__ import annotations

import pytest

from polisyos.foundry.methods import SlotType
from polisyos.foundry.methods.catalog.simulation import ensure_simulation_methods_registered
from polisyos.runtime.quality.generation_cycle import _joint_simulation_port_outcome
from polisyos.runtime.quality.joint_simulation_horizon import (
    EngineDecision,
    EnginePlan,
    HorizonSpec,
    JointSimulationControllerError,
    JointSimulationHorizonController,
    JointSimulationRequest,
    SimulationTrajectory,
    TrajectoryPoint,
    _system_dynamics_state_for_subset,
)
from polisyos.runtime.quality.recursive_generation_cycle import _joint_simulation_is_unsupported
from tests.unit.runtime.quality.test_joint_simulation_horizon import (
    _atom,
    _coupling_graph,
    _request,
)


def _coupled_plan() -> EnginePlan:
    return EnginePlan(
        engine_kind="coupled_des_abm",
        objective_ref="objective://claims-queue-fallback",
        eligibility_conditions=(
            "unemployment_claims",
            "benefit_queue",
            "service_queue",
        ),
        variable_map={
            "agents.income": "benefit_amount",
            "government.balance": "service_rate",
        },
        coupled_state={
            "initial_income": [1000.0, 600.0, 400.0],
            "initial_savings": [0.0, 0.0, 0.0],
            "is_employed": [0.0, 0.0, 0.0],
        },
        coupled_params={
            "benefit_amount": 0.0,
            "service_rate": 0.5,
            "initial_queue_length": 0.0,
            "seed": 7,
        },
    )


def _trajectory(
    *,
    engine_kind: str = "ncm_parallel_worlds",
    method_fqn: str = "polisyos.foreign.engine@9.9.9",
    objective_ref: str = "objective://foreign-plan",
    physical_run_ref: str = "sha256:" + "f" * 64,
) -> SimulationTrajectory:
    return SimulationTrajectory(
        run_level="joint",
        atom_ids=("income_subsidy", "balance_grant"),
        engine_kind=engine_kind,  # type: ignore[arg-type]
        method_fqn=method_fqn,
        objective_ref=objective_ref,
        points=(
            TrajectoryPoint(
                step=0,
                outcomes={"firm_survival": 2.0},
                effect={"firm_survival": 1.0},
            ),
        ),
        diagnostics={"physical_run_ref": physical_run_ref},
    )


def test_unsupported_first_engine_falls_back_to_supported_second() -> None:
    """B07: coupling rejection must continue selection through the plan list."""

    request = _request(policy_domain="unemployment_claims_benefit").model_copy(
        update={
            "coupling_graph": _coupling_graph("shared_resource"),
            "selected_outcomes": ("final_queue_length",),
            "baseline_state": {"final_queue_length": 0.0},
            "horizon": HorizonSpec(start=0, end=0),
            "engine_plan": (_request().engine_plan[0], _coupled_plan()),
        }
    )

    result = JointSimulationHorizonController().run(request)

    assert [item.decision for item in result.engine_decisions] == ["unsupported", "selected"]
    assert result.engine_decisions[0].reason == "coupling_composition_gate_unsupported"
    assert result.engine_decisions[1].engine_kind == "coupled_des_abm"
    assert result.engine_decisions[1].decision == "selected"
    assert result.trajectories
    assert all(
        trajectory.engine_kind == "coupled_des_abm" for trajectory in result.trajectories
    )
    status, blockers = _joint_simulation_port_outcome(result)
    assert status == "joint_simulated"
    assert _joint_simulation_is_unsupported(result) is False
    assert "n5_coupling_blocked" not in blockers


def test_all_engine_candidates_incompatible_return_typed_rejection() -> None:
    """B07: no coupling-compatible candidate remains a typed no-run refusal."""

    first = _coupled_plan().model_copy(
        update={"declared_equilibrium_semantics": "game_model"}
    )
    second = _request().engine_plan[0]
    request = _request(policy_domain="unemployment_claims_benefit").model_copy(
        update={
            "coupling_graph": _coupling_graph("shared_resource"),
            "horizon": HorizonSpec(start=0, end=0),
            "engine_plan": (first, second),
        }
    )

    result = JointSimulationHorizonController().run(request)

    assert len(result.engine_decisions) == 2
    assert all(item.decision == "unsupported" for item in result.engine_decisions)
    assert [item.reason for item in result.engine_decisions] == [
        "equilibrium_semantics_not_backed_by_engine",
        "coupling_composition_gate_unsupported",
    ]
    assert not result.trajectories
    assert result.receipt.calibration_status == "unsupported_coupling_gated"
    assert result.feedback_classification.support_status == "unsupported"
    assert result.feedback_classification.engine_supported is False
    assert "unsupported_coupling_class:shared_resource" in (
        result.feedback_classification.support_blockers
    )
    assert "all_engine_candidates_rejected" in result.feedback_classification.support_blockers
    assert "declared_semantics_unbacked:game_model" in (
        result.feedback_classification.limitations
    )
    assert result.diagnostics["unsupported_objectives"] == [
        first.objective_ref,
        second.objective_ref,
    ]
    assert [
        item["reason"] for item in result.diagnostics["unsupported_reasons"]
    ] == [
        "equilibrium_semantics_not_backed_by_engine",
        "coupling_composition_gate_unsupported",
    ]
    assert {
        item["reason"] for item in result.content_bound_payload()["engine_decisions"]
    } == {
        "equilibrium_semantics_not_backed_by_engine",
        "coupling_composition_gate_unsupported",
    }
    assert result.diagnostics["coupling_support_status"] == "unsupported"
    assert result.diagnostics["coupling_gate_blocked"] is True
    status, blockers = _joint_simulation_port_outcome(result)
    assert status == "simulation_blocked"
    assert _joint_simulation_is_unsupported(result) is True
    assert "unsupported_coupling_class:shared_resource" in blockers

    no_coupling_request = _request(policy_domain="unemployment_claims_benefit").model_copy(
        update={
            "engine_plan": (
                first,
                second.model_copy(
                    update={
                        "engine_kind": "method_registry_estimator",
                        "method_fqn": None,
                    }
                ),
            )
        }
    )
    no_coupling_result = JointSimulationHorizonController().run(no_coupling_request)
    assert no_coupling_result.receipt.calibration_status == "no_run"
    assert no_coupling_result.diagnostics["coupling_support_status"] == "not_applicable"
    assert no_coupling_result.diagnostics["coupling_gate_blocked"] is False
    assert no_coupling_result.feedback_classification.support_status == "not_applicable"
    _, no_coupling_blockers = _joint_simulation_port_outcome(no_coupling_result)
    assert "n5_coupling_blocked" not in no_coupling_blockers


def test_selected_plan_requires_its_executed_trajectory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B06: a selected decision without its content-bound physical run is not evidence."""

    controller = JointSimulationHorizonController()
    monkeypatch.setattr(
        controller,
        "_engine_runners",
        lambda: {
            "ncm_parallel_worlds": lambda request, plan, decision: [
                _trajectory(
                    engine_kind=decision.engine_kind,
                    method_fqn=decision.method_fqn or "",
                    objective_ref=plan.objective_ref,
                )
            ]
        },
    )

    with pytest.raises(
        JointSimulationControllerError,
        match="selected_plan_execution_binding_missing",
    ):
        controller.run(_request().model_copy(update={"horizon": HorizonSpec(start=0, end=0)}))


def test_static_engine_rejected_by_actual_grid_falls_back_to_stock_flow() -> None:
    """B06: the exact requested four-step grid selects a real dynamic fallback."""

    base = _request()
    world_ref = base.world_model_record.world_model_record_id
    atoms = (
        _atom(
            intervention_id="capacity_inflow",
            causal_variable="agents.income",
            engine_variable="exogenous_inflows.0",
            value=2.0,
            world_model_record_ref=world_ref,
        ),
        _atom(
            intervention_id="demand_inflow",
            causal_variable="government.balance",
            engine_variable="exogenous_inflows.1",
            value=3.0,
            world_model_record_ref=world_ref,
        ),
    )
    static_plan = base.engine_plan[0]
    dynamic_plan = EnginePlan(
        engine_kind="system_dynamics",
        objective_ref="objective://fallback-after-temporal-rejection",
        variable_map={
            "agents.income": "exogenous_inflows.0",
            "government.balance": "exogenous_inflows.1",
            "stock0": "stock:0",
            "stock1": "stock:1",
        },
        system_dynamics_state={
            "initial_stocks": [10.0, 0.0],
            "flow_matrix": [[0.0, 0.1], [0.0, 0.0]],
            "exogenous_inflows": [0.0, 0.0],
        },
        system_dynamics_params={"dt": 1.0},
    )
    request = base.model_copy(
        update={
            "intervention_atoms": atoms,
            "selected_outcomes": ("stock0", "stock1"),
            "baseline_state": {"stock0": 10.0, "stock1": 0.0},
            "horizon": HorizonSpec(start=0, end=3, step=1),
            "engine_plan": (static_plan, dynamic_plan),
        }
    )

    result = JointSimulationHorizonController().run(request)

    assert request.horizon.steps() == (0, 1, 2, 3)
    assert "multi_period" not in static_plan.eligibility_conditions
    assert [item.decision for item in result.engine_decisions] == ["unsupported", "selected"]
    assert result.engine_decisions[0].reason == "static_engine_cannot_ground_dynamic_horizon"
    assert result.engine_decisions[1].engine_kind == "system_dynamics"
    assert result.engine_decisions[1].objective_ref == dynamic_plan.objective_ref
    assert result.trajectories
    assert all(item.engine_kind == "system_dynamics" for item in result.trajectories)
    joint = result.trajectory_for("joint", ("capacity_inflow", "demand_inflow"))
    assert [point.step for point in joint.points] == [0, 1, 2, 3]
    assert [point.outcomes["stock0"] for point in joint.points] == pytest.approx(
        [10.0, 11.0, 11.9, 12.71]
    )
    assert [point.outcomes["stock1"] for point in joint.points] == pytest.approx(
        [0.0, 4.0, 8.1, 12.29]
    )


def _system_dynamics_input_fallback_request(
    first_flow_matrix: object,
) -> tuple[JointSimulationRequest, EnginePlan]:
    """Build two registry-backed plans with invalid and valid stock-flow inputs."""

    base = _request()
    world_ref = base.world_model_record.world_model_record_id
    atoms = (
        _atom(
            intervention_id="capacity_inflow",
            causal_variable="agents.income",
            engine_variable="exogenous_inflows.0",
            value=2.0,
            world_model_record_ref=world_ref,
        ),
        _atom(
            intervention_id="demand_inflow",
            causal_variable="government.balance",
            engine_variable="exogenous_inflows.1",
            value=3.0,
            world_model_record_ref=world_ref,
        ),
    )
    variable_map = {
        "agents.income": "exogenous_inflows.0",
        "government.balance": "exogenous_inflows.1",
        "stock0": "stock:0",
        "stock1": "stock:1",
    }

    def plan(*, objective_ref: str, flow_matrix: object) -> EnginePlan:
        return EnginePlan(
            engine_kind="system_dynamics",
            objective_ref=objective_ref,
            variable_map=dict(variable_map),
            system_dynamics_state={
                "initial_stocks": [10.0, 0.0],
                "flow_matrix": flow_matrix,
                "exogenous_inflows": [0.0, 0.0],
            },
            system_dynamics_params={"dt": 1.0},
        )

    invalid_plan = plan(
        objective_ref="objective://invalid-first-system-dynamics-plan",
        flow_matrix=first_flow_matrix,
    )
    valid_plan = plan(
        objective_ref="objective://valid-second-system-dynamics-plan",
        flow_matrix=[[0.0, 0.1], [0.0, 0.0]],
    )
    request = base.model_copy(
        update={
            "intervention_atoms": atoms,
            "selected_outcomes": ("stock0", "stock1"),
            "baseline_state": {"stock0": 10.0, "stock1": 0.0},
            "horizon": HorizonSpec(start=0, end=3, step=1),
            "engine_plan": (invalid_plan, valid_plan),
        }
    )
    return request, valid_plan


def _install_system_dynamics_runner_spy(
    controller: JointSimulationHorizonController,
    monkeypatch: pytest.MonkeyPatch,
) -> list[int]:
    """Count physical system-dynamics runner calls while preserving its behavior."""

    calls = [0]
    original_runner = controller._run_system_dynamics_horizon

    def count_runs(
        request: JointSimulationRequest,
        plan: EnginePlan,
        decision: EngineDecision,
    ) -> list[SimulationTrajectory]:
        calls[0] += 1
        return original_runner(request, plan, decision)

    monkeypatch.setattr(
        controller,
        "_engine_runners",
        lambda: {"system_dynamics": count_runs},
    )
    return calls


@pytest.mark.parametrize(
    "invalid_flow_matrix",
    [
        pytest.param([0.0, 0.1], id="wrong-rank"),
        pytest.param([[0.0, 0.1, 0.0], [0.0, 0.0, 0.0]], id="symbolic-dimension-mismatch"),
    ],
)
def test_invalid_first_system_dynamics_plan_falls_back_to_registered_second(
    invalid_flow_matrix: object,
) -> None:
    """B07: schema-invalid first inputs are rejected before the registered fallback runs."""

    request, valid_plan = _system_dynamics_input_fallback_request(invalid_flow_matrix)
    controller = JointSimulationHorizonController()

    result = controller.run(request)

    assert [item.decision for item in result.engine_decisions] == ["unsupported", "selected"]
    assert result.engine_decisions[0].reason == "engine_input_contract_failed"
    selected = result.engine_decisions[1]
    assert selected.engine_kind == "system_dynamics"
    method_fqn = selected.method_fqn
    assert method_fqn == "simulation.system_dynamics.stock_flow@1.0.0"
    assert selected.objective_ref == valid_plan.objective_ref
    assert result.trajectories
    assert all(
        trajectory.engine_kind == "system_dynamics"
        and trajectory.objective_ref == valid_plan.objective_ref
        for trajectory in result.trajectories
    )

    joint = result.trajectory_for("joint", ("capacity_inflow", "demand_inflow"))
    assert [point.step for point in joint.points] == [0, 1, 2, 3]
    registered_method = controller._registry.get(method_fqn)
    direct = registered_method.pure_step(
        {
            "initial_stocks": [10.0, 0.0],
            "flow_matrix": [[0.0, 0.1], [0.0, 0.0]],
            "exogenous_inflows": [2.0, 3.0],
        },
        {"n_steps": 3, "dt": 1.0},
    )["result"]["trajectory"]
    assert [row[0] for row in direct] == pytest.approx(
        [point.outcomes["stock0"] for point in joint.points]
    )
    assert [row[1] for row in direct] == pytest.approx(
        [point.outcomes["stock1"] for point in joint.points]
    )
    assert [point.outcomes["stock0"] for point in joint.points] == pytest.approx(
        [10.0, 11.0, 11.9, 12.71]
    )
    assert [point.outcomes["stock1"] for point in joint.points] == pytest.approx(
        [0.0, 4.0, 8.1, 12.29]
    )


def _registered_seir_input_preflight_case(
    susceptible: object,
) -> tuple[
    JointSimulationHorizonController,
    JointSimulationRequest,
    EnginePlan,
    EngineDecision,
]:
    """Build a controlled preflight-only probe for the registered SEIR input slots."""

    controller = JointSimulationHorizonController()
    ensure_simulation_methods_registered(controller._registry)
    method_fqn = "simulation.compartmental.seir@1.0.0"
    entry = controller._registry.get_entry(method_fqn)
    assert entry is not None
    input_slots = {slot.name: slot for slot in entry.signature.input_slots}
    assert set(input_slots) == {"susceptible", "exposed", "infected", "recovered"}
    assert all(slot.slot_type is SlotType.SCALAR for slot in input_slots.values())
    assert all(slot.contract_id is None and not slot.shape for slot in input_slots.values())

    base_request = _request()
    atom = _atom(
        "seir_preflight_atom",
        causal_variable="agents.income",
        engine_variable="audit_noise",
        value=1.0,
        world_model_record_ref=base_request.world_model_record_ref,
    )
    plan = EnginePlan(
        engine_kind="method_registry_estimator",
        objective_ref="objective://seir-input-preflight-only",
        method_fqn=method_fqn,
        variable_map={"agents.income": "audit_noise"},
        system_dynamics_state={
            "susceptible": susceptible,
            "exposed": 0.0,
            "infected": 0.0,
            "recovered": 0.0,
            "audit_noise": 0.0,
        },
    )
    request = base_request.model_copy(
        update={"intervention_atoms": (atom,), "engine_plan": (plan,)}
    )

    # Current SEIR metadata cannot establish this controller's output semantics.
    # Keep the real selector refusal and construct a controlled decision only to
    # exercise the shared preselection input validator, not production eligibility.
    selector_result = controller._select_registry_method_engine(plan)
    assert selector_result.decision == "unsupported"
    assert selector_result.reason == "method_output_shape_does_not_back_semantics"
    decision = selector_result.model_copy(
        update={
            "decision": "selected",
            "method_fqn": method_fqn,
            "reason": "controlled_input_preflight_probe",
            "blockers": (),
        }
    )
    return controller, request, plan, decision


@pytest.mark.parametrize(
    ("susceptible", "expected_issue"),
    [
        pytest.param(0.0, None, id="valid-zero-scalar"),
        pytest.param("0.0", "registered_input_non_numeric:susceptible", id="string"),
        pytest.param([0.0], "registered_input_non_numeric:susceptible", id="array-rank"),
        pytest.param(True, "registered_input_non_numeric:susceptible", id="boolean"),
        pytest.param(float("nan"), "registered_input_non_finite:susceptible", id="non-finite"),
    ],
)
def test_registered_seir_scalar_inputs_are_preflighted_before_method_engine(
    susceptible: object,
    expected_issue: str | None,
) -> None:
    """The shared input preflight accepts finite scalars and refuses malformed values."""

    controller, request, plan, decision = _registered_seir_input_preflight_case(susceptible)

    issue = controller._registered_system_dynamics_input_issue(request, plan, decision)

    if expected_issue is None:
        assert issue is None
        assert plan.system_dynamics_state["susceptible"] == 0.0
        assert type(plan.system_dynamics_state["susceptible"]) is float
    else:
        assert issue is not None
        assert expected_issue in issue


def test_square_per_atom_flow_matrix_dimension_mismatch_falls_back() -> None:
    """A square override still fails when its shared stock axis disagrees with state."""

    request, valid_plan = _system_dynamics_input_fallback_request(
        [[0.0, 0.1], [0.0, 0.0]]
    )
    first_atom = request.intervention_atoms[0]
    square_override = [[0.0]]
    assert len(square_override) == 1 and len(square_override[0]) == 1
    invalid_plan = valid_plan.model_copy(
        update={
            "objective_ref": "objective://square-override-invalid-axis",
            "system_dynamics_state_overrides_by_atom": {
                first_atom.intervention_id: {"flow_matrix": square_override}
            },
        }
    )
    request = request.model_copy(update={"engine_plan": (invalid_plan, valid_plan)})

    result = JointSimulationHorizonController().run(request)

    assert [item.decision for item in result.engine_decisions] == ["unsupported", "selected"]
    assert result.engine_decisions[0].reason == "engine_input_contract_failed"
    assert result.engine_decisions[0].blockers == (
        "registered_input_dimension_mismatch:initial_stocks:n_stocks",
    )
    assert result.engine_decisions[1].method_fqn == (
        "simulation.system_dynamics.stock_flow@1.0.0"
    )
    assert result.engine_decisions[1].objective_ref == valid_plan.objective_ref
    assert result.trajectories
    assert all(
        trajectory.objective_ref == valid_plan.objective_ref for trajectory in result.trajectories
    )


def test_method_registry_stock_flow_input_state_uses_shared_preflight() -> None:
    """A selected registry estimator with system state receives the same validation."""

    request, valid_plan = _system_dynamics_input_fallback_request(
        [[0.0, 0.1], [0.0, 0.0]]
    )
    controller = JointSimulationHorizonController()
    ensure_simulation_methods_registered(controller._registry)
    entry = controller._registry.get_entry("simulation.system_dynamics.stock_flow@1.0.0")
    assert entry is not None
    atom = request.intervention_atoms[0]
    plan = valid_plan.model_copy(
        update={
            "engine_kind": "method_registry_estimator",
            "method_fqn": entry.signature.fqn,
            "system_dynamics_state_overrides_by_atom": {
                atom.intervention_id: {"initial_stocks": [10.0]}
            },
        }
    )
    decision = controller._select_registry_method_engine(plan)
    assert decision.decision == "selected"
    assert decision.method_fqn == "simulation.system_dynamics.stock_flow@1.0.0"

    issue = controller._registered_system_dynamics_input_issue(
        request.model_copy(update={"engine_plan": (plan,)}),
        plan,
        decision,
    )

    assert issue == "registered_input_dimension_mismatch:initial_stocks:n_stocks"


@pytest.mark.parametrize(
    "invalid_flow_matrix",
    [
        pytest.param([0.0, 0.1], id="wrong-rank"),
        pytest.param([[0.0, 0.1, 0.0], [0.0, 0.0, 0.0]], id="symbolic-dimension-mismatch"),
    ],
)
def test_removing_system_dynamics_input_validation_keeps_marker_but_fails(
    invalid_flow_matrix: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R1: removing schema validation leaves selection green but the real engine fails."""

    request, _valid_plan = _system_dynamics_input_fallback_request(invalid_flow_matrix)
    controller = JointSimulationHorizonController()
    monkeypatch.setattr(
        controller,
        "_registered_system_dynamics_input_issue",
        lambda request, plan, decision: None,
    )

    selected = controller._select_engine(request)
    assert selected.decisions[0].decision == "selected"
    assert selected.decisions[0].reason == "engine_eligibility_satisfied"
    with pytest.raises(ValueError, match="flow_matrix must be a square matrix"):
        controller.run(request)


def test_identical_per_atom_flow_matrix_overrides_are_order_independent() -> None:
    """Identical typed writes compose under either atom order and share run identity."""

    request, valid_plan = _system_dynamics_input_fallback_request(
        [[0.0, 0.1], [0.0, 0.0]]
    )
    atoms = request.intervention_atoms
    flow_matrix = [[0.0, 0.1], [0.0, 0.0]]
    plan = valid_plan.model_copy(
        update={
            "system_dynamics_state_overrides_by_atom": {
                atom.intervention_id: {"flow_matrix": flow_matrix} for atom in atoms
            }
        }
    )
    forward_request = request.model_copy(update={"engine_plan": (plan,)})
    reverse_atoms = tuple(reversed(atoms))
    reverse_request = request.model_copy(
        update={"engine_plan": (plan,), "intervention_atoms": reverse_atoms}
    )
    controller = JointSimulationHorizonController()

    forward = controller.run(forward_request)
    reverse = controller.run(reverse_request)

    assert forward.engine_decisions[0].decision == "selected"
    assert reverse.engine_decisions[0].decision == "selected"
    assert forward.engine_decisions[0].method_fqn == (
        "simulation.system_dynamics.stock_flow@1.0.0"
    )
    assert reverse.engine_decisions[0].method_fqn == (
        "simulation.system_dynamics.stock_flow@1.0.0"
    )
    joint_forward = forward.trajectory_for(
        "joint", tuple(atom.intervention_id for atom in atoms)
    )
    joint_reverse = reverse.trajectory_for(
        "joint", tuple(atom.intervention_id for atom in reverse_atoms)
    )
    assert [point.outcomes for point in joint_forward.points] == [
        point.outcomes for point in joint_reverse.points
    ]
    assert joint_forward.diagnostics["physical_run_ref"] == joint_reverse.diagnostics[
        "physical_run_ref"
    ]


@pytest.mark.parametrize("reverse_atoms", [False, True], ids=["forward", "reverse"])
def test_different_valid_per_atom_flow_matrices_refuse_before_runner(
    reverse_atoms: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Different valid state writes conflict independent of request atom order."""

    request, valid_plan = _system_dynamics_input_fallback_request(
        [[0.0, 0.1], [0.0, 0.0]]
    )
    atoms = request.intervention_atoms
    plan = valid_plan.model_copy(
        update={
            "system_dynamics_state_overrides_by_atom": {
                atoms[0].intervention_id: {
                    "flow_matrix": [[0.0, 0.1], [0.0, 0.0]]
                },
                atoms[1].intervention_id: {
                    "flow_matrix": [[0.0, 0.2], [0.0, 0.0]]
                },
            }
        }
    )
    ordered_atoms = tuple(reversed(atoms)) if reverse_atoms else atoms
    request = request.model_copy(
        update={"engine_plan": (plan,), "intervention_atoms": ordered_atoms}
    )
    controller = JointSimulationHorizonController()
    physical_runs = _install_system_dynamics_runner_spy(controller, monkeypatch)

    result = controller.run(request)

    assert len(result.engine_decisions) == 1
    assert result.engine_decisions[0].decision == "unsupported"
    assert result.engine_decisions[0].reason == "engine_intervention_assignment_conflict"
    assert result.engine_decisions[0].blockers == ("engine_variable_conflict:flow_matrix",)
    assert result.trajectories == ()
    assert physical_runs == [0]


def test_container_and_child_state_writes_refuse_in_both_order_sensitive_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A container override and another atom's child write have no unordered merge law."""

    request, valid_plan = _system_dynamics_input_fallback_request(
        [[0.0, 0.1], [0.0, 0.0]]
    )
    container_atom, child_atom = request.intervention_atoms
    plan = valid_plan.model_copy(
        update={
            "system_dynamics_state_overrides_by_atom": {
                container_atom.intervention_id: {
                    "exogenous_inflows": [0.0, 0.0]
                }
            }
        }
    )
    forward_atoms = (container_atom, child_atom)
    reverse_atoms = tuple(reversed(forward_atoms))
    forward_state = _system_dynamics_state_for_subset(plan, forward_atoms)
    reverse_state = _system_dynamics_state_for_subset(plan, reverse_atoms)
    assert forward_state["exogenous_inflows"] == [2.0, 3.0]
    assert reverse_state["exogenous_inflows"] == [2.0, 0.0]

    for ordered_atoms in (forward_atoms, reverse_atoms):
        ordered_request = request.model_copy(
            update={"engine_plan": (plan,), "intervention_atoms": ordered_atoms}
        )
        controller = JointSimulationHorizonController()
        physical_runs = _install_system_dynamics_runner_spy(controller, monkeypatch)
        result = controller.run(ordered_request)

        assert len(result.engine_decisions) == 1
        assert result.engine_decisions[0].decision == "unsupported"
        assert result.engine_decisions[0].reason == "engine_intervention_assignment_conflict"
        assert result.engine_decisions[0].blockers[0].startswith(
            "engine_variable_conflict:exogenous_inflows"
        )
        assert result.trajectories == ()
        assert physical_runs == [0]


def test_foreign_trajectory_cannot_satisfy_selected_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B06: a result from another engine/plan cannot authorize the selected one."""

    controller = JointSimulationHorizonController()
    monkeypatch.setattr(
        controller,
        "_engine_runners",
        lambda: {
            "ncm_parallel_worlds": lambda request, plan, decision: [_trajectory()]
        },
    )

    with pytest.raises(
        JointSimulationControllerError,
        match="selected_trajectory_binding_mismatch",
    ):
        controller.run(_request().model_copy(update={"horizon": HorizonSpec(start=0, end=0)}))
