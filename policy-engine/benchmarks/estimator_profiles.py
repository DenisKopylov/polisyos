"""Shared benchmark estimator profiles for PolicyOS benchmark suites."""

from __future__ import annotations

import os
from typing import Any

from benchmarks.runtime import BenchmarkTier


ESTIMATION_METHOD_PROFILES = ("production_estimation", "full_matrix_estimation")


def fast_benchmark_mode() -> bool:
    return os.environ.get("BENCH_TEST_FAST", "0").strip() == "1"


def resolve_estimation_method_profile(
    tier: BenchmarkTier,
    *,
    requested: str | None = None,
) -> str:
    value = (requested or os.environ.get("BENCH_ESTIMATION_METHOD_PROFILE", "")).strip().lower()
    if not value:
        value = "production_estimation" if tier is BenchmarkTier.LOCAL_EVIDENCE else "full_matrix_estimation"
    if value not in ESTIMATION_METHOD_PROFILES:
        valid = ", ".join(ESTIMATION_METHOD_PROFILES)
        raise ValueError(f"Unknown estimation method profile: {value!r}. Expected one of: {valid}")
    return value


def policyos_nuisance_params(
    tier: BenchmarkTier,
    *,
    seed: int,
    hte: bool = False,
) -> dict[str, Any]:
    """Canonical competitive nuisance configuration used in benchmark suites."""
    local = tier is BenchmarkTier.LOCAL_EVIDENCE
    fast_mode = fast_benchmark_mode()
    if fast_mode:
        crossfit_folds = 2
        n_repeats = 1
    elif local:
        crossfit_folds = 3
        n_repeats = 1
    else:
        crossfit_folds = 5
        n_repeats = 3
    seed_manifest = tuple(seed + 997 * idx for idx in range(n_repeats))
    propensity_clip = 0.025 if local else 0.01
    overlap_trim = 0.025 if local else 0.02
    return {
        "nuisance_model_family": "competitive",
        "crossfit_folds": crossfit_folds,
        "n_repeats": n_repeats,
        "random_seed": seed,
        "random_seed_manifest": seed_manifest,
        "propensity_backend": "histgradientboosting" if local else "lightgbm",
        "propensity_backend_candidates": ["lightgbm", "histgradientboosting", "logistic_regression"],
        "outcome_backend": "histgradientboosting" if local else "lightgbm",
        "outcome_backend_candidates": [
            "histgradientboosting",
            "elastic_net",
            "lightgbm",
            "random_forest",
            "gradient_boosting",
        ],
        "backend_selection_policy": "causal_risk",
        "selection_objective": "causal_risk",
        "calibration_mode": "isotonic",
        "calibration_fraction": 0.1 if fast_mode else (0.18 if local else 0.2),
        "min_calibration_size": 16 if fast_mode else (24 if local else 32),
        "min_effective_sample_size": 24 if fast_mode else (48 if local else 80),
        "propensity_clipping": propensity_clip,
        "propensity_trimming": overlap_trim,
        "overlap_trim": overlap_trim,
        "overlap_diagnostic_policy": "ntv_proxy+ess",
        "weak_overlap_mode": "stabilized_trimmed_dr" if local else "diagnostic_only",
        "overlap_guard": 0.12 if local else 0.08,
        "outcome_scaling": "raw+standardized",
        "inference_backend": "bootstrap_eif",
        "ci_mode": "auto",
        "coverage_guard": "ess_aware",
        "bootstrap_draws": 40 if fast_mode else (100 if local else 500),
        "feature_importance_mode": "model_based",
        "parallel_folds": True,
        "max_parallel_folds": 3,
    }


def policyos_causal_forest_params(tier: BenchmarkTier, *, seed: int) -> dict[str, Any]:
    local = tier is BenchmarkTier.LOCAL_EVIDENCE
    fast_mode = fast_benchmark_mode()
    return {
        "n_estimators": 160 if local else 320,
        "n_estimators_candidates": [128, 160, 224] if local else [240, 320, 480],
        "min_samples_leaf": 6 if local else 8,
        "min_samples_leaf_candidates": [4, 6, 8] if local else [6, 8, 12],
        "max_samples": 0.5,
        "honest": True,
        "cv_folds": 2 if local else 3,
        "random_state": seed,
        "feature_importance_method": "model_based",
        "confidence_level": 0.95,
        "model_y_backend": "histgradientboosting" if local else "random_forest",
        "model_t_backend": "histgradientboosting" if local else "random_forest",
        "bootstrap_inference_samples": 12 if fast_mode else (24 if local else 48),
        "bootstrap_inference_n_jobs": 4,
        "subgroup_quantiles": 4,
        "selection_objective": "r_risk",
        "split_policy": "crossfit_pseudo_outcome",
        "calibration_mode": "causal_isotonic",
    }


