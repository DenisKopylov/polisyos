"""Integration witnesses for registered-engine input and applicability gates."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from polisyos.foundry.methods.catalog.simulation.coupled import (
    CoupledPolicySimulationEstimator,
)
from polisyos.foundry.methods.catalog.simulation.dynamics import (
    StockFlowSystemDynamicsEstimator,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    EnginePlan,
    HorizonSpec,
    JointSimulationControllerError,
    JointSimulationHorizonController,
    JointSimulationRequest,
)
from tests.unit.runtime.quality.test_joint_simulation_horizon import _atom, _request


def _stock_flow_request(
    *,
    initial_stocks: tuple[float, ...] = (10.0, 0.0),
    flow_matrix: tuple[tuple[float, ...], ...] = ((0.0, 0.1), (0.0, 0.0)),
    conflicting_atoms: bool = False,
) -> JointSimulationRequest:
    """Build the existing typed request around the registered StockFlow method."""
    base = _request()
    record_ref = base.world_model_record.world_model_record_id
    first_atom = _atom(
        intervention_id="income_subsidy",
        causal_variable="agents.income",
        engine_variable="exogenous_inflows.0",
        value=1.0,
        world_model_record_ref=record_ref,
    )
    atoms = [first_atom]
    variable_map = {
        "agents.income": "exogenous_inflows.0",
        "government.balance": "exogenous_inflows.1",
        "stock0": "stock:0",
    }
    if conflicting_atoms:
        atoms.append(
            _atom(
                intervention_id="balance_grant",
                causal_variable="government.balance",
                engine_variable="exogenous_inflows.0",
                value=2.0,
                world_model_record_ref=record_ref,
            )
        )
        variable_map["government.balance"] = "exogenous_inflows.0"

    plan = EnginePlan(
        engine_kind="system_dynamics",
        objective_ref="objective://registered-stock-flow-applicability",
        variable_map=variable_map,
        system_dynamics_state={
            "initial_stocks": list(initial_stocks),
            "flow_matrix": [list(row) for row in flow_matrix],
            "exogenous_inflows": [0.0, 0.0],
        },
        system_dynamics_params={"dt": 1.0},
    )
    return base.model_copy(
        update={
            "intervention_atoms": tuple(atoms),
            "selected_outcomes": ("stock0",),
            "baseline_state": {"stock0": 10.0},
            "horizon": HorizonSpec(start=0, end=1, step=1),
            "engine_plan": (plan,),
        }
    )


def _install_real_stock_flow_counter(monkeypatch: pytest.MonkeyPatch) -> list[None]:
    """Count calls while delegating each one to the registered producer."""
    original = StockFlowSystemDynamicsEstimator.pure_step
    calls: list[None] = []

    def counted(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        calls.append(None)
        return original(state, params)

    monkeypatch.setattr(
        StockFlowSystemDynamicsEstimator,
        "pure_step",
        staticmethod(counted),
    )
    return calls


def test_registered_stock_flow_valid_slots_reach_the_real_producer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_real_stock_flow_counter(monkeypatch)

    result = JointSimulationHorizonController().run(_stock_flow_request())

    assert result.engine_decisions[0].method_fqn == "simulation.system_dynamics.stock_flow@1.0.0"
    assert result.engine_decisions[0].decision == "selected"
    assert calls
    assert result.trajectories


def test_registered_stock_flow_rejects_inconsistent_declared_dimensions_before_producer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_real_stock_flow_counter(monkeypatch)
    request = _stock_flow_request(initial_stocks=(10.0,))

    result = JointSimulationHorizonController().run(request)

    decision = result.engine_decisions[0]
    assert decision.decision == "unsupported"
    assert decision.reason == "engine_input_contract_failed"
    assert decision.blockers == (
        "registered_input_dimension_mismatch:initial_stocks:n_stocks",
    )
    assert result.trajectories == ()
    assert result.receipt.calibration_status == "no_run"
    assert calls == []


def test_expected_applicability_accepts_the_same_supported_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_real_stock_flow_counter(monkeypatch)
    request = _stock_flow_request()
    controller = JointSimulationHorizonController()
    applicability = controller.assess_applicability(request)

    assert applicability.status == "eligible"
    assert applicability.request_digest is not None
    result = controller.run(request, expected_applicability=applicability)

    assert result.engine_decisions[0].decision == "selected"
    assert calls


@pytest.mark.parametrize("changed_input", ["horizon", "state"])
def test_expected_applicability_rejects_a_changed_request_before_producer(
    monkeypatch: pytest.MonkeyPatch,
    changed_input: str,
) -> None:
    calls = _install_real_stock_flow_counter(monkeypatch)
    request = _stock_flow_request()
    controller = JointSimulationHorizonController()
    applicability = controller.assess_applicability(request)
    assert applicability.status == "eligible"

    if changed_input == "horizon":
        changed_request = request.model_copy(
            update={"horizon": HorizonSpec(start=0, end=2, step=1)}
        )
    else:
        plan = request.engine_plan[0].model_copy(
            update={
                "system_dynamics_state": {
                    **request.engine_plan[0].system_dynamics_state,
                    "initial_stocks": [11.0, 0.0],
                }
            }
        )
        changed_request = request.model_copy(update={"engine_plan": (plan,)})

    with pytest.raises(JointSimulationControllerError) as raised:
        controller.run(changed_request, expected_applicability=applicability)

    assert raised.value.code == "joint_simulation_applicability_changed_before_run"
    assert calls == []


def test_system_dynamics_conflicting_aliases_refuse_before_real_producer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_real_stock_flow_counter(monkeypatch)

    result = JointSimulationHorizonController().run(
        _stock_flow_request(conflicting_atoms=True)
    )

    decision = result.engine_decisions[0]
    assert decision.decision == "unsupported"
    assert decision.reason == "engine_intervention_assignment_conflict"
    assert decision.blockers == ("engine_variable_conflict:exogenous_inflows.0",)
    assert result.trajectories == ()
    assert result.receipt.calibration_status == "no_run"
    assert calls == []


def test_coupled_conflicting_aliases_refuse_before_real_producer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = CoupledPolicySimulationEstimator.pure_step
    calls: list[None] = []

    def counted(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        calls.append(None)
        return original(state, params)

    monkeypatch.setattr(
        CoupledPolicySimulationEstimator,
        "pure_step",
        staticmethod(counted),
    )
    base = _request(policy_domain="unemployment_claims_benefit")
    record_ref = base.world_model_record.world_model_record_id
    atoms = (
        _atom(
            intervention_id="income_subsidy",
            causal_variable="agents.income",
            engine_variable="benefit_amount",
            value=1.0,
            world_model_record_ref=record_ref,
        ),
        _atom(
            intervention_id="balance_grant",
            causal_variable="government.balance",
            engine_variable="benefit_amount",
            value=2.0,
            world_model_record_ref=record_ref,
        ),
    )
    plan = EnginePlan(
        engine_kind="coupled_des_abm",
        objective_ref="objective://coupled-conflicting-aliases",
        eligibility_conditions=(
            "unemployment_claims",
            "benefit_queue",
            "service_queue",
        ),
        variable_map={
            "agents.income": "benefit_amount",
            "government.balance": "benefit_amount",
        },
        coupled_state={
            "initial_income": [1000.0, 600.0, 400.0],
            "initial_savings": [0.0, 0.0, 0.0],
            "is_employed": [1.0, 1.0, 1.0],
        },
        coupled_params={
            "benefit_amount": 0.0,
            "service_rate": 0.5,
            "initial_queue_length": 0.0,
            "seed": 7,
        },
    )
    request = base.model_copy(
        update={
            "intervention_atoms": atoms,
            "selected_outcomes": ("final_queue_length",),
            "baseline_state": {"final_queue_length": 0.0},
            "horizon": HorizonSpec(start=0, end=1, step=1),
            "engine_plan": (plan,),
        }
    )

    result = JointSimulationHorizonController().run(request)

    decision = result.engine_decisions[0]
    assert decision.engine_kind == "coupled_des_abm"
    assert decision.decision == "unsupported"
    assert decision.reason == "engine_intervention_assignment_conflict"
    assert decision.blockers == ("engine_variable_conflict:benefit_amount",)
    assert result.trajectories == ()
    assert result.receipt.calibration_status == "no_run"
    assert calls == []
