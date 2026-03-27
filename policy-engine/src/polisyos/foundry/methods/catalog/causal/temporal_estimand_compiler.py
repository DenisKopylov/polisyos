from __future__ import annotations

import math
from enum import Enum
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.foundry.methods.catalog.causal.protocols import (
    DynamicTreatmentData,
    PanelObservationalData,
)
from polisyos.ir.analytics.dynamic_regime import (
    ContinuousTimeQuery,
    InterventionInterpolationPolicy,
    TemporalSamplingScheme,
    TemporalInterventionTrajectory,
    TemporalTargetFunctional,
)


class TemporalBackendTarget(str, Enum):
    LINEAR_SDE = "linear_sde"
    ODE = "ode"
    DISCRETE_FALLBACK = "discrete_fallback"


class TemporalComparatorSemantics(str, Enum):
    UNTREATED_COUNTERFACTUAL = "untreated_counterfactual"
    NEVER_TREAT_BASELINE = "never_treat_baseline"


class TemporalFallbackMode(str, Enum):
    NONE = "none"
    DISCRETE_TIME = "discrete_time"


class TemporalDataContract(str, Enum):
    PANEL_OBSERVATIONAL = "panel_observational_data"
    DYNAMIC_TREATMENT = "dynamic_treatment_data"


class TemporalCompileError(RuntimeError):
    """Machine-readable compile-time failure for temporal plans."""

    def __init__(self, reason_code: str, message: str, *, details: dict[str, Any] | None = None):
        self.reason_code = reason_code
        self.details = dict(details or {})
        super().__init__(message)


