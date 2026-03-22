from __future__ import annotations

import inspect
from typing import Any, Callable, ClassVar, Mapping

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
    extract_cate_from_estimator,
    require_econml,
)
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.ir.analytics.causal import CausalMethod, EstimationStatus
from polisyos.ir.analytics.hte import FeatureImportance, HTEResult, SubgroupEffect


def _supports_discrete_treatment_kwarg(cls: type) -> bool:
    try:
        return "discrete_treatment" in inspect.signature(cls).parameters
    except (TypeError, ValueError):
        return False


def _candidate_ints(raw: Any) -> list[int]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        values = raw
    else:
        values = [raw]
    resolved: list[int] = []
    for item in values:
        try:
            resolved.append(int(item))
        except Exception:
            continue
    return resolved


def _selected_n_estimators(params: Mapping[str, Any]) -> int:
    default = int(params.get("n_estimators", 500))
    candidates = _candidate_ints(params.get("n_estimators_candidates"))
    return max([default, *candidates]) if candidates else default


def _selected_min_samples_leaf(params: Mapping[str, Any]) -> int:
    default = int(params.get("min_samples_leaf", 5))
    candidates = _candidate_ints(params.get("min_samples_leaf_candidates"))
    return min([default, *candidates]) if candidates else default


def _supports_fit_inference_kwarg(model: Any) -> bool:
    try:
        return "inference" in inspect.signature(model.fit).parameters
    except (TypeError, ValueError, AttributeError):
        return False


def _build_bootstrap_inference(params: Mapping[str, Any]) -> Any | None:
    n_samples = int(params.get("bootstrap_inference_samples", 0) or 0)
    if n_samples < 2:
        return None
    try:
        from econml.inference import BootstrapInference
    except Exception:
        return None
    return BootstrapInference(
        n_bootstrap_samples=n_samples,
        n_jobs=max(1, int(params.get("bootstrap_inference_n_jobs", 1))),
        bootstrap_type=str(params.get("bootstrap_inference_type", "pivot")),
        verbose=0,
    )


def _resolve_first_stage_model(
    raw: Any,
    *,
    task: str,
    seed: int,
) -> Any:
    token = "" if raw is None else str(raw).strip().lower()
    if token in {"", "auto", "default"}:
        return "auto"
    try:
        from sklearn.ensemble import (
            GradientBoostingClassifier,
            GradientBoostingRegressor,
            HistGradientBoostingClassifier,
            HistGradientBoostingRegressor,
            RandomForestClassifier,
            RandomForestRegressor,
        )
        from sklearn.linear_model import ElasticNet, LogisticRegression
    except Exception:
        return "auto"

    if task == "regression":
        if token in {"histgradientboosting", "hist_gb", "hgb"}:
            return HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, random_state=seed)
        if token in {"gradient_boosting", "gb"}:
            return GradientBoostingRegressor(random_state=seed)
        if token in {"random_forest", "rf"}:
            return RandomForestRegressor(
                n_estimators=200,
                min_samples_leaf=5,
                random_state=seed,
                n_jobs=1,
            )
        if token in {"elastic_net", "elastic_net_sparse"}:
            return ElasticNet(alpha=0.01, l1_ratio=0.9, max_iter=3000, random_state=seed)
        return "auto"

    if token in {"histgradientboosting", "hist_gb", "hgb"}:
        return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, random_state=seed)
    if token in {"gradient_boosting", "gb"}:
        return GradientBoostingClassifier(random_state=seed)
    if token in {"random_forest", "rf"}:
        return RandomForestClassifier(
            n_estimators=200,
            min_samples_leaf=5,
            random_state=seed,
            n_jobs=1,
        )
    if token in {"linear", "logistic", "logistic_regression"}:
        return LogisticRegression(max_iter=1000, solver="lbfgs")
    return "auto"


