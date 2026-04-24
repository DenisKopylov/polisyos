"""Fit cross-fitted nuisance functions and outcome scaling for orthogonal learners."""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np

from polisyos.foundry.methods.catalog.causal.calibration import (
    make_calibrated_propensity_prediction,
)
from polisyos.foundry.methods.catalog.causal.ci_backends import (
    bootstrap_mean_interval as _ci_bootstrap_mean_interval,
)
from polisyos.foundry.methods.catalog.causal.ci_backends import (
    robust_standard_error as _ci_robust_standard_error,
)
from polisyos.foundry.methods.catalog.causal.nuisance_backends import (
    build_split_manifest,
    make_outcome_backends,
    make_propensity_backend,
    make_tau_backends,
)


@dataclasses.dataclass(frozen=True)
class NuisanceConfig:
    """Nuisance config data model."""

    nuisance_model_family: str = "competitive"
    crossfit_folds: int = 5
    n_repeats: int = 3
    random_seed: int = 42
    random_seed_manifest: tuple[int, ...] = ()
    propensity_clipping: float = 0.01
    propensity_trimming: float = 0.02
    overlap_trim: float = 0.02
    outcome_scaling: str = "auto"
    calibration_mode: str = "isotonic"
    inference_backend: str = "bootstrap_eif"
    bootstrap_draws: int = 500
    feature_importance_mode: str = "model_based"


@dataclasses.dataclass(frozen=True)
class OutcomeScaler:
    """Store affine outcome-scaling parameters shared by nuisance and target learners."""

    mean: float
    scale: float
    applied: bool
    policy: str = "auto"


@dataclasses.dataclass
class CrossFitNuisanceOutputs:
    """Carry fold-wise nuisance predictions, propensity scores, and split metadata."""

    propensity: np.ndarray
    mu1: np.ndarray
    mu0: np.ndarray
    trim_mask: np.ndarray
    scaler: OutcomeScaler
    config: NuisanceConfig
    split_manifest: tuple[tuple[tuple[np.ndarray, np.ndarray], ...], ...] | None = None
    backend_info: dict[str, Any] | None = None

    def effect_signal(self) -> np.ndarray:
        return self.mu1 - self.mu0

    def aipw_scores(self, outcome: np.ndarray, treatment: np.ndarray) -> np.ndarray:
        e = np.clip(
            self.propensity, self.config.propensity_clipping, 1.0 - self.config.propensity_clipping
        )
        return (
            self.effect_signal()
            + treatment * (outcome - self.mu1) / e
            - (1.0 - treatment) * (outcome - self.mu0) / (1.0 - e)
        )

    def diagnostics(self) -> dict[str, Any]:
        propensity = np.asarray(self.propensity, dtype=float).reshape(-1)
        clip = float(self.config.propensity_clipping)
        clipped = np.isclose(propensity, clip) | np.isclose(propensity, 1.0 - clip)
        weights = 1.0 / np.clip(propensity * (1.0 - propensity), clip, None)
        ess = float((np.sum(weights) ** 2) / max(np.sum(weights**2), 1e-12))
        hist_counts, hist_edges = np.histogram(
            propensity,
            bins=(0.0, 0.05, 0.1, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95, 1.0),
        )
        return {
            "clipping_fraction": float(np.mean(clipped)) if clipped.size else 0.0,
            "support_mismatch_fraction": float(np.mean(~self.trim_mask))
            if self.trim_mask.size
            else 0.0,
            "effective_sample_size": ess,
            "propensity_histogram": {
                "edges": [float(edge) for edge in hist_edges.tolist()],
                "counts": [int(count) for count in hist_counts.tolist()],
            },
            "overlap_histogram": {
                "edges": [float(edge) for edge in hist_edges.tolist()],
                "counts": [int(count) for count in hist_counts.tolist()],
            },
            "trim_threshold": max(
                float(self.config.propensity_clipping),
                float(self.config.propensity_trimming),
                float(self.config.overlap_trim),
            ),
            "outcome_scaler": {
                "mean": float(self.scaler.mean),
                "scale": float(self.scaler.scale),
                "applied": bool(self.scaler.applied),
                "policy": self.scaler.policy,
            },
            "backend_info": dict(self.backend_info or {}),
            "calibration_mode": self.config.calibration_mode,
            "split_manifest": _summarize_split_manifest(self.split_manifest),
            "propensity_summary": {
                "min": float(np.min(propensity)) if propensity.size else float("nan"),
                "max": float(np.max(propensity)) if propensity.size else float("nan"),
                "mean": float(np.mean(propensity)) if propensity.size else float("nan"),
                "std": float(np.std(propensity)) if propensity.size else float("nan"),
            },
        }


