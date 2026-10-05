"""Behavioral controls for Morris geometry before point and uncertainty analysis."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("SALib", reason="Morris geometry controls require a genuine SALib backend")

from polisyos.scientist.methods.doe.analysis import analyze_sensitivity
from polisyos.scientist.methods.doe.designs import (
    NormalDistributionSpecV1,
    ParameterDist,
    ParameterSpec,
    RunFailurePolicy,
    SensitivityPlan,
    TriangularDistributionSpecV1,
)
from polisyos.scientist.methods.doe.multi_output import MultiOutputAnalyzer
from polisyos.scientist.methods.doe.sampling import generate_sensitivity_samples
from polisyos.scientist.methods.doe.stability import RankingStabilityChecker
from polisyos.scientist.methods.doe.uncertainty import (
    SensitivityUncertaintyConfig,
    morris_elementary_effects_from_samples,
)


def _plan() -> SensitivityPlan:
    return SensitivityPlan(
        parameter_specs=[
            ParameterSpec(name="x", lower_bound=0.0, upper_bound=10.0),
            ParameterSpec(name="z", lower_bound=0.0, upper_bound=1.0),
        ],
        n_trajectories=8,
        seed=17,
        uncertainty=SensitivityUncertaintyConfig(
            enabled=True,
            method="percentile",
            n_resamples=20,
            random_seed=7,
        ),
    )


def _corrupt(samples: np.ndarray, mutation: str) -> np.ndarray:
    corrupted = samples.copy()
    if mutation == "two_coordinates":
        # Add a second changed coordinate while keeping all points on-grid.
        first_changed = np.flatnonzero(samples[1] != samples[0])[0]
        other = 1 - first_changed
        corrupted[1, other] = samples[0, other] + (
            -2.0 / 3.0 if samples[0, other] > 0.5 * (10.0 if other == 0 else 1.0) else 2.0 / 3.0
        ) * (10.0 if other == 0 else 1.0)
    elif mutation == "tiny_second_coordinate":
        first_changed = np.flatnonzero(samples[1] != samples[0])[0]
        corrupted[1, 1 - first_changed] += 1e-10
    elif mutation == "off_grid":
        corrupted[:3, 1] += 0.01
    elif mutation == "wrong_delta":
        # Valid grid and OAT structure alone do not establish SALib's delta.
        corrupted[:3] = [[0.0, 0.0], [10.0 / 3.0, 0.0], [10.0 / 3.0, 2.0 / 3.0]]
    elif mutation == "repeated_factor":
        corrupted[:3] = [[0.0, 0.0], [20.0 / 3.0, 0.0], [0.0, 0.0]]
    elif mutation == "zero_step":
        corrupted[1] = corrupted[0]
    elif mutation == "cross_trajectory_splice":
        corrupted[[1, 4]] = corrupted[[4, 1]]
    elif mutation == "outside_support":
        corrupted[:3, 0] += 20.0
    elif mutation == "nonfinite":
        corrupted[1, 0] = np.nan
    else:
        raise AssertionError(f"Unknown test mutation: {mutation}")
    return corrupted


@pytest.mark.parametrize(
    "mutation",
    [
        "two_coordinates",
        "tiny_second_coordinate",
        "off_grid",
        "wrong_delta",
        "repeated_factor",
        "zero_step",
        "cross_trajectory_splice",
        "outside_support",
        "nonfinite",
    ],
)
def test_invalid_morris_geometry_cannot_emit_point_or_pca_result(mutation: str) -> None:
    """Divisible finite matrices must still prove the defining trajectory geometry."""
    plan = _plan()
    samples = generate_sensitivity_samples(plan)
    outputs = 2.0 * samples[:, 0] + 3.0 * samples[:, 1]
    corrupted = _corrupt(samples, mutation)
    with pytest.raises(ValueError):
        analyze_sensitivity(plan, corrupted, outputs)
    with pytest.raises(ValueError):
        MultiOutputAnalyzer().analyze(plan, corrupted, np.column_stack([outputs, -outputs]))
    with pytest.raises(ValueError):
        RankingStabilityChecker(n_bootstrap=20, seed=23).check(plan, corrupted, outputs)
    with pytest.raises(ValueError):
        morris_elementary_effects_from_samples(
            corrupted,
            outputs,
            ["x", "z"],
            parameter_bounds={"x": (0.0, 10.0), "z": (0.0, 1.0)},
            num_levels=4,
        )


@pytest.mark.parametrize("num_levels", [2, 3, 4, 6])
def test_native_morris_blocks_preserve_point_uncertainty_under_units_and_order(
    num_levels: int,
) -> None:
    """Whole block permutation/reversal and physical unit changes preserve the effect law."""
    plan = _plan()
    for parameter in plan.parameter_specs:
        parameter.num_levels = num_levels
    samples = generate_sensitivity_samples(plan)
    blocks = samples.reshape(-1, 3, 2)[::-1, ::-1, :]
    reordered = blocks.reshape(-1, 2)
    baseline = analyze_sensitivity(plan, samples, 2.0 * samples[:, 0] + 3.0 * samples[:, 1])
    restored = analyze_sensitivity(plan, reordered, 2.0 * reordered[:, 0] + 3.0 * reordered[:, 1])
    assert baseline.mu_star == pytest.approx({"x": 20.0, "z": 3.0})
    assert restored.mu_star == pytest.approx(baseline.mu_star)

    # Express x in centimetres while retaining the same physical response.
    scaled_plan = SensitivityPlan.model_validate(plan.model_dump())
    scaled_plan.parameter_specs[0].upper_bound = 1000.0
    scaled = samples.copy()
    scaled[:, 0] *= 100.0
    scaled_result = analyze_sensitivity(
        scaled_plan,
        scaled,
        0.02 * scaled[:, 0] + 3.0 * scaled[:, 1],
    )
    assert scaled_result.mu_star == pytest.approx(baseline.mu_star)
    for result in (baseline, restored, scaled_result):
        assert result.uncertainty is not None
        estimates = {
            item.parameter: item.estimate
            for item in result.uncertainty.sensitivity_results
            if item.index == "mu_star"
        }
        assert estimates == pytest.approx(result.mu_star)


@pytest.mark.parametrize("distribution", [ParameterDist.NORMAL, ParameterDist.TRIANGULAR])
def test_admitted_nonuniform_designs_use_their_actual_source_coordinates(
    distribution: ParameterDist,
) -> None:
    """A genuine transformed design passes; an off-grid perturbation fails before SALib."""
    plan = _plan()
    parameter = plan.parameter_specs[1]
    parameter.distribution = distribution
    parameter.distribution_spec = (
        NormalDistributionSpecV1(mean=0.5, std=0.2)
        if distribution == ParameterDist.NORMAL
        else TriangularDistributionSpecV1(mode_fraction=0.75)
    )
    samples = generate_sensitivity_samples(plan)
    outputs = 2.0 * samples[:, 0] + 3.0 * samples[:, 1]
    result = analyze_sensitivity(plan, samples, outputs)
    assert all(np.isfinite(value) for value in result.mu_star.values())
    assert result.metadata["uncertainty_status"] == "unavailable"
    samples[:3, 1] += 0.01
    with pytest.raises(ValueError, match="support|grid"):
        analyze_sensitivity(plan, samples, outputs)


def test_drop_failed_keeps_only_valid_original_morris_blocks() -> None:
    plan = _plan()
    plan.run_failure_policy = RunFailurePolicy.DROP_FAILED
    samples = generate_sensitivity_samples(plan)
    outputs = 2.0 * samples[:, 0] + 3.0 * samples[:, 1]
    samples[1, 0] = np.nan
    result = analyze_sensitivity(plan, samples, outputs)
    assert result.metadata["effective_trajectory_ids"] == list(range(1, 8))
    assert result.failed_runs == 1
    assert result.metadata["effective_run_count"] == 21
    assert result.mu_star == pytest.approx({"x": 20.0, "z": 3.0})
    assert result.uncertainty is None


def test_stability_reads_back_rankings_from_whole_native_morris_blocks() -> None:
    """A consumer must resample actual trajectories to retain a valid analytic ranking."""
    plan = _plan()
    samples = generate_sensitivity_samples(plan)
    outputs = 2.0 * samples[:, 0] + 3.0 * samples[:, 1]
    report = RankingStabilityChecker(n_bootstrap=8, seed=23).check(plan, samples, outputs)
    assert report.n_bootstrap == 8
    assert report.rank_stability_score == pytest.approx(1.0)
    assert report.rank_variance == {"x": 0.0, "z": 0.0}


@pytest.mark.parametrize("failure_policy", list(RunFailurePolicy))
def test_stability_cannot_launder_failed_original_runs_through_resampling(
    failure_policy: RunFailurePolicy,
) -> None:
    plan = _plan()
    plan.run_failure_policy = failure_policy
    samples = generate_sensitivity_samples(plan)
    outputs = 2.0 * samples[:, 0] + 3.0 * samples[:, 1]
    outputs[1] = np.nan
    with pytest.raises(ValueError, match="failed|successful trajectories"):
        RankingStabilityChecker(n_bootstrap=20, seed=23).check(plan, samples, outputs)


def test_wrong_declared_grid_cannot_authorize_existing_sample_matrix() -> None:
    plan = _plan()
    samples = generate_sensitivity_samples(plan)
    outputs = 2.0 * samples[:, 0] + 3.0 * samples[:, 1]
    plan.parameter_specs[0].num_levels = 6
    plan.parameter_specs[1].num_levels = 6
    with pytest.raises(ValueError, match="grid"):
        analyze_sensitivity(plan, samples, outputs)
