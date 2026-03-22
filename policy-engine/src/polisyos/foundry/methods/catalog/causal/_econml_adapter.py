from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from polisyos.foundry.methods.catalog.causal.ci_backends import robust_standard_error
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData

ECONML_IMPORT_ERROR: Exception | None = None
ECONML_AVAILABLE = False

try:  # pragma: no cover - depends on optional dependency
    import econml  # noqa: F401

    ECONML_AVAILABLE = True
except Exception as exc:  # pragma: no cover - optional dependency
    ECONML_IMPORT_ERROR = exc


SHAP_MAX_BACKGROUND = 300
SHAP_MAX_ROWS = 1200
SHAP_MIN_ROWS_FOR_SUBSAMPLE = 500


@dataclass(frozen=True)
class HTEData:
    y: np.ndarray
    t: np.ndarray
    x: np.ndarray
    w: np.ndarray | None
    feature_names: list[str]
    confounder_names: list[str]


def require_econml() -> None:
    if not ECONML_AVAILABLE:
        raise ImportError(
            "EconML is required for HTE methods. Install optional deps: "
            "pip install policy-engine[causal]"
        ) from ECONML_IMPORT_ERROR


def build_hte_data(state: Any) -> HTEData:
    data = (
        state
        if isinstance(state, HTEObservationalData)
        else HTEObservationalData.model_validate(state)
    )
    x = np.asarray(data.covariates, dtype=float)
    if data.confounders is None:
        w = None
    else:
        w = np.asarray(data.confounders, dtype=float)

    feature_names = (
        list(data.feature_names)
        if data.feature_names is not None
        else [f"x{i}" for i in range(x.shape[1])]
    )
    confounder_names = (
        list(data.confounder_names)
        if data.confounder_names is not None
        else [f"w{i}" for i in range(w.shape[1])] if w is not None else []
    )
    return HTEData(
        y=np.asarray(data.outcome, dtype=float),
        t=np.asarray(data.treatment, dtype=int),
        x=x,
        w=w,
        feature_names=feature_names,
        confounder_names=confounder_names,
    )


def _sanitize_effect(values: Any) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim > 1:
        arr = arr.reshape(arr.shape[0], -1)[:, 0]
    return arr.ravel()


def _align_metric_length(values: Any, *, n_samples: int, fill: float = np.nan) -> np.ndarray:
    arr = _sanitize_effect(values)
    if arr.size == n_samples:
        return arr
    if arr.size == 1 and n_samples > 1:
        return np.full(n_samples, float(arr[0]), dtype=float)
    if arr.size == 0:
        return np.full(n_samples, fill, dtype=float)
    return np.full(n_samples, fill, dtype=float)


def _scalar_from_any(value: Any) -> float | None:
    try:
        arr = np.asarray(value, dtype=float).reshape(-1)
    except Exception:
        return None
    if arr.size == 0:
        return None
    scalar = float(arr[0])
    return scalar if np.isfinite(scalar) else None


def _extract_ate_confidence_interval(
    inference: Any,
    *,
    alpha: float,
) -> tuple[float, float] | None:
    for method_name in ("conf_int", "conf_int_mean"):
        method = getattr(inference, method_name, None)
        if not callable(method):
            continue
        for kwargs in ({"alpha": alpha}, {}):
            try:
                interval = method(**kwargs)
            except TypeError:
                continue
            except Exception:
                interval = None
            if interval is None:
                continue
            try:
                lo = float(np.asarray(interval[0], dtype=float).reshape(-1)[0])
                hi = float(np.asarray(interval[1], dtype=float).reshape(-1)[0])
            except Exception:
                continue
            if np.isfinite(lo) and np.isfinite(hi):
                return lo, hi
    return None


def _extract_ate_standard_error(inference: Any) -> float | None:
    for attr_name in ("stderr_mean", "mean_pred_stderr", "stderr_point", "std_point"):
        attr = getattr(inference, attr_name, None)
        if attr is None:
            continue
        try:
            value = attr() if callable(attr) else attr
        except Exception:
            continue
        scalar = _scalar_from_any(value)
        if scalar is not None:
            return scalar
    return None


def _guarded_ate_standard_error(cate: np.ndarray, cate_std: np.ndarray) -> float | None:
    cate_arr = np.asarray(cate, dtype=float).reshape(-1)
    cate_arr = cate_arr[np.isfinite(cate_arr)]
    if cate_arr.size <= 1:
        return None
    between_var = float(np.var(cate_arr, ddof=1))
    cate_std_arr = np.asarray(cate_std, dtype=float).reshape(-1)
    cate_std_arr = cate_std_arr[np.isfinite(cate_std_arr)]
    within_var = float(np.mean(cate_std_arr**2)) if cate_std_arr.size else 0.0
    total_var = max(0.0, between_var + within_var)
    ate_se = float(np.sqrt(total_var / cate_arr.size))
    return ate_se if np.isfinite(ate_se) else None


