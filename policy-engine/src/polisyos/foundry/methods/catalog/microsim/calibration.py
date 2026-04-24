"""Public microsim calibration module API."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np

try:
    from scipy.optimize import BFGS, minimize
    from scipy.stats import chi2

    _SCIPY_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only in reduced runtimes.
    BFGS = None
    minimize = None
    chi2 = None
    _SCIPY_AVAILABLE = False

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
from polisyos.foundry.methods.catalog._payloads import extract_model_payload
from polisyos.foundry.methods.catalog._phase1_artifacts import resolve_artifact_store
from polisyos.foundry.methods.catalog.survey._raking_core import (
    build_raking_design_from_feature_targets,
    run_raking_with_fallbacks,
)
from polisyos.ir.analytics.microsim_calibration import (
    persist_microsim_calibration_report,
    report_from_target_compatibility,
)
from polisyos.ir.analytics.survey_raking import SurveyRakingDiagnosticReport

from .protocols import (
    ReweightingCompatibilityReason,
    ReweightingCompatibilityStatus,
    ReweightingCompatibilityTestMethod,
    ReweightingResult,
    ReweightingTargetCompatibility,
    ReweightingTargetGap,
    ReweightingTargetKind,
    ReweightingTargetSpec,
    SurveyMicroData,
)

_EPS = 1e-12
_LINEAR_TARGET_KINDS = {
    ReweightingTargetKind.TOTAL_WEIGHT,
    ReweightingTargetKind.MEAN_INCOME,
    ReweightingTargetKind.FEATURE_MEAN,
}
_DISTRIBUTIONAL_TARGET_KINDS = {
    ReweightingTargetKind.INCOME_QUANTILE,
    ReweightingTargetKind.WEIGHT_QUANTILE,
    ReweightingTargetKind.WEIGHT_GINI,
}


@dataclass(frozen=True)
class _CalibrationContext:
    data: SurveyMicroData
    specs: tuple[ReweightingTargetSpec, ...]
    base_weights: np.ndarray
    target_total: float
    lower_bound: float
    effective_upper_bound: float | None
    max_weight_ratio: float | None
    design: np.ndarray
    basis_columns: tuple[str, ...]
    solver: str
    max_iterations: int
    objective_tolerance: float


@dataclass(frozen=True)
class _SolveResult:
    theta: np.ndarray
    weights: np.ndarray
    raw_moments: np.ndarray
    standardized_moments: np.ndarray
    objective_value: float
    solver_status: str
    solver_message: str | None
    iterations: int | None
    method: str
    weighting_matrix: np.ndarray | None = None
    covariance: np.ndarray | None = None


def _is_none_like(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value == "None")


def _survey_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=SurveyMicroData,
        nested_keys=("survey_micro_data",),
    )


def _validate_quantile(q: float | None, *, label: str) -> float:
    if q is None:
        raise ValueError(f"{label} requires quantile to be provided")
    q = float(q)
    if not 0.0 <= q <= 1.0:
        raise ValueError(f"{label} quantile must lie in [0, 1]")
    return q


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    order = np.argsort(values, kind="mergesort")
    x = values[order]
    w = weights[order]
    total = float(np.sum(w))
    if x.size == 0 or total <= _EPS:
        return 0.0
    cdf = (np.cumsum(w) - 0.5 * w) / total
    return float(np.interp(quantile, cdf, x, left=x[0], right=x[-1]))


def _gini(values: np.ndarray) -> float:
    x = np.sort(np.asarray(values, dtype=float))
    if x.size == 0 or np.sum(x) <= _EPS:
        return 0.0
    ranks = np.arange(1.0, float(x.size) + 1.0, dtype=float)
    total = float(np.sum(x))
    gini = (2.0 * np.sum(ranks * x)) / (x.size * total) - (x.size + 1.0) / x.size
    return float(np.clip(gini, 0.0, 1.0))


def _safe_standardize(vector: np.ndarray) -> np.ndarray:
    arr = np.asarray(vector, dtype=float)
    std = float(np.std(arr))
    if std <= _EPS:
        return np.zeros_like(arr, dtype=float)
    return (arr - float(np.mean(arr))) / std


def _default_tolerance(spec: ReweightingTargetSpec) -> float:
    base = max(abs(float(spec.target_value)), 1.0)
    if spec.kind in _LINEAR_TARGET_KINDS:
        return 1e-6 * base
    if spec.kind in {
        ReweightingTargetKind.INCOME_QUANTILE,
        ReweightingTargetKind.WEIGHT_QUANTILE,
    }:
        return 1e-4 * base
    return 1e-4


def _target_scale(spec: ReweightingTargetSpec) -> float:
    if spec.scale is not None:
        return max(abs(float(spec.scale)), _EPS)
    tolerance = spec.tolerance if spec.tolerance is not None else _default_tolerance(spec)
    return max(float(tolerance), _EPS)


def _default_target_name(payload: Mapping[str, Any]) -> str:
    kind = str(payload["kind"])
    if kind == ReweightingTargetKind.FEATURE_MEAN.value:
        feature_name = payload.get("feature_name")
        feature_index = payload.get("feature_index")
        suffix = feature_name if feature_name is not None else f"feature_{feature_index}"
        return f"feature_mean:{suffix}"
    if kind in {
        ReweightingTargetKind.INCOME_QUANTILE.value,
        ReweightingTargetKind.WEIGHT_QUANTILE.value,
    }:
        quantile = payload.get("quantile")
        return f"{kind}:q{int(round(float(quantile) * 100.0))}"
    return kind


def _subset_survey_data(data: SurveyMicroData, indices: np.ndarray) -> SurveyMicroData:
    updates: dict[str, Any] = {
        "market_income": np.asarray(data.market_income, dtype=float)[indices],
        "weights": np.asarray(data.weights, dtype=float)[indices],
        "features": None if data.features is None else np.asarray(data.features)[indices],
        "household_ids": None
        if data.household_ids is None
        else np.asarray(data.household_ids)[indices],
    }
    for field_name in (
        "period_id",
        "cohort_id",
        "region_id",
        "policy_id",
        "reform_id",
        "instrument_z",
        "income_repeat_measure",
        "taxrate_repeat_measure",
    ):
        value = getattr(data, field_name, None)
        if value is None:
            continue
        updates[field_name] = np.asarray(value)[indices]
    return data.model_copy(update=updates)


def _effective_upper_bound(
    *,
    n_obs: int,
    target_total: float,
    lower_bound: float,
    upper_bound: float | None,
    max_weight_ratio: float | None,
) -> float | None:
    if upper_bound is not None:
        return float(upper_bound)
    if max_weight_ratio is None:
        return None
    mean_weight = float(target_total) / max(float(n_obs), 1.0)
    return max(lower_bound, float(max_weight_ratio) * mean_weight)


def _project_weights(
    raw_weights: np.ndarray,
    *,
    target_total: float,
    lower_bound: float,
    effective_upper_bound: float | None,
) -> np.ndarray:
    raw = np.maximum(np.asarray(raw_weights, dtype=float), _EPS)
    n_obs = raw.shape[0]
    if n_obs == 0:
        return raw

    lower = np.full(n_obs, lower_bound, dtype=float)
    if effective_upper_bound is None:
        scale = float(target_total) / max(float(np.sum(raw)), _EPS)
        return np.maximum(lower_bound, raw * scale)

    upper = np.full(n_obs, effective_upper_bound, dtype=float)
    min_total = float(np.sum(lower))
    max_total = float(np.sum(upper))
    if target_total <= min_total + _EPS:
        return lower.copy()
    if target_total >= max_total - _EPS:
        return upper.copy()

    weights = np.empty_like(raw)
    free = np.ones(n_obs, dtype=bool)
    remaining_total = float(target_total)

    while True:
        if not np.any(free):
            break
        raw_free = raw[free]
        scale = remaining_total / max(float(np.sum(raw_free)), _EPS)
        candidate = raw_free * scale
        low_hits = candidate <= lower[free] + _EPS
        high_hits = candidate >= upper[free] - _EPS
        if not np.any(low_hits | high_hits):
            weights[free] = candidate
            break
        free_indices = np.flatnonzero(free)
        if np.any(low_hits):
            low_idx = free_indices[low_hits]
            weights[low_idx] = lower[low_idx]
            remaining_total -= float(np.sum(weights[low_idx]))
            free[low_idx] = False
        if np.any(high_hits):
            high_idx = free_indices[high_hits]
            weights[high_idx] = upper[high_idx]
            remaining_total -= float(np.sum(weights[high_idx]))
            free[high_idx] = False

    weights = np.clip(weights, lower_bound, effective_upper_bound)
    correction = float(target_total) - float(np.sum(weights))
    if abs(correction) > 1e-8:
        adjustable = (
            (weights > lower_bound + 1e-8)
            if correction < 0.0
            else (weights < effective_upper_bound - 1e-8)
        )
        if np.any(adjustable):
            weights[adjustable] += correction / float(np.sum(adjustable))
            weights = np.clip(weights, lower_bound, effective_upper_bound)
    return weights


def _build_target_specs(
    data: SurveyMicroData, params: Mapping[str, Any]
) -> list[ReweightingTargetSpec]:
    current_total = float(np.sum(np.asarray(data.weights, dtype=float)))
    current_mean = float(
        np.sum(np.asarray(data.weights, dtype=float) * np.asarray(data.market_income, dtype=float))
        / max(current_total, _EPS)
    )

    explicit_targets: list[ReweightingTargetSpec] = []
    targets_param = params.get("targets")
    if not _is_none_like(targets_param):
        if not isinstance(targets_param, (list, tuple)):
            raise ValueError("targets must be a list of target specifications")
        for raw_target in targets_param:
            if isinstance(raw_target, ReweightingTargetSpec):
                spec = raw_target
            else:
                if not isinstance(raw_target, Mapping):
                    raise ValueError("each target specification must be a mapping")
                payload = dict(raw_target)
                payload.setdefault("name", _default_target_name(payload))
                spec = ReweightingTargetSpec.model_validate(payload)
            explicit_targets.append(spec)

    specs = list(explicit_targets)
    kinds_present = {spec.kind for spec in specs}
    if (
        not _is_none_like(params.get("target_total_weight"))
        and ReweightingTargetKind.TOTAL_WEIGHT not in kinds_present
    ):
        specs.append(
            ReweightingTargetSpec(
                name="total_weight",
                kind=ReweightingTargetKind.TOTAL_WEIGHT,
                target_value=float(params["target_total_weight"]),
            )
        )
        kinds_present.add(ReweightingTargetKind.TOTAL_WEIGHT)
    if (
        not _is_none_like(params.get("target_mean_income"))
        and ReweightingTargetKind.MEAN_INCOME not in kinds_present
    ):
        specs.append(
            ReweightingTargetSpec(
                name="mean_income",
                kind=ReweightingTargetKind.MEAN_INCOME,
                target_value=float(params["target_mean_income"]),
            )
        )
        kinds_present.add(ReweightingTargetKind.MEAN_INCOME)

    if not specs:
        specs = [
            ReweightingTargetSpec(
                name="total_weight",
                kind=ReweightingTargetKind.TOTAL_WEIGHT,
                target_value=current_total,
            ),
            ReweightingTargetSpec(
                name="mean_income",
                kind=ReweightingTargetKind.MEAN_INCOME,
                target_value=current_mean,
            ),
        ]
        kinds_present = {spec.kind for spec in specs}

    if ReweightingTargetKind.TOTAL_WEIGHT not in kinds_present:
        specs.insert(
            0,
            ReweightingTargetSpec(
                name="total_weight",
                kind=ReweightingTargetKind.TOTAL_WEIGHT,
                target_value=current_total,
            ),
        )

    resolved_specs: list[ReweightingTargetSpec] = []
    for spec in specs:
        updates: dict[str, Any] = {}
        if spec.tolerance is None:
            updates["tolerance"] = _default_tolerance(spec)
        if spec.kind in {
            ReweightingTargetKind.INCOME_QUANTILE,
            ReweightingTargetKind.WEIGHT_QUANTILE,
        }:
            updates["quantile"] = _validate_quantile(spec.quantile, label=spec.name)
        if spec.kind == ReweightingTargetKind.FEATURE_MEAN:
            if data.features is None:
                raise ValueError("feature_mean targets require SurveyMicroData.features")
            if spec.feature_name is not None:
                if data.feature_names is None:
                    raise ValueError(
                        "feature_mean target uses feature_name but feature_names are missing"
                    )
                if spec.feature_name not in data.feature_names:
                    raise ValueError(
                        f"unknown feature_name '{spec.feature_name}' in target '{spec.name}'"
                    )
                updates["feature_index"] = data.feature_names.index(spec.feature_name)
            if (
                spec.feature_index
                if spec.feature_index is not None
                else updates.get("feature_index")
            ) is None:
                raise ValueError("feature_mean targets require feature_index or feature_name")
        resolved_specs.append(spec.model_copy(update=updates))
    return resolved_specs


def _target_total(specs: Sequence[ReweightingTargetSpec]) -> float:
    for spec in specs:
        if spec.kind == ReweightingTargetKind.TOTAL_WEIGHT:
            return float(spec.target_value)
    raise ValueError("target specifications must include total_weight")


def _build_design_matrix(
    data: SurveyMicroData,
    specs: Sequence[ReweightingTargetSpec],
    base_weights: np.ndarray,
) -> tuple[np.ndarray, tuple[str, ...]]:
    income = np.asarray(data.market_income, dtype=float)
    columns: list[np.ndarray] = []
    labels: list[str] = []

    needs_income = any(spec.kind == ReweightingTargetKind.MEAN_INCOME for spec in specs)
    needs_feature = any(spec.kind == ReweightingTargetKind.FEATURE_MEAN for spec in specs)
    needs_distributional = any(spec.kind in _DISTRIBUTIONAL_TARGET_KINDS for spec in specs)

    if data.instrument_z is not None:
        instruments = np.asarray(data.instrument_z, dtype=float)
        if instruments.ndim == 1:
            instruments = instruments[:, None]
        for column_index in range(instruments.shape[1]):
            columns.append(_safe_standardize(instruments[:, column_index]))
            labels.append(
                "instrument_z" if instruments.shape[1] == 1 else f"instrument_z_{column_index}"
            )

    if needs_income or needs_distributional:
        columns.append(_safe_standardize(income))
        labels.append("income")

    if needs_distributional:
        income_rank = np.argsort(np.argsort(income, kind="mergesort"), kind="mergesort").astype(
            float
        )
        columns.append(_safe_standardize(income_rank))
        labels.append("income_rank")

        log_base_weights = np.log(np.maximum(base_weights, _EPS))
        columns.append(_safe_standardize(log_base_weights))
        labels.append("log_base_weight")

        centered_income = _safe_standardize(income**2)
        columns.append(centered_income)
        labels.append("income_sq")

    if needs_feature and data.features is not None:
        feature_indices = sorted(
            {
                int(spec.feature_index)
                for spec in specs
                if spec.kind == ReweightingTargetKind.FEATURE_MEAN
                and spec.feature_index is not None
            }
        )
        for feature_index in feature_indices:
            column = _safe_standardize(np.asarray(data.features[:, feature_index], dtype=float))
            columns.append(column)
            if data.feature_names is not None and feature_index < len(data.feature_names):
                labels.append(str(data.feature_names[feature_index]))
            else:
                labels.append(f"feature_{feature_index}")

    if not columns:
        columns.append(_safe_standardize(np.arange(income.shape[0], dtype=float)))
        labels.append("observation_rank")

    return np.column_stack(columns), tuple(labels)


def _make_context(
    data: SurveyMicroData,
    specs: Sequence[ReweightingTargetSpec],
    *,
    lower_bound: float,
    upper_bound: float | None,
    max_weight_ratio: float | None,
    solver: str,
    max_iterations: int,
    objective_tolerance: float,
) -> _CalibrationContext:
    base_weights = np.asarray(data.weights, dtype=float)
    target_total = _target_total(specs)
    effective_upper = _effective_upper_bound(
        n_obs=base_weights.shape[0],
        target_total=target_total,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        max_weight_ratio=max_weight_ratio,
    )
    design, labels = _build_design_matrix(data, specs, base_weights)
    return _CalibrationContext(
        data=data,
        specs=tuple(specs),
        base_weights=base_weights,
        target_total=target_total,
        lower_bound=lower_bound,
        effective_upper_bound=effective_upper,
        max_weight_ratio=max_weight_ratio,
        design=design,
        basis_columns=labels,
        solver=solver,
        max_iterations=max_iterations,
        objective_tolerance=objective_tolerance,
    )


def _evaluate_target(
    spec: ReweightingTargetSpec, data: SurveyMicroData, weights: np.ndarray
) -> float:
    income = np.asarray(data.market_income, dtype=float)
    total = max(float(np.sum(weights)), _EPS)
    if spec.kind == ReweightingTargetKind.TOTAL_WEIGHT:
        return float(np.sum(weights))
    if spec.kind == ReweightingTargetKind.MEAN_INCOME:
        return float(np.sum(weights * income) / total)
    if spec.kind == ReweightingTargetKind.FEATURE_MEAN:
        feature = np.asarray(data.features[:, int(spec.feature_index)], dtype=float)
        return float(np.sum(weights * feature) / total)
    if spec.kind == ReweightingTargetKind.INCOME_QUANTILE:
        return _weighted_quantile(income, weights, float(spec.quantile))
    if spec.kind == ReweightingTargetKind.WEIGHT_QUANTILE:
        return float(np.quantile(np.asarray(weights, dtype=float), float(spec.quantile)))
    if spec.kind == ReweightingTargetKind.WEIGHT_GINI:
        return _gini(np.asarray(weights, dtype=float))
    raise ValueError(f"unsupported target kind '{spec.kind}'")


def _moment_vector(ctx: _CalibrationContext, weights: np.ndarray) -> np.ndarray:
    return np.asarray(
        [
            _evaluate_target(spec, ctx.data, weights) - float(spec.target_value)
            for spec in ctx.specs
        ],
        dtype=float,
    )


def _standardized_moment_vector(ctx: _CalibrationContext, weights: np.ndarray) -> np.ndarray:
    raw = _moment_vector(ctx, weights)
    scales = np.asarray([_target_scale(spec) for spec in ctx.specs], dtype=float)
    return raw / np.maximum(scales, _EPS)


def _weights_from_theta(ctx: _CalibrationContext, theta: np.ndarray) -> np.ndarray:
    if ctx.design.shape[1] == 0:
        raw = ctx.base_weights
    else:
        raw = ctx.base_weights * np.exp(
            np.clip(ctx.design @ np.asarray(theta, dtype=float), -20.0, 20.0)
        )
    return _project_weights(
        raw,
        target_total=ctx.target_total,
        lower_bound=ctx.lower_bound,
        effective_upper_bound=ctx.effective_upper_bound,
    )


def _solve_closed_form_linear(
    ctx: _CalibrationContext,
) -> tuple[np.ndarray, dict[str, float]]:
    income = np.asarray(ctx.data.market_income, dtype=float)
    weights = np.asarray(ctx.base_weights, dtype=float)
    target_mean = next(
        float(spec.target_value)
        for spec in ctx.specs
        if spec.kind == ReweightingTargetKind.MEAN_INCOME
    )
    s0 = float(np.sum(weights))
    s1 = float(np.sum(weights * income))
    s2 = float(np.sum(weights * income * income))
    rhs = np.asarray([ctx.target_total, ctx.target_total * target_mean], dtype=float)
    matrix = np.asarray([[s0, s1], [s1, s2]], dtype=float)
    a, b = np.linalg.pinv(matrix) @ rhs
    calibrated = _project_weights(
        weights * (a + b * income),
        target_total=ctx.target_total,
        lower_bound=ctx.lower_bound,
        effective_upper_bound=ctx.effective_upper_bound,
    )
    return calibrated, {"a": float(a), "b": float(b)}


def _objective(
    ctx: _CalibrationContext,
    theta: np.ndarray,
    weighting_matrix: np.ndarray,
) -> float:
    standardized = _standardized_moment_vector(ctx, _weights_from_theta(ctx, theta))
    return float(standardized.T @ weighting_matrix @ standardized)


def _solver_methods(preference: str) -> tuple[str, ...]:
    solver = preference.lower()
    if solver in {"trust-constr", "trust_constr"}:
        return ("trust-constr",)
    if solver == "powell":
        return ("Powell",)
    if solver == "auto":
        return ("trust-constr", "Powell")
    raise ValueError(f"unsupported solver '{preference}'")


def _run_solver(
    ctx: _CalibrationContext,
    initial_theta: np.ndarray,
    weighting_matrix: np.ndarray,
) -> _SolveResult:
    theta0 = np.asarray(initial_theta, dtype=float)
    if ctx.design.shape[1] == 0:
        weights = _weights_from_theta(ctx, theta0)
        raw = _moment_vector(ctx, weights)
        standardized = _standardized_moment_vector(ctx, weights)
        return _SolveResult(
            theta=theta0,
            weights=weights,
            raw_moments=raw,
            standardized_moments=standardized,
            objective_value=float(standardized.T @ weighting_matrix @ standardized),
            solver_status="success",
            solver_message="projection_only",
            iterations=0,
            method="projection_only",
            weighting_matrix=weighting_matrix,
        )

    if not _SCIPY_AVAILABLE or minimize is None:
        weights = _weights_from_theta(ctx, theta0)
        raw = _moment_vector(ctx, weights)
        standardized = _standardized_moment_vector(ctx, weights)
        return _SolveResult(
            theta=theta0,
            weights=weights,
            raw_moments=raw,
            standardized_moments=standardized,
            objective_value=float(standardized.T @ weighting_matrix @ standardized),
            solver_status="stalled",
            solver_message="scipy unavailable; nonlinear optimization skipped",
            iterations=0,
            method="unavailable",
            weighting_matrix=weighting_matrix,
        )

    def fun(theta: np.ndarray) -> float:
        return _objective(ctx, theta, weighting_matrix)

    best: _SolveResult | None = None
    for method in _solver_methods(ctx.solver):
        kwargs: dict[str, Any] = {}
        options = {"maxiter": ctx.max_iterations}
        if method == "trust-constr":
            kwargs["jac"] = "2-point"
            if BFGS is not None:
                kwargs["hess"] = BFGS()
            options.update(
                {
                    "gtol": ctx.objective_tolerance,
                    "xtol": ctx.objective_tolerance,
                    "verbose": 0,
                }
            )
        else:
            options.update(
                {
                    "xtol": ctx.objective_tolerance,
                    "ftol": ctx.objective_tolerance,
                }
            )
        result = minimize(fun, theta0, method=method, options=options, **kwargs)
        theta = np.asarray(result.x, dtype=float)
        weights = _weights_from_theta(ctx, theta)
        raw = _moment_vector(ctx, weights)
        standardized = _standardized_moment_vector(ctx, weights)
        solve = _SolveResult(
            theta=theta,
            weights=weights,
            raw_moments=raw,
            standardized_moments=standardized,
            objective_value=float(standardized.T @ weighting_matrix @ standardized),
            solver_status="success" if bool(result.success) else "stalled",
            solver_message=str(result.message),
            iterations=int(getattr(result, "nit", 0) or 0),
            method=method,
            weighting_matrix=weighting_matrix,
        )
        if best is None:
            best = solve
            continue
        if solve.objective_value < best.objective_value - 1e-12:
            best = solve
            continue
        if best.solver_status != "success" and solve.solver_status == "success":
            best = solve
    assert best is not None
    return best


def _estimate_moment_covariance(
    ctx: _CalibrationContext,
    theta: np.ndarray,
    *,
    reps: int,
    rng: np.random.Generator,
) -> np.ndarray | None:
    if reps < 2:
        return None
    n_obs = ctx.base_weights.shape[0]
    probabilities = ctx.base_weights / max(float(np.sum(ctx.base_weights)), _EPS)
    samples: list[np.ndarray] = []
    for _ in range(reps):
        indices = rng.choice(n_obs, size=n_obs, replace=True, p=probabilities)
        boot_data = _subset_survey_data(ctx.data, indices)
        boot_ctx = _make_context(
            boot_data,
            ctx.specs,
            lower_bound=ctx.lower_bound,
            upper_bound=ctx.effective_upper_bound if ctx.max_weight_ratio is None else None,
            max_weight_ratio=ctx.max_weight_ratio,
            solver=ctx.solver,
            max_iterations=max(20, min(80, ctx.max_iterations // 2)),
            objective_tolerance=max(ctx.objective_tolerance, 1e-5),
        )
        if boot_ctx.design.shape[1] != theta.shape[0]:
            return None
        weights = _weights_from_theta(boot_ctx, theta)
        samples.append(_standardized_moment_vector(boot_ctx, weights))
    if len(samples) < 2:
        return None
    covariance = np.cov(np.asarray(samples, dtype=float), rowvar=False, ddof=1)
    covariance = np.atleast_2d(np.asarray(covariance, dtype=float))
    if covariance.shape != (len(ctx.specs), len(ctx.specs)):
        return None
    if not np.all(np.isfinite(covariance)):
        return None
    return covariance


def _stable_weighting_matrix(covariance: np.ndarray | None, n_targets: int) -> np.ndarray:
    if covariance is None:
        return np.eye(n_targets, dtype=float)
    diagonal_scale = float(np.mean(np.diag(covariance))) if covariance.size else 1.0
    ridge = max(diagonal_scale, 1.0) * 1e-8
    return np.linalg.pinv(covariance + ridge * np.eye(n_targets, dtype=float))


def _fit_two_step_gmm(
    ctx: _CalibrationContext,
    *,
    covariance_bootstrap_reps: int,
    rng: np.random.Generator,
) -> tuple[_SolveResult, _SolveResult | None]:
    identity = np.eye(len(ctx.specs), dtype=float)
    stage1 = _run_solver(ctx, np.zeros(ctx.design.shape[1], dtype=float), identity)
    covariance = _estimate_moment_covariance(
        ctx,
        stage1.theta,
        reps=covariance_bootstrap_reps,
        rng=rng,
    )
    weighting_matrix = _stable_weighting_matrix(covariance, len(ctx.specs))
    if ctx.design.shape[1] == 0 or np.allclose(weighting_matrix, identity):
        stage1 = _SolveResult(
            **{
                **stage1.__dict__,
                "weighting_matrix": weighting_matrix,
                "covariance": covariance,
            }
        )
        return stage1, None
    stage2 = _run_solver(ctx, stage1.theta, weighting_matrix)
    stage2 = _SolveResult(
        **{
            **stage2.__dict__,
            "weighting_matrix": weighting_matrix,
            "covariance": covariance,
        }
    )
    return stage1, stage2


def _approximate_jacobian(ctx: _CalibrationContext, theta: np.ndarray) -> np.ndarray:
    if theta.size == 0:
        return np.zeros((len(ctx.specs), 0), dtype=float)
    jacobian = np.zeros((len(ctx.specs), theta.size), dtype=float)
    for column in range(theta.size):
        step = 1e-4 * max(1.0, abs(float(theta[column])))
        theta_plus = theta.copy()
        theta_minus = theta.copy()
        theta_plus[column] += step
        theta_minus[column] -= step
        moments_plus = _moment_vector(ctx, _weights_from_theta(ctx, theta_plus))
        moments_minus = _moment_vector(ctx, _weights_from_theta(ctx, theta_minus))
        jacobian[:, column] = (moments_plus - moments_minus) / (2.0 * step)
    return jacobian


def _is_hansen_applicable(
    ctx: _CalibrationContext,
    solution: _SolveResult,
    *,
    active_lower_bounds: int,
    active_upper_bounds: int,
) -> bool:
    return (
        solution.weighting_matrix is not None
        and solution.method not in {"closed_form_linear", "projection_only", "unavailable"}
        and all(spec.kind in _LINEAR_TARGET_KINDS for spec in ctx.specs)
        and len(ctx.specs) > ctx.design.shape[1]
        and ctx.design.shape[1] > 0
        and active_lower_bounds == 0
        and active_upper_bounds == 0
        and _SCIPY_AVAILABLE
        and chi2 is not None
    )


def _bootstrap_distance_test(
    ctx: _CalibrationContext,
    observed_statistic: float,
    solution: _SolveResult,
    *,
    reps: int,
    rng: np.random.Generator,
) -> tuple[float | None, tuple[str, ...]]:
    if reps <= 0:
        return None, ()
    n_obs = ctx.base_weights.shape[0]
    probabilities = solution.weights / max(float(np.sum(solution.weights)), _EPS)
    stats: list[float] = []
    failures = 0
    weighting_matrix = (
        np.asarray(solution.weighting_matrix, dtype=float)
        if solution.weighting_matrix is not None
        else np.eye(len(ctx.specs), dtype=float)
    )
    for _ in range(reps):
        indices = rng.choice(n_obs, size=n_obs, replace=True, p=probabilities)
        boot_data = _subset_survey_data(ctx.data, indices)
        boot_ctx = _make_context(
            boot_data,
            ctx.specs,
            lower_bound=ctx.lower_bound,
            upper_bound=ctx.effective_upper_bound if ctx.max_weight_ratio is None else None,
            max_weight_ratio=ctx.max_weight_ratio,
            solver=ctx.solver,
            max_iterations=max(20, min(100, ctx.max_iterations // 2)),
            objective_tolerance=max(ctx.objective_tolerance, 1e-5),
        )
        try:
            boot_solution = _run_solver(boot_ctx, solution.theta, weighting_matrix)
        except Exception:
            failures += 1
            continue
        if (
            boot_solution.solver_status != "success"
            and boot_solution.objective_value > observed_statistic * 100.0
        ):
            failures += 1
            continue
        stats.append(float(boot_data.weights.shape[0] * boot_solution.objective_value))
    if len(stats) < max(10, reps // 4):
        return None, ("Bootstrap compatibility test failed to collect enough converged re-solves.",)
    p_value = float(
        (1.0 + np.sum(np.asarray(stats, dtype=float) >= observed_statistic)) / (len(stats) + 1.0)
    )
    warnings: list[str] = []
    if failures:
        warnings.append(f"Bootstrap dropped {failures} failed re-solves out of {reps}")
    return p_value, tuple(warnings)


def _build_target_gaps(
    ctx: _CalibrationContext,
    solution: _SolveResult,
    *,
    weighting_matrix: np.ndarray | None,
) -> tuple[list[ReweightingTargetGap], dict[str, float], dict[str, float]]:
    target_moments = {spec.name: float(spec.target_value) for spec in ctx.specs}
    achieved_moments = {
        spec.name: float(_evaluate_target(spec, ctx.data, solution.weights)) for spec in ctx.specs
    }
    dual = None
    if weighting_matrix is not None:
        dual = np.asarray(weighting_matrix @ solution.standardized_moments, dtype=float)
    gaps: list[ReweightingTargetGap] = []
    for index, spec in enumerate(ctx.specs):
        tolerance = float(
            spec.tolerance if spec.tolerance is not None else _default_tolerance(spec)
        )
        achieved = achieved_moments[spec.name]
        abs_gap = abs(achieved - float(spec.target_value))
        scaled_gap = abs_gap / max(_target_scale(spec), _EPS)
        gaps.append(
            ReweightingTargetGap(
                name=spec.name,
                kind=spec.kind,
                target_value=float(spec.target_value),
                achieved_value=float(achieved),
                abs_gap=float(abs_gap),
                scaled_gap=float(scaled_gap),
                tolerance=float(tolerance),
                binding=bool(abs_gap > tolerance),
                shadow_price=float(abs(dual[index])) if dual is not None else float(scaled_gap),
            )
        )
    return gaps, target_moments, achieved_moments


def _build_target_compatibility(
    ctx: _CalibrationContext,
    solution: _SolveResult,
    *,
    alpha: float,
    bootstrap_reps: int,
    rng: np.random.Generator,
) -> tuple[ReweightingTargetCompatibility, dict[str, float], dict[str, float]]:
    per_target, target_moments, achieved_moments = _build_target_gaps(
        ctx,
        solution,
        weighting_matrix=solution.weighting_matrix,
    )
    exact_feasible = bool(all(gap.abs_gap <= gap.tolerance for gap in per_target))
    active_lower_bounds = int(np.sum(solution.weights <= ctx.lower_bound + 1e-8))
    active_upper_bounds = (
        int(np.sum(solution.weights >= ctx.effective_upper_bound - 1e-8))
        if ctx.effective_upper_bound is not None
        else 0
    )
    warnings: list[str] = []
    if active_lower_bounds:
        warnings.append(f"Lower bound active for {active_lower_bounds} units")
    if active_upper_bounds:
        warnings.append(f"Upper bound active for {active_upper_bounds} units")

    statistic: float | None = None
    p_value: float | None = None
    df: int | None = None
    test_method = ReweightingCompatibilityTestMethod.NONE

    objective_value = float(solution.objective_value)
    distance_to_feasibility = float(np.sqrt(max(objective_value, 0.0)))
    normalized_distance = float(distance_to_feasibility / max(np.sqrt(len(ctx.specs)), 1.0))

    jacobian = _approximate_jacobian(ctx, solution.theta)
    jacobian_rank = int(np.linalg.matrix_rank(jacobian)) if jacobian.size else 0
    with np.errstate(over="ignore", invalid="ignore"):
        condition_number = float(np.linalg.cond(jacobian)) if jacobian.size else None
    if condition_number is not None and not np.isfinite(condition_number):
        condition_number = None

    if _is_hansen_applicable(
        ctx,
        solution,
        active_lower_bounds=active_lower_bounds,
        active_upper_bounds=active_upper_bounds,
    ):
        statistic = float(ctx.base_weights.shape[0] * objective_value)
        df = int(len(ctx.specs) - ctx.design.shape[1])
        if df > 0 and chi2 is not None:
            p_value = float(1.0 - chi2.cdf(statistic, df))
            test_method = ReweightingCompatibilityTestMethod.HANSEN_J
    elif bootstrap_reps > 0:
        statistic = float(ctx.base_weights.shape[0] * objective_value)
        p_value, boot_warnings = _bootstrap_distance_test(
            ctx,
            statistic,
            solution,
            reps=bootstrap_reps,
            rng=rng,
        )
        warnings.extend(boot_warnings)
        if p_value is not None:
            test_method = ReweightingCompatibilityTestMethod.DISTANCE_BOOTSTRAP

    weak_jacobian = jacobian.size > 0 and (
        jacobian_rank < min(len(ctx.specs), max(ctx.design.shape[1], 1))
        or (condition_number is not None and condition_number > 1e8)
    )

    if solution.solver_status != "success" and not exact_feasible:
        status = ReweightingCompatibilityStatus.NUMERIC_FAILURE
        reason = ReweightingCompatibilityReason.SOLVER_STALLED
    elif (active_lower_bounds or active_upper_bounds) and not exact_feasible:
        status = ReweightingCompatibilityStatus.INCOMPATIBLE
        reason = ReweightingCompatibilityReason.BOUNDS_PRECLUDE_TARGETS
    elif weak_jacobian:
        status = (
            ReweightingCompatibilityStatus.APPROXIMATELY_COMPATIBLE
            if exact_feasible
            else ReweightingCompatibilityStatus.INCONCLUSIVE
        )
        reason = ReweightingCompatibilityReason.WEAK_JACOBIAN
    elif exact_feasible and (p_value is None or p_value >= alpha):
        status = ReweightingCompatibilityStatus.COMPATIBLE
        reason = ReweightingCompatibilityReason.TARGETS_SATISFIED
    elif exact_feasible or (
        p_value is not None and p_value >= alpha and normalized_distance <= 1.0
    ):
        status = ReweightingCompatibilityStatus.APPROXIMATELY_COMPATIBLE
        reason = ReweightingCompatibilityReason.TARGETS_SATISFIED
    else:
        status = ReweightingCompatibilityStatus.INCOMPATIBLE
        if active_lower_bounds or active_upper_bounds:
            reason = ReweightingCompatibilityReason.BOUNDS_PRECLUDE_TARGETS
        elif p_value is None and bootstrap_reps > 0:
            reason = ReweightingCompatibilityReason.BOOTSTRAP_FAILED
        else:
            reason = ReweightingCompatibilityReason.TARGETS_CONFLICT

    report = ReweightingTargetCompatibility(
        status=status,
        reason_code=reason,
        exact_feasible=exact_feasible,
        distance_to_feasibility=float(distance_to_feasibility),
        normalized_distance=float(normalized_distance),
        test_method=test_method,
        statistic=statistic,
        df=df,
        p_value=p_value,
        alpha=float(alpha),
        n_targets=len(ctx.specs),
        n_free_params=int(ctx.design.shape[1]),
        jacobian_rank=int(jacobian_rank),
        condition_number=condition_number,
        active_lower_bounds=active_lower_bounds,
        active_upper_bounds=active_upper_bounds,
        per_target=per_target,
        warnings=warnings,
        solver_status=solution.solver_status,
        solver_message=solution.solver_message,
        iterations=solution.iterations,
    )
    return report, target_moments, achieved_moments


def _compatibility_from_raking(
    diagnostics: SurveyRakingDiagnosticReport,
    *,
    exact_tolerance: float,
    warn_tolerance: float,
) -> ReweightingTargetCompatibility:
    per_target: list[ReweightingTargetGap] = []
    for name, target_value in diagnostics.target_totals.items():
        achieved_value = float(diagnostics.achieved_totals.get(name, 0.0))
        abs_gap = abs(achieved_value - float(target_value))
        tolerance = max(float(exact_tolerance) * (1.0 + abs(float(target_value))), _EPS)
        per_target.append(
            ReweightingTargetGap(
                name=str(name),
                kind=ReweightingTargetKind.FEATURE_MEAN,
                target_value=float(target_value),
                achieved_value=float(achieved_value),
                abs_gap=float(abs_gap),
                scaled_gap=float(abs_gap / tolerance),
                tolerance=tolerance,
                binding=bool(abs_gap > tolerance),
                shadow_price=float(abs_gap / tolerance),
            )
        )

    if diagnostics.decision == "pass":
        status = ReweightingCompatibilityStatus.COMPATIBLE
        reason = ReweightingCompatibilityReason.TARGETS_SATISFIED
    elif diagnostics.decision == "warn":
        status = ReweightingCompatibilityStatus.APPROXIMATELY_COMPATIBLE
        reason = ReweightingCompatibilityReason.TARGETS_SATISFIED
    else:
        status = ReweightingCompatibilityStatus.INCOMPATIBLE
        if diagnostics.stop_reason == "structural_zero":
            reason = ReweightingCompatibilityReason.ZERO_CELL_OR_SUPPORT
        else:
            reason = ReweightingCompatibilityReason.TARGETS_CONFLICT

    statistic = float(max(diagnostics.max_rel_margin_error, 0.0) * diagnostics.n_obs)
    p_value = None
    test_method = ReweightingCompatibilityTestMethod.NONE
    if diagnostics.decision != "pass":
        normalized_distance = float(
            max(diagnostics.max_rel_margin_error, diagnostics.rms_rel_margin_error)
        )
    else:
        normalized_distance = 0.0

    return ReweightingTargetCompatibility(
        status=status,
        reason_code=reason,
        exact_feasible=bool(
            diagnostics.converged and diagnostics.max_rel_margin_error <= exact_tolerance
        ),
        distance_to_feasibility=float(diagnostics.max_rel_margin_error),
        normalized_distance=float(normalized_distance),
        test_method=test_method,
        statistic=statistic,
        df=None,
        p_value=p_value,
        alpha=None,
        n_targets=len(per_target),
        n_free_params=0,
        jacobian_rank=None,
        condition_number=None,
        active_lower_bounds=0,
        active_upper_bounds=0,
        per_target=per_target,
        warnings=list(diagnostics.warnings),
        solver_status="success" if diagnostics.converged else "stalled",
        solver_message=diagnostics.stop_reason,
        iterations=int(diagnostics.n_sweeps),
    )


@foundry_method(
    namespace="microsim.calibration",
    version="1.0.0",
    tags={"microsim", "calibration", "survey"},
)
class ReweightingCalibrationEstimator:
    """Calibrate survey weights so a microsimulation matches external control totals."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scipy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="reweighting_calibration",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "market_income",
                    SlotType.VECTOR,
                    Unit("income", "currency"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "weights",
                    SlotType.VECTOR,
                    Unit("weight", "survey"),
                    shape=("n_obs",),
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("calibration", "json"),
                    contract_id=ReweightingResult.contract_id,
                ),
                SlotSpec(
                    "weights",
                    SlotType.VECTOR,
                    Unit("weight", "survey"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "diagnostics",
                    SlotType.SCALAR,
                    Unit("diagnostic", "json"),
                    contract_id=SurveyRakingDiagnosticReport.contract_id,
                ),
                SlotSpec(
                    "microsim_calibration_report",
                    SlotType.SCALAR,
                    Unit("calibration_gate", "json"),
                ),
                SlotSpec(
                    "microsim_calibration_report_ref",
                    SlotType.SCALAR,
                    Unit("artifact_ref", "json"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="target_total_weight", default=None),
            ParameterSpec(name="target_mean_income", default=None),
            ParameterSpec(name="targets", default=None),
            ParameterSpec(name="raking_targets", default=None),
            ParameterSpec(name="raking_target_mode", default="auto"),
            ParameterSpec(name="raking_max_iterations", default=100),
            ParameterSpec(name="raking_exact_tolerance", default=1e-6),
            ParameterSpec(name="raking_warn_tolerance", default=1e-4),
            ParameterSpec(name="raking_collapse_sparse_categories", default=True),
            ParameterSpec(name="raking_collapse_map", default=None),
            ParameterSpec(name="raking_allow_bounded_fallback", default=True),
            ParameterSpec(name="raking_allow_penalized_fallback", default=True),
            ParameterSpec(name="raking_bounded_lower_ratio", default=0.3),
            ParameterSpec(name="raking_bounded_upper_ratio", default=3.0),
            ParameterSpec(name="raking_hard_lower_ratio", default=0.2),
            ParameterSpec(name="raking_hard_upper_ratio", default=5.0),
            ParameterSpec(name="raking_fallback_ridge", default=1e-2),
            ParameterSpec(name="raking_fallback_max_iterations", default=200),
            ParameterSpec(name="lower_bound", default=1e-8),
            ParameterSpec(name="upper_bound", default=None),
            ParameterSpec(name="max_weight_ratio", default=5.0),
            ParameterSpec(name="solver", default="auto"),
            ParameterSpec(name="max_iterations", default=250),
            ParameterSpec(name="objective_tolerance", default=1e-6),
            ParameterSpec(name="gmm_covariance_bootstrap_reps", default=32),
            ParameterSpec(name="compatibility_alpha", default=0.05),
            ParameterSpec(name="compatibility_bootstrap_reps", default=64),
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
            "Linear fast-path, IPF/raking, and nonlinear two-step GMM calibration for survey "
            "reweighting, with structured target-compatibility diagnostics."
        ),
        tags=frozenset({"microsim", "calibration", "survey", "gmm"}),
        when_to_use=(
            "Align microsimulation outputs to control totals, feature means, quantiles, or "
            "weight-dispersion targets while keeping a compatibility report for downstream audit."
        ),
        citations=(
            "Deville, J. & Sarndal, C. (1992). Calibration estimators in survey sampling. Journal of the American Statistical Association, 87(418), 376-382.",
            "Hansen, L. (1982). Large sample properties of generalized method of moments estimators. Econometrica, 50(4), 1029-1054.",
        ),
        when_not_to_use=(
            "Need a dedicated IPOPT/GEL backend, very high-dimensional weak moments, or a "
            "production-hardened large-n bootstrap budget beyond the local runtime."
        ),
        output_interpretation=(
            "Read target_compatibility as the readiness gate. 'approximately_compatible' is a "
            "sensitivity success, while 'incompatible' and 'numeric_failure' should block silent use."
        ),
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> SurveyMicroData:
        payload = _survey_payload(fallback_state)
        payload.update(bound_inputs)
        return SurveyMicroData.model_validate(payload)

    @staticmethod
    def pure_step(state: SurveyMicroData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state if isinstance(state, SurveyMicroData) else SurveyMicroData.model_validate(state)
        )
        income = np.asarray(data.market_income, dtype=float)
        base_weights = np.asarray(data.weights, dtype=float)
        artifact_store = resolve_artifact_store(
            state.model_dump(mode="python") if isinstance(state, SurveyMicroData) else state,
            params,
        )
        if np.any(~np.isfinite(income)):
            raise ValueError("market_income must contain only finite values")
        if np.any(~np.isfinite(base_weights)) or np.any(base_weights <= 0.0):
            raise ValueError("weights must be finite and strictly positive")

        def _build_output(
            *,
            result: ReweightingResult,
            weights: np.ndarray,
            diagnostics: Any,
            numpy_artifacts: Any | None = None,
            numpy_warnings: Any | None = None,
        ) -> dict[str, Any]:
            compatibility = result.target_compatibility
            calibration_report = (
                None
                if compatibility is None
                else report_from_target_compatibility(
                    compatibility,
                    max_abs_gap=float(result.max_abs_gap),
                    metadata={"solver": result.metadata.get("solver")},
                )
            )
            calibration_report_ref = (
                persist_microsim_calibration_report(artifact_store, calibration_report)
                if artifact_store is not None and calibration_report is not None
                else None
            )
            updated_result = result.model_copy(
                update={
                    "metadata": {
                        **result.metadata,
                        "microsim_calibration_decision": (
                            None if calibration_report is None else calibration_report.decision
                        ),
                        "microsim_calibration_report_ref": (
                            None
                            if calibration_report_ref is None
                            else calibration_report_ref.model_dump(mode="json")
                        ),
                    }
                }
            )
            output = {
                "result": updated_result,
                "weights": weights,
                "diagnostics": diagnostics,
                "microsim_calibration_report": (
                    None
                    if calibration_report is None
                    else calibration_report.model_dump(mode="json")
                ),
                "microsim_calibration_report_ref": (
                    None
                    if calibration_report_ref is None
                    else calibration_report_ref.model_dump(mode="json")
                ),
            }
            if numpy_artifacts is not None:
                output["__numpy_artifacts__"] = numpy_artifacts
            if numpy_warnings is not None:
                output["__numpy_warnings__"] = numpy_warnings
            return output

        lower_bound = max(1e-8, float(params.get("lower_bound", 1e-8)))
        upper_raw = params.get("upper_bound")
        upper_bound = None if _is_none_like(upper_raw) else float(upper_raw)
        if upper_bound is not None and upper_bound < lower_bound:
            raise ValueError("upper_bound must be >= lower_bound")
        max_ratio_raw = params.get("max_weight_ratio", 5.0)
        max_weight_ratio = None if _is_none_like(max_ratio_raw) else max(1.0, float(max_ratio_raw))

        solver = str(params.get("solver", "auto"))
        max_iterations = max(20, int(params.get("max_iterations", 250)))
        objective_tolerance = max(1e-10, float(params.get("objective_tolerance", 1e-6)))
        covariance_bootstrap_reps = max(0, int(params.get("gmm_covariance_bootstrap_reps", 32)))
        compatibility_alpha = float(params.get("compatibility_alpha", 0.05))
        compatibility_bootstrap_reps = max(0, int(params.get("compatibility_bootstrap_reps", 64)))
        rng = np.random.default_rng(0)

        raking_targets = params.get("raking_targets")
        if not _is_none_like(raking_targets):
            if not _is_none_like(params.get("targets")):
                raise ValueError("Use either targets or raking_targets, not both")
            if data.features is None:
                raise ValueError("raking_targets requires SurveyMicroData.features")
            target_total = (
                float(np.sum(base_weights))
                if _is_none_like(params.get("target_total_weight"))
                else float(params["target_total_weight"])
            )
            design = build_raking_design_from_feature_targets(
                base_weights=base_weights,
                features=data.features,
                feature_names=data.feature_names,
                raking_targets=raking_targets,
                target_mode=str(params.get("raking_target_mode", "auto")),
                population_total=target_total,
            )
            execution = run_raking_with_fallbacks(
                base_weights=design["base_weights"],
                category_matrix=design["category_matrix"],
                target_totals=design["target_totals"],
                margin_ids=design["margin_ids"],
                margin_names_by_category=design["margin_names_by_category"],
                category_labels=design["category_labels"],
                max_iterations=int(params.get("raking_max_iterations", 100)),
                exact_tolerance=float(params.get("raking_exact_tolerance", 1e-6)),
                warn_tolerance=float(params.get("raking_warn_tolerance", 1e-4)),
                collapse_sparse_categories=bool(
                    params.get("raking_collapse_sparse_categories", True)
                ),
                collapse_map=params.get("raking_collapse_map"),
                allow_bounded_fallback=bool(params.get("raking_allow_bounded_fallback", True)),
                allow_penalized_fallback=bool(params.get("raking_allow_penalized_fallback", True)),
                bounded_lower_ratio=float(params.get("raking_bounded_lower_ratio", 0.3)),
                bounded_upper_ratio=float(params.get("raking_bounded_upper_ratio", 3.0)),
                hard_lower_ratio=float(params.get("raking_hard_lower_ratio", 0.2)),
                hard_upper_ratio=float(params.get("raking_hard_upper_ratio", 5.0)),
                fallback_ridge=float(params.get("raking_fallback_ridge", 1e-2)),
                fallback_max_iterations=int(params.get("raking_fallback_max_iterations", 200)),
            )
            calibrated = np.asarray(execution["weights"], dtype=float)
            diagnostics = execution["diagnostics"]
            compatibility = _compatibility_from_raking(
                diagnostics,
                exact_tolerance=float(params.get("raking_exact_tolerance", 1e-6)),
                warn_tolerance=float(params.get("raking_warn_tolerance", 1e-4)),
            )
            max_abs_gap = (
                float(
                    max(
                        abs(float(diagnostics.achieved_totals.get(name, 0.0)) - float(target))
                        for name, target in diagnostics.target_totals.items()
                    )
                )
                if diagnostics.target_totals
                else 0.0
            )
            result = ReweightingResult(
                calibrated_weights=calibrated,
                target_moments=dict(diagnostics.target_totals),
                achieved_moments=dict(diagnostics.achieved_totals),
                max_abs_gap=max_abs_gap,
                target_compatibility=compatibility,
                metadata={
                    "solver": "rake_ipf",
                    "basis_columns": list(execution["category_labels"]),
                    "legacy_linear_fast_path": False,
                    "decision": diagnostics.decision,
                    "stop_reason": diagnostics.stop_reason,
                    "fallback_used": diagnostics.fallback_used,
                },
            )
            return _build_output(
                result=result,
                weights=calibrated,
                diagnostics=diagnostics,
                numpy_artifacts=execution["artifacts"],
                numpy_warnings=execution["warnings"],
            )

        specs = _build_target_specs(data, params)
        target_total = _target_total(specs)
        effective_upper = _effective_upper_bound(
            n_obs=base_weights.shape[0],
            target_total=target_total,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            max_weight_ratio=max_weight_ratio,
        )
        min_total = lower_bound * float(base_weights.shape[0])
        max_total = (
            float("inf")
            if effective_upper is None
            else effective_upper * float(base_weights.shape[0])
        )

        if target_total < min_total - 1e-9 or target_total > max_total + 1e-9:
            projected = _project_weights(
                base_weights,
                target_total=target_total,
                lower_bound=lower_bound,
                effective_upper_bound=effective_upper,
            )
            ctx = _make_context(
                data,
                specs,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                max_weight_ratio=max_weight_ratio,
                solver=solver,
                max_iterations=max_iterations,
                objective_tolerance=objective_tolerance,
            )
            fallback = _SolveResult(
                theta=np.zeros(ctx.design.shape[1], dtype=float),
                weights=projected,
                raw_moments=_moment_vector(ctx, projected),
                standardized_moments=_standardized_moment_vector(ctx, projected),
                objective_value=float(
                    _standardized_moment_vector(ctx, projected).T
                    @ _standardized_moment_vector(ctx, projected)
                ),
                solver_status="success",
                solver_message="Bounds prevent exact normalization to target_total",
                iterations=0,
                method="bounds_projection",
                weighting_matrix=np.eye(len(specs), dtype=float),
            )
            compatibility, target_moments, achieved_moments = _build_target_compatibility(
                ctx,
                fallback,
                alpha=compatibility_alpha,
                bootstrap_reps=compatibility_bootstrap_reps,
                rng=rng,
            )
            result = ReweightingResult(
                calibrated_weights=projected,
                target_moments=target_moments,
                achieved_moments=achieved_moments,
                max_abs_gap=float(
                    max((gap.abs_gap for gap in compatibility.per_target), default=0.0)
                ),
                target_compatibility=compatibility,
                metadata={"solver": "bounds_projection", "basis_columns": []},
            )
            return _build_output(result=result, weights=projected, diagnostics=None)

        linear_fast_path = len(specs) == 2 and {spec.kind for spec in specs} == {
            ReweightingTargetKind.TOTAL_WEIGHT,
            ReweightingTargetKind.MEAN_INCOME,
        }
        if linear_fast_path:
            ctx = _make_context(
                data,
                specs,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                max_weight_ratio=max_weight_ratio,
                solver=solver,
                max_iterations=max_iterations,
                objective_tolerance=objective_tolerance,
            )
            calibrated, linear_metadata = _solve_closed_form_linear(ctx)
            solution = _SolveResult(
                theta=np.zeros(ctx.design.shape[1], dtype=float),
                weights=calibrated,
                raw_moments=_moment_vector(ctx, calibrated),
                standardized_moments=_standardized_moment_vector(ctx, calibrated),
                objective_value=float(
                    _standardized_moment_vector(ctx, calibrated).T
                    @ _standardized_moment_vector(ctx, calibrated)
                ),
                solver_status="success",
                solver_message="closed_form_linear_calibration",
                iterations=1,
                method="closed_form_linear",
                weighting_matrix=np.eye(len(specs), dtype=float),
            )
            compatibility, target_moments, achieved_moments = _build_target_compatibility(
                ctx,
                solution,
                alpha=compatibility_alpha,
                bootstrap_reps=0,
                rng=rng,
            )
            result = ReweightingResult(
                calibrated_weights=calibrated,
                target_moments=target_moments,
                achieved_moments=achieved_moments,
                max_abs_gap=float(
                    max((gap.abs_gap for gap in compatibility.per_target), default=0.0)
                ),
                target_compatibility=compatibility,
                metadata={
                    **linear_metadata,
                    "solver": "closed_form_linear",
                    "basis_columns": list(ctx.basis_columns),
                    "legacy_linear_fast_path": True,
                },
            )
            return _build_output(result=result, weights=calibrated, diagnostics=None)

        ctx = _make_context(
            data,
            specs,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            max_weight_ratio=max_weight_ratio,
            solver=solver,
            max_iterations=max_iterations,
            objective_tolerance=objective_tolerance,
        )
        stage1, stage2 = _fit_two_step_gmm(
            ctx,
            covariance_bootstrap_reps=covariance_bootstrap_reps,
            rng=rng,
        )
        final = stage2 or stage1
        compatibility, target_moments, achieved_moments = _build_target_compatibility(
            ctx,
            final,
            alpha=compatibility_alpha,
            bootstrap_reps=compatibility_bootstrap_reps,
            rng=rng,
        )
        result = ReweightingResult(
            calibrated_weights=final.weights,
            target_moments=target_moments,
            achieved_moments=achieved_moments,
            max_abs_gap=float(max((gap.abs_gap for gap in compatibility.per_target), default=0.0)),
            target_compatibility=compatibility,
            metadata={
                "solver": final.method,
                "basis_columns": list(ctx.basis_columns),
                "legacy_linear_fast_path": False,
                "stage1_objective": float(stage1.objective_value),
                "stage2_objective": float(stage2.objective_value)
                if stage2 is not None
                else float(stage1.objective_value),
                "covariance_bootstrap_reps": int(covariance_bootstrap_reps),
                "used_two_step_gmm": bool(stage2 is not None),
            },
        )
        return _build_output(result=result, weights=final.weights, diagnostics=None)


__all__ = ["ReweightingCalibrationEstimator"]
