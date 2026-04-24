"""Shared graph-dependence contracts used across survey, spatial, and econometrics methods."""

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


def _to_numpy(value: Any) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value
    return np.asarray(value)


class DependenceGraphSpec(BaseModel):
    """A candidate exogenous graph used to screen cross-unit dependence."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    graph_id: str
    family: str = "SAR"
    W: Any
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("graph_id", "family", mode="before")
    @classmethod
    def _clean_string(cls, value: Any) -> str:
        candidate = str(value).strip()
        if not candidate:
            raise ValueError("graph_id/family must be non-empty")
        return candidate

    @field_validator("W", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> np.ndarray:
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_weights(self) -> DependenceGraphSpec:
        if not isinstance(self.W, np.ndarray) or self.W.ndim != 2:
            raise ValueError("W must be a 2D numpy array")
        if self.W.shape[0] != self.W.shape[1]:
            raise ValueError("W must be square")
        if self.W.shape[0] < 3:
            raise ValueError("W must cover at least 3 areas")
        if not np.isfinite(self.W).all():
            raise ValueError("W must be finite")
        return self

    @field_serializer("W", mode="plain", when_used="json")
    def _serialize_matrix(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class DependenceDiagnosticData(BaseModel):
    """Residual vector plus a family of aligned candidate graphs."""

    contract_id: ClassVar[str] = "foundry.dependence.diagnostic_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    residuals: Any
    candidate_graphs: tuple[DependenceGraphSpec, ...]
    area_ids: tuple[str, ...] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("residuals", mode="before")
    @classmethod
    def _coerce_residuals(cls, value: Any) -> np.ndarray:
        return _to_numpy(value)

    @field_validator("area_ids", mode="before")
    @classmethod
    def _coerce_area_ids(cls, value: Any) -> tuple[str, ...] | None:
        if value is None:
            return None
        if not isinstance(value, (tuple, list)):
            raise ValueError("area_ids must be a tuple/list of strings")
        return tuple(str(item) for item in value)

    @model_validator(mode="after")
    def _validate_alignment(self) -> DependenceDiagnosticData:
        if not isinstance(self.residuals, np.ndarray) or self.residuals.ndim != 1:
            raise ValueError("residuals must be a 1D numpy array")
        if self.residuals.shape[0] < 3:
            raise ValueError("residuals must contain at least 3 observations")
        if not np.isfinite(self.residuals).all():
            raise ValueError("residuals must be finite")
        if not self.candidate_graphs:
            raise ValueError("candidate_graphs must be non-empty")
        n_obs = self.residuals.shape[0]
        if self.area_ids is not None and len(self.area_ids) != n_obs:
            raise ValueError("area_ids length must match residuals")
        for graph in self.candidate_graphs:
            if graph.W.shape != (n_obs, n_obs):
                raise ValueError(
                    f"candidate graph {graph.graph_id!r} does not align with residuals"
                )
        return self

    @field_serializer("residuals", mode="plain", when_used="json")
    def _serialize_residuals(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class GraphDependenceDiagnostic(BaseModel):
    """Per-graph diagnostic summary returned by the shared primitive."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    graph_id: str
    family: str
    identifiable: bool
    moran_i: float | None = None
    geary_c: float | None = None
    moran_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    geary_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    pesaran_cd: float | None = None
    pesaran_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    lm_error: float | None = None
    lm_error_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    lm_lag: float | None = None
    lm_lag_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    dependence_score: float = 0.0
    profile_curvature: float | None = None
    information_eigen_min: float | None = None
    information_condition_number: float | None = None
    rho_confidence_interval: tuple[float, float] | None = None
    rho_interval_contains_zero: bool | None = None
    boundary_hit: bool | None = None
    decision: Literal["identified", "fallback_independent", "not_identified"] = "not_identified"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DependenceDiagnosticResult(BaseModel):
    """Shared output contract for graph-aware dependence screening."""

    contract_id: ClassVar[str] = "foundry.dependence.diagnostic_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True)

    method_name: str
    detected: bool
    class_label: Literal["none", "weak_or_none", "graph_local", "mixed", "inconclusive"]
    estimator_status: Literal["ok", "fallback_independent", "not_identified"]
    decision: Literal["identified", "fallback_independent", "not_identified"] = (
        "fallback_independent"
    )
    strength: Literal["none", "weak", "strong", "unknown"] = "unknown"
    identifiable: bool
    selected_graph_id: str | None = None
    moran_i: float | None = None
    geary_c: float | None = None
    moran_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    geary_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    pesaran_cd: float | None = None
    pesaran_cd_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    lm_error: float | None = None
    lm_error_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    lm_lag: float | None = None
    lm_lag_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    profile_curvature: float | None = None
    information_eigen_min: float | None = None
    information_condition_number: float | None = None
    rho_confidence_interval: tuple[float, float] | None = None
    rho_interval_contains_zero: bool | None = None
    fallback_reason: str | None = None
    graph_diagnostics: tuple[GraphDependenceDiagnostic, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "DependenceDiagnosticData",
    "DependenceDiagnosticResult",
    "DependenceGraphSpec",
    "GraphDependenceDiagnostic",
]
