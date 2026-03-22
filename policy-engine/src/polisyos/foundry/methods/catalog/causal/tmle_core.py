from __future__ import annotations

import hashlib
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

import numpy as np

from polisyos.foundry.methods.catalog.causal._sklearn_compat import (
    LinearRegression as CompatLinearRegression,
    LogisticRegression as CompatLogisticRegression,
    SKLEARN_AVAILABLE,
)
from polisyos.foundry.methods.catalog.causal.nuisance_layer import (
    bootstrap_mean_interval,
    build_nuisance_config,
    fit_outcome_scaler,
    inverse_scale,
    robust_standard_error,
    scale_outcome,
)

try:  # pragma: no cover - optional dependency
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import (
        GradientBoostingClassifier,
        GradientBoostingRegressor,
        HistGradientBoostingClassifier,
        HistGradientBoostingRegressor,
        RandomForestClassifier,
        RandomForestRegressor,
    )
    from sklearn.linear_model import ElasticNet, LogisticRegression as SklearnLogisticRegression

    SKLEARN_EXTENDED_AVAILABLE = True
except Exception:  # pragma: no cover - fallback covered by tests
    CalibratedClassifierCV = None
    GradientBoostingClassifier = None
    GradientBoostingRegressor = None
    HistGradientBoostingClassifier = None
    HistGradientBoostingRegressor = None
    RandomForestClassifier = None
    RandomForestRegressor = None
    ElasticNet = None
    SklearnLogisticRegression = None
    SKLEARN_EXTENDED_AVAILABLE = False


@dataclass(frozen=True)
class ATENuisanceContract:
    nuisance_model_family: str = "competitive"
    propensity_backend: str = "lightgbm"
    propensity_backend_candidates: tuple[str, ...] = ()
    outcome_backend: str = "lightgbm"
    outcome_backend_candidates: tuple[str, ...] = ()
    backend_selection_policy: str = "causal_risk"
    selection_objective: str = "causal_risk"
    calibration_mode: str = "isotonic"
    crossfit_folds: int = 5
    n_repeats: int = 3
    random_seed: int = 42
    random_seed_manifest: tuple[int, ...] = ()
    propensity_clipping: float = 0.01
    propensity_trimming: float = 0.02
    outcome_scaling: str = "raw+standardized"
    inference_backend: str = "bootstrap_eif"
    bootstrap_draws: int = 500
    feature_importance_mode: str = "model_based"
    calibration_fraction: float = 0.2
    min_calibration_size: int = 24
    min_effective_sample_size: float = 48.0
    ci_mode: str = "auto"
    coverage_guard: str = "ess_aware"
    overlap_diagnostic_policy: str = "ntv_proxy+ess"
    weak_overlap_mode: str = "diagnostic_only"
    overlap_guard: float = 0.10
    parallel_folds: bool = True
    max_parallel_folds: int = 0
    max_targeting_iter: int = 3
    targeting_step_limit: float = 5.0

    @classmethod
    def from_params(cls, params: Mapping[str, Any] | None) -> "ATENuisanceContract":
        raw = dict(params or {})
        base = build_nuisance_config(raw)
        seed_manifest_raw = raw.get("random_seed_manifest")
        seed_manifest = tuple(int(seed) for seed in seed_manifest_raw) if seed_manifest_raw is not None else ()
        propensity_backend_candidates = _as_backend_candidates(raw.get("propensity_backend_candidates"))
        outcome_backend_candidates = _as_backend_candidates(raw.get("outcome_backend_candidates"))
        return cls(
            nuisance_model_family=base.nuisance_model_family,
            propensity_backend=str(raw.get("propensity_backend", "lightgbm")),
            propensity_backend_candidates=propensity_backend_candidates,
            outcome_backend=str(raw.get("outcome_backend", "lightgbm")),
            outcome_backend_candidates=outcome_backend_candidates,
            backend_selection_policy=str(raw.get("backend_selection_policy", "causal_risk")),
            selection_objective=str(raw.get("selection_objective", "causal_risk")),
            calibration_mode=str(raw.get("calibration_mode", "isotonic")),
            crossfit_folds=base.crossfit_folds,
            n_repeats=base.n_repeats,
            random_seed=base.random_seed,
            random_seed_manifest=seed_manifest,
            propensity_clipping=base.propensity_clipping,
            propensity_trimming=base.propensity_trimming,
            outcome_scaling=base.outcome_scaling,
            inference_backend=base.inference_backend,
            bootstrap_draws=base.bootstrap_draws,
            feature_importance_mode=base.feature_importance_mode,
            calibration_fraction=float(raw.get("calibration_fraction", 0.2)),
            min_calibration_size=max(0, int(raw.get("min_calibration_size", 24))),
            min_effective_sample_size=float(raw.get("min_effective_sample_size", 48.0)),
            ci_mode=str(raw.get("ci_mode", "auto")),
            coverage_guard=str(raw.get("coverage_guard", "ess_aware")),
            overlap_diagnostic_policy=str(raw.get("overlap_diagnostic_policy", "ntv_proxy+ess")),
            weak_overlap_mode=str(raw.get("weak_overlap_mode", "diagnostic_only")),
            overlap_guard=float(raw.get("overlap_guard", 0.10)),
            parallel_folds=bool(raw.get("parallel_folds", True)),
            max_parallel_folds=max(0, int(raw.get("max_parallel_folds", 0))),
            max_targeting_iter=max(1, int(raw.get("max_targeting_iter", 3))),
            targeting_step_limit=float(raw.get("targeting_step_limit", 5.0)),
        )

    def as_legacy_config(self) -> dict[str, Any]:
        return {
            "nuisance_model_family": self.nuisance_model_family,
            "crossfit_folds": self.crossfit_folds,
            "n_repeats": self.n_repeats,
            "propensity_backend": self.propensity_backend,
            "propensity_backend_candidates": list(self.propensity_backend_candidates),
            "outcome_backend": self.outcome_backend,
            "outcome_backend_candidates": list(self.outcome_backend_candidates),
            "backend_selection_policy": self.backend_selection_policy,
            "selection_objective": self.selection_objective,
            "calibration_mode": self.calibration_mode,
            "calibration_fraction": self.calibration_fraction,
            "min_calibration_size": self.min_calibration_size,
            "min_effective_sample_size": self.min_effective_sample_size,
            "random_seed_manifest": list(self.random_seed_manifest),
            "propensity_clipping": self.propensity_clipping,
            "propensity_trimming": self.propensity_trimming,
            "ci_mode": self.ci_mode,
            "coverage_guard": self.coverage_guard,
            "overlap_diagnostic_policy": self.overlap_diagnostic_policy,
            "weak_overlap_mode": self.weak_overlap_mode,
            "overlap_guard": self.overlap_guard,
            "parallel_folds": self.parallel_folds,
            "max_parallel_folds": self.max_parallel_folds,
            "outcome_scaling": self.outcome_scaling,
            "inference_backend": self.inference_backend,
            "bootstrap_draws": self.bootstrap_draws,
            "feature_importance_mode": self.feature_importance_mode,
        }

    def as_contract_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["random_seed_manifest"] = list(self.random_seed_manifest)
        return payload


