"""Public causal causal bcf module API."""
from __future__ import annotations

from typing import Any, Callable, ClassVar, Literal, Mapping, Sequence

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog.causal._common import (
    build_failure_report,
    build_success_report,
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal._econml_adapter import (
    build_cate_quantile_subgroups,
    build_hte_data,
)
from polisyos.foundry.methods.catalog.causal.ci_backends import (
    bootstrap_mean_interval,
    robust_standard_error,
)
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.foundry.methods.catalog.causal.superlearner import SuperLearnerConfig, SuperLearnerNuisance
from polisyos.ir.analytics.causal import CausalMethod, EstimationStatus
from polisyos.ir.analytics.hte import FeatureImportance, HTEResult, SubgroupEffect


def _estimate_propensity_scores(
    X: np.ndarray,
    T: np.ndarray,
    *,
    seed: int,
) -> tuple[np.ndarray, Any | None, list[str]]:
    X = np.asarray(X, dtype=float)
    T = np.asarray(T, dtype=float).reshape(-1)
    warnings: list[str] = []
    if X.shape[0] == 0:
        return np.array([], dtype=float), None, warnings
    if np.unique(T).size < 2:
        return np.full(X.shape[0], float(np.mean(T)), dtype=float), None, warnings

    try:
        from sklearn.linear_model import LogisticRegression

        model = LogisticRegression(max_iter=1000, solver="lbfgs")
        model.fit(X, T)
        propensity = np.asarray(model.predict_proba(X)[:, 1], dtype=float)
        return np.clip(propensity, 0.02, 0.98), model, warnings
    except Exception as exc:
        warnings.append(f"logistic propensity fit failed: {exc}")

    try:
        from sklearn.ensemble import GradientBoostingClassifier  # type: ignore[import]

        model = GradientBoostingClassifier(
            random_state=seed,
            n_estimators=160,
            learning_rate=0.05,
            max_depth=2,
            subsample=0.8,
        )
        model.fit(X, T)
        propensity = np.asarray(model.predict_proba(X)[:, 1], dtype=float)
        return np.clip(propensity, 0.02, 0.98), model, warnings
    except Exception as exc:
        warnings.append(f"gradient boosting propensity fit failed: {exc}")

    return np.full(X.shape[0], float(np.mean(T)), dtype=float), None, warnings


def _predict_propensity_scores(
    model: Any | None,
    X: np.ndarray,
    *,
    default: float,
) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    if X.shape[0] == 0:
        return np.array([], dtype=float)
    if model is None:
        return np.full(X.shape[0], default, dtype=float)
    try:
        if hasattr(model, "predict_proba"):
            propensity = np.asarray(model.predict_proba(X)[:, 1], dtype=float)
        else:
            propensity = np.asarray(model.predict(X), dtype=float).reshape(-1)
    except Exception:
        propensity = np.full(X.shape[0], default, dtype=float)
    return np.clip(propensity, 0.02, 0.98)


def _coerce_stochtree_prediction(payload: Any, *, term: str) -> np.ndarray:
    if isinstance(payload, dict):
        for key in (term, "tau", "cate", "mu", "prognostic_function", "y_hat"):
            value = payload.get(key)
            if value is not None:
                return np.asarray(value, dtype=float)
        raise KeyError(f"stochtree prediction missing requested term {term!r}")
    return np.asarray(payload, dtype=float)


def _posterior_std_from_draws(draws: np.ndarray, *, n_obs: int) -> np.ndarray:
    arr = np.asarray(draws, dtype=float)
    if arr.ndim <= 1:
        return np.full(n_obs, float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0, dtype=float)
    if arr.shape[0] == n_obs:
        return np.std(arr, axis=1, ddof=1)
    if arr.shape[-1] == n_obs:
        return np.std(arr, axis=0, ddof=1)
    flat = arr.reshape(-1)
    return np.full(n_obs, float(np.std(flat, ddof=1)) if flat.size > 1 else 0.0, dtype=float)


def _ridge_fit(X: np.ndarray, y: np.ndarray, alpha: float = 1.0) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float).ravel()
    Xa = np.column_stack([np.ones(X.shape[0]), X])
    reg = alpha * np.eye(Xa.shape[1])
    reg[0, 0] = 0.0
    beta, *_ = np.linalg.lstsq(Xa.T @ Xa + reg, Xa.T @ y, rcond=None)
    return beta


