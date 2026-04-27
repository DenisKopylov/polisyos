from __future__ import annotations

import numpy as np

from polisyos.scientist.doe.sensitivity_benchmark import (
    CoverageScenarioResult,
    build_coverage_profile,
    default_morris_benchmark_cases,
    default_sensitivity_truth_suite,
    default_sobol_benchmark_cases,
    ishigami_truth,
    morris_linear_truth,
    morris_nonmonotonic_truth,
    run_morris_effect_coverage_benchmark,
    run_sobol_linear_coverage_benchmark,
    sobol_g_function_truth,
    sobol_heavy_tailed_additive_truth,
    sobol_linear_truth,
    sobol_sparse_interaction_truth,
)
from polisyos.scientist.doe.uncertainty import SensitivityUncertaintyConfig


def test_analytic_truth_suites_cover_sobol_and_morris_cases() -> None:
    linear = sobol_linear_truth({"x1": 2.0, "x2": 1.0})
    assert linear.indices["S1"]["x1"] > linear.indices["S1"]["x2"]
    assert linear.indices["S1"] == linear.indices["ST"]

    ishigami = ishigami_truth()
    assert ishigami.indices["ST"]["x3"] > ishigami.indices["S1"]["x3"]

    g_truth = sobol_g_function_truth({"x1": 0.0, "x2": 9.0})
    assert g_truth.indices["ST"]["x1"] > g_truth.indices["ST"]["x2"]

    sparse = sobol_sparse_interaction_truth({"x1": 2.0, "x2": 0.0}, {"x1:x2": 1.0})
    assert sparse.indices["ST"]["x2"] > sparse.indices["S1"]["x2"]

    morris = morris_linear_truth({"x1": -2.0, "x2": 0.5})
    assert morris.indices["mu"]["x1"] == -2.0
    assert morris.indices["mu_star"]["x1"] == 2.0
    assert morris.indices["sigma"]["x2"] == 0.0

    nonmonotonic = morris_nonmonotonic_truth({"x1": 1.0})
    assert nonmonotonic.indices["mu"]["x1"] == 0.0
    assert nonmonotonic.indices["mu_star"]["x1"] > 0.0

    heavy = sobol_heavy_tailed_additive_truth({"x1": 2.0, "x2": 1.0})
    assert heavy.indices["ST"]["x1"] > heavy.indices["ST"]["x2"]

    assert len(default_sensitivity_truth_suite()) >= 10


def test_default_executable_benchmark_cases_cover_requested_classes() -> None:
    sobol_cases = default_sobol_benchmark_cases(reference_sample_size=256, seed=21)
    morris_cases = default_morris_benchmark_cases()

    assert {case.benchmark_id for case in sobol_cases} >= {
        "sobol_linear",
        "sobol_ishigami",
        "sobol_g_function",
        "sobol_sparse_high_d_interactions",
        "sobol_discontinuous_threshold",
        "sobol_heavy_tailed_additive",
    }
    assert {case.benchmark_id for case in morris_cases} >= {
        "morris_linear",
        "morris_quadratic_derivative_reference",
        "morris_pairwise_interaction",
        "morris_nonmonotonic_cancellation",
        "morris_sparse_screening",
        "morris_grouped_factors",
    }


def test_sobol_linear_coverage_benchmark_smoke() -> None:
    result = run_sobol_linear_coverage_benchmark(
        {"x1": 2.0, "x2": 1.0},
        sample_size=24,
        repetitions=3,
        seed=19,
    )

    assert isinstance(result, CoverageScenarioResult)
    assert result.n_repetitions == 3
    assert result.dimension == 2
    assert result.sample_size == 24
    assert 0.0 <= result.marginal_coverage <= 1.0


def test_morris_effect_coverage_benchmark_smoke() -> None:
    truth = morris_linear_truth({"x1": 2.0, "x2": 1.0})

    def sampler(_rng: np.random.Generator, trajectories: int) -> np.ndarray:
        return np.tile(np.array([[2.0, 1.0]], dtype=float), (trajectories, 1))

    result = run_morris_effect_coverage_benchmark(
        sampler,
        truth,
        trajectories=4,
        repetitions=2,
        uncertainty_config=SensitivityUncertaintyConfig(
            enabled=True,
            method="percentile",
            n_resamples=20,
            random_seed=12,
        ),
    )

    assert result.n_repetitions == 2
    assert result.sampler == "random_morris"
    assert result.dimension == 2


def test_build_coverage_profile_records_approval_summary() -> None:
    scenario = CoverageScenarioResult(
        scenario_id="demo",
        method="paired_bca_bootstrap",
        index_types=["S1", "ST"],
        sampler="iid_mc",
        dimension=2,
        sample_size=128,
        n_repetitions=2000,
        nominal_level=0.95,
        marginal_coverage=0.95,
        simultaneous_coverage=0.94,
        mean_interval_width=0.2,
        median_interval_width=0.18,
        interval_score=0.22,
        miss_below_rate=0.5,
        miss_above_rate=0.5,
        boundary_failure_rate=0.0,
        pairwise_calibration={"0.9-1.0": 0.95},
        approved=True,
    )

    profile = build_coverage_profile(
        coverage_profile_id="sobol_iid_saltelli_paired_bca_v1",
        method="paired_bca_bootstrap",
        index_types=["S1", "ST"],
        samplers=["iid_mc"],
        benchmark_commit="abc123",
        scenario_results=[scenario],
    )

    assert profile.approved
    assert profile.coverage_summary.min_95_coverage == 0.95
    assert profile.benchmark_commit == "abc123"
