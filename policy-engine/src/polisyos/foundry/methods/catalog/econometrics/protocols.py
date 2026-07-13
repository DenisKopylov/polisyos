"""Define econometric input/output contracts and the shared estimator protocol."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from statistics import NormalDist
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Protocol, runtime_checkable

import numpy as np
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from polisyos.foundry.methods.base import MethodMetadata, MethodSignature
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    NativeValueEstimandBinding,
    OutputContractDeclaration,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    ValueUncertaintyProjectionKind,
    value_uncertainty_output_contract,
)
from polisyos.ir.registry.refs import DependenceStructureRef

if TYPE_CHECKING:
    import pandas as pd


_FLOAT_EPS = 1e-12


def _to_numpy(value: Any) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value
    return np.asarray(value)


def _is_repeated_cross_section(metadata: dict[str, Any]) -> bool:
    shape = str(metadata.get("data_shape", "")).strip().lower()
    return shape in {"repeated_cross_section", "survey_repeated_cross_section", "survey_microdata"}


class PanelData(BaseModel):
    """Validated panel data input for classical econometric estimators."""

    contract_id: ClassVar[str] = "foundry.econometrics.panel_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    dependent: Any  # shape: (n_obs,)
    exog: Any  # shape: (n_obs, n_features)
    entity_ids: Any  # shape: (n_obs,)
    time_ids: Any  # shape: (n_obs,)
    instrument_ids: Any | None = None  # shape: (n_obs, n_instruments)
    feature_names: list[str] | None = None
    instrument_names: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("dependent", "exog", "entity_ids", "time_ids", "instrument_ids", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> PanelData:
        if _is_repeated_cross_section(self.metadata):
            raise ValueError(
                "panel estimators require longitudinal panel data; received repeated cross-section/survey data. "
                "Use transport, survey, or repeated cross-section workflows instead."
            )
        if not isinstance(self.dependent, np.ndarray) or self.dependent.ndim != 1:
            raise ValueError("dependent must be a 1D numpy array")
        if not isinstance(self.exog, np.ndarray) or self.exog.ndim != 2:
            raise ValueError("exog must be a 2D numpy array")
        if not isinstance(self.entity_ids, np.ndarray) or self.entity_ids.ndim != 1:
            raise ValueError("entity_ids must be a 1D numpy array")
        if not isinstance(self.time_ids, np.ndarray) or self.time_ids.ndim != 1:
            raise ValueError("time_ids must be a 1D numpy array")

        n_obs = self.dependent.shape[0]
        if self.exog.shape[0] != n_obs:
            raise ValueError("exog row count must match dependent length")
        if self.entity_ids.shape[0] != n_obs:
            raise ValueError("entity_ids length must match dependent length")
        if self.time_ids.shape[0] != n_obs:
            raise ValueError("time_ids length must match dependent length")
        if n_obs < 8:
            raise ValueError("panel data requires at least 8 observations")
        if self.exog.shape[1] < 1:
            raise ValueError("exog must contain at least one feature")

        if not np.isfinite(self.dependent).all() or not np.isfinite(self.exog).all():
            raise ValueError("dependent/exog contain non-finite values")

        n_entities = np.unique(self.entity_ids).size
        n_periods = np.unique(self.time_ids).size
        if n_entities < 2:
            raise ValueError("panel data requires at least 2 entities")
        if n_periods < 2:
            raise ValueError("panel data requires at least 2 time periods")

        if self.instrument_ids is not None:
            if not isinstance(self.instrument_ids, np.ndarray) or self.instrument_ids.ndim != 2:
                raise ValueError("instrument_ids must be a 2D numpy array")
            if self.instrument_ids.shape[0] != n_obs:
                raise ValueError("instrument_ids row count must match dependent length")
            if self.instrument_ids.shape[1] < 1:
                raise ValueError("instrument_ids must contain at least one instrument")
            if not np.isfinite(self.instrument_ids).all():
                raise ValueError("instrument_ids contain non-finite values")

        if self.feature_names is not None and len(self.feature_names) != self.exog.shape[1]:
            raise ValueError("feature_names length must match exog column count")
        if (
            self.instrument_ids is not None
            and self.instrument_names is not None
            and len(self.instrument_names) != self.instrument_ids.shape[1]
        ):
            raise ValueError("instrument_names length must match instrument_ids column count")

        return self

    @field_serializer(
        "dependent",
        "exog",
        "entity_ids",
        "time_ids",
        "instrument_ids",
        mode="plain",
        when_used="json",
    )
    def _serialize_numpy_fields(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @property
    def n_obs(self) -> int:
        return int(self.dependent.shape[0])

    @property
    def n_features(self) -> int:
        return int(self.exog.shape[1])

    @property
    def n_entities(self) -> int:
        return int(np.unique(self.entity_ids).size)

    @property
    def n_periods(self) -> int:
        return int(np.unique(self.time_ids).size)

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        *,
        dependent_col: str,
        exog_cols: list[str],
        entity_col: str,
        time_col: str,
        instrument_cols: list[str] | None = None,
    ) -> PanelData:
        frame = df.copy()
        frame = frame.sort_values([entity_col, time_col])
        return cls(
            dependent=frame[dependent_col].to_numpy(dtype=float),
            exog=frame[exog_cols].to_numpy(dtype=float),
            entity_ids=frame[entity_col].to_numpy(),
            time_ids=frame[time_col].to_numpy(),
            instrument_ids=frame[instrument_cols].to_numpy(dtype=float)
            if instrument_cols
            else None,
            feature_names=list(exog_cols),
            instrument_names=list(instrument_cols or []),
        )


class TimeSeriesData(BaseModel):
    """Validated time-series input for ARIMA/VAR estimators."""

    contract_id: ClassVar[str] = "foundry.econometrics.time_series_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    endog: Any  # shape: (T,) or (T, k)
    exog: Any | None = None  # shape: (T, m)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("endog", "exog", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> TimeSeriesData:
        if not isinstance(self.endog, np.ndarray) or self.endog.ndim not in {1, 2}:
            raise ValueError("endog must be 1D or 2D numpy array")
        if self.endog.shape[0] < 8:
            raise ValueError("time-series requires at least 8 observations")
        if not np.isfinite(self.endog).all():
            raise ValueError("endog contains non-finite values")

        if self.exog is not None:
            if not isinstance(self.exog, np.ndarray) or self.exog.ndim != 2:
                raise ValueError("exog must be a 2D numpy array")
            if self.exog.shape[0] != self.endog.shape[0]:
                raise ValueError("exog row count must match endog observations")
            if not np.isfinite(self.exog).all():
                raise ValueError("exog contains non-finite values")

        return self

    @field_serializer("endog", "exog", mode="plain", when_used="json")
    def _serialize_numpy_fields(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @property
    def n_obs(self) -> int:
        return int(self.endog.shape[0])


class ThresholdEffectModel(str, Enum):
    """Declare whether the policy rule induces a jump or a slope kink."""

    THRESHOLD = "threshold"
    KINK = "kink"


class ThresholdIdentificationMode(str, Enum):
    """Describe the identification route used by a threshold-family estimator."""

    GLOBAL_PROFILE = "global_profile"
    GLOBAL_IV_GMM = "global_iv_gmm"
    GLOBAL_CONTROL_FUNCTION = "global_control_function"
    LOCAL_FUZZY_RD = "local_fuzzy_rd"
    LOCAL_FUZZY_RKD = "local_fuzzy_rkd"


class ThresholdSurfaceMode(str, Enum):
    """Describe how the state-dependent threshold surface was specified."""

    CONSTANT = "constant"
    AFFINE_STATE_FIXED = "affine_state_fixed"
    AFFINE_STATE_ESTIMATED = "affine_state_estimated"


class ThresholdScoreSummary(BaseModel):
    """Compact support summary for the normalized score R = Q - gamma(S)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_score: float
    max_score: float
    mean_score: float
    std_score: float = Field(ge=0.0)
    positive_share: float = Field(ge=0.0, le=1.0)
    support_within_window: int = Field(ge=0)
    window_half_width: float = Field(ge=0.0)


