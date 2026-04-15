"""Entity-resolution record models and explainable match candidates."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EntityRecord(BaseModel):
    """One source-specific entity representation participating in matching."""

    model_config = ConfigDict(extra="forbid")

    entity_id: str = Field(..., min_length=1)
    canonical_name: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    aliases: list[str] = Field(default_factory=list)
    identifiers: dict[str, str] = Field(default_factory=dict)
    attributes: dict[str, str] = Field(default_factory=dict)
    provenance_ref: str | None = None


class EntityMatchEvidence(BaseModel):
    """One explainable evidence item contributing to a probabilistic match."""

    model_config = ConfigDict(extra="forbid")

    evidence_type: str = Field(..., min_length=1)
    detail: str = Field(..., min_length=1)
    score: float = Field(default=0.0, ge=0.0, le=1.0)


class EntityMatchCandidate(BaseModel):
    """Persistable and reversible candidate entity match."""

    model_config = ConfigDict(extra="forbid")

    match_id: str = Field(..., min_length=1)
    left_entity_id: str = Field(..., min_length=1)
    right_entity_id: str = Field(..., min_length=1)
    left_source: str = Field(..., min_length=1)
    right_source: str = Field(..., min_length=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    method: str = Field(default="probabilistic_name_identifier_v1", min_length=1)
    evidence: list[EntityMatchEvidence] = Field(default_factory=list)
    override_provenance_ref: str | None = None
    override_status: Literal["candidate", "accepted", "rejected"] = "candidate"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def build_match_id(left_entity_id: str, right_entity_id: str, *, method: str) -> str:
        ordered = sorted([left_entity_id, right_entity_id])
        digest = hashlib.sha256(f"{ordered[0]}|{ordered[1]}|{method}".encode("utf-8")).hexdigest()[:20]
        return f"entity_match_{digest}"


class EntityMatchBatch(BaseModel):
    """Batch wrapper for CAS persistence and replay."""

    model_config = ConfigDict(extra="forbid")

    candidates: list[EntityMatchCandidate] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    method: str = Field(default="probabilistic_name_identifier_v1", min_length=1)
    metadata: dict[str, str] = Field(default_factory=dict)


__all__ = [
    "EntityMatchBatch",
    "EntityMatchCandidate",
    "EntityMatchEvidence",
    "EntityRecord",
]
