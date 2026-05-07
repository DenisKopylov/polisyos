from __future__ import annotations

import numpy as np
from polisyos.scientist.methods.doe.uncertainty import (
    SensitivityUncertaintyConfig,
    SobolRowBlockData,
    analyze_hierarchical_replicate_bootstrap,
    analyze_morris_trajectory_bootstrap,
    analyze_rqmc_replicate_ci,
    analyze_single_qmc_warning,
    analyze_sobol_asymptotic_delta,
    analyze_sobol_paired_bootstrap,
    analyze_surrogate_sobol_bootstrap,
    apply_calibrated_multiplier,
    morris_analytic_intervals,
    morris_elementary_effects_from_storage,
    morris_storage_from_elementary_effects,
    resolve_sensitivity_uncertainty_method,
    sobol_blocks_from_salib_outputs,
    sobol_blocks_from_storage,
    sobol_storage_from_blocks,
)


def test_sobol_salib_output_parser_preserves_row_blocks() -> None:
    outputs = np.arange(18, dtype=float)

    blocks = sobol_blocks_from_salib_outputs(outputs, ["x1", "x2"], calc_second_order=True)

    np.testing.assert_array_equal(blocks.y_a, np.array([0.0, 6.0, 12.0]))
    np.testing.assert_array_equal(blocks.y_b, np.array([5.0, 11.0, 17.0]))
    np.testing.assert_array_equal(blocks.y_ab[:, 0], np.array([1.0, 7.0, 13.0]))
    np.testing.assert_array_equal(blocks.y_ab[:, 1], np.array([2.0, 8.0, 14.0]))
    assert blocks.y_ba is not None
    np.testing.assert_array_equal(blocks.y_ba[:, 0], np.array([3.0, 9.0, 15.0]))
    np.testing.assert_array_equal(blocks.y_ba[:, 1], np.array([4.0, 10.0, 16.0]))


def test_sobol_paired_bootstrap_returns_catalog_uncertainty() -> None:
    rng = np.random.default_rng(42)
    n_rows = 48
    y_a = rng.normal(0.0, 1.0, size=n_rows)
    y_b = rng.normal(0.0, 1.0, size=n_rows)
    y_ab = np.column_stack(
        [
            y_a + rng.normal(0.0, 0.05, size=n_rows),
            rng.normal(0.0, 1.0, size=n_rows),
        ]
    )
    blocks = SobolRowBlockData(
        y_a=y_a,
        y_b=y_b,
        y_ab=y_ab,
        parameter_names=("x1", "x2"),
    )
    config = SensitivityUncertaintyConfig(
        enabled=True,
        method="percentile",
        n_resamples=80,
        random_seed=7,
    )

    bundle = analyze_sobol_paired_bootstrap(blocks, config)

    st_x1 = next(
        item for item in bundle.sensitivity_results if item.parameter == "x1" and item.index == "ST"
    )
    assert st_x1.ci is not None
    assert st_x1.ci.method == "paired_percentile_bootstrap"
    assert st_x1.simultaneous_ci is not None
    assert bundle.joint_uncertainty.covariance_matrix is not None
    assert set(bundle.joint_uncertainty.rank_probabilities) == {"x1", "x2"}
    assert sum(bundle.joint_uncertainty.rank_probabilities["x1"].values()) == 1.0
    assert "x1>x2" in bundle.joint_uncertainty.pairwise_dominance


def test_studentized_bootstrap_variant_is_available() -> None:
    rng = np.random.default_rng(99)
    blocks = SobolRowBlockData(
        y_a=rng.normal(size=16),
        y_b=rng.normal(size=16),
        y_ab=rng.normal(size=(16, 2)),
        parameter_names=("x1", "x2"),
    )
    config = SensitivityUncertaintyConfig(
        enabled=True,
        method="studentized",
        n_resamples=20,
        studentized_inner_resamples=10,
        random_seed=13,
    )

    bundle = analyze_sobol_paired_bootstrap(blocks, config)

    assert bundle.sensitivity_results[0].ci is not None
    assert bundle.sensitivity_results[0].ci.method == "paired_studentized_bootstrap"


