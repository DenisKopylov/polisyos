"""Behavioral witnesses for SIM-02 output, atom, and trajectory semantics.

The existing N5 tests cover the happy paths of the joint controller.  This
file keeps the three E02 counterexamples together so that a future repair is
driven by the observable controller boundary:

* B18 must not turn a missing/non-finite selected outcome into a numeric zero;
* B20 must not make incompatible atom assignments order-dependent; and
* B22 must not turn uncovered horizon steps into an implicit last-value hold.

The tests include positive controls for an explicit zero and identical
assignments. Producer callbacks are patched only at the numerical-output seam;
the request, engine selection, controller, and typed result remain real.

Resource classification is ``N/C-light``: the shared request fixture no
longer imports JAX at collection, and these witnesses do not execute a native
JAX fit. The native coupled-engine positive path remains reserved for its
separate controlled slot.

Bounded residual: native JAX coupled execution and external model-output
semantics are not established by patched-output controls. Program-graph
execution is tested at the override admission boundary; its artifact-backed
execution path remains covered by the native quality suite.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
from polisyos.foundry.methods.catalog.simulation.coupled import (
    CoupledPolicySimulationEstimator,
)
from polisyos.foundry.methods.catalog.simulation.dynamics import (
    StockFlowSystemDynamicsEstimator,
)
from polisyos.foundry.methods.selection.registry import MethodRegistry
from polisyos.runtime.quality import joint_simulation_horizon as joint_simulation_horizon_module
from polisyos.runtime.quality.joint_simulation_horizon import (
    EnginePlan,
    HorizonSpec,
    JointSimulationControllerError,
    JointSimulationHorizonController,
    JointSimulationRequest,
)
from tests.unit.runtime.quality.test_joint_simulation_horizon import (
    _atom,
    _coupling_graph,
    _request,
)


def _request_with_same_target_assignments(
    *,
    left_value: float,
    right_value: float,
    reverse: bool = False,
    policy_domain: str = "fiscal_credit",
) -> JointSimulationRequest:
    """Build an NCM request whose two atoms target the same world variable."""
    request = _request(policy_domain=policy_domain)
    world_record_ref = request.world_model_record.world_model_record_id
    atoms = (
        _atom(
            intervention_id="income_subsidy",
            causal_variable="agents.income",
            engine_variable="income_delta",
            value=left_value,
            world_model_record_ref=world_record_ref,
        ),
        _atom(
            intervention_id="balance_grant",
            causal_variable="agents.income",
            engine_variable="income_delta",
            value=right_value,
            world_model_record_ref=world_record_ref,
        ),
    )
    if reverse:
        atoms = tuple(reversed(atoms))
    return request.model_copy(update={"intervention_atoms": atoms})


def _coupled_request(
    *,
    left_value: float = 1.0,
    right_value: float = 1.0,
    reverse: bool = False,
    horizon: HorizonSpec | None = None,
    initial_queue_length: Any = 4.0,
) -> JointSimulationRequest:
    """Build a real coupled-engine request without invoking its JAX producer."""
    request = _request_with_same_target_assignments(
        left_value=left_value,
        right_value=right_value,
        reverse=reverse,
        policy_domain="unemployment_claims_benefit",
    )
    return request.model_copy(
        update={
            "coupling_graph": _coupling_graph("shared_resource"),
            "selected_outcomes": ("final_queue_length",),
            "baseline_state": {"final_queue_length": 0.0},
            "horizon": horizon or HorizonSpec(start=0, end=3, step=1),
            "engine_plan": (
                EnginePlan(
                    engine_kind="coupled_des_abm",
                    objective_ref="objective://sim02-queue",
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
                        "initial_income": [1000.0, 600.0],
                        "initial_savings": [0.0, 0.0],
                        "is_employed": [0.0, 0.0],
                    },
                    coupled_params={
                        "benefit_amount": 0.0,
                        "service_rate": 0.5,
                        **(
                            {"initial_queue_length": initial_queue_length}
                            if initial_queue_length is not None
                            else {}
                        ),
                    },
                ),
            ),
        }
    )


def _system_dynamics_request(
    *,
    selected_outcomes: tuple[str, ...] = ("stock0",),
    horizon: HorizonSpec | None = None,
    overrides_by_atom: dict[str, dict[str, Any]] | None = None,
    system_dynamics_params: dict[str, Any] | None = None,
) -> JointSimulationRequest:
    """Build a registered stock-flow request with deterministic small inputs."""
    request = _request()
    return request.model_copy(
        update={
            "selected_outcomes": selected_outcomes,
            "baseline_state": dict.fromkeys(selected_outcomes, 10.0),
            "horizon": horizon or HorizonSpec(start=0, end=2, step=1),
            "engine_plan": (
                EnginePlan(
                    engine_kind="system_dynamics",
                    objective_ref="objective://sim02-stock-flow",
                    variable_map={
                        "agents.income": "exogenous_inflows.0",
                        "government.balance": "exogenous_inflows.1",
                        "stock0": "stock:0",
                        "stock1": "stock:1",
                        "mass_balance": "mass_balance",
                    },
                    system_dynamics_state={
                        "initial_stocks": [10.0, 0.0],
                        "flow_matrix": [[0.0, 0.0], [0.0, 0.0]],
                        "exogenous_inflows": [0.0, 0.0],
                    },
                    system_dynamics_params=(
                        {"dt": 1.0} if system_dynamics_params is None else system_dynamics_params
                    ),
                    system_dynamics_state_overrides_by_atom=overrides_by_atom or {},
                ),
            ),
        }
    )


@pytest.mark.parametrize(
    ("world_summaries", "selected_outcomes", "expected_code"),
    [
        pytest.param(
            [],
            ("firm_survival",),
            "ncm_world_summaries_missing",
            id="empty-world-summaries",
        ),
        pytest.param(
            [{"world_index": 0}],
            ("firm_survival",),
            "ncm_outcome_missing",
            id="missing-selected-outcome",
        ),
        pytest.param(
            [{"world_index": 0, "firm_survival": {"mean": 2.0}}],
            ("firm_survival", "missing_outcome"),
            "ncm_outcome_missing",
            id="mixed-valid-and-missing-selected-outcome",
        ),
        pytest.param(
            [{"world_index": 0, "firm_survival": {"mean": float("nan")}}],
            ("firm_survival",),
            "ncm_outcome_non_finite",
            id="nan-selected-outcome",
        ),
        pytest.param(
            [{"world_index": 0, "firm_survival": {"mean": float("inf")}}],
            ("firm_survival",),
            "ncm_outcome_non_finite",
            id="infinite-selected-outcome",
        ),
    ],
)
def test_ncm_selected_outcome_missing_or_nonfinite_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    world_summaries: list[dict[str, Any]],
    selected_outcomes: tuple[str, ...],
    expected_code: str,
) -> None:
    """B18: absence and invalid numbers must not become an observed zero."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "counterfactual_result": {
                "world_summaries": world_summaries,
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fake_pure_step))
    request = _request().model_copy(update={"selected_outcomes": selected_outcomes})

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController().run(request)

    # The typed code is the concrete fail-closed signal; no result means no
    # numeric trajectory can be mistaken for a measured zero.
    assert raised.value.code == expected_code


