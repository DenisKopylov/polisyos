"""Dynamic panel template."""

from __future__ import annotations

from typing import Any

import numpy as np

from polisyos.synthetic_world.models import SyntheticWorldDGP
from polisyos.synthetic_world.operators import (
    apply_entity_sampling,
    apply_measurement_error,
    apply_missingness,
)
from polisyos.synthetic_world.targets import (
    register_distributional_targets,
    register_dynamic_causal_targets,
    register_forecasting_targets,
    register_latent_state_targets,
    register_panel_econometrics_targets,
    register_prior_targets,
    register_reference_posterior_targets,
    register_regression_targets,
    register_survey_targets,
)

from .common import MaterializedWorldPayload, default_splits


def materialize_panel_dynamic_world(spec: SyntheticWorldDGP) -> MaterializedWorldPayload:
    """Materialize a panel-dynamic world."""
    rng = np.random.default_rng(spec.seed)
    n_units = int(spec.n_units)
    n_periods = int(spec.n_periods)
    n_features = int(spec.n_features)
    features = rng.normal(size=(n_units, n_features))
    alpha = rng.normal(scale=0.55, size=n_units)
    time_effect = np.linspace(-0.3, 0.3, n_periods, dtype=float)
    beta = np.linspace(0.3, -0.12, n_features, dtype=float)

    state = np.zeros((n_units, n_periods), dtype=float)
    treatment = np.zeros((n_units, n_periods), dtype=int)
    propensity = np.zeros((n_units, n_periods), dtype=float)
    instrument = np.zeros((n_units, n_periods), dtype=int)
    complier_gap = np.zeros((n_units, n_periods), dtype=float)
    outcome = np.zeros((n_units, n_periods), dtype=float)
    treatment_effect = spec.treatment_effect + spec.heterogeneity_scale * features[:, 0]

    for period in range(n_periods):
        lag = state[:, period - 1] if period > 0 else np.zeros(n_units, dtype=float)
        base_logit = -0.1 + 0.45 * lag + 0.25 * features[:, 0] + spec.confounding_strength * alpha
        instrument_prob = 1.0 / (
            1.0 + np.exp(-np.clip(0.15 + 0.2 * features[:, 0] - 0.1 * lag, -30.0, 30.0))
        )
        instrument[:, period] = rng.binomial(1, instrument_prob, size=n_units).astype(int)
        baseline_propensity = 1.0 / (1.0 + np.exp(-np.clip(base_logit, -30.0, 30.0)))
        propensity[:, period] = 1.0 / (
            1.0
            + np.exp(
                -np.clip(
                    base_logit + spec.intervention.instrument_strength * instrument[:, period],
                    -30.0,
                    30.0,
                )
            )
        )
        complier_gap[:, period] = (
            1.0
            / (
                1.0
                + np.exp(-np.clip(base_logit + spec.intervention.instrument_strength, -30.0, 30.0))
            )
            - baseline_propensity
        )
        treatment[:, period] = rng.binomial(1, propensity[:, period], size=n_units).astype(int)
        innovation = rng.normal(scale=spec.noise_scale, size=n_units)
        structural_mean = (
            spec.autoregressive_scale * lag + features @ beta + alpha + time_effect[period]
        )
        state[:, period] = structural_mean + innovation
        outcome[:, period] = (
            state[:, period]
            + treatment_effect * treatment[:, period]
            + rng.normal(scale=spec.noise_scale, size=n_units)
        )

    sampling = apply_entity_sampling(
        entity_signal=np.mean(propensity, axis=1),
        design_kind=spec.sampling.kind,
        inclusion_rate=spec.sampling.inclusion_rate,
        rng=rng,
    )
    sampled_index = np.flatnonzero(sampling.sample_mask)
    repeated_units = np.repeat(sampled_index, n_periods)
    repeated_time = np.tile(np.arange(n_periods, dtype=int), sampled_index.shape[0])

    latent_table: dict[str, np.ndarray] = {
        "unit_id": repeated_units,
        "time": repeated_time,
        "latent_state": state[sampled_index].reshape(-1),
        "propensity": propensity[sampled_index].reshape(-1),
        "instrument": instrument[sampled_index].reshape(-1),
        "treatment_effect": np.repeat(treatment_effect[sampled_index], n_periods),
        "outcome": outcome[sampled_index].reshape(-1),
        "treatment": treatment[sampled_index].reshape(-1),
        "inclusion_probability": np.repeat(
            sampling.inclusion_probability[sampled_index], n_periods
        ),
        "base_weight": np.repeat(sampling.base_weight[sampled_index], n_periods),
    }
    for feature_idx in range(n_features):
        latent_table[f"feature_{feature_idx}"] = np.repeat(
            features[sampled_index, feature_idx], n_periods
        )

    observed_table = {
        name: values
        for name, values in latent_table.items()
        if name not in {"latent_state", "propensity", "treatment_effect"}
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
        targets=spec.missingness.targets or ("outcome", "feature_0"),
        rng=rng,
    )

    last_state = state[sampled_index, -1].astype(float)
    drift = features[sampled_index] @ beta + alpha[sampled_index]
    forecast_means: dict[int, np.ndarray] = {}
    forecast_intervals: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for horizon in (1, 3, 6):
        mean = last_state.copy()
        for _ in range(horizon):
            mean = spec.autoregressive_scale * mean + drift
        variance = spec.noise_scale**2 * sum(
            spec.autoregressive_scale ** (2 * lag) for lag in range(horizon)
        )
        radius = 1.645 * np.sqrt(variance)
        forecast_means[horizon] = mean
        forecast_intervals[horizon] = (mean - radius, mean + radius)

    truth_registry: dict[str, dict[str, Any]] = {}
    complier_mask = np.mean(complier_gap[sampled_index], axis=1) > 0.05
    if not np.any(complier_mask):
        complier_mask = np.ones(sampled_index.shape[0], dtype=bool)
    irf_horizons = np.arange(1, 5, dtype=int)
    irf = float(np.mean(treatment_effect[sampled_index])) * (
        spec.autoregressive_scale ** (irf_horizons - 1)
    )
    truth_registry.update(
        register_dynamic_causal_targets(
            treatment_effect=treatment_effect[sampled_index],
            unit_ids=sampled_index,
            regime_value=float(np.mean(state[sampled_index, -1] + treatment_effect[sampled_index])),
            path_treated=np.mean(
                state[sampled_index] + treatment_effect[sampled_index, None], axis=0
            ),
            path_untreated=np.mean(state[sampled_index], axis=0),
            horizon_ids=np.arange(n_periods, dtype=int),
        )
    )
    truth_registry.update(
        register_panel_econometrics_targets(
            rho=spec.autoregressive_scale,
            treatment_effect=treatment_effect[sampled_index],
            unit_ids=sampled_index,
            iv_late=float(np.mean(treatment_effect[sampled_index][complier_mask])),
            complier_share=float(np.mean(complier_mask)),
            irf=irf,
            horizons=irf_horizons,
        )
    )
    truth_registry.update(
        register_forecasting_targets(
            forecast_means=forecast_means,
            forecast_intervals=forecast_intervals,
            entity_ids=sampled_index,
            coord_name="unit_id",
        )
    )
    truth_registry.update(
        register_regression_targets(
            conditional_mean=outcome[sampled_index, -1],
            conditional_variance=np.full(sampled_index.shape[0], spec.noise_scale**2, dtype=float),
            unit_ids=sampled_index,
        )
    )
    truth_registry.update(
        register_distributional_targets(
            sample=outcome[sampled_index, -1],
            subgroup_ids=(treatment[sampled_index, -1] > 0).astype(int),
            subgroup_name="treated_last_period",
        )
    )
    truth_registry.update(
        register_survey_targets(
            sampling=sampling,
            outcome=outcome[:, -1],
            entity_ids=np.arange(n_units, dtype=int),
            coord_name="unit_id",
            domain_codes=(features[:, 0] > 0).astype(int),
            domain_name="domain",
            design_variance=float(np.var(sampling.base_weight * outcome[:, -1]) / max(n_units, 1)),
        )
    )
    truth_registry.update(
        register_prior_targets(
            parameter_names=["rho", "treatment_effect", "instrument_strength"],
            prior_mean=np.zeros(3, dtype=float),
            prior_covariance=np.diag(np.array([0.25, 1.0, 1.0], dtype=float)),
            predictive_mean=np.zeros(sampled_index.shape[0], dtype=float),
            predictive_std=np.full(
                sampled_index.shape[0], np.sqrt(1.0 + spec.noise_scale**2), dtype=float
            ),
            coord_name="unit_id",
            entity_ids=sampled_index,
        )
    )
    truth_registry.update(
        register_reference_posterior_targets(
            parameter_names=["rho", "treatment_effect", "instrument_strength"],
            point_estimates=np.array(
                [
                    spec.autoregressive_scale,
                    float(np.mean(treatment_effect[sampled_index])),
                    spec.intervention.instrument_strength,
                ],
                dtype=float,
            ),
            covariance=np.diag(
                np.array(
                    [0.02, spec.noise_scale**2 / max(sampled_index.shape[0], 1), 0.03], dtype=float
                )
            ),
            predictive_mean=forecast_means[1],
            predictive_std=(forecast_intervals[1][1] - forecast_intervals[1][0]) / (2.0 * 1.645),
            coord_name="unit_id",
            entity_ids=sampled_index,
            log_evidence=float(
                -0.5 * sampled_index.shape[0] * np.log(2.0 * np.pi * spec.noise_scale**2)
            ),
        )
    )
    truth_registry.update(
        register_latent_state_targets(
            state_values=state[sampled_index].reshape(-1),
            coord_name="panel_row",
            entity_ids=np.arange(repeated_units.shape[0], dtype=int),
            extras={
                "unit_id": repeated_units.tolist(),
                "time": repeated_time.tolist(),
            },
        )
    )

    metadata: dict[str, Any] = {
        "measurement": measurement_meta,
        "missingness": missingness_meta,
        "sampled_entities": int(sampled_index.shape[0]),
        "population_size": n_units,
    }
    return MaterializedWorldPayload(
        latent_table=latent_table,
        observed_table=observed_table,
        truth_registry=truth_registry,
        metadata=metadata,
        splits=default_splits(repeated_units.shape[0]),
    )


__all__ = ["materialize_panel_dynamic_world"]