class ThresholdStateField(BaseModel):
    """Typed threshold/kink state payload carried by ``EconometricResult``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    regime_model: ThresholdEffectModel
    identification_mode: ThresholdIdentificationMode
    threshold_surface_mode: ThresholdSurfaceMode
    continuity_imposed: bool
    threshold_shift: float
    state_weights: tuple[float, ...] = ()
    state_variable_names: tuple[str, ...] = ()
    trim_fraction: float = Field(default=0.1, ge=0.0, lt=0.5)
    candidate_count: int = Field(ge=1)
    objective_value: float = Field(ge=0.0)
    regime_counts: dict[str, int] = Field(default_factory=dict)
    normalized_score: ThresholdScoreSummary
    threshold_variable_endogeneity_adjusted: bool = False
    control_function_order: int | None = Field(default=None, ge=1)
    first_stage_r_squared: float | None = Field(default=None, ge=0.0, le=1.0)
    first_stage_f_statistic: float | None = Field(default=None, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_state_payload(self) -> ThresholdStateField:
        for name, count in self.regime_counts.items():
            if int(count) < 0:
                raise ValueError(f"regime_counts.{name} must be non-negative")
        if self.state_variable_names and len(self.state_variable_names) != len(self.state_weights):
            raise ValueError("state_variable_names length must match state_weights length")
        return self


class ThresholdRegressionData(BaseModel):
    """Validated cross-sectional input for threshold and kink econometric models."""

    contract_id: ClassVar[str] = "foundry.econometrics.threshold_regression_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    dependent: Any  # shape: (n_obs,)
    exog: Any  # shape: (n_obs, n_features)
    running_variable: Any  # shape: (n_obs,)
    state_variables: Any | None = None  # shape: (n_obs, n_states)
    instruments: Any | None = None  # shape: (n_obs, n_instruments)
    treatment: Any | None = None  # shape: (n_obs,)
    policy_variable: Any | None = None  # shape: (n_obs,)
    cluster_ids: Any | None = None  # shape: (n_obs,)
    feature_names: list[str] | None = None
    state_names: list[str] | None = None
    instrument_names: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "dependent",
        "exog",
        "running_variable",
        "state_variables",
        "instruments",
        "treatment",
        "policy_variable",
        "cluster_ids",
        mode="before",
    )
    @classmethod
    def _coerce_threshold_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_threshold_shapes(self) -> ThresholdRegressionData:
        if not isinstance(self.dependent, np.ndarray) or self.dependent.ndim != 1:
            raise ValueError("dependent must be a 1D numpy array")
        if not isinstance(self.exog, np.ndarray) or self.exog.ndim != 2:
            raise ValueError("exog must be a 2D numpy array")
        if not isinstance(self.running_variable, np.ndarray) or self.running_variable.ndim != 1:
            raise ValueError("running_variable must be a 1D numpy array")

        n_obs = self.dependent.shape[0]
        if n_obs < 12:
            raise ValueError("threshold regression data requires at least 12 observations")
        if self.exog.shape[0] != n_obs:
            raise ValueError("exog row count must match dependent length")
        if self.running_variable.shape[0] != n_obs:
            raise ValueError("running_variable length must match dependent length")
        if self.exog.shape[1] < 1:
            raise ValueError("exog must contain at least one feature")

        if not np.isfinite(self.dependent).all():
            raise ValueError("dependent contains non-finite values")
        if not np.isfinite(self.exog).all():
            raise ValueError("exog contains non-finite values")
        if not np.isfinite(self.running_variable).all():
            raise ValueError("running_variable contains non-finite values")

        if self.state_variables is not None:
            if not isinstance(self.state_variables, np.ndarray) or self.state_variables.ndim != 2:
                raise ValueError("state_variables must be a 2D numpy array")
            if self.state_variables.shape[0] != n_obs:
                raise ValueError("state_variables row count must match dependent length")
            if not np.isfinite(self.state_variables).all():
                raise ValueError("state_variables contain non-finite values")
        if self.instruments is not None:
            if not isinstance(self.instruments, np.ndarray) or self.instruments.ndim != 2:
                raise ValueError("instruments must be a 2D numpy array")
            if self.instruments.shape[0] != n_obs:
                raise ValueError("instruments row count must match dependent length")
            if self.instruments.shape[1] < 1:
                raise ValueError("instruments must contain at least one instrument")
            if not np.isfinite(self.instruments).all():
                raise ValueError("instruments contain non-finite values")
        if self.treatment is not None:
            if not isinstance(self.treatment, np.ndarray) or self.treatment.ndim != 1:
                raise ValueError("treatment must be a 1D numpy array")
            if self.treatment.shape[0] != n_obs:
                raise ValueError("treatment length must match dependent length")
            if not np.isfinite(self.treatment).all():
                raise ValueError("treatment contains non-finite values")
        if self.policy_variable is not None:
            if not isinstance(self.policy_variable, np.ndarray) or self.policy_variable.ndim != 1:
                raise ValueError("policy_variable must be a 1D numpy array")
            if self.policy_variable.shape[0] != n_obs:
                raise ValueError("policy_variable length must match dependent length")
            if not np.isfinite(self.policy_variable).all():
                raise ValueError("policy_variable contains non-finite values")
        if self.cluster_ids is not None:
            if not isinstance(self.cluster_ids, np.ndarray) or self.cluster_ids.ndim != 1:
                raise ValueError("cluster_ids must be a 1D numpy array")
            if self.cluster_ids.shape[0] != n_obs:
                raise ValueError("cluster_ids length must match dependent length")

        if self.feature_names is not None and len(self.feature_names) != self.exog.shape[1]:
            raise ValueError("feature_names length must match exog column count")
        if self.state_variables is not None and self.state_names is not None:
            if len(self.state_names) != self.state_variables.shape[1]:
                raise ValueError("state_names length must match state_variables column count")
        if self.instruments is not None and self.instrument_names is not None:
            if len(self.instrument_names) != self.instruments.shape[1]:
                raise ValueError("instrument_names length must match instruments column count")

        return self

    @field_serializer(
        "dependent",
        "exog",
        "running_variable",
        "state_variables",
        "instruments",
        "treatment",
        "policy_variable",
        "cluster_ids",
        mode="plain",
        when_used="json",
    )
    def _serialize_threshold_numpy_fields(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @property
    def n_obs(self) -> int:
        return int(self.dependent.shape[0])

    @property
    def n_features(self) -> int:
        return int(self.exog.shape[1])

    @property
    def n_states(self) -> int:
        if self.state_variables is None:
            return 0
        return int(self.state_variables.shape[1])

    @property
    def n_instruments(self) -> int:
        if self.instruments is None:
            return 0
        return int(self.instruments.shape[1])

    @property
    def n_clusters(self) -> int | None:
        if self.cluster_ids is None:
            return None
        return int(np.unique(self.cluster_ids).shape[0])


CoverageGuaranteeTier = Literal[
    "NONE",
    "HEURISTIC_POST_SELECTION",
    "ORTHOGONAL_CROSSFIT",
    "WEAK_IV_ROBUST_SET",
]


class ConfidenceSetSegment(BaseModel):
    """Single contiguous segment of a confidence interval/set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lower: float
    upper: float

    @model_validator(mode="after")
    def _validate_bounds(self) -> ConfidenceSetSegment:
        if not np.isfinite(self.lower) or not np.isfinite(self.upper):
            raise ValueError("confidence-set segment bounds must be finite")
        if self.lower > self.upper:
            raise ValueError("confidence-set segment lower must be <= upper")
        return self


