"""Fieldwise comparators for cross-backend equivalence certificates."""

from __future__ import annotations

from typing import Any

import numpy as np

from polisyos.foundry.methods.equivalence.protocol import (
    ComparatorKind,
    FieldComparison,
    FieldToleranceSpec,
)


def compare_field_values(
    *,
    spec: FieldToleranceSpec,
    lhs: Any,
    rhs: Any,
) -> FieldComparison:
    """Apply one comparator spec to a pair of field values."""

    if spec.comparator is ComparatorKind.EXACT:
        return _compare_exact(spec=spec, lhs=lhs, rhs=rhs)
    if spec.comparator is ComparatorKind.ABS_REL:
        return _compare_abs_rel(spec=spec, lhs=lhs, rhs=rhs)
    if spec.comparator is ComparatorKind.ULP:
        return _compare_ulp(spec=spec, lhs=lhs, rhs=rhs)
    if spec.comparator is ComparatorKind.NORM:
        return _compare_norm(spec=spec, lhs=lhs, rhs=rhs)
    if spec.comparator is ComparatorKind.DISTRIBUTIONAL:
        return _compare_distributional(spec=spec, lhs=lhs, rhs=rhs)
    raise ValueError(f"Unsupported comparator: {spec.comparator.value}")


def _compare_exact(
    *,
    spec: FieldToleranceSpec,
    lhs: Any,
    rhs: Any,
) -> FieldComparison:
    lhs_shape = _shape_of(lhs)
    rhs_shape = _shape_of(rhs)

    if _should_use_array_comparison(lhs, rhs):
        lhs_arr = np.asarray(lhs)
        rhs_arr = np.asarray(rhs)
        if lhs_arr.shape != rhs_arr.shape:
            return FieldComparison(
                path=spec.path,
                comparator=spec.comparator,
                requirement=spec.requirement,
                strict_ok=False,
                relaxed_ok=False,
                lhs_shape=tuple(int(dim) for dim in lhs_arr.shape),
                rhs_shape=tuple(int(dim) for dim in rhs_arr.shape),
                message="shape mismatch",
            )
        try:
            matched = bool(np.array_equal(lhs_arr, rhs_arr, equal_nan=spec.equal_nan))
        except TypeError:
            matched = bool(np.array_equal(lhs_arr, rhs_arr))
        return FieldComparison(
            path=spec.path,
            comparator=spec.comparator,
            requirement=spec.requirement,
            strict_ok=matched,
            relaxed_ok=matched,
            lhs_shape=tuple(int(dim) for dim in lhs_arr.shape),
            rhs_shape=tuple(int(dim) for dim in rhs_arr.shape),
            message="" if matched else "exact equality check failed",
        )

    matched = lhs == rhs
    return FieldComparison(
        path=spec.path,
        comparator=spec.comparator,
        requirement=spec.requirement,
        strict_ok=bool(matched),
        relaxed_ok=bool(matched),
        lhs_shape=lhs_shape,
        rhs_shape=rhs_shape,
        message="" if matched else "exact equality check failed",
    )