@dataclass
class ATENuisanceBundle:
    propensity: np.ndarray
    mu1: np.ndarray
    mu0: np.ndarray
    trim_mask: np.ndarray
    scaler: Any
    contract: ATENuisanceContract
    split_manifest: list[dict[str, Any]] = field(default_factory=list)
    calibration_modes: list[str] = field(default_factory=list)
    propensity_backends: list[str] = field(default_factory=list)
    outcome_backends: list[str] = field(default_factory=list)
    selection_manifest: list[dict[str, Any]] = field(default_factory=list)

    def effect_signal(self) -> np.ndarray:
        return self.mu1 - self.mu0

    def diagnostics(self) -> dict[str, Any]:
        propensity = np.asarray(self.propensity, dtype=float).reshape(-1)
        clip = float(self.contract.propensity_clipping)
        clipped = np.isclose(propensity, clip) | np.isclose(propensity, 1.0 - clip)
        weights = 1.0 / np.clip(propensity * (1.0 - propensity), clip, None)
        effective_sample_size = float((np.sum(weights) ** 2) / max(np.sum(weights**2), 1e-12))
        hist_counts, hist_edges = np.histogram(
            propensity,
            bins=(0.0, 0.05, 0.1, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95, 1.0),
        )
        effect_scale = max(float(abs(np.mean(self.effect_signal()))), 0.25)
        overlap_ntv = float(np.clip(np.mean(np.abs(propensity - 0.5) / 0.5), 0.0, 1.0))
        clipping_fraction = float(np.mean(clipped)) if clipped.size else 0.0
        support_mismatch_fraction = float(np.mean(~self.trim_mask)) if self.trim_mask.size else 0.0
        coverage_guard_triggered = _coverage_guard_triggered(
            diagnostics={
                "effective_sample_size": effective_sample_size,
                "clipping_fraction": clipping_fraction,
                "support_mismatch_fraction": support_mismatch_fraction,
                "overlap_ntv": overlap_ntv,
            },
            contract=self.contract,
        )
        diagnostics = {
            "clipping_fraction": clipping_fraction,
            "support_mismatch_fraction": support_mismatch_fraction,
            "effective_sample_size": effective_sample_size,
            "propensity_histogram": {
                "edges": [float(edge) for edge in hist_edges.tolist()],
                "counts": [int(count) for count in hist_counts.tolist()],
            },
            "trim_threshold": max(
                float(self.contract.propensity_clipping),
                float(self.contract.propensity_trimming),
            ),
            "outcome_scaler": {
                "mean": float(self.scaler.mean),
                "scale": float(self.scaler.scale),
                "applied": bool(self.scaler.applied),
            },
            "calibration_modes": list(self.calibration_modes),
            "propensity_backends": list(self.propensity_backends),
            "outcome_backends": list(self.outcome_backends),
            "split_manifest": list(self.split_manifest),
            "selection_manifest": list(self.selection_manifest),
            "effect_scale": effect_scale,
            "overlap_ntv": overlap_ntv,
            "overlap_ntv_guard_threshold": _coverage_guard_ntv_threshold(self.contract),
            "min_effective_sample_size": float(self.contract.min_effective_sample_size),
            "coverage_guard": self.contract.coverage_guard,
            "coverage_guard_triggered": coverage_guard_triggered,
        }
        return diagnostics


@dataclass
class ATEFitResult:
    ate: float
    standard_error: float
    ci_lower: float
    ci_upper: float
    interval_method: str
    eif_mean: float
    eif_standard_deviation: float
    eif_values: np.ndarray
    nuisance_bundle: ATENuisanceBundle
    targeting_summary: dict[str, Any] | None = None

    @property
    def effect_scale(self) -> float:
        return max(float(abs(self.ate)), 0.25)


_SHARED_NUISANCE_CACHE: dict[str, ATENuisanceBundle] = {}
_SHARED_NUISANCE_CACHE_ORDER: list[str] = []
_SHARED_NUISANCE_CACHE_MAX = 64
_SHARED_NUISANCE_LOCK = threading.RLock()