def _extract_tree_importances(
    estimator: Any,
    *,
    feature_names: list[str],
) -> list[dict[str, Any]]:
    raw = getattr(estimator, "feature_importances_", None)
    if raw is None and hasattr(estimator, "model_cate"):
        raw = getattr(estimator.model_cate, "feature_importances_", None)
    if raw is None and hasattr(estimator, "model_final"):
        raw = getattr(estimator.model_final, "feature_importances_", None)
    if raw is None:
        return []

    values = np.asarray(raw, dtype=float).ravel()
    if values.size == 0:
        return []
    order = np.argsort(-values)
    output: list[dict[str, Any]] = []
    for rank, feat_idx in enumerate(order, start=1):
        idx = int(feat_idx)
        name = feature_names[idx] if idx < len(feature_names) else f"x{idx}"
        output.append(
            {
                "feature_name": name,
                "importance_score": float(values[idx]),
                "importance_rank": rank,
                "method": "tree_based",
                "metadata": {},
            }
        )
    return output


def _extract_shap_importances(
    estimator: Any,
    x: np.ndarray,
    *,
    feature_names: list[str],
    rng: np.random.Generator,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    try:  # pragma: no cover - optional dependency
        import shap
    except (ImportError, ModuleNotFoundError):
        return [], ["SHAP not installed; falling back to tree_based feature importance"]

    if x.shape[0] > SHAP_MAX_ROWS:
        idx = rng.choice(np.arange(x.shape[0]), size=SHAP_MAX_ROWS, replace=False)
        x_eval = x[idx]
        warnings.append(
            f"SHAP evaluation rows capped at {SHAP_MAX_ROWS} (from {x.shape[0]})"
        )
    else:
        x_eval = x

    if x_eval.shape[0] > SHAP_MIN_ROWS_FOR_SUBSAMPLE:
        bg_idx = rng.choice(
            np.arange(x_eval.shape[0]),
            size=min(SHAP_MAX_BACKGROUND, x_eval.shape[0]),
            replace=False,
        )
        x_bg = x_eval[bg_idx]
    else:
        x_bg = x_eval

    base_model = None
    for attr in ("model_cate", "model_final", "final_model"):
        if hasattr(estimator, attr):
            candidate = getattr(estimator, attr)
            if candidate is not None:
                base_model = candidate
                break
    if base_model is None:
        base_model = estimator

    try:  # pragma: no cover - optional dependency
        explainer = shap.TreeExplainer(base_model, data=x_bg)
        shap_values = explainer.shap_values(x_eval)
        arr = np.asarray(shap_values, dtype=float)
        if arr.ndim == 3:
            arr = arr[0]
        scores = np.mean(np.abs(arr), axis=0)
    except Exception as exc:  # pragma: no cover - runtime safety
        return [], [f"SHAP failed ({type(exc).__name__}); falling back to tree_based"]

    order = np.argsort(-scores)
    output: list[dict[str, Any]] = []
    for rank, feat_idx in enumerate(order, start=1):
        idx = int(feat_idx)
        name = feature_names[idx] if idx < len(feature_names) else f"x{idx}"
        output.append(
            {
                "feature_name": name,
                "importance_score": float(scores[idx]),
                "importance_rank": rank,
                "method": "shap",
                "metadata": {"sample_rows": int(x_eval.shape[0])},
            }
        )
    return output, warnings


def extract_feature_importances(
    estimator: Any,
    x: np.ndarray,
    *,
    feature_names: list[str],
    method: str,
    rng: np.random.Generator,
) -> tuple[list[dict[str, Any]], list[str]]:
    if method == "shap":
        shap_importances, shap_warnings = _extract_shap_importances(
            estimator, x, feature_names=feature_names, rng=rng
        )
        if shap_importances:
            return shap_importances, shap_warnings
        tree_importances = _extract_tree_importances(estimator, feature_names=feature_names)
        return tree_importances, shap_warnings

    if method == "permutation":
        warnings = [
            "Permutation importance is not implemented for EconML wrappers; "
            "falling back to tree_based"
        ]
        return _extract_tree_importances(estimator, feature_names=feature_names), warnings

    return _extract_tree_importances(estimator, feature_names=feature_names), []


def extract_cate_from_estimator(
    estimator: Any,
    x: np.ndarray,
    *,
    alpha: float,
    feature_names: list[str],
    feature_importance_method: str,
    rng: np.random.Generator,
) -> dict[str, Any]:
    warnings: list[str] = []
    cate = _sanitize_effect(estimator.effect(x))
    n_samples = int(cate.shape[0])

    ci_lower = np.full(n_samples, np.nan, dtype=float)
    ci_upper = np.full(n_samples, np.nan, dtype=float)
    try:
        lo, hi = estimator.effect_interval(x, alpha=alpha)
        ci_lower = _align_metric_length(lo, n_samples=n_samples)
        ci_upper = _align_metric_length(hi, n_samples=n_samples)
    except Exception:  # noqa: BLE001 - econml estimator API varies per backend
        warnings.append("Estimator does not provide effect_interval; per-row CIs omitted")

    cate_std = np.full(n_samples, np.nan, dtype=float)
    try:
        inference = estimator.effect_inference(x)
        cate_std = _align_metric_length(
            getattr(inference, "std_point", np.nan),
            n_samples=n_samples,
        )
    except Exception:  # noqa: BLE001 - econml estimator API varies per backend
        warnings.append("Estimator does not provide effect_inference; per-row std omitted")

    ate = float(np.mean(cate))
    ate_ci_lower = float("nan")
    ate_ci_upper = float("nan")
    ate_p_value = None
    native_ate_inference = None
    try:
        native_ate_inference = estimator.ate_inference(x)
        conf = _extract_ate_confidence_interval(native_ate_inference, alpha=alpha)
        if conf is not None:
            ate_ci_lower, ate_ci_upper = conf
        pvalue = getattr(native_ate_inference, "pvalue", None)
        if pvalue is not None:
            ate_p_value = float(np.asarray(pvalue).ravel()[0])
    except Exception:  # noqa: BLE001 - econml estimator API varies per backend
        native_ate_inference = None

    ate_se = _extract_ate_standard_error(native_ate_inference) if native_ate_inference is not None else None
    if ate_se is None:
        guarded_se = _guarded_ate_standard_error(cate, cate_std)
        if guarded_se is None and np.isfinite(cate).sum() > 1:
            guarded_se = robust_standard_error(cate)
        if guarded_se is not None:
            ate_se = guarded_se
        if not (np.isfinite(ate_ci_lower) and np.isfinite(ate_ci_upper)):
            if ate_se is not None:
                half_width = 1.96 * max(ate_se, 1e-12)
                ate_ci_lower = float(ate - half_width)
                ate_ci_upper = float(ate + half_width)
                warnings.append(
                    "Estimator does not provide usable ate_inference; ATE CI via Wald fallback"
                )
            else:
                warnings.append("Estimator does not provide usable ate_inference; ATE CI omitted")

    guarded_se = _guarded_ate_standard_error(cate, cate_std)
    if guarded_se is not None and np.isfinite(ate_ci_lower) and np.isfinite(ate_ci_upper):
        native_half_width = max(abs(ate - ate_ci_lower), abs(ate_ci_upper - ate))
        guarded_half_width = 1.96 * max(guarded_se, 1e-12)
        if guarded_half_width > native_half_width + 1e-12:
            ate_ci_lower = float(ate - guarded_half_width)
            ate_ci_upper = float(ate + guarded_half_width)
            warnings.append("ATE CI widened by guarded variance floor")

    importances, importance_warnings = extract_feature_importances(
        estimator,
        x,
        feature_names=feature_names,
        method=feature_importance_method,
        rng=rng,
    )
    warnings.extend(importance_warnings)

    return {
        "cate_values": cate.tolist(),
        "cate_std_values": cate_std.tolist(),
        "cate_ci_lower_values": ci_lower.tolist(),
        "cate_ci_upper_values": ci_upper.tolist(),
        "ate": ate,
        "ate_ci_lower": ate_ci_lower,
        "ate_ci_upper": ate_ci_upper,
        "ate_p_value": ate_p_value,
        "feature_importances": importances,
        "warnings": warnings,
    }


def build_cate_quantile_subgroups(
    *,
    cate_values: list[float],
    n_quantiles: int,
    alpha: float,
) -> list[dict[str, Any]]:
    values = np.asarray(cate_values, dtype=float)
    if values.size == 0:
        return []
    q = max(2, int(n_quantiles))
    edges = np.quantile(values, np.linspace(0.0, 1.0, q + 1))
    output: list[dict[str, Any]] = []
    for idx in range(q):
        lo = float(edges[idx])
        hi = float(edges[idx + 1])
        if idx < q - 1:
            mask = (values >= lo) & (values < hi)
        else:
            mask = (values >= lo) & (values <= hi)
        if not mask.any():
            continue
        bucket = values[mask]
        output.append(
            {
                "subgroup_id": f"cate_q{idx + 1}",
                "subgroup_label": f"CATE quantile {idx + 1}",
                "subgroup_label_human": f"Population segment {idx + 1} by estimated uplift",
                "subgroup_query": f"cate >= {lo:.6g} AND cate <= {hi:.6g}",
                "n_units": int(mask.sum()),
                "cate_mean": float(np.mean(bucket)),
                "cate_std": float(np.std(bucket)),
                "cate_ci_lower": float(np.percentile(bucket, 100.0 * alpha / 2.0)),
                "cate_ci_upper": float(np.percentile(bucket, 100.0 * (1.0 - alpha / 2.0))),
                "confidence_level": float(1.0 - alpha),
                "is_significant": False,
                "p_value": None,
                "metadata": {"quantile_index": idx + 1},
            }
        )
    return output


__all__ = [
    "HTEData",
    "require_econml",
    "build_hte_data",
    "extract_cate_from_estimator",
    "build_cate_quantile_subgroups",
]
