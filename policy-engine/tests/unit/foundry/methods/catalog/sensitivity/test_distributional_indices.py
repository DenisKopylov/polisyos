from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.sensitivity import (
    analyze_distribution,
    analyze_quantile,
    sample_size_delta_tv,
    sample_size_qosa_cvm,
)


def _estimate_by_group(
    result: dict, *, alpha: float | None = None, method: str | None = None
) -> dict[str, float]:
    if "targets" in result:
        target = next(item for item in result["targets"] if item["alpha"] == alpha)
        return {".".join(est["group"]): float(est["raw_estimate"]) for est in target["estimates"]}
    entry = next(item for item in result["results"] if item["method"] == method)
    return {".".join(est["group"]): float(est["raw_estimate"]) for est in entry["estimates"]}


def test_qosa_pinball_detects_quantile_driver() -> None:
    rng = np.random.default_rng(42)
    n = 360
    x1 = rng.uniform(-1.0, 1.0, size=n)
    x2 = rng.normal(size=n)
    y = 2.5 * x1 + 0.2 * rng.normal(size=n)
    X = np.column_stack([x1, x2])
    problem = {"names": ["policy_rate", "noise"]}

    result = analyze_quantile(
        problem=problem,
        X=X,
        Y=y,
        alphas=(0.5, 0.95),
        groups="first_order",
        cv=4,
        n_bins=8,
        min_leaf=8,
        random_seed=7,
    )

    median = _estimate_by_group(result, alpha=0.5)
    upper_tail = _estimate_by_group(result, alpha=0.95)
    assert median["policy_rate"] > median["noise"] + 0.08
    assert upper_tail["policy_rate"] > upper_tail["noise"]
    assert result["results"][0]["method"] == "qosa_pinball"
    assert result["results"][0]["target"]["loss"] == "pinball"
    first_estimate = result["targets"][0]["estimates"][0]
    assert first_estimate["diagnostics"]["denominator"] > 0.0
    assert "quantile_coverage" in first_estimate["diagnostics"]
    assert first_estimate["estimate"] == np.clip(first_estimate["raw_estimate"], 0.0, 1.0)


def test_distributional_indices_detect_cdf_driver() -> None:
    rng = np.random.default_rng(123)
    n = 420
    x1 = rng.uniform(-1.0, 1.0, size=n)
    x2 = rng.normal(size=n)
    y = x1 + 0.15 * rng.normal(size=n)
    X = np.column_stack([x1, x2])
    problem = {"names": ["income_shift", "placebo"]}

    result = analyze_distribution(
        problem=problem,
        X=X,
        Y=y,
        metrics=("cvm", "tail_cvm", "pawn", "delta_tv"),
        groups="first_order",
        grid_size=96,
        cv=4,
        n_bins=8,
        min_leaf=8,
        random_seed=11,
        classifier_iterations=80,
    )

    cvm = _estimate_by_group(result, method="cvm_orthogonal")
    pawn = _estimate_by_group(result, method="pawn_ks")
    assert cvm["income_shift"] > cvm["placebo"] + 0.03
    assert pawn["income_shift"] > pawn["placebo"]
    cvm_entry = next(item for item in result["results"] if item["method"] == "cvm_orthogonal")
    diagnostics = cvm_entry["estimates"][0]["diagnostics"]
    assert diagnostics["denominator"] > 0.0
    assert diagnostics["monotonicity_enforced"] is True
    assert "null_dummy_index" in diagnostics
    assert "tail_exceedances" in diagnostics