def test_morris_trajectory_bootstrap_reports_rank_uncertainty_and_low_r_warning() -> None:
    elementary_effects = np.array(
        [
            [2.0, 0.10],
            [2.1, 0.20],
            [1.9, 0.10],
            [2.2, 0.15],
            [1.8, 0.05],
        ],
        dtype=float,
    )
    config = SensitivityUncertaintyConfig(
        enabled=True,
        method="normal",
        n_resamples=80,
        random_seed=11,
    )

    bundle = analyze_morris_trajectory_bootstrap(elementary_effects, ["x1", "x2"], config)

    mu_star_x1 = next(
        item
        for item in bundle.sensitivity_results
        if item.parameter == "x1" and item.index == "mu_star"
    )
    assert mu_star_x1.ci is not None
    assert mu_star_x1.ci.low >= 0.0
    assert mu_star_x1.diagnostics.ci_status == "screening_precision_low"
    assert bundle.joint_uncertainty.pairwise_dominance["x1>x2"] > 0.95
    assert "screening_precision_low" in bundle.method_metadata.warnings


def test_rqmc_replicate_ci_uses_replicate_level_uncertainty() -> None:
    replicate_estimates = np.array(
        [
            [0.31, 0.20],
            [0.29, 0.21],
            [0.34, 0.18],
            [0.30, 0.22],
        ],
        dtype=float,
    )
    config = SensitivityUncertaintyConfig(
        enabled=True,
        n_resamples=50,
        random_seed=5,
    )

    bundle = analyze_rqmc_replicate_ci(replicate_estimates, ["x1", "x2"], config=config)

    st_x1 = next(item for item in bundle.sensitivity_results if item.parameter == "x1")
    assert st_x1.ci is not None
    assert st_x1.ci.method == "replicate_t_interval"
    assert st_x1.simultaneous_ci is not None
    assert st_x1.simultaneous_ci.method == "replicate_t_interval_max_t"
    assert st_x1.diagnostics.ci_status == "not_calibrated_few_qmc_replicates"
    assert bundle.joint_uncertainty.rank_probabilities["x1"]["1"] >= 0.9


def test_morris_analytic_intervals_use_log_scale_sigma_bootstrap() -> None:
    intervals = morris_analytic_intervals(
        np.array([[1.0, 0.5], [1.2, 0.4], [0.8, 0.6], [1.1, 0.55]]),
        ["x1", "x2"],
        n_resamples=50,
        random_seed=3,
    )

    sigma_x1 = intervals["x1:sigma"]
    assert sigma_x1.method == "morris_log_sigma_bootstrap"
    assert sigma_x1.n_resamples == 50
    assert sigma_x1.low >= 0.0


def test_sobol_asymptotic_delta_returns_covariance_and_intervals() -> None:
    rng = np.random.default_rng(123)
    n_rows = 40
    y_a = rng.normal(size=n_rows)
    y_b = rng.normal(size=n_rows)
    y_ab = np.column_stack(
        [0.8 * y_a + rng.normal(scale=0.1, size=n_rows), rng.normal(size=n_rows)]
    )
    blocks = SobolRowBlockData(
        y_a=y_a,
        y_b=y_b,
        y_ab=y_ab,
        parameter_names=("x1", "x2"),
    )
    config = SensitivityUncertaintyConfig(enabled=True, n_resamples=40, random_seed=22)

    bundle = analyze_sobol_asymptotic_delta(blocks, config)

    st_x1 = next(
        item for item in bundle.sensitivity_results if item.parameter == "x1" and item.index == "ST"
    )
    assert st_x1.ci is not None
    assert st_x1.ci.method == "asymptotic_delta"
    assert bundle.joint_uncertainty.covariance_matrix is not None


def test_storage_payloads_round_trip_row_level_data() -> None:
    blocks = SobolRowBlockData(
        y_a=np.array([1.0, 2.0, 3.0]),
        y_b=np.array([1.5, 2.5, 3.5]),
        y_ab=np.array([[1.1, 1.4], [2.1, 2.4], [3.1, 3.4]]),
        parameter_names=("x1", "x2"),
    )

    payload = sobol_storage_from_blocks(blocks, rng_seed=9, row_block_id="rb1")
    restored = sobol_blocks_from_storage(payload)

    assert payload.n == 3
    assert payload.d == 2
    assert payload.rng_seed == 9
    np.testing.assert_allclose(restored.y_ab, blocks.y_ab)

    morris_payload = morris_storage_from_elementary_effects(
        np.array([[1.0, 0.5], [1.1, 0.4]]),
        ["x1", "x2"],
        num_levels=4,
        delta=2.0 / 3.0,
    )
    restored_ee = morris_elementary_effects_from_storage(morris_payload)
    np.testing.assert_allclose(restored_ee, np.array([[1.0, 0.5], [1.1, 0.4]]))