class PostSelectionInterval(BaseModel):
    """Typed post-selection interval/set bundle for one structural target."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    parameter: str
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    method_family: Literal[
        "post_selection_wald",
        "orthogonal_score_wald",
        "anderson_rubin_hc1",
        "clr_proxy",
        "set_inversion",
    ]
    semantics: Literal["confidence_interval", "confidence_set"] = "confidence_interval"
    segments: tuple[ConfidenceSetSegment, ...] = Field(default_factory=tuple)
    point_estimate: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_segments(self) -> PostSelectionInterval:
        if not self.parameter.strip():
            raise ValueError("parameter must be non-empty")
        previous_upper: float | None = None
        for segment in self.segments:
            if previous_upper is not None and segment.lower < previous_upper:
                raise ValueError("interval segments must be ordered and non-overlapping")
            previous_upper = float(segment.upper)
        if self.point_estimate is not None and not np.isfinite(self.point_estimate):
            raise ValueError("point_estimate must be finite")
        return self

    def convex_hull(self) -> tuple[float, float] | None:
        """Return the smallest contiguous interval covering all segments."""
        if not self.segments:
            return None
        return (float(self.segments[0].lower), float(self.segments[-1].upper))


class SparsityComplexityDiagnostic(BaseModel):
    """Operational proxy for approximate sparsity and complexity-adjusted sample size."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selected_controls_union: int = Field(ge=0)
    selected_instruments_union: int = Field(ge=0)
    complexity_ratio_controls: float = Field(ge=0.0)
    complexity_ratio_instruments: float = Field(ge=0.0)
    support_stability_controls: float | None = Field(default=None, ge=0.0, le=1.0)
    support_stability_instruments: float | None = Field(default=None, ge=0.0, le=1.0)
    passed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrthogonalityNuisanceDiagnostic(BaseModel):
    """Runtime proxy for orthogonal-score construction and nuisance estimation quality."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    score_type: Literal["none", "post_selection_wald", "partial_linear_iv_orthogonal"] = "none"
    cross_fitted: bool = False
    n_folds: int | None = Field(default=None, ge=2)
    orthogonality_score: float | None = None
    nuisance_rmse_y: float | None = Field(default=None, ge=0.0)
    nuisance_rmse_d: float | None = Field(default=None, ge=0.0)
    nuisance_rmse_z: float | None = Field(default=None, ge=0.0)
    product_rate_proxy: float | None = Field(default=None, ge=0.0)
    passed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_numeric_fields(self) -> OrthogonalityNuisanceDiagnostic:
        for field_name in (
            "orthogonality_score",
            "nuisance_rmse_y",
            "nuisance_rmse_d",
            "nuisance_rmse_z",
            "product_rate_proxy",
        ):
            value = getattr(self, field_name)
            if value is not None and not np.isfinite(value):
                raise ValueError(f"{field_name} must be finite")
        return self


class IdentificationDiagnostic(BaseModel):
    """Identification-strength payload used to gate high-dimensional IV coverage tiers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    weak_iv_test_family: Literal[
        "none",
        "robust_f_proxy",
        "montiel_olea_pflueger_proxy",
        "sanderson_windmeijer_proxy",
        "anderson_rubin_hc1",
        "clr_proxy",
    ] = "none"
    weak_iv_stat: float | None = None
    critical_value: float | None = None
    passed: bool = False
    many_instrument_flag: bool = False
    multiple_endogenous_flag: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_stat_fields(self) -> IdentificationDiagnostic:
        if self.weak_iv_stat is not None and not np.isfinite(self.weak_iv_stat):
            raise ValueError("weak_iv_stat must be finite")
        if self.critical_value is not None and not np.isfinite(self.critical_value):
            raise ValueError("critical_value must be finite")
        return self


