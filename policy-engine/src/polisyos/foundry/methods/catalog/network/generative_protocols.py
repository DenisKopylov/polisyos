"""Typed contracts for generative network estimators and design-stage outputs."""
from __future__ import annotations

from typing import Any, ClassVar, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from .protocols import NetworkData


def _to_numpy(value: Any) -> Any:
    if value is None or isinstance(value, np.ndarray):
        return value
    return np.asarray(value)


class EdgeListNetworkData(BaseModel):
    """Sparse network input contract with optional node features and states."""

    contract_id: ClassVar[str] = "foundry.network.edge_list_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    edge_index: Any
    edge_weight: Any | None = None
    node_features: Any | None = None
    node_states: Any | None = None
    node_ids: list[str] | None = None
    n_nodes: int | None = Field(default=None, ge=2)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("edge_index", "edge_weight", "node_features", "node_states", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "EdgeListNetworkData":
        if not isinstance(self.edge_index, np.ndarray) or self.edge_index.ndim != 2:
            raise ValueError("edge_index must be a 2D numpy array")
        if self.edge_index.shape[1] != 2:
            raise ValueError("edge_index must have shape (n_edges, 2)")
        if np.any(self.edge_index < 0):
            raise ValueError("edge_index entries must be non-negative")
        inferred_n_nodes = self._resolved_n_nodes()
        if inferred_n_nodes < 2:
            raise ValueError("EdgeListNetworkData requires at least 2 nodes")
        if self.edge_weight is not None:
            if not isinstance(self.edge_weight, np.ndarray) or self.edge_weight.ndim != 1:
                raise ValueError("edge_weight must be a 1D numpy array")
            if self.edge_weight.shape[0] != self.edge_index.shape[0]:
                raise ValueError("edge_weight length must match edge_index rows")
        if self.node_features is not None:
            if not isinstance(self.node_features, np.ndarray) or self.node_features.ndim != 2:
                raise ValueError("node_features must be a 2D numpy array")
            if self.node_features.shape[0] != inferred_n_nodes:
                raise ValueError("node_features rows must match node count")
        if self.node_states is not None:
            if not isinstance(self.node_states, np.ndarray) or self.node_states.ndim != 1:
                raise ValueError("node_states must be a 1D numpy array")
            if self.node_states.shape[0] != inferred_n_nodes:
                raise ValueError("node_states length must match node count")
        if self.node_ids is not None and len(self.node_ids) != inferred_n_nodes:
            raise ValueError("node_ids length must match node count")
        if np.max(self.edge_index, initial=-1) >= inferred_n_nodes:
            raise ValueError("edge_index references node ids outside the declared node range")
        return self

    def _resolved_n_nodes(self) -> int:
        if self.n_nodes is not None:
            return int(self.n_nodes)
        if self.node_features is not None:
            return int(self.node_features.shape[0])
        if self.node_states is not None:
            return int(self.node_states.shape[0])
        if self.node_ids is not None:
            return len(self.node_ids)
        if self.edge_index.size == 0:
            return 0
        return int(np.max(self.edge_index) + 1)

    def to_network_data(self) -> NetworkData:
        """Materialize a dense adjacency matrix for algorithms that expect one."""
        n_nodes = self._resolved_n_nodes()
        weights = (
            np.asarray(self.edge_weight, dtype=float)
            if self.edge_weight is not None
            else np.ones(self.edge_index.shape[0], dtype=float)
        )
        adjacency = np.zeros((n_nodes, n_nodes), dtype=float)
        for (src, dst), weight in zip(np.asarray(self.edge_index, dtype=int), weights, strict=True):
            if src == dst:
                continue
            adjacency[src, dst] += float(weight)
            adjacency[dst, src] += float(weight)
        np.fill_diagonal(adjacency, 0.0)
        return NetworkData(
            adjacency=adjacency,
            node_features=self.node_features,
            node_states=self.node_states,
            node_ids=self.node_ids,
            metadata=dict(self.metadata),
        )

    @field_serializer("edge_index", "edge_weight", "node_features", "node_states", mode="plain", when_used="json")
    def _serialize_numpy(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class ERGMResult(BaseModel):
    """ERGM null-model fit output with diagnostics and simulated envelope summaries."""

    contract_id: ClassVar[str] = "foundry.network.ergm_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    method_name: str
    fit_status: Literal["success", "null_lite", "failed", "input_invalid"] = "null_lite"
    coefficients: dict[str, float] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    gof_checks: dict[str, Any] = Field(default_factory=dict)
    null_envelope: dict[str, Any] = Field(default_factory=dict)
    simulated_graphs: Any | None = None
    degeneracy_alarm: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("simulated_graphs", mode="before")
    @classmethod
    def _coerce_graphs(cls, value: Any) -> Any:
        return _to_numpy(value)

    @field_serializer("simulated_graphs", mode="plain", when_used="json")
    def _serialize_graphs(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class SBMStratificationResult(BaseModel):
    """Block assignments, uncertainty surface, and design-stage diagnostics."""

    contract_id: ClassVar[str] = "foundry.network.sbm_stratification_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    method_name: str
    labels: Any
    responsibilities: Any | None = None
    co_clustering: Any | None = None
    block_connectivity: Any
    degree_correction: Any | None = None
    stability: dict[str, Any] = Field(default_factory=dict)
    positivity_report: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "labels",
        "responsibilities",
        "co_clustering",
        "block_connectivity",
        "degree_correction",
        mode="before",
    )
    @classmethod
    def _coerce_result_arrays(cls, value: Any) -> Any:
        return _to_numpy(value)

    @field_serializer(
        "labels",
        "responsibilities",
        "co_clustering",
        "block_connectivity",
        "degree_correction",
        mode="plain",
        when_used="json",
    )
    def _serialize_result_arrays(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class DiffusionNullResult(BaseModel):
    """Observed diffusion compared against an ERGM-style null ensemble."""

    contract_id: ClassVar[str] = "foundry.network.diffusion_null_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    method_name: str
    metric_name: str = "final_mean_state"
    observed_metric: float
    null_mean: float
    null_std: float = Field(ge=0.0)
    z_score: float | None = None
    p_value: float = Field(ge=0.0, le=1.0)
    envelope: dict[str, float] = Field(default_factory=dict)
    simulated_metrics: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("simulated_metrics", mode="before")
    @classmethod
    def _coerce_metrics(cls, value: Any) -> Any:
        return _to_numpy(value)

    @field_serializer("simulated_metrics", mode="plain", when_used="json")
    def _serialize_metrics(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


__all__ = [
    "DiffusionNullResult",
    "EdgeListNetworkData",
    "ERGMResult",
    "SBMStratificationResult",
]