def _as_backend_candidates(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        values = [item.strip() for item in raw.split(",") if item.strip()]
        return tuple(values)
    if isinstance(raw, (list, tuple, set)):
        return tuple(str(item).strip() for item in raw if str(item).strip())
    return ()


def _candidate_names(primary: str, extras: tuple[str, ...]) -> list[str]:
    names: list[str] = []
    for item in (primary, *extras):
        name = str(item).strip().lower()
        if name and name not in names:
            names.append(name)
    return names


def _instantiate_propensity_model(backend_name: str, *, seed: int) -> tuple[Any, str]:
    key = backend_name.strip().lower()
    if key in {"lightgbm", "lgbm"}:
        try:  # pragma: no cover - optional dependency
            import lightgbm as lgb  # type: ignore[import]

            return (
                lgb.LGBMClassifier(
                    n_estimators=160,
                    learning_rate=0.05,
                    num_leaves=31,
                    min_child_samples=10,
                    subsample=0.85,
                    colsample_bytree=0.85,
                    random_state=seed,
                    n_jobs=1,
                ),
                "lightgbm",
            )
        except Exception:
            key = "histgradientboosting"
    if key in {"histgradientboosting", "histgb"} and SKLEARN_EXTENDED_AVAILABLE:
        return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, random_state=seed), "histgradientboosting"
    if key in {"gradient_boosting", "gbm"} and SKLEARN_EXTENDED_AVAILABLE and GradientBoostingClassifier is not None:
        return GradientBoostingClassifier(random_state=seed), "gradient_boosting"
    if key in {"random_forest", "rf"} and SKLEARN_EXTENDED_AVAILABLE and RandomForestClassifier is not None:
        return RandomForestClassifier(n_estimators=200, random_state=seed, n_jobs=1), "random_forest"
    if key in {"logistic_regression", "logistic"} and SKLEARN_AVAILABLE:
        if SklearnLogisticRegression is not None:
            return SklearnLogisticRegression(max_iter=1000, solver="lbfgs"), "logistic_regression"
        return CompatLogisticRegression(max_iter=500), "compat_logistic_regression"
    return CompatLogisticRegression(max_iter=500), "compat_logistic_regression"


def _instantiate_regression_model(backend_name: str, *, seed: int) -> tuple[Any, str]:
    key = backend_name.strip().lower()
    if key in {"lightgbm", "lgbm"}:
        try:  # pragma: no cover - optional dependency
            import lightgbm as lgb  # type: ignore[import]

            return (
                lgb.LGBMRegressor(
                    n_estimators=180,
                    learning_rate=0.05,
                    num_leaves=31,
                    min_child_samples=10,
                    subsample=0.85,
                    colsample_bytree=0.85,
                    random_state=seed,
                    n_jobs=1,
                ),
                "lightgbm",
            )
        except Exception:
            key = "histgradientboosting"
    if key in {"histgradientboosting", "histgb"} and SKLEARN_EXTENDED_AVAILABLE:
        return HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, random_state=seed), "histgradientboosting"
    if key in {"elastic_net", "elasticnet"} and SKLEARN_EXTENDED_AVAILABLE and ElasticNet is not None:
        return ElasticNet(alpha=0.01, l1_ratio=0.5, max_iter=3000, random_state=seed), "elastic_net"
    if key in {"random_forest", "rf"} and SKLEARN_EXTENDED_AVAILABLE and RandomForestRegressor is not None:
        return RandomForestRegressor(n_estimators=200, random_state=seed, n_jobs=1), "random_forest"
    if key in {"gradient_boosting", "gbm"} and SKLEARN_EXTENDED_AVAILABLE and GradientBoostingRegressor is not None:
        return GradientBoostingRegressor(random_state=seed), "gradient_boosting"
    return CompatLinearRegression(), "compat_linear_regression"


def _base_probability(model: Any, X: np.ndarray, *, clip: float) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    if hasattr(model, "predict_proba"):
        proba = np.asarray(model.predict_proba(X), dtype=float)
        if proba.ndim == 2 and proba.shape[1] >= 2:
            return np.clip(proba[:, 1], clip, 1.0 - clip)
    if hasattr(model, "decision_function"):
        score = np.asarray(model.decision_function(X), dtype=float).reshape(-1)
        return np.clip(1.0 / (1.0 + np.exp(-score)), clip, 1.0 - clip)
    pred = np.asarray(model.predict(X), dtype=float).reshape(-1)
    return np.clip(pred, clip, 1.0 - clip)


def _propensity_score_loss(
    target: np.ndarray,
    pred: np.ndarray,
    *,
    clip: float,
) -> float:
    safe_pred = np.clip(np.asarray(pred, dtype=float).reshape(-1), clip, 1.0 - clip)
    truth = np.asarray(target, dtype=float).reshape(-1)
    brier = float(np.mean((truth - safe_pred) ** 2))
    overlap_ntv = float(np.clip(np.mean(np.abs(safe_pred - 0.5) / 0.5), 0.0, 1.0))
    return brier + 0.05 * overlap_ntv


def _regression_score_loss(
    target: np.ndarray,
    pred: np.ndarray,
) -> float:
    truth = np.asarray(target, dtype=float).reshape(-1)
    guess = np.asarray(pred, dtype=float).reshape(-1)
    if truth.size == 0 or guess.size == 0 or truth.size != guess.size:
        return float("inf")
    return float(np.mean((truth - guess) ** 2))


