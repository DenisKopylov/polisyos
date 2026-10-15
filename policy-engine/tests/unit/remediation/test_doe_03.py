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
    MorrisStoragePayload,
    SensitivityUncertaintyConfig,
    analyze_morris_trajectory_bootstrap,
    morris_elementary_effects_from_samples,
    morris_elementary_effects_from_storage,
    morris_storage_from_elementary_effects,
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
    assert result.metadata["failed_row_reasons"] == [{"row_index": 0, "reason": "nonfinite_input"}]
    assert result.metadata["effective_trajectory_ids"] == [1, 2, 3]


def test_multi_output_drop_failed_propagates_selection_limit_before_uncertainty() -> None:
    """Dropped Morris blocks limit both components and aggregate projection."""
    plan = _morris_plan(
        policy=RunFailurePolicy.DROP_FAILED,
        uncertainty=SensitivityUncertaintyConfig(
            enabled=True,
            method="percentile",
            n_resamples=20,
            random_seed=7,
        ),
    )
    samples = generate_sensitivity_samples(plan)
    outputs = np.column_stack([samples[:, 0], samples[:, 1]])
    outputs[0, 0] = np.nan

    result = MultiOutputAnalyzer().analyze(plan, samples, outputs)

    assert result.metadata["analysis_posture"] == "limited"
    assert result.metadata["selection_bias_status"] == "not_established"
    assert result.metadata["effective_run_count"] == 9
    assert result.aggregate_ranking
    for component in result.per_component:
        assert component.metadata["analysis_posture"] == "limited"
        assert component.metadata["selection_bias_status"] == "not_established"
        assert component.metadata["uncertainty_status"] == "unavailable"
        assert component.uncertainty is None


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
    assert result.per_component[0].metadata["pca_variance_threshold_status"] == ("unmet_limited")


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

    with pytest.raises(ValueError, match=r"coordinate|bounds|normal"):
        morris_elementary_effects_from_samples(samples, outputs, ["x"])


def test_morris_effect_ci_and_json_retained_matrix_share_declared_units() -> None:
    """Actual Morris point, intervals, and JSON-retained effects obey one coordinate law."""
    config = SensitivityUncertaintyConfig(
        enabled=True,
        method="percentile",
        n_resamples=200,
        random_seed=41,
        interval_types=["marginal"],
    )
    cases = [
        (0.0, 10.0, 1.0),
        (0.0, 1000.0, 1.0),
        (-5.0, 5.0, 1.0),
        (0.0, 10.0, 1000.0),
    ]
    observed: list[tuple[float, tuple[float, float], float, tuple[float, float]]] = []

    for lower, upper, output_scale in cases:
        plan = SensitivityPlan(
            method=SensitivityMethod.MORRIS,
            parameter_specs=[
                ParameterSpec(
                    name="x",
                    lower_bound=lower,
                    upper_bound=upper,
                    num_levels=4,
                )
            ],
            n_trajectories=24,
            seed=37,
            allow_large_run=True,
            uncertainty=config,
        )
        samples = generate_sensitivity_samples(plan)
        unit_x = (samples[:, 0] - lower) / (upper - lower)
        outputs = output_scale * (20.0 * unit_x + 5.0 * np.square(unit_x))
        result = analyze_sensitivity(plan, samples, outputs)
        independent_effects = (
            np.diff(outputs.reshape(-1, 2), axis=1)[:, 0]
            / np.diff(unit_x.reshape(-1, 2), axis=1)[:, 0]
        )
        expected_point = float(np.mean(np.abs(independent_effects)))

        assert result.mu_star["x"] == pytest.approx(expected_point)
        assert result.uncertainty is not None
        live_item = next(
            item
            for item in result.uncertainty.sensitivity_results
            if item.parameter == "x" and item.index == "mu_star"
        )
        assert live_item.ci is not None
        assert live_item.ci.raw_low < live_item.estimate < live_item.ci.raw_high
        np.testing.assert_allclose(live_item.estimate, expected_point, rtol=1e-11, atol=1e-11)

        effects = morris_elementary_effects_from_samples(
            samples,
            outputs,
            ["x"],
            parameter_bounds={"x": (lower, upper)},
            num_levels=4,
        )
        payload = morris_storage_from_elementary_effects(
            effects,
            ["x"],
            num_levels=4,
            delta=2.0 / 3.0,
            trajectory_ids=[f"t{index + 1}" for index in range(effects.shape[0])],
            scaled=False,
        )
        retained = MorrisStoragePayload.model_validate_json(payload.model_dump_json())
        restored = morris_elementary_effects_from_storage(retained)
        np.testing.assert_array_equal(restored, effects)
        retained_bundle = analyze_morris_trajectory_bootstrap(restored, ["x"], config)
        retained_item = next(
            item
            for item in retained_bundle.sensitivity_results
            if item.parameter == "x" and item.index == "mu_star"
        )
        assert retained_item.ci is not None
        np.testing.assert_allclose(retained_item.estimate, live_item.estimate, rtol=0, atol=0)
        np.testing.assert_allclose(
            [retained_item.ci.raw_low, retained_item.ci.raw_high],
            [live_item.ci.raw_low, live_item.ci.raw_high],
            rtol=0,
            atol=0,
        )
        observed.append(
            (
                expected_point,
                (live_item.ci.raw_low, live_item.ci.raw_high),
                retained_item.estimate,
                (retained_item.ci.raw_low, retained_item.ci.raw_high),
            )
        )

    base_point, base_ci, _, _ = observed[0]
    for point, ci, retained_point, retained_ci in (observed[1], observed[2]):
        assert point == pytest.approx(base_point)
        assert ci == pytest.approx(base_ci)
        assert retained_point == pytest.approx(base_point)
        assert retained_ci == pytest.approx(base_ci)
    scaled_point, scaled_ci, retained_scaled_point, retained_scaled_ci = observed[3]
    assert scaled_point == pytest.approx(1000.0 * base_point)
    assert scaled_ci == pytest.approx(tuple(1000.0 * value for value in base_ci))
    assert retained_scaled_point == pytest.approx(1000.0 * base_point)
    assert retained_scaled_ci == pytest.approx(tuple(1000.0 * value for value in base_ci))
