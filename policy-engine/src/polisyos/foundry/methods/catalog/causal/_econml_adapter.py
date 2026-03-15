from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

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
    w: np.ndarray
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
        w = x
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
        else [f"w{i}" for i in range(w.shape[1])]
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
    ate_ci_lower = float(np.percentile(cate, 100.0 * alpha / 2.0))
    ate_ci_upper = float(np.percentile(cate, 100.0 * (1.0 - alpha / 2.0)))
    ate_p_value = None
    try:
        ate_inf = estimator.ate_inference(x)
        conf = ate_inf.conf_int(alpha=alpha)
        ate_ci_lower = float(np.asarray(conf[0]).ravel()[0])
        ate_ci_upper = float(np.asarray(conf[1]).ravel()[0])
        pvalue = getattr(ate_inf, "pvalue", None)
        if pvalue is not None:
            ate_p_value = float(np.asarray(pvalue).ravel()[0])
    except Exception:  # noqa: BLE001 - econml estimator API varies per backend
        warnings.append("Estimator does not provide ate_inference; ATE CI via empirical quantiles")

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