def _fit_propensity_backend(
    X: np.ndarray,
    T: np.ndarray,
    train_idx: np.ndarray,
    calib_idx: np.ndarray,
    test_idx: np.ndarray,
    contract: ATENuisanceContract,
    *,
    seed: int,
) -> tuple[np.ndarray, str, str, dict[str, Any]]:
    X = np.asarray(X, dtype=float)
    T = np.asarray(T, dtype=float).reshape(-1)
    backend_name = contract.propensity_backend.strip().lower()
    calibration_mode = contract.calibration_mode.strip().lower()

    train_idx = np.asarray(train_idx, dtype=int)
    calib_idx = np.asarray(calib_idx, dtype=int)
    test_idx = np.asarray(test_idx, dtype=int)
    candidate_names = _candidate_names(backend_name, contract.propensity_backend_candidates)
    selection_record = {
        "selection_objective": contract.selection_objective,
        "split_policy": contract.overlap_diagnostic_policy,
        "tested_propensity_backends": list(candidate_names),
        "tested_outcome_backends": [],
        "selected_propensity_backend": None,
        "selected_outcome_backend": None,
        "calibration_modes": [],
    }

    calibration_applied = False
    min_calibration_size = max(0, int(contract.min_calibration_size))
    if np.unique(T[train_idx]).size < 2:
        propensity = np.full(test_idx.size, float(np.clip(np.mean(T[train_idx]), contract.propensity_clipping, 1.0 - contract.propensity_clipping)))
        selection_record["selected_propensity_backend"] = "constant"
        selection_record["calibration_modes"] = ["none"]
        return propensity, "constant", "none", selection_record

    best_score = float("inf")
    best_payload: tuple[np.ndarray, str, str] | None = None
    for candidate_name in candidate_names:
        try:
            model, backend_used = _instantiate_propensity_model(candidate_name, seed=seed)
        except Exception:
            continue
        try:
            model.fit(X[train_idx], T[train_idx])
        except Exception:
            continue

        raw_calib = _base_probability(model, X[calib_idx if calib_idx.size else train_idx], clip=contract.propensity_clipping)
        raw_test = _base_probability(model, X[test_idx], clip=contract.propensity_clipping)
        calibration_used = "none"
        if (
            calibration_mode not in {"none", "uncalibrated"}
            and calib_idx.size >= min_calibration_size
            and np.unique(T[calib_idx]).size >= 2
            and CalibratedClassifierCV is not None
        ):
            candidate_modes = ("sigmoid",) if calibration_mode == "sigmoid" else ("isotonic", "sigmoid")
            for candidate_mode in candidate_modes:
                try:
                    calibrator = CalibratedClassifierCV(model, method=candidate_mode, cv="prefit")
                    calibrator.fit(X[calib_idx], T[calib_idx])
                    raw_test = np.asarray(calibrator.predict_proba(X[test_idx])[:, 1], dtype=float)
                    raw_calib = np.asarray(calibrator.predict_proba(X[calib_idx])[:, 1], dtype=float)
                    calibration_applied = True
                    calibration_used = candidate_mode
                    break
                except Exception:
                    calibration_applied = False

        score_idx = calib_idx if calib_idx.size else train_idx
        score_target = T[score_idx]
        score_pred = raw_calib if calib_idx.size else _base_probability(model, X[train_idx], clip=contract.propensity_clipping)
        score = _propensity_score_loss(score_target, score_pred, clip=contract.propensity_clipping)
        selection_record["calibration_modes"].append(calibration_used)
        if score < best_score:
            best_score = score
            best_payload = (
                np.clip(raw_test, contract.propensity_clipping, 1.0 - contract.propensity_clipping),
                backend_used,
                calibration_used,
            )
    if best_payload is None:
        propensity = np.full(test_idx.size, float(np.clip(np.mean(T[train_idx]), contract.propensity_clipping, 1.0 - contract.propensity_clipping)))
        selection_record["selected_propensity_backend"] = "constant"
        selection_record["calibration_modes"] = ["none"]
        return propensity, "constant", "none", selection_record
    raw, backend_used, calibration_used = best_payload
    selection_record["selected_propensity_backend"] = backend_used
    return raw, backend_used, calibration_used, selection_record


def _fit_regression_backend(
    X: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    test_idx: np.ndarray,
    contract: ATENuisanceContract,
    *,
    seed: int,
) -> tuple[np.ndarray, str, dict[str, Any]]:
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float).reshape(-1)
    train_idx = np.asarray(train_idx, dtype=int)
    test_idx = np.asarray(test_idx, dtype=int)

    backend_name = contract.outcome_backend.strip().lower()
    candidate_names = _candidate_names(backend_name, contract.outcome_backend_candidates)
    selection_record = {
        "selection_objective": contract.selection_objective,
        "split_policy": contract.overlap_diagnostic_policy,
        "tested_propensity_backends": [],
        "tested_outcome_backends": list(candidate_names),
        "selected_propensity_backend": None,
        "selected_outcome_backend": None,
        "calibration_modes": [],
    }

    if train_idx.size < 3 or np.unique(train_idx).size < 3:
        mean_value = float(np.mean(y[train_idx])) if train_idx.size else float(np.mean(y))
        selection_record["selected_outcome_backend"] = "constant"
        return np.full(test_idx.size, mean_value, dtype=float), "constant", selection_record

    val_size = max(1, int(round(0.2 * train_idx.size)))
    val_size = min(val_size, max(train_idx.size - 2, 1))
    rng = np.random.default_rng(seed + 701)
    shuffled = np.array(train_idx, copy=True)
    rng.shuffle(shuffled)
    val_idx = np.sort(shuffled[:val_size])
    fit_idx = np.sort(shuffled[val_size:]) if val_size < shuffled.size else np.sort(shuffled)
    if fit_idx.size < 2:
        fit_idx = np.asarray(train_idx, dtype=int)
        val_idx = np.asarray(train_idx, dtype=int)

    best_score = float("inf")
    best_payload: tuple[np.ndarray, str] | None = None
    for candidate_name in candidate_names:
        try:
            model, backend_used = _instantiate_regression_model(candidate_name, seed=seed)
            model.fit(X[fit_idx], y[fit_idx])
            score_pred = np.asarray(model.predict(X[val_idx]), dtype=float)
            score = _regression_score_loss(y[val_idx], score_pred)
            preds = np.asarray(model.predict(X[test_idx]), dtype=float)
        except Exception:
            continue
        if score < best_score:
            best_score = score
            best_payload = (preds, backend_used)

    if best_payload is None:
        mean_value = float(np.mean(y[train_idx]))
        selection_record["selected_outcome_backend"] = "constant"
        return np.full(test_idx.size, mean_value, dtype=float), "constant", selection_record

    preds, backend_used = best_payload
    selection_record["selected_outcome_backend"] = backend_used
    return preds, backend_used, selection_record


