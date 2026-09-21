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
from tests.unit.runtime.quality.test_joint_simulation_horizon import _request


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


def test_paired_replicates_require_distinct_seeds() -> None:
    """B21: duplicate seeds are not independent replications."""

    with pytest.raises(ValueError, match="seeds must be unique"):
        paired_monte_carlo_effect(
            lambda seed: {"welfare": float(seed)},
            lambda seed: {"welfare": float(seed + 1)},
            seeds=(7, 7),
            metric_names=("welfare",),
        )


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