@dataclasses.dataclass
class TauFitResult:
    """Tau fit result data model."""

    cate_predictions: np.ndarray
    feature_importances: np.ndarray | None
    fitted_values: np.ndarray | None = None


def build_nuisance_config(params: dict[str, Any] | None = None) -> NuisanceConfig:
    """Build nuisance config."""
    raw = params or {}
    seed_manifest_raw = raw.get("random_seed_manifest")
    seed_manifest = (
        tuple(int(seed) for seed in seed_manifest_raw) if seed_manifest_raw is not None else ()
    )
    return NuisanceConfig(
        nuisance_model_family=str(raw.get("nuisance_model_family", "competitive")),
        crossfit_folds=max(2, int(raw.get("crossfit_folds", 5))),
        n_repeats=max(1, int(raw.get("n_repeats", 3))),
        random_seed=int(raw.get("random_seed", raw.get("seed", 42))),
        random_seed_manifest=seed_manifest,
        propensity_clipping=float(raw.get("propensity_clipping", 0.01)),
        propensity_trimming=float(raw.get("propensity_trimming", raw.get("overlap_trim", 0.02))),
        overlap_trim=float(raw.get("overlap_trim", 0.02)),
        outcome_scaling=str(raw.get("outcome_scaling", "auto")),
        calibration_mode=str(raw.get("calibration_mode", "isotonic")),
        inference_backend=str(raw.get("inference_backend", "bootstrap_eif")),
        bootstrap_draws=max(40, int(raw.get("bootstrap_draws", 500))),
        feature_importance_mode=str(raw.get("feature_importance_mode", "model_based")),
    )


def crossfit_nuisances(
    X: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    config: NuisanceConfig,
) -> CrossFitNuisanceOutputs:
    """Crossfit nuisances helper."""
    X = np.asarray(X, dtype=float)
    treatment = np.asarray(treatment, dtype=float).reshape(-1)
    outcome = np.asarray(outcome, dtype=float).reshape(-1)

    n_obs = outcome.shape[0]
    scaler = fit_outcome_scaler(outcome, config.outcome_scaling)
    scaled_outcome = scale_outcome(outcome, scaler)

    propensity_sum = np.zeros(n_obs, dtype=float)
    mu1_sum = np.zeros(n_obs, dtype=float)
    mu0_sum = np.zeros(n_obs, dtype=float)
    propensity_backend = make_propensity_backend(config.random_seed, config.nuisance_model_family)
    outcome_backend = make_outcome_backends(config.random_seed, config.nuisance_model_family)
    split_manifest, repeat_seeds = build_split_manifest(
        treatment,
        n_folds=config.crossfit_folds,
        n_repeats=config.n_repeats,
        base_seed=config.random_seed,
        seed_manifest=config.random_seed_manifest,
    )

    for repeat, rep_seed in enumerate(repeat_seeds):
        folds = split_manifest[repeat] if repeat < len(split_manifest) else tuple()
        for fold_id, (train_idx, test_idx) in enumerate(folds):
            fold_seed = rep_seed + 37 * (fold_id + 1)
            train_treatment = treatment[train_idx]
            train_mean_prop = float(
                np.clip(
                    np.mean(train_treatment),
                    config.propensity_clipping,
                    1.0 - config.propensity_clipping,
                )
            )
            try:
                propensity_sum[test_idx] += _fit_predict_propensity(
                    X,
                    treatment,
                    train_idx,
                    test_idx,
                    config.nuisance_model_family,
                    fold_seed,
                    config.propensity_clipping,
                    config.calibration_mode,
                )
            except Exception:
                propensity_sum[test_idx] += np.full(test_idx.size, train_mean_prop, dtype=float)

            treated_train = train_idx[treatment[train_idx] > 0.5]
            control_train = train_idx[treatment[train_idx] <= 0.5]
            mu1_sum[test_idx] += inverse_scale(
                _fit_predict_regression(
                    X,
                    scaled_outcome,
                    treated_train,
                    test_idx,
                    config.nuisance_model_family,
                    fold_seed + 11,
                ),
                scaler,
            )
            mu0_sum[test_idx] += inverse_scale(
                _fit_predict_regression(
                    X,
                    scaled_outcome,
                    control_train,
                    test_idx,
                    config.nuisance_model_family,
                    fold_seed + 29,
                ),
                scaler,
            )

    denom = float(config.n_repeats)
    propensity = propensity_sum / denom
    mu1 = mu1_sum / denom
    mu0 = mu0_sum / denom
    trim = max(config.overlap_trim, config.propensity_trimming, config.propensity_clipping)
    trim_mask = (propensity >= trim) & (propensity <= 1.0 - trim)
    if not np.any(trim_mask):
        trim_mask = np.ones(n_obs, dtype=bool)

    return CrossFitNuisanceOutputs(
        propensity=np.clip(
            propensity, config.propensity_clipping, 1.0 - config.propensity_clipping
        ),
        mu1=mu1,
        mu0=mu0,
        trim_mask=trim_mask,
        scaler=scaler,
        config=config,
        split_manifest=split_manifest,
        backend_info={
            "propensity_backend": propensity_backend.name,
            "outcome_backend": outcome_backend.name,
            "calibration_mode": config.calibration_mode,
        },
    )


