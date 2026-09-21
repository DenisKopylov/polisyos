"""Test-first witnesses for the SIM-03 estimation and joint-run contracts.

The tests deliberately exercise the observable seams for B19/B21/B23/B25/B26.
They remain an N/C-exclusive profile because the shared joint-simulation
fixture imports the native registry and numerical stack.
"""

from __future__ import annotations

from typing import Any

import pytest

from polisyos.foundry.coupling.estimation import (
    calibrate_coupled_smm,
    paired_monte_carlo_effect,
    summary_distance,
)
from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
from polisyos.runtime.quality.joint_simulation_horizon import (
    JointSimulationControllerError,
    JointSimulationHorizonController,
    SimulationTrajectory,
    TrajectoryPoint,
    _higher_order_residuals,
)
from tests.unit.runtime.quality.test_joint_simulation_horizon import _atom, _request


def test_summary_distance_requires_one_declared_metric_set() -> None:
    """B25: a missing required moment cannot be treated as a zero-distance fit."""

    with pytest.raises(ValueError, match="required summary moments"):
        summary_distance(
            {"easy": 0.0},
            {"easy": 0.0, "hard": 100.0},
            required_moment_names=("easy", "hard"),
        )


def test_smm_missing_required_moment_cannot_win_calibration() -> None:
    """B25: removing a difficult required moment never improves SMM selection."""

    def runner(params: dict[str, float], seed: int | None) -> dict[str, float]:
        del seed
        if params["candidate"] == 0.0:
            return {"easy": 0.0}
        return {"easy": 0.0, "hard": 99.0}

    result = calibrate_coupled_smm(
        {"candidate": (0.0, 1.0)},
        runner,
        {"easy": 0.0, "hard": 100.0},
        required_moment_names=("easy", "hard"),
        seeds=(11, 13),
    )

    assert result.best_params == {"candidate": 1.0}
    missing = next(item for item in result.evaluated if item["params"] == {"candidate": 0.0})
    assert missing["loss"] == float("inf")
    assert missing["missing_moments"] == ("hard",)
    assert missing["moment_counts"] == {"easy": 2, "hard": 0}


def test_smm_all_incomparable_candidates_are_explicitly_blocked() -> None:
    """B25: all-infinite loss cannot select the first parameter combination."""

    result = calibrate_coupled_smm(
        {"candidate": (0.0, 1.0)},
        lambda params, seed: {"easy": float(params["candidate"])},
        {"easy": 0.0, "hard": 100.0},
        required_moment_names=("easy", "hard"),
        seeds=(11, 13),
    )

    assert result.best_params is None
    assert result.best_loss == float("inf")
    assert result.comparison_status == "no_comparable"
    assert result.status == "blocked"


def test_single_paired_draw_has_unestimated_standard_error() -> None:
    """B21: one stochastic draw cannot claim a measured zero standard error."""

    result = paired_monte_carlo_effect(
        lambda seed: {"welfare": float(seed)},
        lambda seed: {"welfare": float(seed + 2)},
        seeds=(7,),
        metric_names=("welfare",),
    )

    assert result.n_replications == 1
    assert result.standard_errors["welfare"] is None
    assert result.standard_error_status["welfare"] == "standard_error_not_estimated"


def test_paired_replicates_require_distinct_seeds() -> None:
    """B21: duplicate seeds are not independent replications."""

    with pytest.raises(ValueError, match="seeds must be unique"):
        paired_monte_carlo_effect(
            lambda seed: {"welfare": float(seed)},
            lambda seed: {"welfare": float(seed + 1)},
            seeds=(7, 7),
            metric_names=("welfare",),
        )


def test_joint_request_runs_each_requested_replication_with_distinct_seeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B21: request-level replication count and seed schedule reach the runner."""

    calls: list[int] = []

    def counted(state: Any, params: Any) -> dict[str, Any]:
        query = state["ncm_query_data"]
        calls.append(int(params["__seed__"]))
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {
                        "world_index": 0,
                        "firm_survival": {"mean": float(len(query.interventions))},
                    }
                ]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(counted))
    request = _request().model_copy(update={"seed": 17, "replications": 2})
    result = JointSimulationHorizonController().run(request)

    assert len(calls) == 6
    assert calls.count(17) == 3
    assert calls.count(18) == 3
    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert joint.points[0].engine_state["replication_count"] == 2
    assert joint.points[0].engine_state["replication_seeds"] == [17, 18]
    assert result.diagnostics["requested_replications"] == 2
    assert result.diagnostics["replication_seeds"] == [17, 18]


def test_ncm_evidence_none_and_explicit_empty_are_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B19: explicit empty evidence must not truthiness-fallback to baseline."""

    observed: list[dict[str, float]] = []

    def counted(state: Any, params: Any) -> dict[str, Any]:
        del params
        query = state["ncm_query_data"]
        observed.append(dict(query.evidence))
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {"world_index": 0, "firm_survival": {"mean": 1.0}}
                ]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(counted))
    controller = JointSimulationHorizonController()
    controller.run(_request().model_copy(update={"evidence_state": None}))
    controller.run(_request().model_copy(update={"evidence_state": {}}))

    assert observed[0] == {
        "income_delta": 0.0,
        "balance_delta": 0.0,
        "firm_survival": 1.0,
    }
    assert observed[3] == {}


