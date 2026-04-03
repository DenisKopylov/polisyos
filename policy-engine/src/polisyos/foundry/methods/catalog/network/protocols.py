"""Public network protocols module API."""
from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator


def _to_numpy(value: Any) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value
    return np.asarray(value)


class NetworkData(BaseModel):
    """Network data public type."""
    contract_id: ClassVar[str] = "foundry.network.data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    adjacency: Any
    node_features: Any | None = None
    node_states: Any | None = None
    node_ids: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("adjacency", "node_features", "node_states", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "NetworkData":
        if not isinstance(self.adjacency, np.ndarray) or self.adjacency.ndim != 2:
            raise ValueError("adjacency must be a 2D numpy array")
        n_nodes = self.adjacency.shape[0]
        if self.adjacency.shape[1] != n_nodes:
            raise ValueError("adjacency must be square")
        if self.node_features is not None:
            if not isinstance(self.node_features, np.ndarray) or self.node_features.ndim != 2:
                raise ValueError("node_features must be a 2D numpy array")
            if self.node_features.shape[0] != n_nodes:
                raise ValueError("node_features rows must match node count")
        if self.node_states is not None:
            if not isinstance(self.node_states, np.ndarray) or self.node_states.ndim != 1:
                raise ValueError("node_states must be a 1D numpy array")
            if self.node_states.shape[0] != n_nodes:
                raise ValueError("node_states length must match node count")
        if self.node_ids is not None and len(self.node_ids) != n_nodes:
            raise ValueError("node_ids length must match node count")
        return self

    @field_serializer("adjacency", "node_features", "node_states", mode="plain", when_used="json")
    def _serialize_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class MultiplexNetworkData(BaseModel):
    """Multiplex network data public type."""
    contract_id: ClassVar[str] = "foundry.network.multiplex_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    adjacency_layers: Any
    node_features: Any | None = None
    node_ids: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("adjacency_layers", "node_features", mode="before")
    @classmethod
    def _coerce_layer_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_layers(self) -> "MultiplexNetworkData":
        if not isinstance(self.adjacency_layers, np.ndarray) or self.adjacency_layers.ndim != 3:
            raise ValueError("adjacency_layers must be a 3D numpy array")
        n_layers, n_nodes, n_nodes_2 = self.adjacency_layers.shape
        if n_layers < 2 or n_nodes != n_nodes_2:
            raise ValueError("adjacency_layers must have shape (n_layers>=2, n_nodes, n_nodes)")
        if self.node_features is not None:
            if not isinstance(self.node_features, np.ndarray) or self.node_features.ndim != 2:
                raise ValueError("node_features must be a 2D numpy array")
            if self.node_features.shape[0] != n_nodes:
                raise ValueError("node_features rows must match node count")
        if self.node_ids is not None and len(self.node_ids) != n_nodes:
            raise ValueError("node_ids length must match node count")
        return self

    @field_serializer("adjacency_layers", "node_features", mode="plain", when_used="json")
    def _serialize_layer_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class NetworkResult(BaseModel):
    """Network result data model."""
    contract_id: ClassVar[str] = "foundry.network.result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    method_name: str
    metrics: dict[str, float] = Field(default_factory=dict)
    node_scores: Any | None = None
    labels: Any | None = None
    state_trajectories: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("node_scores", "labels", "state_trajectories", mode="before")
    @classmethod
    def _coerce_result_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @field_serializer("node_scores", "labels", "state_trajectories", mode="plain", when_used="json")
    def _serialize_result_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


__all__ = [
    "MultiplexNetworkData",
    "NetworkData",
    "NetworkResult",
]