def _make_split_manifest(treatment: np.ndarray, contract: ATENuisanceContract) -> list[dict[str, Any]]:
    treatment = np.asarray(treatment, dtype=float).reshape(-1)
    n_obs = treatment.size
    if contract.random_seed_manifest:
        repeat_seeds = list(contract.random_seed_manifest)[: contract.n_repeats]
        if len(repeat_seeds) < contract.n_repeats:
            start = repeat_seeds[-1] if repeat_seeds else contract.random_seed
            repeat_seeds.extend(start + 997 * (idx + 1) for idx in range(contract.n_repeats - len(repeat_seeds)))
    else:
        repeat_seeds = [contract.random_seed + 997 * repeat for repeat in range(contract.n_repeats)]

    idx_all = np.arange(n_obs)
    split_manifest: list[dict[str, Any]] = []
    for repeat, rep_seed in enumerate(repeat_seeds):
        repeat_rng = np.random.default_rng(rep_seed)
        treated_idx = idx_all[treatment > 0.5]
        control_idx = idx_all[treatment <= 0.5]
        repeat_rng.shuffle(treated_idx)
        repeat_rng.shuffle(control_idx)
        treated_folds = np.array_split(treated_idx, contract.crossfit_folds)
        control_folds = np.array_split(control_idx, contract.crossfit_folds)
        folds: list[dict[str, Any]] = []
        for fold_id in range(contract.crossfit_folds):
            test_idx = np.sort(np.concatenate([treated_folds[fold_id], control_folds[fold_id]]))
            train_idx = np.setdiff1d(idx_all, test_idx, assume_unique=False)
            folds.append(
                {
                    "fold": fold_id,
                    "train_size": int(train_idx.size),
                    "test_size": int(test_idx.size),
                }
            )
        split_manifest.append({"repeat": repeat, "seed": int(rep_seed), "folds": folds})
    return split_manifest


def _hash_array(arr: np.ndarray) -> str:
    payload = np.ascontiguousarray(np.asarray(arr))
    digest = hashlib.blake2b(digest_size=16)
    digest.update(str(payload.dtype).encode("utf-8"))
    digest.update(np.asarray(payload.shape, dtype=np.int64).tobytes())
    digest.update(payload.tobytes())
    return digest.hexdigest()


def _contract_fingerprint(contract: ATENuisanceContract) -> str:
    return repr(
        (
            contract.nuisance_model_family,
            contract.propensity_backend,
            contract.propensity_backend_candidates,
            contract.outcome_backend,
            contract.outcome_backend_candidates,
            contract.selection_objective,
            contract.calibration_mode,
            contract.crossfit_folds,
            contract.n_repeats,
            contract.random_seed,
            contract.random_seed_manifest,
            contract.propensity_clipping,
            contract.propensity_trimming,
            contract.outcome_scaling,
            contract.calibration_fraction,
            contract.min_calibration_size,
        )
    )


def _shared_nuisance_cache_key(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    contract: ATENuisanceContract,
    params: Mapping[str, Any] | None = None,
) -> str | None:
    if params is not None and params.get("__disable_shared_nuisance_cache"):
        return None
    explicit = None if params is None else params.get("__shared_nuisance_key")
    signature = _contract_fingerprint(contract)
    if explicit is not None:
        return f"explicit::{explicit!s}::{signature}"
    return "::".join(
        [
            "auto",
            _hash_array(np.asarray(X, dtype=float)),
            _hash_array(np.asarray(T, dtype=float)),
            _hash_array(np.asarray(Y, dtype=float)),
            signature,
        ]
    )


def _cache_get(key: str | None) -> ATENuisanceBundle | None:
    if key is None:
        return None
    with _SHARED_NUISANCE_LOCK:
        cached = _SHARED_NUISANCE_CACHE.get(key)
        if cached is not None:
            if key in _SHARED_NUISANCE_CACHE_ORDER:
                _SHARED_NUISANCE_CACHE_ORDER.remove(key)
            _SHARED_NUISANCE_CACHE_ORDER.append(key)
        return cached


def _cache_put(key: str | None, bundle: ATENuisanceBundle) -> None:
    if key is None:
        return
    with _SHARED_NUISANCE_LOCK:
        _SHARED_NUISANCE_CACHE[key] = bundle
        if key in _SHARED_NUISANCE_CACHE_ORDER:
            _SHARED_NUISANCE_CACHE_ORDER.remove(key)
        _SHARED_NUISANCE_CACHE_ORDER.append(key)
        while len(_SHARED_NUISANCE_CACHE_ORDER) > _SHARED_NUISANCE_CACHE_MAX:
            evicted = _SHARED_NUISANCE_CACHE_ORDER.pop(0)
            _SHARED_NUISANCE_CACHE.pop(evicted, None)


def _fit_crossfit_fold(
    *,
    X: np.ndarray,
    T: np.ndarray,
    Y_scaled: np.ndarray,
    scaler: Any,
    contract: ATENuisanceContract,
    rep_seed: int,
    fold_id: int,
    fit_idx: np.ndarray,
    calib_idx: np.ndarray,
    test_idx: np.ndarray,
) -> dict[str, Any]:
    propensity, prop_backend, calibration_mode, prop_selection = _fit_propensity_backend(
        X,
        T,
        fit_idx,
        calib_idx,
        test_idx,
        contract,
        seed=rep_seed + 11 * (fold_id + 1),
    )
    treated_train = fit_idx[T[fit_idx] > 0.5]
    control_train = fit_idx[T[fit_idx] <= 0.5]
    mu1_scaled, mu1_backend, mu1_selection = _fit_regression_backend(
        X,
        Y_scaled,
        treated_train,
        test_idx,
        contract,
        seed=rep_seed + 17 * (fold_id + 1),
    )
    mu0_scaled, mu0_backend, mu0_selection = _fit_regression_backend(
        X,
        Y_scaled,
        control_train,
        test_idx,
        contract,
        seed=rep_seed + 29 * (fold_id + 1),
    )
    return {
        "test_idx": np.asarray(test_idx, dtype=int),
        "propensity": propensity,
        "mu1": inverse_scale(mu1_scaled, scaler),
        "mu0": inverse_scale(mu0_scaled, scaler),
        "prop_backend": prop_backend,
        "calibration_mode": calibration_mode,
        "outcome_backends": [mu1_backend, mu0_backend],
        "selection_records": [
            prop_selection,
            {**mu1_selection, "arm": "treated"},
            {**mu0_selection, "arm": "control"},
        ],
    }


