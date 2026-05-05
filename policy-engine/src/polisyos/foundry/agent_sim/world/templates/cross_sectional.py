"""Cross-sectional SCM template."""

from __future__ import annotations

from typing import Any

import numpy as np

from polisyos.foundry.agent_sim.world.models import SyntheticWorldDGP
from polisyos.foundry.agent_sim.world.operators import (
    apply_entity_sampling,
    apply_measurement_error,
    apply_missingness,
    static_treatment_assignments,
)
from polisyos.foundry.agent_sim.world.targets import (
    exact_linear_regression_posterior,
    register_binary_classification_targets,
    register_cross_sectional_causal_targets,
    register_cross_sectional_econometrics_targets,
    register_distributional_targets,
    register_latent_state_targets,
    register_prior_targets,
    register_regression_targets,
    register_survey_targets,
)

from .common import MaterializedWorldPayload, default_splits


def _default_numeric_targets(table: dict[str, np.ndarray]) -> tuple[str, ...]:
    excluded = {"unit_id", "inclusion_probability", "base_weight", "calibrated_weight"}
    return tuple(
        name
        for name, values in table.items()
        if name not in excluded and np.issubdtype(np.asarray(values).dtype, np.number)
    )


def materialize_cross_sectional_world(spec: SyntheticWorldDGP) -> MaterializedWorldPayload:
    """Materialize a cross-sectional world with Bayesian/ML/causal/survey truth."""
    rng = np.random.default_rng(spec.seed)
    n_obs = int(spec.n_units)
    n_features = int(spec.n_features)
    features = rng.normal(size=(n_obs, n_features))
    latent_u = rng.normal(scale=0.7, size=n_obs)
    beta = np.linspace(0.45, -0.15, n_features, dtype=float)
    treatment, propensity = static_treatment_assignments(
        features=features,
        latent_driver=latent_u,
        confounding_strength=spec.confounding_strength,
        rng=rng,
    )
    mediator = 0.45 * treatment + 0.35 * features[:, 0] + rng.normal(scale=0.2, size=n_obs)
    baseline = 0.8 + features @ beta + 0.6 * latent_u + 0.25 * mediator
    treatment_effect = spec.treatment_effect + spec.heterogeneity_scale * (
        0.8 * features[:, 0] - 0.4 * features[:, min(1, n_features - 1)]
    )
    epsilon = rng.normal(scale=spec.noise_scale, size=n_obs)
    y0 = baseline + epsilon
    y1 = baseline + treatment_effect + epsilon
    observed_outcome = np.where(treatment == 1, y1, y0)
    positive_class_probability = 1.0 / (
        1.0 + np.exp(-(observed_outcome / max(spec.classification_temperature, 1.0e-6)))
    )
    labels = rng.binomial(1, positive_class_probability).astype(int)

    sampling = apply_entity_sampling(
        entity_signal=propensity,
        design_kind=spec.sampling.kind,
        inclusion_rate=spec.sampling.inclusion_rate,
        rng=rng,
    )
    sampled_index = np.flatnonzero(sampling.sample_mask)

    latent_table: dict[str, np.ndarray] = {
        "unit_id": sampled_index.astype(int),
        "latent_confounder": latent_u[sampled_index],
        "propensity": propensity[sampled_index],
        "mediator": mediator[sampled_index],
        "treatment_effect": treatment_effect[sampled_index],
        "potential_outcome_0": y0[sampled_index],
        "potential_outcome_1": y1[sampled_index],
        "outcome": observed_outcome[sampled_index],
        "label": labels[sampled_index],
        "classification_probability": positive_class_probability[sampled_index],
        "treatment": treatment[sampled_index],
        "inclusion_probability": sampling.inclusion_probability[sampled_index],
        "base_weight": sampling.base_weight[sampled_index],
    }
    for feature_idx in range(n_features):
        latent_table[f"feature_{feature_idx}"] = features[sampled_index, feature_idx]

    observed_table = {
        name: values
        for name, values in latent_table.items()
        if not name.startswith("latent_")
        and not name.startswith("potential_outcome_")
        and name != "treatment_effect"
        and name != "propensity"
    }

    measurement_targets = spec.measurement.targets or _default_numeric_targets(observed_table)
    observed_table, measurement_meta = apply_measurement_error(
        observed_table,
        kind=spec.measurement.kind,
        scale=spec.measurement.scale,
        misclassification_probability=spec.measurement.misclassification_probability,
        heaping_base=spec.measurement.heaping_base,
        top_code_quantile=spec.measurement.top_code_quantile,
        targets=measurement_targets,
        rng=rng,
    )
    missing_targets = spec.missingness.targets or tuple(
        name for name in _default_numeric_targets(observed_table) if name != "base_weight"
    )
    observed_table, missingness_meta = apply_missingness(
        observed_table,
        clean_reference=latent_table,
        mechanism=spec.missingness.mechanism,
        rate=spec.missingness.rate,
        strength=spec.missingness.strength,
        targets=missing_targets,
        rng=rng,
    )

    truth_registry: dict[str, dict[str, Any]] = {}
    unit_ids = sampled_index.astype(int)
    truth_registry.update(
        register_cross_sectional_causal_targets(
            y0=y0[sampled_index],
            y1=y1[sampled_index],
            treatment=treatment[sampled_index],
            unit_ids=unit_ids,
            propensity=propensity[sampled_index],
            mediator=mediator[sampled_index],
        )
    )
    truth_registry.update(
        register_cross_sectional_econometrics_targets(
            treatment_effect=treatment_effect[sampled_index],
            structural_coefficients={
                "intercept": 0.8,
                **{f"feature_{idx}": float(beta[idx]) for idx in range(n_features)},
            },
        )
    )
    truth_registry.update(
        register_regression_targets(
            conditional_mean=baseline[sampled_index]
            + propensity[sampled_index] * treatment_effect[sampled_index],
            conditional_variance=np.full(sampled_index.shape[0], spec.noise_scale**2, dtype=float),
            unit_ids=unit_ids,
        )
    )
    truth_registry.update(
        register_binary_classification_targets(
            class_probability=positive_class_probability[sampled_index],
            labels=labels[sampled_index],
            entity_ids=unit_ids,
            coord_name="unit_id",
        )
    )
    truth_registry.update(
        register_distributional_targets(
            sample=observed_outcome[sampled_index],
            subgroup_ids=treatment[sampled_index],
            subgroup_name="treatment",
        )
    )
    truth_registry.update(
        register_survey_targets(
            sampling=sampling,
            outcome=observed_outcome,
            entity_ids=np.arange(n_obs, dtype=int),
            coord_name="unit_id",
            domain_codes=(features[:, 0] > 0).astype(int),
            domain_name="domain",
            design_variance=float(np.var(sampling.base_weight * observed_outcome) / max(n_obs, 1)),
        )
    )
    design = np.column_stack(
        [
            np.ones(sampled_index.shape[0], dtype=float),
            treatment[sampled_index].astype(float),
            features[sampled_index],
        ]
    )
    coefficient_names = ["intercept", "treatment"] + [f"feature_{idx}" for idx in range(n_features)]
    prior_scale = 5.0
    prior_predictive_std = np.sqrt(
        np.sum((design * prior_scale) ** 2, axis=1) + spec.noise_scale**2
    )
    truth_registry.update(
        register_prior_targets(
            parameter_names=coefficient_names,
            prior_mean=np.zeros(len(coefficient_names), dtype=float),
            prior_covariance=np.eye(len(coefficient_names), dtype=float) * (prior_scale**2),
            predictive_mean=np.zeros(sampled_index.shape[0], dtype=float),
            predictive_std=prior_predictive_std,
            coord_name="unit_id",
            entity_ids=unit_ids,
        )
    )
    truth_registry["bayesian.exact_posterior"] = exact_linear_regression_posterior(
        design=design,
        outcome=observed_outcome[sampled_index],
        noise_scale=spec.noise_scale,
        coefficient_names=coefficient_names,
    )
    truth_registry.update(
        register_latent_state_targets(
            state_values=latent_u[sampled_index],
            coord_name="unit_id",
            entity_ids=unit_ids,
        )
    )

    metadata: dict[str, Any] = {
        "measurement": measurement_meta,
        "missingness": missingness_meta,
        "sampled_entities": int(sampled_index.shape[0]),
        "population_size": n_obs,
    }
    return MaterializedWorldPayload(
        latent_table=latent_table,
        observed_table=observed_table,
        truth_registry=truth_registry,
        metadata=metadata,
        splits=default_splits(sampled_index.shape[0]),
    )


__all__ = ["materialize_cross_sectional_world"]
