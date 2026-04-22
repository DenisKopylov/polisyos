"""Define cohort-level distribution shifts, coupling diagnostics, and report refs."""
from __future__ import annotations

import math
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import (
    ArtifactRefModel,
    CausalAssumptionCardRef,
    DistributionalBoundsBundleRef,
    DistributionalDualCertificateRef,
    DistributionalEffectBundleRef,
    OrdinalPovertyReportRef,
    DistributionalProofArtifactRef,
    DistributionalReportRef,
    EstimandASTRef,
    ProofBundleRef,
)

_DISTRIBUTIONAL_REPORT_SCHEMA_NAME = "ir.distributional_report"
_DISTRIBUTIONAL_REPORT_SCHEMA_VERSION = "1.0"
_DISTRIBUTIONAL_EFFECT_BUNDLE_SCHEMA_NAME = "ir.distributional_effect_bundle"
_DISTRIBUTIONAL_EFFECT_BUNDLE_SCHEMA_VERSION = "1.0"
_ORDINAL_POVERTY_REPORT_SCHEMA_NAME = "ir.ordinal_poverty_report"
_ORDINAL_POVERTY_REPORT_SCHEMA_VERSION = "1.0"
_DISTRIBUTIONAL_BOUNDS_BUNDLE_SCHEMA_NAME = "ir.distributional_bounds_bundle"
_DISTRIBUTIONAL_BOUNDS_BUNDLE_SCHEMA_VERSION = "1.0"
_DISTRIBUTIONAL_DUAL_CERTIFICATE_SCHEMA_NAME = "ir.distributional_dual_certificate"
_DISTRIBUTIONAL_DUAL_CERTIFICATE_SCHEMA_VERSION = "1.0"
_DISTRIBUTIONAL_PROOF_ARTIFACT_SCHEMA_NAME = "ir.distributional_proof_artifact"
_DISTRIBUTIONAL_PROOF_ARTIFACT_SCHEMA_VERSION = "1.0"
_CAUSAL_ASSUMPTION_CARD_SCHEMA_NAME = "ir.causal_assumption_card"
_CAUSAL_ASSUMPTION_CARD_SCHEMA_VERSION = "1.0"
_DISCRETE_DISTRIBUTION_SUMMARY_SCHEMA_NAME = "ir.discrete_distribution_summary"
_DISCRETE_DISTRIBUTION_SUMMARY_SCHEMA_VERSION = "1.0"
_OT_COUPLING_SUMMARY_SCHEMA_NAME = "ir.ot_coupling_summary"
_OT_COUPLING_SUMMARY_SCHEMA_VERSION = "1.0"
_QUANTILE_SHIFT_SUMMARY_SCHEMA_NAME = "ir.quantile_shift_summary"
_QUANTILE_SHIFT_SUMMARY_SCHEMA_VERSION = "1.0"
_TAIL_RISK_DELTA_SUMMARY_SCHEMA_NAME = "ir.tail_risk_delta_summary"
_TAIL_RISK_DELTA_SUMMARY_SCHEMA_VERSION = "1.0"
_SUBGROUP_DISTRIBUTION_COMPARISON_SCHEMA_NAME = "ir.subgroup_distribution_comparison"
_SUBGROUP_DISTRIBUTION_COMPARISON_SCHEMA_VERSION = "1.0"


def _justification_rank(justification: "DistributionalJustification") -> int:
    order = {
        DistributionalJustification.SCENARIO: 0,
        DistributionalJustification.BOUNDED: 1,
        DistributionalJustification.IDENTIFIED: 2,
    }
    return order[justification]


def _weakest_justification(
    *justifications: "DistributionalJustification | None",
) -> "DistributionalJustification":
    present = [justification for justification in justifications if justification is not None]
    if not present:
        return DistributionalJustification.SCENARIO
    return min(present, key=_justification_rank)


def _ensure_finite(value: float | None, *, field_name: str) -> float | None:
    if value is None:
        return None
    casted = float(value)
    if not math.isfinite(casted):
        raise ValueError(f"{field_name} must be finite")
    return casted


