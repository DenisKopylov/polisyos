"""
Scholar contracts (research/enrichment).

Defines the minimal ABI boundary between Scholar and other modules.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..artifacts.manifest import ArtifactRef


class TimeWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str | None = None
    end: str | None = None
    notes: list[str] = Field(default_factory=list)


class ResearchIntent(BaseModel):
    """Input envelope for Scholar research requests."""

    model_config = ConfigDict(extra="forbid")

    domain: str | None = None
    topic: str | None = None
    jurisdictions: list[str] = Field(default_factory=list)
    time_window: TimeWindow | None = None
    required_outputs: list[str] = Field(default_factory=list)
    budgets: dict[str, int | float | str] | None = None
    limits: dict[str, int | float | str] | None = None
    notes: list[str] = Field(default_factory=list)


class KnowledgeBundleRef(ArtifactRef):
    kind: Literal["scholar.knowledge_bundle"] = "scholar.knowledge_bundle"
    media_type: Literal["application/json"] = "application/json"


class EnrichmentReportRef(ArtifactRef):
    kind: Literal["scholar.enrichment_report"] = "scholar.enrichment_report"
    media_type: Literal["application/json"] = "application/json"


class KnowledgeBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: ResearchIntent | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


__all__ = [
    "TimeWindow",
    "ResearchIntent",
    "KnowledgeBundleRef",
    "EnrichmentReportRef",
    "KnowledgeBundle",
]
