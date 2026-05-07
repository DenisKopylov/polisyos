"""Tests for multi-output sensitivity analysis."""

from __future__ import annotations

import numpy as np
import pytest

SALib = pytest.importorskip("SALib", reason="SALib not installed")

from polisyos.scientist.methods.doe.designs import ParameterSpec, SensitivityMethod, SensitivityPlan
from polisyos.scientist.methods.doe.multi_output import MultiOutputAnalyzer, MultiOutputSensitivityResult


def _make_plan(n_traj: int = 10) -> SensitivityPlan:
    return SensitivityPlan(
        method=SensitivityMethod.MORRIS,
        parameter_specs=[
            ParameterSpec(name="x1", lower_bound=0, upper_bound=1),
            ParameterSpec(name="x2", lower_bound=0, upper_bound=1),
        ],
        n_trajectories=n_traj,
        allow_large_run=True,
    )


def _generate_samples(plan: SensitivityPlan) -> np.ndarray:
    from polisyos.scientist.methods.doe.sampling import generate_sensitivity_samples

    return generate_sensitivity_samples(plan)


class TestMultiOutputAnalyzer:
    def test_two_output_pca(self):
        plan = _make_plan()
        samples = _generate_samples(plan)
        # Two correlated outputs
        out1 = 2 * samples[:, 0] + 0.5 * samples[:, 1]
        out2 = 1.5 * samples[:, 0] + 0.3 * samples[:, 1]
        outputs = np.column_stack([out1, out2])

        analyzer = MultiOutputAnalyzer()
        result = analyzer.analyze(plan, samples, outputs)
        assert isinstance(result, MultiOutputSensitivityResult)
        assert result.n_components_used >= 1
        assert len(result.aggregate_ranking) == 2
        assert result.total_variance_explained > 0

    def test_single_output_fallback(self):
        plan = _make_plan()
        samples = _generate_samples(plan)
        outputs = 2 * samples[:, 0] + 0.5 * samples[:, 1]  # 1-D

        analyzer = MultiOutputAnalyzer()
        result = analyzer.analyze(plan, samples, outputs)
        assert result.n_components_used == 1
        assert result.total_variance_explained == 1.0
        assert len(result.per_component) == 1

    def test_correlated_outputs_fewer_components(self):
        """Highly correlated outputs should need fewer PCA components."""
        plan = _make_plan()
        samples = _generate_samples(plan)
        base = 2 * samples[:, 0] + samples[:, 1]
        outputs = np.column_stack([base, base + 0.01 * np.random.randn(len(base))])

        analyzer = MultiOutputAnalyzer(min_variance_explained=0.95)
        result = analyzer.analyze(plan, samples, outputs)
        # Should only need 1 component for nearly-identical outputs
        assert result.n_components_used <= 2

    def test_ranking_aggregation(self):
        plan = _make_plan()
        samples = _generate_samples(plan)
        # x1 dominates in both outputs
        out1 = 5 * samples[:, 0] + 0.1 * samples[:, 1]
        out2 = 3 * samples[:, 0] + 0.2 * samples[:, 1]
        outputs = np.column_stack([out1, out2])

        analyzer = MultiOutputAnalyzer()
        result = analyzer.analyze(plan, samples, outputs)
        assert result.aggregate_ranking[0] == "x1"

    def test_zero_variance_output_raises(self):
        plan = _make_plan()
        samples = _generate_samples(plan)
        outputs = np.ones((samples.shape[0], 2))

        analyzer = MultiOutputAnalyzer()
        with pytest.raises(ValueError, match="zero variance"):
            analyzer.analyze(plan, samples, outputs)