def _ensure_non_empty(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate:
        raise ValueError(f"{field_name} must be non-empty")
    return candidate


def _validate_unique_artifact_refs(
    refs: list[ArtifactRefModel],
    *,
    field_name: str,
) -> None:
    seen: set[str] = set()
    for ref in refs:
        artifact_id = str(ref.artifact_id)
        if artifact_id in seen:
            raise ValueError(f"{field_name} contains duplicate artifact_id {artifact_id}")
        seen.add(artifact_id)


def _validate_ref_kind(
    ref: ArtifactRefModel | None,
    *,
    field_name: str,
    allowed_kinds: set[str],
) -> None:
    if ref is None:
        return
    if ref.kind not in allowed_kinds:
        expected = ", ".join(sorted(allowed_kinds))
        raise ValueError(f"{field_name} must reference one of [{expected}], got {ref.kind}")


def _validate_ref_list_kind(
    refs: list[ArtifactRefModel],
    *,
    field_name: str,
    allowed_kind: str,
) -> None:
    for ref in refs:
        if ref.kind != allowed_kind:
            raise ValueError(f"{field_name} entries must reference {allowed_kind}, got {ref.kind}")


def _persist_distributional_leaf(
    store: ArtifactStore,
    payload: BaseModel,
    *,
    kind: str,
    schema_name: str,
    schema_version: str,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    ref = put_json_artifact(
        store,
        payload.model_dump(mode="json"),
        kind=kind,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ArtifactRefModel.model_validate(ref)


def _load_distributional_leaf(store: ArtifactStore, ref: ArtifactRefModel, model: type[BaseModel]) -> Any:
    payload = get_json_artifact(store, ref.artifact_id)
    return model.model_validate(payload)


class DistributionalJustification(str, Enum):
    """Declare whether a distributional claim is identified, bounded, or scenario-based."""
    IDENTIFIED = "identified"
    BOUNDED = "bounded"
    SCENARIO = "scenario"


class DistributionalFunctional(str, Enum):
    """Declare which distributional functional is being bounded."""

    TAIL_PROB = "tail_probability"
    CDF = "cdf"
    QUANTILE = "quantile"
    QUANTILE_SHIFT = "quantile_shift"
    TAIL_DELTA = "tail_probability_change"
    ITE_CDF = "ite_cdf"
    ITE_TAIL_RISK = "ite_tail_risk"
    GINI = "gini"
    THEIL_T = "theil_t"
    ATKINSON = "atkinson"
    POVERTY_HEADCOUNT = "poverty_headcount"


class DistributionalProofTarget(str, Enum):
    """Declare which distribution-valued object the proof artifact certifies."""

    CDF = "cdf"
    SURVIVAL = "survival"
    LORENZ = "lorenz"
    QUANTILE = "quantile"
    TAIL_PROB = "tail_prob"
    EXPECTED_SHORTFALL = "expected_shortfall"
    MARGINAL_PAIR = "marginal_pair"
    COUPLING = "coupling"


class DistributionalBoundUniformity(str, Enum):
    """Describe whether bounds are identified, uniform, pointwise, or not applicable."""

    IDENTIFIED = "identified"
    UNIFORM_SHARP = "uniform_sharp"
    UNIFORM_OUTER = "uniform_outer"
    POINTWISE_ONLY = "pointwise_only"
    NOT_APPLICABLE = "not_applicable"


class DistributionalCouplingStatus(str, Enum):
    """Describe whether coupling-level claims are identified, set-identified, or scenario-only."""

    NOT_USED = "not_used"
    IDENTIFIED = "identified"
    SET_IDENTIFIED = "set_identified"
    SCENARIO_ONLY = "scenario_only"


class CohortDimension(str, Enum):
    """Select the cohort axis used when slicing winners/losers summaries."""

    INCOME_QUINTILE = "income_quintile"
    INCOME_DECILE = "income_decile"
    GEOGRAPHY = "geography"
    AGE_GROUP = "age_group"
    GENDER = "gender"
    ETHNICITY = "ethnicity"
    EDUCATION = "education"
    EMPLOYMENT_STATUS = "employment_status"
    CUSTOM = "custom"


class ImpactDirection(str, Enum):
    """Coarse direction of a cohort or KPI impact."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class MetricUnit(str, Enum):
    """Declare how distributional magnitudes should be rendered downstream."""

    PERCENT = "percent"
    RATIO = "ratio"
    ABSOLUTE = "absolute"


class CouplingDiagnostics(BaseModel):
    """Summarize optimal-transport coupling quality and identifiability assumptions."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    mass_conservation_error: float = Field(ge=0.0)
    source_marginal_l1_error: float = Field(default=0.0, ge=0.0)
    target_marginal_l1_error: float = Field(default=0.0, ge=0.0)
    support_mismatch_note: str | None = None
    regularization_strength: float | None = Field(default=None, gt=0.0)
    sinkhorn_iterations: int | None = Field(default=None, ge=0, le=200)
    convergence_delta: float | None = Field(default=None, ge=0.0)
    weighting_mode: str = Field(default="uniform", min_length=1)
    identifiability_assumptions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_finite_numbers(self) -> "CouplingDiagnostics":
        for field_name in (
            "mass_conservation_error",
            "source_marginal_l1_error",
            "target_marginal_l1_error",
            "regularization_strength",
            "convergence_delta",
        ):
            _ensure_finite(getattr(self, field_name), field_name=field_name)
        _ensure_non_empty(self.support_mismatch_note, field_name="support_mismatch_note")
        _ensure_non_empty(self.weighting_mode, field_name="weighting_mode")
        return self


class CausalAssumptionCard(BaseModel):
    """Typed assumption card attached to distributional proof artifacts and bundles."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    scope: str = Field(pattern=r"^(marginal|coupling|bound|estimation)$")
    status: str = Field(pattern=r"^(identified_needed|bound_needed|scenario_only)$")
    theorem_family: str = Field(min_length=1)
    assumption_type: str = Field(min_length=1)
    description: str = Field(min_length=1)
    testable: bool
    evidence_ref: ArtifactRefModel | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_card(self) -> "CausalAssumptionCard":
        _ensure_non_empty(self.theorem_family, field_name="theorem_family")
        _ensure_non_empty(self.assumption_type, field_name="assumption_type")
        _ensure_non_empty(self.description, field_name="description")
        return self


class DistributionalSupportDomain(BaseModel):
    """Declare the support over which a distributional theorem family is certified."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lower: float | None = None
    upper: float | None = None
    unit: str | None = None

    @model_validator(mode="after")
    def _validate_domain(self) -> "DistributionalSupportDomain":
        lower = _ensure_finite(self.lower, field_name="lower")
        upper = _ensure_finite(self.upper, field_name="upper")
        _ensure_non_empty(self.unit, field_name="unit")
        if lower is not None and upper is not None and lower > upper:
            raise ValueError("support_domain.lower must be <= support_domain.upper")
        return self


class DistributionalDualBoundWitness(BaseModel):
    """Store primal/dual objective traces for one side of a distributional bound."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bound_direction: str = Field(pattern=r"^(lower|upper)$")
    primal_objective_values: tuple[float, ...] = Field(min_length=1)
    dual_objective_values: tuple[float, ...] = Field(min_length=1)
    dual_gaps: tuple[float, ...] = Field(min_length=1)
    constraint_multipliers_ref: ArtifactRefModel | None = None
    witness_functions_ref: ArtifactRefModel | None = None
    truncation_error_bound: float | None = Field(default=None, ge=0.0)
    approximation_error_bound: float | None = Field(default=None, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_witness(self) -> "DistributionalDualBoundWitness":
        lengths = {
            len(self.primal_objective_values),
            len(self.dual_objective_values),
            len(self.dual_gaps),
        }
        if len(lengths) != 1:
            raise ValueError("distributional dual witness vectors must have equal length")
        for field_name in (
            "primal_objective_values",
            "dual_objective_values",
            "dual_gaps",
        ):
            for value in getattr(self, field_name):
                finite_value = _ensure_finite(value, field_name=field_name)
                if field_name == "dual_gaps" and finite_value is not None and finite_value < 0.0:
                    raise ValueError("dual_gaps must be non-negative")
        _ensure_finite(self.truncation_error_bound, field_name="truncation_error_bound")
        _ensure_finite(self.approximation_error_bound, field_name="approximation_error_bound")
        return self


class DistributionalDualCertificate(BaseModel):
    """Machine-checkable certificate for one distributional theorem family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    theorem_family: str = Field(min_length=1)
    functional: DistributionalFunctional
    axis: GridAxis
    assumption_class: str = Field(min_length=1)
    primal_problem_class: str = Field(min_length=1)
    dual_problem_class: str = Field(min_length=1)
    sharpness_status: str = Field(
        default="unknown",
        pattern=r"^(sharp|inner_approx|outer_approx|unknown)$",
    )
    bound_uniformity: DistributionalBoundUniformity = DistributionalBoundUniformity.NOT_APPLICABLE
    attainment_status: str = Field(
        default="unknown",
        pattern=r"^(attained|approximated|limit|unknown)$",
    )
    support_domain: DistributionalSupportDomain | None = None
    normalization: dict[str, Any] = Field(default_factory=dict)
    lower_bound_witness: DistributionalDualBoundWitness
    upper_bound_witness: DistributionalDualBoundWitness
    pointwise_not_uniform_warning: bool = False
    assumptions_used: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_certificate(self) -> "DistributionalDualCertificate":
        _ensure_non_empty(self.theorem_family, field_name="theorem_family")
        _ensure_non_empty(self.assumption_class, field_name="assumption_class")
        _ensure_non_empty(self.primal_problem_class, field_name="primal_problem_class")
        _ensure_non_empty(self.dual_problem_class, field_name="dual_problem_class")
        if self.lower_bound_witness.bound_direction != "lower":
            raise ValueError("lower_bound_witness must have bound_direction='lower'")
        if self.upper_bound_witness.bound_direction != "upper":
            raise ValueError("upper_bound_witness must have bound_direction='upper'")
        axis_length = len(self.axis.values)
        for witness_name in ("lower_bound_witness", "upper_bound_witness"):
            witness = getattr(self, witness_name)
            if len(witness.primal_objective_values) != axis_length:
                raise ValueError(
                    f"{witness_name} objective vectors must match certificate axis length"
                )
        if self.pointwise_not_uniform_warning and (
            self.bound_uniformity is not DistributionalBoundUniformity.POINTWISE_ONLY
        ):
            raise ValueError(
                "pointwise_not_uniform_warning requires bound_uniformity='pointwise_only'"
            )
        if self.sharpness_status == "sharp":
            max_gap = max(
                max(self.lower_bound_witness.dual_gaps),
                max(self.upper_bound_witness.dual_gaps),
            )
            if max_gap > 1e-8:
                raise ValueError("sharp certificates require numerically zero dual gaps")
        return self


class DistributionalFunctionalParameters(BaseModel):
    """Typed parameters needed by specific distributional functionals."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    poverty_line: float | None = None
    poverty_lines: tuple[float, ...] = ()
    atkinson_epsilon: float | None = Field(default=None, ge=0.0)
    mean_floor: float | None = Field(default=None, gt=0.0)
    support_floor: float | None = None
    support_ceiling: float | None = None
    normalization_mode: str | None = None
    target_potential_outcome: str | None = Field(default=None, pattern=r"^(y0|y1)$")

    @model_validator(mode="after")
    def _validate_parameters(self) -> "DistributionalFunctionalParameters":
        _ensure_finite(self.poverty_line, field_name="poverty_line")
        _ensure_finite(self.atkinson_epsilon, field_name="atkinson_epsilon")
        _ensure_finite(self.mean_floor, field_name="mean_floor")
        _ensure_finite(self.support_floor, field_name="support_floor")
        _ensure_finite(self.support_ceiling, field_name="support_ceiling")
        _ensure_non_empty(self.normalization_mode, field_name="normalization_mode")
        if (
            self.support_floor is not None
            and self.support_ceiling is not None
            and self.support_floor > self.support_ceiling
        ):
            raise ValueError("support_floor must be <= support_ceiling")
        for value in self.poverty_lines:
            _ensure_finite(value, field_name="poverty_lines")
        return self


class DistributionalProofArtifact(BaseModel):
    """Typed proof wrapper for distributional estimands and coupling-level claims."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    base_proof_ref: ProofBundleRef | None = None
    estimand_ast_ref: EstimandASTRef | None = None
    target: DistributionalProofTarget
    support_ref: ArtifactRefModel | None = None
    grid_ref: ArtifactRefModel | None = None
    identified_curve_ref: ArtifactRefModel | None = None
    bounded_curve_ref: ArtifactRefModel | None = None
    derived_from_target: DistributionalProofTarget | None = None
    bound_uniformity: DistributionalBoundUniformity = DistributionalBoundUniformity.NOT_APPLICABLE
    coupling_status: DistributionalCouplingStatus = DistributionalCouplingStatus.NOT_USED
    theorem_family: str = Field(min_length=1)
    assumption_card_refs: list[CausalAssumptionCardRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_artifact(self) -> "DistributionalProofArtifact":
        _ensure_non_empty(self.theorem_family, field_name="theorem_family")
        _validate_unique_artifact_refs(
            [ArtifactRefModel.model_validate(ref.model_dump(mode="json")) for ref in self.assumption_card_refs],
            field_name="assumption_card_refs",
        )
        if self.target is DistributionalProofTarget.COUPLING:
            if self.coupling_status is DistributionalCouplingStatus.NOT_USED:
                raise ValueError("coupling target requires a non-trivial coupling_status")
        elif self.coupling_status is not DistributionalCouplingStatus.NOT_USED:
            raise ValueError("non-coupling targets must use coupling_status='not_used'")
        if self.coupling_status in {
            DistributionalCouplingStatus.IDENTIFIED,
            DistributionalCouplingStatus.SET_IDENTIFIED,
        } and self.base_proof_ref is None:
            raise ValueError("identified or set-identified coupling claims require base_proof_ref")
        derived_targets = {
            DistributionalProofTarget.QUANTILE,
            DistributionalProofTarget.TAIL_PROB,
            DistributionalProofTarget.EXPECTED_SHORTFALL,
            DistributionalProofTarget.LORENZ,
        }
        if self.target in derived_targets:
            allowed_sources = (
                {
                    DistributionalProofTarget.CDF,
                    DistributionalProofTarget.SURVIVAL,
                }
                if self.target is DistributionalProofTarget.LORENZ
                else {
                    DistributionalProofTarget.CDF,
                    DistributionalProofTarget.SURVIVAL,
                    DistributionalProofTarget.MARGINAL_PAIR,
                }
            )
            if self.derived_from_target not in allowed_sources:
                raise ValueError("derived distributional targets must cite a valid upstream source")
            if self.bound_uniformity is DistributionalBoundUniformity.POINTWISE_ONLY:
                raise ValueError("derived distributional targets cannot rely on pointwise-only bounds")
        elif self.derived_from_target is not None:
            raise ValueError("derived_from_target is only valid for derived functionals")
        if self.bound_uniformity in {
            DistributionalBoundUniformity.UNIFORM_SHARP,
            DistributionalBoundUniformity.UNIFORM_OUTER,
            DistributionalBoundUniformity.POINTWISE_ONLY,
        } and self.bounded_curve_ref is None:
            raise ValueError("bounded proof artifacts require bounded_curve_ref")
        if self.bound_uniformity is DistributionalBoundUniformity.IDENTIFIED and self.base_proof_ref is None:
            raise ValueError("identified distributional proof artifacts require base_proof_ref")
        if (
            self.target is not DistributionalProofTarget.COUPLING
            and self.bound_uniformity is DistributionalBoundUniformity.NOT_APPLICABLE
            and self.base_proof_ref is None
            and self.identified_curve_ref is None
            and self.bounded_curve_ref is None
        ):
            raise ValueError("marginal distributional proof artifacts require proof or curve refs")
        return self


class DistributionBin(BaseModel):
    """Store one histogram bin in a normalized discrete distribution summary."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=0)
    lower_edge: float
    upper_edge: float
    midpoint: float
    probability: float = Field(ge=0.0, le=1.0)
    sample_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_bin(self) -> "DistributionBin":
        lower = _ensure_finite(self.lower_edge, field_name="lower_edge")
        upper = _ensure_finite(self.upper_edge, field_name="upper_edge")
        midpoint = _ensure_finite(self.midpoint, field_name="midpoint")
        _ensure_finite(self.probability, field_name="probability")
        if upper < lower:
            raise ValueError("upper_edge must be >= lower_edge")
        if midpoint < lower or midpoint > upper:
            raise ValueError("midpoint must fall within [lower_edge, upper_edge]")
        return self


class DiscreteDistributionSummary(BaseModel):
    """Describe a weighted discrete outcome distribution over histogram bins."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    outcome_name: str = Field(min_length=1)
    sample_size: int = Field(ge=1)
    total_weight: float = Field(gt=0.0)
    weighting_mode: str = Field(min_length=1)
    mean_value: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    bins: list[DistributionBin] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_distribution(self) -> "DiscreteDistributionSummary":
        _ensure_non_empty(self.outcome_name, field_name="outcome_name")
        _ensure_non_empty(self.weighting_mode, field_name="weighting_mode")
        for field_name in ("total_weight", "mean_value", "min_value", "max_value"):
            _ensure_finite(getattr(self, field_name), field_name=field_name)
        total_probability = sum(bin_.probability for bin_ in self.bins)
        if abs(total_probability - 1.0) > 1e-6:
            raise ValueError(
                f"distribution probabilities must sum to 1.0, got {total_probability:.8f}"
            )
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValueError("min_value must be <= max_value")
        return self


class GridAxis(BaseModel):
    """Describe the grid over which a distributional envelope is reported."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    axis_name: str = Field(min_length=1)
    values: tuple[float, ...] = Field(min_length=1)
    unit: str | None = None

    @model_validator(mode="after")
    def _validate_axis(self) -> "GridAxis":
        _ensure_non_empty(self.axis_name, field_name="axis_name")
        _ensure_non_empty(self.unit, field_name="unit")
        previous: float | None = None
        for value in self.values:
            finite_value = _ensure_finite(value, field_name="values")
            if finite_value is None:
                raise ValueError("axis values must be finite")
            if previous is not None and finite_value <= previous:
                raise ValueError("axis values must be strictly increasing")
            previous = finite_value
        return self


class FunctionalBounds(BaseModel):
    """Store lower/upper envelopes for one functional on a fixed grid."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lower: tuple[float, ...] = Field(min_length=1)
    upper: tuple[float, ...] = Field(min_length=1)
    monotone: bool | None = None
    notes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_bounds(self) -> "FunctionalBounds":
        if len(self.lower) != len(self.upper):
            raise ValueError("lower and upper bounds must have equal length")
        for lower_value, upper_value in zip(self.lower, self.upper, strict=True):
            finite_lower = _ensure_finite(lower_value, field_name="lower")
            finite_upper = _ensure_finite(upper_value, field_name="upper")
            if finite_lower is None or finite_upper is None:
                raise ValueError("functional bounds must be finite")
            if finite_lower > finite_upper:
                raise ValueError("lower bounds must not exceed upper bounds")
        return self


DistributionalDualCertificate.model_rebuild()


class DistributionalBoundsMethodSummary(BaseModel):
    """Summarize one distributional bounds construction on a fixed query grid."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: str = Field(min_length=1)
    functional: DistributionalFunctional
    axis: GridAxis
    bounds: FunctionalBounds
    sharpness: str = Field(default="unknown", pattern=r"^(sharp|inner_approx|outer_approx|unknown)$")
    assumptions_used: list[str] = Field(default_factory=list)
    display_label: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_summary(self) -> "DistributionalBoundsMethodSummary":
        _ensure_non_empty(self.method, field_name="method")
        if len(self.axis.values) != len(self.bounds.lower):
            raise ValueError("distributional bounds axis and envelopes must have equal length")
        return self


class DistributionalBoundsBundle(BaseModel):
    """Canonical bounds contract for partially identified distributional functionals."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    estimand_type: str = Field(min_length=1)
    functional: DistributionalFunctional
    axis: GridAxis
    functional_parameters: DistributionalFunctionalParameters | None = None
    point_identified: bool = False
    consensus_bounds: FunctionalBounds | None = None
    sharpness_status: str = Field(
        default="unknown",
        pattern=r"^(sharp|inner_approx|outer_approx|unknown)$",
    )
    dual_certificate_ref: DistributionalDualCertificateRef | None = None
    method_summaries: list[DistributionalBoundsMethodSummary] = Field(default_factory=list)
    rescue_actions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_bundle(self) -> "DistributionalBoundsBundle":
        _ensure_non_empty(self.estimand_type, field_name="estimand_type")
        parameters = self.functional_parameters
        if self.functional is DistributionalFunctional.ATKINSON and (
            parameters is None or parameters.atkinson_epsilon is None
        ):
            raise ValueError("Atkinson bounds require functional_parameters.atkinson_epsilon")
        if self.functional is DistributionalFunctional.POVERTY_HEADCOUNT and self.axis.axis_name not in {
            "poverty_line",
            "threshold",
        }:
            raise ValueError("poverty_headcount bounds must use a poverty_line axis")
        warnings = list(self.warnings)
        for summary in self.method_summaries:
            if summary.functional is not self.functional:
                raise ValueError("all method_summaries must target the bundle functional")
            if summary.axis != self.axis:
                raise ValueError("all method_summaries must use the bundle axis")

        consensus_bounds = self.consensus_bounds
        if consensus_bounds is not None and len(consensus_bounds.lower) != len(self.axis.values):
            raise ValueError("consensus_bounds and axis must have equal length")

        if consensus_bounds is None and self.method_summaries:
            consensus_lower = tuple(
                max(summary.bounds.lower[index] for summary in self.method_summaries)
                for index in range(len(self.axis.values))
            )
            consensus_upper = tuple(
                min(summary.bounds.upper[index] for summary in self.method_summaries)
                for index in range(len(self.axis.values))
            )
            if any(lower > upper for lower, upper in zip(consensus_lower, consensus_upper, strict=True)):
                warnings.append(
                    "Consensus envelope is empty at one or more grid points; inspect method-specific bounds."
                )
            else:
                consensus_bounds = FunctionalBounds(
                    lower=consensus_lower,
                    upper=consensus_upper,
                )

        sharpness_status = self.sharpness_status
        if self.method_summaries:
            inferred_status = min(
                (summary.sharpness for summary in self.method_summaries),
                key=lambda candidate: {
                    "unknown": 0,
                    "outer_approx": 1,
                    "inner_approx": 2,
                    "sharp": 3,
                }[candidate],
            )
            if sharpness_status == "unknown":
                sharpness_status = inferred_status

        point_identified = self.point_identified
        if consensus_bounds is not None:
            point_identified = all(
                abs(upper - lower) <= 1e-12
                for lower, upper in zip(consensus_bounds.lower, consensus_bounds.upper, strict=True)
            )

        object.__setattr__(self, "consensus_bounds", consensus_bounds)
        object.__setattr__(self, "sharpness_status", sharpness_status)
        object.__setattr__(self, "point_identified", point_identified)
        object.__setattr__(self, "warnings", warnings)
        return self


def attach_distributional_dual_certificate_ref(
    bundle: DistributionalBoundsBundle,
    dual_certificate_ref: DistributionalDualCertificateRef | None,
) -> DistributionalBoundsBundle:
    """Attach a persisted distributional dual-certificate ref to the bundle."""

    return bundle.model_copy(update={"dual_certificate_ref": dual_certificate_ref})


class QuantileShiftEntry(BaseModel):
    """Store one baseline-to-counterfactual shift at a specific quantile."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    quantile: float = Field(ge=0.0, le=1.0)
    baseline_value: float
    counterfactual_value: float
    shift: float

    @model_validator(mode="after")
    def _validate_quantile_shift(self) -> "QuantileShiftEntry":
        for field_name in ("quantile", "baseline_value", "counterfactual_value", "shift"):
            _ensure_finite(getattr(self, field_name), field_name=field_name)
        return self


class QuantileShiftSummary(BaseModel):
    """Collect sorted quantile-shift entries for one outcome variable."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    outcome_name: str = Field(min_length=1)
    entries: list[QuantileShiftEntry] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_summary(self) -> "QuantileShiftSummary":
        _ensure_non_empty(self.outcome_name, field_name="outcome_name")
        quantiles = [entry.quantile for entry in self.entries]
        if quantiles != sorted(quantiles):
            raise ValueError("quantile entries must be sorted in ascending order")
        return self


class TailRiskDeltaEntry(BaseModel):
    """Store the exceedance and expected-shortfall delta at one baseline quantile."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    baseline_quantile: float = Field(ge=0.0, le=1.0)
    threshold_value: float
    baseline_exceedance_probability: float = Field(ge=0.0, le=1.0)
    counterfactual_exceedance_probability: float = Field(ge=0.0, le=1.0)
    exceedance_probability_delta: float
    baseline_expected_shortfall: float | None = None
    counterfactual_expected_shortfall: float | None = None
    expected_shortfall_delta: float | None = None

    @model_validator(mode="after")
    def _validate_tail_entry(self) -> "TailRiskDeltaEntry":
        for field_name in (
            "baseline_quantile",
            "threshold_value",
            "baseline_exceedance_probability",
            "counterfactual_exceedance_probability",
            "exceedance_probability_delta",
            "baseline_expected_shortfall",
            "counterfactual_expected_shortfall",
            "expected_shortfall_delta",
        ):
            _ensure_finite(getattr(self, field_name), field_name=field_name)
        return self


class TailRiskDeltaSummary(BaseModel):
    """Collect tail-risk deltas for one outcome variable."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    outcome_name: str = Field(min_length=1)
    entries: list[TailRiskDeltaEntry] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_summary(self) -> "TailRiskDeltaSummary":
        _ensure_non_empty(self.outcome_name, field_name="outcome_name")
        return self


class OTCouplingSummary(BaseModel):
    """Store a transport matrix and support diagnostics for optimal-transport analysis."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    source_support: tuple[float, ...]
    target_support: tuple[float, ...]
    transport_matrix: tuple[tuple[float, ...], ...]
    regularization_strength: float = Field(gt=0.0)
    sinkhorn_iterations: int = Field(ge=1, le=200)
    convergence_delta: float = Field(ge=0.0)
    weighting_mode: str = Field(min_length=1)
    density_ratio_diagnostics: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_coupling(self) -> "OTCouplingSummary":
        _ensure_finite(self.regularization_strength, field_name="regularization_strength")
        _ensure_finite(self.convergence_delta, field_name="convergence_delta")
        _ensure_non_empty(self.weighting_mode, field_name="weighting_mode")
        if not self.source_support:
            raise ValueError("source_support must be non-empty")
        if not self.target_support:
            raise ValueError("target_support must be non-empty")
        if len(self.transport_matrix) != len(self.source_support):
            raise ValueError("transport_matrix row count must match source_support")
        total_mass = 0.0
        for row in self.transport_matrix:
            if len(row) != len(self.target_support):
                raise ValueError("transport_matrix column count must match target_support")
            for value in row:
                finite_value = _ensure_finite(value, field_name="transport_matrix")
                if finite_value is None or finite_value < 0.0:
                    raise ValueError("transport_matrix entries must be finite and non-negative")
                total_mass += finite_value
        if abs(total_mass - 1.0) > 1e-4:
            raise ValueError(f"transport_matrix must sum to 1.0, got {total_mass:.8f}")
        return self


class SubgroupDistributionComparison(BaseModel):
    """Compare baseline and counterfactual distributions for one subgroup."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    subgroup_dimension: CohortDimension
    subgroup_id: str = Field(min_length=1)
    subgroup_label: str = Field(min_length=1)
    baseline_distribution_ref: ArtifactRefModel
    counterfactual_distribution_ref: ArtifactRefModel
    coupling_ref: ArtifactRefModel | None = None
    coupling_diagnostics: CouplingDiagnostics
    quantile_shift_ref: ArtifactRefModel | None = None
    tail_risk_delta_ref: ArtifactRefModel | None = None
    wasserstein_distance: float | None = Field(default=None, ge=0.0)
    baseline_sample_size: int = Field(ge=1)
    counterfactual_sample_size: int = Field(ge=1)
    causal_assumptions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_subgroup(self) -> "SubgroupDistributionComparison":
        _ensure_non_empty(self.subgroup_id, field_name="subgroup_id")
        _ensure_non_empty(self.subgroup_label, field_name="subgroup_label")
        _ensure_finite(self.wasserstein_distance, field_name="wasserstein_distance")
        return self


class OrdinalPovertyEstimate(BaseModel):
    """Typed ORAF estimate payload for one population snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    headcount_h: float = Field(ge=0.0, le=1.0)
    ordinal_intensity_a: float = Field(ge=0.0)
    ordinal_adjusted_headcount_q: float = Field(ge=0.0)
    af_m0_baseline: float = Field(ge=0.0)
    beta: float = Field(ge=1.0)
    k_threshold: float = Field(ge=0.0, le=1.0)
    n_agents: int = Field(ge=1)
    n_dimensions: int = Field(ge=1)
    n_poor: int = Field(ge=0)
    dimension_weights: tuple[float, ...] = ()
    deprivation_cutoffs: tuple[int, ...] = ()
    dimension_names: tuple[str, ...] = ()
    threshold_weights_basis: str = Field(default="equal", min_length=1)
    dimension_contributions: dict[str, Any] = Field(default_factory=dict)
    cutoff_diagnostics: dict[str, Any] = Field(default_factory=dict)
    legacy_gap_envelope: dict[str, Any] = Field(default_factory=dict)
    poor_mask: tuple[int, ...] = ()
    breadth_scores: tuple[float, ...] = ()
    severity_scores: tuple[float, ...] = ()
    censored_scores: tuple[float, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_estimate(self) -> "OrdinalPovertyEstimate":
        _ensure_non_empty(self.threshold_weights_basis, field_name="threshold_weights_basis")
        if self.n_poor > self.n_agents:
            raise ValueError("n_poor must not exceed n_agents")
        if self.dimension_weights and len(self.dimension_weights) != self.n_dimensions:
            raise ValueError("dimension_weights length must match n_dimensions")
        if self.deprivation_cutoffs and len(self.deprivation_cutoffs) != self.n_dimensions:
            raise ValueError("deprivation_cutoffs length must match n_dimensions")
        if self.dimension_names and len(self.dimension_names) != self.n_dimensions:
            raise ValueError("dimension_names length must match n_dimensions")
        for field_name in (
            "dimension_weights",
            "breadth_scores",
            "severity_scores",
            "censored_scores",
        ):
            values = getattr(self, field_name)
            for value in values:
                _ensure_finite(value, field_name=field_name)
        for field_name in ("poor_mask", "deprivation_cutoffs"):
            values = getattr(self, field_name)
            for value in values:
                if int(value) != value:
                    raise ValueError(f"{field_name} must contain integer-valued entries")
        for field_name in ("poor_mask", "breadth_scores", "severity_scores", "censored_scores"):
            values = getattr(self, field_name)
            if values and len(values) != self.n_agents:
                raise ValueError(f"{field_name} length must match n_agents")
        return self


class OrdinalPovertyReport(BaseModel):
    """Persist baseline/counterfactual ORAF summaries for one simulation run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    methodology: str = Field(default="oraf_phase2", min_length=1)
    baseline: OrdinalPovertyEstimate
    counterfactual: OrdinalPovertyEstimate | None = None
    deltas: dict[str, float] = Field(default_factory=dict)
    source_simulation_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_report(self) -> "OrdinalPovertyReport":
        _ensure_non_empty(self.methodology, field_name="methodology")
        _ensure_non_empty(self.source_simulation_ref, field_name="source_simulation_ref")
        if self.counterfactual is not None:
            if self.counterfactual.n_dimensions != self.baseline.n_dimensions:
                raise ValueError("baseline and counterfactual must have matching n_dimensions")
            if (
                self.counterfactual.dimension_names
                and self.baseline.dimension_names
                and self.counterfactual.dimension_names != self.baseline.dimension_names
            ):
                raise ValueError("baseline and counterfactual must use the same dimension_names")
        if not self.deltas and self.counterfactual is not None:
            object.__setattr__(
                self,
                "deltas",
                {
                    "headcount_h": self.counterfactual.headcount_h - self.baseline.headcount_h,
                    "ordinal_intensity_a": (
                        self.counterfactual.ordinal_intensity_a - self.baseline.ordinal_intensity_a
                    ),
                    "ordinal_adjusted_headcount_q": (
                        self.counterfactual.ordinal_adjusted_headcount_q
                        - self.baseline.ordinal_adjusted_headcount_q
                    ),
                    "af_m0_baseline": (
                        self.counterfactual.af_m0_baseline - self.baseline.af_m0_baseline
                    ),
                },
            )
        for key, value in self.deltas.items():
            _ensure_non_empty(key, field_name="deltas")
            _ensure_finite(value, field_name="deltas")
        return self


class DistributionalEffectBundle(BaseModel):
    """Persist the leaf artifact refs that make up a full distributional analysis bundle."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    outcome_name: str = Field(min_length=1)
    distributional_query_kind: str = Field(default="interventional_law", min_length=1)
    justification: DistributionalJustification
    marginal_justification: DistributionalJustification | None = None
    marginal_law_justification: DistributionalJustification | None = None
    coupling_justification: DistributionalJustification | None = None
    baseline_distribution_ref: ArtifactRefModel
    counterfactual_distribution_ref: ArtifactRefModel
    coupling_ref: ArtifactRefModel | None = None
    coupling_diagnostics: CouplingDiagnostics
    wasserstein_distance: float | None = Field(default=None, ge=0.0)
    quantile_shift_ref: ArtifactRefModel | None = None
    tail_risk_delta_ref: ArtifactRefModel | None = None
    ordinal_poverty_ref: OrdinalPovertyReportRef | None = None
    subgroup_distribution_refs: list[ArtifactRefModel] = Field(default_factory=list)
    distributional_bounds_refs: list[DistributionalBoundsBundleRef] = Field(default_factory=list)
    marginal_law_proof_ref: ArtifactRefModel | None = None
    distributional_proof_ref: ArtifactRefModel | None = None
    coupling_proof_ref: ArtifactRefModel | None = None
    causal_assumption_refs: list[ArtifactRefModel] = Field(default_factory=list)
    causal_assumptions: list[str] = Field(default_factory=list)
    readiness_cap: str = Field(default="simulation_ready", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_bundle(self) -> "DistributionalEffectBundle":
        _ensure_non_empty(self.outcome_name, field_name="outcome_name")
        _ensure_non_empty(self.distributional_query_kind, field_name="distributional_query_kind")
        _ensure_non_empty(self.readiness_cap, field_name="readiness_cap")
        _ensure_finite(self.wasserstein_distance, field_name="wasserstein_distance")
        marginal_law_justification = (
            self.marginal_law_justification
            or self.marginal_justification
            or self.justification
        )
        marginal_justification = self.marginal_justification or marginal_law_justification
        coupling_justification = self.coupling_justification
        if coupling_justification is None and self.coupling_ref is not None:
            coupling_justification = DistributionalJustification.SCENARIO
        if self.coupling_ref is None:
            legacy_justification = marginal_justification
        else:
            legacy_justification = _weakest_justification(
                marginal_justification,
                coupling_justification,
            )
        marginal_law_proof_ref = self.marginal_law_proof_ref or self.distributional_proof_ref
        object.__setattr__(self, "marginal_justification", marginal_justification)
        object.__setattr__(self, "marginal_law_justification", marginal_law_justification)
        object.__setattr__(self, "coupling_justification", coupling_justification)
        object.__setattr__(self, "marginal_law_proof_ref", marginal_law_proof_ref)
        if self.distributional_proof_ref is None and marginal_law_proof_ref is not None:
            object.__setattr__(self, "distributional_proof_ref", marginal_law_proof_ref)
        object.__setattr__(self, "justification", legacy_justification)
        _validate_ref_kind(
            self.ordinal_poverty_ref,
            field_name="ordinal_poverty_ref",
            allowed_kinds={"ir.ordinal_poverty_report"},
        )
        _validate_ref_kind(
            self.distributional_proof_ref,
            field_name="distributional_proof_ref",
            allowed_kinds={"ir.distributional_proof_artifact", "ir.proof_bundle"},
        )
        _validate_ref_kind(
            self.coupling_proof_ref,
            field_name="coupling_proof_ref",
            allowed_kinds={"ir.distributional_proof_artifact", "ir.negative_certificate"},
        )
        _validate_ref_list_kind(
            self.distributional_bounds_refs,
            field_name="distributional_bounds_refs",
            allowed_kind="ir.distributional_bounds_bundle",
        )
        _validate_ref_list_kind(
            self.causal_assumption_refs,
            field_name="causal_assumption_refs",
            allowed_kind="ir.causal_assumption_card",
        )
        if (
            marginal_law_justification is DistributionalJustification.BOUNDED
            and (
                not self.distributional_bounds_refs
                or self.distributional_proof_ref is None
                or self.distributional_proof_ref.kind != "ir.distributional_proof_artifact"
            )
        ):
            raise ValueError(
                "marginal_law_justification='bounded' requires distributional_bounds_refs "
                "and distributional_proof_ref"
            )
        if (
            marginal_law_justification is DistributionalJustification.IDENTIFIED
            and self.distributional_proof_ref is None
        ):
            raise ValueError("marginal_law_justification='identified' requires distributional_proof_ref")
        if (
            coupling_justification is DistributionalJustification.BOUNDED
            and (
                self.coupling_proof_ref is None
                or self.coupling_proof_ref.kind != "ir.distributional_proof_artifact"
            )
        ):
            raise ValueError(
                "coupling_justification='bounded' requires coupling_proof_ref"
            )
        if (
            coupling_justification is DistributionalJustification.IDENTIFIED
            and (
                self.coupling_proof_ref is None
                or self.coupling_proof_ref.kind != "ir.distributional_proof_artifact"
            )
        ):
            raise ValueError("coupling_justification='identified' requires coupling_proof_ref")
        _validate_unique_artifact_refs(
            self.subgroup_distribution_refs,
            field_name="subgroup_distribution_refs",
        )
        _validate_unique_artifact_refs(
            self.distributional_bounds_refs,
            field_name="distributional_bounds_refs",
        )
        _validate_unique_artifact_refs(
            self.causal_assumption_refs,
            field_name="causal_assumption_refs",
        )
        return self


class CohortImpact(BaseModel):
    """Distributional impact summary for one cohort within a breakdown."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cohort_id: str = Field(min_length=1)
    cohort_label: str = Field(min_length=1)
    population_share: float = Field(ge=0.0, le=1.0)
    metric_values: dict[str, float] = Field(default_factory=dict)
    metric_deltas: dict[str, float] = Field(default_factory=dict)
    impact_direction: ImpactDirection = ImpactDirection.NEUTRAL
    is_vulnerable: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_finite_numbers(self) -> "CohortImpact":
        for bucket_name, bucket in (
            ("metric_values", self.metric_values),
            ("metric_deltas", self.metric_deltas),
        ):
            for key, value in bucket.items():
                if not math.isfinite(value):
                    raise ValueError(f"{bucket_name}.{key} must be finite")
        return self


class DimensionBreakdown(BaseModel):
    """Distributional comparison grouped by one cohort dimension."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension: CohortDimension
    dimension_label: str = Field(min_length=1)
    cohorts: list[CohortImpact] = Field(min_length=2)
    primary_metric: str = Field(min_length=1)
    primary_metric_unit: MetricUnit = MetricUnit.PERCENT
    gini_before: float | None = Field(default=None, ge=0.0, le=1.0)
    gini_after: float | None = Field(default=None, ge=0.0, le=1.0)
    gini_delta: float | None = None

    @model_validator(mode="after")
    def _validate_population_shares(self) -> "DimensionBreakdown":
        total = sum(cohort.population_share for cohort in self.cohorts)
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Population shares must sum to ~1.0, got {total:.4f}")
        return self

    @model_validator(mode="after")
    def _validate_unique_cohort_ids(self) -> "DimensionBreakdown":
        seen: set[str] = set()
        for cohort in self.cohorts:
            if cohort.cohort_id in seen:
                raise ValueError(f"Duplicate cohort_id within dimension: {cohort.cohort_id}")
            seen.add(cohort.cohort_id)
        return self

    @model_validator(mode="after")
    def _validate_primary_metric_exists(self) -> "DimensionBreakdown":
        for cohort in self.cohorts:
            if self.primary_metric not in cohort.metric_deltas:
                raise ValueError(
                    f"Cohort {cohort.cohort_id} missing primary metric '{self.primary_metric}'"
                )
        return self

    @model_validator(mode="after")
    def _compute_gini_delta(self) -> "DimensionBreakdown":
        if (
            self.gini_before is not None
            and self.gini_after is not None
            and self.gini_delta is None
        ):
            object.__setattr__(self, "gini_delta", self.gini_after - self.gini_before)
        return self


class WinnersLosersEntry(BaseModel):
    """Flattened cohort record used in winners/losers summaries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cohort_id: str
    cohort_label: str
    dimension: CohortDimension
    net_impact: float
    impact_direction: ImpactDirection
    population_share: float = Field(ge=0.0, le=1.0)
    is_vulnerable: bool = False
    key_metric: str = ""
    key_metric_delta: float = 0.0


class WinnersLosersTable(BaseModel):
    """Partition of affected cohorts into winners, losers, and neutral groups."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    winners: list[WinnersLosersEntry] = Field(default_factory=list)
    losers: list[WinnersLosersEntry] = Field(default_factory=list)
    neutral: list[WinnersLosersEntry] = Field(default_factory=list)
    canonical_dimension: CohortDimension | None = None

    @property
    def total_winners_share(self) -> float:
        return sum(entry.population_share for entry in self.winners)

    @property
    def total_losers_share(self) -> float:
        return sum(entry.population_share for entry in self.losers)

    @property
    def vulnerable_losers(self) -> list[WinnersLosersEntry]:
        return [entry for entry in self.losers if entry.is_vulnerable]


class DistributionalReport(BaseModel):
    """Top-level distributional impact report for a policy evaluation run."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "title": "DistributionalReport",
            "description": "Distributional impact analysis report for policy evaluation.",
        },
    )

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    breakdowns: list[DimensionBreakdown] = Field(min_length=1)
    winners_losers: WinnersLosersTable = Field(default_factory=WinnersLosersTable)

    overall_gini_before: float | None = Field(default=None, ge=0.0, le=1.0)
    overall_gini_after: float | None = Field(default=None, ge=0.0, le=1.0)
    overall_gini_delta: float | None = None

    palma_ratio_before: float | None = Field(default=None, ge=0.0)
    palma_ratio_after: float | None = Field(default=None, ge=0.0)
    palma_ratio_delta: float | None = None
    ordinal_poverty_summary: dict[str, Any] = Field(default_factory=dict)

    source_simulation_ref: str | None = None
    methodology: str = "agent_aggregation"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _compute_overall_deltas(self) -> "DistributionalReport":
        if (
            self.overall_gini_before is not None
            and self.overall_gini_after is not None
            and self.overall_gini_delta is None
        ):
            object.__setattr__(
                self,
                "overall_gini_delta",
                self.overall_gini_after - self.overall_gini_before,
            )
        if (
            self.palma_ratio_before is not None
            and self.palma_ratio_after is not None
            and self.palma_ratio_delta is None
        ):
            object.__setattr__(
                self,
                "palma_ratio_delta",
                self.palma_ratio_after - self.palma_ratio_before,
            )
        return self

    def get_breakdown(self, dimension: CohortDimension) -> DimensionBreakdown | None:
        for breakdown in self.breakdowns:
            if breakdown.dimension == dimension:
                return breakdown
        return None

    def has_equity_concerns(
        self,
        *,
        gini_threshold: float = 0.02,
        vulnerable_loss_threshold_pct: float = -5.0,
    ) -> bool:
        if self.overall_gini_delta is not None and self.overall_gini_delta > gini_threshold:
            return True
        for loser in self.winners_losers.vulnerable_losers:
            if loser.net_impact < vulnerable_loss_threshold_pct:
                return True
        return False


def persist_discrete_distribution_summary(
    store: ArtifactStore,
    summary: DiscreteDistributionSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist a discrete distribution summary as a JSON leaf artifact."""
    return _persist_distributional_leaf(
        store,
        summary,
        kind="ir.discrete_distribution_summary",
        schema_name=_DISCRETE_DISTRIBUTION_SUMMARY_SCHEMA_NAME,
        schema_version=_DISCRETE_DISTRIBUTION_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_discrete_distribution_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> DiscreteDistributionSummary:
    """Load discrete distribution summary."""
    return _load_distributional_leaf(store, ref, DiscreteDistributionSummary)


def persist_distributional_bounds_bundle(
    store: ArtifactStore,
    bundle: DistributionalBoundsBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> DistributionalBoundsBundleRef:
    """Persist a distributional bounds bundle and return its typed artifact ref."""

    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind="ir.distributional_bounds_bundle",
        schema_name=_DISTRIBUTIONAL_BOUNDS_BUNDLE_SCHEMA_NAME,
        schema_version=_DISTRIBUTIONAL_BOUNDS_BUNDLE_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return DistributionalBoundsBundleRef.model_validate(ref)


def load_distributional_bounds_bundle(
    store: ArtifactStore,
    ref: DistributionalBoundsBundleRef,
) -> DistributionalBoundsBundle:
    """Load distributional bounds bundle."""

    payload = get_json_artifact(store, ref.artifact_id)
    return DistributionalBoundsBundle.model_validate(payload)


def persist_distributional_dual_certificate(
    store: ArtifactStore,
    certificate: DistributionalDualCertificate,
    *,
    inputs: list[InputRef] | None = None,
) -> DistributionalDualCertificateRef:
    """Persist a distributional dual certificate and return its typed ref."""

    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.distributional_dual_certificate",
        schema_name=_DISTRIBUTIONAL_DUAL_CERTIFICATE_SCHEMA_NAME,
        schema_version=_DISTRIBUTIONAL_DUAL_CERTIFICATE_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return DistributionalDualCertificateRef.model_validate(ref)


def load_distributional_dual_certificate(
    store: ArtifactStore,
    ref: DistributionalDualCertificateRef,
) -> DistributionalDualCertificate:
    """Load distributional dual certificate."""

    payload = get_json_artifact(store, ref.artifact_id)
    return DistributionalDualCertificate.model_validate(payload)


def persist_ot_coupling_summary(
    store: ArtifactStore,
    summary: OTCouplingSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist an optimal-transport coupling summary as a JSON leaf artifact."""
    return _persist_distributional_leaf(
        store,
        summary,
        kind="ir.ot_coupling_summary",
        schema_name=_OT_COUPLING_SUMMARY_SCHEMA_NAME,
        schema_version=_OT_COUPLING_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_ot_coupling_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> OTCouplingSummary:
    """Load ot coupling summary."""
    return _load_distributional_leaf(store, ref, OTCouplingSummary)


def persist_quantile_shift_summary(
    store: ArtifactStore,
    summary: QuantileShiftSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist a quantile-shift summary as a JSON leaf artifact."""
    return _persist_distributional_leaf(
        store,
        summary,
        kind="ir.quantile_shift_summary",
        schema_name=_QUANTILE_SHIFT_SUMMARY_SCHEMA_NAME,
        schema_version=_QUANTILE_SHIFT_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_quantile_shift_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> QuantileShiftSummary:
    """Load quantile shift summary."""
    return _load_distributional_leaf(store, ref, QuantileShiftSummary)


def persist_tail_risk_delta_summary(
    store: ArtifactStore,
    summary: TailRiskDeltaSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist a tail-risk delta summary as a JSON leaf artifact."""
    return _persist_distributional_leaf(
        store,
        summary,
        kind="ir.tail_risk_delta_summary",
        schema_name=_TAIL_RISK_DELTA_SUMMARY_SCHEMA_NAME,
        schema_version=_TAIL_RISK_DELTA_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_tail_risk_delta_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> TailRiskDeltaSummary:
    """Load tail risk delta summary."""
    return _load_distributional_leaf(store, ref, TailRiskDeltaSummary)


def persist_subgroup_distribution_comparison(
    store: ArtifactStore,
    comparison: SubgroupDistributionComparison,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist one subgroup distribution comparison as a JSON leaf artifact."""
    return _persist_distributional_leaf(
        store,
        comparison,
        kind="ir.subgroup_distribution_comparison",
        schema_name=_SUBGROUP_DISTRIBUTION_COMPARISON_SCHEMA_NAME,
        schema_version=_SUBGROUP_DISTRIBUTION_COMPARISON_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_subgroup_distribution_comparison(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> SubgroupDistributionComparison:
    """Load subgroup distribution comparison."""
    return _load_distributional_leaf(store, ref, SubgroupDistributionComparison)


def persist_causal_assumption_card(
    store: ArtifactStore,
    card: CausalAssumptionCard,
    *,
    inputs: list[InputRef] | None = None,
) -> CausalAssumptionCardRef:
    """Persist one typed causal-assumption card."""
    ref = _persist_distributional_leaf(
        store,
        card,
        kind="ir.causal_assumption_card",
        schema_name=_CAUSAL_ASSUMPTION_CARD_SCHEMA_NAME,
        schema_version=_CAUSAL_ASSUMPTION_CARD_SCHEMA_VERSION,
        inputs=inputs,
    )
    return CausalAssumptionCardRef.model_validate(ref)


def load_causal_assumption_card(
    store: ArtifactStore,
    ref: CausalAssumptionCardRef,
) -> CausalAssumptionCard:
    """Load one causal-assumption card."""
    return _load_distributional_leaf(store, ref, CausalAssumptionCard)


def persist_distributional_proof_artifact(
    store: ArtifactStore,
    artifact: DistributionalProofArtifact,
    *,
    inputs: list[InputRef] | None = None,
) -> DistributionalProofArtifactRef:
    """Persist a typed distributional proof wrapper."""
    ref = _persist_distributional_leaf(
        store,
        artifact,
        kind="ir.distributional_proof_artifact",
        schema_name=_DISTRIBUTIONAL_PROOF_ARTIFACT_SCHEMA_NAME,
        schema_version=_DISTRIBUTIONAL_PROOF_ARTIFACT_SCHEMA_VERSION,
        inputs=inputs,
    )
    return DistributionalProofArtifactRef.model_validate(ref)


def load_distributional_proof_artifact(
    store: ArtifactStore,
    ref: DistributionalProofArtifactRef,
) -> DistributionalProofArtifact:
    """Load a typed distributional proof wrapper."""
    return _load_distributional_leaf(store, ref, DistributionalProofArtifact)


def persist_ordinal_poverty_report(
    store: ArtifactStore,
    report: OrdinalPovertyReport,
    *,
    inputs: list[InputRef] | None = None,
) -> OrdinalPovertyReportRef:
    """Persist an ordinal multidimensional poverty report."""
    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind="ir.ordinal_poverty_report",
        schema_name=_ORDINAL_POVERTY_REPORT_SCHEMA_NAME,
        schema_version=_ORDINAL_POVERTY_REPORT_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return OrdinalPovertyReportRef.model_validate(ref)


def load_ordinal_poverty_report(
    store: ArtifactStore,
    ref: OrdinalPovertyReportRef,
) -> OrdinalPovertyReport:
    """Load ordinal multidimensional poverty report."""
    payload = get_json_artifact(store, ref.artifact_id)
    return OrdinalPovertyReport.model_validate(payload)


def persist_distributional_effect_bundle(
    store: ArtifactStore,
    bundle: DistributionalEffectBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> DistributionalEffectBundleRef:
    """Persist a distributional leaf-ref bundle and return its typed artifact ref."""
    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind="ir.distributional_effect_bundle",
        schema_name=_DISTRIBUTIONAL_EFFECT_BUNDLE_SCHEMA_NAME,
        schema_version=_DISTRIBUTIONAL_EFFECT_BUNDLE_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return DistributionalEffectBundleRef.model_validate(ref)


def load_distributional_effect_bundle(
    store: ArtifactStore,
    ref: DistributionalEffectBundleRef,
) -> DistributionalEffectBundle:
    """Load distributional effect bundle."""
    payload = get_json_artifact(store, ref.artifact_id)
    return DistributionalEffectBundle.model_validate(payload)


def persist_distributional_report(
    store: ArtifactStore,
    report: DistributionalReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _DISTRIBUTIONAL_REPORT_SCHEMA_NAME,
    schema_version: str = _DISTRIBUTIONAL_REPORT_SCHEMA_VERSION,
) -> DistributionalReportRef:
    """Persist a top-level distributional report and return its typed artifact ref."""
    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind="ir.distributional_report",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return DistributionalReportRef.model_validate(ref)


def load_distributional_report(
    store: ArtifactStore,
    ref: DistributionalReportRef,
) -> DistributionalReport:
    """Load distributional report."""
    payload = get_json_artifact(store, ref.artifact_id)
    return DistributionalReport.model_validate(payload)


__all__ = [
    "CausalAssumptionCard",
    "CohortDimension",
    "CohortImpact",
    "CouplingDiagnostics",
    "DimensionBreakdown",
    "DiscreteDistributionSummary",
    "DistributionBin",
    "DistributionalBoundUniformity",
    "DistributionalDualBoundWitness",
    "DistributionalDualCertificate",
    "DistributionalBoundsBundle",
    "DistributionalBoundsMethodSummary",
    "DistributionalCouplingStatus",
    "DistributionalEffectBundle",
    "DistributionalFunctional",
    "DistributionalFunctionalParameters",
    "DistributionalJustification",
    "DistributionalProofArtifact",
    "DistributionalProofTarget",
    "DistributionalReport",
    "DistributionalSupportDomain",
    "FunctionalBounds",
    "GridAxis",
    "ImpactDirection",
    "MetricUnit",
    "OrdinalPovertyEstimate",
    "OrdinalPovertyReport",
    "OTCouplingSummary",
    "QuantileShiftEntry",
    "QuantileShiftSummary",
    "SubgroupDistributionComparison",
    "TailRiskDeltaEntry",
    "TailRiskDeltaSummary",
    "WinnersLosersEntry",
    "WinnersLosersTable",
    "attach_distributional_dual_certificate_ref",
    "persist_discrete_distribution_summary",
    "load_discrete_distribution_summary",
    "persist_distributional_bounds_bundle",
    "load_distributional_bounds_bundle",
    "persist_distributional_dual_certificate",
    "load_distributional_dual_certificate",
    "persist_distributional_effect_bundle",
    "load_distributional_effect_bundle",
    "persist_ordinal_poverty_report",
    "load_ordinal_poverty_report",
    "persist_distributional_proof_artifact",
    "load_distributional_proof_artifact",
    "persist_distributional_report",
    "load_distributional_report",
    "persist_ot_coupling_summary",
    "load_ot_coupling_summary",
    "persist_quantile_shift_summary",
    "load_quantile_shift_summary",
    "persist_causal_assumption_card",
    "load_causal_assumption_card",
    "persist_subgroup_distribution_comparison",
    "load_subgroup_distribution_comparison",
    "persist_tail_risk_delta_summary",
    "load_tail_risk_delta_summary",
]
