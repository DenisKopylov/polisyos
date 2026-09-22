"""Regression tests for the bounded DOE-01 execution contract."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.scientist.methods.doe import sampling as sampling_module
from polisyos.scientist.methods.doe.adaptive import AdaptiveSampler, ConvergenceConfig
from polisyos.scientist.methods.doe.designs import (
    AdversarialPlan,
    AdversarialStrategy,
    ParameterSpec,
    SensitivityMethod,
    SensitivityPlan,
)


def test_grid_extreme_materializes_only_the_declared_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """The capped GRID_EXTREME prefix must not enumerate the full product first."""
    original_product = sampling_module.itertools.product
    yielded = 0

    def counted_product(*iterables: object):
        nonlocal yielded
        for corner in original_product(*iterables):
            yielded += 1
            yield corner

    monkeypatch.setattr(sampling_module.itertools, "product", counted_product)
    plan = AdversarialPlan(
        parameter_specs=[
            ParameterSpec(name=f"x{i}", lower_bound=0.0, upper_bound=1.0)
            for i in range(12)
        ],
        strategy=AdversarialStrategy.GRID_EXTREME,
        max_iterations=3,
    )

    samples = sampling_module.generate_adversarial_samples(plan)

    assert samples.shape == (3, 12)
    assert yielded == 3
    assert samples.base is None


def _adaptive_plan(
    *,
    n_trajectories: int,
    max_estimated_runs: int,
    allow_large_run: bool,
) -> SensitivityPlan:
    return SensitivityPlan(
        method=SensitivityMethod.MORRIS,
        parameter_specs=[
            ParameterSpec(name="x1", lower_bound=0.0, upper_bound=1.0),
            ParameterSpec(name="x2", lower_bound=0.0, upper_bound=1.0),
        ],
        n_trajectories=n_trajectories,
        max_estimated_runs=max_estimated_runs,
        allow_large_run=allow_large_run,
    )


def test_adaptive_sampler_returns_last_completed_round_without_hidden_evaluation() -> None:
    """Exhausting rounds must not evaluate an unrecorded extra sample batch."""
    calls: list[np.ndarray] = []

    def evaluator(samples: np.ndarray) -> np.ndarray:
        calls.append(samples.copy())
        return samples[:, 0] + 2.0 * samples[:, 1]

    result = AdaptiveSampler(
        _adaptive_plan(n_trajectories=2, max_estimated_runs=100, allow_large_run=True),
        convergence=ConvergenceConfig(
            max_rounds=2,
            ranking_stability_threshold=1.01,
            trajectory_step=1,
        ),
    ).run(evaluator)

    assert len(calls) == 2
    assert result.total_evaluations == sum(len(batch) for batch in calls)
    assert result.final_result.total_runs == len(calls[-1])
    assert result.stop_reason == "max_rounds_reached"


def test_adaptive_sampler_stops_before_oversized_follow_up_without_override() -> None:
    """A false large-run permission must stop before evaluator work exceeds the cap."""
    calls: list[np.ndarray] = []

    def evaluator(samples: np.ndarray) -> np.ndarray:
        calls.append(samples.copy())
        return samples[:, 0] + samples[:, 1]

    result = AdaptiveSampler(
        _adaptive_plan(n_trajectories=1, max_estimated_runs=3, allow_large_run=False),
        convergence=ConvergenceConfig(
            max_rounds=3,
            ranking_stability_threshold=1.01,
            trajectory_step=1,
        ),
    ).run(evaluator)

    assert len(calls) == 1
    assert len(result.rounds) == 1
    assert result.total_evaluations == len(calls[0])
    assert result.stop_reason == "max_estimated_runs_exceeded"


def test_adaptive_sampler_rejects_zero_round_budget_before_evaluation() -> None:
    with pytest.raises(ValueError, match="max_rounds"):
        ConvergenceConfig(max_rounds=0)
