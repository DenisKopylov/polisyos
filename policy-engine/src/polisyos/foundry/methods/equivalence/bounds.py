"""Tolerance-bound derivation for backend equivalence certificates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from polisyos.foundry.methods.backends.protocol import MethodResult
from polisyos.foundry.methods.equivalence.protocol import (
    ComparatorKind,
    FieldRequirement,
    FieldToleranceSpec,
)


@dataclass(frozen=True, slots=True)
class FieldCalibrationStats:
    """Empirical error summary for one field path across a calibration battery."""

    path: str
    comparator: ComparatorKind
    requirement: FieldRequirement
    case_count: int
    strict_quantile: float
    abs_error_p50: float
    abs_error_p95: float
    abs_error_p99: float
    abs_error_max: float
    rel_error_p50: float
    rel_error_p95: float
    rel_error_p99: float
    rel_error_max: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "comparator": self.comparator.value,
            "requirement": self.requirement.value,
            "case_count": self.case_count,
            "strict_quantile": self.strict_quantile,
            "abs_error_p50": self.abs_error_p50,
            "abs_error_p95": self.abs_error_p95,
            "abs_error_p99": self.abs_error_p99,
            "abs_error_max": self.abs_error_max,
            "rel_error_p50": self.rel_error_p50,
            "rel_error_p95": self.rel_error_p95,
            "rel_error_p99": self.rel_error_p99,
            "rel_error_max": self.rel_error_max,
        }


@dataclass(frozen=True, slots=True)
class EquivalencePolicy:
    """Policy controlling calibration scope and tolerance synthesis."""

    strict_quantile: float = 0.99
    relaxed_multiplier: float = 10.0
    relaxed_headroom: float = 1.0e-12
    scale_floor: float = 1.0e-12
    equal_nan: bool = True
    confidence: float | None = 0.95
    pin_runtime_fingerprints: bool = False
    certificate_ttl_days: int | None = 90
    comparator_overrides: Mapping[str, ComparatorKind] = field(default_factory=dict)
    exact_paths: tuple[str, ...] = ()
    advisory_paths: tuple[str, ...] = ()
    diagnostic_only_paths: tuple[str, ...] = ()
    include_prefixes: tuple[str, ...] = ()
    exclude_prefixes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not (0.0 < self.strict_quantile <= 1.0):
            raise ValueError("strict_quantile must be in (0, 1]")
        if self.relaxed_multiplier < 1.0:
            raise ValueError("relaxed_multiplier must be >= 1")
        if self.relaxed_headroom < 0.0:
            raise ValueError("relaxed_headroom must be non-negative")
        if self.scale_floor < 0.0:
            raise ValueError("scale_floor must be non-negative")
        if self.confidence is not None and not (0.0 < self.confidence <= 1.0):
            raise ValueError("confidence must be in (0, 1]")
        if self.certificate_ttl_days is not None and self.certificate_ttl_days <= 0:
            raise ValueError("certificate_ttl_days must be positive when provided")


def derive_pairwise_budget(
    *,
    source_result: MethodResult,
    target_result: MethodResult,
) -> tuple[float, float]:
    """Return one conservative base abs/rel budget for a backend result pair."""

    expected_budgets = (
        _expected_budget(source_result),
        _expected_budget(target_result),
    )
    abs_candidates = [
        float(value)
        for budget in expected_budgets
        for key, value in budget.items()
        if key.endswith("_abs_tol") and value is not None
    ]
    rel_candidates = [
        float(value)
        for budget in expected_budgets
        for key, value in budget.items()
        if key.endswith("_rel_tol") and value is not None
    ]
    return max(abs_candidates, default=0.0), max(rel_candidates, default=0.0)


def derive_field_tolerance_spec(
    *,
    path: str,
    samples: list[tuple[Any, Any]],
    base_abs_tol: float,
    base_rel_tol: float,
    policy: EquivalencePolicy,
) -> tuple[FieldToleranceSpec, FieldCalibrationStats]:
    """Synthesize one field-level tolerance spec from calibration samples."""

    comparator = _infer_comparator(path=path, samples=samples, policy=policy)
    requirement = _infer_requirement(path=path, policy=policy)

    if comparator is ComparatorKind.EXACT:
        exact_failures = sum(
            not _exact_match(lhs, rhs, equal_nan=policy.equal_nan) for lhs, rhs in samples
        )
        stats = FieldCalibrationStats(
            path=path,
            comparator=comparator,
            requirement=requirement,
            case_count=len(samples),
            strict_quantile=policy.strict_quantile,
            abs_error_p50=0.0,
            abs_error_p95=0.0,
            abs_error_p99=0.0,
            abs_error_max=float(exact_failures > 0),
            rel_error_p50=0.0,
            rel_error_p95=0.0,
            rel_error_p99=0.0,
            rel_error_max=float(exact_failures > 0),
        )
        return (
            FieldToleranceSpec(
                path=path,
                comparator=comparator,
                requirement=requirement,
                strict_atol=0.0,
                strict_rtol=0.0,
                relaxed_atol=0.0,
                relaxed_rtol=0.0,
                equal_nan=policy.equal_nan,
                scale_floor=policy.scale_floor,
                confidence=policy.confidence,
                metadata={"calibration_stats": stats.as_dict()},
            ),
            stats,
        )

    abs_errors: list[float] = []
    rel_errors: list[float] = []
    for lhs, rhs in samples:
        abs_error, rel_error = _numeric_errors(
            lhs=lhs,
            rhs=rhs,
            scale_floor=policy.scale_floor,
            equal_nan=policy.equal_nan,
        )
        abs_errors.append(abs_error)
        rel_errors.append(rel_error)

    strict_abs = max(float(base_abs_tol), _quantile(abs_errors, policy.strict_quantile))
    strict_rel = max(float(base_rel_tol), _quantile(rel_errors, policy.strict_quantile))
    relaxed_abs = max(
        strict_abs,
        strict_abs * policy.relaxed_multiplier,
        strict_abs + policy.relaxed_headroom,
    )
    relaxed_rel = max(
        strict_rel,
        strict_rel * policy.relaxed_multiplier,
        strict_rel + policy.relaxed_headroom,
    )

    stats = FieldCalibrationStats(
        path=path,
        comparator=comparator,
        requirement=requirement,
        case_count=len(samples),
        strict_quantile=policy.strict_quantile,
        abs_error_p50=_quantile(abs_errors, 0.50),
        abs_error_p95=_quantile(abs_errors, 0.95),
        abs_error_p99=_quantile(abs_errors, 0.99),
        abs_error_max=max(abs_errors, default=0.0),
        rel_error_p50=_quantile(rel_errors, 0.50),
        rel_error_p95=_quantile(rel_errors, 0.95),
        rel_error_p99=_quantile(rel_errors, 0.99),
        rel_error_max=max(rel_errors, default=0.0),
    )
    return (
        FieldToleranceSpec(
            path=path,
            comparator=ComparatorKind.ABS_REL,
            requirement=requirement,
            strict_atol=strict_abs,
            strict_rtol=strict_rel,
            relaxed_atol=relaxed_abs,
            relaxed_rtol=relaxed_rel,
            scale_floor=policy.scale_floor,
            equal_nan=policy.equal_nan,
            confidence=policy.confidence,
            metadata={"calibration_stats": stats.as_dict()},
        ),
        stats,
    )


def _expected_budget(result: MethodResult) -> Mapping[str, Any]:
    observed = dict(result.reproducibility.observed_tolerance_budget or {})
    if observed.get("expected_budget"):
        return dict(observed["expected_budget"])
    artifact = result.artifacts.get("backend_runtime_fingerprint")
    if isinstance(artifact, Mapping):
        observed_artifact = artifact.get("observed_tolerance_budget")
        if isinstance(observed_artifact, Mapping) and observed_artifact.get("expected_budget"):
            return dict(observed_artifact["expected_budget"])
        if isinstance(artifact.get("tolerance_budget"), Mapping):
            return dict(artifact["tolerance_budget"])
    return {}


def _infer_comparator(
    *,
    path: str,
    samples: list[tuple[Any, Any]],
    policy: EquivalencePolicy,
) -> ComparatorKind:
    override = policy.comparator_overrides.get(path)
    if override is not None:
        return override
    if _path_matches(path, policy.exact_paths):
        return ComparatorKind.EXACT
    if not samples:
        return ComparatorKind.EXACT
    lhs, rhs = samples[0]
    if _is_float_like(lhs) or _is_float_like(rhs):
        return ComparatorKind.ABS_REL
    return ComparatorKind.EXACT


def _infer_requirement(
    *,
    path: str,
    policy: EquivalencePolicy,
) -> FieldRequirement:
    if _path_matches(path, policy.diagnostic_only_paths):
        return FieldRequirement.DIAGNOSTIC_ONLY
    if _path_matches(path, policy.advisory_paths):
        return FieldRequirement.ADVISORY
    if path.startswith("output.") or path.startswith("slot_outputs."):
        return FieldRequirement.REQUIRED
    return FieldRequirement.DIAGNOSTIC_ONLY


def _path_matches(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}.") for prefix in prefixes)


def _is_float_like(value: Any) -> bool:
    try:
        arr = np.asarray(value)
    except Exception:
        return isinstance(value, float)
    return bool(np.issubdtype(arr.dtype, np.floating))


def _exact_match(lhs: Any, rhs: Any, *, equal_nan: bool) -> bool:
    if (
        hasattr(lhs, "shape")
        or hasattr(rhs, "shape")
        or isinstance(lhs, (list, tuple))
        or isinstance(rhs, (list, tuple))
    ):
        lhs_arr = np.asarray(lhs)
        rhs_arr = np.asarray(rhs)
        if lhs_arr.shape != rhs_arr.shape:
            return False
        try:
            return bool(np.array_equal(lhs_arr, rhs_arr, equal_nan=equal_nan))
        except TypeError:
            return bool(np.array_equal(lhs_arr, rhs_arr))
    return bool(lhs == rhs)


def _numeric_errors(
    *,
    lhs: Any,
    rhs: Any,
    scale_floor: float,
    equal_nan: bool,
) -> tuple[float, float]:
    lhs_arr = np.asarray(lhs, dtype=np.float64)
    rhs_arr = np.asarray(rhs, dtype=np.float64)
    if lhs_arr.shape != rhs_arr.shape:
        return float("inf"), float("inf")

    abs_err = np.abs(lhs_arr - rhs_arr)
    scale = np.maximum(np.abs(rhs_arr), float(scale_floor))
    rel_err = abs_err / scale

    if equal_nan:
        mask = ~(np.isnan(lhs_arr) & np.isnan(rhs_arr))
        abs_err = abs_err[mask]
        rel_err = rel_err[mask]
    finite_mask = np.isfinite(abs_err) & np.isfinite(rel_err)
    if abs_err.size == 0 or not np.any(finite_mask):
        return 0.0, 0.0
    return float(np.max(abs_err[finite_mask])), float(np.max(rel_err[finite_mask]))


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    return float(np.quantile(np.asarray(values, dtype=np.float64), q))


__all__ = [
    "EquivalencePolicy",
    "FieldCalibrationStats",
    "derive_field_tolerance_spec",
    "derive_pairwise_budget",
]
