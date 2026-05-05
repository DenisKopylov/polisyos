from __future__ import annotations

import numpy as np
from polisyos.foundry.methods.catalog.econometrics.dependence import (
    route_cross_sectional_dependence,
)
from polisyos.foundry.methods.catalog.econometrics.panel import (
    FixedEffectsEstimator,
    PanelDataEstimator,
    RandomEffectsEstimator,
)


def _flatten_panel(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n_entities, n_periods = matrix.shape
    entity_ids = np.repeat(np.arange(n_entities), n_periods)
    time_ids = np.tile(np.arange(n_periods), n_entities)
    return matrix.reshape(-1), entity_ids, time_ids


def test_dependence_router_detects_common_shock_removed() -> None:
    rng = np.random.default_rng(7)
    n_entities = 8
    n_periods = 10
    common_shock = np.linspace(-1.5, 1.5, n_periods)
    residual_matrix = common_shock[np.newaxis, :] + 0.05 * rng.normal(size=(n_entities, n_periods))
    residuals, entity_ids, time_ids = _flatten_panel(residual_matrix)

    diagnostic = route_cross_sectional_dependence(
        residuals,
        entity_ids=entity_ids,
        time_ids=time_ids,
    )

    assert diagnostic.class_label == "common_shock_removed"
    assert diagnostic.dependence_removed_by_time_effects is True
    assert diagnostic.estimator_status == "ok"


def test_dependence_router_detects_persistent_factor_structure() -> None:
    rng = np.random.default_rng(11)
    loadings = np.linspace(-1.8, 1.8, 8)
    factor = np.sin(np.linspace(0.0, 3.0, 12))
    residual_matrix = loadings[:, np.newaxis] * factor[np.newaxis, :] + 0.03 * rng.normal(
        size=(8, 12)
    )
    residuals, entity_ids, time_ids = _flatten_panel(residual_matrix)

    diagnostic = route_cross_sectional_dependence(
        residuals,
        entity_ids=entity_ids,
        time_ids=time_ids,
    )

    assert diagnostic.class_label == "factor"
    assert diagnostic.estimator_status == "unsafe_for_default_inference"
    assert diagnostic.recommended_covariance == "cce_reroute"


def test_dependence_router_detects_block_dependence() -> None:
    rng = np.random.default_rng(19)
    cluster_ids = np.repeat(np.arange(4), 3)
    cluster_shocks = rng.normal(scale=0.4, size=(4, 12))
    residual_matrix = cluster_shocks[cluster_ids] + 0.5 * rng.normal(size=(12, 12))
    residuals, entity_ids, time_ids = _flatten_panel(residual_matrix)

    diagnostic = route_cross_sectional_dependence(
        residuals,
        entity_ids=entity_ids,
        time_ids=time_ids,
        dependence_metadata={"cluster_ids": cluster_ids},
    )

    assert diagnostic.class_label == "block"
    assert diagnostic.estimator_status == "ok_conservative"
    assert diagnostic.recommended_covariance in {"cluster", "fixed_g_cluster"}


def test_panel_estimators_expose_dependence_parameters() -> None:
    parameter_names = {param.name for param in PanelDataEstimator.signature.parameters}
    assert {
        "dependence_mode",
        "dependence_covariance",
        "dependence_fallback",
        "dependence_metadata",
    } <= parameter_names

    fixed_effects_params = {param.name for param in FixedEffectsEstimator.signature.parameters}
    assert {
        "dependence_mode",
        "dependence_covariance",
        "dependence_fallback",
        "dependence_metadata",
    } <= fixed_effects_params

    random_effects_params = {param.name for param in RandomEffectsEstimator.signature.parameters}
    assert {
        "dependence_mode",
        "dependence_covariance",
        "dependence_fallback",
        "dependence_metadata",
    } <= random_effects_params
