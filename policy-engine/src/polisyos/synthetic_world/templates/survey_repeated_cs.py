"""Repeated cross-sectional survey template."""
from __future__ import annotations

from typing import Any

import numpy as np

from polisyos.synthetic_world.models import SyntheticWorldDGP
from polisyos.synthetic_world.operators import apply_measurement_error, apply_missingness, apply_survey_sampling, survey_wave_treatment_assignments
from polisyos.synthetic_world.targets import (
    register_binary_classification_targets,
    register_distributional_targets,
    register_forecasting_targets,
    register_latent_state_targets,
    register_prior_targets,
    register_regression_targets,
    register_reference_posterior_targets,
    register_survey_econometrics_targets,
)

from .common import MaterializedWorldPayload, default_splits


def materialize_survey_repeated_cross_section_world(spec: SyntheticWorldDGP) -> MaterializedWorldPayload:
    """Materialize a survey repeated-cross-section world."""
    rng = np.random.default_rng(spec.seed)
    n_units = int(spec.n_units)
    n_features = int(spec.n_features)
    n_waves = int(spec.n_waves)

    population_features = rng.normal(size=(n_units, n_features))
    strata = np.mod(np.arange(n_units), spec.n_strata)
    clusters = np.mod(np.arange(n_units), spec.n_clusters)
    base_size_signal = 0.5 * np.abs(population_features[:, 0]) + 0.25 * strata + 0.2 * clusters
    wave_effect = np.linspace(-0.25, 0.35, n_waves, dtype=float)
    wave_ids = np.arange(n_waves, dtype=int)
    wave_treatment = survey_wave_treatment_assignments(
        wave_index=wave_ids,
        treatment_share=spec.intervention.treatment_share,
    )

    respondent_rows: list[dict[str, Any]] = []
    population_wave_means: list[float] = []
    inclusion_probability_by_wave: list[np.ndarray] = []
    response_probability_by_wave: list[np.ndarray] = []
    calibrated_weight_by_wave: list[np.ndarray] = []
    design_effect_by_wave: list[float] = []

    for wave in wave_ids:
        wave_sampling = apply_survey_sampling(
            size_signal=base_size_signal + 0.15 * wave,
            inclusion_rate=spec.sampling.inclusion_rate,
            response_rate=spec.sampling.response_rate,
            n_strata=spec.sampling.n_strata,
            n_clusters=spec.sampling.n_clusters,
            calibrate_weights=spec.sampling.calibrate_weights,
            rng=rng,
        )
        inclusion_probability_by_wave.append(wave_sampling.inclusion_probability.copy())
        response_probability_by_wave.append(np.asarray(wave_sampling.response_probability, dtype=float).copy())
        calibrated_weight_by_wave.append(np.asarray(wave_sampling.calibrated_weight, dtype=float).copy())
        design_effect_by_wave.append(float(wave_sampling.design_effect or 1.0))

        latent_driver = rng.normal(scale=0.45, size=n_units)
        outcome_mean = (
            0.6
            + population_features @ np.linspace(0.35, -0.12, n_features, dtype=float)
            + wave_effect[wave]
            + spec.treatment_effect * wave_treatment[wave]
            + spec.heterogeneity_scale * population_features[:, 0]
            + 0.2 * latent_driver
        )
        outcome = outcome_mean + rng.normal(scale=spec.noise_scale, size=n_units)
        population_wave_means.append(float(np.mean(outcome)))

        labels_probability = 1.0 / (1.0 + np.exp(-(outcome / max(spec.classification_temperature, 1.0e-6))))
        labels = rng.binomial(1, labels_probability).astype(int)
        respondent_mask = np.asarray(wave_sampling.respondent_mask, dtype=bool)
        respondent_indices = np.flatnonzero(respondent_mask)

        for idx in respondent_indices:
            row = {
                "unit_id": int(idx),
                "wave": int(wave),
                "stratum": int(strata[idx]),
                "cluster": int(clusters[idx]),
                "treatment": int(wave_treatment[wave]),
                "outcome": float(outcome[idx]),
                "label": int(labels[idx]),
                "classification_probability": float(labels_probability[idx]),
                "conditional_mean": float(outcome_mean[idx]),
                "conditional_variance": float(spec.noise_scale**2),
                "inclusion_probability": float(wave_sampling.inclusion_probability[idx]),
                "response_probability": float(wave_sampling.response_probability[idx]),
                "base_weight": float(wave_sampling.base_weight[idx]),
                "calibrated_weight": float(wave_sampling.calibrated_weight[idx]),
            }
            for feature_idx in range(n_features):
                row[f"feature_{feature_idx}"] = float(population_features[idx, feature_idx])
            respondent_rows.append(row)

    ordered_keys = sorted(respondent_rows[0]) if respondent_rows else []
    latent_table = {
        key: np.asarray([row[key] for row in respondent_rows])
        for key in ordered_keys
    }
    observed_table = dict(latent_table)
    observed_table, measurement_meta = apply_measurement_error(
        observed_table,
        kind=spec.measurement.kind,
        scale=spec.measurement.scale,
        misclassification_probability=spec.measurement.misclassification_probability,
        heaping_base=spec.measurement.heaping_base,
        top_code_quantile=spec.measurement.top_code_quantile,
        targets=spec.measurement.targets or ("outcome", "feature_0"),
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

    respondent_unit_ids = np.asarray(latent_table["unit_id"], dtype=int)
    respondent_wave_ids = np.asarray(latent_table["wave"], dtype=int)
    truth_registry: dict[str, dict[str, Any]] = {}
    truth_registry.update(
        register_regression_targets(
            conditional_mean=np.asarray(latent_table["conditional_mean"], dtype=float),
            conditional_variance=np.asarray(latent_table["conditional_variance"], dtype=float),
            unit_ids=np.arange(respondent_unit_ids.shape[0], dtype=int),
        )
    )
    truth_registry.update(
        register_binary_classification_targets(
            class_probability=np.asarray(latent_table["classification_probability"], dtype=float),
            labels=np.asarray(latent_table["label"], dtype=int),
            entity_ids=np.arange(respondent_unit_ids.shape[0], dtype=int),
            coord_name="respondent_row",
        )
    )
    truth_registry.update(
        {
            "survey.inclusion_probabilities": {
                "values": np.concatenate(inclusion_probability_by_wave).tolist(),
                "coords": {
                    "population_row": list(np.arange(n_units * n_waves, dtype=int)),
                    "wave": np.repeat(wave_ids, n_units).tolist(),
                },
            },
            "survey.response_probabilities": {
                "values": np.concatenate(response_probability_by_wave).tolist(),
                "coords": {
                    "population_row": list(np.arange(n_units * n_waves, dtype=int)),
                    "wave": np.repeat(wave_ids, n_units).tolist(),
                },
            },
            "survey.base_weights": {
                "values": np.concatenate([1.0 / values for values in inclusion_probability_by_wave]).tolist(),
                "coords": {
                    "population_row": list(np.arange(n_units * n_waves, dtype=int)),
                    "wave": np.repeat(wave_ids, n_units).tolist(),
                },
            },
            "survey.calibrated_weights": {
                "values": np.concatenate(calibrated_weight_by_wave).tolist(),
                "coords": {
                    "population_row": list(np.arange(n_units * n_waves, dtype=int)),
                    "wave": np.repeat(wave_ids, n_units).tolist(),
                },
            },
            "survey.design_effect": {"value": float(np.mean(design_effect_by_wave))},
            "survey.design_variance": {
                "value": float(
                    np.var(
                        np.asarray(latent_table["calibrated_weight"], dtype=float)
                        * np.asarray(latent_table["outcome"], dtype=float)
                    )
                    / max(len(respondent_rows), 1)
                )
            },
            "survey.population_mean": {"value": float(np.mean(population_wave_means))},
            "survey.population_total": {"value": float(np.sum(population_wave_means))},
            "survey.domain_means": {
                "values": [float(np.mean(np.asarray(population_wave_means)[wave_treatment == marker])) for marker in np.unique(wave_treatment)],
                "coords": {"treatment_wave": [str(marker) for marker in np.unique(wave_treatment)]},
            },
        }
    )
    truth_registry.update(
        register_survey_econometrics_targets(
            wave_effects=wave_effect,
            wave_ids=wave_ids,
        )
    )
    forecast_means: dict[int, np.ndarray] = {}
    forecast_intervals: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    last_wave_mean = np.asarray([population_wave_means[-1]], dtype=float)
    for horizon in (1, 2):
        forecast_mean = last_wave_mean + horizon * (population_wave_means[-1] - population_wave_means[-2])
        radius = 1.645 * spec.noise_scale * np.sqrt(float(horizon))
        forecast_means[horizon] = forecast_mean
        forecast_intervals[horizon] = (forecast_mean - radius, forecast_mean + radius)
    truth_registry.update(
        register_forecasting_targets(
            forecast_means=forecast_means,
            forecast_intervals=forecast_intervals,
            entity_ids=np.array([n_waves], dtype=int),
            coord_name="forecast_wave",
        )
    )
    truth_registry.update(
        register_distributional_targets(
            sample=np.asarray(latent_table["outcome"], dtype=float),
            subgroup_ids=respondent_wave_ids,
            subgroup_name="wave",
        )
    )
    truth_registry["causal.ate"] = {"value": float(spec.treatment_effect)}
    truth_registry["causal.att"] = {"value": float(spec.treatment_effect)}
    truth_registry["causal.cate"] = {
        "values": (spec.treatment_effect + spec.heterogeneity_scale * np.asarray(latent_table["feature_0"], dtype=float)).tolist(),
        "coords": {"respondent_row": list(np.arange(respondent_unit_ids.shape[0], dtype=int))},
    }
    truth_registry.update(
        register_prior_targets(
            parameter_names=["treatment_effect", "wave_trend"],
            prior_mean=np.zeros(2, dtype=float),
            prior_covariance=np.diag(np.array([1.0, 1.0], dtype=float)),
            predictive_mean=np.zeros(1, dtype=float),
            predictive_std=np.full(1, np.sqrt(1.0 + spec.noise_scale**2), dtype=float),
            coord_name="forecast_wave",
            entity_ids=np.array([n_waves], dtype=int),
        )
    )
    truth_registry.update(
        register_reference_posterior_targets(
            parameter_names=["treatment_effect", "wave_trend"],
            point_estimates=np.array([spec.treatment_effect, population_wave_means[-1] - population_wave_means[-2]], dtype=float),
            covariance=np.diag(np.array([0.03, 0.02], dtype=float)),
            predictive_mean=forecast_means[1],
            predictive_std=(forecast_intervals[1][1] - forecast_intervals[1][0]) / (2.0 * 1.645),
            coord_name="forecast_wave",
            entity_ids=np.array([n_waves], dtype=int),
            log_evidence=float(-0.5 * len(respondent_rows) * np.log(2.0 * np.pi * spec.noise_scale**2)),
        )
    )
    truth_registry.update(
        register_latent_state_targets(
            state_values=np.asarray(latent_table["conditional_mean"], dtype=float),
            coord_name="respondent_row",
            entity_ids=np.arange(respondent_unit_ids.shape[0], dtype=int),
            extras={
                "unit_id": respondent_unit_ids.tolist(),
                "wave": respondent_wave_ids.tolist(),
            },
        )
    )

    metadata: dict[str, Any] = {
        "measurement": measurement_meta,
        "missingness": missingness_meta,
        "population_size": n_units,
        "n_waves": n_waves,
        "wave_treatment": wave_treatment.tolist(),
    }
    return MaterializedWorldPayload(
        latent_table=latent_table,
        observed_table=observed_table,
        truth_registry=truth_registry,
        metadata=metadata,
        splits=default_splits(len(respondent_rows)),
    )


__all__ = ["materialize_survey_repeated_cross_section_world"]
