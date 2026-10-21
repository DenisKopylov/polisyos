"""Materialize CATE/HTE payloads and optional EconML diagnostics for causal methods."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from polisyos.foundry.methods.catalog.causal.ci_backends import robust_standard_error
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData

ECONML_IMPORT_ERROR: Exception | None = None
ECONML_AVAILABLE = False

try:  # pragma: no cover - depends on optional dependency
    import econml

    ECONML_AVAILABLE = True
except Exception as exc:  # pragma: no cover - optional dependency
    ECONML_IMPORT_ERROR = exc


SHAP_MAX_BACKGROUND = 300
SHAP_MAX_ROWS = 1200
_LEGACY_NORMAL_WALD_MULTIPLIER = 1.96


@dataclass(frozen=True)
class HTEData:
    """Carry treatment, outcome, covariate, and confounder arrays for HTE estimators."""

    y: np.ndarray
    t: np.ndarray
    x: np.ndarray
    w: np.ndarray | None
    feature_names: list[str]
    confounder_names: list[str]


def require_econml() -> None:
    """Require econml helper."""
    if not ECONML_AVAILABLE:
        raise ImportError(
            "EconML is required for HTE methods. Install optional deps: "
            "pip install policy-engine[causal]"
        ) from ECONML_IMPORT_ERROR


def build_hte_data(state: Any) -> HTEData:
    """Build hte data."""
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
        else [f"w{i}" for i in range(w.shape[1])]
        if w is not None
        else []
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
    if arr.ndim == 0:
        return arr.reshape(1)
    if any(dimension != 1 for dimension in arr.shape[1:]):
        raise ValueError(f"effect must be one value per observation; got {arr.shape}")
    return arr.reshape(arr.shape[0])


def _optional_metric_vector(
    values: Any,
    *,
    n_samples: int,
    field_name: str,
    nonnegative: bool = False,
) -> np.ndarray:
    """Validate a scalar-outcome per-observation metric without padding or truncation."""
    if values is None:
        return np.empty(0, dtype=float)
    try:
        arr = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must contain numeric values") from exc
    if arr.ndim == 0:
        if n_samples != 1:
            raise ValueError(f"{field_name} must contain one value per observation")
        arr = arr.reshape(1)
    if arr.shape[0] != n_samples:
        raise ValueError(
            f"{field_name} first dimension must match n_samples={n_samples}; got {arr.shape}"
        )
    if any(dimension != 1 for dimension in arr.shape[1:]):
        raise ValueError(
            f"{field_name} must represent one outcome and treatment per observation; got {arr.shape}"
        )
    arr = arr.reshape(n_samples)
    if not np.isfinite(arr).all():
        raise ValueError(f"{field_name} must contain only finite values")
    if nonnegative and np.any(arr < 0.0):
        raise ValueError(f"{field_name} must contain nonnegative standard errors")
    return arr


def _single_finite_scalar(value: Any, *, field_name: str) -> float:
    """Require one finite scalar from a single-outcome, single-treatment result."""
    try:
        arr = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if arr.size != 1:
        raise ValueError(f"{field_name} must contain exactly one scalar; got {arr.shape}")
    scalar = float(arr.reshape(-1)[0])
    if not np.isfinite(scalar):
        raise ValueError(f"{field_name} must be finite")
    return scalar


def _optional_ate_member_warning(
    warnings: list[str],
    *,
    member_name: str,
    phase: str,
    exception_type: str,
) -> None:
    warnings.append(
        "ATE_OPTIONAL_SUMMARY_MEMBER_UNAVAILABLE: "
        f"member={member_name}; phase={phase}; exception={exception_type}; value omitted"
    )


def _read_optional_ate_summary_member(
    inference: Any,
    *,
    member_name: str,
    warnings: list[str],
    call_kwargs: Mapping[str, Any] | None = None,
    callable_required: bool = False,
) -> Any | None:
    """Read and optionally invoke one native summary member with a typed warning boundary."""
    try:
        member = getattr(inference, member_name)
    except AttributeError as exc:
        try:
            inspect.getattr_static(inference, member_name)
        except AttributeError:
            return None
        except Exception as static_exc:
            _optional_ate_member_warning(
                warnings,
                member_name=member_name,
                phase="discovery",
                exception_type=type(static_exc).__name__,
            )
            return None
        _optional_ate_member_warning(
            warnings,
            member_name=member_name,
            phase="access",
            exception_type=type(exc).__name__,
        )
        return None
    except Exception as exc:
        _optional_ate_member_warning(
            warnings,
            member_name=member_name,
            phase="access",
            exception_type=type(exc).__name__,
        )
        return None

    if member is None:
        return None
    if not callable(member):
        if callable_required:
            _optional_ate_member_warning(
                warnings,
                member_name=member_name,
                phase="protocol",
                exception_type="TypeError",
            )
            return None
        return member

    try:
        return member(**(call_kwargs or {}))
    except Exception as exc:
        _optional_ate_member_warning(
            warnings,
            member_name=member_name,
            phase="invoke",
            exception_type=type(exc).__name__,
        )
        return None


def _extract_ate_confidence_interval(
    inference: Any,
    *,
    alpha: float,
    warnings: list[str],
) -> tuple[float, float] | None:
    for method_name in ("conf_int_mean", "conf_int"):
        interval = _read_optional_ate_summary_member(
            inference,
            member_name=method_name,
            warnings=warnings,
            call_kwargs={"alpha": alpha},
            callable_required=True,
        )
        if interval is None:
            continue
        if not isinstance(interval, (tuple, list)) or len(interval) != 2:
            raise ValueError(f"{method_name} must return a lower/upper pair")
        lower = _single_finite_scalar(interval[0], field_name=f"{method_name}.lower")
        upper = _single_finite_scalar(interval[1], field_name=f"{method_name}.upper")
        if lower > upper:
            raise ValueError(f"{method_name} returned a reversed confidence interval")
        return lower, upper
    return None


def _extract_ate_standard_error(inference: Any, *, warnings: list[str]) -> float | None:
    # `std_point` and `stderr_point` include cross-row effect heterogeneity; neither is
    # the standard error of the aggregate estimate. Only mean-level SE fields are valid here.
    for member_name in ("stderr_mean", "mean_pred_stderr"):
        value = _read_optional_ate_summary_member(
            inference,
            member_name=member_name,
            warnings=warnings,
        )
        if value is None:
            continue
        scalar = _single_finite_scalar(value, field_name=member_name)
        if scalar < 0.0:
            raise ValueError(f"{member_name} must be a nonnegative standard error")
        return scalar
    return None


def _extract_ate_p_value(inference: Any, *, warnings: list[str]) -> float | None:
    pvalue = _read_optional_ate_summary_member(
        inference,
        member_name="pvalue",
        warnings=warnings,
        call_kwargs={"value": 0},
    )
    if pvalue is None:
        return None
    scalar = _single_finite_scalar(pvalue, field_name="ate_inference.pvalue")
    if not 0.0 <= scalar <= 1.0:
        raise ValueError("ate_inference.pvalue must be between zero and one")
    return scalar


def _read_pointwise_standard_error(inference: Any) -> Any | None:
    """Read the per-observation SE protocol; never substitute population dispersion."""
    for attr_name in ("stderr", "pred_stderr"):
        try:
            value = getattr(inference, attr_name, None)
        except (AttributeError, NotImplementedError):
            continue
        if value is not None:
            return value
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
    if callable(raw):
        try:
            raw = raw()
        except Exception:
            return []
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
    if x.shape[0] > SHAP_MAX_ROWS:
        idx = rng.choice(np.arange(x.shape[0]), size=SHAP_MAX_ROWS, replace=False)
        x_eval = x[idx]
        warnings.append(f"SHAP evaluation rows capped at {SHAP_MAX_ROWS} (from {x.shape[0]})")
    else:
        x_eval = x

    shap_values_method = getattr(estimator, "shap_values", None)
    if not callable(shap_values_method):
        return [], [
            "EconML estimator does not expose native shap_values; "
            "falling back to tree_based feature importance"
        ]
    try:  # pragma: no cover - optional dependency and backend path
        explanations = shap_values_method(
            x_eval,
            feature_names=feature_names,
            background_samples=min(SHAP_MAX_BACKGROUND, int(x_eval.shape[0])),
        )
    except (ImportError, ModuleNotFoundError):  # pragma: no cover - optional dependency
        return [], ["SHAP not installed; falling back to tree_based feature importance"]
    except Exception as exc:  # pragma: no cover - backend runtime safety
        return [], [
            f"Estimator-native SHAP failed ({type(exc).__name__}); "
            "falling back to tree_based feature importance"
        ]

    if not isinstance(explanations, Mapping) or len(explanations) != 1:
        raise ValueError("Estimator-native SHAP must return one outcome explanation")
    treatment_explanations = next(iter(explanations.values()))
    if not isinstance(treatment_explanations, Mapping) or len(treatment_explanations) != 1:
        raise ValueError("Estimator-native SHAP must return one treatment explanation")
    explanation = next(iter(treatment_explanations.values()))
    raw_values = getattr(explanation, "values", None)
    if raw_values is None:
        raise ValueError("Estimator-native SHAP explanation is missing values")
    try:
        arr = np.asarray(raw_values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Estimator-native SHAP values must be numeric") from exc
    if arr.shape != x_eval.shape:
        raise ValueError(
            f"Estimator-native SHAP values must match evaluation shape {x_eval.shape}; got {arr.shape}"
        )
    if not np.isfinite(arr).all():
        raise ValueError("Estimator-native SHAP values must be finite")
    scores = np.mean(np.abs(arr), axis=0)

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
    """Extract feature importances helper."""
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
    """Extract CATE and optional estimator diagnostics without inventing missing values."""
    warnings: list[str] = []
    n_samples = int(x.shape[0])
    cate = _sanitize_effect(estimator.effect(x))
    if cate.size != n_samples:
        raise ValueError(
            f"effect must contain one value per observation ({n_samples}); got {cate.shape}"
        )

    ci_lower = np.empty(0, dtype=float)
    ci_upper = np.empty(0, dtype=float)
    interval_method = getattr(estimator, "effect_interval", None)
    interval = None
    if callable(interval_method):
        try:
            interval = interval_method(x, alpha=alpha)
        except (AttributeError, NotImplementedError):
            interval = None
    if interval is None:
        warnings.append("Estimator does not provide effect_interval; per-row CIs omitted")
    else:
        if not isinstance(interval, (tuple, list)) or len(interval) != 2:
            raise ValueError("effect_interval must return a lower/upper pair")
        ci_lower = _optional_metric_vector(
            interval[0], n_samples=n_samples, field_name="effect_interval.lower"
        )
        ci_upper = _optional_metric_vector(
            interval[1], n_samples=n_samples, field_name="effect_interval.upper"
        )

    cate_std = np.empty(0, dtype=float)
    inference_method = getattr(estimator, "effect_inference", None)
    inference = None
    if callable(inference_method):
        try:
            inference = inference_method(x)
        except (AttributeError, NotImplementedError):
            inference = None
    raw_stderr = _read_pointwise_standard_error(inference) if inference is not None else None
    if raw_stderr is None:
        warnings.append("Estimator does not provide per-row standard errors; values omitted")
    else:
        cate_std = _optional_metric_vector(
            raw_stderr,
            n_samples=n_samples,
            field_name="effect_inference.stderr",
            nonnegative=True,
        )

    ate = float(np.mean(cate))
    ate_ci_lower = float("nan")
    ate_ci_upper = float("nan")
    ate_p_value = None
    native_ate_inference = None
    ate_inference_method = getattr(estimator, "ate_inference", None)
    if callable(ate_inference_method):
        try:
            native_ate_inference = ate_inference_method(x)
        except (AttributeError, NotImplementedError):
            native_ate_inference = None
    if native_ate_inference is not None:
        conf = _extract_ate_confidence_interval(
            native_ate_inference,
            alpha=alpha,
            warnings=warnings,
        )
        if conf is not None:
            ate_ci_lower, ate_ci_upper = conf
        ate_p_value = _extract_ate_p_value(native_ate_inference, warnings=warnings)

    ate_se = (
        _extract_ate_standard_error(native_ate_inference, warnings=warnings)
        if native_ate_inference is not None
        else None
    )
    guarded_se = _guarded_ate_standard_error(cate, cate_std)
    if guarded_se is None and np.isfinite(cate).sum() > 1:
        guarded_se = robust_standard_error(cate)
    if ate_se is None and guarded_se is not None:
        ate_se = guarded_se

    # CI availability is independent of whether the native summary exposed a mean SE.
    if not (np.isfinite(ate_ci_lower) and np.isfinite(ate_ci_upper)):
        if ate_se is not None:
            # Retain the legacy fallback multiplier pending a separate basis decision.
            half_width = _LEGACY_NORMAL_WALD_MULTIPLIER * max(ate_se, 1e-12)
            ate_ci_lower = float(ate - half_width)
            ate_ci_upper = float(ate + half_width)
            warnings.append(
                "Native ATE interval unavailable; retained the existing fixed 1.96 "
                "normal-Wald fallback, whose inferential basis remains unqualified"
            )
        else:
            warnings.append("Estimator does not provide usable ate_inference; ATE CI omitted")

    guarded_se = _guarded_ate_standard_error(cate, cate_std)
    if guarded_se is not None and np.isfinite(ate_ci_lower) and np.isfinite(ate_ci_upper):
        native_half_width = max(abs(ate - ate_ci_lower), abs(ate_ci_upper - ate))
        # This legacy widening also remains unqualified; alpha does not change its multiplier.
        guarded_half_width = _LEGACY_NORMAL_WALD_MULTIPLIER * max(guarded_se, 1e-12)
        if guarded_half_width > native_half_width + 1e-12:
            ate_ci_lower = float(ate - guarded_half_width)
            ate_ci_upper = float(ate + guarded_half_width)
            warnings.append(
                "ATE CI widened by the existing guarded variance floor with the fixed 1.96 "
                "multiplier; its inferential basis remains unqualified"
            )

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
    """Build cate quantile subgroups."""
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
    "build_cate_quantile_subgroups",
    "build_hte_data",
    "extract_cate_from_estimator",
    "require_econml",
]
