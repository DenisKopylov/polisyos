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
from polisyos.ir.refs import FiscalFeedbackLinkRef


def _to_numpy(value: Any) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value
    return np.asarray(value)


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


__all__ = [
    "BehavioralResponseResult",
    "DynamicMicrosimResult",
    "HeterogeneousBehavioralResponseResult",
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
    "SurveyMicroData",
    "TaxBenefitResult",
]