def policyos_causal_bcf_params(tier: BenchmarkTier, *, seed: int) -> dict[str, Any]:
    local = tier is BenchmarkTier.LOCAL_EVIDENCE
    fast_mode = fast_benchmark_mode()
    return {
        "backend": "sklearn",
        "confidence_level": 0.95,
        "bootstrap_runs": 40 if fast_mode else (60 if local else 120),
        "num_gfr": 50 if local else 100,
        "num_mcmc": 80 if fast_mode else (120 if local else 200),
        "num_trees_mu": 200 if local else 280,
        "num_trees_tau": 80 if local else 120,
        "ridge_alpha": 1.0,
        "random_state": seed,
        "selection_objective": "r_risk",
        "split_policy": "crossfit_pseudo_outcome",
        "calibration_mode": "causal_isotonic",
    }


def policyos_forestdr_params(tier: BenchmarkTier, *, seed: int) -> dict[str, Any]:
    local = tier is BenchmarkTier.LOCAL_EVIDENCE
    fast_mode = fast_benchmark_mode()
    return {
        "n_estimators": 64 if local else 240,
        "min_samples_leaf": 20 if local else 10,
        "max_depth": 6 if local else None,
        "cv_folds": 2 if fast_mode or local else 3,
        "bootstrap_draws": 40 if fast_mode else (60 if local else 100),
        "confidence_level": 0.95,
        "random_state": seed,
    }


def policyos_xlearner_params(tier: BenchmarkTier, *, seed: int) -> dict[str, Any]:
    local = tier is BenchmarkTier.LOCAL_EVIDENCE
    fast_mode = fast_benchmark_mode()
    return {
        "learner_type": "x",
        "base_model": "auto",
        "base_model_candidates": ["linear", "elastic_net_sparse", "gradient_boosting", "random_forest"],
        "random_state": seed,
        "feature_importance_method": "model_based",
        "confidence_level": 0.95,
        "bootstrap_inference_samples": 12 if fast_mode else (24 if local else 48),
        "bootstrap_inference_n_jobs": 4,
        "subgroup_quantiles": 4,
        "selection_objective": "r_risk",
        "split_policy": "crossfit_pseudo_outcome",
        "calibration_mode": "causal_isotonic",
    }


def benchmark_selection_manifest_from_params(
    params: dict[str, Any] | None,
    *,
    method_label: str | None = None,
) -> dict[str, Any]:
    payload = dict(params or {})
    selected_propensity = payload.get("propensity_backend")
    selected_outcome = (
        payload.get("outcome_backend")
        or payload.get("base_model")
        or method_label
    )
    tested_propensity = payload.get("propensity_backend_candidates")
    if not tested_propensity:
        tested_propensity = [selected_propensity] if selected_propensity else []
    tested_outcome = payload.get("outcome_backend_candidates")
    if not tested_outcome:
        tested_outcome = payload.get("base_model_candidates")
    if not tested_outcome:
        tested_outcome = [selected_outcome] if selected_outcome else []
    calibration_modes = [
        value
        for value in [
            payload.get("calibration_mode"),
            payload.get("cate_calibration_mode"),
        ]
        if value
    ]
    manifest = {
        "selected_propensity_backend": selected_propensity,
        "selected_outcome_backend": selected_outcome,
        "tested_propensity_backends": [str(value) for value in tested_propensity if value is not None],
        "tested_outcome_backends": [str(value) for value in tested_outcome if value is not None],
        "selection_objective": payload.get("selection_objective") or payload.get("backend_selection_policy"),
        "split_policy": payload.get("split_policy") or payload.get("overlap_diagnostic_policy"),
        "calibration_modes": [str(value) for value in calibration_modes],
    }
    if payload.get("feature_importance_method"):
        manifest["feature_importance_method"] = str(payload["feature_importance_method"])
    return manifest


def external_dml_params(*, seed: int) -> dict[str, Any]:
    return {
        "model_type": "linear",
        "cv_folds": 3,
        "random_state": seed,
    }


__all__ = [
    "ESTIMATION_METHOD_PROFILES",
    "benchmark_selection_manifest_from_params",
    "external_dml_params",
    "fast_benchmark_mode",
    "policyos_causal_bcf_params",
    "policyos_causal_forest_params",
    "policyos_forestdr_params",
    "policyos_nuisance_params",
    "policyos_xlearner_params",
    "resolve_estimation_method_profile",
]
