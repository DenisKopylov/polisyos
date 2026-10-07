"""Integration witnesses for required numeric outputs at simulation consumers.

The wrappers below call each registered engine's real ``pure_step`` and then
alter only its returned payload.  This keeps the controller's output intake
under test while the captured direct engine output serves as the positive
oracle for the same invocation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from typing import Any

import pytest

from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
from polisyos.foundry.methods.catalog.simulation.coupled import (
    CoupledPolicySimulationEstimator,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    EnginePlan,
    HorizonSpec,
    JointSimulationControllerError,
    JointSimulationHorizonController,
    JointSimulationRequest,
)
from tests.unit.runtime.quality.test_joint_simulation_horizon import (
    _ncm_with_cross_term,
    _request,
)

_Mutator = Callable[[dict[str, Any]], None]


def _install_real_ncm_output_wrapper(
    monkeypatch: pytest.MonkeyPatch,
    mutate: _Mutator,
) -> list[dict[str, Any]]:
    """Record actual NCM outputs, then alter only the controller-bound copy."""
    original = NCMEngineMethod.pure_step
    direct_outputs: list[dict[str, Any]] = []

    def wrapped(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        direct = original(state, params)
        direct_outputs.append(deepcopy(direct))
        controller_payload = deepcopy(direct)
        mutate(controller_payload)
        return controller_payload

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(wrapped))
    return direct_outputs


def _ncm_summary(output: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = output["counterfactual_result"]
    assert isinstance(payload, Mapping)
    summaries = payload["world_summaries"]
    assert isinstance(summaries, Sequence) and summaries
    summary = summaries[0]
    assert isinstance(summary, Mapping)
    return summary


def _damage_ncm_empty_package(output: dict[str, Any]) -> None:
    output["counterfactual_result"] = {}


def _damage_ncm_malformed_result_container(output: dict[str, Any]) -> None:
    output["counterfactual_result"] = "not-a-result-mapping"


def _damage_ncm_missing_selected_output(output: dict[str, Any]) -> None:
    del output["counterfactual_result"]["world_summaries"][0]["firm_survival"]


def _damage_ncm_malformed_summary_container(output: dict[str, Any]) -> None:
    output["counterfactual_result"]["world_summaries"] = "not-a-summary-sequence"


def _damage_ncm_malformed_stats(output: dict[str, Any]) -> None:
    output["counterfactual_result"]["world_summaries"][0]["firm_survival"] = []


def _damage_ncm_nan(output: dict[str, Any]) -> None:
    output["counterfactual_result"]["world_summaries"][0]["firm_survival"]["mean"] = float(
        "nan"
    )


def _damage_ncm_infinity(output: dict[str, Any]) -> None:
    output["counterfactual_result"]["world_summaries"][0]["firm_survival"]["mean"] = float(
        "inf"
    )


@pytest.mark.parametrize(
    ("mutate", "selected_outcomes", "expected_code"),
    [
        pytest.param(
            _damage_ncm_empty_package,
            ("firm_survival",),
            "ncm_world_summaries_missing",
            id="empty-result-package",
        ),
        pytest.param(
            _damage_ncm_missing_selected_output,
            ("firm_survival", "income_delta"),
            "ncm_outcome_missing",
            id="one-selected-output-missing",
        ),
        pytest.param(
            _damage_ncm_malformed_result_container,
            ("firm_survival",),
            "ncm_world_summaries_malformed",
            id="malformed-result-container",
        ),
        pytest.param(
            _damage_ncm_malformed_summary_container,
            ("firm_survival",),
            "ncm_world_summaries_malformed",
            id="malformed-summary-container",
        ),
        pytest.param(
            _damage_ncm_malformed_stats,
            ("firm_survival",),
            "ncm_outcome_malformed",
            id="malformed-selected-output-structure",
        ),
        pytest.param(
            _damage_ncm_nan,
            ("firm_survival",),
            "ncm_outcome_non_finite",
            id="nan-selected-output",
        ),
        pytest.param(
            _damage_ncm_infinity,
            ("firm_survival",),
            "ncm_outcome_non_finite",
            id="infinite-selected-output",
        ),
    ],
)
def test_registered_ncm_output_damage_is_refused_with_distinct_reasons(
    monkeypatch: pytest.MonkeyPatch,
    mutate: _Mutator,
    selected_outcomes: tuple[str, ...],
    expected_code: str,
) -> None:
    """Malformed, absent, and non-finite NCM values never become a number."""
    direct_outputs = _install_real_ncm_output_wrapper(monkeypatch, mutate)
    request = _request().model_copy(
        update={
            "selected_outcomes": selected_outcomes,
            "horizon": HorizonSpec(start=0, end=0),
        }
    )

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController().run(request)

    # The method ran and its unaltered output had the selected value.  Only the
    # controller-bound payload was damaged; no SimulationResult escaped.
    assert direct_outputs
    direct_summary = _ncm_summary(direct_outputs[0])
    for outcome in selected_outcomes:
        assert outcome in direct_summary
    direct_stats = direct_summary["firm_survival"]
    assert isinstance(direct_stats, Mapping)
    assert isinstance(direct_stats.get("mean"), (int, float))
    assert raised.value.code == expected_code


def test_registered_ncm_direct_zero_remains_a_numeric_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An actual constant-zero engine outcome remains observable as zero."""
    spec = _ncm_with_cross_term()
    zero_equations = tuple(
        equation.model_copy(
            update={
                "equation_type": "nonlinear",
                "equation_params": {"noise_expression": "0.0"},
            }
        )
        if equation.variable == "firm_survival"
        else equation
        for equation in spec.structural_equations
    )
    request = _request(ncm=spec.model_copy(update={"structural_equations": zero_equations}))
    request = request.model_copy(update={"horizon": HorizonSpec(start=0, end=0)})
    direct_outputs = _install_real_ncm_output_wrapper(monkeypatch, lambda output: None)

    result = JointSimulationHorizonController().run(request)

    direct_stats = _ncm_summary(direct_outputs[0])["firm_survival"]
    assert isinstance(direct_stats, Mapping)
    assert direct_stats["mean"] == 0.0
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert joint.points[0].outcomes["firm_survival"] == direct_stats["mean"]