def _fit_crossfit_nuisance_bundle_uncached(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    contract: ATENuisanceContract,
) -> ATENuisanceBundle:
    X = np.asarray(X, dtype=float)
    T = np.asarray(T, dtype=float).reshape(-1)
    Y = np.asarray(Y, dtype=float).reshape(-1)
    n_obs = Y.size

    scaler = fit_outcome_scaler(Y, contract.outcome_scaling)
    Y_scaled = scale_outcome(Y, scaler)

    propensity_sum = np.zeros(n_obs, dtype=float)
    mu1_sum = np.zeros(n_obs, dtype=float)
    mu0_sum = np.zeros(n_obs, dtype=float)
    split_manifest = _make_split_manifest(T, contract)
    calibration_modes: list[str] = []
    propensity_backends: list[str] = []
    outcome_backends: list[str] = []
    selection_manifest: list[dict[str, Any]] = []

    if contract.random_seed_manifest:
        repeat_seeds = list(contract.random_seed_manifest)[: contract.n_repeats]
        if len(repeat_seeds) < contract.n_repeats:
            start = repeat_seeds[-1] if repeat_seeds else contract.random_seed
            repeat_seeds.extend(start + 997 * (idx + 1) for idx in range(contract.n_repeats - len(repeat_seeds)))
    else:
        repeat_seeds = [contract.random_seed + 997 * repeat for repeat in range(contract.n_repeats)]

    idx_all = np.arange(n_obs)
    tasks: list[dict[str, Any]] = []
    for repeat, rep_seed in enumerate(repeat_seeds):
        repeat_rng = np.random.default_rng(rep_seed)
        treated_idx = idx_all[T > 0.5].copy()
        control_idx = idx_all[T <= 0.5].copy()
        repeat_rng.shuffle(treated_idx)
        repeat_rng.shuffle(control_idx)
        treated_folds = np.array_split(treated_idx, contract.crossfit_folds)
        control_folds = np.array_split(control_idx, contract.crossfit_folds)

        for fold_id in range(contract.crossfit_folds):
            test_idx = np.sort(np.concatenate([treated_folds[fold_id], control_folds[fold_id]]))
            train_idx = np.setdiff1d(idx_all, test_idx, assume_unique=False)
            train_rng = np.random.default_rng(rep_seed + 37 * (fold_id + 1))
            shuffled_train = train_idx.copy()
            train_rng.shuffle(shuffled_train)
            calib_size = int(round(contract.calibration_fraction * shuffled_train.size))
            if shuffled_train.size >= contract.min_calibration_size + 4:
                calib_size = max(calib_size, contract.min_calibration_size)
            calib_size = max(0, min(calib_size, max(shuffled_train.size - 4, 0)))
            calib_idx = np.sort(shuffled_train[:calib_size]) if calib_size > 0 else np.array([], dtype=int)
            fit_idx = np.sort(shuffled_train[calib_size:]) if calib_size > 0 else shuffled_train
            if fit_idx.size < 4:
                fit_idx = train_idx
                calib_idx = np.array([], dtype=int)
            tasks.append(
                {
                    "rep_seed": int(rep_seed),
                    "fold_id": int(fold_id),
                    "fit_idx": np.asarray(fit_idx, dtype=int),
                    "calib_idx": np.asarray(calib_idx, dtype=int),
                    "test_idx": np.asarray(test_idx, dtype=int),
                }
            )

    max_workers = 1
    if contract.parallel_folds and len(tasks) > 1:
        auto_workers = os.cpu_count() or 1
        max_workers = min(len(tasks), contract.max_parallel_folds or auto_workers)
        max_workers = max(1, int(max_workers))

    if max_workers > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            fold_results = list(
                executor.map(
                    lambda task: _fit_crossfit_fold(
                        X=X,
                        T=T,
                        Y_scaled=Y_scaled,
                        scaler=scaler,
                        contract=contract,
                        rep_seed=int(task["rep_seed"]),
                        fold_id=int(task["fold_id"]),
                        fit_idx=np.asarray(task["fit_idx"], dtype=int),
                        calib_idx=np.asarray(task["calib_idx"], dtype=int),
                        test_idx=np.asarray(task["test_idx"], dtype=int),
                    ),
                    tasks,
                )
            )
    else:
        fold_results = [
            _fit_crossfit_fold(
                X=X,
                T=T,
                Y_scaled=Y_scaled,
                scaler=scaler,
                contract=contract,
                rep_seed=int(task["rep_seed"]),
                fold_id=int(task["fold_id"]),
                fit_idx=np.asarray(task["fit_idx"], dtype=int),
                calib_idx=np.asarray(task["calib_idx"], dtype=int),
                test_idx=np.asarray(task["test_idx"], dtype=int),
            )
            for task in tasks
        ]

    for fold_result in fold_results:
        test_idx = np.asarray(fold_result["test_idx"], dtype=int)
        propensity_sum[test_idx] += np.asarray(fold_result["propensity"], dtype=float)
        mu1_sum[test_idx] += np.asarray(fold_result["mu1"], dtype=float)
        mu0_sum[test_idx] += np.asarray(fold_result["mu0"], dtype=float)
        propensity_backends.append(str(fold_result["prop_backend"]))
        calibration_modes.append(str(fold_result["calibration_mode"]))
        outcome_backends.extend(str(value) for value in fold_result["outcome_backends"])
        selection_manifest.extend(
            record for record in fold_result["selection_records"] if isinstance(record, dict)
        )

    denom = float(contract.n_repeats)
    propensity = np.clip(propensity_sum / denom, contract.propensity_clipping, 1.0 - contract.propensity_clipping)
    mu1 = mu1_sum / denom
    mu0 = mu0_sum / denom
    trim_threshold = max(contract.propensity_clipping, contract.propensity_trimming)
    trim_mask = (propensity >= trim_threshold) & (propensity <= 1.0 - trim_threshold)
    if not np.any(trim_mask):
        trim_mask = np.ones(n_obs, dtype=bool)

    return ATENuisanceBundle(
        propensity=propensity,
        mu1=mu1,
        mu0=mu0,
        trim_mask=trim_mask,
        scaler=scaler,
        contract=contract,
        split_manifest=split_manifest,
        calibration_modes=calibration_modes,
        propensity_backends=propensity_backends,
        outcome_backends=outcome_backends,
        selection_manifest=selection_manifest,
    )