class IntervalDisagreementDiagnostic(BaseModel):
    """Compare Wald-style post-selection intervals against weak-IV robust sets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    wald_ci: PostSelectionInterval | None = None
    weak_iv_robust_ci: PostSelectionInterval | None = None
    ci_disagreement_ratio: float | None = Field(default=None, ge=0.0)
    set_inversion_used: bool = False
    materially_different: bool | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_ratio(self) -> IntervalDisagreementDiagnostic:
        if self.ci_disagreement_ratio is not None and not np.isfinite(self.ci_disagreement_ratio):
            raise ValueError("ci_disagreement_ratio must be finite")
        return self


class PostSelectionCoverageDiagnostic(BaseModel):
    """Decision-relevant runtime diagnostics for post-selection/high-dimensional IV."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sample_size_requirement: str | None = None
    sparsity: SparsityComplexityDiagnostic | None = None
    orthogonality: OrthogonalityNuisanceDiagnostic | None = None
    identification: IdentificationDiagnostic | None = None
    interval_disagreement: IntervalDisagreementDiagnostic | None = None
    overall_gate_passed: bool = False
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    decision_notes: tuple[str, ...] = Field(default_factory=tuple)


class VolatilityBreakDetectionMethod(str, Enum):
    """Break-screening family used before segment-wise volatility estimation."""

    NONE = "none"
    BINSEG_LOG_VARIANCE = "binseg_log_variance"
    PELT_LOG_VARIANCE = "pelt_log_variance"


