"""Distinguishing witnesses for the bounded DOE-03 repair.

The tests in this module deliberately exercise the real DOE entry points.  The
small matrices are witnesses for B102--B105, not a statistical coverage
campaign or evidence that three observations are scientifically sufficient.
"""

from __future__ import annotations

import builtins

import numpy as np
import pytest

pytest.importorskip("SALib", reason="DOE-03 requires the pinned SALib backend")

from polisyos.scientist.methods.doe.analysis import analyze_sensitivity
from polisyos.scientist.methods.doe.designs import (
    ParameterSpec,
    RunFailurePolicy,
    SensitivityMethod,
    SensitivityPlan,
)
from polisyos.scientist.methods.doe.multi_output import MultiOutputAnalyzer
from polisyos.scientist.methods.doe.sampling import generate_sensitivity_samples
from polisyos.scientist.methods.doe.uncertainty import (
    SensitivityUncertaintyConfig,
    morris_elementary_effects_from_samples,
)


def _morris_plan(
    *,
    policy: RunFailurePolicy = RunFailurePolicy.FAIL_FAST,
    min_success_rate: float = 0.5,
    n_trajectories: int = 4,
    uncertainty: SensitivityUncertaintyConfig | None = None,
) -> SensitivityPlan:
    return SensitivityPlan(
        method=SensitivityMethod.MORRIS,
        parameter_specs=[
            ParameterSpec(name="x1", lower_bound=0.0, upper_bound=1.0),
            ParameterSpec(name="x2", lower_bound=0.0, upper_bound=1.0),
        ],
        n_trajectories=n_trajectories,
        seed=17,
        allow_large_run=True,
        run_failure_policy=policy,
        min_success_rate=min_success_rate,
        uncertainty=uncertainty or SensitivityUncertaintyConfig(),
    )


@pytest.mark.parametrize(
    ("failed_rows", "expected_trajectory_ids", "expected_runs"),
    [
        ([1], [1, 2, 3], 9),
        ([1, 4, 5], [2, 3], 6),
    ],
)
def test_drop_failed_discards_whole_morris_trajectories(
    failed_rows: list[int],
    expected_trajectory_ids: list[int],
    expected_runs: int,
) -> None:
    """Partial Morris blocks are never re-paired by a divisibility coincidence."""
    plan = _morris_plan(policy=RunFailurePolicy.DROP_FAILED)
    samples = generate_sensitivity_samples(plan)
    outputs = samples[:, 0] + 2.0 * samples[:, 1]
    outputs[failed_rows] = np.nan

    result = analyze_sensitivity(plan, samples, outputs)

    assert result.total_runs == 12
    assert result.successful_runs == 12 - len(failed_rows)
    assert result.failed_runs == len(failed_rows)
    assert result.metadata["morris_trajectory_size"] == 3
    assert result.metadata["effective_trajectory_ids"] == expected_trajectory_ids
    assert result.metadata["effective_run_count"] == expected_runs
    assert result.metadata["failed_row_indices"] == failed_rows
    assert result.metadata["analysis_posture"] == "limited"
    assert result.metadata["selection_bias_status"] == "not_established"
    assert "drop_failed_selection_bias_not_established" in result.metadata["warnings"]


def test_multi_output_applies_fail_fast_before_pca() -> None:
    """A failed original run cannot disappear while outputs are reduced."""
    plan = _morris_plan(policy=RunFailurePolicy.FAIL_FAST)
    samples = generate_sensitivity_samples(plan)
    outputs = np.column_stack([samples[:, 0], samples[:, 1]])
    outputs[:3, :] = np.nan

    with pytest.raises(ValueError, match="failed simulation runs detected"):
        analyze_sensitivity(plan, samples, outputs[:, 0])
    with pytest.raises(ValueError, match="failed simulation runs detected"):
        MultiOutputAnalyzer().analyze(plan, samples, outputs)


def test_multi_output_enforces_min_success_rate_on_original_denominator() -> None:
    """PCA cannot turn an insufficient original batch into a successful one."""
    plan = _morris_plan(
        policy=RunFailurePolicy.IMPUTE_BASELINE,
        min_success_rate=0.9,
    )
    samples = generate_sensitivity_samples(plan)
    outputs = np.column_stack([samples[:, 0], samples[:, 1]])
    outputs[:3, :] = np.nan

    with pytest.raises(ValueError, match="below min_success_rate"):
        MultiOutputAnalyzer().analyze(plan, samples, outputs)


def test_multi_output_imputation_preserves_original_run_accounting() -> None:
    """An explicit imputation policy retains denominator and failure metadata."""
    plan = _morris_plan(policy=RunFailurePolicy.IMPUTE_BASELINE)
    samples = generate_sensitivity_samples(plan)
    outputs = np.column_stack([samples[:, 0], samples[:, 1]])
    outputs[:3, :] = np.nan

    result = MultiOutputAnalyzer().analyze(plan, samples, outputs)

    assert result.per_component
    component = result.per_component[0]
    assert component.total_runs == 12
    assert component.successful_runs == 9
    assert component.failed_runs == 3
    assert component.metadata["run_failure_policy"] == RunFailurePolicy.IMPUTE_BASELINE.value
    assert component.metadata["failed_row_indices"] == [0, 1, 2]


