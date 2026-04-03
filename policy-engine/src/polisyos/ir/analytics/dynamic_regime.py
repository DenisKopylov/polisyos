"""IR models for dynamic treatment regimes and temporal causal inference.

Covers g-computation results, SNMM (g-estimation), DTR (Q/A-learning, OWL),
off-policy evaluation, causal bandits, and Phase C continuous-time effect
trajectory contracts.

References:
    Robins (1986). A new approach to causal inference in mortality studies.
    Hernán & Robins (2020). Causal Inference: What If. Chapman & Hall.
    Murphy (2003). Optimal dynamic treatment regimes. JRSS-B.
    Lattimore, Munos & Szepesvári (2016). Causal bandits. NeurIPS.
"""
from __future__ import annotations

import math
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import (
    ArtifactRefModel,
    ContinuousTimeQueryRef,
    DynamicTreatmentRegimeRef,
    EffectTrajectoryBundleRef,
    TemporalInterventionTrajectoryRef,
)

_CONTINUOUS_TIME_QUERY_SCHEMA_NAME = "ir.continuous_time_query"
_CONTINUOUS_TIME_QUERY_SCHEMA_VERSION = "1.0"
_TEMPORAL_INTERVENTION_TRAJECTORY_SCHEMA_NAME = "ir.temporal_intervention_trajectory"
_TEMPORAL_INTERVENTION_TRAJECTORY_SCHEMA_VERSION = "1.0"
_DYNAMIC_TREATMENT_REGIME_SCHEMA_NAME = "ir.dynamic_treatment_regime"
_DYNAMIC_TREATMENT_REGIME_SCHEMA_VERSION = "1.0"
_EFFECT_TRAJECTORY_BUNDLE_SCHEMA_NAME = "ir.effect_trajectory_bundle"
_EFFECT_TRAJECTORY_BUNDLE_SCHEMA_VERSION = "1.0"


def _validate_non_empty_ref(ref: ArtifactRefModel, *, field_name: str) -> ArtifactRefModel:
    if not str(ref.kind).strip():
        raise ValueError(f"{field_name}.kind must be non-empty")
    if not str(ref.media_type).strip():
        raise ValueError(f"{field_name}.media_type must be non-empty")
    return ref


def _coerce_finite_float(value: Any, *, field_name: str) -> float:
    casted = float(value)
    if not math.isfinite(casted):
        raise ValueError(f"{field_name} must be finite")
    return casted


class TemporalTargetFunctional(str, Enum):
    """Functionals over an intervention-induced effect path on a time horizon."""

    EFFECT_PATH = "effect_path"
    INTEGRAL_EFFECT = "integral_effect"
    TIME_TO_THRESHOLD = "time_to_threshold"
    OCCUPANCY_PROBABILITY = "occupancy_probability"


class TemporalPathRepresentation(str, Enum):
    """Model family used to represent the trajectory-level causal object."""

    LINEAR_SDE = "linear_sde"
    ODE = "ode"
    DISCRETE_REPLAY = "discrete_replay"
    NEURAL_CDE = "neural_cde"
    NEURAL_SDE = "neural_sde"


class TemporalSamplingScheme(str, Enum):
    """Observation schedule used to connect the temporal query to data."""

    REGULAR_GRID = "regular_grid"
    IRREGULAR_GRID = "irregular_grid"


class InterventionInterpolationPolicy(str, Enum):
    """How interventions are interpolated between observed control points."""

    PIECEWISE_CONSTANT = "piecewise_constant"
    LINEAR = "linear"


class StrategicAdaptationMode(str, Enum):
    """Whether strategic response is excluded or modeled outside the trajectory."""

    ABSENT = "absent"
    MODELED_SEPARATELY = "modeled_separately"


class TemporalQueryMode(str, Enum):
    """Canonical execution mode for a temporal causal query."""

    FIXED_INTERVENTION = "fixed_intervention"
    OPTIMAL_POLICY_DISCOVERY = "optimal_policy_discovery"


class RuntimeSupportStatus(str, Enum):
    """Machine-readable runtime support surface for temporal contracts."""

    SUPPORTED = "supported"
    DEGRADED = "degraded"
    BLOCKED_RESEARCH = "blocked_research"
    BLOCKED_UNSUPPORTED = "blocked_unsupported"


