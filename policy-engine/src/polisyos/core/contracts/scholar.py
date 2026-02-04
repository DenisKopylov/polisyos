"""
Scholar contracts (research/enrichment).

Defines the minimal ABI boundary between Scholar and other modules.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.kernel.base import ID_PATTERN
from polisyos.ir.world.trust import TrustTier

from ..artifacts.manifest import ArtifactRef

_ID_RE = re.compile(ID_PATTERN)


class TimeWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str | None = None
    end: str | None = None
    notes: list[str] = Field(default_factory=list)


SourceKind = Literal["local_file", "bytes", "url"]


class SourceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: SourceKind

    # Identity: exactly one
    canonical_url: str | None = None
    official_id: str | None = None
    source_locator: str | None = None

    # Required by Fabric docs ingest
    license: str

    # Optional hints/metadata
    mime_hint: str | None = None
    props: dict[str, str] = Field(default_factory=dict)

    # Acquire payload
    path: str | None = None
    data: bytes | None = None
    url: str | None = None

    @model_validator(mode="after")
    def _validate_source(self) -> "SourceSpec":
        identities = [self.canonical_url, self.official_id, self.source_locator]
        provided = [value for value in identities if isinstance(value, str) and value.strip()]
        if len(provided) != 1:
            raise ValueError(
                "exactly one of canonical_url, official_id, source_locator is required"
            )
        if not self.license.strip():
            raise ValueError("license is required")
        if self.kind == "local_file":
            if not self.path:
                raise ValueError("local_file source requires path")
            if self.data is not None or self.url is not None:
                raise ValueError("local_file source forbids data/url payload fields")
        elif self.kind == "bytes":
            if self.data is None:
                raise ValueError("bytes source requires data")
            if self.path is not None or self.url is not None:
                raise ValueError("bytes source forbids path/url payload fields")
        elif self.kind == "url":
            if not self.url:
                raise ValueError("url source requires url")
            if self.path is not None or self.data is not None:
                raise ValueError("url source forbids path/data payload fields")
        return self


class BudgetsV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_docs: int | None = Field(default=None, ge=1)
    max_bytes_total: int | None = Field(default=None, ge=1)
    max_claims_total: int | None = Field(default=None, ge=1)
    max_bytes_per_doc: int | None = Field(default=None, ge=1)


class ThresholdsV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_doc_trust_tier: TrustTier = TrustTier.MEDIUM


class ResearchIntent(BaseModel):
    """Input envelope for Scholar research requests.

    Legacy fields:
    - `budgets`
    - `limits`

    Scholar MVP reads `budgets_v1`/`thresholds_v1` first, then falls back
    to legacy `budgets` values by key.
    """

    model_config = ConfigDict(extra="forbid")

    domain: str | None = None
    topic: str | None = None
    jurisdictions: list[str] = Field(default_factory=list)
    jurisdiction: str | None = None
    time_window: TimeWindow | None = None

    seed_sources: list[SourceSpec] = Field(default_factory=list)
    claim_targets: list[str] | None = None
    budgets_v1: BudgetsV1 | None = None
    thresholds_v1: ThresholdsV1 | None = None

    required_outputs: list[str] = Field(default_factory=list)
    budgets: dict[str, int | float | str] | None = None
    limits: dict[str, int | float | str] | None = None
    notes: list[str] = Field(default_factory=list)

    @field_validator("claim_targets")
    @classmethod
    def _validate_claim_targets(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        for item in value:
            if not item:
                raise ValueError("claim_targets must not contain empty strings")
            if _ID_RE.fullmatch(item) is None:
                raise ValueError(f"claim_targets item does not match {ID_PATTERN}: {item!r}")
        return value


class ResearchIntentRef(ArtifactRef):
    kind: Literal["scholar.research_intent"] = "scholar.research_intent"
    media_type: Literal["application/json"] = "application/json"


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
    "BudgetsV1",
    "EnrichmentReportRef",
    "KnowledgeBundle",
    "KnowledgeBundleRef",
    "ResearchIntent",
    "ResearchIntentRef",
    "SourceKind",
    "SourceSpec",
    "ThresholdsV1",
    "TimeWindow",
]