def _coupled_request(*, horizon: HorizonSpec | None = None) -> JointSimulationRequest:
    """Build the existing unemployment-claims queue engine fixture."""
    request = _request(policy_domain="unemployment_claims_benefit")
    return request.model_copy(
        update={
            "selected_outcomes": ("final_queue_length",),
            "baseline_state": {"final_queue_length": 0.0},
            "horizon": horizon or HorizonSpec(start=0, end=1, step=1),
            "engine_plan": (
                EnginePlan(
                    engine_kind="coupled_des_abm",
                    objective_ref="objective://required-queue-output",
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
                        "is_employed": [1.0, 1.0, 1.0],
                    },
                    coupled_params={
                        "benefit_amount": 0.0,
                        "service_rate": 0.5,
                        "initial_queue_length": 0.0,
                        "seed": 7,
                    },
                ),
            ),
        }
    )


def _install_real_coupled_output_wrapper(
    monkeypatch: pytest.MonkeyPatch,
    mutate: _Mutator,
) -> list[dict[str, Any]]:
    """Record actual coupled outputs, then alter only the controller-bound copy."""
    original = CoupledPolicySimulationEstimator.pure_step
    direct_outputs: list[dict[str, Any]] = []

    def wrapped(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        direct = original(state, params)
        direct_outputs.append(deepcopy(direct))
        controller_payload = deepcopy(direct)
        mutate(controller_payload)
        return controller_payload

    monkeypatch.setattr(CoupledPolicySimulationEstimator, "pure_step", staticmethod(wrapped))
    return direct_outputs


def _coupled_result(output: Mapping[str, Any]) -> Mapping[str, Any]:
    result = output["result"]
    assert isinstance(result, Mapping)
    return result


def _damage_coupled_missing_queue(output: dict[str, Any]) -> None:
    del output["result"]["queue_length_trajectory"]


def _damage_coupled_malformed_queue(output: dict[str, Any]) -> None:
    output["result"]["queue_length_trajectory"] = "not-a-trajectory"


def _damage_coupled_non_finite_queue(output: dict[str, Any]) -> None:
    output["result"]["queue_length_trajectory"][0] = float("nan")


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    [
        pytest.param(
            _damage_coupled_missing_queue,
            "coupled_queue_trajectory_incomplete",
            id="missing-required-queue-trajectory",
        ),
        pytest.param(
            _damage_coupled_malformed_queue,
            "coupled_queue_trajectory_non_numeric",
            id="malformed-queue-container",
        ),
        pytest.param(
            _damage_coupled_non_finite_queue,
            "coupled_queue_trajectory_non_finite",
            id="non-finite-queue-value",
        ),
    ],
)
def test_registered_coupled_queue_output_damage_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    mutate: _Mutator,
    expected_code: str,
) -> None:
    """The queue consumer refuses absent, malformed, and non-finite results."""
    direct_outputs = _install_real_coupled_output_wrapper(monkeypatch, mutate)

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController().run(_coupled_request())

    assert direct_outputs
    direct_result = _coupled_result(direct_outputs[0])
    direct_trajectory = direct_result["queue_length_trajectory"]
    assert isinstance(direct_trajectory, Sequence)
    assert direct_trajectory
    assert all(isinstance(value, (int, float)) for value in direct_trajectory)
    assert raised.value.code == expected_code


def test_registered_coupled_direct_zero_queue_remains_numeric_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real no-queue engine result agrees with its direct producer output."""
    direct_outputs = _install_real_coupled_output_wrapper(monkeypatch, lambda output: None)

    result = JointSimulationHorizonController().run(_coupled_request())

    assert direct_outputs
    direct_result = _coupled_result(direct_outputs[-1])
    assert direct_result["final_queue_length"] == 0.0
    assert all(value == 0.0 for value in direct_result["queue_length_trajectory"])
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert [point.outcomes["final_queue_length"] for point in joint.points] == [0.0, 0.0]