def fit_crossfit_nuisance_bundle(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    contract: ATENuisanceContract,
    params: Mapping[str, Any] | None = None,
) -> ATENuisanceBundle:
    precomputed = None if params is None else params.get("__shared_nuisance_bundle")
    if isinstance(precomputed, ATENuisanceBundle):
        return precomputed
    cache_key = _shared_nuisance_cache_key(X, T, Y, contract, params)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    bundle = _fit_crossfit_nuisance_bundle_uncached(X, T, Y, contract)
    _cache_put(cache_key, bundle)
    return bundle


def _interval_from_eif(
    estimate: float,
    eif_values: np.ndarray,
    contract: ATENuisanceContract,
    *,
    seed_offset: int,
    nuisance: ATENuisanceBundle | None = None,
) -> tuple[float, float, float, float, str]:
    eif_values = np.asarray(eif_values, dtype=float).reshape(-1)
    eif_values = eif_values[np.isfinite(eif_values)]
    if eif_values.size == 0:
        return estimate, 0.0, estimate, estimate, "degenerate"

    pseudo_values = estimate + eif_values
    se = robust_standard_error(eif_values)
    use_bootstrap = contract.inference_backend == "bootstrap_eif" and contract.bootstrap_draws >= 2
    if contract.ci_mode.strip().lower() == "wald":
        use_bootstrap = False
    elif contract.ci_mode.strip().lower() == "bootstrap":
        use_bootstrap = contract.bootstrap_draws >= 2

    if use_bootstrap:
        ci_lower, ci_upper = bootstrap_mean_interval(
            pseudo_values,
            seed=contract.random_seed + seed_offset,
            draws=contract.bootstrap_draws,
        )
        interval_method = "bootstrap_eif"
    else:
        z = 1.96
        ci_lower = estimate - z * se
        ci_upper = estimate + z * se
        interval_method = "wald_eif"

    diagnostics = nuisance.diagnostics() if nuisance is not None else {}
    coverage_guard = contract.coverage_guard.strip().lower()
    ci_mode = contract.ci_mode.strip().lower()
    if ci_mode == "conservative" or (
        ci_mode == "auto"
        and coverage_guard != "off"
        and _coverage_guard_triggered(diagnostics=diagnostics, contract=contract)
    ):
        ess = float(diagnostics.get("effective_sample_size", 1.0))
        inflation = min(
            2.0,
            max(1.15, np.sqrt(float(contract.min_effective_sample_size) / max(ess, 1.0))),
        )
        overlap_ntv = float(diagnostics.get("overlap_ntv", 0.0))
        if overlap_ntv > _coverage_guard_ntv_threshold(contract):
            inflation = min(2.0, max(inflation, 1.0 + overlap_ntv))
        half_width = max(abs(ci_upper - estimate), abs(estimate - ci_lower), 1.96 * se)
        ci_lower = estimate - inflation * half_width
        ci_upper = estimate + inflation * half_width
        interval_method = f"{interval_method}+coverage_guard"
    return estimate, se, ci_lower, ci_upper, interval_method


def _coverage_guard_ntv_threshold(contract: ATENuisanceContract) -> float:
    return max(0.40, 2.5 * float(contract.overlap_guard))


def _coverage_guard_triggered(
    *,
    diagnostics: Mapping[str, Any],
    contract: ATENuisanceContract,
) -> bool:
    coverage_guard = contract.coverage_guard.strip().lower()
    if coverage_guard == "off":
        return False
    return bool(
        float(diagnostics.get("effective_sample_size", float("inf")))
        < float(contract.min_effective_sample_size)
        or float(diagnostics.get("clipping_fraction", 0.0)) > float(contract.overlap_guard)
        or float(diagnostics.get("support_mismatch_fraction", 0.0)) > float(contract.overlap_guard)
        or float(diagnostics.get("overlap_ntv", 0.0)) > _coverage_guard_ntv_threshold(contract)
    )


def _weak_overlap_mode(contract: ATENuisanceContract) -> str:
    return contract.weak_overlap_mode.strip().lower()


def _point_estimation_mask(
    nuisance: ATENuisanceBundle,
    contract: ATENuisanceContract,
) -> np.ndarray:
    mode = _weak_overlap_mode(contract)
    if mode in {"diagnostic_only", "diagnostics_only", "none", "off"}:
        return np.ones_like(nuisance.trim_mask, dtype=bool)
    return np.asarray(nuisance.trim_mask, dtype=bool)


def _targeting_step_limit(
    contract: ATENuisanceContract,
    nuisance: ATENuisanceBundle,
    response: np.ndarray,
    valid_mask: np.ndarray,
) -> float:
    scale = 1.0
    if bool(getattr(nuisance.scaler, "applied", False)):
        scale = max(scale, float(getattr(nuisance.scaler, "scale", 1.0)))
    valid_response = np.asarray(response[valid_mask] if np.any(valid_mask) else response, dtype=float)
    if valid_response.size > 1:
        scale = max(scale, float(np.std(valid_response, ddof=1)))
    return max(float(contract.targeting_step_limit), float(contract.targeting_step_limit) * scale)