def test_delta_tv_density_estimator_runs_and_reports_density_diagnostics() -> None:
    rng = np.random.default_rng(321)
    n = 180
    x1 = rng.uniform(-1.0, 1.0, size=n)
    x2 = rng.normal(size=n)
    y = x1 + 0.2 * rng.normal(size=n)
    X = np.column_stack([x1, x2])

    result = analyze_distribution(
        problem={"names": ["driver", "placebo"]},
        X=X,
        Y=y,
        metrics=("delta_tv",),
        tv_method="density",
        groups="first_order",
        grid_size=64,
        cv=3,
        n_bins=6,
        min_leaf=6,
        random_seed=13,
    )

    entry = result["results"][0]
    assert entry["method"] == "delta_tv_density"
    estimates = _estimate_by_group(result, method="delta_tv_density")
    assert estimates["driver"] > estimates["placebo"]
    diagnostics = entry["estimates"][0]["diagnostics"]
    assert diagnostics["tv_method"] == "density"
    assert diagnostics["unconditional_density_mass"] > 0.8
    assert "null_dummy_index" in diagnostics


def test_optional_forest_learners_are_used_when_available() -> None:
    pytest.importorskip("sklearn")
    rng = np.random.default_rng(17)
    n = 100
    X = rng.normal(size=(n, 2))
    Y = X[:, 0] + rng.normal(scale=0.3, size=n)

    qosa = analyze_quantile(
        problem={"names": ["x1", "x2"]},
        X=X,
        Y=Y,
        alphas=(0.5,),
        learner="quantile_forest",
        cv=2,
        min_leaf=4,
        random_seed=19,
    )
    dist = analyze_distribution(
        problem={"names": ["x1", "x2"]},
        X=X,
        Y=Y,
        metrics=("cvm",),
        cdf_learner="cdf_forest",
        grid_size=32,
        cv=2,
        min_leaf=4,
        random_seed=19,
    )

    assert qosa["targets"][0]["estimates"][0]["diagnostics"]["learner"] == "quantile_forest"
    assert dist["results"][0]["estimates"][0]["diagnostics"]["learner"] == "cdf_forest"


def test_distributional_bootstrap_attaches_intervals() -> None:
    rng = np.random.default_rng(5)
    n = 120
    X = rng.normal(size=(n, 2))
    Y = X[:, 0] + rng.normal(scale=0.5, size=n)

    result = analyze_distribution(
        problem={"names": ["x1", "x2"]},
        X=X,
        Y=Y,
        metrics=("cvm",),
        groups="first_order",
        grid_size=32,
        cv=3,
        n_boot=4,
        n_bins=5,
        min_leaf=5,
        random_seed=9,
    )

    estimate = result["results"][0]["estimates"][0]
    assert estimate["stderr"] is not None
    assert estimate["ci_low"] is not None
    assert estimate["ci_high"] is not None


def test_sample_size_planners_are_monotone() -> None:
    small_error = sample_size_qosa_cvm(0.025, 0.05, 3, 2)
    large_error = sample_size_qosa_cvm(0.05, 0.05, 3, 2)
    delta_plan = sample_size_delta_tv(0.05, 0.05, 3, 2)
    assert small_error > large_error
    assert delta_plan > large_error


def test_foundry_methods_registered_and_run(isolated_registry) -> None:
    rng = np.random.default_rng(99)
    X = rng.normal(size=(180, 2))
    Y = X[:, 0] + 0.1 * rng.normal(size=180)
    state = {"inputs_matrix": X, "outputs": Y, "problem": {"names": ["driver", "noise"]}}

    qosa = isolated_registry.get("sensitivity.distributional.qosa_pinball@1.0.0")
    dist = isolated_registry.get("sensitivity.distributional.distributional_indices@1.0.0")

    q_result = qosa.pure_step(state, {"alphas": (0.5,), "cv": 3, "n_bins": 6, "min_leaf": 6})
    d_result = dist.pure_step(
        state,
        {
            "metrics": ("cvm", "pawn"),
            "grid_size": 48,
            "cv": 3,
            "n_bins": 6,
            "min_leaf": 6,
        },
    )

    assert q_result["result"]["method"] == "qosa_pinball"
    assert d_result["result"]["method"] == "quantile_distributional_sensitivity"
