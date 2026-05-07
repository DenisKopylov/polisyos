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

from polisyos.ir.analytics.rough_path_semantics import (
    PathLiftMethod,
    RoughPathIdentificationStatus,
    RoughPathInterventionCertificate,
    RoughPathTopology,
    TemporalPathSemanticsAttachment,
    TemporalPathSemanticsScope,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.references import (
    ArtifactRefModel,
    ContinuousTimeQueryRef,
    DynamicTreatmentRegimeRef,
    EffectTrajectoryBundleRef,
    TemporalIdentificationCertificateRef,
    TemporalInterventionTrajectoryRef,
)

_CONTINUOUS_TIME_QUERY_SCHEMA_NAME = "ir.continuous_time_query"
_CONTINUOUS_TIME_QUERY_SCHEMA_VERSION = "1.0"
_TEMPORAL_INTERVENTION_TRAJECTORY_SCHEMA_NAME = "ir.temporal_intervention_trajectory"
_TEMPORAL_INTERVENTION_TRAJECTORY_SCHEMA_VERSION = "1.0"
_TEMPORAL_IDENTIFICATION_CERTIFICATE_SCHEMA_NAME = "ir.temporal_identification_certificate"
_TEMPORAL_IDENTIFICATION_CERTIFICATE_SCHEMA_VERSION = "1.0"
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


def _coerce_python_bool(value: Any, *, field_name: str) -> bool:
    try:
        return bool(value)
    except Exception as exc:  # pragma: no cover - defensive normalization
        raise ValueError(f"{field_name} must be coercible to bool") from exc


def _coerce_string_tuple(value: Any, *, field_name: str) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if not isinstance(value, (tuple, list, set)):
        raise ValueError(f"{field_name} must be a tuple/list of non-empty strings")
    normalized = tuple(str(item).strip() for item in value if str(item).strip())
    if len(normalized) != len(tuple(value)):
        raise ValueError(f"{field_name} entries must be non-empty strings")
    return normalized


def _coerce_float_tuple(value: Any, *, field_name: str) -> tuple[float, ...]:
    if value in (None, ""):
        return ()
    if not isinstance(value, (tuple, list)):
        raise ValueError(f"{field_name} must be a tuple/list of finite floats")
    return tuple(_coerce_finite_float(item, field_name=field_name) for item in value)


class TemporalTargetFunctional(str, Enum):
    """Functionals over an intervention-induced effect path on a time horizon."""

    EFFECT_PATH = "effect_path"
    INTEGRAL_EFFECT = "integral_effect"
    TIME_TO_THRESHOLD = "time_to_threshold"
    OCCUPANCY_PROBABILITY = "occupancy_probability"
    CUMULATIVE_INCIDENCE = "cumulative_incidence"
    SURVIVAL_CURVE = "survival_curve"


class TemporalPathRepresentation(str, Enum):
    """Model family used to represent the trajectory-level causal object."""

    LINEAR_SDE = "linear_sde"
    ODE = "ode"
    DISCRETE_REPLAY = "discrete_replay"
    EVENT_PROCESS_WEIGHTING = "event_process_weighting"
    NEURAL_CDE = "neural_cde"
    NEURAL_SDE = "neural_sde"
    GEOMETRIC_ROUGH_PATH = "geometric_rough_path"
    CADLAG_ROUGH_PATH = "cadlag_rough_path"
    TRUNCATED_SIGNATURE = "truncated_signature"
    HYBRID_ROUGH_EVENT = "hybrid_rough_event"


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


class TemporalIdentificationTheoremFamily(str, Enum):
    """Theorem family used to identify a continuous-time causal object."""

    NSDE_FIXED_OBSERVED_CHANNEL_V1 = "nsde_fixed_observed_channel_v1"
    NCDE_FIXED_OBSERVED_CHANNEL_V1 = "ncde_fixed_observed_channel_v1"
    LOCAL_INDEPENDENCE_WEIGHTING_V1 = "local_independence_weighting_v1"


class TemporalInterventionSemantics(str, Enum):
    """Intervention semantics certified for one temporal theorem family."""

    SURGICAL_REPLACEMENT = "surgical_replacement"
    INTENSITY_REPLACEMENT = "intensity_replacement"


class TemporalObservabilityRegime(str, Enum):
    """Observability regime assumed by a temporal identification theorem."""

    FULL_STATE = "full_state"
    OBSERVED_FILTRATION = "observed_filtration"


class TemporalLawObject(str, Enum):
    """Law-invariant object used to transport observational to intervention semantics."""

    GENERATOR = "generator"
    SEMIMARTINGALE_CHARACTERISTICS = "semimartingale_characteristics"
    CANONICAL_CONTROL_PATH = "canonical_control_path"
    INTENSITY_COMPENSATOR = "intensity_compensator"


class TemporalIdentificationSupportStatus(str, Enum):
    """Support regime disclosed alongside a temporal identification certificate."""

    ON_SUPPORT = "on_support"
    MODEL_EXTRAPOLATION = "model_extrapolation"


class CausalTranslationCertificateStatus(str, Enum):
    """Semantic equivalence status for discrete-to-continuous temporal translation."""

    CERTIFIED_EXACT = "certified_exact"
    CERTIFIED_RESTRICTED = "certified_restricted"
    NOT_CERTIFIED = "not_certified"
    FAILED = "failed"


class CausalTranslationScope(BaseModel):
    """Restrict which functionals and variables the translation certificate covers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query_functionals_covered: tuple[str, ...]
    time_grid_covered: tuple[float, ...]
    variables_covered: tuple[str, ...]

    @field_validator("query_functionals_covered", "variables_covered", mode="before")
    @classmethod
    def _normalize_string_fields(cls, value: Any, info: Any) -> tuple[str, ...]:
        return _coerce_string_tuple(value, field_name=str(info.field_name))

    @field_validator("time_grid_covered", mode="before")
    @classmethod
    def _normalize_time_grid(cls, value: Any) -> tuple[float, ...]:
        grid = _coerce_float_tuple(value, field_name="time_grid_covered")
        if len(grid) < 2:
            raise ValueError("time_grid_covered must contain at least two time points")
        return grid


class CausalTranslationValueQuantization(BaseModel):
    """Describe any value-space quantization introduced by the abstraction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = False
    bin_edges: tuple[float, ...] | None = None

    @field_validator("bin_edges", mode="before")
    @classmethod
    def _normalize_bin_edges(cls, value: Any) -> tuple[float, ...] | None:
        if value in (None, ""):
            return None
        edges = _coerce_float_tuple(value, field_name="bin_edges")
        if len(edges) < 2:
            raise ValueError("bin_edges must contain at least two values when provided")
        return edges

    @model_validator(mode="after")
    def _validate_enabled_consistency(self) -> CausalTranslationValueQuantization:
        if not self.enabled and self.bin_edges is not None:
            raise ValueError("bin_edges require enabled=true")
        return self


class CausalTranslationTauMapping(BaseModel):
    """State-space abstraction map from continuous trajectories to certified observables."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["time_sampling"] = "time_sampling"
    sampling_times: tuple[float, ...]
    value_quantization: CausalTranslationValueQuantization = Field(
        default_factory=CausalTranslationValueQuantization
    )

    @field_validator("sampling_times", mode="before")
    @classmethod
    def _normalize_sampling_times(cls, value: Any) -> tuple[float, ...]:
        times = _coerce_float_tuple(value, field_name="sampling_times")
        if len(times) < 2:
            raise ValueError("sampling_times must contain at least two points")
        return times


class CausalTranslationOmegaMapping(BaseModel):
    """Intervention abstraction map paired with the tau state map."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["intervention_lift"] = "intervention_lift"
    interpolation_policy: InterventionInterpolationPolicy
    hold_semantics: Literal["zoh", "foh"]
    knot_times: tuple[float, ...]
    knot_values: tuple[float, ...]

    @field_validator("knot_times", "knot_values", mode="before")
    @classmethod
    def _normalize_knots(cls, value: Any, info: Any) -> tuple[float, ...]:
        knots = _coerce_float_tuple(value, field_name=str(info.field_name))
        if len(knots) < 2:
            raise ValueError(f"{info.field_name} must contain at least two points")
        return knots

    @model_validator(mode="after")
    def _validate_knot_alignment(self) -> CausalTranslationOmegaMapping:
        if len(self.knot_times) != len(self.knot_values):
            raise ValueError("knot_times and knot_values must have equal length")
        return self


class CausalTranslationSufficientConditions(BaseModel):
    """Machine-checkable sufficient conditions used for the translation verdict."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    time_scale_matches: bool
    interpolation_policy_matches_contract: bool
    grid_regular: bool
    horizon_aligned: bool
    backend_exact_discretization: bool
    allowed_interventions_restricted_to_omega_image: bool
    unique_solution_assumed: bool

    @field_validator(
        "time_scale_matches",
        "interpolation_policy_matches_contract",
        "grid_regular",
        "horizon_aligned",
        "backend_exact_discretization",
        "allowed_interventions_restricted_to_omega_image",
        "unique_solution_assumed",
        mode="before",
    )
    @classmethod
    def _normalize_bool_fields(cls, value: Any, info: Any) -> bool:
        return _coerce_python_bool(value, field_name=str(info.field_name))


class CausalTranslationCertificate(BaseModel):
    """Proof-carrying temporal diagnostic for causal translation under discretization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: str = "ir.causal_translation_certificate"
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    status: CausalTranslationCertificateStatus
    abstraction_family: Literal["exact_tau_transformation"] = "exact_tau_transformation"
    scope: CausalTranslationScope
    tau_mapping: CausalTranslationTauMapping
    omega_mapping: CausalTranslationOmegaMapping
    sufficient_conditions: CausalTranslationSufficientConditions
    assumptions_introduced: tuple[str, ...] = ()
    failure_reasons: tuple[str, ...] = ()
    evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("assumptions_introduced", "failure_reasons", mode="before")
    @classmethod
    def _normalize_string_lists(cls, value: Any, info: Any) -> tuple[str, ...]:
        return _coerce_string_tuple(value, field_name=str(info.field_name))

    @property
    def is_certified(self) -> bool:
        return self.status in {
            CausalTranslationCertificateStatus.CERTIFIED_EXACT,
            CausalTranslationCertificateStatus.CERTIFIED_RESTRICTED,
        }


def _preferred_backend(metadata: dict[str, Any]) -> str:
    return str(metadata.get("preferred_backend", "linear_sde")).strip().lower()


def _process_family(metadata: dict[str, Any]) -> str:
    return str(metadata.get("process_family", "")).strip().lower()


_ROUGH_PATH_REPRESENTATIONS = {
    TemporalPathRepresentation.GEOMETRIC_ROUGH_PATH,
    TemporalPathRepresentation.CADLAG_ROUGH_PATH,
    TemporalPathRepresentation.TRUNCATED_SIGNATURE,
    TemporalPathRepresentation.HYBRID_ROUGH_EVENT,
}

_ROUGH_PATH_BACKEND_NAMES = frozenset(
    {
        TemporalPathRepresentation.GEOMETRIC_ROUGH_PATH.value,
        TemporalPathRepresentation.CADLAG_ROUGH_PATH.value,
        TemporalPathRepresentation.TRUNCATED_SIGNATURE.value,
        TemporalPathRepresentation.HYBRID_ROUGH_EVENT.value,
    }
)


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
        result = tuple(
            _coerce_finite_float(item, field_name=str(info.field_name)) for item in value
        )
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
    def _validate_trajectory(self) -> TemporalInterventionTrajectory:
        if len(self.time_points) != len(self.values):
            raise ValueError("time_points and values must have equal length")
        for left, right in zip(self.time_points[:-1], self.time_points[1:], strict=False):
            if right <= left:
                raise ValueError("time_points must be strictly increasing")
        return self

    @property
    def is_binary_schedule(self) -> bool:
        return all(
            math.isclose(value, round(value), abs_tol=1e-8) and round(value) in {0, 1}
            for value in self.values
        )


class TemporalIdentificationCertificate(BaseModel):
    """Typed theorem-backed identification certificate for temporal bundles."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    theorem_family: TemporalIdentificationTheoremFamily
    identified_functionals: tuple[TemporalTargetFunctional, ...]
    intervention_semantics: TemporalInterventionSemantics = (
        TemporalInterventionSemantics.SURGICAL_REPLACEMENT
    )
    observability_regime: TemporalObservabilityRegime = TemporalObservabilityRegime.FULL_STATE
    law_object: TemporalLawObject
    law_invariant: bool = True
    assumptions: tuple[str, ...] = Field(default_factory=tuple)
    canonical_control_required: bool = False
    control_canonicalization: InterventionInterpolationPolicy | None = None
    support_status: TemporalIdentificationSupportStatus = (
        TemporalIdentificationSupportStatus.ON_SUPPORT
    )
    notes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("identified_functionals", "assumptions", mode="before")
    @classmethod
    def _coerce_string_collections(cls, value: Any, info: Any) -> Any:
        if info.field_name == "identified_functionals":
            if not isinstance(value, (tuple, list)):
                raise ValueError(
                    "identified_functionals must be a tuple/list of temporal functionals"
                )
            return tuple(value)
        return _coerce_string_tuple(value, field_name=str(info.field_name))

    @model_validator(mode="after")
    def _validate_theorem_scope(self) -> TemporalIdentificationCertificate:
        if not self.identified_functionals:
            raise ValueError("identified_functionals must contain at least one target functional")
        if not self.law_invariant:
            raise ValueError("temporal identification certificates must certify law_invariant=true")

        if (
            self.theorem_family
            is TemporalIdentificationTheoremFamily.NSDE_FIXED_OBSERVED_CHANNEL_V1
        ):
            if self.law_object not in {
                TemporalLawObject.GENERATOR,
                TemporalLawObject.SEMIMARTINGALE_CHARACTERISTICS,
            }:
                raise ValueError(
                    "nsde_fixed_observed_channel_v1 requires generator or semimartingale_characteristics"
                )
            if self.canonical_control_required:
                raise ValueError(
                    "neural SDE identification must not require canonical control paths"
                )
            if self.control_canonicalization is not None:
                raise ValueError(
                    "neural SDE identification must not declare control canonicalization"
                )
            return self

        if (
            self.theorem_family
            is TemporalIdentificationTheoremFamily.LOCAL_INDEPENDENCE_WEIGHTING_V1
        ):
            if (
                self.intervention_semantics
                is not TemporalInterventionSemantics.INTENSITY_REPLACEMENT
            ):
                raise ValueError(
                    "local_independence_weighting_v1 requires intervention_semantics=intensity_replacement"
                )
            if self.observability_regime is not TemporalObservabilityRegime.OBSERVED_FILTRATION:
                raise ValueError(
                    "local_independence_weighting_v1 requires observability_regime=observed_filtration"
                )
            if self.law_object is not TemporalLawObject.INTENSITY_COMPENSATOR:
                raise ValueError(
                    "local_independence_weighting_v1 requires law_object=intensity_compensator"
                )
            if self.canonical_control_required:
                raise ValueError(
                    "local_independence_weighting_v1 must not require canonical control paths"
                )
            if self.control_canonicalization is not None:
                raise ValueError(
                    "local_independence_weighting_v1 must not declare control canonicalization"
                )
            return self

        if self.law_object is not TemporalLawObject.CANONICAL_CONTROL_PATH:
            raise ValueError(
                "ncde_fixed_observed_channel_v1 requires law_object=canonical_control_path"
            )
        if not self.canonical_control_required:
            raise ValueError(
                "ncde_fixed_observed_channel_v1 requires canonical_control_required=true"
            )
        if self.control_canonicalization is None:
            raise ValueError(
                "ncde_fixed_observed_channel_v1 requires an explicit control_canonicalization"
            )
        return self


def _strategic_adaptation_mode(metadata: dict[str, Any]) -> str:
    raw = metadata.get("strategic_adaptation_mode", StrategicAdaptationMode.ABSENT.value)
    if isinstance(raw, StrategicAdaptationMode):
        return raw.value
    candidate = str(raw).strip().lower()
    return candidate or StrategicAdaptationMode.ABSENT.value


def _temporal_identification_certificate_from_metadata(
    metadata: dict[str, Any],
) -> TemporalIdentificationCertificate | None:
    payload = metadata.get("temporal_identification_certificate")
    if payload is None:
        return None
    if isinstance(payload, TemporalIdentificationCertificate):
        return payload
    try:
        return TemporalIdentificationCertificate.model_validate(payload)
    except Exception:
        return None


def _temporal_identification_scope_from_metadata(
    metadata: dict[str, Any],
) -> dict[str, Any] | None:
    payload = metadata.get("identification_scope")
    if isinstance(payload, dict):
        return dict(payload)
    return None


def _rough_path_attachment_from_metadata(
    metadata: dict[str, Any],
) -> TemporalPathSemanticsAttachment | None:
    payload = metadata.get("path_semantics")
    if payload is None:
        return None
    if isinstance(payload, TemporalPathSemanticsAttachment):
        return payload
    try:
        return TemporalPathSemanticsAttachment.model_validate(payload)
    except Exception:
        return None


def _rough_path_certificate_from_metadata(
    metadata: dict[str, Any],
) -> RoughPathInterventionCertificate | None:
    payload = metadata.get("rough_path_certificate")
    if payload is None:
        payload = metadata.get("rough_path_intervention_certificate")
    if payload is None:
        return None
    if isinstance(payload, RoughPathInterventionCertificate):
        return payload
    try:
        return RoughPathInterventionCertificate.model_validate(payload)
    except Exception:
        return None


def _rough_path_identification_status_from_metadata(
    metadata: dict[str, Any],
) -> RoughPathIdentificationStatus | None:
    raw = metadata.get("rough_path_identification_status")
    if isinstance(raw, RoughPathIdentificationStatus):
        return raw
    if raw is not None:
        try:
            return RoughPathIdentificationStatus(str(raw).strip())
        except Exception:
            return None
    certificate = _rough_path_certificate_from_metadata(metadata)
    if certificate is None:
        return None
    return certificate.status


def _rough_path_scope_errors(
    *,
    preferred_backend: str,
    attachment: TemporalPathSemanticsAttachment | None,
    certificate: RoughPathInterventionCertificate | None,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if attachment is None:
        blockers.append("research_gated_path_semantics_missing")
        return tuple(blockers)
    if certificate is None:
        blockers.append("research_gated_rough_path_certificate_missing")
        return tuple(blockers)
    if not attachment.interpolation_is_adapted or not certificate.interpolation_is_adapted:
        blockers.append("research_gated_interpolation_not_adapted")
    if not attachment.future_leakage_ruled_out or not certificate.future_leakage_ruled_out:
        blockers.append("research_gated_future_leakage")
    if (
        not attachment.sampling_ignorability_checked
        or certificate.sampling_ignorability_ref is None
    ):
        blockers.append("research_gated_sampling_ignorability_unchecked")
    if attachment.semantics_scope is TemporalPathSemanticsScope.LATENT_PATH:
        if not attachment.lift_faithfulness_checked or certificate.lift_faithfulness_ref is None:
            blockers.append("research_gated_lift_faithfulness_unchecked")
    if preferred_backend == TemporalPathRepresentation.TRUNCATED_SIGNATURE.value:
        if attachment.lift_method is not PathLiftMethod.LOGSIGNATURE:
            blockers.append("unsupported_path_semantics")
    if preferred_backend == TemporalPathRepresentation.CADLAG_ROUGH_PATH.value:
        if attachment.topology is not RoughPathTopology.SKOROKHOD:
            blockers.append("unsupported_path_semantics")
    if certificate.status is RoughPathIdentificationStatus.BLOCKED:
        blockers.append("blocked_rough_path_identification")
    return tuple(blockers)


def _coerce_temporal_target_functional(value: Any) -> TemporalTargetFunctional | None:
    if isinstance(value, TemporalTargetFunctional):
        return value
    try:
        return TemporalTargetFunctional(str(value).strip())
    except Exception:
        return None


def _coerce_temporal_query_mode(value: Any) -> TemporalQueryMode | None:
    if isinstance(value, TemporalQueryMode):
        return value
    try:
        return TemporalQueryMode(str(value).strip())
    except Exception:
        return None


def _coerce_sampling_scheme(value: Any) -> TemporalSamplingScheme | None:
    if isinstance(value, TemporalSamplingScheme):
        return value
    try:
        return TemporalSamplingScheme(str(value).strip())
    except Exception:
        return None


def _coerce_interpolation_policy(value: Any) -> InterventionInterpolationPolicy | None:
    if isinstance(value, InterventionInterpolationPolicy):
        return value
    try:
        return InterventionInterpolationPolicy(str(value).strip())
    except Exception:
        return None


def _coerce_intervention_semantics(value: Any) -> TemporalInterventionSemantics | None:
    if isinstance(value, TemporalInterventionSemantics):
        return value
    try:
        return TemporalInterventionSemantics(str(value).strip())
    except Exception:
        return None


def _coerce_observability_regime(value: Any) -> TemporalObservabilityRegime | None:
    if isinstance(value, TemporalObservabilityRegime):
        return value
    try:
        return TemporalObservabilityRegime(str(value).strip())
    except Exception:
        return None


def _coerce_law_object(value: Any) -> TemporalLawObject | None:
    if isinstance(value, TemporalLawObject):
        return value
    try:
        return TemporalLawObject(str(value).strip())
    except Exception:
        return None


def _coerce_theorem_family(value: Any) -> TemporalIdentificationTheoremFamily | None:
    if isinstance(value, TemporalIdentificationTheoremFamily):
        return value
    try:
        return TemporalIdentificationTheoremFamily(str(value).strip())
    except Exception:
        return None


def _neural_identification_scope_errors(
    *,
    preferred_backend: str,
    theorem_family: Any,
    identified_functionals: tuple[Any, ...],
    intervention_semantics: Any,
    observability_regime: Any,
    law_invariant: bool,
    law_object: Any,
    canonical_control_required: bool,
    control_canonicalization: Any,
    query_mode: Any,
    sampling_scheme: Any,
    target_functional: Any,
    interpolation_policy: Any,
    strategic_adaptation_mode: Any,
) -> tuple[str, ...]:
    blockers: list[str] = []
    normalized_backend = str(preferred_backend).strip().lower()
    normalized_theorem_family = _coerce_theorem_family(theorem_family)
    normalized_functionals = {
        functional
        for functional in (
            _coerce_temporal_target_functional(item) for item in identified_functionals
        )
        if functional is not None
    }
    normalized_target = _coerce_temporal_target_functional(target_functional)
    normalized_query_mode = _coerce_temporal_query_mode(query_mode)
    normalized_sampling_scheme = _coerce_sampling_scheme(sampling_scheme)
    normalized_interpolation_policy = _coerce_interpolation_policy(interpolation_policy)
    normalized_intervention_semantics = _coerce_intervention_semantics(intervention_semantics)
    normalized_observability_regime = _coerce_observability_regime(observability_regime)
    normalized_law_object = _coerce_law_object(law_object)
    strategic_mode = str(strategic_adaptation_mode).strip().lower()

    if normalized_query_mode is not TemporalQueryMode.FIXED_INTERVENTION:
        blockers.append("query_mode")
    if normalized_sampling_scheme is not TemporalSamplingScheme.REGULAR_GRID:
        blockers.append("sampling_scheme")
    if normalized_target not in {
        TemporalTargetFunctional.EFFECT_PATH,
        TemporalTargetFunctional.INTEGRAL_EFFECT,
    }:
        blockers.append("target_functional")
    elif normalized_target not in normalized_functionals:
        blockers.append("identified_functionals")
    if normalized_intervention_semantics is not TemporalInterventionSemantics.SURGICAL_REPLACEMENT:
        blockers.append("intervention_semantics")
    if normalized_observability_regime is not TemporalObservabilityRegime.FULL_STATE:
        blockers.append("observability_regime")
    if not bool(law_invariant):
        blockers.append("law_invariant")
    if strategic_mode not in {"", StrategicAdaptationMode.ABSENT.value}:
        blockers.append("strategic_adaptation_mode")

    if normalized_backend == "neural_sde":
        if (
            normalized_theorem_family
            is not TemporalIdentificationTheoremFamily.NSDE_FIXED_OBSERVED_CHANNEL_V1
        ):
            blockers.append("theorem_family")
        if normalized_law_object not in {
            TemporalLawObject.GENERATOR,
            TemporalLawObject.SEMIMARTINGALE_CHARACTERISTICS,
        }:
            blockers.append("law_object")
        if bool(canonical_control_required):
            blockers.append("canonical_control_required")
        if control_canonicalization is not None:
            blockers.append("control_canonicalization")
        return tuple(blockers)

    if (
        normalized_theorem_family
        is not TemporalIdentificationTheoremFamily.NCDE_FIXED_OBSERVED_CHANNEL_V1
    ):
        blockers.append("theorem_family")
    if normalized_law_object is not TemporalLawObject.CANONICAL_CONTROL_PATH:
        blockers.append("law_object")
    if not bool(canonical_control_required):
        blockers.append("canonical_control_required")
    if normalized_interpolation_policy not in {
        InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        InterventionInterpolationPolicy.LINEAR,
    }:
        blockers.append("interpolation_policy")
    elif (
        _coerce_interpolation_policy(control_canonicalization)
        is not normalized_interpolation_policy
    ):
        blockers.append("control_canonicalization")
    return tuple(blockers)


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
    def _validate_time_contract(self) -> ContinuousTimeQuery:
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
        preferred_backend = _preferred_backend(self.metadata)
        process_family = _process_family(self.metadata)
        if preferred_backend == "event_process_weighting":
            if self.query_mode is not TemporalQueryMode.FIXED_INTERVENTION:
                blockers.append("unsupported_query_mode")
            if self.target_functional not in {
                TemporalTargetFunctional.CUMULATIVE_INCIDENCE,
                TemporalTargetFunctional.SURVIVAL_CURVE,
            }:
                blockers.append("unsupported_target_functional")
            if process_family and process_family not in {
                "counting_process",
                "marked_point_process",
                "event_log",
            }:
                blockers.append("unsupported_process_family")
            return tuple(blockers)
        if preferred_backend in _ROUGH_PATH_BACKEND_NAMES:
            blockers.extend(
                _rough_path_scope_errors(
                    preferred_backend=preferred_backend,
                    attachment=_rough_path_attachment_from_metadata(self.metadata),
                    certificate=_rough_path_certificate_from_metadata(self.metadata),
                )
            )
        elif self.sampling_scheme is TemporalSamplingScheme.IRREGULAR_GRID:
            blockers.append("research_gated_sampling_scheme")
        if self.target_functional not in {
            TemporalTargetFunctional.EFFECT_PATH,
            TemporalTargetFunctional.INTEGRAL_EFFECT,
        }:
            blockers.append("unsupported_target_functional")
        if preferred_backend in {"neural_cde", "neural_sde"}:
            certificate = _temporal_identification_certificate_from_metadata(self.metadata)
            if certificate is None:
                blockers.append("research_gated_backend")
            else:
                scope_errors = _neural_identification_scope_errors(
                    preferred_backend=preferred_backend,
                    theorem_family=certificate.theorem_family,
                    identified_functionals=certificate.identified_functionals,
                    intervention_semantics=certificate.intervention_semantics,
                    observability_regime=certificate.observability_regime,
                    law_invariant=certificate.law_invariant,
                    law_object=certificate.law_object,
                    canonical_control_required=certificate.canonical_control_required,
                    control_canonicalization=certificate.control_canonicalization,
                    query_mode=self.query_mode,
                    sampling_scheme=self.sampling_scheme,
                    target_functional=self.target_functional,
                    interpolation_policy=self.interpolation_policy,
                    strategic_adaptation_mode=_strategic_adaptation_mode(self.metadata),
                )
                if scope_errors:
                    blockers.append("unsupported_identification_scope")
            blockers.append("unsupported_backend_target")
        elif preferred_backend not in {"linear_sde", "ode"} | _ROUGH_PATH_BACKEND_NAMES:
            blockers.append("unsupported_backend_target")
        return tuple(blockers)

    @property
    def runtime_support_status(self) -> RuntimeSupportStatus:
        if not self.runtime_blockers:
            if _preferred_backend(self.metadata) in _ROUGH_PATH_BACKEND_NAMES:
                status = _rough_path_identification_status_from_metadata(self.metadata)
                if status in {
                    RoughPathIdentificationStatus.IDENTIFIED_REPRESENTATION_ONLY,
                    RoughPathIdentificationStatus.PARTIALLY_IDENTIFIED,
                }:
                    return RuntimeSupportStatus.DEGRADED
            return RuntimeSupportStatus.SUPPORTED
        if any(reason.startswith("research_gated_") for reason in self.runtime_blockers):
            return RuntimeSupportStatus.BLOCKED_RESEARCH
        return RuntimeSupportStatus.BLOCKED_UNSUPPORTED

    @property
    def runtime_eligible(self) -> bool:
        """True when current engineering scope can execute the query."""

        return self.runtime_support_status in {
            RuntimeSupportStatus.SUPPORTED,
            RuntimeSupportStatus.DEGRADED,
        }


class EffectTrajectoryBundle(BaseModel):
    """Canonical public contract for temporal effect trajectories and diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    query_ref: ContinuousTimeQueryRef
    trajectory_ref: ArtifactRefModel
    confidence_band_ref: ArtifactRefModel
    solver_diagnostics_ref: ArtifactRefModel
    identification_certificate_ref: TemporalIdentificationCertificateRef | None = None
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
    def _validate_bundle_refs(self) -> EffectTrajectoryBundle:
        _validate_non_empty_ref(self.trajectory_ref, field_name="trajectory_ref")
        _validate_non_empty_ref(self.confidence_band_ref, field_name="confidence_band_ref")
        _validate_non_empty_ref(
            self.solver_diagnostics_ref,
            field_name="solver_diagnostics_ref",
        )
        if self.identification_certificate_ref is not None:
            _validate_non_empty_ref(
                self.identification_certificate_ref,
                field_name="identification_certificate_ref",
            )
        if self.path_representation is TemporalPathRepresentation.DISCRETE_REPLAY:
            if self.discretization_error is not None:
                raise ValueError(
                    "discrete fallback bundles must not claim a numeric discretization_error"
                )
            if self.discretization_note is None:
                raise ValueError(
                    "discrete fallback bundles must disclose why discretization_error is unavailable"
                )
            if not self.continuous_time_degraded:
                raise ValueError("discrete fallback bundles must set continuous_time_degraded=true")
        elif self.discretization_error is None and self.discretization_note is None:
            raise ValueError("bundles must publish discretization_error or a discretization_note")
        has_path_semantics = "path_semantics" in self.metadata
        if has_path_semantics and self.metadata["path_semantics"] is None:
            raise ValueError("metadata.path_semantics must not be null")
        if has_path_semantics and self.path_representation not in _ROUGH_PATH_REPRESENTATIONS:
            raise ValueError(
                "metadata.path_semantics is reserved for rough/signature path representations"
            )
        if has_path_semantics:
            attachment = self.path_semantics_attachment
            if attachment is None:
                raise ValueError("metadata.path_semantics must be a valid attachment payload")
            if self.path_representation is TemporalPathRepresentation.TRUNCATED_SIGNATURE:
                if attachment.lift_method is not PathLiftMethod.LOGSIGNATURE:
                    raise ValueError(
                        "truncated_signature bundles must declare lift_method=logsignature"
                    )
                if attachment.signature_level is None:
                    raise ValueError("truncated_signature bundles must declare signature_level")
        return self

    @property
    def is_research_gated(self) -> bool:
        """True when the represented path family is outside current runtime scope."""

        neural_research_blockers = {
            "missing_identification_certificate",
            "unsupported_identification_scope",
        }
        return any(
            reason.startswith("research_gated_") or reason in neural_research_blockers
            for reason in self.runtime_blockers
        )

    @property
    def path_semantics_attachment(self) -> TemporalPathSemanticsAttachment | None:
        """Return the validated rough/signature semantics attachment when present."""

        candidate = self.metadata.get("path_semantics")
        if candidate is None:
            return None
        if isinstance(candidate, TemporalPathSemanticsAttachment):
            return candidate
        return TemporalPathSemanticsAttachment.model_validate(candidate)

    @property
    def path_semantics_scope(self) -> TemporalPathSemanticsScope | None:
        """Return the declared claim scope for rough/signature path semantics."""

        attachment = self.path_semantics_attachment
        if attachment is None:
            return None
        return attachment.semantics_scope

    @property
    def path_semantics_disclosure_notes(self) -> tuple[str, ...]:
        """Disclose whether the bundle certifies latent or representation-level claims."""

        scope = self.path_semantics_scope
        if scope is None:
            return ()
        if scope is TemporalPathSemanticsScope.REPRESENTED_PATH:
            return ("claim_scope_limited_to_represented_path",)
        if scope is TemporalPathSemanticsScope.SIGNATURE_EQUIVALENCE_CLASS:
            return ("claim_scope_limited_to_signature_equivalence_class",)
        return ("claim_scope_covers_latent_path",)

    @property
    def identification_scope(self) -> dict[str, Any] | None:
        """Return the serialized identification-scope disclosure when present."""

        return _temporal_identification_scope_from_metadata(self.metadata)

    @property
    def runtime_eligible(self) -> bool:
        """True when current engineering scope can consume the bundle at runtime."""

        return self.runtime_support_status in {
            RuntimeSupportStatus.SUPPORTED,
            RuntimeSupportStatus.DEGRADED,
        }

    @property
    def runtime_blockers(self) -> tuple[str, ...]:
        blockers: list[str] = []
        if self.path_representation in {
            TemporalPathRepresentation.NEURAL_CDE,
            TemporalPathRepresentation.NEURAL_SDE,
        }:
            if self.identification_certificate_ref is None:
                blockers.append("missing_identification_certificate")
            else:
                scope_is_supported = False
                scope = self.identification_scope
                if scope is None:
                    scope_is_supported = False
                else:
                    preferred_backend = (
                        "neural_cde"
                        if self.path_representation is TemporalPathRepresentation.NEURAL_CDE
                        else "neural_sde"
                    )
                    scope_errors = _neural_identification_scope_errors(
                        preferred_backend=preferred_backend,
                        theorem_family=scope.get("theorem_family"),
                        identified_functionals=tuple(scope.get("identified_functionals", ()) or ()),
                        intervention_semantics=scope.get("intervention_semantics"),
                        observability_regime=scope.get("observability_regime"),
                        law_invariant=bool(scope.get("law_invariant", True)),
                        law_object=scope.get("law_object"),
                        canonical_control_required=bool(
                            scope.get("canonical_control_required", False)
                        ),
                        control_canonicalization=scope.get("control_canonicalization"),
                        query_mode=scope.get("query_mode"),
                        sampling_scheme=scope.get("sampling_scheme"),
                        target_functional=scope.get("target_functional"),
                        interpolation_policy=self.interpolation_policy,
                        strategic_adaptation_mode=scope.get(
                            "strategic_adaptation_mode",
                            self.strategic_adaptation_mode.value,
                        ),
                    )
                    scope_is_supported = not scope_errors
                if (
                    not scope_is_supported
                    or self.strategic_adaptation_mode is not StrategicAdaptationMode.ABSENT
                ):
                    blockers.append("unsupported_identification_scope")
        elif self.path_representation in _ROUGH_PATH_REPRESENTATIONS:
            attachment = self.path_semantics_attachment
            if attachment is None:
                blockers.append("research_gated_path_semantics_missing")
            else:
                if not attachment.interpolation_is_adapted:
                    blockers.append("research_gated_interpolation_not_adapted")
                if not attachment.future_leakage_ruled_out:
                    blockers.append("research_gated_future_leakage")
                if not attachment.sampling_ignorability_checked:
                    blockers.append("research_gated_sampling_ignorability_unchecked")
                if (
                    attachment.semantics_scope is TemporalPathSemanticsScope.LATENT_PATH
                    and not attachment.lift_faithfulness_checked
                ):
                    blockers.append("research_gated_lift_faithfulness_unchecked")
            if (
                _rough_path_identification_status_from_metadata(self.metadata)
                is RoughPathIdentificationStatus.BLOCKED
            ):
                blockers.append("blocked_rough_path_identification")
        return tuple(blockers)

    @property
    def runtime_support_status(self) -> RuntimeSupportStatus:
        if self.is_research_gated:
            return RuntimeSupportStatus.BLOCKED_RESEARCH
        if self.path_representation is TemporalPathRepresentation.DISCRETE_REPLAY:
            return RuntimeSupportStatus.DEGRADED
        if (
            self.path_representation in _ROUGH_PATH_REPRESENTATIONS
            and _rough_path_identification_status_from_metadata(self.metadata)
            in {
                RoughPathIdentificationStatus.IDENTIFIED_REPRESENTATION_ONLY,
                RoughPathIdentificationStatus.PARTIALLY_IDENTIFIED,
            }
        ):
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

    time_points: tuple[int, ...] = Field(description="Sorted sequence of time indices (0-based).")
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
    def _validate_scheduled_actions(self) -> DynamicTreatmentRegime:
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
    value_estimate: float = Field(description="E[Y^{d*}]: expected outcome under optimal regime.")
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
    policy_value: float = Field(description="Estimated value V̂^π of the target policy.")
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


def persist_temporal_identification_certificate(
    store: ArtifactStore,
    certificate: TemporalIdentificationCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _TEMPORAL_IDENTIFICATION_CERTIFICATE_SCHEMA_NAME,
    schema_version: str = _TEMPORAL_IDENTIFICATION_CERTIFICATE_SCHEMA_VERSION,
) -> TemporalIdentificationCertificateRef:
    """Persist temporal identification certificate helper."""
    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.temporal_identification_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return TemporalIdentificationCertificateRef.model_validate(ref)


def load_temporal_identification_certificate(
    store: ArtifactStore,
    ref: TemporalIdentificationCertificateRef,
) -> TemporalIdentificationCertificate:
    """Load temporal identification certificate."""
    payload = get_json_artifact(store, ref.artifact_id)
    return TemporalIdentificationCertificate.model_validate(payload)


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
    "CausalTranslationCertificate",
    "CausalTranslationCertificateStatus",
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
    "TemporalIdentificationCertificate",
    "TemporalIdentificationSupportStatus",
    "TemporalIdentificationTheoremFamily",
    "TemporalInterventionSemantics",
    "TemporalInterventionTrajectory",
    "TemporalLawObject",
    "TemporalObservabilityRegime",
    "TemporalPathRepresentation",
    "TemporalQueryMode",
    "TemporalSamplingScheme",
    "TemporalTargetFunctional",
    "load_continuous_time_query",
    "load_dynamic_treatment_regime",
    "load_effect_trajectory_bundle",
    "load_temporal_identification_certificate",
    "load_temporal_intervention_trajectory",
    "persist_continuous_time_query",
    "persist_dynamic_treatment_regime",
    "persist_effect_trajectory_bundle",
    "persist_temporal_identification_certificate",
    "persist_temporal_intervention_trajectory",
]