class VolatilityLossFamily(str, Enum):
    """Robustness mode used when fitting segment-wise volatility models."""

    GAUSSIAN_QML = "gaussian_qml"
    HUBER_PROXY = "huber_proxy"


class VolatilityRegimeSegment(BaseModel):
    """One group-specific finite regime recovered by the nonstationary volatility workflow."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_label: str
    segment_index: int = Field(ge=0)
    start_index: int = Field(ge=0)
    end_index: int = Field(ge=0)
    start_time_id: str | int | float | None = None
    end_time_id: str | int | float | None = None
    n_entities: int = Field(ge=1)
    n_obs: int = Field(ge=1)
    params: dict[str, float] = Field(default_factory=dict)
    persistence: float | None = None
    mean_conditional_volatility: float | None = Field(default=None, ge=0.0)
    variance_covariate_proxy_effects: dict[str, float] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_segment_payload(self) -> VolatilityRegimeSegment:
        if self.end_index < self.start_index:
            raise ValueError("end_index must be >= start_index")
        for bucket_name, bucket in (
            ("params", self.params),
            ("variance_covariate_proxy_effects", self.variance_covariate_proxy_effects),
        ):
            for key, value in bucket.items():
                if not np.isfinite(value):
                    raise ValueError(f"{bucket_name}.{key} must be finite")
        if self.persistence is not None and not np.isfinite(self.persistence):
            raise ValueError("persistence must be finite when provided")
        return self


class VolatilityBreak(BaseModel):
    """Machine-readable break date summary for one policy-relevant group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_label: str
    breakpoint_index: int = Field(ge=1)
    breakpoint_time_id: str | int | float | None = None
    detection_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_break_payload(self) -> VolatilityBreak:
        if self.detection_score is not None and not np.isfinite(self.detection_score):
            raise ValueError("detection_score must be finite when provided")
        return self