def _ridge_predict(X: np.ndarray, beta: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    Xa = np.column_stack([np.ones(X.shape[0]), X])
    return Xa @ beta


def _feature_importances_from_array(
    values: np.ndarray,
    feature_names: Sequence[str],
    *,
    method: str,
    minimum_total: float = 1e-10,
) -> list[dict[str, Any]]:
    values = np.asarray(values, dtype=float).ravel()
    if values.size == 0:
        return []
    if not np.isfinite(values).any():
        return []
    values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
    order = np.argsort(-np.abs(values))
    total = float(np.sum(np.abs(values)))
    if total <= minimum_total:
        return []
    out: list[dict[str, Any]] = []
    for rank, idx in enumerate(order, start=1):
        name = feature_names[int(idx)] if int(idx) < len(feature_names) else f"x{int(idx)}"
        out.append(
            {
                "feature_name": name,
                "importance_score": float(abs(values[int(idx)])),
                "importance_rank": rank,
                "method": method,
                "metadata": {},
            }
    )
    return out


def _permute_importance_from_predictor(
    predict_fn: Callable[[np.ndarray], np.ndarray],
    X: np.ndarray,
    *,
    seed: int,
    repeats: int,
    max_rows: int,
) -> np.ndarray | None:
    X = np.asarray(X, dtype=float)
    if X.ndim != 2 or X.shape[1] == 0 or X.shape[0] == 0:
        return None

    rng = np.random.default_rng(seed)
    if X.shape[0] > max_rows:
        subset = np.sort(rng.choice(X.shape[0], size=max_rows, replace=False))
        X_eval = X[subset]
    else:
        X_eval = X

    try:
        baseline = np.asarray(predict_fn(X_eval), dtype=float).reshape(-1)
    except Exception:
        return None
    if baseline.shape[0] != X_eval.shape[0] or not np.isfinite(baseline).all():
        return None

    importances = np.zeros(X_eval.shape[1], dtype=float)
    n_repeats = max(1, int(repeats))
    for column_idx in range(X_eval.shape[1]):
        scores: list[float] = []
        for _ in range(n_repeats):
            permuted = np.array(X_eval, copy=True)
            permuted[:, column_idx] = permuted[rng.permutation(permuted.shape[0]), column_idx]
            try:
                permuted_pred = np.asarray(predict_fn(permuted), dtype=float).reshape(-1)
            except Exception:
                continue
            if permuted_pred.shape[0] != baseline.shape[0] or not np.isfinite(permuted_pred).all():
                continue
            scores.append(float(np.mean((permuted_pred - baseline) ** 2)))
        if scores:
            importances[column_idx] = max(0.0, float(np.mean(scores)))

    total = float(np.sum(importances))
    if total <= 1e-12:
        return None
    return importances / total


def _fit_two_stage_linear_bcf(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    *,
    ridge_alpha: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    control = T <= 0.5
    treated = ~control
    if int(control.sum()) < 3 or int(treated.sum()) < 3:
        mu_beta = _ridge_fit(X, Y, alpha=ridge_alpha)
        tau_beta = np.zeros(X.shape[1] + 1, dtype=float)
    else:
        mu_beta = _ridge_fit(X[control], Y[control], alpha=ridge_alpha)
        mu_hat = _ridge_predict(X, mu_beta)
        tau_beta = _ridge_fit(X[treated], Y[treated] - mu_hat[treated], alpha=ridge_alpha)
    mu_hat = _ridge_predict(X, mu_beta)
    tau_hat = _ridge_predict(X, tau_beta)
    return mu_hat, tau_hat, mu_beta, tau_beta


def _fit_sklearn_pseudo_bcf(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    *,
    seed: int,
    bootstrap_runs: int,
    num_trees_mu: int,
    num_trees_tau: int,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    list[str],
    Callable[[np.ndarray], np.ndarray] | None,
]:
    warnings: list[str] = []
    try:  # pragma: no cover - optional dependency
        from sklearn.ensemble import GradientBoostingClassifier  # type: ignore[import]
        from sklearn.ensemble import GradientBoostingRegressor  # type: ignore[import]
        from sklearn.linear_model import LogisticRegression

        def _fit_once(
            X_fit: np.ndarray,
            T_fit: np.ndarray,
            Y_fit: np.ndarray,
            *,
            fit_seed: int,
        ) -> tuple[np.ndarray, np.ndarray, GradientBoostingRegressor]:
            if np.unique(T_fit).size >= 2:
                try:
                    propensity_model = GradientBoostingClassifier(
                        random_state=fit_seed + 3,
                        n_estimators=max(120, int(num_trees_mu)),
                        learning_rate=0.05,
                        max_depth=2,
                        subsample=0.8,
                    )
                    propensity_model.fit(X_fit, T_fit)
                    pi_hat = np.asarray(propensity_model.predict_proba(X_fit)[:, 1], dtype=float)
                except Exception:
                    propensity_model = LogisticRegression(max_iter=1000, solver="lbfgs")
                    propensity_model.fit(X_fit, T_fit)
                    pi_hat = np.asarray(propensity_model.predict_proba(X_fit)[:, 1], dtype=float)
            else:
                pi_hat = np.full(X_fit.shape[0], float(np.mean(T_fit)), dtype=float)
            pi_hat = np.clip(pi_hat, 0.02, 0.98)

            mu_features = np.column_stack([X_fit, pi_hat])
            mu_model = GradientBoostingRegressor(
                random_state=fit_seed,
                n_estimators=max(120, int(num_trees_mu)),
                learning_rate=0.03,
                max_depth=3,
                subsample=0.8,
                min_samples_leaf=8,
            )
            mu_model.fit(mu_features, Y_fit)
            mu_hat_local = np.asarray(mu_model.predict(mu_features), dtype=float)

            denominator = T_fit - pi_hat
            safe_denominator = np.where(
                np.abs(denominator) < 0.05,
                np.where(denominator >= 0.0, 0.05, -0.05),
                denominator,
            )
            tau_target = (Y_fit - mu_hat_local) / safe_denominator
            tau_weight = np.square(denominator)
            tau_model_local = GradientBoostingRegressor(
                random_state=fit_seed + 11,
                n_estimators=max(60, int(num_trees_tau)),
                learning_rate=0.03,
                max_depth=2,
                subsample=0.8,
                min_samples_leaf=10,
            )
            tau_model_local.fit(X_fit, tau_target, sample_weight=tau_weight)
            tau_hat_local = np.asarray(tau_model_local.predict(X_fit), dtype=float)
            return mu_hat_local, tau_hat_local, tau_model_local

        mu_hat, tau_hat, tau_model = _fit_once(X, T, Y, fit_seed=seed)
        warnings.append(
            "sklearn fallback uses propensity-augmented pseudo-outcome calibration"
        )

        boot = np.zeros((bootstrap_runs, X.shape[0]), dtype=float)
        rng = np.random.default_rng(seed)
        for b in range(bootstrap_runs):
            idx = rng.integers(0, X.shape[0], size=X.shape[0])
            Xb, Tb, Yb = X[idx], T[idx], Y[idx]
            _, _, tau_b = _fit_once(Xb, Tb, Yb, fit_seed=seed + 100 + b)
            boot[b] = np.asarray(tau_b.predict(X), dtype=float)

        tau_std = np.std(boot, axis=0, ddof=1)
        coef = getattr(tau_model, "feature_importances_", np.array([]))
        if np.asarray(coef).size == 0 and hasattr(tau_model, "estimators_"):
            coef = np.std(boot, axis=0)
        predict_tau = lambda X_new: np.asarray(tau_model.predict(np.asarray(X_new, dtype=float)), dtype=float).ravel()
        return mu_hat, tau_hat, tau_std, np.asarray(coef, dtype=float), warnings, predict_tau
    except Exception as exc:  # pragma: no cover - optional dependency
        warnings.append(f"sklearn fallback unavailable: {exc}")
        mu_hat, tau_hat, mu_beta, tau_beta = _fit_two_stage_linear_bcf(
            X, T, Y, ridge_alpha=1.0
        )
        tau_std = np.full(X.shape[0], float(np.std(tau_hat, ddof=1) / np.sqrt(max(len(tau_hat), 1))))
        coef = np.abs(tau_beta[1:])
        predict_tau = lambda X_new: np.asarray(_ridge_predict(np.asarray(X_new, dtype=float), tau_beta), dtype=float).ravel()
        return mu_hat, tau_hat, tau_std, coef, warnings, predict_tau


def _fit_stochtree_bcf(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    *,
    seed: int,
    params: Mapping[str, Any],
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    list[str],
    Callable[[np.ndarray], np.ndarray] | None,
] | None:
    try:  # pragma: no cover - optional dependency
        from stochtree import BCFModel  # type: ignore[import]
    except Exception as exc:  # pragma: no cover - optional dependency
        return None

    warnings: list[str] = []
    try:
        propensity_train, propensity_model, propensity_warnings = _estimate_propensity_scores(
            X,
            T,
            seed=seed + 31,
        )
        warnings.extend(propensity_warnings)
        propensity_mean = float(np.mean(propensity_train)) if propensity_train.size else 0.5
        model = BCFModel()
        if not hasattr(model, "sample"):
            raise AttributeError("BCFModel exposes neither sample nor fit")
        model.sample(
            X,
            T,
            Y,
            propensity_train=propensity_train,
            X_test=X,
            Z_test=T,
            propensity_test=propensity_train,
            num_gfr=int(params.get("num_gfr", 100)),
            num_mcmc=int(params.get("num_mcmc", 200)),
            general_params={"random_seed": seed},
            prognostic_forest_params={"num_trees": int(params.get("num_trees_mu", 200))},
            treatment_effect_forest_params={"num_trees": int(params.get("num_trees_tau", 50))},
        )

        tau_hat = _coerce_stochtree_prediction(
            model.predict(
                X,
                T,
                propensity=propensity_train,
                type="mean",
                terms="tau",
            ),
            term="tau",
        ).reshape(-1)
        mu_hat = _coerce_stochtree_prediction(
            model.predict(
                X,
                T,
                propensity=propensity_train,
                type="mean",
                terms="mu",
            ),
            term="mu",
        ).reshape(-1)
        tau_draws = _coerce_stochtree_prediction(
            model.predict(
                X,
                T,
                propensity=propensity_train,
                type="posterior",
                terms="tau",
            ),
            term="tau",
        )
        tau_std = _posterior_std_from_draws(tau_draws, n_obs=X.shape[0])

        def _predict_tau(X_new: np.ndarray) -> np.ndarray:
            X_arr = np.asarray(X_new, dtype=float)
            propensity_new = _predict_propensity_scores(
                propensity_model,
                X_arr,
                default=propensity_mean,
            )
            pred = model.predict(
                X_arr,
                np.zeros(X_arr.shape[0], dtype=float),
                propensity=propensity_new,
                type="mean",
                terms="tau",
            )
            return _coerce_stochtree_prediction(pred, term="tau").reshape(-1)

        coef = np.abs(np.asarray(getattr(model, "feature_importances_", np.array([])), dtype=float).ravel())
        warnings.append("stochtree backend uses explicit propensity augmentation with tau-term predictions")
        return mu_hat, tau_hat, tau_std, coef, warnings, _predict_tau
    except Exception as exc:
        warnings.append(f"stochtree backend failed: {exc}")
        return None


@foundry_method(
    namespace="causal.hte",
    version="1.0.0",
    tags={"causal", "hte", "bayesian-causal-forest", "bcf"},
)
class CausalBCF:
    """Bayesian Causal Forest with backend fallback chain."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="causal_bcf",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="hte_data",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("observations", "rows"),
                    shape=("n_obs", "n_features"),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(name="causal_effect_report", slot_type=SlotType.SCALAR, unit=Unit("report", "json")),
                SlotSpec(name="hte_result", slot_type=SlotType.SCALAR, unit=Unit("report", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="backend", default="auto"),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="bootstrap_runs", default=100),
            ParameterSpec(name="feature_importance_mode", default="permutation"),
            ParameterSpec(name="permutation_repeats", default=5),
            ParameterSpec(name="permutation_rows", default=256),
            ParameterSpec(name="heterogeneity_threshold", default=1e-8),
            ParameterSpec(name="num_gfr", default=100),
            ParameterSpec(name="num_mcmc", default=200),
            ParameterSpec(name="num_trees_mu", default=200),
            ParameterSpec(name="num_trees_tau", default=50),
            ParameterSpec(name="ridge_alpha", default=1.0),
            ParameterSpec(name="random_state", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Bayesian Causal Forest for heterogeneous treatment effects with a "
            "backend fallback chain: stochtree → sklearn pseudo-BCF → numpy/pymc fallback."
        ),
        tags=frozenset({"causal", "hte", "bayesian-causal-forest", "bcf"}),
        citations=(
            "Hahn, P.R., Murray, J.S. & Carvalho, C.M. (2020). Bayesian Regression Tree Models for Causal Inference: Regularization, Confounding, and Heterogeneous Effects.",
            "Hill, J. (2011). Bayesian nonparametric modeling for causal inference.",
        ),
        equations={
            "bcf": "Y = mu(X) + tau(X) * T + eps",
            "cate": "tau(x) = E[Y(1) - Y(0) | X = x]",
        },
        assumptions={
            "unconfoundedness": "No unobserved confounders conditional on observed covariates.",
            "overlap": "0 < P(T=1|X) < 1 across support.",
            "consistency": "Observed outcome equals potential outcome under observed treatment.",
        },
        when_to_use=(
            "Heterogeneous treatment effects with uncertainty quantification; prefer stochtree when installed."
        ),
        when_not_to_use="Average treatment effects only; very tiny samples (<100).",
        typical_min_obs=200,
        output_interpretation="CATE(x): posterior mean treatment effect for unit with covariates x.",
    )

    @staticmethod
    def pure_step(state: HTEObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, HTEObservationalData)
            else HTEObservationalData.model_validate(state)
        )
        hte = build_hte_data(data)
        seed = params.get("random_state")
        if seed is None:
            seed = params.get("__seed__", 0)
        seed_int = int(seed)
        confidence_level = float(params.get("confidence_level", 0.95))
        backend = str(params.get("backend", "auto")).lower()
        bootstrap_runs = int(params.get("bootstrap_runs", 100))
        feature_importance_mode = str(params.get("feature_importance_mode", "permutation")).lower()
        permutation_repeats = max(1, int(params.get("permutation_repeats", 5)))
        permutation_rows = max(64, int(params.get("permutation_rows", 256)))
        heterogeneity_threshold = max(0.0, float(params.get("heterogeneity_threshold", 1e-8)))
        ridge_alpha = float(params.get("ridge_alpha", 1.0))

        backend_used = "numpy"
        warnings: list[str] = []

        stochtree_result: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]] | None = None
        if backend in ("auto", "stochtree"):
            stochtree_result = _fit_stochtree_bcf(
                hte.x,
                hte.t,
                hte.y,
                seed=seed_int,
                params=params,
            )
            if stochtree_result is not None:
                backend_used = "stochtree"
                warnings.extend(stochtree_result[4])

        if stochtree_result is None:
            if backend == "stochtree":
                warnings.append("stochtree backend unavailable; using sklearn pseudo-BCF fallback")
            backend_used = "sklearn"
            mu_hat, tau_hat, tau_std, coef, fit_warnings, predict_tau = _fit_sklearn_pseudo_bcf(
                hte.x,
                hte.t,
                hte.y,
                seed=seed_int,
                bootstrap_runs=max(20, bootstrap_runs),
                num_trees_mu=int(params.get("num_trees_mu", 200)),
                num_trees_tau=int(params.get("num_trees_tau", 50)),
            )
            warnings.extend(fit_warnings)
        else:
            mu_hat, tau_hat, tau_std, coef, fit_warnings, predict_tau = stochtree_result
            warnings.extend(fit_warnings)

        if backend == "pymc" and stochtree_result is None:
            warnings.append("pymc backend requested but unavailable; using sklearn/numpy fallback")

        tau_hat = np.asarray(tau_hat, dtype=float).reshape(-1)
        tau_std = np.asarray(tau_std, dtype=float).reshape(-1)
        if tau_std.shape != tau_hat.shape or not np.isfinite(tau_std).any():
            tau_std = np.full_like(tau_hat, robust_standard_error(tau_hat))
        tau_std = np.nan_to_num(tau_std, nan=0.0, posinf=0.0, neginf=0.0)
        ate = float(np.mean(tau_hat))
        ate_se = robust_standard_error(tau_hat)
        ci = bootstrap_mean_interval(
            tau_hat,
            seed=seed_int + 503,
            draws=max(40, bootstrap_runs),
        )

        heterogeneity_signal = float(np.std(tau_hat, ddof=1)) if tau_hat.size > 1 else 0.0
        subgroup_payloads = build_cate_quantile_subgroups(
            cate_values=tau_hat,
            n_quantiles=4,
            alpha=1.0 - confidence_level,
        )
        feature_names = list(hte.feature_names)
        feature_importances: list[dict[str, Any]] = []
        if heterogeneity_signal > heterogeneity_threshold:
            if feature_importance_mode == "permutation" and predict_tau is not None:
                perm_scores = _permute_importance_from_predictor(
                    predict_tau,
                    hte.x,
                    seed=seed_int + 907,
                    repeats=permutation_repeats,
                    max_rows=permutation_rows,
                )
                if perm_scores is not None:
                    feature_importances = _feature_importances_from_array(
                        perm_scores,
                        feature_names,
                        method="permutation",
                    )
            if not feature_importances:
                feature_importances = _feature_importances_from_array(
                    coef[1:] if coef.size > 1 else coef,
                    feature_names,
                    method=f"{backend_used}:model_based",
                )

        hte_result = HTEResult(
            method=CausalMethod.CAUSAL_BCF,
            ate=ate,
            ate_ci_lower=float(ci[0]),
            ate_ci_upper=float(ci[1]),
            ate_p_value=None,
            confidence_level=confidence_level,
            cate_values=tau_hat.tolist(),
            cate_std_values=tau_std.tolist(),
            cate_ci_lower_values=(tau_hat - 1.96 * tau_std).tolist(),
            cate_ci_upper_values=(tau_hat + 1.96 * tau_std).tolist(),
            subgroup_effects=[SubgroupEffect.model_validate(item) for item in subgroup_payloads],
            feature_importances=[FeatureImportance.model_validate(item) for item in feature_importances],
            n_samples=int(hte.y.shape[0]),
            n_treated=int(np.sum(hte.t == 1)),
            n_control=int(np.sum(hte.t == 0)),
            n_features=int(hte.x.shape[1]),
            feature_names=feature_names,
            econml_estimator_class=f"{backend_used}.BCFModel" if backend_used == "stochtree" else f"{backend_used}.PseudoBCF",
            econml_params={
                "backend": backend_used,
                "bootstrap_runs": bootstrap_runs,
                "ridge_alpha": ridge_alpha,
            },
            feature_display_map={name: name for name in feature_names},
            metadata={
                "backend_used": backend_used,
                "warnings": list(warnings),
                "feature_importance_method": feature_importance_mode,
                "heterogeneity_signal": heterogeneity_signal,
                "permutation_repeats": permutation_repeats,
            },
        )

        report = build_success_report(
            method=CausalMethod.CAUSAL_BCF,
            estimand="ATE_from_CATE",
            point_estimate=ate,
            confidence_interval=ci,
            confidence_level=confidence_level,
            p_value=None,
            inference_method=f"bcf_{backend_used}",
            sample_size=int(hte.y.shape[0]),
            n_treated=int(np.sum(hte.t == 1)),
            n_control=int(np.sum(hte.t == 0)),
            pre_periods=0,
            post_periods=0,
            assumptions=dict(CausalBCF.metadata.assumptions),
            method_params={
                "backend": backend_used,
                "bootstrap_runs": bootstrap_runs,
                "num_gfr": int(params.get("num_gfr", 100)),
                "num_mcmc": int(params.get("num_mcmc", 200)),
                "num_trees_mu": int(params.get("num_trees_mu", 200)),
                "num_trees_tau": int(params.get("num_trees_tau", 50)),
                "ridge_alpha": ridge_alpha,
            },
            metadata={
                "hte_result_present": True,
                "backend_used": backend_used,
                "warnings": list(warnings),
            },
        )
        return wrap_causal_output(
            report,
            warnings=list(warnings),
            extras={"hte_result": hte_result},
        )


__all__ = ["CausalBCF"]
