"""Define ML catalog input/output contracts for tabular, clustering, embedding, and survival tasks."""
from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

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
    def _validate_shapes(self) -> "TabularData":
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
    def _validate_shapes(self) -> "SurvivalData":
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
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("predictions", "target", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "PredictionResult":
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
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("predictions", "lower", "upper", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        return _to_numpy(value)

    @field_serializer("predictions", "lower", "upper", mode="plain", when_used="json")
    def _serialize_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


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
    "ClusteringResult",
    "EmbeddingResult",
    "PredictionIntervalResult",
    "PredictionResult",
    "SurvivalData",
    "SurvivalResult",
    "TabularData",
]
