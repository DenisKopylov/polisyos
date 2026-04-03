"""Public analytics data views module API."""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DataViewType(str, Enum):
    """Logical shape of a runtime data view request."""

    PANEL = "panel"
    SNAPSHOT = "snapshot"
    NETWORK = "network"


class AccessTier(str, Enum):
    """Access-sensitivity tier required to materialize a data view."""

    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"


class DataFilter(BaseModel):
    """Predicate applied while slicing a materialized data view."""

    column: str
    op: str = Field(..., pattern=r"^(==|!=|>|<|>=|<=)$")
    value: str | int | float | bool

    model_config = ConfigDict(extra="forbid")


class DataViewRequest(BaseModel):
    """Request for a panel, snapshot, or network view over execution data."""

    request_id: str
    run_id: str
    view_type: DataViewType
    metrics: List[str] = Field(..., description="List of columns to select.")
    filters: List[DataFilter] = Field(default_factory=list)
    step_start: Optional[int] = None
    step_end: Optional[int] = None
    aggregation: Optional[str] = Field(default="mean", pattern=r"^(mean|sum|count|min|max)$")
    access_tier: AccessTier
    ego_node_id: Optional[str] = Field(None, description="Center node for network query")
    hop_depth: int = Field(1, ge=1, le=5, description="Search depth")
    relation_types: Optional[List[str]] = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_request(self) -> "DataViewRequest":
        if not self.metrics:
            raise ValueError("DataViewRequest.metrics must not be empty")
        if self.view_type == DataViewType.NETWORK:
            if not self.ego_node_id:
                raise ValueError("Network view requires ego_node_id")
            if "neighbor_id" not in self.metrics:
                raise ValueError("Network view requires 'neighbor_id' in metrics")
        if self.view_type == DataViewType.SNAPSHOT:
            if self.step_end is None:
                raise ValueError("Snapshot view requires step_end")
            if self.step_start is not None and self.step_start != self.step_end:
                raise ValueError("Snapshot view requires step_start to match step_end")
        return self