def test_ncm_explicit_zero_is_preserved_as_a_real_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B18 positive control: an explicit finite zero remains numeric zero."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {"world_index": 0, "firm_survival": {"mean": 0.0}},
                ],
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fake_pure_step))

    result = JointSimulationHorizonController().run(_request())

    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert joint.points[0].outcomes == {"firm_survival": 0.0}


@pytest.mark.parametrize(
    ("producer_output", "expected_code"),
    [
        pytest.param(None, "ncm_result_malformed", id="non-mapping-envelope"),
        pytest.param(
            {"counterfactual_result": {"world_summaries": [{"firm_survival": {"mean": []}}]}},
            "ncm_outcome_missing",
            id="empty-selected-value",
        ),
    ],
)
def test_ncm_malformed_result_is_typed(
    monkeypatch: pytest.MonkeyPatch,
    producer_output: object,
    expected_code: str,
) -> None:
    """B18 malformed envelopes and empty values cannot become numeric outcomes."""

    def fake_pure_step(state: Any, params: Any) -> object:
        del state, params
        return producer_output

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fake_pure_step))

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController().run(_request())

    assert raised.value.code == expected_code


@pytest.mark.parametrize("reverse", [False, True], ids=("left-right", "right-left"))
def test_conflicting_atom_assignments_are_rejected_instead_of_last_wins(
    monkeypatch: pytest.MonkeyPatch,
    reverse: bool,
) -> None:
    """B20: different values for one target slot are not list-order semantics."""

    calls = 0

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        del state, params
        return {}

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fake_pure_step))

    request = _request_with_same_target_assignments(
        left_value=1.0,
        right_value=2.0,
        reverse=reverse,
    )

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController().run(request)
    assert raised.value.code == "intervention_assignment_conflict"
    assert calls == 0