def test_three_atom_controller_reports_real_higher_order_residual_and_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B26: a real three-atom run exposes order-three non-additivity."""

    def triple_only(state: Any, params: Any) -> dict[str, Any]:
        del params
        query = state["ncm_query_data"]
        value = 1.0 if len(query.interventions[0]) == 3 else 0.0
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {"world_index": 0, "firm_survival": {"mean": value}}
                ]
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(triple_only))
    request = _request()
    world_ref = request.world_model_record.world_model_record_id
    third = _atom(
        intervention_id="third_atom",
        causal_variable="agents.income",
        engine_variable="income_delta",
        value=1.0,
        world_model_record_ref=world_ref,
    )
    request = request.model_copy(
        update={
            "intervention_atoms": (*request.intervention_atoms, third),
            "baseline_state": {"firm_survival": 0.0},
        }
    )

    result = JointSimulationHorizonController().run(request)

    assert result.higher_order_residuals == {"firm_survival": {0: 1.0}}
    assert result.feedback_classification.numeric_interaction == "non_additive"
    assert result.feedback_classification.checked_interaction_orders == (1, 2, 3)
    assert result.diagnostics["checked_interaction_orders"] == [1, 2, 3]


def test_joint_simulation_requires_explicit_selected_outcome_baseline() -> None:
    """B19: missing comparator state must not silently become numeric zero."""

    request = _request().model_copy(update={"baseline_state": {}})

    with pytest.raises(JointSimulationControllerError) as raised:
        JointSimulationHorizonController().run(request)

    assert raised.value.code == "baseline_state_missing_for_outcome"


def test_explicit_comparator_makes_equal_scenarios_zero_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B19: a measured comparator, not zero, defines the effect origin."""

    def fixed_outcome(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {"world_index": 0, "firm_survival": {"mean": 100.0}},
                ],
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fixed_outcome))
    request = _request().model_copy(
        update={"baseline_state": {"firm_survival": 100.0}},
    )

    result = JointSimulationHorizonController().run(request)

    assert all(
        point.effect == {"firm_survival": 0.0}
        for trajectory in result.trajectories
        for point in trajectory.points
    )


def test_joint_simulation_reuses_physical_spec_across_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B23: the joint role reuses its identical pair calculation."""

    original = NCMEngineMethod.pure_step
    calls: list[dict[str, Any]] = []

    def counted(state: Any, params: Any) -> dict[str, Any]:
        calls.append(dict(params))
        return original(state, params)

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(counted))
    result = JointSimulationHorizonController().run(_request())

    assert len(calls) == 3
    pair_ref = result.trajectory_for("pairwise", ("income_subsidy", "balance_grant")).diagnostics[
        "physical_run_ref"
    ]
    joint_ref = result.trajectory_for("joint", ("income_subsidy", "balance_grant")).diagnostics[
        "physical_run_ref"
    ]
    assert pair_ref == joint_ref


def test_joint_residual_keeps_higher_order_interaction_visible() -> None:
    """B26: zero pairwise terms do not prove global additivity."""

    trajectories = [
        SimulationTrajectory(
            run_level="individual",
            atom_ids=(atom,),
            engine_kind="method_registry_estimator",
            method_fqn="tests.sim03",
            objective_ref="objective://sim03",
            points=(TrajectoryPoint(step=0, outcomes={"y": 0.0}, effect={"y": 0.0}),),
        )
        for atom in ("a", "b", "c")
    ]
    trajectories.extend(
        SimulationTrajectory(
            run_level="pairwise",
            atom_ids=pair,
            engine_kind="method_registry_estimator",
            method_fqn="tests.sim03",
            objective_ref="objective://sim03",
            points=(TrajectoryPoint(step=0, outcomes={"y": 0.0}, effect={"y": 0.0}),),
        )
        for pair in (("a", "b"), ("a", "c"), ("b", "c"))
    )
    trajectories.append(
        SimulationTrajectory(
            run_level="joint",
            atom_ids=("a", "b", "c"),
            engine_kind="method_registry_estimator",
            method_fqn="tests.sim03",
            objective_ref="objective://sim03",
            points=(TrajectoryPoint(step=0, outcomes={"y": 1.0}, effect={"y": 1.0}),),
        )
    )

    residuals = _higher_order_residuals(trajectories, ("y",))

    assert residuals == {"y": {0: 1.0}}