class VolatilityCoverageSummary(BaseModel):
    """Coverage-first diagnostics attached to nonstationary volatility outputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary_nominal_coverage: float = Field(gt=0.0, lt=1.0)
    empirical_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    ece: float | None = Field(default=None, ge=0.0)
    max_calibration_error: float | None = Field(default=None, ge=0.0)
    conditional_coverage_pvalue: float | None = Field(default=None, ge=0.0, le=1.0)
    independence_pvalue: float | None = Field(default=None, ge=0.0, le=1.0)
    sample_count: int = Field(ge=0)
    recommended_action: str | None = None
    diagnostic_levels: tuple[float, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_diagnostic_levels(self) -> VolatilityCoverageSummary:
        for level in self.diagnostic_levels:
            if not 0.0 < float(level) < 1.0:
                raise ValueError("diagnostic_levels must stay inside (0, 1)")
        return self


class NonstationaryVolatilitySummary(BaseModel):
    """Typed Phase-2 payload for grouped structural-break volatility estimates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    grouping_strategy: str
    break_detection_method: VolatilityBreakDetectionMethod
    loss_family: VolatilityLossFamily
    distribution: str
    n_groups: int = Field(ge=1)
    n_regimes: int = Field(ge=1)
    breaks: tuple[VolatilityBreak, ...] = ()
    segments: tuple[VolatilityRegimeSegment, ...] = ()
    coverage: VolatilityCoverageSummary | None = None
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_summary_counts(self) -> NonstationaryVolatilitySummary:
        if self.segments and self.n_regimes < len(self.segments):
            raise ValueError("n_regimes must be >= the number of segment records")
        return self


