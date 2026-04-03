"""Public microsim protocols module API."""
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


class SurveyMicroData(BaseModel):
    """Survey micro data public type."""
    contract_id: ClassVar[str] = "foundry.microsim.survey_micro_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    market_income: Any
    weights: Any
    household_ids: Any | None = None
    features: Any | None = None
    feature_names: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("market_income", "weights", "household_ids", "features", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "SurveyMicroData":
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
        return self

    @field_serializer("market_income", "weights", "household_ids", "features", mode="plain", when_used="json")
    def _serialize_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class MicrosimResult(BaseModel):
    """Microsim result data model."""
    contract_id: ClassVar[str] = "foundry.microsim.result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    disposable_income: Any
    tax_liability: Any
    benefit_income: Any
    weighted_mean_disposable_income: float
    weighted_gini: float
    policy_revenue: float
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("disposable_income", "tax_liability", "benefit_income", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        return _to_numpy(value)

    @field_serializer("disposable_income", "tax_liability", "benefit_income", mode="plain", when_used="json")
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


class ReweightingResult(BaseModel):
    """Reweighting result data model."""
    contract_id: ClassVar[str] = "foundry.microsim.reweighting_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    calibrated_weights: Any
    target_moments: dict[str, float] = Field(default_factory=dict)
    achieved_moments: dict[str, float] = Field(default_factory=dict)
    max_abs_gap: float
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
    """Tax benefit result data model."""
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
    """Behavioral response result data model."""
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

    @field_serializer("adjusted_market_income", "labor_supply_change", mode="plain", when_used="json")
    def _serialize_behavioral_vector(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    def to_uncertainty_envelope(self) -> UncertaintyEnvelope:
        point = float(self.weighted_mean_income)
        return UncertaintyEnvelope(
            point_estimate=point,
            confidence_interval=(point, point),
            confidence_level=None,
            distribution_family=DistributionFamily.UNKNOWN,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
            metadata={"elasticity": self.elasticity},
        )


class ImputationResult(BaseModel):
    """Imputation result data model."""
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


class DynamicMicrosimResult(BaseModel):
    """Dynamic microsim result data model."""
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
    "ImputationResult",
    "MicrosimResult",
    "ReweightingResult",
    "SurveyMicroData",
    "TaxBenefitResult",
]
