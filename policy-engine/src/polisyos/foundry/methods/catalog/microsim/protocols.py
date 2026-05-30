"""Public microsim protocols module API."""

from __future__ import annotations

from enum import Enum
from typing import Any, ClassVar, Literal

import numpy as np
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from polisyos.foundry.calibration.identifiability import IdentifiabilityReport
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)
from polisyos.ir.registry.refs import DynamicMicrosimValidationReportRef, FiscalFeedbackLinkRef


def _to_numpy(value: Any) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value
    return np.asarray(value)


def _jsonable_array_payload(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {key: _jsonable_array_payload(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_jsonable_array_payload(item) for item in value)
    if isinstance(value, list):
        return [_jsonable_array_payload(item) for item in value]
    return value


class SurveyMicroData(BaseModel):
    """Survey micro data public type."""

    contract_id: ClassVar[str] = "foundry.microsim.survey_micro_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    market_income: Any
    weights: Any
    household_ids: Any | None = None
    features: Any | None = None
    feature_names: list[str] | None = None
    period_id: Any | None = None
    cohort_id: Any | None = None
    region_id: Any | None = None
    policy_id: Any | None = None
    reform_id: Any | None = None
    instrument_z: Any | None = None
    schedule_segments: Any | None = None
    kink_points: Any | None = None
    notch_points: Any | None = None
    income_repeat_measure: Any | None = None
    taxrate_repeat_measure: Any | None = None
    microsim_calibration_report: Any | None = None
    microsim_calibration_report_ref: Any | None = None
    sample_design: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "market_income",
        "weights",
        "household_ids",
        "features",
        "period_id",
        "cohort_id",
        "region_id",
        "policy_id",
        "reform_id",
        "instrument_z",
        "kink_points",
        "notch_points",
        "income_repeat_measure",
        "taxrate_repeat_measure",
        mode="before",
    )
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> SurveyMicroData:
        if not isinstance(self.market_income, np.ndarray) or self.market_income.ndim != 1:
            raise ValueError("market_income must be a 1D numpy array")
        if not isinstance(self.weights, np.ndarray) or self.weights.ndim != 1:
            raise ValueError("weights must be a 1D numpy array")
        n_obs = self.market_income.shape[0]
        if self.weights.shape[0] != n_obs:
            raise ValueError("weights length must match market_income length")
        if self.features is not None:
            if not isinstance(self.features, np.ndarray) or self.features.ndim != 2:
                raise ValueError("features must be a 2D numpy array")
            if self.features.shape[0] != n_obs:
                raise ValueError("features row count must match market_income length")
            if self.feature_names is not None and len(self.feature_names) != self.features.shape[1]:
                raise ValueError("feature_names length must match feature columns")
        if self.household_ids is not None:
            if not isinstance(self.household_ids, np.ndarray) or self.household_ids.ndim != 1:
                raise ValueError("household_ids must be a 1D numpy array")
            if self.household_ids.shape[0] != n_obs:
                raise ValueError("household_ids length must match market_income length")
        obs_level_fields = (
            ("period_id", self.period_id),
            ("cohort_id", self.cohort_id),
            ("region_id", self.region_id),
            ("policy_id", self.policy_id),
            ("reform_id", self.reform_id),
            ("instrument_z", self.instrument_z),
            ("income_repeat_measure", self.income_repeat_measure),
            ("taxrate_repeat_measure", self.taxrate_repeat_measure),
        )
        for field_name, value in obs_level_fields:
            if value is None:
                continue
            if not isinstance(value, np.ndarray):
                raise ValueError(f"{field_name} must be a numpy array")
            if field_name == "instrument_z":
                if value.ndim not in {1, 2}:
                    raise ValueError("instrument_z must be a 1D or 2D numpy array")
                if value.shape[0] != n_obs:
                    raise ValueError("instrument_z row count must match market_income length")
                continue
            if value.ndim != 1:
                raise ValueError(f"{field_name} must be a 1D numpy array")
            if value.shape[0] != n_obs:
                raise ValueError(f"{field_name} length must match market_income length")
        return self

    @field_serializer(
        "market_income",
        "weights",
        "household_ids",
        "features",
        "period_id",
        "cohort_id",
        "region_id",
        "policy_id",
        "reform_id",
        "instrument_z",
        "kink_points",
        "notch_points",
        "income_repeat_measure",
        "taxrate_repeat_measure",
        mode="plain",
        when_used="json",
    )
    def _serialize_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class MicrosimResult(BaseModel):
    """Carry household income outputs and summary metrics emitted by static microsimulation runs."""

    contract_id: ClassVar[str] = "foundry.microsim.result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    disposable_income: Any
    tax_liability: Any
    benefit_income: Any
    weighted_mean_disposable_income: float
    weighted_gini: float
    policy_revenue: float
    fiscal_feedback_ref: FiscalFeedbackLinkRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("disposable_income", "tax_liability", "benefit_income", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        return _to_numpy(value)

    @field_serializer(
        "disposable_income", "tax_liability", "benefit_income", mode="plain", when_used="json"
    )
    def _serialize_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    def to_uncertainty_envelope(self) -> UncertaintyEnvelope:
        point = float(self.weighted_mean_disposable_income)
        return UncertaintyEnvelope(
            point_estimate=point,
            confidence_interval=(point, point),
            confidence_level=None,
            distribution_family=DistributionFamily.UNKNOWN,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
            metadata={"weighted_gini": self.weighted_gini, "policy_revenue": self.policy_revenue},
        )


class ReweightingTargetKind(str, Enum):
    """Kinds of reweighting targets supported by the microsim calibration layer."""

    TOTAL_WEIGHT = "total_weight"
    MEAN_INCOME = "mean_income"
    FEATURE_MEAN = "feature_mean"
    INCOME_QUANTILE = "income_quantile"
    WEIGHT_QUANTILE = "weight_quantile"
    WEIGHT_GINI = "weight_gini"


class ReweightingCompatibilityStatus(str, Enum):
    """Top-level status describing whether a target set is numerically/statistically compatible."""

    COMPATIBLE = "compatible"
    APPROXIMATELY_COMPATIBLE = "approximately_compatible"
    INCOMPATIBLE = "incompatible"
    INCONCLUSIVE = "inconclusive"
    NUMERIC_FAILURE = "numeric_failure"


class ReweightingCompatibilityReason(str, Enum):
    """Machine-readable reason codes for compatibility outcomes."""

    TARGETS_SATISFIED = "TARGETS_SATISFIED"
    TARGETS_CONFLICT = "TARGETS_CONFLICT"
    BOUNDS_PRECLUDE_TARGETS = "BOUNDS_PRECLUDE_TARGETS"
    WEAK_JACOBIAN = "WEAK_JACOBIAN"
    ZERO_CELL_OR_SUPPORT = "ZERO_CELL_OR_SUPPORT"
    NONSMOOTH_TARGET_NEEDS_SMOOTHING = "NONSMOOTH_TARGET_NEEDS_SMOOTHING"
    BOOTSTRAP_FAILED = "BOOTSTRAP_FAILED"
    SOLVER_STALLED = "SOLVER_STALLED"
    INVALID_TARGET_SPEC = "INVALID_TARGET_SPEC"


class ReweightingCompatibilityTestMethod(str, Enum):
    """Compatibility test family used to classify the calibrated solution."""

    HANSEN_J = "hansen_j"
    DISTANCE_BOOTSTRAP = "distance_bootstrap"
    NONE = "none"


class ReweightingTargetSpec(BaseModel):
    """Declare one calibration target for linear or nonlinear reweighting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    kind: ReweightingTargetKind
    target_value: float
    tolerance: float | None = None
    quantile: float | None = None
    feature_name: str | None = None
    feature_index: int | None = None
    scale: float | None = None


class ReweightingTargetGap(BaseModel):
    """Per-target achieved-versus-requested gap diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    kind: ReweightingTargetKind
    target_value: float
    achieved_value: float
    abs_gap: float
    scaled_gap: float
    tolerance: float
    binding: bool = False
    shadow_price: float | None = None


class ReweightingTargetCompatibility(BaseModel):
    """Structured report describing whether a target set is feasible and well-behaved."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    status: ReweightingCompatibilityStatus
    reason_code: ReweightingCompatibilityReason | None = None
    exact_feasible: bool
    distance_to_feasibility: float
    normalized_distance: float
    test_method: ReweightingCompatibilityTestMethod = ReweightingCompatibilityTestMethod.NONE
    statistic: float | None = None
    df: int | None = None
    p_value: float | None = None
    alpha: float | None = None
    n_targets: int
    n_free_params: int
    jacobian_rank: int | None = None
    condition_number: float | None = None
    active_lower_bounds: int = 0
    active_upper_bounds: int = 0
    per_target: list[ReweightingTargetGap] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    solver_status: str = "unknown"
    solver_message: str | None = None
    iterations: int | None = None


class ReweightingResult(BaseModel):
    """Record calibrated weights plus target-versus-achieved moment gaps for replay and audit."""

    contract_id: ClassVar[str] = "foundry.microsim.reweighting_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    calibrated_weights: Any
    target_moments: dict[str, float] = Field(default_factory=dict)
    achieved_moments: dict[str, float] = Field(default_factory=dict)
    max_abs_gap: float
    target_compatibility: ReweightingTargetCompatibility | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("calibrated_weights", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        return _to_numpy(value)

    @field_serializer("calibrated_weights", mode="plain", when_used="json")
    def _serialize_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class TaxBenefitResult(BaseModel):
    """Capture disposable-income, tax-rate, and revenue outputs from tax-benefit simulations."""

    contract_id: ClassVar[str] = "foundry.microsim.tax_benefit_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    disposable_income: Any
    tax_liability: Any
    benefit_income: Any
    marginal_tax_rate: Any
    effective_tax_rate: Any
    weighted_mean_disposable_income: float
    policy_revenue: float
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "disposable_income",
        "tax_liability",
        "benefit_income",
        "marginal_tax_rate",
        "effective_tax_rate",
        mode="before",
    )
    @classmethod
    def _coerce_numpy_vector(cls, value: Any) -> Any:
        return _to_numpy(value)

    @field_serializer(
        "disposable_income",
        "tax_liability",
        "benefit_income",
        "marginal_tax_rate",
        "effective_tax_rate",
        mode="plain",
        when_used="json",
    )
    def _serialize_vector(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    def to_uncertainty_envelope(self) -> UncertaintyEnvelope:
        point = float(self.weighted_mean_disposable_income)
        return UncertaintyEnvelope(
            point_estimate=point,
            confidence_interval=(point, point),
            confidence_level=None,
            distribution_family=DistributionFamily.UNKNOWN,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
            metadata={"policy_revenue": self.policy_revenue},
        )


class BehavioralResponseResult(BaseModel):
    """Capture post-reform incomes and elasticity diagnostics emitted by behavioral-response runs."""

    contract_id: ClassVar[str] = "foundry.microsim.behavioral_response_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    adjusted_market_income: Any
    labor_supply_change: Any
    weighted_mean_income: float
    elasticity: float
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("adjusted_market_income", "labor_supply_change", mode="before")
    @classmethod
    def _coerce_behavioral_vector(cls, value: Any) -> Any:
        return _to_numpy(value)

    @field_serializer(
        "adjusted_market_income", "labor_supply_change", mode="plain", when_used="json"
    )
    def _serialize_behavioral_vector(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    def to_uncertainty_envelope(self) -> UncertaintyEnvelope:
        point = float(self.weighted_mean_income)
        lower = point
        upper = point
        elasticity_grid = getattr(self, "elasticity_grid", None)
        if isinstance(elasticity_grid, dict):
            lower_candidate = elasticity_grid.get("weighted_mean_income_lower")
            upper_candidate = elasticity_grid.get("weighted_mean_income_upper")
            if lower_candidate is not None:
                lower = float(lower_candidate)
            if upper_candidate is not None:
                upper = float(upper_candidate)
        return UncertaintyEnvelope(
            point_estimate=point,
            confidence_interval=(min(lower, point, upper), max(lower, point, upper)),
            confidence_level=None,
            distribution_family=DistributionFamily.UNKNOWN,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
            metadata={"elasticity": self.elasticity},
        )


class HeterogeneousBehavioralResponseResult(BaseModel):
    """Carry behavioral-response estimates with explicit identification semantics."""

    contract_id: ClassVar[str] = "foundry.microsim.behavioral_response_result.v2"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    adjusted_market_income: Any
    labor_supply_change: Any
    weighted_mean_income: float
    identified_object: Literal[
        "individual_eta",
        "conditional_mean_eta",
        "distribution_eta",
        "local_average_eta",
        "bounds_only",
        "not_identified",
        "manual_override_required",
    ]
    regime: Literal["cross_section", "repeated_cross_section", "panel"]
    elasticity_mean: float | None = None
    elasticity_by_obs: Any | None = None
    elasticity_lower: Any | None = None
    elasticity_upper: Any | None = None
    elasticity_grid: dict[str, Any] | None = None
    first_stage_strength: float | None = None
    overlap_score: float | None = None
    measurement_reliability: float | None = None
    effective_sample_size: float | None = None
    identifiability_status: Literal["identified", "sloppy", "non_identified"]
    identifiability: IdentifiabilityReport | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "adjusted_market_income",
        "labor_supply_change",
        "elasticity_by_obs",
        "elasticity_lower",
        "elasticity_upper",
        mode="before",
    )
    @classmethod
    def _coerce_behavioral_array(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @field_serializer(
        "adjusted_market_income",
        "labor_supply_change",
        "elasticity_by_obs",
        "elasticity_lower",
        "elasticity_upper",
        mode="plain",
        when_used="json",
    )
    def _serialize_behavioral_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    def to_uncertainty_envelope(self) -> UncertaintyEnvelope:
        point = float(self.weighted_mean_income)
        lower = point
        upper = point
        if isinstance(self.elasticity_grid, dict):
            lower_candidate = self.elasticity_grid.get("weighted_mean_income_lower")
            upper_candidate = self.elasticity_grid.get("weighted_mean_income_upper")
            if lower_candidate is not None:
                lower = float(lower_candidate)
            if upper_candidate is not None:
                upper = float(upper_candidate)
        return UncertaintyEnvelope(
            point_estimate=point,
            confidence_interval=(min(lower, point, upper), max(lower, point, upper)),
            confidence_level=None,
            distribution_family=DistributionFamily.UNKNOWN,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
            metadata={
                "identified_object": self.identified_object,
                "identifiability_status": self.identifiability_status,
                "elasticity_mean": self.elasticity_mean,
            },
        )


class InverseBehavioralIdentifiedSet(BaseModel):
    """Set-valued fallback summary when inverse calibration is only partially identified."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    parameter_bounds: dict[str, tuple[float, float]] = Field(default_factory=dict)
    representative_point: dict[str, float] = Field(default_factory=dict)
    feasible_share: float | None = Field(default=None, ge=0.0, le=1.0)
    grid_size: int | None = Field(default=None, ge=1)
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_parameter_bounds(self) -> InverseBehavioralIdentifiedSet:
        for key, interval in self.parameter_bounds.items():
            lower, upper = interval
            if not np.isfinite(lower) or not np.isfinite(upper):
                raise ValueError(f"parameter_bounds.{key} must be finite")
            if lower > upper:
                raise ValueError(f"parameter_bounds.{key} lower must be <= upper")
        return self


class InverseBehavioralCalibrationResult(BaseModel):
    """Typed inverse-calibration artifact for Track 11 behavioral calibration."""

    contract_id: ClassVar[str] = "foundry.microsim.inverse_behavioral_calibration_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    objective_family: str
    constraint_family: str
    objective_params: dict[str, float] = Field(default_factory=dict)
    constraint_params: dict[str, float] = Field(default_factory=dict)
    normalization: dict[str, Any] = Field(default_factory=dict)
    fit_loss: float = Field(ge=0.0)
    optimality_gap_stats: dict[str, float] = Field(default_factory=dict)
    identified_object: Literal[
        "objective_params",
        "objective_and_constraint_params",
        "bounds_only",
        "not_identified",
        "manual_override_required",
    ]
    regime: Literal["cross_section", "repeated_cross_section", "panel"]
    effective_sample_size: float | None = None
    measurement_reliability: float | None = None
    identifiability_status: Literal["identified", "sloppy", "non_identified"]
    identifiability: IdentifiabilityReport | None = None
    jacobian_rank: int | None = Field(default=None, ge=0)
    condition_number: float | None = Field(default=None, ge=0.0)
    bootstrap_intervals: dict[str, tuple[float, float]] = Field(default_factory=dict)
    identified_set: InverseBehavioralIdentifiedSet | None = None
    identified_set_summary: dict[str, Any] | None = None
    fallback_used: bool = False
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    microsim_calibration_report: dict[str, Any] | None = None
    microsim_calibration_report_ref: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_identification_payload(self) -> InverseBehavioralCalibrationResult:
        if self.identified_object == "bounds_only" and self.identified_set is None:
            raise ValueError("identified_set is required when identified_object='bounds_only'")
        if (
            self.identified_object == "objective_and_constraint_params"
            and not self.constraint_params
        ):
            raise ValueError(
                "constraint_params are required when "
                "identified_object='objective_and_constraint_params'"
            )
        if self.identified_object == "not_identified" and self.objective_params:
            raise ValueError("not_identified results cannot publish objective_params")
        return self


class ImputationResult(BaseModel):
    """Record imputed incomes and training-quality metadata for missing-data repair."""

    contract_id: ClassVar[str] = "foundry.microsim.imputation_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    imputed_market_income: Any
    missing_share: float
    rmse_train: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("imputed_market_income", mode="before")
    @classmethod
    def _coerce_imputed_vector(cls, value: Any) -> Any:
        return _to_numpy(value)

    @field_serializer("imputed_market_income", mode="plain", when_used="json")
    def _serialize_imputed_vector(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class MNARIncomeBoundsTarget(BaseModel):
    """Describe the estimand bounded by a microsim MNAR sensitivity run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    estimand: Literal["weighted_mean_income"] = "weighted_mean_income"
    scale: Literal["raw_income", "log_income", "equivalized_income"] = "raw_income"
    weighted: bool = True
    back_transform_rule: str | None = None
    equivalence_scale_source: str | None = None


class MNARIncomeAssumptionVector(BaseModel):
    """Machine-readable summary of the assumptions defining an MNAR family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mechanism_class: Literal[
        "selection.logit",
        "selection.probit",
        "pattern_mixture.locscale",
        "support_only",
    ]
    income_score: str | None = None
    gamma_range: tuple[float, float] | None = None
    delta_range: tuple[float, float] | None = None
    lambda_range: tuple[float, float] | None = None
    support_bounds: tuple[float, float]
    strata: tuple[str, ...] = ()
    external_anchors: tuple[str, ...] = ()
    missingness_types: tuple[str, ...] = ()
    taxonomy_entries: tuple[str, ...] = ()
    additional_restrictions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_ranges(self) -> MNARIncomeAssumptionVector:
        if self.support_bounds[0] > self.support_bounds[1]:
            raise ValueError("support_bounds must be ordered")
        for label, interval in (
            ("gamma_range", self.gamma_range),
            ("delta_range", self.delta_range),
            ("lambda_range", self.lambda_range),
        ):
            if interval is not None and interval[0] > interval[1]:
                raise ValueError(f"{label} must be ordered")
        if self.lambda_range is not None and self.lambda_range[0] <= 0.0:
            raise ValueError("lambda_range must remain strictly positive")
        return self


class MNARIncomeBoundsInterval(BaseModel):
    """Lower/upper interval for a deterministic MNAR bounds run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lower: float
    upper: float
    reference_value: float | None = None
    grid_argmin: dict[str, Any] | None = None
    grid_argmax: dict[str, Any] | None = None
    manski_outer_bound: dict[str, float] | None = None

    @model_validator(mode="after")
    def _validate_bounds(self) -> MNARIncomeBoundsInterval:
        if self.lower > self.upper:
            raise ValueError("lower bound must not exceed upper bound")
        if self.reference_value is not None and not (
            self.lower <= self.reference_value <= self.upper
        ):
            raise ValueError("reference_value must lie within the interval")
        if self.manski_outer_bound is not None:
            lower = float(self.manski_outer_bound.get("lower", self.lower))
            upper = float(self.manski_outer_bound.get("upper", self.upper))
            if lower > upper:
                raise ValueError("manski_outer_bound must be ordered")
        return self


class MNARIncomeBoundsDiagnostics(BaseModel):
    """Diagnostics and audit hooks for the MNAR bounds calculation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    response_rate: float
    missing_share: float
    weight_dispersion: float | None = None
    effective_sample_size: float | None = None
    share_clipped_to_support: float | None = None
    alpha_solver_converged: bool | None = None
    selection_weight_effective_sample_size_min: float | None = None
    selection_curve_monotonicity: str | None = None
    tail_amplification: float | None = None
    mi_monte_carlo_error: float | None = None
    notes: dict[str, Any] = Field(default_factory=dict)


class MNARIncomeBoundsProvenance(BaseModel):
    """Provenance fields emitted alongside MNAR bounds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: str
    timestamp_utc: str
    software: str = "polisyos"
    source_contract: str = SurveyMicroData.contract_id


class MNARIncomeBoundsResult(BaseModel):
    """Typed payload stored in ``ImputationResult.metadata['mnar_bounds']``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "mnar_income_bounds_result.v1"
    target: MNARIncomeBoundsTarget
    assumption_vector: MNARIncomeAssumptionVector
    bounds: MNARIncomeBoundsInterval
    diagnostics: MNARIncomeBoundsDiagnostics
    provenance: MNARIncomeBoundsProvenance
    scenario_grid: tuple[dict[str, Any], ...] = ()
    strata: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()


class ValidationMomentSpec(BaseModel):
    """Declare one life-cycle income moment used by dynamic microsim validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    moment_id: str
    family: Literal["level", "dispersion", "tail", "persistence", "mobility", "lifetime"]
    scale: Literal["raw", "log", "equivalized", "relative"]
    unit: str
    transform: str | None = None
    tolerance_abs: float | None = Field(default=None, ge=0.0)
    tolerance_rel: float | None = Field(default=None, ge=0.0)
    primary: bool = True


class ValidationCellResult(BaseModel):
    """Per cohort-horizon-moment comparison between simulated and observed panel moments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cohort_key: dict[str, str | int]
    horizon_years: int = Field(ge=0)
    moment_id: str
    support_type: Literal["direct", "stitched", "extrapolated"]
    simulated_value: float
    observed_value: float
    bias: float
    relative_bias: float | None = None
    se: float | None = Field(default=None, ge=0.0)
    test_stat: float | None = None
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    p_value_adjusted: float | None = Field(default=None, ge=0.0, le=1.0)
    ci_lower: float | None = None
    ci_upper: float | None = None
    n_sim: int | None = Field(default=None, ge=0)
    n_obs: int | None = Field(default=None, ge=0)
    ess_obs: float | None = Field(default=None, ge=0.0)
    ess_sim: float | None = Field(default=None, ge=0.0)


class ValidationOmnibusTest(BaseModel):
    """Vector-level validation test over horizons, moments, or the full diagnostic grid."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: Literal["cohort_moment_horizons", "cohort_all_moments", "global_all"]
    method: Literal["wald", "hansen_j_type", "diebold_mariano", "giacomini_white", "sup_wald"]
    null_hypothesis: str
    statistic: float
    df: int | None = Field(default=None, ge=0)
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    p_value_adjusted: float | None = Field(default=None, ge=0.0, le=1.0)
    covariance_estimator: str | None = None
    bootstrap_reps: int | None = Field(default=None, ge=0)


class HorizonBiasEnvelope(BaseModel):
    """Horizon-dependent bias path with pointwise or simultaneous uncertainty bands."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_moment_id: str
    horizons: list[int]
    point_path: list[float]
    lower_path: list[float]
    upper_path: list[float]
    confidence_level: float = Field(gt=0.0, lt=1.0)
    simultaneous: bool = True
    method: Literal[
        "sup_t_block_bootstrap",
        "pointwise_block_bootstrap",
        "state_space_parametric",
        "hybrid",
    ]
    scale: Literal["bias", "relative_bias"]
    block_scheme: str | None = None
    block_length: int | None = Field(default=None, ge=1)
    extrapolated_from_horizon: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _validate_path_lengths(self) -> HorizonBiasEnvelope:
        n_horizons = len(self.horizons)
        if not (
            len(self.point_path)
            == len(self.lower_path)
            == len(self.upper_path)
            == n_horizons
        ):
            raise ValueError("horizons, point_path, lower_path, and upper_path lengths must match")
        return self


class SensitivityRunResult(BaseModel):
    """Summary for one dynamic-validation sensitivity scenario."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: str
    changed_inputs: dict[str, Any]
    status: Literal["pass", "warn", "fail", "inconclusive"]
    key_shifts: dict[str, float] = Field(default_factory=dict)


class DynamicMicrosimValidationDiagnostic(BaseModel):
    """Typed validation artifact for dynamic microsimulation against panel moments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    status: Literal["pass", "warn", "fail", "inconclusive", "not_run"]
    validation_target: Literal["life_cycle_income_moments"] = "life_cycle_income_moments"
    comparison_dataset: str
    comparison_dataset_version: str | None = None
    panel_span_years: int | None = Field(default=None, ge=0)
    direct_support_max_horizon: int | None = Field(default=None, ge=0)
    cohort_dimensions: tuple[str, ...]
    horizons_reported: list[int]
    moment_specs: list[ValidationMomentSpec]
    cell_results: list[ValidationCellResult]
    omnibus_tests: list[ValidationOmnibusTest] = Field(default_factory=list)
    bias_envelopes: list[HorizonBiasEnvelope] = Field(default_factory=list)
    sensitivity_runs: list[SensitivityRunResult] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _default_dynamic_validation_moments() -> tuple[ValidationMomentSpec, ...]:
    return (
        ValidationMomentSpec(
            moment_id="mean_log_income",
            family="level",
            scale="log",
            unit="log_currency",
            transform="log(max(y, 1))",
            tolerance_abs=0.03,
            primary=True,
        ),
        ValidationMomentSpec(
            moment_id="median_income",
            family="level",
            scale="raw",
            unit="currency",
            primary=True,
        ),
        ValidationMomentSpec(
            moment_id="p10_income",
            family="tail",
            scale="raw",
            unit="currency",
            primary=True,
        ),
        ValidationMomentSpec(
            moment_id="p90_income",
            family="tail",
            scale="raw",
            unit="currency",
            primary=True,
        ),
        ValidationMomentSpec(
            moment_id="var_log_income",
            family="dispersion",
            scale="log",
            unit="log_currency_sq",
            transform="var(log(max(y, 1)))",
            primary=True,
        ),
        ValidationMomentSpec(
            moment_id="low_income_share",
            family="tail",
            scale="raw",
            unit="share",
            primary=True,
        ),
        ValidationMomentSpec(
            moment_id="autocovariance_1y_log_income",
            family="persistence",
            scale="log",
            unit="log_currency_sq",
            transform="cov(log(y_t), log(y_t-1))",
            primary=True,
        ),
        ValidationMomentSpec(
            moment_id="autocovariance_5y_log_income",
            family="persistence",
            scale="log",
            unit="log_currency_sq",
            transform="cov(log(y_t), log(y_t-5))",
            primary=True,
        ),
        ValidationMomentSpec(
            moment_id="rank_rank_persistence",
            family="mobility",
            scale="relative",
            unit="correlation",
            primary=True,
        ),
        ValidationMomentSpec(
            moment_id="lifetime_discounted_income",
            family="lifetime",
            scale="raw",
            unit="currency_present_value",
            transform="sum(beta^h * y_h)",
            primary=True,
        ),
    )


class DynamicValidationSensitivitySpec(BaseModel):
    """One robustness scenario for dynamic microsim validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: str
    changed_inputs: dict[str, Any] = Field(default_factory=dict)


class DynamicValidationSpec(BaseModel):
    """Configuration for validating dynamic microsimulation moments against panel data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    comparison_dataset: str
    comparison_dataset_version: str | None = None
    panel_span_years: int | None = Field(default=None, ge=0)
    direct_support_max_horizon: int | None = Field(default=None, ge=0)
    income_concept: Literal["market", "gross", "disposable", "equivalized_disposable"] = "market"
    cohort_dimensions: tuple[str, ...] = ("all",)
    horizons: tuple[int, ...] = ()
    moment_specs: tuple[ValidationMomentSpec, ...] = Field(
        default_factory=_default_dynamic_validation_moments
    )
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    bootstrap_reps: int = Field(default=199, ge=0)
    bootstrap_seed: int = 0
    block_scheme: str = "stationary_bootstrap"
    block_length: int = Field(default=4, ge=1)
    support_type_by_horizon: dict[int, Literal["direct", "stitched", "extrapolated"]] = Field(
        default_factory=dict
    )
    low_income_threshold: float = 1.0
    minimum_cell_ess: float | None = Field(default=None, ge=0.0)
    multiple_testing_correction: Literal["none", "bonferroni", "holm_stepdown"] = "holm_stepdown"
    max_abs_relative_bias_warn: float | None = Field(default=0.05, ge=0.0)
    max_abs_relative_bias_fail: float | None = Field(default=0.10, ge=0.0)
    global_pass_rule: Literal["tolerance", "p_value_or_tolerance"] = "tolerance"
    sensitivity_scenarios: tuple[DynamicValidationSensitivitySpec, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_horizons(self) -> DynamicValidationSpec:
        if any(horizon < 0 for horizon in self.horizons):
            raise ValueError("horizons must be non-negative")
        if (
            self.max_abs_relative_bias_warn is not None
            and self.max_abs_relative_bias_fail is not None
            and self.max_abs_relative_bias_warn > self.max_abs_relative_bias_fail
        ):
            raise ValueError("warn relative-bias threshold must be <= fail threshold")
        return self


class DynamicMicrosimResult(BaseModel):
    """Carry final outcomes and time paths emitted by dynamic microsimulation runs."""

    contract_id: ClassVar[str] = "foundry.microsim.dynamic_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    final_market_income: Any
    disposable_income: Any
    mean_income_path: list[float] = Field(default_factory=list)
    policy_revenue_path: list[float] = Field(default_factory=list)
    weighted_mean_final_income: float
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("final_market_income", "disposable_income", mode="before")
    @classmethod
    def _coerce_dynamic_vector(cls, value: Any) -> Any:
        return _to_numpy(value)

    @field_serializer("final_market_income", "disposable_income", mode="plain", when_used="json")
    def _serialize_dynamic_vector(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    def to_uncertainty_envelope(self) -> UncertaintyEnvelope:
        point = float(self.weighted_mean_final_income)
        return UncertaintyEnvelope(
            point_estimate=point,
            confidence_interval=(point, point),
            confidence_level=None,
            distribution_family=DistributionFamily.UNKNOWN,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
            metadata={"mean_income_path": list(self.mean_income_path)},
        )


class DynamicMicrosimResultV2(DynamicMicrosimResult):
    """Dynamic microsimulation result with optional validation and replay-ready path payloads."""

    contract_id: ClassVar[str] = "foundry.microsim.dynamic_result.v2"

    validation_diagnostic: DynamicMicrosimValidationDiagnostic | None = None
    dynamic_validation_report_ref: DynamicMicrosimValidationReportRef | None = None
    market_income_path: Any | None = None
    weights: Any | None = None
    cohort_data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("market_income_path", "weights", mode="before")
    @classmethod
    def _coerce_optional_dynamic_array(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @field_validator("cohort_data", mode="before")
    @classmethod
    def _coerce_cohort_data(cls, value: Any) -> Any:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("cohort_data must be a mapping")
        return {
            str(key): _to_numpy(item) if item is not None else None
            for key, item in value.items()
        }

    @model_validator(mode="after")
    def _validate_optional_paths(self) -> DynamicMicrosimResultV2:
        final_income = np.asarray(self.final_market_income)
        if self.market_income_path is not None:
            path = np.asarray(self.market_income_path)
            if path.ndim != 2:
                raise ValueError("market_income_path must be a 2D array of periods by observations")
            if path.shape[1] != final_income.shape[0]:
                raise ValueError("market_income_path observation count must match final_market_income")
        if self.weights is not None:
            weights = np.asarray(self.weights)
            if weights.ndim != 1:
                raise ValueError("weights must be a 1D array")
            if weights.shape[0] != final_income.shape[0]:
                raise ValueError("weights length must match final_market_income")
        for key, value in self.cohort_data.items():
            if value is None:
                continue
            array = np.asarray(value)
            if array.ndim != 1:
                raise ValueError(f"cohort_data.{key} must be a 1D array")
            if array.shape[0] != final_income.shape[0]:
                raise ValueError(f"cohort_data.{key} length must match final_market_income")
        return self

    @field_serializer("market_income_path", "weights", mode="plain", when_used="json")
    def _serialize_optional_dynamic_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @field_serializer("cohort_data", mode="plain", when_used="json")
    def _serialize_cohort_data(self, value: dict[str, Any]) -> Any:
        return _jsonable_array_payload(value)

    @classmethod
    def from_v1(
        cls,
        result: DynamicMicrosimResult,
        *,
        validation_diagnostic: DynamicMicrosimValidationDiagnostic | None = None,
        market_income_path: Any | None = None,
        weights: Any | None = None,
        cohort_data: dict[str, Any] | None = None,
        dynamic_validation_report_ref: DynamicMicrosimValidationReportRef | None = None,
    ) -> DynamicMicrosimResultV2:
        payload = result.model_dump(mode="python")
        payload.update(
            {
                "validation_diagnostic": validation_diagnostic,
                "dynamic_validation_report_ref": dynamic_validation_report_ref,
                "market_income_path": market_income_path,
                "weights": weights,
                "cohort_data": cohort_data or {},
            }
        )
        return cls.model_validate(payload)

    def to_uncertainty_envelope(self) -> UncertaintyEnvelope:
        point = float(self.weighted_mean_final_income)
        metadata: dict[str, Any] = {
            "mean_income_path": list(self.mean_income_path),
            "validation_status": (
                self.validation_diagnostic.status if self.validation_diagnostic is not None else None
            ),
        }
        if self.validation_diagnostic is not None:
            metadata["validation_warnings"] = list(self.validation_diagnostic.warnings)
            candidates = {
                "mean_income",
                "mean_market_income",
                "weighted_mean_final_income",
            }
            selected = next(
                (
                    envelope
                    for envelope in self.validation_diagnostic.bias_envelopes
                    if envelope.target_moment_id in candidates
                    and envelope.scale == "bias"
                    and envelope.point_path
                ),
                None,
            )
            if selected is not None:
                lower_bias = float(selected.lower_path[-1])
                upper_bias = float(selected.upper_path[-1])
                corrected_lower = point - upper_bias
                corrected_upper = point - lower_bias
                metadata["validation_bias_envelope"] = selected.model_dump(mode="python")
                return UncertaintyEnvelope(
                    point_estimate=point,
                    confidence_interval=(
                        min(corrected_lower, corrected_upper),
                        max(corrected_lower, corrected_upper),
                    ),
                    confidence_level=float(selected.confidence_level),
                    distribution_family=DistributionFamily.BOOTSTRAP,
                    source=UncertaintySource.BOOTSTRAP,
                    propagation_method=PropagationMethod.MONTE_CARLO,
                    interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
                    metadata=metadata,
                )
        return UncertaintyEnvelope(
            point_estimate=point,
            confidence_interval=(point, point),
            confidence_level=None,
            distribution_family=DistributionFamily.UNKNOWN,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
            metadata=metadata,
        )


def upgrade_dynamic_microsim_result(
    result: DynamicMicrosimResult | DynamicMicrosimResultV2,
    *,
    validation_diagnostic: DynamicMicrosimValidationDiagnostic | None = None,
    dynamic_validation_report_ref: DynamicMicrosimValidationReportRef | None = None,
    market_income_path: Any | None = None,
    weights: Any | None = None,
    cohort_data: dict[str, Any] | None = None,
) -> DynamicMicrosimResultV2:
    """Adapt a v1 dynamic microsim result into the v2 validation-ready contract."""

    if isinstance(result, DynamicMicrosimResultV2):
        updates: dict[str, Any] = {}
        if validation_diagnostic is not None:
            updates["validation_diagnostic"] = validation_diagnostic
        if dynamic_validation_report_ref is not None:
            updates["dynamic_validation_report_ref"] = dynamic_validation_report_ref
        if market_income_path is not None:
            updates["market_income_path"] = market_income_path
        if weights is not None:
            updates["weights"] = weights
        if cohort_data is not None:
            updates["cohort_data"] = cohort_data
        if not updates:
            return result
        payload = result.model_dump(mode="python")
        payload.update(updates)
        return DynamicMicrosimResultV2.model_validate(payload)
    return DynamicMicrosimResultV2.from_v1(
        result,
        validation_diagnostic=validation_diagnostic,
        dynamic_validation_report_ref=dynamic_validation_report_ref,
        market_income_path=market_income_path,
        weights=weights,
        cohort_data=cohort_data,
    )


__all__ = [
    "BehavioralResponseResult",
    "DynamicMicrosimResultV2",
    "DynamicMicrosimResult",
    "DynamicMicrosimValidationDiagnostic",
    "DynamicValidationSensitivitySpec",
    "DynamicValidationSpec",
    "HeterogeneousBehavioralResponseResult",
    "HorizonBiasEnvelope",
    "ImputationResult",
    "InverseBehavioralCalibrationResult",
    "InverseBehavioralIdentifiedSet",
    "MNARIncomeAssumptionVector",
    "MNARIncomeBoundsDiagnostics",
    "MNARIncomeBoundsInterval",
    "MNARIncomeBoundsProvenance",
    "MNARIncomeBoundsResult",
    "MNARIncomeBoundsTarget",
    "MicrosimResult",
    "ReweightingCompatibilityReason",
    "ReweightingCompatibilityStatus",
    "ReweightingCompatibilityTestMethod",
    "ReweightingResult",
    "ReweightingTargetCompatibility",
    "ReweightingTargetGap",
    "ReweightingTargetKind",
    "ReweightingTargetSpec",
    "SensitivityRunResult",
    "SurveyMicroData",
    "TaxBenefitResult",
    "ValidationCellResult",
    "ValidationMomentSpec",
    "ValidationOmnibusTest",
    "upgrade_dynamic_microsim_result",
]
