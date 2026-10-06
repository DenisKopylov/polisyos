"""Tests for enhanced analysis features (S2 ranking, DROP_FAILED for Sobol, distributions)."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.scientist.methods.doe.analysis import _plan_to_salib_problem
from polisyos.scientist.methods.doe.designs import (
    ParameterDist,
    ParameterSpec,
    RunFailurePolicy,
    SensitivityMethod,
    SensitivityPlan,
    TriangularDistributionSpecV1,
)
from polisyos.scientist.methods.doe.stress_report import VulnerabilityType

_salib_available = True
try:
    import SALib  # noqa: F401
except ImportError:
    _salib_available = False

_skip_no_salib = pytest.mark.skipif(not _salib_available, reason="SALib not installed")


@_skip_no_salib
class TestS2InteractionRanking:
    @pytest.fixture
    def sobol_plan(self):
        return SensitivityPlan(
            method=SensitivityMethod.SOBOL,
            input_law="independent",
            seed=31,
            parameter_specs=[
                ParameterSpec(name="x1", lower_bound=0, upper_bound=1),
                ParameterSpec(name="x2", lower_bound=0, upper_bound=1),
            ],
            n_trajectories=1024,
            max_estimated_runs=6144,
        )

    def test_native_interaction_matches_independent_anova_oracle(self, sobol_plan):
        from polisyos.scientist.methods.doe.analysis import analyze_sensitivity
        from polisyos.scientist.methods.doe.sampling import generate_sensitivity_samples

        samples = generate_sensitivity_samples(sobol_plan)
        outputs = samples[:, 0] + samples[:, 1] + 2 * samples[:, 0] * samples[:, 1]
        result = analyze_sensitivity(sobol_plan, samples, outputs)
        # For centered X,Z iid Uniform[-.5,.5], Y=1.5+2X+2Z+2XZ.
        # Orthogonal variances are 1/3, 1/3, 1/36, totaling 25/36.
        # This truth is derived from the input law, independently of SALib outputs.
        # The fixed 1024-block seeded numerical design has absolute tolerance .01.
        assert result.s1 == pytest.approx({"x1": 12 / 25, "x2": 12 / 25}, abs=0.01)
        assert result.st == pytest.approx({"x1": 13 / 25, "x2": 13 / 25}, abs=0.01)
        assert result.s2["x1"]["x2"] == pytest.approx(1 / 25, abs=0.01)
        assert len(result.top_interactions) == 1
        left, right, interaction = result.top_interactions[0]
        assert (left, right) == ("x1", "x2")
        assert interaction == pytest.approx(1 / 25, abs=0.01)

    def test_no_interactions_for_morris(self):
        from polisyos.scientist.methods.doe.analysis import analyze_sensitivity
        from polisyos.scientist.methods.doe.sampling import generate_sensitivity_samples

        plan = SensitivityPlan(
            method=SensitivityMethod.MORRIS,
            parameter_specs=[
                ParameterSpec(name="x1", lower_bound=0, upper_bound=1),
                ParameterSpec(name="x2", lower_bound=0, upper_bound=1),
            ],
            n_trajectories=10,
            allow_large_run=True,
        )
        samples = generate_sensitivity_samples(plan)
        outputs = 2.0 * samples[:, 0] + 0.5 * samples[:, 1]
        result = analyze_sensitivity(plan, samples, outputs)
        assert result.top_interactions == []


class TestTriangularDistribution:
    def test_triangular_in_problem(self):
        plan = SensitivityPlan(
            method=SensitivityMethod.MORRIS,
            parameter_specs=[
                ParameterSpec(
                    name="x1",
                    lower_bound=0,
                    upper_bound=1,
                    distribution=ParameterDist.TRIANGULAR,
                    distribution_spec=TriangularDistributionSpecV1(mode_fraction=0.5),
                ),
                ParameterSpec(
                    name="x2", lower_bound=0, upper_bound=1, distribution=ParameterDist.UNIFORM
                ),
            ],
            n_trajectories=10,
            allow_large_run=True,
        )
        problem = _plan_to_salib_problem(plan)
        assert "dists" in problem
        assert problem["dists"] == ["triang", "unif"]
        assert problem["bounds"] == [[0, 1, 0.5], [0, 1]]

    def test_uniform_only_no_dists(self):
        plan = SensitivityPlan(
            method=SensitivityMethod.MORRIS,
            parameter_specs=[
                ParameterSpec(name="x1", lower_bound=0, upper_bound=1),
            ],
            n_trajectories=10,
        )
        problem = _plan_to_salib_problem(plan)
        assert "dists" not in problem


class TestExtendedVulnerabilityTypes:
    def test_new_types_exist(self):
        assert VulnerabilityType.DISTRIBUTIONAL == "distributional"
        assert VulnerabilityType.COMBINATORIAL == "combinatorial"
        assert VulnerabilityType.TEMPORAL == "temporal"


@_skip_no_salib
class TestDropFailedForSobol:
    def test_drop_failed_sobol_rejected_to_preserve_sample_geometry(self):
        from polisyos.scientist.methods.doe.analysis import analyze_sensitivity
        from polisyos.scientist.methods.doe.sampling import generate_sensitivity_samples

        plan = SensitivityPlan(
            method=SensitivityMethod.SOBOL,
            input_law="independent",
            seed=31,
            parameter_specs=[
                ParameterSpec(name="x1", lower_bound=0, upper_bound=1),
                ParameterSpec(name="x2", lower_bound=0, upper_bound=1),
            ],
            n_trajectories=64,
            allow_large_run=True,
            run_failure_policy=RunFailurePolicy.DROP_FAILED,
            min_success_rate=0.5,
        )
        samples = generate_sensitivity_samples(plan)
        outputs = samples[:, 0] + samples[:, 1]
        outputs[0] = np.nan
        outputs[1] = np.nan
        with pytest.raises(ValueError, match="structured SOBOL"):
            analyze_sensitivity(plan, samples, outputs)

    def test_drop_failed_fast_still_raises(self):
        from polisyos.scientist.methods.doe.analysis import analyze_sensitivity
        from polisyos.scientist.methods.doe.sampling import generate_sensitivity_samples

        plan = SensitivityPlan(
            method=SensitivityMethod.FAST,
            parameter_specs=[
                ParameterSpec(name="x1", lower_bound=0, upper_bound=1),
                ParameterSpec(name="x2", lower_bound=0, upper_bound=1),
            ],
            n_trajectories=65,
            allow_large_run=True,
            run_failure_policy=RunFailurePolicy.DROP_FAILED,
            min_success_rate=0.5,
        )
        samples = generate_sensitivity_samples(plan)
        outputs = samples[:, 0] + samples[:, 1]
        outputs[0] = np.nan
        with pytest.raises(ValueError, match="DROP_FAILED is only supported"):
            analyze_sensitivity(plan, samples, outputs)