def test_nonfinite_input_is_accounted_as_failed_morris_run() -> None:
    """A finite output cannot turn a nonfinite input row into valid evidence."""
    plan = _morris_plan(policy=RunFailurePolicy.DROP_FAILED)
    samples = generate_sensitivity_samples(plan)
    outputs = samples[:, 0] + 2.0 * samples[:, 1]
    samples[0, 0] = np.nan

    result = analyze_sensitivity(plan, samples, outputs)

    assert result.failed_runs == 1
    assert result.metadata["failed_row_indices"] == [0]
    assert result.metadata["failed_row_reasons"] == [
        {"row_index": 0, "reason": "nonfinite_input"}
    ]
    assert result.metadata["effective_trajectory_ids"] == [1, 2, 3]


def test_pca_caps_components_to_centered_rank_for_wide_small_matrix() -> None:
    """A 3x5 matrix is algebraically limited to rank two after centering."""
    outputs = np.array(
        [
            [0.0, 0.0, 0.0, 0.0, 1.0],
            [1.0, 2.0, 3.0, 4.0, 0.0],
            [2.0, 4.0, 6.0, 8.0, 1.0],
        ]
    )
    analyzer = MultiOutputAnalyzer(max_components=5, min_variance_explained=1.0)

    components, variance_ratio = analyzer._run_pca(outputs)

    assert len(components) == 2
    assert len(variance_ratio) == 2
    assert sum(variance_ratio) == pytest.approx(1.0)
    assert all(np.all(np.isfinite(component)) for component in components)


def test_numpy_pca_fallback_matches_centered_rank(monkeypatch: pytest.MonkeyPatch) -> None:
    """The dependency-free fallback applies the same rank cap as sklearn."""
    outputs = np.array(
        [
            [0.0, 0.0, 0.0, 0.0, 1.0],
            [1.0, 2.0, 3.0, 4.0, 0.0],
            [2.0, 4.0, 6.0, 8.0, 1.0],
        ]
    )
    analyzer = MultiOutputAnalyzer(max_components=5, min_variance_explained=1.0)
    real_import = builtins.__import__

    def import_without_sklearn(name: str, *args: object, **kwargs: object) -> object:
        if name == "sklearn.decomposition" or name.startswith("sklearn."):
            raise ImportError("controlled DOE-03 fallback")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_sklearn)
    components, variance_ratio = analyzer._run_pca(outputs)

    assert len(components) == 2
    assert len(variance_ratio) == 2
    assert sum(variance_ratio) == pytest.approx(1.0)


def test_pca_reports_unmet_variance_threshold_when_component_cap_is_binding() -> None:
    """A capped PCA result exposes unmet explained-variance quality."""
    plan = _morris_plan(n_trajectories=2)
    samples = generate_sensitivity_samples(plan)
    outputs = np.array(
        [
            [1.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 1.0],
            [0.0, 0.0, 0.0, 0.0, 0.0],
        ]
    )
    result = MultiOutputAnalyzer(
        max_components=1,
        min_variance_explained=0.95,
    ).analyze(plan, samples, outputs)

    assert result.n_components_used == 1
    assert result.total_variance_explained < 0.95
    assert result.pca_variance_threshold == pytest.approx(0.95)
    assert result.pca_variance_threshold_status == "unmet_limited"
    assert result.per_component[0].metadata["pca_variance_threshold_status"] == (
        "unmet_limited"
    )


def test_morris_point_and_uncertainty_share_normalized_units() -> None:
    """For y=2x on [0, 10], point and uncertainty effects are both 20."""
    plan = SensitivityPlan(
        method=SensitivityMethod.MORRIS,
        parameter_specs=[ParameterSpec(name="x", lower_bound=0.0, upper_bound=10.0)],
        n_trajectories=4,
        seed=29,
        allow_large_run=True,
        uncertainty=SensitivityUncertaintyConfig(
            enabled=True,
            method="percentile",
            n_resamples=20,
            random_seed=7,
        ),
    )
    samples = generate_sensitivity_samples(plan)
    result = analyze_sensitivity(plan, samples, 2.0 * samples[:, 0])

    assert result.mu_star["x"] == pytest.approx(20.0)
    assert result.uncertainty is not None
    estimate = next(
        item
        for item in result.uncertainty.sensitivity_results
        if item.parameter == "x" and item.index == "mu_star"
    )
    assert estimate.estimate == pytest.approx(result.mu_star["x"])
    assert estimate.estimate == pytest.approx(20.0)


def test_morris_uncertainty_requires_explicit_coordinate_contract() -> None:
    """Unknown physical/normalized transforms fail closed instead of guessing."""
    samples = np.array([[0.0], [10.0], [2.0], [8.0]])
    outputs = 2.0 * samples[:, 0]

    with pytest.raises(ValueError, match="coordinate|bounds|normal"):
        morris_elementary_effects_from_samples(samples, outputs, ["x"])
