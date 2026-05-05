from __future__ import annotations

import numpy as np
from polisyos.foundry.methods.catalog.causal.calibration import (
    make_calibrated_propensity_prediction,
)
from polisyos.foundry.methods.catalog.causal.ci_backends import (
    bootstrap_mean_interval,
    robust_standard_error,
)
from polisyos.foundry.methods.catalog.causal.nuisance_backends import (
    build_split_manifest,
    make_propensity_backend,
)
from polisyos.foundry.methods.catalog.causal.nuisance_layer import (
    build_nuisance_config,
    crossfit_nuisances,
    fit_outcome_scaler,
)


def _synthetic_binary_problem(seed: int = 7) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = 240
    X = rng.normal(size=(n, 4))
    logits = 1.5 * X[:, 0] - 0.8 * X[:, 1] + 0.4 * X[:, 2]
    prop = 1.0 / (1.0 + np.exp(-logits))
    treatment = rng.binomial(1, np.clip(prop, 0.05, 0.95)).astype(float)
    outcome = 1.2 * X[:, 0] + 0.7 * X[:, 1] + 0.5 * treatment + rng.normal(scale=0.3, size=n)
    return X, treatment, outcome


def test_build_nuisance_config_v2_fields() -> None:
    config = build_nuisance_config(
        {
            "crossfit_folds": 5,
            "n_repeats": 3,
            "propensity_clipping": 0.01,
            "propensity_trimming": 0.02,
            "calibration_mode": "sigmoid",
            "bootstrap_draws": 500,
            "random_seed_manifest": [11, 22, 33],
        }
    )
    assert config.crossfit_folds == 5
    assert config.n_repeats == 3
    assert config.propensity_clipping == 0.01
    assert config.calibration_mode == "sigmoid"
    assert config.random_seed_manifest == (11, 22, 33)


def test_crossfit_nuisances_is_deterministic_and_reports_diagnostics() -> None:
    X, treatment, outcome = _synthetic_binary_problem()
    config = build_nuisance_config(
        {
            "crossfit_folds": 4,
            "n_repeats": 2,
            "random_seed": 13,
            "random_seed_manifest": [101, 202],
            "propensity_clipping": 0.01,
            "propensity_trimming": 0.02,
            "calibration_mode": "isotonic",
            "outcome_scaling": "raw+standardized",
        }
    )

    first = crossfit_nuisances(X, treatment, outcome, config)
    second = crossfit_nuisances(X, treatment, outcome, config)

    np.testing.assert_allclose(first.propensity, second.propensity)
    np.testing.assert_allclose(first.mu1, second.mu1)
    np.testing.assert_allclose(first.mu0, second.mu0)
    assert first.diagnostics()["effective_sample_size"] > 0.0
    assert first.diagnostics()["clipping_fraction"] >= 0.0
    assert first.diagnostics()["support_mismatch_fraction"] >= 0.0
    assert first.diagnostics()["propensity_histogram"]["counts"]
    assert first.diagnostics()["overlap_histogram"]["counts"]
    assert first.diagnostics()["split_manifest"]["n_repeats"] == 2


def test_calibrated_propensity_prediction_remains_in_bounds() -> None:
    X, treatment, _ = _synthetic_binary_problem(seed=19)
    config = build_nuisance_config({"random_seed": 19, "calibration_mode": "isotonic"})
    split_manifest, repeat_seeds = build_split_manifest(
        treatment,
        n_folds=config.crossfit_folds,
        n_repeats=1,
        base_seed=config.random_seed,
        seed_manifest=config.random_seed_manifest,
    )
    train_idx, test_idx = split_manifest[0][0]
    backend = make_propensity_backend(19, "competitive")
    pred, calibration = make_calibrated_propensity_prediction(
        X,
        treatment,
        train_idx=train_idx,
        test_idx=test_idx,
        base_model=backend.model,
        stabilizer_model=backend.stabilizer,
        calibration_mode="sigmoid",
        clip=0.01,
        seed=repeat_seeds[0],
    )
    assert calibration.calibration_size >= 1
    assert np.all(pred >= 0.01)
    assert np.all(pred <= 0.99)


def test_interval_helpers_bootstrap_eif_and_scale_policy() -> None:
    values = np.array([1.0, 1.4, 1.2, 1.8, 1.6], dtype=float)
    lower, upper = bootstrap_mean_interval(values, seed=3, draws=64)
    assert lower < upper
    assert robust_standard_error(values) > 0.0

    scaler = fit_outcome_scaler(values, "raw+standardized")
    assert scaler.applied is True
    assert scaler.policy == "raw+standardized"