def test_identical_atom_assignments_are_order_invariant() -> None:
    """B20 positive control: compatible duplicate assignments preserve behavior."""

    left_first = JointSimulationHorizonController().run(
        _request_with_same_target_assignments(left_value=1.0, right_value=1.0)
    )
    right_first = JointSimulationHorizonController().run(
        _request_with_same_target_assignments(
            left_value=1.0,
            right_value=1.0,
            reverse=True,
        )
    )

    left_joint = left_first.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    right_joint = right_first.trajectory_for("joint", ("balance_grant", "income_subsidy"))
    assert left_joint.points == right_joint.points


class _ShortTrajectoryMethod:
    """Tiny registry method that exposes one point for a three-step request."""

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="short_trajectory",
        namespace="tests.sim02",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))}),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="SIM-02 short-trajectory test method.",
        tags=frozenset({"simulation", "sim02"}),
        assumptions={
            "joint_simulation_output_shape": "time_series_trajectory",
            "joint_simulation_equilibrium_semantics": "dynamic_SCM",
        },
    )

    @staticmethod
    def pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "result": {
                "trajectory": [[10.0]],
                "final_stocks": [99.0],
            }
        }


def _short_trajectory_request(method_fqn: str) -> JointSimulationRequest:
    """Build a dynamic request whose runner returns less coverage than asked."""
    request = _request()
    return request.model_copy(
        update={
            "selected_outcomes": ("stock0",),
            "baseline_state": {"stock0": 10.0},
            "horizon": HorizonSpec(start=0, end=2, step=1),
            "engine_plan": (
                EnginePlan(
                    engine_kind="method_registry_estimator",
                    objective_ref="objective://sim02-short-trajectory",
                    method_fqn=method_fqn,
                    variable_map={"stock0": "stock:0"},
                    coupled_state={"queue_length": 0.0},
                ),
            ),
        }
    )


def test_short_trajectory_is_not_silently_extended_by_final_value() -> None:
    """B22: uncovered horizon steps remain partial or fail closed, never hold-last."""

    registry = MethodRegistry._create_fresh()
    method_fqn = registry.register(_ShortTrajectoryMethod)

    failure_code: str | None = None
    try:
        result = JointSimulationHorizonController(method_registry=registry).run(
            _short_trajectory_request(method_fqn)
        )
    except JointSimulationControllerError as raised:
        failure_code = raised.code
    if failure_code is not None:
        assert failure_code == "trajectory_coverage_incomplete"
        return

    # A permitted partial result has only the point the method actually
    # emitted.  It must carry an explicit status and cannot expose final_stocks
    # as a silent hold-last reconstruction for steps 1 and 2.
    joint = result.trajectory_for(
        "joint",
        ("income_subsidy", "balance_grant"),
    )
    assert [point.step for point in joint.points] == [0]
    assert [point.outcomes for point in joint.points] == [{"stock0": 10.0}]
    assert joint.diagnostics.get("coverage_status") == "partial"
    assert tuple(joint.diagnostics.get("covered_steps", ())) == (0,)
    assert joint.diagnostics.get("hold_last", False) is False
    assert joint.diagnostics["time_alignment_status"] == "not_established"


@pytest.mark.parametrize("reverse", [False, True], ids=("left-right", "right-left"))
def test_coupled_conflicting_assignments_refuse_before_method_invocation(
    monkeypatch: pytest.MonkeyPatch,
    reverse: bool,
) -> None:
    """The selected coupled engine cannot observe order-dependent atoms."""
    calls = 0

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        del state, params
        return {"result": {"initial_queue_length": 0.0}}

    monkeypatch.setattr(
        CoupledPolicySimulationEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )
    request = _coupled_request(left_value=1.0, right_value=2.0, reverse=reverse)

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController().run(request)

    assert raised.value.code == "intervention_assignment_conflict"
    assert calls == 0


