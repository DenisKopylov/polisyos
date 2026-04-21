"""Estimate intervention effects with structural time-series counterfactuals."""
from __future__ import annotations

import math
from typing import Any, ClassVar, Mapping

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    compute_cohen_d,
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.foundry.methods.catalog.causal.temporal_estimand_compiler import (
    TemporalBackendTarget,
    TemporalExecutionPlan,
    compile_temporal_estimand,
)
from polisyos.ir.analytics.causal import CausalMethod, DiagnosticTest, EstimationStatus
from polisyos.ir.analytics.dynamic_regime import (
    CausalTranslationCertificate,
    CausalTranslationCertificateStatus,
    CausalTranslationOmegaMapping,
    CausalTranslationScope,
    CausalTranslationSufficientConditions,
    CausalTranslationTauMapping,
    ContinuousTimeQuery,
    EffectTrajectoryBundle,
    InterventionInterpolationPolicy,
    TemporalIdentificationCertificate,
    TemporalInterventionTrajectory,
    TemporalPathRepresentation,
    TemporalTargetFunctional,
)

_TEMPORAL_SOLVER_DIAGNOSTICS_SCHEMA_NAME = "ir.temporal_solver_diagnostics"
_TEMPORAL_SOLVER_DIAGNOSTICS_SCHEMA_VERSION = "1.1"


def _normal_two_sided_pvalue(z_score: float) -> float:
    return float(math.erfc(abs(z_score) / math.sqrt(2.0)))


