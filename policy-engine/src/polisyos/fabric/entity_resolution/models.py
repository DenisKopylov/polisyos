"""Entity-resolution record models and explainable match candidates."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
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
    merge_governance_ref: str | None = None
    override_status: Literal["candidate", "accepted", "rejected"] = "candidate"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def build_match_id(left_entity_id: str, right_entity_id: str, *, method: str) -> str:
        ordered = sorted([left_entity_id, right_entity_id])
        digest = hashlib.sha256(f"{ordered[0]}|{ordered[1]}|{method}".encode()).hexdigest()[:20]
        return f"entity_match_{digest}"


class EntityMatchBatch(BaseModel):
    """Batch wrapper for CAS persistence and replay."""

    model_config = ConfigDict(extra="forbid")

    candidates: list[EntityMatchCandidate] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    method: str = Field(default="probabilistic_name_identifier_v1", min_length=1)
    metadata: dict[str, str] = Field(default_factory=dict)


class EntityOverrideAuditRecord(BaseModel):
    """Append-only governance evidence for an entity-match override."""

    model_config = ConfigDict(extra="forbid")

    override_id: str = Field(..., min_length=1)
    match_id: str = Field(..., min_length=1)
    status: Literal["accepted", "rejected"]
    actor: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    provenance_ref: str | None = None
    merge_governance_ref: str | None = None
    canonical_write: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    previous_status: Literal["candidate", "accepted", "rejected"] = "candidate"


class EntityOverrideEnvelope(BaseModel):
    """Persisted override payload with candidate and audit evidence."""

    model_config = ConfigDict(extra="forbid")

    candidate: EntityMatchCandidate
    audit: EntityOverrideAuditRecord


__all__ = [
    "EntityMatchBatch",
    "EntityMatchCandidate",
    "EntityMatchEvidence",
    "EntityOverrideAuditRecord",
    "EntityOverrideEnvelope",
    "EntityRecord",
]