@pytest.mark.parametrize(
    ("left_value", "right_value"),
    [
        pytest.param(True, 1, id="bool-versus-int"),
        pytest.param(1, 1.0, id="int-versus-float"),
        pytest.param(
            {"enabled": True, "thresholds": [1, 2.0]},
            {"enabled": 1, "thresholds": [1, 2.0]},
            id="nested-bool-versus-int",
        ),
        pytest.param(
            {"enabled": True, "thresholds": [1, 2.0]},
            {"enabled": True, "thresholds": [1.0, 2.0]},
            id="nested-int-versus-float",
        ),
    ],
)
@pytest.mark.parametrize("reverse", [False, True], ids=("left-right", "right-left"))
def test_program_parameter_conflicts_refuse_before_graph_execution(
    monkeypatch: pytest.MonkeyPatch,
    left_value: Any,
    right_value: Any,
    reverse: bool,
) -> None:
    """B20 rejects type-distinct program writes before graph execution."""
    source_atoms = _request().intervention_atoms
    request = _request().model_copy(
        update={
            "intervention_atoms": tuple(reversed(source_atoms)) if reverse else source_atoms,
            "engine_plan": (
                EnginePlan(
                    engine_kind="program_graph",
                    objective_ref="objective://sim02-program",
                    program_store=object(),
                    program_graph_ref=object(),
                    exec_plan_ref=object(),
                    program_base_state={},
                    mechanism_registry=object(),
                    slot_registry=object(),
                    merge_registry=object(),
                    program_parameter_overrides_by_atom={
                        "income_subsidy": {"policy_node": {"rate": left_value}},
                        "balance_grant": {"policy_node": {"rate": right_value}},
                    },
                ),
            ),
        }
    )
    calls = 0

    def fake_execute(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        raise AssertionError("conflicts must be refused before graph execution")

    monkeypatch.setattr(joint_simulation_horizon_module, "execute_program_graph", fake_execute)

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController().run(request)

    assert raised.value.code == "intervention_assignment_conflict"
    assert calls == 0


@pytest.mark.parametrize(
    ("left_value", "right_value"),
    [
        pytest.param(True, True, id="bool"),
        pytest.param(1, 1, id="int"),
        pytest.param(1.0, 1.0, id="float"),
        pytest.param(
            {"enabled": True, "thresholds": [1, 2.0]},
            {"thresholds": [1, 2.0], "enabled": True},
            id="nested-json-values",
        ),
    ],
)
def test_identical_program_parameter_overrides_merge_independent_of_atom_order(
    monkeypatch: pytest.MonkeyPatch,
    left_value: Any,
    right_value: Any,
) -> None:
    """Compatible program-parameter writes remain invariant under permutation."""
    artifact_ref = SimpleNamespace(artifact_id="sha256:sim02")
    artifacts = SimpleNamespace(state_delta_ref=artifact_ref, metrics_ref=artifact_ref)
    captured_overrides: list[dict[str, dict[str, Any]] | None] = []

    def fake_execute(*args: Any, **kwargs: Any) -> Any:
        del args
        captured_overrides.append(kwargs["parameter_overrides"])
        return artifacts

    monkeypatch.setattr(joint_simulation_horizon_module, "execute_program_graph", fake_execute)
    monkeypatch.setattr(
        joint_simulation_horizon_module,
        "apply_state_delta",
        lambda *args, **kwargs: {"firm_survival": 0.0},
    )

    trajectories = []
    for reverse in (False, True):
        atoms = _request().intervention_atoms
        plan = EnginePlan(
            engine_kind="program_graph",
            objective_ref="objective://sim02-compatible-program-writes",
            program_store=object(),
            program_graph_ref=object(),
            exec_plan_ref=object(),
            program_base_state={},
            mechanism_registry=object(),
            slot_registry=object(),
            merge_registry=object(),
            program_parameter_overrides_by_atom={
                "income_subsidy": {"policy_node": {"rate": left_value}},
                "balance_grant": {"policy_node": {"rate": right_value}},
            },
        )
        request = _request().model_copy(
            update={
                "intervention_atoms": tuple(reversed(atoms)) if reverse else atoms,
                "selected_outcomes": ("firm_survival",),
                "baseline_state": {"firm_survival": 0.0},
                "engine_plan": (plan,),
            }
        )
        trajectories.append(JointSimulationHorizonController().run(request))

    assert captured_overrides
    assert all(
        override is not None
        and json.dumps(override["policy_node"]["rate"], sort_keys=True)
        == json.dumps(left_value, sort_keys=True)
        for override in captured_overrides
    )
    left = trajectories[0].trajectory_for("joint", ("income_subsidy", "balance_grant"))
    right = trajectories[1].trajectory_for("joint", ("balance_grant", "income_subsidy"))
    assert left.points == right.points


@pytest.mark.parametrize(
    ("state", "expected_code"),
    [
        pytest.param({}, "program_graph_outcome_missing", id="missing-selected-state"),
        pytest.param(
            {"firm_survival": float("nan")},
            "program_graph_outcome_non_finite",
            id="non-finite-selected-state",
        ),
        pytest.param(
            {"firm_survival": {"mean": 1.0}},
            "program_graph_outcome_non_numeric",
            id="malformed-selected-state",
        ),
    ],
)
def test_program_graph_selected_outcome_is_typed_at_controller_boundary(
    monkeypatch: pytest.MonkeyPatch,
    state: dict[str, Any],
    expected_code: str,
) -> None:
    """B18 selected state rows are checked by the real graph adapter consumer."""
    artifact_ref = SimpleNamespace(artifact_id="sha256:sim02")
    artifacts = SimpleNamespace(state_delta_ref=artifact_ref, metrics_ref=artifact_ref)
    plan = EnginePlan(
        engine_kind="program_graph",
        objective_ref="objective://sim02-program-output",
        program_store=object(),
        program_graph_ref=object(),
        exec_plan_ref=object(),
        program_base_state={},
        mechanism_registry=object(),
        slot_registry=object(),
        merge_registry=object(),
    )
    request = _request().model_copy(
        update={
            "selected_outcomes": ("firm_survival",),
            "baseline_state": {"firm_survival": 0.0},
            "engine_plan": (plan,),
        }
    )
    monkeypatch.setattr(
        joint_simulation_horizon_module,
        "execute_program_graph",
        lambda *args, **kwargs: artifacts,
    )
    monkeypatch.setattr(
        joint_simulation_horizon_module,
        "apply_state_delta",
        lambda *args, **kwargs: state,
    )

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController().run(request)

    assert raised.value.code == expected_code


def test_program_graph_explicit_zero_is_preserved_at_controller_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B18 explicit zero remains a real finite program state outcome."""
    artifact_ref = SimpleNamespace(artifact_id="sha256:sim02")
    artifacts = SimpleNamespace(state_delta_ref=artifact_ref, metrics_ref=artifact_ref)
    plan = EnginePlan(
        engine_kind="program_graph",
        objective_ref="objective://sim02-program-zero",
        program_store=object(),
        program_graph_ref=object(),
        exec_plan_ref=object(),
        program_base_state={},
        mechanism_registry=object(),
        slot_registry=object(),
        merge_registry=object(),
    )
    request = _request().model_copy(
        update={
            "selected_outcomes": ("firm_survival",),
            "baseline_state": {"firm_survival": 0.0},
            "engine_plan": (plan,),
        }
    )
    monkeypatch.setattr(
        joint_simulation_horizon_module,
        "execute_program_graph",
        lambda *args, **kwargs: artifacts,
    )
    monkeypatch.setattr(
        joint_simulation_horizon_module,
        "apply_state_delta",
        lambda *args, **kwargs: {"firm_survival": 0.0},
    )

    result = JointSimulationHorizonController().run(request)

    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert joint.points[0].outcomes == {"firm_survival": 0.0}


def test_system_state_override_conflict_refuses_before_method_invocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """System-dynamics atom overlays cannot silently replace each other."""
    calls = 0

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        del state, params
        return {"result": {"trajectory": [[10.0], [10.0], [10.0]]}}

    monkeypatch.setattr(
        StockFlowSystemDynamicsEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )
    request = _system_dynamics_request(
        overrides_by_atom={
            "income_subsidy": {"initial_stocks": [4.0, 0.0]},
            "balance_grant": {"initial_stocks": [8.0, 0.0]},
        }
    )

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController().run(request)

    assert raised.value.code == "intervention_assignment_conflict"
    assert calls == 0


def test_identical_system_state_overrides_merge_independent_of_atom_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compatible nested state writes preserve the same state under permutation."""
    received_states: list[dict[str, Any]] = []

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del params
        received_states.append(state)
        return {"result": {"trajectory": [[4.0, 0.0], [4.0, 0.0], [4.0, 0.0]]}}

    monkeypatch.setattr(
        StockFlowSystemDynamicsEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )
    captured_joint_states = []
    for reverse in (False, True):
        request = _system_dynamics_request(
            overrides_by_atom={
                "income_subsidy": {"initial_stocks": [4.0, 0.0]},
                "balance_grant": {"initial_stocks": [4.0, 0.0]},
            }
        )
        if reverse:
            request = request.model_copy(
                update={"intervention_atoms": tuple(reversed(request.intervention_atoms))}
            )
        before = len(received_states)
        JointSimulationHorizonController().run(request)
        captured_joint_states.append(received_states[-1])
        assert len(received_states) > before

    assert captured_joint_states == [
        {
            "initial_stocks": [4.0, 0.0],
            "flow_matrix": [[0.0, 0.0], [0.0, 0.0]],
            "exogenous_inflows": [1.0, 1.0],
        },
        {
            "initial_stocks": [4.0, 0.0],
            "flow_matrix": [[0.0, 0.0], [0.0, 0.0]],
            "exogenous_inflows": [1.0, 1.0],
        },
    ]


@pytest.mark.parametrize(
    ("result", "initial_queue_length", "expected_code"),
    [
        pytest.param({}, None, "coupled_outcome_missing", id="missing-queue-output"),
        pytest.param(
            {"queue_length_trajectory": [float("nan")]},
            0.0,
            "coupled_outcome_non_finite",
            id="non-finite-queue-output",
        ),
        pytest.param(
            {"queue_length_trajectory": [0.0]},
            "unknown",
            "coupled_outcome_non_numeric",
            id="malformed-initial-queue",
        ),
    ],
)
def test_coupled_selected_queue_output_is_typed_and_never_defaulted(
    monkeypatch: pytest.MonkeyPatch,
    result: dict[str, Any],
    initial_queue_length: Any,
    expected_code: str,
) -> None:
    """Missing and malformed queue output cannot be emitted as numeric zero."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {"result": result}

    monkeypatch.setattr(
        CoupledPolicySimulationEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController().run(
            _coupled_request(initial_queue_length=initial_queue_length)
        )

    assert raised.value.code == expected_code


def test_identical_coupled_assignments_merge_independent_of_atom_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compatible direct queue-engine inputs do not depend on atom ordering."""
    received_params: list[dict[str, Any]] = []

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state
        received_params.append(dict(params))
        return {"result": {"queue_length_trajectory": [3.0, 2.0, 1.0]}}

    monkeypatch.setattr(
        CoupledPolicySimulationEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )
    results = [
        JointSimulationHorizonController().run(
            _coupled_request(left_value=1.0, right_value=1.0, reverse=reverse)
        )
        for reverse in (False, True)
    ]

    assert received_params
    assert all(params["benefit_amount"] == 1.0 for params in received_params)
    left = results[0].trajectory_for("joint", ("income_subsidy", "balance_grant"))
    right = results[1].trajectory_for("joint", ("balance_grant", "income_subsidy"))
    assert left.points == right.points
    assert left.diagnostics["time_alignment_status"] == "matched"


def test_coupled_omitted_initial_queue_uses_registered_method_contract_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A declared method default is an effective input, not a missing output."""
    received_params: list[dict[str, Any]] = []

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state
        received_params.append(dict(params))
        return {"result": {"queue_length_trajectory": [1.0, 2.0, 3.0]}}

    declared_default = next(
        parameter.default
        for parameter in CoupledPolicySimulationEstimator.signature.parameters
        if parameter.name == "initial_queue_length"
    )
    monkeypatch.setattr(
        CoupledPolicySimulationEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )

    result = JointSimulationHorizonController().run(_coupled_request(initial_queue_length=None))

    assert received_params
    assert all(params["initial_queue_length"] == declared_default for params in received_params)
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert joint.points[0].outcomes["final_queue_length"] == declared_default


def test_coupled_short_queue_trajectory_is_partial_and_does_not_hold_final(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the configured initial value and actual queue rows cover the horizon."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "result": {
                "queue_length_trajectory": [3.0],
                "final_queue_length": 99.0,
            }
        }

    monkeypatch.setattr(
        CoupledPolicySimulationEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )
    result = JointSimulationHorizonController().run(_coupled_request())
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))

    assert [point.step for point in joint.points] == [0, 1]
    assert [point.outcomes["final_queue_length"] for point in joint.points] == [4.0, 3.0]
    assert joint.diagnostics["coverage_status"] == "partial"
    assert tuple(joint.diagnostics["covered_steps"]) == (0, 1)
    assert joint.diagnostics["hold_last"] is False
    assert joint.diagnostics["time_alignment_status"] == "matched"


def test_coupled_empty_queue_trajectory_keeps_only_known_initial_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty emitted trajectory is partial, not a held terminal value."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {"result": {"queue_length_trajectory": [], "final_queue_length": 99.0}}

    monkeypatch.setattr(
        CoupledPolicySimulationEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )
    result = JointSimulationHorizonController().run(_coupled_request())
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))

    assert [point.step for point in joint.points] == [0]
    assert [point.outcomes["final_queue_length"] for point in joint.points] == [4.0]
    assert joint.diagnostics["coverage_status"] == "partial"
    assert tuple(joint.diagnostics["covered_steps"]) == (0,)
    assert joint.diagnostics["hold_last"] is False
    assert joint.diagnostics["time_alignment_status"] == "matched"


@pytest.mark.parametrize(
    ("result", "selected_outcomes", "expected_code"),
    [
        pytest.param(
            {"trajectory": [[10.0]], "final_stocks": [10.0]},
            ("mass_balance",),
            "system_dynamics_outcome_missing",
            id="missing-mass-balance",
        ),
        pytest.param(
            {"trajectory": [[float("inf")]]},
            ("stock0",),
            "system_dynamics_outcome_non_finite",
            id="non-finite-stock",
        ),
        pytest.param(
            {"trajectory": [[[10.0]]]},
            ("stock0",),
            "system_dynamics_outcome_non_numeric",
            id="malformed-stock-row",
        ),
    ],
)
def test_system_dynamics_selected_output_is_typed_and_never_defaulted(
    monkeypatch: pytest.MonkeyPatch,
    result: dict[str, Any],
    selected_outcomes: tuple[str, ...],
    expected_code: str,
) -> None:
    """Missing mass-balance and non-finite stocks fail as typed evidence."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {"result": result}

    monkeypatch.setattr(
        StockFlowSystemDynamicsEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController().run(
            _system_dynamics_request(selected_outcomes=selected_outcomes)
        )

    assert raised.value.code == expected_code


def test_system_dynamics_run_level_scalar_is_not_repeated_across_horizon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A single final mass-balance value is not a per-step time series."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "result": {
                "trajectory": [[10.0, 0.0], [10.0, 0.0], [10.0, 0.0]],
                "mass_balance": 0.0,
            }
        }

    monkeypatch.setattr(
        StockFlowSystemDynamicsEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController().run(
            _system_dynamics_request(selected_outcomes=("mass_balance",))
        )

    assert raised.value.code == "system_dynamics_temporal_outcome_series_missing"


def test_system_dynamics_single_point_preserves_explicit_zero_scalar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real finite run-level scalar remains available for a one-point horizon."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {"result": {"trajectory": [[10.0, 0.0]], "mass_balance": 0.0}}

    monkeypatch.setattr(
        StockFlowSystemDynamicsEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )
    request = _system_dynamics_request(
        selected_outcomes=("mass_balance",),
        horizon=HorizonSpec(start=0, end=0, step=1),
    )

    result = JointSimulationHorizonController().run(request)

    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert joint.points[0].outcomes == {"mass_balance": 0.0}


def test_system_dynamics_short_trajectory_is_partial_without_final_stock_fill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A final_stocks value cannot stand in for absent trajectory rows."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "result": {
                "trajectory": [[10.0]],
                "final_stocks": [99.0],
                "mass_balance": 0.0,
            }
        }

    monkeypatch.setattr(
        StockFlowSystemDynamicsEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )
    result = JointSimulationHorizonController().run(_system_dynamics_request())
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))

    assert [point.step for point in joint.points] == [0]
    assert [point.outcomes["stock0"] for point in joint.points] == [10.0]
    assert joint.diagnostics["coverage_status"] == "partial"
    assert tuple(joint.diagnostics["covered_steps"]) == (0,)
    assert joint.diagnostics["hold_last"] is False
    assert joint.diagnostics["time_alignment_status"] == "matched"