def fit_dr_tau_model(
    X: np.ndarray,
    pseudo_outcome: np.ndarray,
    config: NuisanceConfig,
) -> TauFitResult:
    """Fit dr tau model helper."""
    return _fit_tau_model(
        X,
        target=np.asarray(pseudo_outcome, dtype=float),
        sample_weight=None,
        config=config,
        seed_offset=101,
    )


def fit_r_tau_model(
    X: np.ndarray,
    y_residual: np.ndarray,
    t_residual: np.ndarray,
    config: NuisanceConfig,
) -> TauFitResult:
    """Fit r tau model helper."""
    t_residual = np.asarray(t_residual, dtype=float)
    safe = np.abs(t_residual) >= 1e-3
    pseudo = np.zeros_like(t_residual)
    pseudo[safe] = np.asarray(y_residual, dtype=float)[safe] / t_residual[safe]
    weights = np.square(t_residual)
    weights = np.where(safe, np.maximum(weights, 1e-4), 0.0)
    return _fit_tau_model(
        X,
        target=pseudo,
        sample_weight=weights,
        config=config,
        seed_offset=211,
    )


def bootstrap_mean_interval(
    values: np.ndarray,
    *,
    seed: int,
    draws: int,
    influence_values: np.ndarray | None = None,
    backend: str = "bootstrap_eif",
) -> tuple[float, float]:
    """Bootstrap mean interval helper."""
    return _ci_bootstrap_mean_interval(
        values,
        seed=seed,
        draws=draws,
        influence_values=influence_values,
        backend=backend,
    )


def robust_standard_error(values: np.ndarray) -> float:
    """Robust standard error helper."""
    return _ci_robust_standard_error(values)


def fit_outcome_scaler(outcome: np.ndarray, policy: str) -> OutcomeScaler:
    """Fit outcome scaler helper."""
    arr = np.asarray(outcome, dtype=float).reshape(-1)
    mean = float(np.mean(arr))
    scale = float(np.std(arr))
    normalized_policy = policy.strip().lower()
    applied = normalized_policy in {"zscore", "standardized", "raw+standardized"} or (
        normalized_policy == "auto" and scale > 10.0
    )
    return OutcomeScaler(
        mean=mean, scale=max(scale, 1e-8), applied=applied, policy=normalized_policy
    )


def scale_outcome(outcome: np.ndarray, scaler: OutcomeScaler) -> np.ndarray:
    """Scale outcome helper."""
    arr = np.asarray(outcome, dtype=float)
    if not scaler.applied:
        return arr
    return (arr - scaler.mean) / scaler.scale


def inverse_scale(values: np.ndarray, scaler: OutcomeScaler) -> np.ndarray:
    """Inverse scale helper."""
    arr = np.asarray(values, dtype=float)
    if not scaler.applied:
        return arr
    return arr * scaler.scale + scaler.mean


