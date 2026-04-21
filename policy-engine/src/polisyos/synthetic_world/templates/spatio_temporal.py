"""Spatio-temporal world template."""
from __future__ import annotations

from typing import Any

import numpy as np

from polisyos.synthetic_world.models import SyntheticWorldDGP
from polisyos.synthetic_world.operators import apply_entity_sampling, apply_measurement_error, apply_missingness, spatial_intervention_assignments
from polisyos.synthetic_world.targets import (
    register_distributional_targets,
    register_forecasting_targets,
    register_latent_state_targets,
    register_prior_targets,
    register_regression_targets,
    register_reference_posterior_targets,
    register_spatial_causal_targets,
    register_survey_targets,
)

from .common import MaterializedWorldPayload, default_splits


def _normalize_adjacency(n_regions: int) -> np.ndarray:
    adjacency = np.zeros((n_regions, n_regions), dtype=float)
    for region in range(n_regions):
        if region > 0:
            adjacency[region, region - 1] = 1.0
        if region < n_regions - 1:
            adjacency[region, region + 1] = 1.0
    degree = np.sum(adjacency, axis=1, keepdims=True)
    degree[degree == 0.0] = 1.0
    return adjacency / degree


def materialize_spatio_temporal_world(spec: SyntheticWorldDGP) -> MaterializedWorldPayload:
    """Materialize a spatio-temporal world with local forecasts and regime truth."""
    rng = np.random.default_rng(spec.seed)
    n_regions = int(spec.n_regions)
    n_periods = int(spec.n_periods)
    adjacency = _normalize_adjacency(n_regions)
    region_feature = np.linspace(-1.0, 1.0, n_regions, dtype=float)
    state = np.zeros((n_regions, n_periods), dtype=float)
    intervention = np.zeros((n_regions, n_periods), dtype=int)
    outcome = np.zeros((n_regions, n_periods), dtype=float)
    regime_labels = np.array(
        ["baseline" if period < max(1, n_periods // 2) else "shock" for period in range(n_periods)],
        dtype=object,
    )
    region_effect = spec.treatment_effect + spec.heterogeneity_scale * region_feature
    treatment_start = spec.intervention.treatment_start_period
    if treatment_start is None:
        treatment_start = max(1, n_periods // 2)

    for period in range(n_periods):
        previous = state[:, period - 1] if period > 0 else np.zeros(n_regions, dtype=float)
        spillover = adjacency @ previous
        shock = 0.45 if regime_labels[period] == "shock" else 0.0
        state[:, period] = (
            spec.autoregressive_scale * previous
            + spec.spatial_scale * spillover
            + 0.3 * region_feature
            + shock
            + rng.normal(scale=spec.noise_scale, size=n_regions)
        )
        intervention[:, period] = spatial_intervention_assignments(
            n_regions=n_regions,
            period=period,
            treatment_start_period=treatment_start,
        )
        outcome[:, period] = (
            state[:, period]
            + region_effect * intervention[:, period]
            + rng.normal(scale=spec.noise_scale, size=n_regions)
        )

    sampling = apply_entity_sampling(
        entity_signal=np.mean(np.abs(state), axis=1),
        design_kind=spec.sampling.kind,
        inclusion_rate=spec.sampling.inclusion_rate,
        rng=rng,
    )
    sampled_regions = np.flatnonzero(sampling.sample_mask)
    repeated_regions = np.repeat(sampled_regions, n_periods)
    repeated_time = np.tile(np.arange(n_periods, dtype=int), sampled_regions.shape[0])

    latent_table: dict[str, np.ndarray] = {
        "region_id": repeated_regions,
        "time": repeated_time,
        "latent_state": state[sampled_regions].reshape(-1),
        "treatment": intervention[sampled_regions].reshape(-1),
        "outcome": outcome[sampled_regions].reshape(-1),
        "feature_0": np.repeat(region_feature[sampled_regions], n_periods),
        "treatment_effect": np.repeat(region_effect[sampled_regions], n_periods),
        "inclusion_probability": np.repeat(sampling.inclusion_probability[sampled_regions], n_periods),
        "base_weight": np.repeat(sampling.base_weight[sampled_regions], n_periods),
    }
    observed_table = {
        name: values
        for name, values in latent_table.items()
        if name not in {"latent_state", "treatment_effect"}
    }
    observed_table, measurement_meta = apply_measurement_error(
        observed_table,
        kind=spec.measurement.kind,
        scale=spec.measurement.scale,
        misclassification_probability=spec.measurement.misclassification_probability,
        heaping_base=spec.measurement.heaping_base,
        top_code_quantile=spec.measurement.top_code_quantile,
        targets=spec.measurement.targets or ("outcome",),
        rng=rng,
    )
    observed_table, missingness_meta = apply_missingness(
        observed_table,
        clean_reference=latent_table,
        mechanism=spec.missingness.mechanism,
        rate=spec.missingness.rate,
        strength=spec.missingness.strength,
        targets=spec.missingness.targets or ("outcome",),
        rng=rng,
    )

    sampled_adjacency = adjacency[np.ix_(sampled_regions, sampled_regions)]
    last_state = state[sampled_regions, -1].astype(float)
    forecast_means: dict[int, np.ndarray] = {}
    forecast_intervals: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for horizon in (1, 3):
        mean = last_state.copy()
        for _ in range(horizon):
            mean = (
                spec.autoregressive_scale * mean
                + spec.spatial_scale * (sampled_adjacency @ mean)
                + 0.3 * region_feature[sampled_regions]
            )
        radius = 1.645 * spec.noise_scale * np.sqrt(float(horizon))
        forecast_means[horizon] = mean
        forecast_intervals[horizon] = (mean - radius, mean + radius)

    truth_registry: dict[str, dict[str, Any]] = {}
    truth_registry.update(
        register_spatial_causal_targets(
            treatment_effect=region_effect[sampled_regions],
            region_ids=sampled_regions,
        )
    )
    truth_registry.update(
        register_forecasting_targets(
            forecast_means=forecast_means,
            forecast_intervals=forecast_intervals,
            entity_ids=sampled_regions,
            coord_name="region_id",
        )
    )
    truth_registry.update(
        register_regression_targets(
            conditional_mean=outcome[sampled_regions, -1],
            conditional_variance=np.full(sampled_regions.shape[0], spec.noise_scale**2, dtype=float),
            unit_ids=sampled_regions,
        )
    )
    truth_registry.update(
        register_distributional_targets(
            sample=outcome[sampled_regions, -1],
            subgroup_ids=(intervention[sampled_regions, -1] > 0).astype(int),
            subgroup_name="treated_region",
        )
    )
    truth_registry.update(
        register_survey_targets(
            sampling=sampling,
            outcome=outcome[:, -1],
            entity_ids=np.arange(n_regions, dtype=int),
            coord_name="region_id",
            domain_codes=(region_feature > 0).astype(int),
            domain_name="region_half",
            design_variance=float(np.var(sampling.base_weight * outcome[:, -1]) / max(n_regions, 1)),
        )
    )
    truth_registry.update(
        register_prior_targets(
            parameter_names=["rho", "spatial_scale", "treatment_effect"],
            prior_mean=np.zeros(3, dtype=float),
            prior_covariance=np.diag(np.array([0.25, 0.25, 1.0], dtype=float)),
            predictive_mean=np.zeros(sampled_regions.shape[0], dtype=float),
            predictive_std=np.full(sampled_regions.shape[0], np.sqrt(1.0 + spec.noise_scale**2), dtype=float),
            coord_name="region_id",
            entity_ids=sampled_regions,
        )
    )
    truth_registry.update(
        register_reference_posterior_targets(
            parameter_names=["rho", "spatial_scale", "treatment_effect"],
            point_estimates=np.array(
                [spec.autoregressive_scale, spec.spatial_scale, float(np.mean(region_effect[sampled_regions]))],
                dtype=float,
            ),
            covariance=np.diag(np.array([0.03, 0.03, 0.04], dtype=float)),
            predictive_mean=forecast_means[1],
            predictive_std=(forecast_intervals[1][1] - forecast_intervals[1][0]) / (2.0 * 1.645),
            coord_name="region_id",
            entity_ids=sampled_regions,
            log_evidence=float(-0.5 * sampled_regions.shape[0] * np.log(2.0 * np.pi * spec.noise_scale**2)),
        )
    )
    truth_registry.update(
        register_latent_state_targets(
            state_values=state[sampled_regions].reshape(-1),
            coord_name="spatial_row",
            entity_ids=np.arange(repeated_regions.shape[0], dtype=int),
            extras={
                "region_id": repeated_regions.tolist(),
                "time": repeated_time.tolist(),
            },
        )
    )
    truth_registry["regime.labels"] = {
        "values": regime_labels.tolist(),
        "coords": {"time": list(np.arange(n_periods, dtype=int))},
    }
    truth_registry["spatial.adjacency"] = {
        "values": adjacency.tolist(),
        "coords": {"row_region_id": list(np.arange(n_regions, dtype=int)), "col_region_id": list(np.arange(n_regions, dtype=int))},
    }

    metadata: dict[str, Any] = {
        "measurement": measurement_meta,
        "missingness": missingness_meta,
        "sampled_entities": int(sampled_regions.shape[0]),
        "population_size": n_regions,
    }
    return MaterializedWorldPayload(
        latent_table=latent_table,
        observed_table=observed_table,
        truth_registry=truth_registry,
        metadata=metadata,
        splits=default_splits(repeated_regions.shape[0]),
    )


__all__ = ["materialize_spatio_temporal_world"]
