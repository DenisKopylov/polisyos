"""Provenance-event contracts for world graph agents, activities, inputs, and outputs."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BeforeValidator, Field, model_validator

from polisyos.ir.kernel.base import (
    ARTIFACT_ID_PATTERN,
    ID_PATTERN,
    KernelModel,
    reject_floats_deep,
)

if TYPE_CHECKING:
    from datetime import datetime
else:
    from datetime import datetime

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class EventKind(str, Enum):
    """Event kind public type."""

    FETCH_DOC = "fetch_doc"
    NORMALIZE_DOC = "normalize_doc"
    STRUCTURE_DOC = "structure_doc"
    CHUNK_DOC = "chunk_doc"
    EXTRACT_CLAIMS = "extract_claims"
    NORMALIZE_CLAIMS = "normalize_claims"
    DETECT_CONFLICTS = "detect_conflicts"
    RESOLVE_CONFLICTS = "resolve_conflicts"
    ASSEMBLE_NORM_PACK = "assemble_norm_pack"
    EVALUATE_LEGALITY = "evaluate_legality"
    INGEST_DATASET = "ingest_dataset"
    QUERY_WORLD = "query_world"
    SIMULATE = "simulate"
    VALIDATE = "validate"
    KNOWLEDGE_BUNDLE_BUILD = "knowledge_bundle_build"


class ProvAgentType(str, Enum):
    """Prov agent type public type."""

    SYSTEM = "system"
    USER = "user"
    MODEL = "model"
    CONNECTOR = "connector"
    EXTRACTOR = "extractor"
    SCHEDULER = "scheduler"
    HUMAN_REVIEWER = "human_reviewer"


class ProvActivityType(str, Enum):
    """Prov activity type public type."""

    FETCH_DOC = "fetch_doc"
    NORMALIZE_DOC = "normalize_doc"
    STRUCTURE_DOC = "structure_doc"
    CHUNK_DOC = "chunk_doc"
    EXTRACT_CLAIMS = "extract_claims"
    NORMALIZE_CLAIMS = "normalize_claims"
    DETECT_CONFLICTS = "detect_conflicts"
    RESOLVE_CONFLICTS = "resolve_conflicts"
    ASSEMBLE_NORM_PACK = "assemble_norm_pack"
    EVALUATE_LEGALITY = "evaluate_legality"
    INGEST_DATASET = "ingest_dataset"
    QUERY_WORLD = "query_world"
    SIMULATE = "simulate"
    VALIDATE = "validate"
    KNOWLEDGE_BUNDLE_BUILD = "knowledge_bundle_build"


class ProvAgent(KernelModel):
    """Prov agent public type."""

    agent_id: str = Field(..., pattern=ID_PATTERN)
    agent_type: ProvAgentType
    label: str
    component_id: str | None = None
    model_id: str | None = None
    metadata: Annotated[dict[str, str], BeforeValidator(reject_floats_deep)] = Field(
        default_factory=dict
    )


class ProvActivity(KernelModel):
    """Prov activity public type."""

    activity_id: str = Field(..., pattern=ID_PATTERN)
    activity_type: ProvActivityType
    label: str
    started_at: datetime
    ended_at: datetime | None = None
    parameters: Annotated[dict[str, Any], BeforeValidator(reject_floats_deep)] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_activity(self) -> ProvActivity:
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at must be >= started_at")
        return self


class WorldObjectRef(KernelModel):
    """Point a provenance edge at either a world object id or the artifact that produced it."""

    world_id: str | None = Field(None, pattern=ID_PATTERN)
    artifact_id: str | None = Field(None, pattern=ARTIFACT_ID_PATTERN)

    @model_validator(mode="after")
    def validate_ref(self) -> WorldObjectRef:
        if self.world_id is None and self.artifact_id is None:
            raise ValueError("WorldObjectRef requires world_id or artifact_id")
        return self


class WorldEvent(KernelModel):
    """Capture one immutable pipeline event after its ids, inputs, and outputs are stable enough to persist."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    event_id: str = Field(..., pattern=ID_PATTERN)
    event_kind: EventKind
    agent: ProvAgent
    activity: ProvActivity
    inputs: list[WorldObjectRef] = Field(default_factory=list)
    outputs: list[WorldObjectRef] = Field(default_factory=list)
    evidence_ref: str | None = Field(None, pattern=ARTIFACT_ID_PATTERN)
    provenance_ref: str | None = Field(None, pattern=ARTIFACT_ID_PATTERN)
    props: Annotated[dict[str, Any], BeforeValidator(reject_floats_deep)] = Field(
        default_factory=dict
    )


__all__ = [
    "EventKind",
    "ProvActivity",
    "ProvActivityType",
    "ProvAgent",
    "ProvAgentType",
    "WorldEvent",
    "WorldObjectRef",
]