def _fit_tau_model(
    X: np.ndarray,
    *,
    target: np.ndarray,
    sample_weight: np.ndarray | None,
    config: NuisanceConfig,
    seed_offset: int,
) -> TauFitResult:
    X = np.asarray(X, dtype=float)
    target = np.asarray(target, dtype=float).reshape(-1)
    pred_sum = np.zeros(X.shape[0], dtype=float)
    fi_sum = np.zeros(X.shape[1], dtype=float)
    fi_count = 0
    active_weight_mask = None
    if sample_weight is not None:
        sample_weight = np.asarray(sample_weight, dtype=float).reshape(-1)
        active_weight_mask = sample_weight > 0
    for repeat in range(config.n_repeats):
        seed = config.random_seed + seed_offset + 101 * repeat
        models = make_tau_backends(seed, config.nuisance_model_family)
        local_preds: list[np.ndarray] = []
        local_fis: list[np.ndarray] = []
        for model in models:
            try:
                if active_weight_mask is not None and np.any(active_weight_mask):
                    model.fit(
                        X[active_weight_mask],
                        target[active_weight_mask],
                        sample_weight=sample_weight[active_weight_mask],
                    )
                else:
                    model.fit(X, target)
                local_preds.append(_predict_regression(model, X))
                feature_imp = _extract_feature_importances(
                    model,
                    X.shape[1],
                    X=X[active_weight_mask]
                    if active_weight_mask is not None and np.any(active_weight_mask)
                    else X,
                    y=target[active_weight_mask]
                    if active_weight_mask is not None and np.any(active_weight_mask)
                    else target,
                    sample_weight=sample_weight[active_weight_mask]
                    if active_weight_mask is not None and np.any(active_weight_mask)
                    else sample_weight,
                    mode=config.feature_importance_mode,
                    seed=seed + len(local_fis),
                )
                if feature_imp is not None:
                    local_fis.append(feature_imp)
            except Exception:
                continue
        if local_preds:
            pred_sum += np.mean(np.vstack(local_preds), axis=0)
        if local_fis:
            fi_sum += np.mean(np.vstack(local_fis), axis=0)
            fi_count += 1
    cate_predictions = pred_sum / float(config.n_repeats)
    feature_importances = None
    if fi_count > 0:
        feature_importances = fi_sum / float(fi_count)
        total = float(np.sum(feature_importances))
        if total > 0:
            feature_importances = feature_importances / total
    return TauFitResult(cate_predictions=cate_predictions, feature_importances=feature_importances)


def _make_propensity_model(family: str, seed: int) -> Any:
    selection = make_propensity_backend(seed, family)
    return selection.model


def _make_outcome_model(family: str, seed: int) -> Any:
    selection = make_outcome_backends(seed, family)
    return selection.model


def _fit_predict_propensity(
    X: np.ndarray,
    treatment: np.ndarray,
    train_idx: np.ndarray,
    test_idx: np.ndarray,
    family: str,
    seed: int,
    clip: float,
    calibration_mode: str,
) -> np.ndarray:
    family = family.strip().lower()
    selection = make_propensity_backend(seed, family)
    try:
        calibrated_pred, _calibration = make_calibrated_propensity_prediction(
            X,
            treatment,
            train_idx=train_idx,
            test_idx=test_idx,
            base_model=selection.model,
            stabilizer_model=selection.stabilizer,
            calibration_mode=calibration_mode,
            clip=clip,
            seed=seed,
        )
        return calibrated_pred
    except Exception:
        mean_prop = float(np.clip(np.mean(treatment[train_idx]), clip, 1.0 - clip))
        return np.full(test_idx.size, mean_prop, dtype=float)


def _fit_predict_regression(
    X: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    test_idx: np.ndarray,
    family: str,
    seed: int,
) -> np.ndarray:
    if train_idx.size < 8:
        return np.full(test_idx.size, float(np.mean(y)) if y.size else 0.0, dtype=float)
    selection = make_outcome_backends(seed, family)
    models = [selection.model]
    if selection.stabilizer is not None:
        models.append(selection.stabilizer)
    preds: list[np.ndarray] = []
    for model in models:
        try:
            model.fit(X[train_idx], y[train_idx])
            preds.append(_predict_regression(model, X[test_idx]))
        except Exception:
            continue
    if preds:
        return np.mean(np.vstack(preds), axis=0)
    return np.full(
        test_idx.size, float(np.mean(y[train_idx])) if train_idx.size else 0.0, dtype=float
    )


def _predict_regression(model: Any, X: np.ndarray) -> np.ndarray:
    pred = model.predict(X)
    return np.asarray(pred, dtype=float).reshape(-1)


