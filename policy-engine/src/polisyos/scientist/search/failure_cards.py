"""Typed failure cards for search funnel, judges, and governance signals."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.search.uncertainty import UncertaintyType


class FailureSeverity(str, Enum):
    """Failure severity public type."""
    BLOCKER = "blocker"
    WARNING = "warning"
    INFO = "info"


class TypedFailureCard(BaseModel):
    """Structured typed failure record attached to funnel evaluations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    judge_name: str = Field(min_length=1)
    failure_type: str = Field(min_length=1)
    severity: FailureSeverity
    description: str = Field(min_length=1)
    uncertainty_type: UncertaintyType | None = None
    remediation_hint: str | None = None
    evidence_ref: ArtifactRef | None = None
    metric_name: str | None = None
    observed_value: float | None = None
    threshold_value: float | None = None
    threshold_direction: Literal["max", "min"] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_blocker(self) -> bool:
        return self.severity == FailureSeverity.BLOCKER
