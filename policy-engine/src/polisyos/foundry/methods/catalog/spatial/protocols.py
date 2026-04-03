"""Public spatial protocols module API."""
from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator


def _to_numpy(value: Any) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value
    return np.asarray(value)


class SpatialData(BaseModel):
    """Spatial data public type."""
    contract_id: ClassVar[str] = "foundry.spatial.data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    coordinates: Any
    values: Any | None = None
    features: Any | None = None
    weights_matrix: Any | None = None
    feature_names: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("coordinates", "values", "features", "weights_matrix", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "SpatialData":
        if not isinstance(self.coordinates, np.ndarray) or self.coordinates.ndim != 2:
            raise ValueError("coordinates must be a 2D numpy array")
        n_obs = self.coordinates.shape[0]
        if n_obs < 3:
            raise ValueError("spatial data requires at least 3 observations")
        if self.values is not None:
            if not isinstance(self.values, np.ndarray) or self.values.ndim != 1:
                raise ValueError("values must be a 1D numpy array")
            if self.values.shape[0] != n_obs:
                raise ValueError("values length must match coordinates rows")
        if self.features is not None:
            if not isinstance(self.features, np.ndarray) or self.features.ndim != 2:
                raise ValueError("features must be a 2D numpy array")
            if self.features.shape[0] != n_obs:
                raise ValueError("features rows must match coordinates rows")
            if self.feature_names is not None and len(self.feature_names) != self.features.shape[1]:
                raise ValueError("feature_names length must match feature columns")
        if self.weights_matrix is not None:
            if not isinstance(self.weights_matrix, np.ndarray) or self.weights_matrix.ndim != 2:
                raise ValueError("weights_matrix must be a 2D numpy array")
            if self.weights_matrix.shape != (n_obs, n_obs):
                raise ValueError("weights_matrix must be square and match coordinates rows")
        return self

    @field_serializer("coordinates", "values", "features", "weights_matrix", mode="plain", when_used="json")
    def _serialize_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class GravityFlowData(BaseModel):
    """Gravity flow data public type."""
    contract_id: ClassVar[str] = "foundry.spatial.gravity_flow_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    origin_coords: Any
    destination_coords: Any
    origin_mass: Any
    destination_mass: Any
    observed_flows: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "origin_coords",
        "destination_coords",
        "origin_mass",
        "destination_mass",
        "observed_flows",
        mode="before",
    )
    @classmethod
    def _coerce_gravity_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_gravity_shapes(self) -> "GravityFlowData":
        if not isinstance(self.origin_coords, np.ndarray) or self.origin_coords.ndim != 2:
            raise ValueError("origin_coords must be a 2D numpy array")
        if not isinstance(self.destination_coords, np.ndarray) or self.destination_coords.ndim != 2:
            raise ValueError("destination_coords must be a 2D numpy array")
        n_origins = self.origin_coords.shape[0]
        n_destinations = self.destination_coords.shape[0]
        if not isinstance(self.origin_mass, np.ndarray) or self.origin_mass.shape != (n_origins,):
            raise ValueError("origin_mass must be a 1D numpy array matching origin_coords")
        if not isinstance(self.destination_mass, np.ndarray) or self.destination_mass.shape != (n_destinations,):
            raise ValueError("destination_mass must be a 1D numpy array matching destination_coords")
        if self.observed_flows is not None:
            if not isinstance(self.observed_flows, np.ndarray) or self.observed_flows.shape != (
                n_origins,
                n_destinations,
            ):
                raise ValueError("observed_flows must match origin/destination grid")
        return self

    @field_serializer(
        "origin_coords",
        "destination_coords",
        "origin_mass",
        "destination_mass",
        "observed_flows",
        mode="plain",
        when_used="json",
    )
    def _serialize_gravity_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class AccessibilityData(BaseModel):
    """Accessibility data public type."""
    contract_id: ClassVar[str] = "foundry.spatial.accessibility_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    origin_coords: Any
    destination_coords: Any
    opportunity_mass: Any
    travel_cost_matrix: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "origin_coords",
        "destination_coords",
        "opportunity_mass",
        "travel_cost_matrix",
        mode="before",
    )
    @classmethod
    def _coerce_access_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_access_shapes(self) -> "AccessibilityData":
        if not isinstance(self.origin_coords, np.ndarray) or self.origin_coords.ndim != 2:
            raise ValueError("origin_coords must be a 2D numpy array")
        if not isinstance(self.destination_coords, np.ndarray) or self.destination_coords.ndim != 2:
            raise ValueError("destination_coords must be a 2D numpy array")
        n_origins = self.origin_coords.shape[0]
        n_destinations = self.destination_coords.shape[0]
        if not isinstance(self.opportunity_mass, np.ndarray) or self.opportunity_mass.shape != (n_destinations,):
            raise ValueError("opportunity_mass must match destination rows")
        if self.travel_cost_matrix is not None:
            if not isinstance(self.travel_cost_matrix, np.ndarray) or self.travel_cost_matrix.shape != (
                n_origins,
                n_destinations,
            ):
                raise ValueError("travel_cost_matrix must match origin/destination grid")
        return self

    @field_serializer(
        "origin_coords",
        "destination_coords",
        "opportunity_mass",
        "travel_cost_matrix",
        mode="plain",
        when_used="json",
    )
    def _serialize_access_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class SpatialResult(BaseModel):
    """Carry coefficients, fit diagnostics, and spatial effects emitted by spatial estimators."""
    contract_id: ClassVar[str] = "foundry.spatial.result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    method_name: str
    statistics: dict[str, float] = Field(default_factory=dict)
    local_coefficients: Any | None = None
    fitted_values: Any | None = None
    scores: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("local_coefficients", "fitted_values", "scores", mode="before")
    @classmethod
    def _coerce_result_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @field_serializer("local_coefficients", "fitted_values", "scores", mode="plain", when_used="json")
    def _serialize_result_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


__all__ = [
    "AccessibilityData",
    "GravityFlowData",
    "SpatialData",
    "SpatialResult",
]
