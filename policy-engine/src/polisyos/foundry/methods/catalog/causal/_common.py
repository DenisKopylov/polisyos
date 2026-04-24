"""Public causal common module API."""

from __future__ import annotations

from typing import Any

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    DiagnosticTest,
    EstimationStatus,
)


def bootstrap_ci(
    estimates: np.ndarray,
    confidence_level: float = 0.95,
) -> tuple[float, float]:
    """Bootstrap ci helper."""
    if not (0.0 < float(confidence_level) < 1.0):
        raise ValueError("confidence_level must be in (0, 1)")
    arr = np.asarray(estimates, dtype=float).reshape(-1)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        raise ValueError("bootstrap_ci requires at least one finite estimate")
    if arr.size == 1:
        point = float(arr[0])
        return point, point
    alpha = 1.0 - confidence_level
    lower = np.percentile(arr, 100.0 * alpha / 2.0)
    upper = np.percentile(arr, 100.0 * (1.0 - alpha / 2.0))
    return float(lower), float(upper)


def compute_rmspe(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Compute rmspe helper."""
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def compute_cohen_d(
    effect: float,
    treated_outcome: np.ndarray,
    control_outcome: np.ndarray,
) -> float:
    """Compute cohen d helper."""
    pooled_std = np.sqrt((np.var(treated_outcome) + np.var(control_outcome)) / 2.0)
    return float(effect / pooled_std) if pooled_std > 0 else 0.0


def build_success_report(
    *,
    method: CausalMethod,
    estimand: str,
    point_estimate: float,
    confidence_interval: tuple[float, float],
    inference_method: str,
    sample_size: int,
    n_treated: int,
    n_control: int,
    pre_periods: int,
    post_periods: int,
    assumptions: dict[str, str],
    diagnostics: list[DiagnosticTest] | None = None,
    **kwargs: Any,
) -> CausalEffectReport:
    """Build success report."""
    payload = dict(kwargs)
    payload.setdefault("diagnostics", diagnostics or [])
    point = float(point_estimate)
    lower = float(confidence_interval[0])
    upper = float(confidence_interval[1])
    if lower > upper:
        lower, upper = upper, lower
    if point < lower:
        lower = point
    elif point > upper:
        upper = point

    return CausalEffectReport(
        method=method,
        status=EstimationStatus.SUCCESS,
        estimand=estimand,
        point_estimate=point,
        confidence_interval=(lower, upper),
        inference_method=inference_method,
        sample_size=sample_size,
        n_treated=n_treated,
        n_control=n_control,
        pre_periods=pre_periods,
        post_periods=post_periods,
        assumptions=assumptions,
        **payload,
    )


def build_failure_report(
    *,
    method: CausalMethod,
    status: EstimationStatus,
    reason: str,
    estimand: str,
    sample_size: int,
    n_treated: int,
    n_control: int,
    pre_periods: int,
    post_periods: int,
    assumptions: dict[str, str],
    diagnostics: list[DiagnosticTest] | None = None,
    **kwargs: Any,
) -> CausalEffectReport:
    """Build failure report."""
    payload = dict(kwargs)
    payload.setdefault("diagnostics", diagnostics or [])
    meta = dict(payload.get("metadata", {}))
    meta.setdefault("error", reason)
    payload["metadata"] = meta
    return CausalEffectReport(
        method=method,
        status=status,
        status_reason=reason,
        estimand=estimand,
        inference_method="none",
        sample_size=sample_size,
        n_treated=n_treated,
        n_control=n_control,
        pre_periods=pre_periods,
        post_periods=post_periods,
        assumptions=assumptions,
        **payload,
    )


def wrap_causal_output(
    report: CausalEffectReport,
    *,
    warnings: list[str] | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wrap causal output helper."""
    output: dict[str, Any] = {
        "report": report,
        "envelope": report.to_uncertainty_envelope(),
        "warnings": list(warnings or []),
        "__determinism_tier__": DeterminismTier.STATISTICAL,
    }
    if extras:
        output.update(extras)
    return output


__all__ = [
    "bootstrap_ci",
    "build_failure_report",
    "build_success_report",
    "compute_cohen_d",
    "compute_rmspe",
    "wrap_causal_output",
]
