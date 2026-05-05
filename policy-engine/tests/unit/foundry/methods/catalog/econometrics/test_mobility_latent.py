from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.catalog.distributional.mobility_latent_adapter import (
    LatentMobilityReportAdapter,
)
from polisyos.foundry.methods.catalog.econometrics.mobility_latent import (
    LatentMobilityEstimator,
)
from polisyos.ir.analytics.mobility import MobilityReport


def _simulate_latent_panel(
    *,
    seed: int,
    n_entities: int = 60,
    n_periods: int = 8,
    means: tuple[float, ...] = (-0.8, 0.8),
    rhos: tuple[float, ...] = (0.25, 0.55),
    sigma_eta: float = 0.12,
    sigma_e: float = 0.04,
) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    k = len(means)
    true_type = np.arange(n_entities) % k
    y = np.zeros((n_entities, n_periods), dtype=float)
    state = np.zeros_like(y)
    for entity in range(n_entities):
        cls = int(true_type[entity])
        state[entity, 0] = rng.normal(scale=sigma_eta)
        for time_idx in range(1, n_periods):
            state[entity, time_idx] = rhos[cls] * state[entity, time_idx - 1] + rng.normal(
                scale=sigma_eta
            )
        y[entity] = means[cls] + state[entity] + rng.normal(scale=sigma_e, size=n_periods)

    return {
        "dependent": y.reshape(-1),
        "exog": np.zeros((n_entities * n_periods, 1), dtype=float),
        "entity_ids": np.repeat(np.arange(n_entities), n_periods),
        "time_ids": np.tile(np.arange(n_periods), n_entities),
        "feature_names": ["zero"],
        "true_type": true_type,
    }


def _fit_fast(state: dict[str, object], **overrides: object) -> dict[str, object]:
    params: dict[str, object] = {
        "n_types": 2,
        "profile_order": 0,
        "n_starts": 1,
        "max_iter": 45,
        "tol": 1e-5,
        "horizons": (1, 5),
        "n_income_classes": 4,
        "random_seed": 13,
    }
    params.update(overrides)
    return LatentMobilityEstimator.pure_step(state, params)


def test_recovers_two_types_basic_dgp() -> None:
    state = _simulate_latent_panel(seed=4)
    result = _fit_fast(state, n_starts=2, max_iter=60)["result"]

    assert result.params["class_0_beta_intercept"] == pytest.approx(-0.8, abs=0.25)
    assert result.params["class_1_beta_intercept"] == pytest.approx(0.8, abs=0.25)
    assert result.diagnostics["selected_k"] == 2
    assert result.diagnostics["rho"][0] < result.diagnostics["rho"][1]


def test_pooled_ar_overstates_persistence_when_types_ignored() -> None:
    state = _simulate_latent_panel(
        seed=7,
        n_entities=70,
        means=(-1.2, 1.2),
        rhos=(0.2, 0.2),
        sigma_eta=0.07,
        sigma_e=0.03,
    )
    result = _fit_fast(state, max_iter=50)["result"]

    assert result.diagnostics["pooled_ar1"] > 0.85
    assert max(result.diagnostics["rho"]) < 0.55


def test_transition_rows_sum_to_one() -> None:
    state = _simulate_latent_panel(seed=8, n_entities=48)
    output = _fit_fast(state, n_income_classes=5)

    transition_tensor = np.asarray(output["transition_tensor"], dtype=float)
    np.testing.assert_allclose(transition_tensor.sum(axis=2), 1.0, atol=1e-8)
    assert transition_tensor.shape == (2, 5, 5)


def test_observed_classes_and_edges_drive_transition_contract() -> None:
    state = _simulate_latent_panel(seed=12, n_entities=40)
    dependent = np.asarray(state["dependent"], dtype=float)
    edges = np.asarray([-2.5, -0.25, 0.25, 2.5], dtype=float)
    state["class_edges"] = edges
    state["observed_classes"] = np.digitize(dependent, edges[1:-1], right=False)

    output = _fit_fast(state, n_income_classes=9, max_iter=35)

    transition_tensor = np.asarray(output["transition_tensor"], dtype=float)
    assert transition_tensor.shape == (2, 3, 3)
    report = output["mobility_report"]
    assert report.population.class_definition["type"] == "observed_classes"
    np.testing.assert_allclose(transition_tensor.sum(axis=2), 1.0, atol=1e-8)


