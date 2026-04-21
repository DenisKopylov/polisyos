from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.dependence_structure import load_dependence_structure


def _simulate_dynamic_panel(
    *,
    seed: int,
    n_entities: int,
    n_periods: int,
    rho: float,
    beta: float,
    error_scale: float = 1.0,
    cluster_ids: np.ndarray | None = None,
    cluster_scale: float = 0.0,
    factor_loadings: np.ndarray | None = None,
    factor_scale: float = 0.0,
) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n_entities, n_periods, 1))
    effects = rng.normal(size=n_entities)
    errors = error_scale * rng.normal(size=(n_entities, n_periods))

    if cluster_ids is not None and cluster_scale > 0.0:
        cluster_ids = np.asarray(cluster_ids)
        cluster_count = int(np.unique(cluster_ids).size)
        cluster_shocks = rng.normal(scale=cluster_scale, size=(cluster_count, n_periods))
        errors = errors + cluster_shocks[cluster_ids]

    if factor_loadings is not None and factor_scale > 0.0:
        factor = rng.normal(scale=factor_scale, size=n_periods)
        errors = errors + np.asarray(factor_loadings)[:, np.newaxis] * factor[np.newaxis, :]

    y = np.zeros((n_entities, n_periods), dtype=float)
    y[:, 0] = effects / max(1.0 - rho, 0.2) + beta * x[:, 0, 0] + errors[:, 0]
    for time_idx in range(1, n_periods):
        y[:, time_idx] = (
            rho * y[:, time_idx - 1]
            + beta * x[:, time_idx, 0]
            + effects
            + errors[:, time_idx]
        )

    state: dict[str, object] = {
        "dependent": y.reshape(-1),
        "exog": x.reshape(n_entities * n_periods, 1),
        "entity_ids": np.repeat(np.arange(n_entities), n_periods),
        "time_ids": np.tile(np.arange(n_periods), n_entities),
        "feature_names": ["policy_x"],
    }
    if cluster_ids is not None:
        state["metadata"] = {"dependence_metadata": {"cluster_ids": cluster_ids}}
    return state


@pytest.mark.parametrize(
    ("fqn", "rho_tolerance", "beta_tolerance"),
    [
        ("econometrics.panel.difference_gmm@1.0.0", 0.18, 0.22),
        ("econometrics.panel.system_gmm@1.0.0", 0.14, 0.20),
    ],
)
def test_dynamic_panel_gmm_recovers_core_parameters(
    isolated_registry,
    fqn: str,
    rho_tolerance: float,
    beta_tolerance: float,
) -> None:
    method = isolated_registry.get(fqn)
    state = _simulate_dynamic_panel(
        seed=17,
        n_entities=120,
        n_periods=8,
        rho=0.6,
        beta=0.9,
    )

    result = method.pure_step(state, {"step_count": 2, "dependence_mode": "auto"})["result"]

    assert result.params["lagged_dependent"] == pytest.approx(0.6, abs=rho_tolerance)
    assert result.params["policy_x"] == pytest.approx(0.9, abs=beta_tolerance)
    assert result.diagnostics["instrument_count"] > len(result.params)
    assert result.diagnostics["hansen_df"] >= 0
    assert result.diagnostics["ar1_statistic"] is not None
    assert result.diagnostics["ar2_pvalue"] is not None
    assert result.cross_sectional_dependence_diagnostic is not None


def test_difference_gmm_suppresses_inference_under_factor_dependence(isolated_registry) -> None:
    method = isolated_registry.get("econometrics.panel.difference_gmm@1.0.0")
    n_entities = 60
    loadings = np.linspace(-0.8, 0.8, n_entities)
    state = _simulate_dynamic_panel(
        seed=4,
        n_entities=n_entities,
        n_periods=9,
        rho=0.55,
        beta=1.0,
        error_scale=0.3,
        factor_loadings=loadings,
        factor_scale=1.0,
    )

    result = method.pure_step(
        state,
        {
            "step_count": 2,
            "dependence_mode": "auto",
            "dependence_fallback": "suppress_inference",
        },
    )["result"]

    diagnostic = result.cross_sectional_dependence_diagnostic
    assert diagnostic is not None
    assert diagnostic.class_label == "factor"
    assert diagnostic.estimator_status == "unsafe_for_default_inference"
    assert result.metadata["inference_suppressed"] is True
    assert result.std_errors == {}
    assert result.p_values == {}
    assert result.confidence_intervals == {}


def test_difference_gmm_auto_routes_to_block_covariance(isolated_registry) -> None:
    method = isolated_registry.get("econometrics.panel.difference_gmm@1.0.0")
    cluster_ids = np.repeat(np.arange(6), 8)
    state = _simulate_dynamic_panel(
        seed=2,
        n_entities=48,
        n_periods=8,
        rho=0.55,
        beta=1.0,
        error_scale=0.6,
        cluster_ids=cluster_ids,
        cluster_scale=0.4,
    )

    result = method.pure_step(
        state,
        {
            "step_count": 2,
            "dependence_mode": "auto",
            "dependence_fallback": "conservative",
        },
    )["result"]

    diagnostic = result.cross_sectional_dependence_diagnostic
    assert diagnostic is not None
    assert diagnostic.class_label == "block"
    assert diagnostic.recommended_covariance == "fixed_g_cluster"
    assert result.diagnostics["applied_covariance"] == "fixed_g_cluster"
    assert result.metadata["dependence_posture"]["class_label"] == "block"


def test_dynamic_panel_persists_shared_dependence_ref(isolated_registry, tmp_path) -> None:
    method = isolated_registry.get("econometrics.panel.system_gmm@1.0.0")
    store = FileSystemCAS(tmp_path / "cas")
    state = _simulate_dynamic_panel(
        seed=21,
        n_entities=80,
        n_periods=7,
        rho=0.5,
        beta=0.8,
    )

    result = method.pure_step(
        state,
        {"step_count": 2, "dependence_mode": "auto", "artifact_store": store},
    )["result"]

    assert result.dependence_ref is not None
    loaded = load_dependence_structure(store, result.dependence_ref)
    diagnostic = result.cross_sectional_dependence_diagnostic
    assert diagnostic is not None
    assert loaded.regime == "panel"
    assert loaded.calibrated is (
        diagnostic.estimator_status in {"ok", "ok_conservative"}
    )
    assert loaded.class_label == diagnostic.class_label
    assert diagnostic.shared_artifacts_ref == str(result.dependence_ref.artifact_id)