def _feature_importances_from_array(
    values: np.ndarray,
    feature_names: list[str],
    *,
    method: str,
    minimum_total: float = 1e-10,
) -> list[dict[str, Any]]:
    arr = np.asarray(values, dtype=float).ravel()
    if arr.size == 0:
        return []
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    total = float(np.sum(np.abs(arr)))
    if total <= minimum_total:
        return []
    order = np.argsort(-np.abs(arr))
    payload: list[dict[str, Any]] = []
    for rank, idx in enumerate(order, start=1):
        name = feature_names[int(idx)] if int(idx) < len(feature_names) else f"x{int(idx)}"
        payload.append(
            {
                "feature_name": name,
                "importance_score": float(abs(arr[int(idx)])),
                "importance_rank": rank,
                "method": method,
                "metadata": {},
            }
        )
    return payload


def _permutation_feature_importances(
    estimator: Any,
    X: np.ndarray,
    *,
    seed: int,
    feature_names: list[str],
    repeats: int = 5,
    max_rows: int = 256,
) -> list[dict[str, Any]]:
    X = np.asarray(X, dtype=float)
    if X.ndim != 2 or X.shape[1] == 0 or X.shape[0] == 0:
        return []
    rng = np.random.default_rng(seed)
    if X.shape[0] > max_rows:
        subset = np.sort(rng.choice(X.shape[0], size=max_rows, replace=False))
        X_eval = X[subset]
    else:
        X_eval = X
    try:
        baseline = np.asarray(estimator.effect(X_eval), dtype=float).reshape(-1)
    except Exception:
        return []
    if baseline.shape[0] != X_eval.shape[0] or not np.isfinite(baseline).all():
        return []

    scores = np.zeros(X_eval.shape[1], dtype=float)
    n_repeats = max(1, int(repeats))
    for column_idx in range(X_eval.shape[1]):
        deltas: list[float] = []
        for _ in range(n_repeats):
            permuted = np.array(X_eval, copy=True)
            permuted[:, column_idx] = permuted[rng.permutation(permuted.shape[0]), column_idx]
            try:
                perm_pred = np.asarray(estimator.effect(permuted), dtype=float).reshape(-1)
            except Exception:
                continue
            if perm_pred.shape[0] != baseline.shape[0] or not np.isfinite(perm_pred).all():
                continue
            deltas.append(float(np.mean((perm_pred - baseline) ** 2)))
        if deltas:
            scores[column_idx] = max(0.0, float(np.mean(deltas)))

    if float(np.sum(scores)) <= 1e-12:
        return []
    return _feature_importances_from_array(scores, feature_names, method="permutation")


def _suppress_importances_if_homogeneous(
    cate_values: np.ndarray,
    importances: list[dict[str, Any]],
    *,
    threshold: float = 1e-8,
) -> list[dict[str, Any]]:
    cate_arr = np.asarray(cate_values, dtype=float).ravel()
    if cate_arr.size == 0 or float(np.nanstd(cate_arr)) <= threshold:
        return []
    total = float(np.sum([float(item.get("importance_score", 0.0)) for item in importances]))
    if total <= threshold:
        return []
    return importances


def _effect_signal(cate_values: np.ndarray) -> float:
    arr = np.asarray(cate_values, dtype=float).ravel()
    if arr.size <= 1:
        return 0.0
    return float(np.std(arr, ddof=1))


