"""Tests for ranking stability checker."""

from __future__ import annotations

import numpy as np
import pytest

SALib = pytest.importorskip("SALib", reason="SALib not installed")

from polisyos.scientist.methods.doe.designs import ParameterSpec, SensitivityMethod, SensitivityPlan
from polisyos.scientist.methods.doe.stability import RankingStabilityChecker, StabilityReport


def _make_plan() -> SensitivityPlan:
    return SensitivityPlan(
        method=SensitivityMethod.MORRIS,
        parameter_specs=[
            ParameterSpec(name="x1", lower_bound=0, upper_bound=1),
            ParameterSpec(name="x2", lower_bound=0, upper_bound=1),
        ],
        n_trajectories=10,
        allow_large_run=True,
    )


def _generate_data(plan: SensitivityPlan):
    from polisyos.scientist.methods.doe.sampling import generate_sensitivity_samples

    samples = generate_sensitivity_samples(plan)
    outputs = 3.0 * samples[:, 0] + 0.1 * samples[:, 1]
    return samples, outputs


class TestRankingStabilityChecker:
    def test_stable_ranking(self):
        plan = _make_plan()
        samples, outputs = _generate_data(plan)
        checker = RankingStabilityChecker(n_bootstrap=20, seed=42)
        report = checker.check(plan, samples, outputs)
        assert isinstance(report, StabilityReport)
        assert report.rank_stability_score > 0.0
        assert report.n_bootstrap == 20

    def test_unstable_detection(self):
        """With noisy data, some parameters may be unstable."""
        plan = _make_plan()
        samples, _ = _generate_data(plan)
        # Make outputs pure noise — rankings should be unstable
        rng = np.random.default_rng(123)
        noisy_outputs = rng.standard_normal(samples.shape[0])
        checker = RankingStabilityChecker(n_bootstrap=20, seed=42)
        report = checker.check(plan, samples, noisy_outputs)
        # With pure noise, stability should be lower
        assert isinstance(report, StabilityReport)
        assert len(report.rank_variance) == 2

    def test_small_sample_warning(self):
        """Too few samples returns empty report."""
        plan = _make_plan()
        samples = np.array([[0.1, 0.2], [0.3, 0.4]])
        outputs = np.array([1.0, 2.0])
        checker = RankingStabilityChecker(n_bootstrap=10)
        report = checker.check(plan, samples, outputs)
        assert report.rank_stability_score == 0.0
        assert report.n_bootstrap == 0

    def test_empty_returns_report(self):
        """Edge case: checker works with plan but no convergence."""
        plan = _make_plan()
        samples, outputs = _generate_data(plan)
        checker = RankingStabilityChecker(n_bootstrap=5)
        report = checker.check(plan, samples, outputs)
        assert isinstance(report, StabilityReport)