def test_single_qmc_warning_marks_ci_unavailable() -> None:
    bundle = analyze_single_qmc_warning({"x1": 0.3, "x2": 0.2}, ["x1", "x2"])

    assert bundle.sensitivity_results[0].ci is None
    assert bundle.sensitivity_results[0].diagnostics.ci_status == "not_calibrated_single_qmc"
    assert "not_calibrated_single_qmc" in bundle.method_metadata.warnings


def test_hierarchical_replicate_bootstrap_includes_simulator_noise_scope() -> None:
    replicate_estimates = np.array(
        [
            [[0.30, 0.20], [0.32, 0.21]],
            [[0.28, 0.22], [0.29, 0.23]],
            [[0.35, 0.18], [0.34, 0.19]],
        ],
        dtype=float,
    )
    config = SensitivityUncertaintyConfig(
        enabled=True,
        n_resamples=40,
        random_seed=8,
        uncertainty_scope="sampling_plus_simulator_noise",
    )

    bundle = analyze_hierarchical_replicate_bootstrap(
        replicate_estimates,
        ["x1", "x2"],
        config=config,
    )

    assert bundle.sensitivity_results[0].ci is not None
    assert (
        bundle.sensitivity_results[0].diagnostics.uncertainty_scope
        == "sampling_plus_simulator_noise"
    )
    assert bundle.method_metadata.metadata["simulator_replicates"] == 2
    assert bundle.joint_uncertainty.pairwise_dominance["x1>x2"] >= 0.9


def test_method_resolution_and_calibrated_multiplier() -> None:
    resolved = resolve_sensitivity_uncertainty_method(
        "sobol",
        sampler="rqmc",
        rqmc_replicates=1,
    )
    assert resolved.method == "none"
    assert resolved.ci_status == "not_calibrated_single_qmc"

    blocks = SobolRowBlockData(
        y_a=np.array([1.0, 2.0, 3.0, 4.0]),
        y_b=np.array([1.2, 2.2, 3.2, 4.2]),
        y_ab=np.array([[1.1, 1.3], [2.1, 2.3], [3.1, 3.3], [4.1, 4.3]]),
        parameter_names=("x1", "x2"),
    )
    config = SensitivityUncertaintyConfig(
        enabled=True, method="normal", n_resamples=40, random_seed=4
    )
    bundle = analyze_sobol_paired_bootstrap(blocks, config)
    original = next(item for item in bundle.sensitivity_results if item.ci is not None)
    calibrated = apply_calibrated_multiplier(bundle, 1.5)
    widened = next(
        item for item in calibrated.sensitivity_results if item.parameter == original.parameter
    )

    assert widened.ci is not None
    assert original.ci is not None
    assert widened.ci.raw_high - widened.ci.raw_low >= original.ci.raw_high - original.ci.raw_low
    assert calibrated.method_metadata.metadata["calibrated_multiplier"] == 1.5


def test_surrogate_sobol_bootstrap_uses_fit_callbacks() -> None:
    rng = np.random.default_rng(33)
    x = rng.random((20, 2))
    y = 2.0 * x[:, 0] + 0.2 * x[:, 1]

    def fit_surrogate(train_x: np.ndarray, train_y: np.ndarray) -> np.ndarray:
        design = np.column_stack([np.ones(train_x.shape[0]), train_x])
        beta, *_ = np.linalg.lstsq(design, train_y, rcond=None)
        return beta

    def compute_indices(beta: np.ndarray) -> dict[str, dict[str, float]]:
        weights = beta[1:] ** 2
        total = float(np.sum(weights))
        return {
            "S1": {"x1": float(weights[0] / total), "x2": float(weights[1] / total)},
            "ST": {"x1": float(weights[0] / total), "x2": float(weights[1] / total)},
        }

    config = SensitivityUncertaintyConfig(
        enabled=True,
        n_resamples=40,
        random_seed=44,
        uncertainty_scope="sampling_plus_surrogate",
    )
    bundle = analyze_surrogate_sobol_bootstrap(
        x,
        y,
        ["x1", "x2"],
        fit_surrogate=fit_surrogate,
        compute_indices=compute_indices,
        config=config,
        surrogate_family="linear_test",
        validation_error=0.0,
        mc_inner_n=100,
    )

    assert bundle.sensitivity_results[0].ci is not None
    assert bundle.method_metadata.metadata["surrogate_family"] == "linear_test"
    assert bundle.sensitivity_results[0].diagnostics.uncertainty_scope == "sampling_plus_surrogate"