def _compare_abs_rel(
    *,
    spec: FieldToleranceSpec,
    lhs: Any,
    rhs: Any,
) -> FieldComparison:
    try:
        lhs_arr = np.asarray(lhs, dtype=np.float64)
        rhs_arr = np.asarray(rhs, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        return FieldComparison(
            path=spec.path,
            comparator=spec.comparator,
            requirement=spec.requirement,
            strict_ok=False,
            relaxed_ok=False,
            message=f"non-numeric value: {exc}",
        )

    lhs_shape = tuple(int(dim) for dim in lhs_arr.shape)
    rhs_shape = tuple(int(dim) for dim in rhs_arr.shape)
    if lhs_shape != rhs_shape:
        return FieldComparison(
            path=spec.path,
            comparator=spec.comparator,
            requirement=spec.requirement,
            strict_ok=False,
            relaxed_ok=False,
            lhs_shape=lhs_shape,
            rhs_shape=rhs_shape,
            message="shape mismatch",
        )

    strict_ok = bool(
        np.all(
            np.isclose(
                lhs_arr,
                rhs_arr,
                atol=float(spec.strict_atol),
                rtol=float(spec.strict_rtol),
                equal_nan=spec.equal_nan,
            )
        )
    )
    relaxed_ok = bool(
        np.all(
            np.isclose(
                lhs_arr,
                rhs_arr,
                atol=float(spec.relaxed_atol or 0.0),
                rtol=float(spec.relaxed_rtol or 0.0),
                equal_nan=spec.equal_nan,
            )
        )
    )

    metrics = _numeric_error_metrics(
        lhs_arr=lhs_arr,
        rhs_arr=rhs_arr,
        scale_floor=float(spec.scale_floor),
        equal_nan=spec.equal_nan,
    )
    if strict_ok:
        message = ""
    elif relaxed_ok:
        message = "strict tolerance exceeded; relaxed envelope passed"
    else:
        message = "relaxed tolerance exceeded"
    return FieldComparison(
        path=spec.path,
        comparator=spec.comparator,
        requirement=spec.requirement,
        strict_ok=strict_ok,
        relaxed_ok=relaxed_ok,
        lhs_shape=lhs_shape,
        rhs_shape=rhs_shape,
        max_abs_error=metrics["max_abs_error"],
        max_rel_error=metrics["max_rel_error"],
        message=message,
        metadata={
            "strict_atol": spec.strict_atol,
            "strict_rtol": spec.strict_rtol,
            "relaxed_atol": spec.relaxed_atol,
            "relaxed_rtol": spec.relaxed_rtol,
            "scale_floor": spec.scale_floor,
        },
    )


def _compare_ulp(
    *,
    spec: FieldToleranceSpec,
    lhs: Any,
    rhs: Any,
) -> FieldComparison:
    try:
        lhs_arr = np.asarray(lhs)
        rhs_arr = np.asarray(rhs)
    except Exception as exc:
        return FieldComparison(
            path=spec.path,
            comparator=spec.comparator,
            requirement=spec.requirement,
            strict_ok=False,
            relaxed_ok=False,
            message=f"non-array value: {exc}",
        )

    lhs_shape = tuple(int(dim) for dim in lhs_arr.shape)
    rhs_shape = tuple(int(dim) for dim in rhs_arr.shape)
    if lhs_shape != rhs_shape:
        return FieldComparison(
            path=spec.path,
            comparator=spec.comparator,
            requirement=spec.requirement,
            strict_ok=False,
            relaxed_ok=False,
            lhs_shape=lhs_shape,
            rhs_shape=rhs_shape,
            message="shape mismatch",
        )

    dtype = _common_float_dtype(lhs_arr.dtype, rhs_arr.dtype)
    if dtype is None:
        return FieldComparison(
            path=spec.path,
            comparator=spec.comparator,
            requirement=spec.requirement,
            strict_ok=False,
            relaxed_ok=False,
            lhs_shape=lhs_shape,
            rhs_shape=rhs_shape,
            message="ULP comparator requires floating-point values",
        )

    lhs_cast = lhs_arr.astype(dtype, copy=False)
    rhs_cast = rhs_arr.astype(dtype, copy=False)
    max_ulp_error = _max_ulp_difference(
        lhs_arr=lhs_cast,
        rhs_arr=rhs_cast,
        equal_nan=spec.equal_nan,
    )
    strict_limit = int(spec.ulp_tol or 0)
    relaxed_limit = int(spec.relaxed_ulp_tol or strict_limit)
    strict_ok = bool(np.isfinite(max_ulp_error) and max_ulp_error <= strict_limit)
    relaxed_ok = bool(np.isfinite(max_ulp_error) and max_ulp_error <= relaxed_limit)
    metrics = _numeric_error_metrics(
        lhs_arr=lhs_cast.astype(np.float64, copy=False),
        rhs_arr=rhs_cast.astype(np.float64, copy=False),
        scale_floor=float(spec.scale_floor),
        equal_nan=spec.equal_nan,
    )
    if strict_ok:
        message = ""
    elif relaxed_ok:
        message = "strict ULP tolerance exceeded; relaxed envelope passed"
    else:
        message = "relaxed ULP tolerance exceeded"
    return FieldComparison(
        path=spec.path,
        comparator=spec.comparator,
        requirement=spec.requirement,
        strict_ok=strict_ok,
        relaxed_ok=relaxed_ok,
        lhs_shape=lhs_shape,
        rhs_shape=rhs_shape,
        max_abs_error=metrics["max_abs_error"],
        max_rel_error=metrics["max_rel_error"],
        max_ulp_error=int(max_ulp_error) if np.isfinite(max_ulp_error) else None,
        message=message,
        metadata={
            "dtype": np.dtype(dtype).name,
            "ulp_tol": strict_limit,
            "relaxed_ulp_tol": relaxed_limit,
        },
    )


def _compare_norm(
    *,
    spec: FieldToleranceSpec,
    lhs: Any,
    rhs: Any,
) -> FieldComparison:
    try:
        lhs_arr = np.asarray(lhs, dtype=np.float64)
        rhs_arr = np.asarray(rhs, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        return FieldComparison(
            path=spec.path,
            comparator=spec.comparator,
            requirement=spec.requirement,
            strict_ok=False,
            relaxed_ok=False,
            message=f"non-numeric value: {exc}",
        )

    lhs_shape = tuple(int(dim) for dim in lhs_arr.shape)
    rhs_shape = tuple(int(dim) for dim in rhs_arr.shape)
    if lhs_shape != rhs_shape:
        return FieldComparison(
            path=spec.path,
            comparator=spec.comparator,
            requirement=spec.requirement,
            strict_ok=False,
            relaxed_ok=False,
            lhs_shape=lhs_shape,
            rhs_shape=rhs_shape,
            message="shape mismatch",
        )

    order = _normalize_norm_order(spec.norm_order)
    norm_error = _relative_norm_error(
        lhs_arr=lhs_arr,
        rhs_arr=rhs_arr,
        order=order,
        scale_floor=float(spec.scale_floor),
        equal_nan=spec.equal_nan,
    )
    strict_tol = float(spec.strict_norm_tol or spec.strict_rtol or spec.strict_atol)
    relaxed_tol = float(spec.relaxed_norm_tol if spec.relaxed_norm_tol is not None else strict_tol)
    strict_ok = bool(np.isfinite(norm_error) and norm_error <= strict_tol)
    relaxed_ok = bool(np.isfinite(norm_error) and norm_error <= relaxed_tol)
    metrics = _numeric_error_metrics(
        lhs_arr=lhs_arr,
        rhs_arr=rhs_arr,
        scale_floor=float(spec.scale_floor),
        equal_nan=spec.equal_nan,
    )
    if strict_ok:
        message = ""
    elif relaxed_ok:
        message = "strict norm tolerance exceeded; relaxed envelope passed"
    else:
        message = "relaxed norm tolerance exceeded"
    return FieldComparison(
        path=spec.path,
        comparator=spec.comparator,
        requirement=spec.requirement,
        strict_ok=strict_ok,
        relaxed_ok=relaxed_ok,
        lhs_shape=lhs_shape,
        rhs_shape=rhs_shape,
        max_abs_error=metrics["max_abs_error"],
        max_rel_error=metrics["max_rel_error"],
        norm_error=norm_error if np.isfinite(norm_error) else None,
        message=message,
        metadata={
            "norm_order": spec.norm_order,
            "strict_norm_tol": strict_tol,
            "relaxed_norm_tol": relaxed_tol,
            "scale_floor": spec.scale_floor,
        },
    )


def _compare_distributional(
    *,
    spec: FieldToleranceSpec,
    lhs: Any,
    rhs: Any,
) -> FieldComparison:
    try:
        lhs_arr = np.asarray(lhs, dtype=np.float64).reshape(-1)
        rhs_arr = np.asarray(rhs, dtype=np.float64).reshape(-1)
    except (TypeError, ValueError) as exc:
        return FieldComparison(
            path=spec.path,
            comparator=spec.comparator,
            requirement=spec.requirement,
            strict_ok=False,
            relaxed_ok=False,
            message=f"non-numeric value: {exc}",
        )

    metric = (spec.distribution_metric or "ks").strip().lower()
    if metric == "ks":
        distribution_error = _kolmogorov_smirnov_distance(
            lhs_arr=lhs_arr,
            rhs_arr=rhs_arr,
            equal_nan=spec.equal_nan,
        )
    elif metric == "mean_std":
        distribution_error = _mean_std_distance(
            lhs_arr=lhs_arr,
            rhs_arr=rhs_arr,
            scale_floor=float(spec.scale_floor),
            equal_nan=spec.equal_nan,
        )
    else:
        return FieldComparison(
            path=spec.path,
            comparator=spec.comparator,
            requirement=spec.requirement,
            strict_ok=False,
            relaxed_ok=False,
            message=f"unsupported distribution metric: {metric}",
        )

    strict_tol = float(spec.strict_distribution_tol or spec.strict_rtol or spec.strict_atol)
    relaxed_tol = float(
        spec.relaxed_distribution_tol if spec.relaxed_distribution_tol is not None else strict_tol
    )
    strict_ok = bool(np.isfinite(distribution_error) and distribution_error <= strict_tol)
    relaxed_ok = bool(np.isfinite(distribution_error) and distribution_error <= relaxed_tol)
    if strict_ok:
        message = ""
    elif relaxed_ok:
        message = "strict distribution tolerance exceeded; relaxed envelope passed"
    else:
        message = "relaxed distribution tolerance exceeded"
    return FieldComparison(
        path=spec.path,
        comparator=spec.comparator,
        requirement=spec.requirement,
        strict_ok=strict_ok,
        relaxed_ok=relaxed_ok,
        lhs_shape=tuple(int(dim) for dim in lhs_arr.shape),
        rhs_shape=tuple(int(dim) for dim in rhs_arr.shape),
        distribution_error=distribution_error if np.isfinite(distribution_error) else None,
        message=message,
        metadata={
            "distribution_metric": metric,
            "strict_distribution_tol": strict_tol,
            "relaxed_distribution_tol": relaxed_tol,
        },
    )


def _numeric_error_metrics(
    *,
    lhs_arr: np.ndarray,
    rhs_arr: np.ndarray,
    scale_floor: float,
    equal_nan: bool,
) -> dict[str, float]:
    paired_nan_mask = (
        np.isnan(lhs_arr) & np.isnan(rhs_arr) if equal_nan else np.zeros_like(lhs_arr, dtype=bool)
    )
    finite_mask = np.isfinite(lhs_arr) & np.isfinite(rhs_arr) & ~paired_nan_mask
    if not np.any(finite_mask):
        return {"max_abs_error": 0.0, "max_rel_error": 0.0}
    abs_error = np.abs(lhs_arr - rhs_arr)
    scale = np.maximum(np.maximum(np.abs(lhs_arr), np.abs(rhs_arr)), scale_floor)
    rel_error = np.divide(
        abs_error,
        scale,
        out=np.zeros_like(abs_error),
        where=scale > 0,
    )
    if finite_mask.shape == ():
        return {
            "max_abs_error": float(abs_error),
            "max_rel_error": float(rel_error),
        }
    return {
        "max_abs_error": float(np.max(abs_error[finite_mask])),
        "max_rel_error": float(np.max(rel_error[finite_mask])),
    }


def _shape_of(value: Any) -> tuple[int, ...] | None:
    if isinstance(value, (str, bytes, bytearray)):
        return None
    try:
        return tuple(int(dim) for dim in np.asarray(value).shape)
    except Exception:
        return None


def _should_use_array_comparison(lhs: Any, rhs: Any) -> bool:
    arrayish = (np.ndarray, list, tuple)
    return (
        (
            hasattr(lhs, "shape")
            or hasattr(rhs, "shape")
            or isinstance(lhs, arrayish)
            or isinstance(rhs, arrayish)
        )
        and not isinstance(lhs, (str, bytes, bytearray))
        and not isinstance(rhs, (str, bytes, bytearray))
    )


def _common_float_dtype(lhs_dtype: np.dtype[Any], rhs_dtype: np.dtype[Any]) -> np.dtype[Any] | None:
    candidate = np.result_type(lhs_dtype, rhs_dtype)
    if not np.issubdtype(candidate, np.floating):
        return None
    if candidate == np.float16:
        return np.dtype(np.float16)
    if candidate == np.float32:
        return np.dtype(np.float32)
    return np.dtype(np.float64)


def _max_ulp_difference(
    *,
    lhs_arr: np.ndarray,
    rhs_arr: np.ndarray,
    equal_nan: bool,
) -> float:
    if lhs_arr.shape != rhs_arr.shape:
        return float("inf")

    paired_nan_mask = (
        np.isnan(lhs_arr) & np.isnan(rhs_arr) if equal_nan else np.zeros_like(lhs_arr, dtype=bool)
    )
    same_inf_mask = np.isinf(lhs_arr) & np.isinf(rhs_arr) & (lhs_arr == rhs_arr)
    finite_mask = ~(paired_nan_mask | same_inf_mask)
    if not np.any(finite_mask):
        return 0.0

    lhs_masked = lhs_arr[finite_mask]
    rhs_masked = rhs_arr[finite_mask]
    if np.any(np.isnan(lhs_masked)) or np.any(np.isnan(rhs_masked)):
        return float("inf")
    if np.any(np.isinf(lhs_masked)) or np.any(np.isinf(rhs_masked)):
        return float("inf")

    lhs_int = _ordered_int_view(lhs_masked)
    rhs_int = _ordered_int_view(rhs_masked)
    return float(np.max(np.abs(lhs_int - rhs_int), initial=0))


def _ordered_int_view(arr: np.ndarray) -> np.ndarray:
    if arr.dtype == np.float16:
        bits_dtype = np.int16
    elif arr.dtype == np.float32:
        bits_dtype = np.int32
    elif arr.dtype == np.float64:
        bits_dtype = np.int64
    else:  # pragma: no cover - guarded by _common_float_dtype
        raise TypeError(f"Unsupported dtype for ULP comparison: {arr.dtype}")
    ints = arr.view(bits_dtype)
    info = np.iinfo(bits_dtype)
    return np.where(ints < 0, info.min - ints, ints)


def _normalize_norm_order(order: str | float | None) -> float | str:
    if order is None:
        return "fro"
    if isinstance(order, (int, float)):
        return float(order)
    rendered = str(order).strip().lower()
    if rendered in {"fro", "f"}:
        return "fro"
    if rendered == "inf":
        return np.inf
    if rendered == "-inf":
        return -np.inf
    return float(rendered)


def _relative_norm_error(
    *,
    lhs_arr: np.ndarray,
    rhs_arr: np.ndarray,
    order: float | str,
    scale_floor: float,
    equal_nan: bool,
) -> float:
    paired_nan_mask = (
        np.isnan(lhs_arr) & np.isnan(rhs_arr) if equal_nan else np.zeros_like(lhs_arr, dtype=bool)
    )
    finite_mask = np.isfinite(lhs_arr) & np.isfinite(rhs_arr) & ~paired_nan_mask
    if not np.any(finite_mask):
        return 0.0
    lhs_clean = np.where(finite_mask, lhs_arr, 0.0)
    rhs_clean = np.where(finite_mask, rhs_arr, 0.0)
    diff = lhs_clean - rhs_clean
    diff_norm = _safe_norm(diff, order)
    lhs_norm = _safe_norm(lhs_clean, order)
    rhs_norm = _safe_norm(rhs_clean, order)
    denom = max(lhs_norm, rhs_norm, scale_floor)
    if denom <= 0:
        return 0.0
    return float(diff_norm / denom)


def _safe_norm(arr: np.ndarray, order: float | str) -> float:
    if arr.ndim <= 1:
        return float(np.linalg.norm(arr.reshape(-1), ord=order if order != "fro" else 2))
    if order == "fro":
        return float(np.linalg.norm(arr, ord="fro"))
    return float(np.linalg.norm(arr.reshape(-1), ord=order))


def _kolmogorov_smirnov_distance(
    *,
    lhs_arr: np.ndarray,
    rhs_arr: np.ndarray,
    equal_nan: bool,
) -> float:
    lhs_clean = _distributional_values(lhs_arr, equal_nan=equal_nan)
    rhs_clean = _distributional_values(rhs_arr, equal_nan=equal_nan)
    if lhs_clean.size == 0 and rhs_clean.size == 0:
        return 0.0
    if lhs_clean.size == 0 or rhs_clean.size == 0:
        return float("inf")
    lhs_sorted = np.sort(lhs_clean)
    rhs_sorted = np.sort(rhs_clean)
    support = np.sort(np.concatenate((lhs_sorted, rhs_sorted)))
    lhs_cdf = np.searchsorted(lhs_sorted, support, side="right") / lhs_sorted.size
    rhs_cdf = np.searchsorted(rhs_sorted, support, side="right") / rhs_sorted.size
    return float(np.max(np.abs(lhs_cdf - rhs_cdf), initial=0.0))


def _mean_std_distance(
    *,
    lhs_arr: np.ndarray,
    rhs_arr: np.ndarray,
    scale_floor: float,
    equal_nan: bool,
) -> float:
    lhs_clean = _distributional_values(lhs_arr, equal_nan=equal_nan)
    rhs_clean = _distributional_values(rhs_arr, equal_nan=equal_nan)
    if lhs_clean.size == 0 and rhs_clean.size == 0:
        return 0.0
    if lhs_clean.size == 0 or rhs_clean.size == 0:
        return float("inf")
    mean_scale = max(abs(float(np.mean(lhs_clean))), abs(float(np.mean(rhs_clean))), scale_floor)
    std_scale = max(abs(float(np.std(lhs_clean))), abs(float(np.std(rhs_clean))), scale_floor)
    mean_error = abs(float(np.mean(lhs_clean) - np.mean(rhs_clean))) / mean_scale
    std_error = abs(float(np.std(lhs_clean) - np.std(rhs_clean))) / std_scale
    return float(max(mean_error, std_error))


def _distributional_values(arr: np.ndarray, *, equal_nan: bool) -> np.ndarray:
    if equal_nan:
        return arr[np.isfinite(arr)]
    return arr[~np.isnan(arr) & np.isfinite(arr)]


__all__ = ["compare_field_values"]