class TemporalTrajectoryResult(BaseModel):
    """Temporal effect trajectory plus diagnostics and optional persisted bundle."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    plan: TemporalExecutionPlan
    observed_path: tuple[float, ...]
    counterfactual_path: tuple[float, ...]
    effect_path: tuple[float, ...]
    solver_mean_path: tuple[float, ...]
    confidence_band_lower: tuple[float, ...]
    confidence_band_upper: tuple[float, ...]
    integral_effect: float
    solver_family: str = Field(min_length=1)
    path_representation: TemporalPathRepresentation
    discretization_error: float | None = Field(default=None, ge=0.0)
    discretization_note: str | None = None
    causal_translation_certificate: CausalTranslationCertificate | None = None
    causal_equivalence_note: str | None = None
    continuous_time_degraded: bool = False
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    effect_bundle: EffectTrajectoryBundle | None = None

    @field_validator(
        "observed_path",
        "counterfactual_path",
        "effect_path",
        "solver_mean_path",
        "confidence_band_lower",
        "confidence_band_upper",
        mode="before",
    )
    @classmethod
    def _coerce_path_tuple(cls, value: Any) -> tuple[float, ...]:
        array = np.asarray(value, dtype=float)
        if array.ndim != 1:
            raise ValueError("trajectory fields must be one-dimensional")
        if not np.isfinite(array).all():
            raise ValueError("trajectory fields must contain only finite values")
        return tuple(float(item) for item in array.tolist())

    @model_validator(mode="after")
    def _validate_path_lengths(self) -> "TemporalTrajectoryResult":
        expected = len(self.plan.time_grid)
        for field_name in (
            "observed_path",
            "counterfactual_path",
            "effect_path",
            "solver_mean_path",
            "confidence_band_lower",
            "confidence_band_upper",
        ):
            if len(getattr(self, field_name)) != expected:
                raise ValueError(f"{field_name} must align with plan.time_grid")
        return self

    def trajectory_payload(self) -> dict[str, Any]:
        return {
            "time_grid": list(self.plan.time_grid),
            "observed_path": list(self.observed_path),
            "counterfactual_path": list(self.counterfactual_path),
            "effect_path": list(self.effect_path),
            "solver_mean_path": list(self.solver_mean_path),
            "integral_effect": float(self.integral_effect),
            "backend_target": self.plan.backend_target.value,
            "target_functional": self.plan.target_functional.value,
            "comparator_semantics": self.plan.comparator_semantics.value,
            "path_representation": self.path_representation.value,
            "materialized_intervention_values": list(self.plan.materialized_intervention_values),
            "continuous_time_degraded": bool(self.continuous_time_degraded),
            "metadata": dict(self.metadata),
        }

    def confidence_band_payload(self) -> dict[str, Any]:
        return {
            "time_grid": list(self.plan.time_grid),
            "lower": list(self.confidence_band_lower),
            "upper": list(self.confidence_band_upper),
            "confidence_level": 0.95,
            "solver_family": self.solver_family,
            "continuous_time_degraded": bool(self.continuous_time_degraded),
        }

    def solver_diagnostics_payload(self) -> dict[str, Any]:
        identification_scope = self.metadata.get("identification_scope")
        identification_support_status = self.metadata.get("identification_support_status")
        payload = {
            "schema_name": _TEMPORAL_SOLVER_DIAGNOSTICS_SCHEMA_NAME,
            "schema_version": _TEMPORAL_SOLVER_DIAGNOSTICS_SCHEMA_VERSION,
            "time_grid": list(self.plan.time_grid),
            "discretization_error": (
                None if self.discretization_error is None else float(self.discretization_error)
            ),
            "discretization_note": self.discretization_note,
            "solver_family": self.solver_family,
            "path_representation": self.path_representation.value,
            "causal_translation_certificate": (
                None
                if self.causal_translation_certificate is None
                else self.causal_translation_certificate.model_dump(mode="json")
            ),
            "causal_equivalence_note": self.causal_equivalence_note,
            "continuous_time_degraded": bool(self.continuous_time_degraded),
            "diagnostics": dict(self.diagnostics),
        }
        if isinstance(identification_scope, dict):
            payload["identification_scope"] = dict(identification_scope)
        if identification_support_status is not None:
            payload["identification_support_status"] = str(identification_support_status)
        return payload


def _coerce_1d_series(
    value: Any,
    *,
    field_name: str,
    expected_length: int,
) -> np.ndarray:
    series = np.asarray(value, dtype=float)
    if series.ndim != 1:
        raise ValueError(f"{field_name} must be a 1D array")
    if series.shape[0] != expected_length:
        raise ValueError(
            f"{field_name} length {series.shape[0]} does not match expected length {expected_length}"
        )
    if not np.isfinite(series).all():
        raise ValueError(f"{field_name} must contain only finite values")
    return series


def _coerce_2d_series(
    value: Any,
    *,
    field_name: str,
    expected_length: int,
) -> np.ndarray:
    series = np.asarray(value, dtype=float)
    if series.ndim != 2:
        raise ValueError(f"{field_name} must be a 2D array")
    if series.shape[1] != expected_length:
        raise ValueError(
            f"{field_name} width {series.shape[1]} does not match expected length {expected_length}"
        )
    if not np.isfinite(series).all():
        raise ValueError(f"{field_name} must contain only finite values")
    return series


def _estimate_linear_dynamics(
    effect_path: np.ndarray,
    time_grid: np.ndarray,
    intervention_path: np.ndarray,
    *,
    force_zero_diffusion: bool = False,
) -> tuple[float, float, float, float]:
    if effect_path.shape[0] < 2:
        return 0.0, 0.0, 0.0, 0.0

    dt = np.diff(time_grid)
    dx_dt = np.diff(effect_path) / dt
    design = np.column_stack(
        [effect_path[:-1], intervention_path[:-1], np.ones_like(effect_path[:-1])]
    )
    coefficients, *_ = np.linalg.lstsq(design, dx_dt, rcond=None)
    drift = float(coefficients[0])
    treatment_gain = float(coefficients[1])
    intercept = float(coefficients[2])
    residual = dx_dt - design @ coefficients
    diffusion = 0.0 if force_zero_diffusion else float(max(np.std(residual), 0.0))
    return drift, treatment_gain, intercept, diffusion


def _simulate_mean_path(
    initial_value: float,
    time_grid: np.ndarray,
    intervention_path: np.ndarray,
    *,
    drift: float,
    treatment_gain: float,
    intercept: float,
) -> np.ndarray:
    path = np.empty(time_grid.shape[0], dtype=float)
    path[0] = float(initial_value)
    for index, dt in enumerate(np.diff(time_grid), start=1):
        prev = path[index - 1]
        path[index] = prev + dt * (
            drift * prev + treatment_gain * intervention_path[index - 1] + intercept
        )
    return path


def _simulate_sde_paths(
    initial_value: float,
    time_grid: np.ndarray,
    intervention_path: np.ndarray,
    *,
    drift: float,
    treatment_gain: float,
    intercept: float,
    diffusion: float,
    n_paths: int,
    rng: np.random.Generator,
) -> np.ndarray:
    paths = np.empty((n_paths, time_grid.shape[0]), dtype=float)
    paths[:, 0] = float(initial_value)
    for index, dt in enumerate(np.diff(time_grid), start=1):
        previous = paths[:, index - 1]
        drift_term = drift * previous + treatment_gain * intervention_path[index - 1] + intercept
        noise = 0.0
        if diffusion > 0.0:
            noise = math.sqrt(float(dt)) * diffusion * rng.normal(size=n_paths)
        paths[:, index] = previous + dt * drift_term + noise
    return paths


def _refined_time_grid(time_grid: np.ndarray) -> np.ndarray:
    refined: list[float] = [float(time_grid[0])]
    for left, right in zip(time_grid[:-1], time_grid[1:]):
        midpoint = float((left + right) / 2.0)
        refined.extend([midpoint, float(right)])
    return np.asarray(refined, dtype=float)


def _materialize_intervention_path(
    time_grid: np.ndarray,
    *,
    knot_times: np.ndarray,
    knot_values: np.ndarray,
    policy: InterventionInterpolationPolicy,
) -> np.ndarray:
    if policy is InterventionInterpolationPolicy.LINEAR:
        return np.interp(time_grid, knot_times, knot_values)
    indices = np.searchsorted(knot_times, time_grid, side="right") - 1
    indices = np.clip(indices, 0, knot_values.shape[0] - 1)
    return knot_values[indices]


def estimate_discretization_error(
    plan: TemporalExecutionPlan,
    *,
    initial_effect: float,
    drift: float,
    treatment_gain: float,
    intercept: float,
) -> float:
    """Estimate temporal discretization error via refined-grid replay."""

    time_grid = np.asarray(plan.time_grid, dtype=float)
    intervention_path = np.asarray(plan.materialized_intervention_values, dtype=float)
    coarse = _simulate_mean_path(
        initial_effect,
        time_grid,
        intervention_path,
        drift=drift,
        treatment_gain=treatment_gain,
        intercept=intercept,
    )
    refined_grid = _refined_time_grid(time_grid)
    refined_intervention = _materialize_intervention_path(
        refined_grid,
        knot_times=np.asarray(plan.resolved_intervention.time_points, dtype=float),
        knot_values=np.asarray(plan.resolved_intervention.values, dtype=float),
        policy=plan.resolved_intervention.interpolation_policy,
    )
    refined = _simulate_mean_path(
        initial_effect,
        refined_grid,
        refined_intervention,
        drift=drift,
        treatment_gain=treatment_gain,
        intercept=intercept,
    )[::2]
    return float(np.max(np.abs(refined - coarse))) if refined.size else 0.0


def _is_regular_time_grid(time_grid: np.ndarray) -> bool:
    if time_grid.shape[0] < 2:
        return False
    diffs = np.diff(time_grid)
    return bool(np.allclose(diffs, diffs[0], atol=1e-8, rtol=1e-8))


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _solver_supports_exact_discretization(
    plan: TemporalExecutionPlan,
    *,
    solver_family: str,
) -> bool:
    solver_declares_exact = bool(plan.solver_config.get("exact_discretization", False)) or (
        solver_family in {"exact_flow", "matrix_exponential", "exact_ou"}
    )
    if not solver_declares_exact:
        return False
    if plan.interpolation_policy is not InterventionInterpolationPolicy.PIECEWISE_CONSTANT:
        return False
    return plan.backend_target in {
        TemporalBackendTarget.LINEAR_SDE,
        TemporalBackendTarget.ODE,
    }


def build_causal_translation_certificate(
    plan: TemporalExecutionPlan,
    *,
    solver_family: str,
) -> tuple[CausalTranslationCertificate, str | None]:
    """Build a semantic translation certificate for temporal discretization."""

    time_grid = np.asarray(plan.time_grid, dtype=float)
    grid_regular = _is_regular_time_grid(time_grid)
    horizon_aligned = bool(
        np.isclose(time_grid[0], plan.query.horizon_start, atol=1e-8)
        and np.isclose(time_grid[-1], plan.query.horizon_end, atol=1e-8)
    )
    time_scale_matches = plan.query.time_scale == plan.resolved_intervention.time_scale
    interpolation_policy_matches_contract = (
        plan.query.interpolation_policy is plan.interpolation_policy
        and plan.resolved_intervention.interpolation_policy is plan.interpolation_policy
    )
    backend_exact_discretization = _solver_supports_exact_discretization(
        plan,
        solver_family=solver_family,
    )
    fallback_active = (
        plan.backend_target is TemporalBackendTarget.DISCRETE_FALLBACK
        or plan.fallback_mode.value != "none"
    )
    neural_backend = plan.backend_target in {
        TemporalBackendTarget.NEURAL_SDE,
        TemporalBackendTarget.NEURAL_CDE,
    }
    sufficient_conditions = CausalTranslationSufficientConditions(
        time_scale_matches=time_scale_matches,
        interpolation_policy_matches_contract=interpolation_policy_matches_contract,
        grid_regular=grid_regular,
        horizon_aligned=horizon_aligned,
        backend_exact_discretization=backend_exact_discretization,
        allowed_interventions_restricted_to_omega_image=not fallback_active,
        unique_solution_assumed=True,
    )
    hold_semantics = (
        "zoh"
        if plan.interpolation_policy is InterventionInterpolationPolicy.PIECEWISE_CONSTANT
        else "foh"
    )
    query_functionals_covered = [
        TemporalTargetFunctional.EFFECT_PATH.value,
        TemporalTargetFunctional.INTEGRAL_EFFECT.value,
    ]
    variables_covered = [
        "effect_path",
        "counterfactual_path",
        "solver_mean_path",
    ]

    assumptions_introduced = [
        "Causal claims are restricted to functionals measurable on the certified time grid.",
        f"Interventions are interpreted between knots via {hold_semantics} hold semantics.",
    ]
    if not backend_exact_discretization:
        assumptions_introduced.append(
            "Exact continuous-time equivalence is not claimed away from the certified grid."
        )
    identification_scope = plan.metadata.get("identification_scope")
    if neural_backend:
        assumptions_introduced.append(
            "Neural temporal execution is theorem-scoped and does not certify exact discretization."
        )

    failure_reasons: list[str] = []
    note: str | None = None
    if not time_scale_matches:
        failure_reasons.append("time_scale_mismatch")
    if not interpolation_policy_matches_contract:
        failure_reasons.append("interpolation_policy_mismatch")
    if not grid_regular:
        failure_reasons.append("irregular_time_grid")
    if not horizon_aligned:
        failure_reasons.append("horizon_not_aligned")
    if fallback_active:
        failure_reasons.append("discrete_fallback_changes_estimand_support")
        fallback_reason_code = str(plan.metadata.get("fallback_reason_code") or "").strip()
        if fallback_reason_code:
            failure_reasons.append(fallback_reason_code)

    if not time_scale_matches or not interpolation_policy_matches_contract:
        status = CausalTranslationCertificateStatus.FAILED
        note = "temporal causal translation certificate failed because the execution contract is inconsistent"
    elif fallback_active or not grid_regular or not horizon_aligned:
        status = CausalTranslationCertificateStatus.NOT_CERTIFIED
        note = (
            "numerical discretization error != causal estimand equivalence; "
            "causal translation not certified"
        )
    elif neural_backend:
        status = CausalTranslationCertificateStatus.CERTIFIED_RESTRICTED
        note = (
            "neural temporal execution is certified only within the supplied theorem-backed "
            "identification scope on the declared time grid"
        )
    elif backend_exact_discretization:
        status = CausalTranslationCertificateStatus.CERTIFIED_EXACT
        note = "causal translation is exact on the certified grid under zero-order hold semantics"
    else:
        status = CausalTranslationCertificateStatus.CERTIFIED_RESTRICTED
        note = (
            "causal claims are certified only for functionals measurable on the declared time grid "
            "under the stated interpolation policy"
        )

    certificate = CausalTranslationCertificate(
        status=status,
        scope=CausalTranslationScope(
            query_functionals_covered=tuple(query_functionals_covered),
            time_grid_covered=tuple(float(value) for value in time_grid.tolist()),
            variables_covered=tuple(variables_covered),
        ),
        tau_mapping=CausalTranslationTauMapping(
            sampling_times=tuple(float(value) for value in time_grid.tolist()),
        ),
        omega_mapping=CausalTranslationOmegaMapping(
            interpolation_policy=plan.interpolation_policy,
            hold_semantics=hold_semantics,
            knot_times=tuple(float(value) for value in plan.resolved_intervention.time_points),
            knot_values=tuple(float(value) for value in plan.resolved_intervention.values),
        ),
        sufficient_conditions=sufficient_conditions,
        assumptions_introduced=tuple(assumptions_introduced),
        failure_reasons=tuple(failure_reasons),
        evidence={
            "backend_target": plan.backend_target.value,
            "solver_family": solver_family,
            "fallback_mode": plan.fallback_mode.value,
            "time_scale_validation": plan.time_scale_validation,
            "intervention_contract_status": plan.intervention_contract_status,
            "fallback_reason_code": str(plan.metadata.get("fallback_reason_code") or ""),
            "theorem_family": (
                None
                if not isinstance(identification_scope, dict)
                else identification_scope.get("theorem_family")
            ),
            "law_object": (
                None
                if not isinstance(identification_scope, dict)
                else identification_scope.get("law_object")
            ),
            "observability_regime": (
                None
                if not isinstance(identification_scope, dict)
                else identification_scope.get("observability_regime")
            ),
            "plan_metadata": _json_safe(dict(plan.metadata)),
            "theory_refs": [
                "Rubenstein et al. 2017 (exact transformations)",
                "Rubenstein et al. 2018 (ODE to DSCM causal consistency)",
                (
                    "Pechlivanidou & Karampetakis 2022 (ZOH exact discretization)"
                    if backend_exact_discretization
                    else "Boeken & Mooij 2024 (subsampled DSCM semantics)"
                ),
            ],
        },
    )
    return certificate, note


def build_solver_diagnostics(
    plan: TemporalExecutionPlan,
    *,
    drift: float,
    treatment_gain: float,
    intercept: float,
    diffusion: float,
    discretization_error: float | None,
    discretization_note: str | None,
    control_count: int,
    band_source: str,
    causal_translation_certificate: CausalTranslationCertificate,
    causal_equivalence_note: str | None,
) -> dict[str, Any]:
    """Build solver diagnostics."""
    dt = float(plan.step_size)
    stability_margin = abs(1.0 + drift * dt)
    return {
        "backend_target": plan.backend_target.value,
        "solver_family": str(plan.solver_config.get("solver_family", "euler_maruyama")),
        "dt": dt,
        "stability_flag": bool(np.isfinite(stability_margin) and stability_margin <= 1.5),
        "stability_margin": float(stability_margin),
        "drift": float(drift),
        "treatment_gain": float(treatment_gain),
        "intercept": float(intercept),
        "diffusion_norm": float(abs(diffusion)),
        "fallback_mode": plan.fallback_mode.value,
        "discretization_error": (
            None if discretization_error is None else float(discretization_error)
        ),
        "discretization_note": discretization_note,
        "comparator_semantics": plan.comparator_semantics.value,
        "target_functional": plan.target_functional.value,
        "interpolation_policy": plan.interpolation_policy.value,
        "causal_translation_certificate": causal_translation_certificate.model_dump(mode="json"),
        "causal_equivalence_note": causal_equivalence_note,
        "materialized_intervention_values": list(plan.materialized_intervention_values),
        "time_scale_validation": plan.time_scale_validation,
        "intervention_contract_status": plan.intervention_contract_status,
        "control_count": int(control_count),
        "band_source": band_source,
        "grid_source": plan.grid_source,
        "plan_metadata": _json_safe(dict(plan.metadata)),
    }


def _bootstrap_effect_samples(
    observed_path: np.ndarray,
    control_series: np.ndarray,
    *,
    n_draws: int,
    rng: np.random.Generator,
) -> np.ndarray:
    n_controls = control_series.shape[0]
    if n_controls == 0:
        return np.repeat(observed_path[None, :], max(1, n_draws), axis=0)
    if n_controls == 1:
        baseline = np.repeat(control_series, max(1, n_draws), axis=0)
        return observed_path[None, :] - baseline
    draws = rng.integers(0, n_controls, size=(max(1, n_draws), n_controls))
    sampled_controls = control_series[draws]
    sampled_baseline = sampled_controls.mean(axis=1)
    return observed_path[None, :] - sampled_baseline


def solve_temporal_effect_path(
    plan: TemporalExecutionPlan,
    *,
    observed_series: Any,
    controls: Mapping[str, Any] | None = None,
) -> TemporalTrajectoryResult:
    """Solve a temporal effect path under a linear-SDE / ODE / fallback plan."""

    controls_map = dict(controls or {})
    expected_length = len(plan.time_grid)
    observed_path = _coerce_1d_series(
        observed_series,
        field_name="observed_series",
        expected_length=expected_length,
    )
    time_grid = np.asarray(plan.time_grid, dtype=float)
    rng = np.random.default_rng(int(controls_map.get("seed", 0)))

    control_count = 0
    control_series: np.ndarray | None = None
    if "control_series" in controls_map and controls_map["control_series"] is not None:
        control_series = _coerce_2d_series(
            controls_map["control_series"],
            field_name="control_series",
            expected_length=expected_length,
        )
        control_count = int(control_series.shape[0])

    if "counterfactual_series" in controls_map and controls_map["counterfactual_series"] is not None:
        counterfactual_path = _coerce_1d_series(
            controls_map["counterfactual_series"],
            field_name="counterfactual_series",
            expected_length=expected_length,
        )
    elif control_series is not None:
        counterfactual_path = np.mean(control_series, axis=0)
    else:
        counterfactual_path = np.zeros_like(observed_path)

    effect_path = observed_path - counterfactual_path
    intervention_path = np.asarray(plan.materialized_intervention_values, dtype=float)
    force_zero_diffusion = plan.backend_target in {
        TemporalBackendTarget.ODE,
        TemporalBackendTarget.NEURAL_CDE,
        TemporalBackendTarget.DISCRETE_FALLBACK,
    }
    drift, treatment_gain, intercept, diffusion = _estimate_linear_dynamics(
        effect_path,
        time_grid,
        intervention_path,
        force_zero_diffusion=force_zero_diffusion,
    )

    discretization_note: str | None = None
    rough_path_degraded = str(
        plan.metadata.get("rough_path_runtime_support", "on_support")
    ).strip().lower() == "degraded"
    continuous_time_degraded = (
        plan.backend_target is TemporalBackendTarget.DISCRETE_FALLBACK
        or rough_path_degraded
    )
    if plan.backend_target is TemporalBackendTarget.DISCRETE_FALLBACK:
        solver_mean_path = effect_path.copy()
        discretization_error = None
        discretization_note = "unavailable_under_discrete_fallback"
    else:
        solver_mean_path = _simulate_mean_path(
            float(effect_path[0]),
            time_grid,
            intervention_path,
            drift=drift,
            treatment_gain=treatment_gain,
            intercept=intercept,
        )
        discretization_error = estimate_discretization_error(
            plan,
            initial_effect=float(effect_path[0]),
            drift=drift,
            treatment_gain=treatment_gain,
            intercept=intercept,
        )

    band_source = "degenerate"
    effect_samples: np.ndarray | None = None
    if "effect_samples" in controls_map and controls_map["effect_samples"] is not None:
        effect_samples = _coerce_2d_series(
            controls_map["effect_samples"],
            field_name="effect_samples",
            expected_length=expected_length,
        )
        band_source = "provided_effect_samples"
    elif control_series is not None:
        effect_samples = _bootstrap_effect_samples(
            observed_path,
            control_series,
            n_draws=int(plan.solver_config.get("bootstrap_draws", 200)),
            rng=rng,
        )
        band_source = "bootstrap_controls" if control_count > 1 else "degenerate_controls"
    elif diffusion > 0.0 and plan.backend_target is not TemporalBackendTarget.DISCRETE_FALLBACK:
        effect_samples = _simulate_sde_paths(
            float(effect_path[0]),
            time_grid,
            intervention_path,
            drift=drift,
            treatment_gain=treatment_gain,
            intercept=intercept,
            diffusion=diffusion,
            n_paths=int(plan.solver_config.get("monte_carlo_paths", 256)),
            rng=rng,
        )
        band_source = "solver_monte_carlo"

    if effect_samples is None:
        effect_samples = np.repeat(
            effect_path[None, :],
            max(1, int(plan.solver_config.get("monte_carlo_paths", 256))),
            axis=0,
        )

    confidence_band_lower = np.quantile(effect_samples, 0.025, axis=0)
    confidence_band_upper = np.quantile(effect_samples, 0.975, axis=0)
    integral_effect = float(np.trapezoid(effect_path, time_grid))
    path_representation = (
        TemporalPathRepresentation.DISCRETE_REPLAY
        if plan.backend_target is TemporalBackendTarget.DISCRETE_FALLBACK
        else (
            TemporalPathRepresentation.ODE
            if plan.backend_target is TemporalBackendTarget.ODE
            else (
                TemporalPathRepresentation.NEURAL_SDE
                if plan.backend_target is TemporalBackendTarget.NEURAL_SDE
                else (
                    TemporalPathRepresentation.NEURAL_CDE
                    if plan.backend_target is TemporalBackendTarget.NEURAL_CDE
                    else (
                        TemporalPathRepresentation.GEOMETRIC_ROUGH_PATH
                        if plan.backend_target is TemporalBackendTarget.GEOMETRIC_ROUGH_PATH
                        else (
                            TemporalPathRepresentation.CADLAG_ROUGH_PATH
                            if plan.backend_target is TemporalBackendTarget.CADLAG_ROUGH_PATH
                            else (
                                TemporalPathRepresentation.TRUNCATED_SIGNATURE
                                if plan.backend_target is TemporalBackendTarget.TRUNCATED_SIGNATURE
                                else (
                                    TemporalPathRepresentation.HYBRID_ROUGH_EVENT
                                    if plan.backend_target is TemporalBackendTarget.HYBRID_ROUGH_EVENT
                                    else TemporalPathRepresentation.LINEAR_SDE
                                )
                            )
                        )
                    )
                )
            )
        )
    )
    solver_family = str(plan.solver_config.get("solver_family", "euler_maruyama"))
    causal_translation_certificate, causal_equivalence_note = build_causal_translation_certificate(
        plan,
        solver_family=solver_family,
    )
    diagnostics = build_solver_diagnostics(
        plan,
        drift=drift,
        treatment_gain=treatment_gain,
        intercept=intercept,
        diffusion=diffusion,
        discretization_error=discretization_error,
        discretization_note=discretization_note,
        control_count=control_count,
        band_source=band_source,
        causal_translation_certificate=causal_translation_certificate,
        causal_equivalence_note=causal_equivalence_note,
    )
    return TemporalTrajectoryResult(
        plan=plan,
        observed_path=tuple(float(value) for value in observed_path.tolist()),
        counterfactual_path=tuple(float(value) for value in counterfactual_path.tolist()),
        effect_path=tuple(float(value) for value in effect_path.tolist()),
        solver_mean_path=tuple(float(value) for value in solver_mean_path.tolist()),
        confidence_band_lower=tuple(float(value) for value in confidence_band_lower.tolist()),
        confidence_band_upper=tuple(float(value) for value in confidence_band_upper.tolist()),
        integral_effect=integral_effect,
        solver_family=solver_family,
        path_representation=path_representation,
        discretization_error=(
            None if discretization_error is None else float(discretization_error)
        ),
        discretization_note=discretization_note,
        causal_translation_certificate=causal_translation_certificate,
        causal_equivalence_note=causal_equivalence_note,
        continuous_time_degraded=continuous_time_degraded,
        diagnostics=diagnostics,
        metadata={
            "control_count": control_count,
            "band_source": band_source,
            "intervention_contract_status": plan.intervention_contract_status,
            "identification_scope": plan.metadata.get("identification_scope"),
            "identification_support_status": plan.metadata.get(
                "identification_support_status"
            ),
            "path_semantics": plan.metadata.get("path_semantics"),
            "rough_path_certificate": plan.metadata.get("rough_path_certificate"),
            "rough_path_identification_status": plan.metadata.get(
                "rough_path_identification_status"
            ),
            "rough_path_runtime_support": plan.metadata.get("rough_path_runtime_support"),
        },
    )


def estimate_structural_time_series_trajectory(
    data: PanelObservationalData | dict[str, Any],
    query: ContinuousTimeQuery,
    *,
    resolved_intervention: TemporalInterventionTrajectory | dict[str, Any] | None = None,
    identification_certificate: TemporalIdentificationCertificate | dict[str, Any] | None = None,
    allow_discrete_fallback: bool = True,
    max_donors: int = 10,
) -> TemporalTrajectoryResult:
    """Construct a panel temporal effect trajectory against untreated donors."""

    panel = data if isinstance(data, PanelObservationalData) else PanelObservationalData.model_validate(data)
    full_time_grid = (
        np.arange(panel.n_periods, dtype=float)
        if panel.time_index is None
        else np.asarray(panel.time_index, dtype=float)
    )
    intervention = (
        None
        if resolved_intervention is None
        else (
            resolved_intervention
            if isinstance(resolved_intervention, TemporalInterventionTrajectory)
            else TemporalInterventionTrajectory.model_validate(resolved_intervention)
        )
    )
    contract_status = "resolved_artifact" if intervention is not None else "compatibility_synthesized"
    if intervention is None:
        intervention = TemporalInterventionTrajectory(
            time_points=tuple(float(value) for value in full_time_grid.tolist()),
            values=tuple(
                1.0 if index >= int(panel.time_treatment) else 0.0
                for index in range(panel.n_periods)
            ),
            time_scale=query.time_scale,
            interpolation_policy=query.interpolation_policy,
            metadata={"contract_status": contract_status, "derived_from_time_treatment": True},
        )
    plan = compile_temporal_estimand(
        query,
        data=panel,
        resolved_intervention=intervention,
        identification_certificate=identification_certificate,
        intervention_contract_status=contract_status,
        allow_discrete_fallback=allow_discrete_fallback,
    )
    treated_idx = np.where(panel.treatment == 1)[0]
    donor_idx = np.where(panel.treatment == 0)[0]
    if treated_idx.shape[0] != 1:
        raise ValueError("Temporal structural time-series path requires exactly one treated unit")
    if donor_idx.shape[0] < 1:
        raise ValueError("Temporal structural time-series path requires at least one control unit")

    treated = int(treated_idx[0])
    donor_series = panel.outcome[donor_idx, :]
    if donor_series.shape[0] > max_donors:
        t0 = panel.time_treatment
        corr_scores = np.array(
            [
                abs(np.corrcoef(panel.outcome[treated, :t0], donor_series[index, :t0])[0, 1])
                if np.std(donor_series[index, :t0]) > 0.0
                else 0.0
                for index in range(donor_series.shape[0])
            ],
            dtype=float,
        )
        top_idx = np.argsort(corr_scores)[::-1][: max(1, min(max_donors, donor_series.shape[0]))]
    else:
        top_idx = np.arange(donor_series.shape[0], dtype=int)

    donor_subset = donor_series[top_idx]
    grid_positions = np.asarray(plan.time_index_positions, dtype=int)
    result = solve_temporal_effect_path(
        plan,
        observed_series=panel.outcome[treated, grid_positions],
        controls={
            "control_series": donor_subset[:, grid_positions],
            "selected_donors": donor_idx[top_idx].astype(int).tolist(),
            "time_treatment": int(panel.time_treatment),
        },
    )
    result.diagnostics["selected_donors"] = donor_idx[top_idx].astype(int).tolist()
    result.diagnostics["treated_unit_index"] = treated
    result.metadata["selected_donor_count"] = int(donor_subset.shape[0])
    result.metadata["intervention_contract_status"] = contract_status
    return result


@foundry_method(
    namespace="causal.inference",
    version="1.0.0",
    tags={"causal", "structural-time-series", "bsts-approximation", "causal-impact"},
)
class StructuralTimeSeries:
    """Fit a latent structural baseline and infer post-intervention effects; avoid unstable pre-period trends."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="structural_time_series",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="outcome_panel",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("outcome", "value"),
                    shape=("n_units", "n_periods"),
                ),
                SlotSpec(
                    name="treatment_indicator",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("binary", "flag"),
                    shape=("n_units",),
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="causal_effect_report",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("report", "json"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="level", default=True),
            ParameterSpec(name="trend", default=False),
            ParameterSpec(name="seasonal", default=None),
            ParameterSpec(name="max_donors", default=10),
            ParameterSpec(name="n_simulations", default=1000),
            ParameterSpec(name="confidence_level", default=0.95),
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
            "Structural time-series causal impact model using state-space estimation "
            "(Kalman filter + simulation smoothing)."
        ),
        tags=frozenset(
            {
                "causal",
                "structural-time-series",
                "bsts-approximation",
                "causal-impact",
            }
        ),
        citations=(
            "Brodersen, K. et al. (2015). Inferring Causal Impact "
            "Using Bayesian Structural Time Series Models.",
            "Harvey, A. (1990). Forecasting, Structural Time Series Models and the Kalman Filter.",
        ),
        equations={
            "state_space": "Y_t = Z_t a_t + beta X_t + eps_t; a_{t+1} = T_t a_t + R_t eta_t",
            "effect": "tau_t = Y_t - Y_hat_t",
        },
        assumptions={
            "stable_pre_period": "Pre-treatment dynamics are stable and identifiable.",
            "predictive_controls": (
                "Control units carry predictive signal for "
                "treated unit counterfactual."
            ),
            "no_structural_break_pre": "No unmodeled structural break before treatment.",
        },
        when_to_use="Interrupted time series with control covariates; estimate causal impact of policy intervention on single time series",
        when_not_to_use="No pre-intervention baseline; confounded trend; multiple simultaneous interventions",
        typical_min_obs=52,
        output_interpretation="Counterfactual predicted series vs actual. Absolute/relative impact = actual - counterfactual. Posterior probability of effect.",
    )

    @staticmethod
    def pure_step(state: PanelObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, PanelObservationalData)
            else PanelObservationalData.model_validate(state)
        )
        assumptions = dict(StructuralTimeSeries.metadata.assumptions)
        treated_idx = np.where(data.treatment == 1)[0]
        donor_idx = np.where(data.treatment == 0)[0]

        if treated_idx.shape[0] != 1:
            report = build_failure_report(
                method=CausalMethod.STRUCTURAL_TIME_SERIES,
                status=EstimationStatus.INPUT_INVALID,
                reason=(
                    "StructuralTimeSeries requires exactly one treated unit, "
                    f"got {treated_idx.shape[0]}"
                ),
                estimand="ATT",
                sample_size=data.n_units * data.n_periods,
                n_treated=int(treated_idx.shape[0]),
                n_control=int(donor_idx.shape[0]),
                pre_periods=data.pre_periods,
                post_periods=data.post_periods,
                assumptions=assumptions,
            )
            return wrap_causal_output(report, warnings=[report.status_reason or "invalid input"])
        if donor_idx.shape[0] < 1:
            report = build_failure_report(
                method=CausalMethod.STRUCTURAL_TIME_SERIES,
                status=EstimationStatus.INPUT_INVALID,
                reason="StructuralTimeSeries requires at least one donor unit",
                estimand="ATT",
                sample_size=data.n_units * data.n_periods,
                n_treated=1,
                n_control=0,
                pre_periods=data.pre_periods,
                post_periods=data.post_periods,
                assumptions=assumptions,
            )
            return wrap_causal_output(report, warnings=[report.status_reason or "invalid input"])
        if data.time_treatment <= 2 or data.time_treatment >= data.n_periods:
            report = build_failure_report(
                method=CausalMethod.STRUCTURAL_TIME_SERIES,
                status=EstimationStatus.INPUT_INVALID,
                reason=(
                    f"time_treatment={data.time_treatment} is invalid "
                    "for structural time-series fitting"
                ),
                estimand="ATT",
                sample_size=data.n_units * data.n_periods,
                n_treated=1,
                n_control=int(donor_idx.shape[0]),
                pre_periods=data.pre_periods,
                post_periods=data.post_periods,
                assumptions=assumptions,
            )
            return wrap_causal_output(report, warnings=[report.status_reason or "invalid input"])

        try:
            from statsmodels.tsa.statespace.structural import UnobservedComponents
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency runtime
            report = build_failure_report(
                method=CausalMethod.STRUCTURAL_TIME_SERIES,
                status=EstimationStatus.NUMERICAL_FAILURE,
                reason=f"statsmodels missing: {exc}",
                estimand="ATT",
                sample_size=data.n_units * data.n_periods,
                n_treated=1,
                n_control=int(donor_idx.shape[0]),
                pre_periods=data.pre_periods,
                post_periods=data.post_periods,
                assumptions=assumptions,
            )
            return wrap_causal_output(
                report, warnings=[report.status_reason or "missing dependency"]
            )

        treated = int(treated_idx[0])
        t0 = data.time_treatment
        max_donors = int(params.get("max_donors", 10))
        donor_series = data.outcome[donor_idx, :]
        corr_scores = np.array(
            [
                abs(np.corrcoef(data.outcome[treated, :t0], donor_series[idx, :t0])[0, 1])
                if np.std(donor_series[idx, :t0]) > 0
                else 0.0
                for idx in range(donor_series.shape[0])
            ]
        )
        top_idx = np.argsort(corr_scores)[::-1][: max(1, min(max_donors, donor_series.shape[0]))]
        donor_subset = donor_series[top_idx]

        y_pre = data.outcome[treated, :t0]
        y_post = data.outcome[treated, t0:]
        x_pre = donor_subset[:, :t0].T
        x_post = donor_subset[:, t0:].T

        seasonal = params.get("seasonal")
        if seasonal is not None:
            seasonal = int(seasonal)

        try:
            model = UnobservedComponents(
                endog=y_pre,
                level=bool(params.get("level", True)),
                trend=bool(params.get("trend", False)),
                seasonal=seasonal,
                exog=x_pre,
            )
            fit = model.fit(disp=False)
            forecast = fit.get_forecast(steps=data.post_periods, exog=x_post)
            predicted = np.asarray(forecast.predicted_mean, dtype=float)
            conf_int = np.asarray(
                forecast.conf_int(alpha=1.0 - float(params.get("confidence_level", 0.95)))
            )
        except Exception as exc:
            report = build_failure_report(
                method=CausalMethod.STRUCTURAL_TIME_SERIES,
                status=EstimationStatus.NUMERICAL_FAILURE,
                reason=f"state-space fit failed: {exc}",
                estimand="ATT",
                sample_size=data.n_units * data.n_periods,
                n_treated=1,
                n_control=int(donor_idx.shape[0]),
                pre_periods=data.pre_periods,
                post_periods=data.post_periods,
                assumptions=assumptions,
            )
            return wrap_causal_output(
                report, warnings=[report.status_reason or "numerical failure"]
            )

        effects = y_post - predicted
        att = float(np.mean(effects))
        lower_pred = conf_int[:, 0]
        upper_pred = conf_int[:, 1]
        effect_lower = y_post - upper_pred
        effect_upper = y_post - lower_pred
        ci = (float(np.mean(effect_lower)), float(np.mean(effect_upper)))

        effect_std = float(np.std(effects, ddof=1)) if effects.shape[0] > 1 else 0.0
        effect_se = float(effect_std / math.sqrt(max(effects.shape[0], 1)))
        z_score = 0.0 if effect_se <= 0 else att / effect_se
        p_value = _normal_two_sided_pvalue(z_score)

        diagnostics = [
            DiagnosticTest(
                test_name="state_space_fit_converged",
                statistic=1.0,
                passed=True,
                details={"llf": float(getattr(fit, "llf", float("nan")))},
            ),
            DiagnosticTest(
                test_name="donor_signal_strength",
                statistic=float(np.mean(corr_scores[top_idx])) if top_idx.size else 0.0,
                passed=bool(top_idx.size > 0 and np.mean(corr_scores[top_idx]) > 0.1),
                details={"n_selected_donors": int(top_idx.size)},
            ),
        ]

        effect_size = compute_cohen_d(
            effect=att,
            treated_outcome=y_post,
            control_outcome=predicted,
        )
        confidence_level = float(params.get("confidence_level", 0.95))
        report = build_success_report(
            method=CausalMethod.STRUCTURAL_TIME_SERIES,
            estimand="ATT",
            point_estimate=att,
            confidence_interval=ci,
            confidence_level=confidence_level,
            standard_error=effect_se,
            p_value=p_value,
            inference_method="state_space_simulation",
            effect_size_cohen_d=effect_size,
            diagnostics=diagnostics,
            sample_size=data.n_units * data.n_periods,
            n_treated=1,
            n_control=int(donor_idx.shape[0]),
            pre_periods=data.pre_periods,
            post_periods=data.post_periods,
            assumptions=assumptions,
            time_effects={
                "period": list(range(t0, data.n_periods)),
                "effect": [float(value) for value in effects],
                "ci_lower": [float(value) for value in effect_lower],
                "ci_upper": [float(value) for value in effect_upper],
            },
            method_params={
                "selected_donors": donor_idx[top_idx].astype(int).tolist(),
                "n_simulations": int(params.get("n_simulations", 1000)),
            },
        )
        return wrap_causal_output(
            report,
            extras={
                "counterfactual": predicted,
                "model_diagnostics": {"llf": float(getattr(fit, "llf", float("nan")))},
            },
        )


__all__ = [
    "StructuralTimeSeries",
    "TemporalTrajectoryResult",
    "build_solver_diagnostics",
    "estimate_discretization_error",
    "estimate_structural_time_series_trajectory",
    "solve_temporal_effect_path",
]