class EconometricResult(BaseModel):
    """Common output contract for econometric methods."""

    contract_id: ClassVar[str] = "foundry.econometrics.result.v2"
    output_contract_declaration: ClassVar[OutputContractDeclaration] = (
        value_uncertainty_output_contract(
            contract_id,
            projection_kind=ValueUncertaintyProjectionKind.ECONOMETRIC,
        )
    )
    model_config = ConfigDict(extra="forbid", frozen=True)

    method_name: str
    params: dict[str, float] = Field(default_factory=dict)
    std_errors: dict[str, float] = Field(default_factory=dict)
    t_stats: dict[str, float] = Field(default_factory=dict)
    p_values: dict[str, float] = Field(default_factory=dict)
    confidence_intervals: dict[str, tuple[float, float]] = Field(default_factory=dict)
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    coverage_guarantee_tier: CoverageGuaranteeTier | None = None
    coverage_diagnostic: PostSelectionCoverageDiagnostic | None = None
    post_selection_ci: dict[str, PostSelectionInterval] = Field(default_factory=dict)
    weak_iv_robust_ci: dict[str, PostSelectionInterval] = Field(default_factory=dict)

    r_squared: float | None = None
    adj_r_squared: float | None = None
    f_statistic: float | None = None
    f_pvalue: float | None = None
    n_obs: int = 0
    n_entities: int | None = None
    n_periods: int | None = None

    diagnostics: dict[str, Any] = Field(default_factory=dict)
    model_info: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    threshold_state_field: ThresholdStateField | None = None
    nonstationary_volatility: NonstationaryVolatilitySummary | None = None
    dependence_ref: DependenceStructureRef | None = None
    cross_sectional_dependence_diagnostic: CrossSectionalDependenceDiagnostic | None = None

    @model_validator(mode="after")
    def _validate_numerics(self) -> EconometricResult:
        for bucket_name, bucket in (
            ("params", self.params),
            ("std_errors", self.std_errors),
            ("t_stats", self.t_stats),
            ("p_values", self.p_values),
        ):
            for key, value in bucket.items():
                if not np.isfinite(value):
                    raise ValueError(f"{bucket_name}.{key} must be finite")

        for key, interval in self.confidence_intervals.items():
            lo, hi = interval
            if not np.isfinite(lo) or not np.isfinite(hi):
                raise ValueError(f"confidence_intervals.{key} must be finite")
            if lo > hi:
                raise ValueError(f"confidence_intervals.{key} lower must be <= upper")

        for bucket_name, bucket in (
            ("post_selection_ci", self.post_selection_ci),
            ("weak_iv_robust_ci", self.weak_iv_robust_ci),
        ):
            for key, interval in bucket.items():
                if interval.parameter != key:
                    raise ValueError(f"{bucket_name}.{key} parameter must match dictionary key")

        return self

    def to_uncertainty_envelope(
        self,
        param_name: str | None = None,
    ) -> UncertaintyEnvelope | None:
        if not self.params:
            return None

        name = param_name
        if name is None:
            non_const = [candidate for candidate in self.params if candidate.lower() != "const"]
            name = non_const[0] if non_const else next(iter(self.params))
        if name not in self.params:
            return None

        point = float(self.params[name])
        interval = self.confidence_intervals.get(name)
        interval_source = "confidence_intervals"
        interval_hull_only = False

        if self.coverage_guarantee_tier == "WEAK_IV_ROBUST_SET":
            weak_interval = self.weak_iv_robust_ci.get(name)
            if weak_interval is not None:
                resolved = weak_interval.convex_hull()
                if resolved is not None:
                    interval = resolved
                    interval_source = "weak_iv_robust_ci"
                    interval_hull_only = len(weak_interval.segments) > 1

        if interval is None:
            post_selection_interval = self.post_selection_ci.get(name)
            if post_selection_interval is not None:
                resolved = post_selection_interval.convex_hull()
                if resolved is not None:
                    interval = resolved
                    interval_source = "post_selection_ci"
                    interval_hull_only = len(post_selection_interval.segments) > 1

        if interval is None:
            if self.coverage_guarantee_tier == "NONE":
                return None
            se = self.std_errors.get(name)
            if se is None or se <= _FLOAT_EPS:
                return None
            z = NormalDist().inv_cdf((1.0 + self.confidence_level) / 2.0)
            interval = (point - z * se, point + z * se)

        lo, hi = float(interval[0]), float(interval[1])
        if lo > hi:
            lo, hi = hi, lo
        if point < lo:
            lo = point
        if point > hi:
            hi = point

        tier = self.coverage_guarantee_tier
        is_heuristic_ci = (
            tier in {"HEURISTIC_POST_SELECTION", "NONE"} if tier is not None else False
        )
        gate_eligible = (
            tier not in {"HEURISTIC_POST_SELECTION", "NONE"} if tier is not None else True
        )

        return UncertaintyEnvelope(
            point_estimate=point,
            confidence_interval=(lo, hi),
            confidence_level=self.confidence_level,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.CAUSAL,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            sample_size=self.n_obs if self.n_obs > 0 else None,
            is_heuristic_ci=is_heuristic_ci,
            gate_eligible=gate_eligible,
            metadata={
                "econometric_method": self.method_name,
                "param_name": name,
                "r_squared": self.r_squared,
                "std_error": self.std_errors.get(name),
                "p_value": self.p_values.get(name),
                "coverage_guarantee_tier": tier,
                "interval_source": interval_source,
                "interval_hull_only": interval_hull_only,
            },
        )

    def to_value_uncertainty(
        self,
        *,
        estimand: object,
        projection_binding: NativeValueEstimandBinding,
    ) -> UncertaintyEnvelope | None:
        """Project only the exact coefficient named by the requested value estimand."""

        estimand_id = getattr(estimand, "estimand_id", None)
        if not isinstance(estimand_id, str) or not estimand_id:
            return None
        if (
            projection_binding.native_contract_id != self.contract_id
            or not projection_binding.matches(estimand)
        ):
            return None
        envelope = self.to_uncertainty_envelope(param_name=estimand_id)
        if envelope is None:
            return None
        return envelope.model_copy(
            update={
                "metadata": {
                    **envelope.metadata,
                    "value_estimand_binding_content_hash": (
                        projection_binding.content_hash
                    ),
                    "value_estimand_binding_native_contract_id": (
                        projection_binding.native_contract_id
                    ),
                    "value_estimand_binding_producer_method_fqn": (
                        projection_binding.producer_method_fqn
                    ),
                }
            }
        )

    def to_consensus_target(self, query: Any) -> Any:
        """Expose this econometric result on the canonical cross-method consensus surface."""

        from polisyos.foundry.methods.components.consensus import target_from_econometric_result

        return target_from_econometric_result(self, query)


