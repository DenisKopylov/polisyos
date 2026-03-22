from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.canon import content_hash
from polisyos.core.canon.canon_json import to_canonical_bytes


class AuditEventType(str, Enum):
    TRACE_RECORD = "TRACE_RECORD"
    AUDIT_ACTION = "AUDIT_ACTION"
    GOVERNANCE_DECISION = "GOVERNANCE_DECISION"
    SIGNING_EVENT = "SIGNING_EVENT"
    PII_DETECTION = "PII_DETECTION"
    ACCESS_GRANT = "ACCESS_GRANT"
    ACCESS_DENY = "ACCESS_DENY"
    TENANT_BOUNDARY_VIOLATION = "TENANT_BOUNDARY_VIOLATION"
    SYSTEM_EVENT = "SYSTEM_EVENT"
    NODE_LIFECYCLE = "NODE_LIFECYCLE"
    CHECKPOINT_EVENT = "CHECKPOINT_EVENT"
    BUDGET_EVENT = "BUDGET_EVENT"
    TOOL_EVENT = "TOOL_EVENT"


class AuditActor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity: str = ""
    spiffe_id: str = ""
    tenant_id: str = ""
    roles: list[str] = Field(default_factory=list)


class AuditResource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = ""
    id: str = ""
    artifact_id: str = ""


class AuditCorrelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = ""
    span_id: str = ""
    trace_id: str = ""


_CHAIN_NAMESPACE = uuid.UUID("ed8f3368-5f17-4adf-8aa4-f20da6a9f9d7")


class ChainedLogEntry(BaseModel):
    """One tamper-evident log entry in chained audit stream."""

    model_config = ConfigDict(extra="forbid")

    entry_id: str
    chain_id: str
    sequence_number: int = Field(..., ge=0)
    timestamp: str
    prev_hash: str = Field(..., min_length=64, max_length=64)
    entry_hash: str = Field(..., min_length=64, max_length=64)
    event_type: AuditEventType
    actor: AuditActor = Field(default_factory=AuditActor)
    resource: AuditResource = Field(default_factory=AuditResource)
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation: AuditCorrelation = Field(default_factory=AuditCorrelation)

    def compute_hash(self) -> str:
        body = self.model_dump(mode="json", exclude={"entry_hash"}, exclude_none=True)
        return content_hash(to_canonical_bytes(body))

    @staticmethod
    def genesis_prev_hash() -> str:
        return "0" * 64

    @staticmethod
    def make_entry_id(chain_id: str, sequence_number: int) -> str:
        return str(uuid.uuid5(_CHAIN_NAMESPACE, f"{chain_id}:{sequence_number}"))

    @classmethod
    def build(
        cls,
        *,
        chain_id: str,
        sequence_number: int,
        prev_hash: str,
        event_type: AuditEventType,
        actor: AuditActor | None = None,
        resource: AuditResource | None = None,
        payload: dict[str, Any] | None = None,
        correlation: AuditCorrelation | None = None,
        timestamp: datetime | None = None,
    ) -> "ChainedLogEntry":
        ts = timestamp or datetime.now(timezone.utc)
        entry = cls(
            entry_id=cls.make_entry_id(chain_id, sequence_number),
            chain_id=chain_id,
            sequence_number=sequence_number,
            timestamp=ts.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            prev_hash=prev_hash,
            entry_hash="0" * 64,
            event_type=event_type,
            actor=actor or AuditActor(),
            resource=resource or AuditResource(),
            payload=payload or {},
            correlation=correlation or AuditCorrelation(),
        )
        return entry.model_copy(update={"entry_hash": entry.compute_hash()})
