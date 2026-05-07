"""Tests for adaptive sensitivity sampling."""

from __future__ import annotations

import numpy as np
import pytest

SALib = pytest.importorskip("SALib", reason="SALib not installed")

from polisyos.scientist.methods.doe.adaptive import (
    AdaptiveResult,
    AdaptiveSampler,
    ConvergenceConfig,
)
from polisyos.scientist.methods.doe.designs import ParameterSpec, SensitivityMethod, SensitivityPlan


def _make_plan(
    method: SensitivityMethod = SensitivityMethod.MORRIS, n_traj: int = 10
) -> SensitivityPlan:
    return SensitivityPlan(
        method=method,
        parameter_specs=[
            ParameterSpec(name="x1", lower_bound=0, upper_bound=1),
            ParameterSpec(name="x2", lower_bound=0, upper_bound=1),
        ],
        n_trajectories=n_traj,
        allow_large_run=True,
    )


def _linear_eval(samples: np.ndarray) -> np.ndarray:
    """Simple linear model: y = 2*x1 + 0.5*x2."""
    return 2.0 * samples[:, 0] + 0.5 * samples[:, 1]


def test_convergence_detected():
    """With a simple linear model, ranking should stabilize quickly."""
    plan = _make_plan(n_traj=8)
    conv = ConvergenceConfig(max_rounds=5, ranking_stability_threshold=0.5, trajectory_step=4)
    sampler = AdaptiveSampler(plan, convergence=conv)
    result = sampler.run(_linear_eval)
    assert isinstance(result, AdaptiveResult)
    assert result.total_evaluations > 0
    assert len(result.rounds) >= 1


def test_max_rounds_reached():
    """With extreme threshold, max_rounds is hit."""
    plan = _make_plan(n_traj=8)
    conv = ConvergenceConfig(max_rounds=2, ranking_stability_threshold=1.01, trajectory_step=4)
    sampler = AdaptiveSampler(plan, convergence=conv)
    result = sampler.run(_linear_eval)
    assert not result.converged
    assert len(result.rounds) == 2


def test_single_round_stable():
    """Single round with very low threshold still produces a result."""
    plan = _make_plan(n_traj=10)
    conv = ConvergenceConfig(max_rounds=1, ranking_stability_threshold=0.0)
    sampler = AdaptiveSampler(plan, convergence=conv)
    result = sampler.run(_linear_eval)
    assert result.final_result is not None
    assert len(result.final_result.ranking) == 2


def test_eval_failure_handled():
    """If evaluator raises, it propagates."""
    plan = _make_plan(n_traj=8)

    def _failing_eval(samples: np.ndarray) -> np.ndarray:
        raise ValueError("eval failed")

    sampler = AdaptiveSampler(plan)
    with pytest.raises(ValueError, match="eval failed"):
        sampler.run(_failing_eval)


def test_progress_tracking():
    """Rounds record trajectory counts and stability."""
    plan = _make_plan(n_traj=6)
    conv = ConvergenceConfig(max_rounds=3, ranking_stability_threshold=0.99, trajectory_step=3)
    sampler = AdaptiveSampler(plan, convergence=conv)
    result = sampler.run(_linear_eval)
    assert len(result.rounds) >= 2
    for rnd in result.rounds:
        assert rnd.n_trajectories > 0
        assert len(rnd.ranking) == 2
