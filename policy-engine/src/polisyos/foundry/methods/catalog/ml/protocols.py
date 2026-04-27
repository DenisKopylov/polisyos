"""Define ML catalog input/output contracts for tabular, clustering, embedding, and survival tasks."""

from __future__ import annotations

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

from polisyos.core.observability.truthfulness import (
    TruthfulnessReceipt,
    validate_truthfulness_receipt,
)
from polisyos.ir.analytics.network_embedding import NetworkEmbeddingFidelityCertificate
from polisyos.ir.analytics.shift_diagnostics import (
    ReadinessBand,
    ShiftDiagnosticReport,
    readiness_after_downgrade,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


def _to_numpy(value: Any) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value
    return np.asarray(value)


class TabularData(BaseModel):
    """Carry tabular features, optional targets, feature names, and sample IDs."""

    contract_id: ClassVar[str] = "foundry.ml.tabular_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    features: Any
    target: Any | None = None
    sample_weight: Any | None = None
    feature_names: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("features", "target", "sample_weight", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> TabularData:
        if not isinstance(self.features, np.ndarray) or self.features.ndim != 2:
            raise ValueError("features must be a 2D numpy array")
        if self.features.shape[0] < 4:
            raise ValueError("tabular data requires at least 4 rows")
        if self.target is not None:
            if not isinstance(self.target, np.ndarray) or self.target.ndim != 1:
                raise ValueError("target must be a 1D numpy array")
            if self.target.shape[0] != self.features.shape[0]:
                raise ValueError("target length must match feature rows")
        if self.sample_weight is not None:
            if not isinstance(self.sample_weight, np.ndarray) or self.sample_weight.ndim != 1:
                raise ValueError("sample_weight must be a 1D numpy array")
            if self.sample_weight.shape[0] != self.features.shape[0]:
                raise ValueError("sample_weight length must match feature rows")
        if self.feature_names is not None and len(self.feature_names) != self.features.shape[1]:
            raise ValueError("feature_names length must match feature columns")
        return self

    @field_serializer("features", "target", "sample_weight", mode="plain", when_used="json")
    def _serialize_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class SurvivalData(BaseModel):
    """Carry survival durations, event indicators, and covariates for hazard/time-to-event models."""

    contract_id: ClassVar[str] = "foundry.ml.survival_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    features: Any
    durations: Any
    events: Any
    feature_names: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("features", "durations", "events", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> SurvivalData:
        if not isinstance(self.features, np.ndarray) or self.features.ndim != 2:
            raise ValueError("features must be a 2D numpy array")
        if not isinstance(self.durations, np.ndarray) or self.durations.ndim != 1:
            raise ValueError("durations must be a 1D numpy array")
        if not isinstance(self.events, np.ndarray) or self.events.ndim != 1:
            raise ValueError("events must be a 1D numpy array")
        n_obs = self.features.shape[0]
        if self.durations.shape[0] != n_obs or self.events.shape[0] != n_obs:
            raise ValueError("durations/events must match feature rows")
        if self.feature_names is not None and len(self.feature_names) != self.features.shape[1]:
            raise ValueError("feature_names length must match feature columns")
        return self

    @field_serializer("features", "durations", "events", mode="plain", when_used="json")
    def _serialize_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class PredictionResult(BaseModel):
    """Store point predictions, observed targets, metrics, and model metadata."""

    contract_id: ClassVar[str] = "foundry.ml.prediction_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    method_name: str
    predictions: Any
    target: Any | None = None
    feature_importances: dict[str, float] = Field(default_factory=dict)
    coefficients: dict[str, float] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    model_info: dict[str, Any] = Field(default_factory=dict)
    embedding_fidelity_certificate: NetworkEmbeddingFidelityCertificate | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("predictions", "target", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> PredictionResult:
        if not isinstance(self.predictions, np.ndarray) or self.predictions.ndim != 1:
            raise ValueError("predictions must be a 1D numpy array")
        if self.target is not None:
            if not isinstance(self.target, np.ndarray) or self.target.ndim != 1:
                raise ValueError("target must be a 1D numpy array")
            if self.target.shape[0] != self.predictions.shape[0]:
                raise ValueError("target length must match predictions")
        return self

    @field_serializer("predictions", "target", mode="plain", when_used="json")
    def _serialize_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    def to_uncertainty_envelope(self) -> UncertaintyEnvelope | None:
        if self.target is None or self.predictions.shape[0] < 2:
            return None
        residual = np.asarray(self.target) - np.asarray(self.predictions)
        center = float(np.mean(residual))
        spread = float(np.std(residual, ddof=1)) if residual.shape[0] > 1 else 0.0
        lower = center - 1.96 * spread
        upper = center + 1.96 * spread
        if lower > upper:
            lower, upper = upper, lower
        return UncertaintyEnvelope(
            point_estimate=center,
            confidence_interval=(lower, upper),
            confidence_level=0.95,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            sample_size=int(self.predictions.shape[0]),
            metadata={"method_name": self.method_name, "metrics": dict(self.metrics)},
        )

    def to_consensus_target(self, query: Any) -> Any:
        """Expose this prediction on the canonical cross-method consensus surface."""

        from polisyos.foundry.methods.consensus import target_from_prediction_result

        return target_from_prediction_result(self, query)


class PredictionResultConsumerInput(BaseModel):
    """Bundle prediction output with the optional Phase-5 shift report."""

    contract_id: ClassVar[str] = "foundry.ml.prediction_result_consumer_input.v1"
    model_config = ConfigDict(extra="forbid", frozen=True)

    prediction_result_id: str
    prediction_result_payload: dict[str, Any]
    shift_diagnostic_report: ShiftDiagnosticReport | None = None
    base_readiness: ReadinessBand = "ready"
    high_stakes: bool = False
    externally_deployed: bool = False

    def resulting_readiness(self) -> ReadinessBand:
        """Return the readiness band the consumer must enforce."""

        if self.shift_diagnostic_report is not None:
            return self.shift_diagnostic_report.readiness_impact.resulting_readiness
        if self.high_stakes or self.externally_deployed:
            return readiness_after_downgrade(self.base_readiness, 1)
        return self.base_readiness

    def refuses_automated_action(self) -> bool:
        """True when automated decisions must be refused."""

        return self.resulting_readiness() == "blocked"

    def audit_shift_report_id(self) -> str | None:
        """Return the attached report id that downstream audit logs should persist."""

        if self.shift_diagnostic_report is None:
            return None
        return self.shift_diagnostic_report.report_id


class ConformalMethodSpec(BaseModel):
    """Describe the conformal method and the precise scope of its coverage claim."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    family: Literal[
        "split_residual",
        "normalized_residual",
        "cqr",
        "mondrian_cqr",
        "weighted_cqr",
        "mondrian_normalized_residual",
        "aps",
        "raps",
        "mondrian_aps",
        "mondrian_raps",
        "clustered_class_conditional",
        "graph_aps",
        "graph_raps",
        "graph_cf_gnn",
        "graph_daps",
        "graph_snaps",
        "empirical_interval",
    ]
    base_model_family: str
    guarantee_scope: list[
        Literal[
            "marginal",
            "group_conditional",
            "class_conditional",
            "finite_shift_class",
            "local_asymptotic",
            "empirical_only",
        ]
    ] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    calibration_size: int = Field(ge=0)
    calibration_timestamp: str | None = None
    calibration_data_hash: str | None = None


class CoverageEstimate(BaseModel):
    """Empirical coverage estimate with a finite-sample confidence interval."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    n: int = Field(ge=0)
    covered: int = Field(ge=0)
    coverage: float = Field(ge=0.0, le=1.0)
    ci_low: float = Field(ge=0.0, le=1.0)
    ci_high: float = Field(ge=0.0, le=1.0)
    method: Literal["wilson", "exact_binomial", "bootstrap"] = "wilson"


class GroupCoverageEstimate(BaseModel):
    """Coverage and support diagnostics for one calibration or evaluation group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_key: str
    group_value: str
    n_calibration: int = Field(ge=0)
    n_evaluation: int | None = Field(default=None, ge=0)
    coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    ci_low: float | None = Field(default=None, ge=0.0, le=1.0)
    ci_high: float | None = Field(default=None, ge=0.0, le=1.0)
    median_width: float | None = Field(default=None, ge=0.0)
    p90_width: float | None = Field(default=None, ge=0.0)
    shortfall: float | None = Field(default=None, ge=0.0)
    guarantee_supported: bool = False
    support_status: Literal["ok", "low_n", "low_ess", "unseen_group"] = "low_n"


class ERTDiagnostic(BaseModel):
    """Classifier-based local coverage diagnostic for delayed outcome labels."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evaluated: bool
    n_splits: int = Field(ge=0)
    feature_set: list[str] = Field(default_factory=list)
    classifier_family: str
    ert_l1: float | None = Field(default=None, ge=0.0)
    ert_l2: float | None = Field(default=None, ge=0.0)
    ert_under: float | None = Field(default=None, ge=0.0)
    ert_over: float | None = Field(default=None, ge=0.0)
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    status: Literal["pass", "warn", "fail", "not_enough_labels"]


class ShiftDiagnostic(BaseModel):
    """Covariate-shift support checks for weighted conformal calibration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evaluated: bool
    calibration_vs_deployment_auc: float | None = Field(default=None, ge=0.0, le=1.0)
    psi_max: float | None = None
    mmd: float | None = None
    density_ratio_ess: float | None = Field(default=None, ge=0.0)
    density_ratio_ess_by_group: dict[str, float] = Field(default_factory=dict)
    unseen_category_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    status: Literal["pass", "warn", "fail", "not_available"]


class ScoreTailDiagnostic(BaseModel):
    """Heavy-tail and interval-vacuity diagnostics for conformal scores."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    score_q50: float
    score_q90: float
    score_q95: float
    score_q99: float
    q99_q90_ratio: float
    hill_tail_index: float | None = None
    vacuity_rate: float = Field(ge=0.0, le=1.0)
    median_interval_width: float = Field(ge=0.0)
    p90_interval_width: float = Field(ge=0.0)
    status: Literal["pass", "warn", "fail"]


class CalibrationSupportDiagnostic(BaseModel):
    """Report whether calibration support is sufficient for the requested groups."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    n_calibration_total: int = Field(ge=0)
    min_group_calibration_n: int = Field(ge=0)
    min_group_weighted_ess: float | None = Field(default=None, ge=0.0)
    groups_below_min_support: list[str] = Field(default_factory=list)
    unsupported_groups_seen: list[str] = Field(default_factory=list)
    status: Literal["pass", "warn", "fail"]


class GraphCoverageDiagnostic(BaseModel):
    """Graph-specific conditional coverage diagnostics for node, edge, or graph outputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    graph_id: str | None = None
    node_or_graph_level: Literal["node", "edge", "graph"]
    degree_bin_coverage: list[GroupCoverageEstimate] = Field(default_factory=list)
    community_coverage: list[GroupCoverageEstimate] = Field(default_factory=list)
    homophily_bin_coverage: list[GroupCoverageEstimate] = Field(default_factory=list)
    temporal_bin_coverage: list[GroupCoverageEstimate] = Field(default_factory=list)
    block_bootstrap_ci_used: bool = False
    effective_sample_size: int | None = Field(default=None, ge=0)
    exchangeability_proxy_status: Literal["pass", "warn", "fail", "not_applicable"]


class ConditionalCoverageDiagnostic(BaseModel):
    """Combined Phase 5 diagnostic for group, local, shift, and support-aware coverage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["pass", "warn", "fail", "unsupported", "pending_outcomes"]
    target_coverage: float = Field(ge=0.0, le=1.0)
    alpha: float = Field(ge=0.0, le=1.0)

    method_spec: ConformalMethodSpec
    marginal: CoverageEstimate | None = None
    groups: list[GroupCoverageEstimate] = Field(default_factory=list)

    ert: ERTDiagnostic | None = None
    shift: ShiftDiagnostic | None = None
    score_tail: ScoreTailDiagnostic | None = None
    calibration_support: CalibrationSupportDiagnostic
    graph: GraphCoverageDiagnostic | None = None

    failure_modes: list[str] = Field(default_factory=list)
    recommended_action: Literal[
        "accept",
        "collect_more_calibration_data",
        "switch_to_mondrian",
        "switch_to_cqr",
        "enable_weighted_conformal",
        "pool_or_cluster_groups",
        "fallback_to_classical_model",
        "human_review_or_abstain",
        "retrain_base_model",
    ] = "accept"


class PredictionIntervalResult(BaseModel):
    """Store prediction bands, coverage, and metadata emitted by interval-producing ML methods."""

    contract_id: ClassVar[str] = "foundry.ml.prediction_interval_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    method_name: str
    predictions: Any
    lower: Any
    upper: Any
    coverage: float | None = None
    alpha: float = Field(default=0.1, ge=0.0, le=1.0)
    conditional_coverage_diagnostic: ConditionalCoverageDiagnostic | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    truthfulness_receipt: TruthfulnessReceipt | None = None

    @field_validator("conditional_coverage_diagnostic", mode="before")
    @classmethod
    def _coerce_conditional_diagnostic(cls, value: Any) -> Any:
        if value is None or isinstance(value, ConditionalCoverageDiagnostic):
            return value
        if isinstance(value, dict):
            return ConditionalCoverageDiagnostic.model_validate(value)
        return value

    @field_validator("predictions", "lower", "upper", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        return _to_numpy(value)

    @field_serializer("predictions", "lower", "upper", mode="plain", when_used="json")
    def _serialize_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    def to_truthfulness_receipt(self) -> TruthfulnessReceipt | None:
        if self.truthfulness_receipt is not None:
            return self.truthfulness_receipt
        candidate = self.metadata.get("truthfulness_receipt")
        if candidate is not None:
            return validate_truthfulness_receipt(candidate)
        return None


class PredictionSetResult(BaseModel):
    """Store conformal classification sets, coverage, and Phase 5 diagnostics."""

    contract_id: ClassVar[str] = "foundry.ml.prediction_set_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    method_name: str
    class_probabilities: Any
    prediction_sets: list[list[int]]
    set_sizes: Any
    predicted_labels: Any
    target: Any | None = None
    coverage: float | None = None
    alpha: float = Field(default=0.1, ge=0.0, le=1.0)
    conditional_coverage_diagnostic: ConditionalCoverageDiagnostic | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    truthfulness_receipt: TruthfulnessReceipt | None = None

    @field_validator("conditional_coverage_diagnostic", mode="before")
    @classmethod
    def _coerce_conditional_diagnostic(cls, value: Any) -> Any:
        if value is None or isinstance(value, ConditionalCoverageDiagnostic):
            return value
        if isinstance(value, dict):
            return ConditionalCoverageDiagnostic.model_validate(value)
        return value

    @field_validator("class_probabilities", "set_sizes", "predicted_labels", "target", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> PredictionSetResult:
        probabilities = np.asarray(self.class_probabilities)
        if probabilities.ndim != 2:
            raise ValueError("class_probabilities must be a 2D array")
        n_obs = probabilities.shape[0]
        if len(self.prediction_sets) != n_obs:
            raise ValueError("prediction_sets length must match probability rows")
        if np.asarray(self.set_sizes).shape != (n_obs,):
            raise ValueError("set_sizes must match probability rows")
        if np.asarray(self.predicted_labels).shape != (n_obs,):
            raise ValueError("predicted_labels must match probability rows")
        if self.target is not None and np.asarray(self.target).shape != (n_obs,):
            raise ValueError("target must match probability rows")
        return self

    @field_serializer(
        "class_probabilities",
        "set_sizes",
        "predicted_labels",
        "target",
        mode="plain",
        when_used="json",
    )
    def _serialize_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    def to_truthfulness_receipt(self) -> TruthfulnessReceipt | None:
        if self.truthfulness_receipt is not None:
            return self.truthfulness_receipt
        candidate = self.metadata.get("truthfulness_receipt")
        if candidate is not None:
            return validate_truthfulness_receipt(candidate)
        return None


class ClusteringResult(BaseModel):
    """Store cluster labels, centroids, scores, and clustering metadata."""

    contract_id: ClassVar[str] = "foundry.ml.clustering_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    method_name: str
    labels: Any
    centers: Any | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("labels", "centers", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @field_serializer("labels", "centers", mode="plain", when_used="json")
    def _serialize_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class EmbeddingResult(BaseModel):
    """Store low-dimensional embeddings, explained variance, and transformer metadata."""

    contract_id: ClassVar[str] = "foundry.ml.embedding_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    method_name: str
    transformed: Any
    components: Any | None = None
    explained_variance_ratio: list[float] = Field(default_factory=list)
    embedding_fidelity_certificate: NetworkEmbeddingFidelityCertificate | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("transformed", "components", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @field_serializer("transformed", "components", mode="plain", when_used="json")
    def _serialize_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class SurvivalResult(BaseModel):
    """Store survival curves, risk scores, concordance metrics, and hazard-model metadata."""

    contract_id: ClassVar[str] = "foundry.ml.survival_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    method_name: str
    risk_scores: Any
    concordance_index: float | None = None
    coefficients: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("risk_scores", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        return _to_numpy(value)

    @field_serializer("risk_scores", mode="plain", when_used="json")
    def _serialize_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


__all__ = [
    "CalibrationSupportDiagnostic",
    "ClusteringResult",
    "ConditionalCoverageDiagnostic",
    "ConformalMethodSpec",
    "CoverageEstimate",
    "EmbeddingResult",
    "ERTDiagnostic",
    "GraphCoverageDiagnostic",
    "GroupCoverageEstimate",
    "PredictionIntervalResult",
    "PredictionResult",
    "PredictionResultConsumerInput",
    "PredictionSetResult",
    "ScoreTailDiagnostic",
    "ShiftDiagnostic",
    "SurvivalData",
    "SurvivalResult",
    "TabularData",
]