class TemporalExecutionPlan(BaseModel):
    """Typed execution plan for temporal effect compilation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query: ContinuousTimeQuery
    data_contract: TemporalDataContract
    backend_target: TemporalBackendTarget
    target_functional: TemporalTargetFunctional
    interpolation_policy: InterventionInterpolationPolicy
    comparator_semantics: TemporalComparatorSemantics
    resolved_intervention: TemporalInterventionTrajectory
    materialized_intervention_values: tuple[float, ...]
    time_grid: tuple[float, ...]
    time_index_positions: tuple[int, ...]
    step_size: float
    grid_source: str = Field(min_length=1)
    time_scale_validation: str = Field(min_length=1)
    intervention_contract_status: str = Field(min_length=1)
    fallback_mode: TemporalFallbackMode = TemporalFallbackMode.NONE
    solver_config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("time_grid", mode="before")
    @classmethod
    def _coerce_time_grid(cls, value: Any) -> tuple[float, ...]:
        if isinstance(value, np.ndarray):
            value = value.tolist()
        if not isinstance(value, (tuple, list)):
            raise ValueError("time_grid must be a tuple/list of floats")
        grid = tuple(float(item) for item in value)
        if len(grid) < 2:
            raise ValueError("time_grid must contain at least two points")
        if any(not math.isfinite(item) for item in grid):
            raise ValueError("time_grid must contain finite points")
        return grid

    @field_validator("materialized_intervention_values", mode="before")
    @classmethod
    def _coerce_intervention_values(cls, value: Any) -> tuple[float, ...]:
        if isinstance(value, np.ndarray):
            value = value.tolist()
        if not isinstance(value, (tuple, list)):
            raise ValueError("materialized_intervention_values must be a tuple/list of floats")
        materialized = tuple(float(item) for item in value)
        if len(materialized) < 2:
            raise ValueError("materialized_intervention_values must contain at least two points")
        if any(not math.isfinite(item) for item in materialized):
            raise ValueError("materialized_intervention_values must contain finite values")
        return materialized

    @field_validator("time_index_positions", mode="before")
    @classmethod
    def _coerce_positions(cls, value: Any) -> tuple[int, ...]:
        if isinstance(value, np.ndarray):
            value = value.tolist()
        if not isinstance(value, (tuple, list)):
            raise ValueError("time_index_positions must be a tuple/list of ints")
        positions = tuple(int(item) for item in value)
        if len(positions) < 2:
            raise ValueError("time_index_positions must contain at least two points")
        return positions

    @field_validator("step_size", mode="before")
    @classmethod
    def _coerce_step_size(cls, value: Any) -> float:
        casted = float(value)
        if not math.isfinite(casted) or casted <= 0.0:
            raise ValueError("step_size must be finite and positive")
        return casted

    @model_validator(mode="after")
    def _validate_grid(self) -> "TemporalExecutionPlan":
        if len(self.time_grid) != len(self.time_index_positions):
            raise ValueError("time_grid and time_index_positions must have equal length")
        if len(self.time_grid) != len(self.materialized_intervention_values):
            raise ValueError("materialized_intervention_values must align with time_grid")
        diffs = np.diff(np.asarray(self.time_grid, dtype=float))
        if np.any(diffs <= 0):
            raise ValueError("time_grid must be strictly increasing")
        if self.backend_target is not TemporalBackendTarget.DISCRETE_FALLBACK:
            if not np.allclose(diffs, diffs[0], atol=1e-8, rtol=1e-8):
                raise ValueError("non-fallback temporal plans require a regular time grid")
        return self


def compile_temporal_estimand(
    query: ContinuousTimeQuery,
    *,
    data: Any,
    resolved_intervention: TemporalInterventionTrajectory | dict[str, Any] | None,
    intervention_contract_status: str = "resolved_artifact",
    allow_discrete_fallback: bool = True,
) -> TemporalExecutionPlan:
    """Compile a continuous-time query into a concrete temporal execution plan."""

    if resolved_intervention is None:
        raise TemporalCompileError(
            "missing_intervention_contract",
            "Temporal execution requires a resolved intervention trajectory contract.",
        )
    intervention = (
        resolved_intervention
        if isinstance(resolved_intervention, TemporalInterventionTrajectory)
        else TemporalInterventionTrajectory.model_validate(resolved_intervention)
    )
    if intervention.interpolation_policy is not query.interpolation_policy:
        raise TemporalCompileError(
            "intervention_policy_mismatch",
            "ContinuousTimeQuery.interpolation_policy must match the resolved intervention artifact.",
            details={
                "query_interpolation_policy": query.interpolation_policy.value,
                "intervention_interpolation_policy": intervention.interpolation_policy.value,
            },
        )
    if intervention.time_scale != query.time_scale:
        raise TemporalCompileError(
            "time_scale_mismatch",
            "ContinuousTimeQuery.time_scale must match the resolved intervention artifact time_scale.",
            details={
                "query_time_scale": query.time_scale,
                "intervention_time_scale": intervention.time_scale,
            },
        )

    if query.sampling_scheme is not TemporalSamplingScheme.REGULAR_GRID:
        raise TemporalCompileError(
            "research_gated_sampling_scheme",
            "Only regular-grid ContinuousTimeQuery objects are executable in Phase C.",
            details={"sampling_scheme": query.sampling_scheme.value},
        )

    if query.target_functional not in {
        TemporalTargetFunctional.EFFECT_PATH,
        TemporalTargetFunctional.INTEGRAL_EFFECT,
    }:
        raise TemporalCompileError(
            "unsupported_target_functional",
            "Only effect_path and integral_effect are implemented in Phase C.",
            details={"target_functional": query.target_functional.value},
        )

    preferred_backend = str(query.metadata.get("preferred_backend", "linear_sde")).strip().lower()
    if preferred_backend in {"neural_sde", "neural_cde"}:
        raise TemporalCompileError(
            "research_gated_backend",
            "Neural temporal backends remain research-gated in Phase C.",
            details={"preferred_backend": preferred_backend},
        )
    if preferred_backend not in {"linear_sde", "ode"}:
        raise TemporalCompileError(
            "unsupported_backend_target",
            "Unsupported temporal backend target.",
            details={"preferred_backend": preferred_backend},
        )

    materialized, contract, observed_grid, grid_source = _coerce_temporal_data(data)
    data_time_scale = _extract_data_time_scale(materialized)
    if data_time_scale is not None and data_time_scale != query.time_scale:
        raise TemporalCompileError(
            "time_scale_mismatch",
            "ContinuousTimeQuery.time_scale must match the data time scale when the data contract declares one.",
            details={
                "query_time_scale": query.time_scale,
                "data_time_scale": data_time_scale,
            },
        )
    in_horizon = np.where(
        (observed_grid >= query.horizon_start - 1e-8)
        & (observed_grid <= query.horizon_end + 1e-8)
    )[0]
    if in_horizon.size < 2:
        raise TemporalCompileError(
            "horizon_out_of_range",
            "The requested horizon does not overlap at least two observed time points.",
            details={
                "horizon_start": query.horizon_start,
                "horizon_end": query.horizon_end,
                "observed_grid_min": float(observed_grid.min()),
                "observed_grid_max": float(observed_grid.max()),
            },
        )

    clipped_grid = observed_grid[in_horizon]
    materialized_intervention = _materialize_intervention_to_grid(
        intervention,
        clipped_grid,
    )
    if contract is TemporalDataContract.PANEL_OBSERVATIONAL:
        _validate_panel_intervention(
            materialized_intervention,
            time_index_positions=in_horizon,
            time_treatment=int(materialized.time_treatment),
        )
    horizon_start_aligned = np.any(np.isclose(clipped_grid, query.horizon_start, atol=1e-8))
    horizon_end_aligned = np.any(np.isclose(clipped_grid, query.horizon_end, atol=1e-8))
    regular_grid = _is_regular_grid(clipped_grid)

    if regular_grid and horizon_start_aligned and horizon_end_aligned:
        backend_target = (
            TemporalBackendTarget.ODE
            if preferred_backend == "ode"
            else TemporalBackendTarget.LINEAR_SDE
        )
        step_size = float(np.diff(clipped_grid)[0])
        return TemporalExecutionPlan(
            query=query,
            data_contract=contract,
            backend_target=backend_target,
            target_functional=query.target_functional,
            interpolation_policy=query.interpolation_policy,
            comparator_semantics=_comparator_for_contract(contract),
            resolved_intervention=intervention,
            materialized_intervention_values=tuple(float(value) for value in materialized_intervention.tolist()),
            time_grid=tuple(float(value) for value in clipped_grid),
            time_index_positions=tuple(int(value) for value in in_horizon.tolist()),
            step_size=step_size,
            grid_source=grid_source,
            time_scale_validation="strict_match",
            intervention_contract_status=intervention_contract_status,
            fallback_mode=TemporalFallbackMode.NONE,
            solver_config=_default_solver_config(
                backend_target=backend_target,
                step_size=step_size,
                n_grid_points=int(clipped_grid.size),
            ),
            metadata={
                "preferred_backend": preferred_backend,
                "grid_aligned": True,
                "materialized_contract_id": getattr(materialized, "contract_id", ""),
                "data_time_scale": data_time_scale or query.time_scale,
                "intervention_time_scale": intervention.time_scale,
                "execution_contract_kind": query.query_mode.value,
            },
        )

    if not allow_discrete_fallback:
        raise TemporalCompileError(
            "time_grid_mismatch",
            "Temporal grid mismatch requires discrete fallback or explicit caller handling.",
            details={
                "grid_regular": regular_grid,
                "horizon_start_aligned": horizon_start_aligned,
                "horizon_end_aligned": horizon_end_aligned,
            },
        )

    diffs = np.diff(clipped_grid)
    positive_diffs = diffs[diffs > 0]
    step_size = float(np.median(positive_diffs)) if positive_diffs.size else 1.0
    return TemporalExecutionPlan(
        query=query,
        data_contract=contract,
        backend_target=TemporalBackendTarget.DISCRETE_FALLBACK,
        target_functional=query.target_functional,
        interpolation_policy=query.interpolation_policy,
        comparator_semantics=_comparator_for_contract(contract),
        resolved_intervention=intervention,
        materialized_intervention_values=tuple(float(value) for value in materialized_intervention.tolist()),
        time_grid=tuple(float(value) for value in clipped_grid),
        time_index_positions=tuple(int(value) for value in in_horizon.tolist()),
        step_size=step_size,
        grid_source=grid_source,
        time_scale_validation="strict_match",
        intervention_contract_status=intervention_contract_status,
        fallback_mode=TemporalFallbackMode.DISCRETE_TIME,
        solver_config=_default_solver_config(
            backend_target=TemporalBackendTarget.DISCRETE_FALLBACK,
            step_size=step_size,
            n_grid_points=int(clipped_grid.size),
        ),
        metadata={
            "preferred_backend": preferred_backend,
            "grid_aligned": False,
            "fallback_reason_code": (
                "irregular_observed_grid" if not regular_grid else "horizon_not_on_grid"
            ),
            "horizon_start_aligned": horizon_start_aligned,
            "horizon_end_aligned": horizon_end_aligned,
            "materialized_contract_id": getattr(materialized, "contract_id", ""),
            "data_time_scale": data_time_scale or query.time_scale,
            "intervention_time_scale": intervention.time_scale,
            "execution_contract_kind": query.query_mode.value,
        },
    )


def _coerce_temporal_data(
    data: Any,
) -> tuple[PanelObservationalData | DynamicTreatmentData, TemporalDataContract, np.ndarray, str]:
    if isinstance(data, PanelObservationalData):
        grid = _extract_numeric_grid(
            data.time_index,
            length=data.n_periods,
            default_name="panel_time_index",
        )
        return data, TemporalDataContract.PANEL_OBSERVATIONAL, grid, "time_index"

    if isinstance(data, DynamicTreatmentData):
        grid = _extract_numeric_grid(
            data.time_ids,
            length=data.n_periods,
            default_name="dynamic_time_ids",
        )
        return data, TemporalDataContract.DYNAMIC_TREATMENT, grid, "time_ids"

    if isinstance(data, dict):
        try:
            panel = PanelObservationalData.model_validate(data)
            grid = _extract_numeric_grid(
                panel.time_index,
                length=panel.n_periods,
                default_name="panel_time_index",
            )
            return panel, TemporalDataContract.PANEL_OBSERVATIONAL, grid, "time_index"
        except Exception:
            dynamic = DynamicTreatmentData.model_validate(data)
            grid = _extract_numeric_grid(
                dynamic.time_ids,
                length=dynamic.n_periods,
                default_name="dynamic_time_ids",
            )
            return dynamic, TemporalDataContract.DYNAMIC_TREATMENT, grid, "time_ids"

    raise TemporalCompileError(
        "unsupported_temporal_data_contract",
        "Expected PanelObservationalData, DynamicTreatmentData, or a compatible mapping.",
        details={"type": type(data).__name__},
    )


def _extract_numeric_grid(values: Any, *, length: int, default_name: str) -> np.ndarray:
    if values is None:
        return np.arange(length, dtype=float)
    grid = np.asarray(values)
    if grid.ndim != 1 or grid.shape[0] != length:
        raise TemporalCompileError(
            "invalid_time_index_shape",
            f"{default_name} must be a 1D array with the same length as the temporal axis.",
            details={"length": length},
        )
    try:
        numeric = grid.astype(float)
    except (TypeError, ValueError) as exc:
        raise TemporalCompileError(
            "non_numeric_time_index",
            f"{default_name} must be numeric for Phase C temporal compilation.",
            details={"error": str(exc)},
        ) from exc
    if not np.isfinite(numeric).all():
        raise TemporalCompileError(
            "non_finite_time_index",
            f"{default_name} contains non-finite values.",
        )
    if np.any(np.diff(numeric) <= 0.0):
        raise TemporalCompileError(
            "non_monotone_time_index",
            f"{default_name} must be strictly increasing.",
        )
    return numeric


def _extract_data_time_scale(data: PanelObservationalData | DynamicTreatmentData) -> str | None:
    metadata = getattr(data, "metadata", {}) or {}
    value = metadata.get("time_scale")
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def _materialize_intervention_to_grid(
    intervention: TemporalInterventionTrajectory,
    time_grid: np.ndarray,
) -> np.ndarray:
    knot_times = np.asarray(intervention.time_points, dtype=float)
    knot_values = np.asarray(intervention.values, dtype=float)
    if time_grid[0] < knot_times[0] - 1e-8 or time_grid[-1] > knot_times[-1] + 1e-8:
        raise TemporalCompileError(
            "intervention_out_of_support",
            "Resolved intervention trajectory does not cover the requested execution horizon.",
            details={
                "intervention_start": float(knot_times[0]),
                "intervention_end": float(knot_times[-1]),
                "grid_start": float(time_grid[0]),
                "grid_end": float(time_grid[-1]),
            },
        )
    if intervention.interpolation_policy is InterventionInterpolationPolicy.LINEAR:
        return np.interp(time_grid, knot_times, knot_values)

    indices = np.searchsorted(knot_times, time_grid, side="right") - 1
    indices = np.clip(indices, 0, knot_values.shape[0] - 1)
    return knot_values[indices]


def _validate_panel_intervention(
    materialized_intervention: np.ndarray,
    *,
    time_index_positions: np.ndarray,
    time_treatment: int,
) -> None:
    if not np.isin(np.round(materialized_intervention), [0, 1]).all() or not np.allclose(
        materialized_intervention,
        np.round(materialized_intervention),
        atol=1e-8,
    ):
        raise TemporalCompileError(
            "unsupported_panel_intervention",
            "Phase C panel temporal execution supports only binary step-like interventions.",
            details={"required_shape": "binary_step_like"},
        )
    expected = np.where(time_index_positions >= int(time_treatment), 1.0, 0.0)
    if not np.allclose(materialized_intervention, expected, atol=1e-8):
        raise TemporalCompileError(
            "unsupported_panel_intervention",
            "Phase C panel temporal execution supports only the observed step intervention defined by time_treatment.",
            details={
                "time_treatment": int(time_treatment),
                "materialized_intervention": materialized_intervention.tolist(),
                "expected_intervention": expected.tolist(),
            },
        )


def _is_regular_grid(grid: np.ndarray) -> bool:
    if grid.size < 2:
        return False
    diffs = np.diff(grid)
    return bool(np.allclose(diffs, diffs[0], atol=1e-8, rtol=1e-8))


def _comparator_for_contract(contract: TemporalDataContract) -> TemporalComparatorSemantics:
    if contract is TemporalDataContract.PANEL_OBSERVATIONAL:
        return TemporalComparatorSemantics.UNTREATED_COUNTERFACTUAL
    return TemporalComparatorSemantics.NEVER_TREAT_BASELINE


def _default_solver_config(
    *,
    backend_target: TemporalBackendTarget,
    step_size: float,
    n_grid_points: int,
) -> dict[str, Any]:
    diffusion_mode = "zero" if backend_target is TemporalBackendTarget.ODE else "estimated"
    solver_family = "euler_maruyama"
    if backend_target is TemporalBackendTarget.DISCRETE_FALLBACK:
        diffusion_mode = "zero"
        solver_family = "discrete_replay"
    return {
        "solver_family": solver_family,
        "dt": float(step_size),
        "n_grid_points": int(n_grid_points),
        "bootstrap_draws": 200,
        "monte_carlo_paths": 256,
        "diffusion_mode": diffusion_mode,
    }


__all__ = [
    "TemporalBackendTarget",
    "TemporalComparatorSemantics",
    "TemporalCompileError",
    "TemporalDataContract",
    "TemporalExecutionPlan",
    "TemporalFallbackMode",
    "compile_temporal_estimand",
]