def _preferred_backend(metadata: dict[str, Any]) -> str:
    return str(metadata.get("preferred_backend", "linear_sde")).strip().lower()


class TemporalInterventionTrajectory(BaseModel):
    """Executable intervention trajectory contract for continuous-time queries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    time_points: tuple[float, ...]
    values: tuple[float, ...]
    time_scale: str = Field(min_length=1)
    interpolation_policy: InterventionInterpolationPolicy = (
        InterventionInterpolationPolicy.PIECEWISE_CONSTANT
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("time_points", "values", mode="before")
    @classmethod
    def _coerce_float_tuple(cls, value: Any, info: Any) -> tuple[float, ...]:
        if not isinstance(value, (tuple, list)):
            raise ValueError(f"{info.field_name} must be a tuple/list of finite floats")
        result = tuple(_coerce_finite_float(item, field_name=str(info.field_name)) for item in value)
        if len(result) < 2:
            raise ValueError(f"{info.field_name} must contain at least two points")
        return result

    @field_validator("time_scale")
    @classmethod
    def _validate_time_scale(cls, value: str) -> str:
        candidate = str(value).strip()
        if not candidate:
            raise ValueError("time_scale must be non-empty")
        return candidate

    @model_validator(mode="after")
    def _validate_trajectory(self) -> "TemporalInterventionTrajectory":
        if len(self.time_points) != len(self.values):
            raise ValueError("time_points and values must have equal length")
        for left, right in zip(self.time_points[:-1], self.time_points[1:]):
            if right <= left:
                raise ValueError("time_points must be strictly increasing")
        return self

    @property
    def is_binary_schedule(self) -> bool:
        return all(math.isclose(value, round(value), abs_tol=1e-8) and round(value) in {0, 1} for value in self.values)


class ContinuousTimeQuery(BaseModel):
    """Continuous-time causal query over a bounded time horizon."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    query_mode: TemporalQueryMode = TemporalQueryMode.FIXED_INTERVENTION
    intervention_trajectory_ref: ArtifactRefModel | None = None
    outcome_process: str = Field(min_length=1)
    horizon_start: float
    horizon_end: float
    target_functional: TemporalTargetFunctional = TemporalTargetFunctional.EFFECT_PATH
    sampling_scheme: TemporalSamplingScheme = TemporalSamplingScheme.REGULAR_GRID
    time_scale: str = Field(min_length=1)
    interpolation_policy: InterventionInterpolationPolicy = (
        InterventionInterpolationPolicy.PIECEWISE_CONSTANT
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("outcome_process", "time_scale")
    @classmethod
    def _validate_non_empty_strings(cls, value: str) -> str:
        candidate = str(value).strip()
        if not candidate:
            raise ValueError("string fields must be non-empty")
        return candidate

    @field_validator("horizon_start", "horizon_end", mode="before")
    @classmethod
    def _validate_horizon_value(cls, value: Any, info: Any) -> float:
        return _coerce_finite_float(value, field_name=str(info.field_name))

    @model_validator(mode="after")
    def _validate_time_contract(self) -> "ContinuousTimeQuery":
        if self.query_mode is TemporalQueryMode.FIXED_INTERVENTION:
            if self.intervention_trajectory_ref is None:
                raise ValueError(
                    "intervention_trajectory_ref is required for fixed_intervention queries"
                )
            _validate_non_empty_ref(
                self.intervention_trajectory_ref,
                field_name="intervention_trajectory_ref",
            )
        elif self.intervention_trajectory_ref is not None:
            _validate_non_empty_ref(
                self.intervention_trajectory_ref,
                field_name="intervention_trajectory_ref",
            )
        if self.horizon_start >= self.horizon_end:
            raise ValueError("horizon_start must be strictly less than horizon_end")
        return self

    @property
    def is_research_gated(self) -> bool:
        """True when the query requires research-track temporal semantics."""

        return any(reason.startswith("research_gated_") for reason in self.runtime_blockers)

    @property
    def runtime_blockers(self) -> tuple[str, ...]:
        blockers: list[str] = []
        if self.sampling_scheme is TemporalSamplingScheme.IRREGULAR_GRID:
            blockers.append("research_gated_sampling_scheme")
        if self.target_functional not in {
            TemporalTargetFunctional.EFFECT_PATH,
            TemporalTargetFunctional.INTEGRAL_EFFECT,
        }:
            blockers.append("unsupported_target_functional")
        preferred_backend = _preferred_backend(self.metadata)
        if preferred_backend in {"neural_cde", "neural_sde"}:
            blockers.append("research_gated_backend")
        elif preferred_backend not in {"linear_sde", "ode"}:
            blockers.append("unsupported_backend_target")
        return tuple(blockers)

    @property
    def runtime_support_status(self) -> RuntimeSupportStatus:
        if not self.runtime_blockers:
            return RuntimeSupportStatus.SUPPORTED
        if any(reason.startswith("research_gated_") for reason in self.runtime_blockers):
            return RuntimeSupportStatus.BLOCKED_RESEARCH
        return RuntimeSupportStatus.BLOCKED_UNSUPPORTED

    @property
    def runtime_eligible(self) -> bool:
        """True when current engineering scope can execute the query."""

        return self.runtime_support_status is RuntimeSupportStatus.SUPPORTED


class EffectTrajectoryBundle(BaseModel):
    """Canonical public contract for temporal effect trajectories and diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    query_ref: ContinuousTimeQueryRef
    trajectory_ref: ArtifactRefModel
    confidence_band_ref: ArtifactRefModel
    solver_diagnostics_ref: ArtifactRefModel
    discretization_error: float | None = Field(default=None, ge=0.0)
    discretization_note: str | None = None
    path_representation: TemporalPathRepresentation
    solver_family: str = Field(min_length=1)
    time_scale: str = Field(min_length=1)
    interpolation_policy: InterventionInterpolationPolicy = (
        InterventionInterpolationPolicy.PIECEWISE_CONSTANT
    )
    strategic_adaptation_mode: StrategicAdaptationMode = StrategicAdaptationMode.ABSENT
    continuous_time_degraded: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("solver_family", "time_scale", "discretization_note")
    @classmethod
    def _validate_bundle_strings(cls, value: str) -> str:
        if value is None:
            return value
        candidate = str(value).strip()
        if not candidate:
            raise ValueError("string fields must be non-empty")
        return candidate

    @field_validator("discretization_error", mode="before")
    @classmethod
    def _validate_discretization_error(cls, value: Any) -> Any:
        if value is None:
            return None
        casted = _coerce_finite_float(value, field_name="discretization_error")
        if casted < 0.0:
            raise ValueError("discretization_error must be non-negative")
        return casted

    @model_validator(mode="after")
    def _validate_bundle_refs(self) -> "EffectTrajectoryBundle":
        _validate_non_empty_ref(self.trajectory_ref, field_name="trajectory_ref")
        _validate_non_empty_ref(self.confidence_band_ref, field_name="confidence_band_ref")
        _validate_non_empty_ref(
            self.solver_diagnostics_ref,
            field_name="solver_diagnostics_ref",
        )
        if self.path_representation is TemporalPathRepresentation.DISCRETE_REPLAY:
            if self.discretization_error is not None:
                raise ValueError("discrete fallback bundles must not claim a numeric discretization_error")
            if self.discretization_note is None:
                raise ValueError("discrete fallback bundles must disclose why discretization_error is unavailable")
            if not self.continuous_time_degraded:
                raise ValueError("discrete fallback bundles must set continuous_time_degraded=true")
        elif self.discretization_error is None and self.discretization_note is None:
            raise ValueError("bundles must publish discretization_error or a discretization_note")
        return self

    @property
    def is_research_gated(self) -> bool:
        """True when the represented path family is outside current runtime scope."""

        return self.path_representation in {
            TemporalPathRepresentation.NEURAL_CDE,
            TemporalPathRepresentation.NEURAL_SDE,
        }

    @property
    def runtime_eligible(self) -> bool:
        """True when current engineering scope can consume the bundle at runtime."""

        return self.runtime_support_status in {
            RuntimeSupportStatus.SUPPORTED,
            RuntimeSupportStatus.DEGRADED,
        }

    @property
    def runtime_blockers(self) -> tuple[str, ...]:
        if self.is_research_gated:
            return ("research_gated_path_representation",)
        return ()

    @property
    def runtime_support_status(self) -> RuntimeSupportStatus:
        if self.is_research_gated:
            return RuntimeSupportStatus.BLOCKED_RESEARCH
        if self.path_representation is TemporalPathRepresentation.DISCRETE_REPLAY:
            return RuntimeSupportStatus.DEGRADED
        return RuntimeSupportStatus.SUPPORTED


class RegimeRule(str, Enum):
    """How a dynamic treatment regime assigns treatment at each time point."""

    ALWAYS_TREAT = "always_treat"
    NEVER_TREAT = "never_treat"
    THRESHOLD = "threshold"  # treat if covariate_t > threshold_value
    LINEAR_BLIP = "linear_blip"  # treat if blip(H_t) > 0
    EXPLICIT_SCHEDULE = "explicit_schedule"  # apply a fixed binary action schedule


class DynamicTreatmentRegime(BaseModel):
    """Specification of a dynamic treatment regime d = (d_0, ..., d_{T-1}).

    A regime maps each unit's observed history H_t to an action A_t ∈ {0, 1}:
        A_t = d_t(H_t)  for t = 0, 1, ..., T-1
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    time_points: tuple[int, ...] = Field(
        description="Sorted sequence of time indices (0-based)."
    )
    treatment_variables: tuple[str, ...] = Field(
        description="Names of treatment variables A_0, A_1, ... in temporal order."
    )
    time_varying_covariates: tuple[str, ...] = Field(
        description="Names of time-varying covariate variables L_0, L_1, ..."
    )
    outcome: str = Field(description="Name of the outcome variable Y.")
    rule: RegimeRule = RegimeRule.ALWAYS_TREAT
    threshold_covariate_index: int = Field(
        default=0,
        ge=0,
        description="Index of the covariate used for threshold rule.",
    )
    threshold_value: float = Field(
        default=0.0,
        description="Threshold value for THRESHOLD rule: treat if L[idx] > threshold.",
    )
    regime_coefficients: tuple[float, ...] | None = Field(
        default=None,
        description="Linear blip coefficients ψ for LINEAR_BLIP rule.",
    )
    scheduled_actions: tuple[int, ...] | None = Field(
        default=None,
        description="Explicit binary action schedule for EXPLICIT_SCHEDULE rule.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_scheduled_actions(self) -> "DynamicTreatmentRegime":
        if self.rule is RegimeRule.EXPLICIT_SCHEDULE:
            if self.scheduled_actions is None:
                raise ValueError("scheduled_actions are required for EXPLICIT_SCHEDULE regimes")
            if len(self.scheduled_actions) != len(self.time_points):
                raise ValueError("scheduled_actions must align with time_points")
            if any(action not in {0, 1} for action in self.scheduled_actions):
                raise ValueError("scheduled_actions must be binary")
        return self


class GComputationResult(BaseModel):
    """Result of g-computation E[Y^{ā}] under a dynamic treatment regime.

    Computed by ParametricGFormula, ICEGFormula, or LTMLEEstimator.
    """

    model_config = ConfigDict(extra="forbid")

    counterfactual_mean: float = Field(
        description="Point estimate E[Y^{ā}] under the specified regime."
    )
    confidence_interval: tuple[float, float] = Field(
        description="Bootstrap or asymptotic confidence interval (lo, hi)."
    )
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    standard_error: float = Field(ge=0.0)
    regime: str = Field(description="RegimeRule value used (e.g. 'always_treat').")
    n_units: int = Field(ge=1)
    n_periods: int = Field(ge=1)
    method: Literal["parametric_g", "ice_g", "ltmle"] = "ice_g"
    sequential_ignorability_assumed: bool = True
    convergence_warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


class SNMMResult(BaseModel):
    """Result of Structural Nested Mean Model (SNMM) fitted via g-estimation.

    psi_estimates contains the blip function parameters ψ = (ψ_0, ..., ψ_K)
    for the linear blip γ(a_t, H_t; ψ) = ψ_0·a_t + ψ_1·a_t·L_{t,1} + ...

    References:
        Robins (1994). Correcting for non-compliance in randomized trials.
    """

    model_config = ConfigDict(extra="forbid")

    psi_estimates: tuple[float, ...] = Field(
        description="Blip function parameter estimates ψ̂ per blip feature."
    )
    psi_std_errors: tuple[float, ...] = Field(
        description="Bootstrap standard errors for each ψ̂ estimate."
    )
    blip_model: Literal["linear", "interaction", "quadratic"] = "linear"
    n_units: int = Field(ge=1)
    n_periods: int = Field(ge=1)
    optimal_regime: DynamicTreatmentRegime | None = None
    convergence_iterations: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DTRResult(BaseModel):
    """Result of Dynamic Treatment Regime estimation (Q-learning, A-learning, OWL, DR-DTR).

    Contains the estimated optimal dynamic regime and its value E[Y^{d*}].

    References:
        Murphy (2003). Optimal dynamic treatment regimes. JRSS-B.
        Zhao et al. (2012). Estimating individualized treatment rules using outcome weighted
            learning. JASA.
        Zhang et al. (2013). Robust estimation of optimal dynamic treatment regimes.
    """

    model_config = ConfigDict(extra="forbid")

    method: Literal["q_learning", "a_learning", "owl", "dr_dtr"]
    optimal_regime: DynamicTreatmentRegime = Field(
        description="Estimated optimal regime d*(H_t) at each stage."
    )
    value_estimate: float = Field(
        description="E[Y^{d*}]: expected outcome under optimal regime."
    )
    value_ci: tuple[float, float] = Field(
        description="Bootstrap confidence interval for value_estimate."
    )
    n_units: int = Field(ge=1)
    n_stages: int = Field(ge=1)
    stage_coefficients: tuple[tuple[float, ...], ...] = Field(
        description="Per-stage model coefficients (Q-function or blip function weights)."
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class OPEResult(BaseModel):
    """Result of Off-Policy Evaluation (IS or DR estimator).

    Estimates V^π = E_{π}[Y] from historical data collected under π_b ≠ π.

    References:
        Precup, Sutton & Singh (2000). Eligibility traces for off-policy policy evaluation.
        Dudík, Langford & Li (2011). Doubly robust policy evaluation and learning.
    """

    model_config = ConfigDict(extra="forbid")

    method: Literal["is", "dr"]
    policy_value: float = Field(
        description="Estimated value V̂^π of the target policy."
    )
    confidence_interval: tuple[float, float]
    effective_sample_size: float = Field(
        ge=0.0,
        description="Kish's ESS = (Σ ρ_i)^2 / Σ ρ_i^2 — lower means high variance.",
    )
    n_trajectories: int = Field(ge=1)
    importance_weight_max: float = Field(
        ge=0.0,
        description="Max importance ratio max_i ρ_i — large value signals overlap issues.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class BanditResult(BaseModel):
    """Result of causal bandit simulation.

    Estimates the optimal intervention arm using causal effect estimates + UCB exploration.

    References:
        Lattimore, Munos & Szepesvári (2016). Causal bandits. NeurIPS.
        Bareinboim, Forney & Pearl (2015). Bandits with unobserved confounders. NeurIPS.
    """

    model_config = ConfigDict(extra="forbid")

    optimal_arm: str = Field(description="Name of the arm with highest estimated effect.")
    arm_estimates: dict[str, float] = Field(
        description="Mapping arm_name → estimated causal effect."
    )
    arm_cis: dict[str, tuple[float, float]] = Field(
        description="Mapping arm_name → 95% CI on causal effect estimate."
    )
    n_rounds: int = Field(ge=1)
    arm_pull_counts: dict[str, int] = Field(
        description="Number of times each arm was selected during exploration."
    )
    cumulative_regret: float | None = Field(
        default=None,
        ge=0.0,
        description="Total regret accumulated over n_rounds (if true optimal known).",
    )
    exploration_strategy: str = "ucb1"
    metadata: dict[str, Any] = Field(default_factory=dict)


def persist_continuous_time_query(
    store: ArtifactStore,
    query: ContinuousTimeQuery,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _CONTINUOUS_TIME_QUERY_SCHEMA_NAME,
    schema_version: str = _CONTINUOUS_TIME_QUERY_SCHEMA_VERSION,
) -> ContinuousTimeQueryRef:
    """Persist continuous time query helper."""
    ref = put_json_artifact(
        store,
        query.model_dump(mode="json"),
        kind="ir.continuous_time_query",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ContinuousTimeQueryRef.model_validate(ref)


def load_continuous_time_query(
    store: ArtifactStore,
    ref: ContinuousTimeQueryRef,
) -> ContinuousTimeQuery:
    """Load continuous time query."""
    payload = get_json_artifact(store, ref.artifact_id)
    return ContinuousTimeQuery.model_validate(payload)


def persist_temporal_intervention_trajectory(
    store: ArtifactStore,
    trajectory: TemporalInterventionTrajectory,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _TEMPORAL_INTERVENTION_TRAJECTORY_SCHEMA_NAME,
    schema_version: str = _TEMPORAL_INTERVENTION_TRAJECTORY_SCHEMA_VERSION,
) -> TemporalInterventionTrajectoryRef:
    """Persist temporal intervention trajectory helper."""
    ref = put_json_artifact(
        store,
        trajectory.model_dump(mode="json"),
        kind="ir.temporal_intervention_trajectory",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return TemporalInterventionTrajectoryRef.model_validate(ref)


def load_temporal_intervention_trajectory(
    store: ArtifactStore,
    ref: TemporalInterventionTrajectoryRef,
) -> TemporalInterventionTrajectory:
    """Load temporal intervention trajectory."""
    payload = get_json_artifact(store, ref.artifact_id)
    return TemporalInterventionTrajectory.model_validate(payload)


def persist_dynamic_treatment_regime(
    store: ArtifactStore,
    regime: DynamicTreatmentRegime,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _DYNAMIC_TREATMENT_REGIME_SCHEMA_NAME,
    schema_version: str = _DYNAMIC_TREATMENT_REGIME_SCHEMA_VERSION,
) -> DynamicTreatmentRegimeRef:
    """Persist dynamic treatment regime helper."""
    ref = put_json_artifact(
        store,
        regime.model_dump(mode="json"),
        kind="ir.dynamic_treatment_regime",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return DynamicTreatmentRegimeRef.model_validate(ref)


def load_dynamic_treatment_regime(
    store: ArtifactStore,
    ref: DynamicTreatmentRegimeRef,
) -> DynamicTreatmentRegime:
    """Load dynamic treatment regime."""
    payload = get_json_artifact(store, ref.artifact_id)
    return DynamicTreatmentRegime.model_validate(payload)


def persist_effect_trajectory_bundle(
    store: ArtifactStore,
    bundle: EffectTrajectoryBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _EFFECT_TRAJECTORY_BUNDLE_SCHEMA_NAME,
    schema_version: str = _EFFECT_TRAJECTORY_BUNDLE_SCHEMA_VERSION,
) -> EffectTrajectoryBundleRef:
    """Persist effect trajectory bundle helper."""
    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind="ir.effect_trajectory_bundle",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return EffectTrajectoryBundleRef.model_validate(ref)


def load_effect_trajectory_bundle(
    store: ArtifactStore,
    ref: EffectTrajectoryBundleRef,
) -> EffectTrajectoryBundle:
    """Load effect trajectory bundle."""
    payload = get_json_artifact(store, ref.artifact_id)
    return EffectTrajectoryBundle.model_validate(payload)


__all__ = [
    "BanditResult",
    "ContinuousTimeQuery",
    "DTRResult",
    "DynamicTreatmentRegime",
    "EffectTrajectoryBundle",
    "GComputationResult",
    "InterventionInterpolationPolicy",
    "OPEResult",
    "RegimeRule",
    "RuntimeSupportStatus",
    "SNMMResult",
    "StrategicAdaptationMode",
    "TemporalInterventionTrajectory",
    "TemporalPathRepresentation",
    "TemporalQueryMode",
    "TemporalSamplingScheme",
    "TemporalTargetFunctional",
    "load_continuous_time_query",
    "load_dynamic_treatment_regime",
    "load_effect_trajectory_bundle",
    "load_temporal_intervention_trajectory",
    "persist_continuous_time_query",
    "persist_dynamic_treatment_regime",
    "persist_effect_trajectory_bundle",
    "persist_temporal_intervention_trajectory",
]
