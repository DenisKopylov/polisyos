"""Behavioral witnesses for SIM-01 engine selection and execution binding."""

from __future__ import annotations

from typing import cast, get_args

import pytest

from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
from polisyos.runtime.quality.generation_cycle import _joint_simulation_port_outcome
from polisyos.runtime.quality.joint_simulation_horizon import (
    EngineDecision,
    EngineKind,
    EnginePlan,
    HorizonSpec,
    JointSimulationControllerError,
    JointSimulationHorizonController,
    SimulationTrajectory,
    TemporalCapability,
    TrajectoryPoint,
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


def _single_step_request():
    """Use one point when exercising the static NCM path."""
    return _request().model_copy(
        update={"horizon": HorizonSpec(start=0, end=0, step=1)}
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
            "horizon": HorizonSpec(start=0, end=0, step=1),
            "coupling_graph": _coupling_graph("shared_resource"),
            "selected_outcomes": ("final_queue_length",),
            "baseline_state": {"final_queue_length": 0.0},
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


@pytest.mark.parametrize("engine_kind", get_args(EngineKind))
@pytest.mark.parametrize(
    ("temporal_capability", "expected_reason", "expected_blocker"),
    [
        (
            "static",
            "static_engine_cannot_ground_dynamic_horizon",
            "static_engine_temporal_capability",
        ),
        (
            "unsupported",
            "engine_temporal_capability_unavailable",
            "engine_temporal_capability_unsupported",
        ),
    ],
)
def test_shared_horizon_admission_rejects_non_multi_period_capability_for_every_engine_kind(
    monkeypatch: pytest.MonkeyPatch,
    engine_kind: EngineKind,
    temporal_capability: str,
    expected_reason: str,
    expected_blocker: str,
) -> None:
    """Every engine kind needs selector evidence of multi-period support."""

    controller = JointSimulationHorizonController()
    plan = _single_step_request().engine_plan[0].model_copy(
        update={
            "engine_kind": cast("EngineKind", engine_kind),
            "eligibility_conditions": (),
        }
    )
    request = _single_step_request().model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=2, step=1),
            "engine_plan": (plan,),
        }
    )

    def static_selector(candidate: EnginePlan) -> EngineDecision:
        return EngineDecision(
            engine_kind=candidate.engine_kind,
            objective_ref=candidate.objective_ref,
            decision="selected",
            method_fqn="test.static-capability",
            equilibrium_semantics="static_SCM",
            temporal_capability=cast("TemporalCapability", temporal_capability),
            output_shape="static_point",
            reason="engine_eligibility_satisfied",
        )

    selectors = dict.fromkeys(get_args(EngineKind), static_selector)
    monkeypatch.setattr(controller, "_engine_selectors", lambda _record: selectors)

    selected = controller._select_engine(request)

    assert selected.decision.decision == "unsupported"
    assert selected.decision.reason == expected_reason
    assert selected.decision.blockers == (expected_blocker,)


def test_unlabeled_static_first_plan_falls_through_to_real_dynamic_engine() -> None:
    """A missing temporal flag cannot make static NCM eligible for a multi-step request."""

    base = _request().model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=2, step=1),
            "selected_outcomes": ("stock0",),
            "baseline_state": {"stock0": 0.0},
        }
    )
    static_plan = base.engine_plan[0].model_copy(
        update={"eligibility_conditions": ("acyclic", "counterfactual_do_worlds")}
    )
    dynamic_plan = EnginePlan(
        engine_kind="system_dynamics",
        objective_ref="objective://temporal-fallback-stock-flow",
        variable_map={
            "agents.income": "exogenous_inflows.0",
            "government.balance": "exogenous_inflows.1",
            "stock0": "stock:0",
        },
        system_dynamics_state={
            "initial_stocks": [0.0, 0.0],
            "flow_matrix": [[0.0, 0.0], [0.0, 0.0]],
            "exogenous_inflows": [0.0, 0.0],
        },
        system_dynamics_params={"dt": 1.0},
    )
    request = base.model_copy(update={"engine_plan": (static_plan, dynamic_plan)})

    result = JointSimulationHorizonController().run(request)

    assert [item.decision for item in result.engine_decisions] == ["unsupported", "selected"]
    assert result.engine_decisions[0].reason == "static_engine_cannot_ground_dynamic_horizon"
    assert result.engine_decisions[0].blockers == ("static_engine_temporal_capability",)
    assert result.engine_decisions[1].engine_kind == "system_dynamics"
    assert result.engine_decisions[1].temporal_capability == "multi_period"
    assert result.trajectories
    assert {trajectory.engine_kind for trajectory in result.trajectories} == {"system_dynamics"}
    assert all(
        tuple(point.step for point in trajectory.points) == (0, 1, 2)
        for trajectory in result.trajectories
    )