def fit_aipw_ate(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    params: Mapping[str, Any] | None = None,
) -> tuple[ATEFitResult, ATENuisanceBundle]:
    contract = ATENuisanceContract.from_params(params)
    nuisance = fit_crossfit_nuisance_bundle(X, T, Y, contract, params)
    e = nuisance.propensity
    valid = _point_estimation_mask(nuisance, contract)
    psi = nuisance.effect_signal() + T * (Y - nuisance.mu1) / e - (1.0 - T) * (
        Y - nuisance.mu0
    ) / (1.0 - e)
    psi_valid = np.asarray(psi[valid], dtype=float)
    ate = float(np.mean(psi_valid))
    eif_values = psi_valid - ate
    ate, se, ci_lower, ci_upper, interval_method = _interval_from_eif(
        ate,
        eif_values,
        contract,
        seed_offset=17,
        nuisance=nuisance,
    )
    result = ATEFitResult(
        ate=ate,
        standard_error=se,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        interval_method=interval_method,
        eif_mean=float(np.mean(eif_values)) if eif_values.size else 0.0,
        eif_standard_deviation=float(np.std(eif_values, ddof=1)) if eif_values.size > 1 else 0.0,
        eif_values=eif_values,
        nuisance_bundle=nuisance,
        targeting_summary=None,
    )
    return result, nuisance


def fit_tmle_ate(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    params: Mapping[str, Any] | None = None,
) -> tuple[ATEFitResult, ATENuisanceBundle]:
    contract = ATENuisanceContract.from_params(params)
    nuisance = fit_crossfit_nuisance_bundle(X, T, Y, contract, params)
    e = nuisance.propensity
    q1 = np.asarray(nuisance.mu1, dtype=float)
    q0 = np.asarray(nuisance.mu0, dtype=float)
    valid = _point_estimation_mask(nuisance, contract)
    q1_star = q1.copy()
    q0_star = q0.copy()
    history: list[dict[str, Any]] = []
    step_limit = _targeting_step_limit(contract, nuisance, Y, valid)

    for iteration in range(contract.max_targeting_iter):
        q_a_star = np.where(T > 0.5, q1_star, q0_star)
        clever = T / e - (1.0 - T) / (1.0 - e)
        residual = Y - q_a_star
        denom = max(float(np.sum((clever[valid]) ** 2)), 1e-12)
        raw_step = float(np.sum(clever[valid] * residual[valid]) / denom)
        step = float(np.clip(raw_step, -step_limit, step_limit))
        q1_star = q1_star + step / e
        q0_star = q0_star - step / (1.0 - e)
        residual_mse = float(np.mean((residual[valid]) ** 2)) if np.any(valid) else float(np.mean(residual**2))
        history.append(
            {
                "iteration": iteration,
                "raw_epsilon": raw_step,
                "epsilon": step,
                "epsilon_limit": step_limit,
                "residual_mse": residual_mse,
                "clever_covariate_mean": float(np.mean(clever[valid])) if np.any(valid) else float(np.mean(clever)),
            }
        )
        if abs(step) < 1e-8:
            break

    targeted_diff = q1_star - q0_star
    ate = float(np.mean(targeted_diff[valid]))
    q_a_star = np.where(T > 0.5, q1_star, q0_star)
    clever = T / e - (1.0 - T) / (1.0 - e)
    eif_values = targeted_diff[valid] + clever[valid] * (Y[valid] - q_a_star[valid]) - ate
    ate, se, ci_lower, ci_upper, interval_method = _interval_from_eif(
        ate,
        eif_values,
        contract,
        seed_offset=53,
        nuisance=nuisance,
    )
    result = ATEFitResult(
        ate=ate,
        standard_error=se,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        interval_method=interval_method,
        eif_mean=float(np.mean(eif_values)) if eif_values.size else 0.0,
        eif_standard_deviation=float(np.std(eif_values, ddof=1)) if eif_values.size > 1 else 0.0,
        eif_values=eif_values,
        nuisance_bundle=nuisance,
        targeting_summary={
            "n_iterations": len(history),
            "converged": bool(history and abs(history[-1]["epsilon"]) < 1e-8),
            "history": history,
            "final_residual_mse": history[-1]["residual_mse"] if history else float("nan"),
        },
    )
    return result, nuisance


def result_payload(
    result: ATEFitResult,
    nuisance: ATENuisanceBundle,
) -> dict[str, Any]:
    contract = nuisance.contract
    payload = {
        "ate": result.ate,
        "standard_error": result.standard_error,
        "ci_lower": result.ci_lower,
        "ci_upper": result.ci_upper,
        "interval_method": result.interval_method,
        "eif_mean": result.eif_mean,
        "eif_standard_deviation": result.eif_standard_deviation,
        "effect_scale": result.effect_scale,
        "nuisance_diagnostics": nuisance.diagnostics(),
        "nuisance_config": contract.as_legacy_config(),
        "nuisance_contract": contract.as_contract_payload(),
        "selection_manifest": {
            "selected_propensity_backend": nuisance.propensity_backends[0] if nuisance.propensity_backends else None,
            "selected_outcome_backend": nuisance.outcome_backends[0] if nuisance.outcome_backends else None,
            "tested_propensity_backends": list(contract.propensity_backend_candidates or (contract.propensity_backend,)),
            "tested_outcome_backends": list(contract.outcome_backend_candidates or (contract.outcome_backend,)),
            "selection_objective": contract.selection_objective,
            "split_policy": contract.overlap_diagnostic_policy,
            "calibration_modes": list(nuisance.calibration_modes),
            "records": list(nuisance.selection_manifest),
        },
    }
    if result.targeting_summary is not None:
        payload["targeting_summary"] = result.targeting_summary
    return payload


__all__ = [
    "ATEFitResult",
    "ATENuisanceBundle",
    "ATENuisanceContract",
    "fit_aipw_ate",
    "fit_crossfit_nuisance_bundle",
    "fit_tmle_ate",
    "result_payload",
]