def test_empty_system_dynamics_trajectory_has_no_outcome_row_to_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty producer trajectory is distinguishable from the known short prefix."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {"result": {"trajectory": [], "final_stocks": [99.0]}}

    monkeypatch.setattr(
        StockFlowSystemDynamicsEstimator,
        "pure_step",
        staticmethod(fake_pure_step),
    )

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController().run(_system_dynamics_request())

    assert raised.value.code == "trajectory_coverage_incomplete"


def test_method_registry_missing_selected_output_is_not_filled_from_final_state() -> None:
    """The generic registry adapter also refuses a missing selected value."""
    registry = MethodRegistry._create_fresh()
    method_fqn = registry.register(_ShortTrajectoryMethod)
    request = _short_trajectory_request(method_fqn).model_copy(
        update={
            "selected_outcomes": ("missing_value",),
            "baseline_state": {"missing_value": 0.0},
        }
    )

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController(method_registry=registry).run(request)

    assert raised.value.code == "method_registry_outcome_missing"


def test_empty_method_registry_trajectory_is_not_filled_from_final_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty temporal method result cannot use its terminal summary as coverage."""
    registry = MethodRegistry._create_fresh()
    method_fqn = registry.register(_ShortTrajectoryMethod)

    def empty_trajectory(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {"result": {"trajectory": [], "final_stocks": [99.0]}}

    monkeypatch.setattr(_ShortTrajectoryMethod, "pure_step", staticmethod(empty_trajectory))

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController(method_registry=registry).run(
            _short_trajectory_request(method_fqn)
        )

    assert raised.value.code == "trajectory_coverage_incomplete"


def test_non_unit_horizon_step_aligns_real_stockflow_rows() -> None:
    """The actual stock-flow producer receives the requested time increment."""
    request = _system_dynamics_request(
        selected_outcomes=("stock0", "stock1"),
        horizon=HorizonSpec(start=0, end=4, step=2),
        system_dynamics_params={},
    )

    result = JointSimulationHorizonController().run(request)

    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert [point.step for point in joint.points] == [0, 2, 4]
    assert [point.outcomes["stock0"] for point in joint.points] == [10.0, 12.0, 14.0]
    assert [point.outcomes["stock1"] for point in joint.points] == [0.0, 2.0, 4.0]
    assert joint.diagnostics["time_alignment_status"] == "matched"
    assert joint.diagnostics["effective_method_time_step"] == 2.0


def test_configured_stockflow_step_mismatch_remains_visible() -> None:
    """An explicit method dt is preserved and marked when labels use another step."""
    request = _system_dynamics_request(
        selected_outcomes=("stock0",),
        horizon=HorizonSpec(start=0, end=4, step=2),
        system_dynamics_params={"dt": 1.0},
    )

    result = JointSimulationHorizonController().run(request)

    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert [point.step for point in joint.points] == [0, 2, 4]
    assert [point.outcomes["stock0"] for point in joint.points] == [10.0, 11.0, 12.0]
    assert joint.diagnostics["time_alignment_status"] == "not_established"
    assert joint.diagnostics["requested_time_step"] == 2
    assert joint.diagnostics["effective_method_time_step"] == 1.0