@foundry_method(
    namespace="causal.hte",
    version="1.0.0",
    tags={"causal", "hte", "causal-forest", "cate"},
)
class CausalForestEstimator:
    """Causal Forest via EconML CausalForestDML."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="causal_forest",
        namespace="placeholder",
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
                SlotSpec(
                    name="causal_effect_report",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("report", "json"),
                ),
                SlotSpec(
                    name="hte_result",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("report", "json"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="n_estimators", default=500),
            ParameterSpec(name="max_depth", default=None),
            ParameterSpec(name="min_samples_leaf", default=5),
            ParameterSpec(name="max_samples", default=0.5),
            ParameterSpec(name="honest", default=True),
            ParameterSpec(name="cv_folds", default=3),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="subgroup_quantiles", default=4),
            ParameterSpec(name="feature_importance_method", default="permutation"),
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
            "Causal Forest (Generalized Random Forest) for heterogeneous treatment effects."
        ),
        tags=frozenset({"causal", "hte", "causal-forest"}),
        citations=(
            "Wager, S., & Athey, S. (2018). Estimation and Inference of Heterogeneous "
            "Treatment Effects using Random Forests.",
            "Athey, S., Tibshirani, J., & Wager, S. (2019). Generalized Random Forests.",
        ),
        equations={
            "cate": "tau(x) = E[Y(1) - Y(0) | X = x]",
            "ate": "ATE = E[tau(X)]",
        },
        assumptions={
            "unconfoundedness": "No unobserved confounders conditional on observed covariates.",
            "overlap": "0 < P(T=1|X) < 1 across support.",
            "consistency": "Observed outcome equals potential outcome under observed treatment.",
        },
        when_to_use="Heterogeneous treatment effects; individual-level CATE estimation; high-dimensional covariates",
        when_not_to_use="Average effect only needed; small sample (<100)",
        typical_min_obs=200,
        output_interpretation="CATE(x): treatment effect for individual with covariates x. ATE = mean(CATE). Feature importances show heterogeneity drivers.",
    )

    @staticmethod
    def pure_step(state: HTEObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            require_econml()
            from econml.dml import CausalForestDML
        except Exception as exc:
            report = build_failure_report(
                method=CausalMethod.CAUSAL_FOREST,
                status=EstimationStatus.NUMERICAL_FAILURE,
                reason=f"Causal forest backend unavailable: {exc}",
                estimand="ATE_from_CATE",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(CausalForestEstimator.metadata.assumptions),
            )
            return wrap_causal_output(
                report,
                warnings=[report.status_reason or "backend unavailable"],
            )

        data = build_hte_data(state)
        alpha = 1.0 - float(params.get("confidence_level", 0.95))
        seed = params.get("random_state")
        if seed is None:
            seed = params.get("__seed__", 0)
        seed_int = int(seed)
        rng = np.random.default_rng(seed_int)
        n_estimators = _selected_n_estimators(params)
        min_samples_leaf = _selected_min_samples_leaf(params)
        model_y = _resolve_first_stage_model(
            params.get("model_y_backend", params.get("model_y")),
            task="regression",
            seed=seed_int + 17,
        )
        model_t = _resolve_first_stage_model(
            params.get("model_t_backend", params.get("model_t")),
            task="classification",
            seed=seed_int + 29,
        )

        model_kwargs: dict[str, Any] = {
            "n_estimators": n_estimators,
            "max_depth": params.get("max_depth"),
            "min_samples_leaf": min_samples_leaf,
            "max_samples": float(params.get("max_samples", 0.5)),
            "honest": bool(params.get("honest", True)),
            "cv": int(params.get("cv_folds", 3)),
            "random_state": seed_int,
            "model_y": model_y,
            "model_t": model_t,
        }
        if _supports_discrete_treatment_kwarg(CausalForestDML):
            model_kwargs["discrete_treatment"] = True
        model = CausalForestDML(**model_kwargs)
        fit_kwargs: dict[str, Any] = {"X": data.x, "W": data.w}
        bootstrap_inference = _build_bootstrap_inference(params)
        if bootstrap_inference is not None and _supports_fit_inference_kwarg(model):
            fit_kwargs["inference"] = bootstrap_inference
        try:
            model.fit(data.y, data.t, **fit_kwargs)
        except TypeError:
            model.fit(data.y, data.t, X=data.x, W=data.w)

        extracted = extract_cate_from_estimator(
            model,
            data.x,
            alpha=alpha,
            feature_names=data.feature_names,
            feature_importance_method=str(params.get("feature_importance_method", "permutation")),
            rng=rng,
        )
        feature_importance_method = str(params.get("feature_importance_method", "permutation")).strip().lower()
        feature_importances = extracted["feature_importances"]
        if feature_importance_method == "permutation":
            feature_importances = _permutation_feature_importances(
                model,
                data.x,
                seed=seed_int + 133,
                feature_names=list(data.feature_names),
                repeats=max(3, int(params.get("feature_importance_repeats", 5))),
                max_rows=max(64, int(params.get("feature_importance_rows", 256))),
            )
        feature_importances = _suppress_importances_if_homogeneous(
            np.asarray(extracted["cate_values"], dtype=float),
            list(feature_importances),
        )
        subgroup_payloads = build_cate_quantile_subgroups(
            cate_values=extracted["cate_values"],
            n_quantiles=int(params.get("subgroup_quantiles", 4)),
            alpha=alpha,
        )

        hte_result = HTEResult(
            method=CausalMethod.CAUSAL_FOREST,
            ate=extracted["ate"],
            ate_ci_lower=extracted["ate_ci_lower"],
            ate_ci_upper=extracted["ate_ci_upper"],
            ate_p_value=extracted["ate_p_value"],
            confidence_level=float(params.get("confidence_level", 0.95)),
            cate_values=extracted["cate_values"],
            cate_std_values=extracted["cate_std_values"],
            cate_ci_lower_values=extracted["cate_ci_lower_values"],
            cate_ci_upper_values=extracted["cate_ci_upper_values"],
            subgroup_effects=[SubgroupEffect.model_validate(item) for item in subgroup_payloads],
            feature_importances=[
                FeatureImportance.model_validate(item) for item in feature_importances
            ],
            n_samples=int(data.y.shape[0]),
            n_treated=int(np.sum(data.t == 1)),
            n_control=int(np.sum(data.t == 0)),
            n_features=int(data.x.shape[1]),
            feature_names=list(data.feature_names),
            econml_estimator_class="econml.dml.CausalForestDML",
            econml_params={
                "n_estimators": n_estimators,
                "n_estimators_candidates": _candidate_ints(params.get("n_estimators_candidates")),
                "max_depth": params.get("max_depth"),
                "min_samples_leaf": min_samples_leaf,
                "min_samples_leaf_candidates": _candidate_ints(params.get("min_samples_leaf_candidates")),
                "max_samples": float(params.get("max_samples", 0.5)),
                "honest": bool(params.get("honest", True)),
                "cv_folds": int(params.get("cv_folds", 3)),
                "model_y_backend": params.get("model_y_backend", params.get("model_y", "auto")),
                "model_t_backend": params.get("model_t_backend", params.get("model_t", "auto")),
                "bootstrap_inference_samples": int(params.get("bootstrap_inference_samples", 0) or 0),
            },
            feature_display_map={name: name for name in data.feature_names},
            metadata={
                "warnings": list(extracted["warnings"]),
                "confounder_names": list(data.confounder_names),
                "feature_importance_method": feature_importance_method,
                "heterogeneity_signal": _effect_signal(np.asarray(extracted["cate_values"], dtype=float)),
            },
        )

        report = build_success_report(
            method=CausalMethod.CAUSAL_FOREST,
            estimand="ATE_from_CATE",
            point_estimate=extracted["ate"],
            confidence_interval=(extracted["ate_ci_lower"], extracted["ate_ci_upper"]),
            confidence_level=float(params.get("confidence_level", 0.95)),
            p_value=extracted["ate_p_value"],
            inference_method="causal_forest_dml",
            sample_size=int(data.y.shape[0]),
            n_treated=int(np.sum(data.t == 1)),
            n_control=int(np.sum(data.t == 0)),
            pre_periods=0,
            post_periods=0,
            assumptions=dict(CausalForestEstimator.metadata.assumptions),
            method_params={
                "n_estimators": n_estimators,
                "min_samples_leaf": min_samples_leaf,
                "feature_importance_method": str(
                    params.get("feature_importance_method", "permutation")
                ),
            },
            metadata={
                "hte_result_present": True,
                "n_features": int(data.x.shape[1]),
            },
        )
        return wrap_causal_output(
            report,
            warnings=list(extracted["warnings"]),
            extras={"hte_result": hte_result},
        )


__all__ = ["CausalForestEstimator"]