def test_all_unlabeled_static_multistep_candidates_refuse_before_runner_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All static candidates preserve typed reasons and produce no N5 run."""

    base = _request()
    first = base.engine_plan[0].model_copy(
        update={"eligibility_conditions": ("acyclic", "counterfactual_do_worlds")}
    )
    second = first.model_copy(update={"objective_ref": "objective://second-static"})
    request = base.model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=2, step=1),
            "engine_plan": (first, second),
        }
    )
    controller = JointSimulationHorizonController()
    runner_lookups: list[None] = []

    def runner_map() -> dict[str, object]:
        runner_lookups.append(None)
        return {}

    monkeypatch.setattr(controller, "_engine_runners", runner_map)
    result = controller.run(request)

    assert [item.decision for item in result.engine_decisions] == ["unsupported", "unsupported"]
    assert [item.reason for item in result.engine_decisions] == [
        "static_engine_cannot_ground_dynamic_horizon",
        "static_engine_cannot_ground_dynamic_horizon",
    ]
    assert [item.blockers for item in result.engine_decisions] == [
        ("static_engine_temporal_capability",),
        ("static_engine_temporal_capability",),
    ]
    assert result.receipt.calibration_status == "no_run"
    assert result.diagnostics["engine_run_claimed"] is False
    assert not result.trajectories
    assert runner_lookups == []


@pytest.mark.parametrize("reverse", [False, True], ids=("left-right", "right-left"))
def test_composition_rejection_falls_back_before_execution(
    monkeypatch: pytest.MonkeyPatch,
    reverse: bool,
) -> None:
    """B07/B20: a selected-looking plan with conflicting writes is skipped."""

    base = _single_step_request()
    world_ref = base.world_model_record.world_model_record_id
    atoms = (
        _atom(
            intervention_id="income_subsidy",
            causal_variable="agents.income",
            engine_variable="income_delta",
            value=1.0,
            world_model_record_ref=world_ref,
        ),
        _atom(
            intervention_id="balance_grant",
            causal_variable="government.balance",
            engine_variable="balance_delta",
            value=2.0,
            world_model_record_ref=world_ref,
        ),
    )
    if reverse:
        atoms = tuple(reversed(atoms))
    supported_plan = base.engine_plan[0].model_copy(
        update={"objective_ref": "objective://composition-fallback"}
    )
    conflicting_plan = base.engine_plan[0].model_copy(
        update={
            "objective_ref": "objective://composition-conflict",
            "variable_map": {
                "agents.income": "income_delta",
                "government.balance": "income_delta",
                "firm_survival": "firm_survival",
            },
        }
    )
    request = base.model_copy(
        update={
            "intervention_atoms": atoms,
            "engine_plan": (conflicting_plan, supported_plan),
        }
    )
    calls: list[object] = []

    def fixed_result(state: object, params: object) -> dict[str, object]:
        del params
        calls.append(state)
        return {
            "counterfactual_result": {
                "world_summaries": [{"firm_survival": {"mean": 1.0}}]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fixed_result))
    result = JointSimulationHorizonController().run(request)

    assert [item.decision for item in result.engine_decisions] == ["unsupported", "selected"]
    assert result.engine_decisions[0].reason == "intervention_assignment_conflict"
    assert result.engine_decisions[1].objective_ref == supported_plan.objective_ref
    assert calls
    assert {item.objective_ref for item in result.trajectories} == {
        supported_plan.objective_ref
    }


def test_all_engine_candidates_incompatible_return_typed_rejection() -> None:
    """B07: no coupling-compatible candidate remains a typed no-run refusal."""

    first = _coupled_plan().model_copy(
        update={"declared_equilibrium_semantics": "game_model"}
    )
    second = _request().engine_plan[0]
    request = _request(policy_domain="unemployment_claims_benefit").model_copy(
        update={
            "horizon": HorizonSpec(start=0, end=0, step=1),
            "coupling_graph": _coupling_graph("shared_resource"),
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
            "horizon": HorizonSpec(start=0, end=0, step=1),
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
        controller.run(_single_step_request())


def test_rejected_engine_reasons_do_not_override_selected_success() -> None:
    """B06: history retains why an earlier candidate was rejected."""

    first = _request().engine_plan[0].model_copy(
        update={"eligibility_conditions": ("multi_period",)}
    )
    second = _request().engine_plan[0].model_copy(
        update={"objective_ref": "objective://fallback-after-temporal-rejection"}
    )
    request = _single_step_request().model_copy(update={"engine_plan": (first, second)})

    result = JointSimulationHorizonController().run(request)

    assert result.engine_decisions[0].decision == "unsupported"
    assert result.engine_decisions[0].reason == "static_engine_cannot_ground_dynamic_horizon"
    assert result.engine_decisions[1].decision == "selected"
    assert result.engine_decisions[1].objective_ref == second.objective_ref
    assert result.trajectories


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
        controller.run(_single_step_request())
