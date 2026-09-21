"""Behavioral witnesses for SIM-01 engine selection and execution binding."""

from __future__ import annotations

import pytest

from polisyos.runtime.quality.generation_cycle import _joint_simulation_port_outcome
from polisyos.runtime.quality.joint_simulation_horizon import (
    EnginePlan,
    JointSimulationControllerError,
    JointSimulationHorizonController,
    SimulationTrajectory,
    TrajectoryPoint,
)
from polisyos.runtime.quality.recursive_generation_cycle import _joint_simulation_is_unsupported
from tests.unit.runtime.quality.test_joint_simulation_horizon import (
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
        controller.run(_request())


def test_rejected_engine_reasons_do_not_override_selected_success() -> None:
    """B06: history retains why an earlier candidate was rejected."""

    first = _request().engine_plan[0].model_copy(
        update={"eligibility_conditions": ("multi_period",)}
    )
    second = _request().engine_plan[0].model_copy(
        update={"objective_ref": "objective://fallback-after-temporal-rejection"}
    )
    request = _request().model_copy(update={"engine_plan": (first, second)})

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
        controller.run(_request())