def test_sample_weights_shift_reported_class_shares() -> None:
    state = _simulate_latent_panel(seed=13, n_entities=48)
    true_type = np.asarray(state["true_type"], dtype=int)
    state["sample_weights"] = np.repeat(np.where(true_type == 1, 5.0, 1.0), 8)

    result = _fit_fast(state, max_iter=45)["result"]

    assert result.params["class_1_share"] > 0.65
    assert result.diagnostics["class_share"][1] > 0.65


def test_label_ordering_is_deterministic() -> None:
    state = _simulate_latent_panel(seed=9, n_entities=42)
    first = _fit_fast(state, max_iter=35, random_seed=99)["result"]
    second = _fit_fast(state, max_iter=35, random_seed=99)["result"]

    first_means = [
        first.params["class_0_beta_intercept"],
        first.params["class_1_beta_intercept"],
    ]
    second_means = [
        second.params["class_0_beta_intercept"],
        second.params["class_1_beta_intercept"],
    ]
    assert first_means == pytest.approx(second_means, abs=1e-12)
    assert first_means == sorted(first_means)


def test_measurement_error_floor_prevents_variance_collapse() -> None:
    n_entities = 12
    n_periods = 6
    state = {
        "dependent": np.zeros(n_entities * n_periods, dtype=float),
        "exog": np.zeros((n_entities * n_periods, 1), dtype=float),
        "entity_ids": np.repeat(np.arange(n_entities), n_periods),
        "time_ids": np.tile(np.arange(n_periods), n_entities),
        "feature_names": ["zero"],
    }

    result = LatentMobilityEstimator.pure_step(
        state,
        {
            "n_types": 1,
            "profile_order": 0,
            "max_iter": 8,
            "n_starts": 1,
            "var_floor": 1e-4,
            "horizons": (1,),
            "n_income_classes": 2,
        },
    )["result"]

    assert result.params["class_0_sigma_eta"] >= 0.01
    assert result.params["class_0_sigma_e"] >= 0.01
    assert result.diagnostics["var_floor_hits"] > 0


def test_fixed_grid_measurement_error_records_selected_grid_value() -> None:
    state = _simulate_latent_panel(seed=21, n_entities=40)
    result = _fit_fast(
        state,
        measurement_error="fixed_grid",
        measurement_error_variance_grid=(0.0004, 0.0025, 0.01),
        max_iter=30,
    )["result"]

    assert any(
        result.diagnostics["measurement_error_variance"] == pytest.approx(item)
        for item in (0.0004, 0.0025, 0.01)
    )
    assert result.diagnostics["measurement_error_grid"] == pytest.approx([0.0004, 0.0025, 0.01])


def test_robustness_and_bootstrap_diagnostics_are_reported() -> None:
    state = _simulate_latent_panel(seed=22, n_entities=36)
    result = _fit_fast(state, max_iter=30, bootstrap_reps=5)["result"]

    robustness = result.diagnostics["robustness"]
    assert robustness["family"] == "classify_then_grouped_entity_demeaned_ar1"
    assert len(robustness["class_counts"]) == 2
    assert robustness["posterior_bootstrap"]["reps"] == 5


def test_adapter_emits_mobility_report_contract() -> None:
    state = _simulate_latent_panel(seed=11, n_entities=36)
    latent = _fit_fast(state, max_iter=35)

    adapted = LatentMobilityReportAdapter.pure_step(
        {
            "transition_tensor": latent["transition_tensor"],
            "row_marginals": latent["row_marginals"],
            "horizons": latent["horizons"],
            "diagnostics": latent["result"].diagnostics,
            "params": latent["result"].metadata,
            "n_entities": latent["result"].n_entities,
            "n_periods": latent["result"].n_periods,
        },
        {"horizon": 5},
    )["result"]

    assert isinstance(adapted, MobilityReport)
    assert adapted.analysis_type == "latent_mobility_transition_matrix"
    assert adapted.summary_metrics["horizon"] == 5
    np.testing.assert_allclose(
        np.asarray(adapted.point_estimate.transition_matrix).sum(axis=1),
        1.0,
        atol=1e-8,
    )


def test_benchmark_metrics_monotone_in_sample_size() -> None:
    from benchmarks.distributional.phase2_mobility_latent_frontier import (
        run_latent_mobility_benchmark,
    )

    small = run_latent_mobility_benchmark(n_entities=32, seed=31)["metrics"]
    large = run_latent_mobility_benchmark(n_entities=64, seed=31)["metrics"]

    assert small["mobility_report_ok"] == 1.0
    assert large["mobility_report_ok"] == 1.0
    assert small["selected_k"] == 2.0
    assert large["selected_k"] == 2.0
    assert large["transition_row_sum_error"] <= small["transition_row_sum_error"] + 1e-12