def _extract_feature_importances(
    model: Any,
    n_features: int,
    *,
    X: np.ndarray | None = None,
    y: np.ndarray | None = None,
    sample_weight: np.ndarray | None = None,
    mode: str = "model_based",
    seed: int = 0,
) -> np.ndarray | None:
    normalized_mode = mode.strip().lower()
    if normalized_mode == "permutation" and X is not None and y is not None:
        perm = _permutation_feature_importances(
            model,
            X,
            y,
            sample_weight=sample_weight,
            seed=seed,
        )
        if perm is not None:
            return perm
    raw = getattr(model, "feature_importances_", None)
    if raw is None:
        raw = getattr(model, "coef_", None)
    if raw is None:
        return None
    arr = np.asarray(raw, dtype=float).reshape(-1)
    if arr.size == n_features + 1:
        arr = arr[1:]
    if arr.size != n_features:
        return None
    arr = np.abs(arr)
    total = float(np.sum(arr))
    if total <= 0:
        return None
    return arr / total


def _permutation_feature_importances(
    model: Any,
    X: np.ndarray,
    y: np.ndarray,
    *,
    sample_weight: np.ndarray | None,
    seed: int,
) -> np.ndarray | None:
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float).reshape(-1)
    if X.ndim != 2 or X.shape[1] == 0 or X.shape[0] != y.shape[0]:
        return None

    rng = np.random.default_rng(seed)
    if X.shape[0] > 256:
        subset = np.sort(rng.choice(X.shape[0], size=256, replace=False))
        X_eval = X[subset]
        y_eval = y[subset]
        weight_eval = (
            None
            if sample_weight is None
            else np.asarray(sample_weight, dtype=float).reshape(-1)[subset]
        )
    else:
        X_eval = X
        y_eval = y
        weight_eval = (
            None if sample_weight is None else np.asarray(sample_weight, dtype=float).reshape(-1)
        )

    try:
        baseline_pred = _predict_regression(model, X_eval)
    except Exception:
        return None
    baseline_loss = _weighted_mse(y_eval, baseline_pred, weight_eval)
    if not np.isfinite(baseline_loss):
        return None

    importances = np.zeros(X_eval.shape[1], dtype=float)
    for column_idx in range(X_eval.shape[1]):
        X_permuted = np.array(X_eval, copy=True)
        X_permuted[:, column_idx] = X_permuted[rng.permutation(X_permuted.shape[0]), column_idx]
        try:
            permuted_pred = _predict_regression(model, X_permuted)
        except Exception:
            continue
        importances[column_idx] = max(
            0.0, _weighted_mse(y_eval, permuted_pred, weight_eval) - baseline_loss
        )

    total = float(np.sum(importances))
    if total <= 0:
        return None
    return importances / total


def _weighted_mse(
    y_true: np.ndarray, y_pred: np.ndarray, sample_weight: np.ndarray | None
) -> float:
    residual = np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float)
    squared = residual**2
    if sample_weight is None:
        return float(np.mean(squared))
    weights = np.asarray(sample_weight, dtype=float).reshape(-1)
    weights = np.maximum(weights, 0.0)
    if np.sum(weights) <= 0:
        return float(np.mean(squared))
    return float(np.average(squared, weights=weights))


def _summarize_split_manifest(
    split_manifest: tuple[tuple[tuple[np.ndarray, np.ndarray], ...], ...] | None,
) -> dict[str, Any]:
    if not split_manifest:
        return {"n_repeats": 0, "n_folds": 0, "repeat_summaries": []}
    repeat_summaries: list[dict[str, Any]] = []
    for repeat_idx, folds in enumerate(split_manifest):
        fold_summaries: list[dict[str, int]] = []
        for train_idx, test_idx in folds:
            fold_summaries.append(
                {
                    "train_size": int(np.asarray(train_idx).size),
                    "test_size": int(np.asarray(test_idx).size),
                }
            )
        repeat_summaries.append(
            {
                "repeat_index": repeat_idx,
                "n_folds": len(folds),
                "folds": fold_summaries,
            }
        )
    return {
        "n_repeats": len(split_manifest),
        "n_folds": len(split_manifest[0]) if split_manifest else 0,
        "repeat_summaries": repeat_summaries,
    }


__all__ = [
    "CrossFitNuisanceOutputs",
    "NuisanceConfig",
    "OutcomeScaler",
    "TauFitResult",
    "bootstrap_mean_interval",
    "build_nuisance_config",
    "crossfit_nuisances",
    "fit_dr_tau_model",
    "fit_outcome_scaler",
    "fit_r_tau_model",
    "inverse_scale",
    "robust_standard_error",
    "scale_outcome",
]