class EconometricDiagnosticResult(BaseModel):
    """Common diagnostic-test payload for econometric methods."""

    contract_id: ClassVar[str] = "foundry.econometrics.diagnostic_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True)

    test_name: str
    statistic: float | None = None
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    passed: bool
    critical_value: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CrossSectionalDependenceDiagnostic(BaseModel):
    """Typed cross-sectional dependence routing payload shared across econometric panel workflows."""

    contract_id: ClassVar[str] = "foundry.econometrics.cross_sectional_dependence_diagnostic.v1"
    model_config = ConfigDict(extra="forbid", frozen=True)

    detected: bool
    class_label: Literal[
        "none",
        "weak_or_none",
        "common_shock_removed",
        "block",
        "spatial_local",
        "network_local",
        "factor",
        "mixed",
        "inconclusive",
    ]
    strength: Literal["none", "weak", "strong", "unknown"]
    estimator_status: Literal[
        "ok",
        "ok_conservative",
        "reroute_required",
        "unsafe_for_default_inference",
    ]
    recommended_covariance: Literal[
        "windmeijer",
        "double_corrected_gmm",
        "cluster",
        "multiway_cluster",
        "fixed_g_cluster",
        "conley_spatial_hac",
        "spatial_windmeijer",
        "network_hac",
        "cce_reroute",
        "dynamic_spatial_network_gmm_reroute",
        "none",
    ]
    tests: list[EconometricDiagnosticResult] = Field(default_factory=list)
    factor_count: int | None = Field(default=None, ge=0)
    alpha_hat: float | None = None
    alpha_ci: tuple[float, float] | None = None
    used_time_dummies: bool = False
    dependence_removed_by_time_effects: bool | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    shared_artifacts_ref: str | None = None

    @model_validator(mode="after")
    def _validate_numeric_ranges(self) -> CrossSectionalDependenceDiagnostic:
        if self.alpha_hat is not None and not np.isfinite(self.alpha_hat):
            raise ValueError("alpha_hat must be finite")
        if self.alpha_ci is not None:
            lo, hi = self.alpha_ci
            if not np.isfinite(lo) or not np.isfinite(hi):
                raise ValueError("alpha_ci must be finite")
            if lo > hi:
                raise ValueError("alpha_ci lower must be <= upper")
        return self


@runtime_checkable
class EconometricEstimator(Protocol):
    """Declare the protocol shared by econometric estimators returning `EconometricResult` payloads."""

    signature: ClassVar[MethodSignature]
    metadata: ClassVar[MethodMetadata]

    @staticmethod
    def pure_step(
        state: PanelData | TimeSeriesData | ThresholdRegressionData,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        """
        Expected output keys:
        - result: EconometricResult
        - envelope: UncertaintyEnvelope | None
        """
        ...


__all__ = [
    "ConfidenceSetSegment",
    "CoverageGuaranteeTier",
    "CrossSectionalDependenceDiagnostic",
    "EconometricDiagnosticResult",
    "EconometricEstimator",
    "EconometricResult",
    "IdentificationDiagnostic",
    "IntervalDisagreementDiagnostic",
    "NonstationaryVolatilitySummary",
    "OrthogonalityNuisanceDiagnostic",
    "PanelData",
    "PostSelectionCoverageDiagnostic",
    "PostSelectionInterval",
    "SparsityComplexityDiagnostic",
    "ThresholdEffectModel",
    "ThresholdIdentificationMode",
    "ThresholdRegressionData",
    "ThresholdScoreSummary",
    "ThresholdStateField",
    "ThresholdSurfaceMode",
    "TimeSeriesData",
    "VolatilityBreak",
    "VolatilityBreakDetectionMethod",
    "VolatilityCoverageSummary",
    "VolatilityLossFamily",
    "VolatilityRegimeSegment",
]
