"""Define approval requests, decisions, and audit events for governance gates.

These contracts are emitted when execution pauses for automated or human review
and are consumed by the gate subsystem, audit logs, and replay/reporting tools.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GateVerdict(str, enum.Enum):
    """Final outcome produced by a governance gate."""

    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    TIMEOUT = "timeout"


class GatePriority(str, enum.Enum):
    """Scheduling priority assigned to a gate request."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class GateEventType(str, enum.Enum):
    """Audit-log event type emitted by the gate subsystem."""

    GATE_REQUESTED = "GATE_REQUESTED"
    GATE_DECIDED = "GATE_DECIDED"
    GATE_TIMEOUT = "GATE_TIMEOUT"
    GATE_CANCELLED = "GATE_CANCELLED"


class GateContext(BaseModel):
    """Execution and risk context presented to a governance approver."""

    model_config = ConfigDict(extra="forbid")

    workflow_id: str
    node_alias: str
    phase: str
    iteration: int = Field(default=1, ge=1)
    is_escalated: bool = False
    governance_profile: str | None = None
    policy_summary: str | None = None
    simulation_results: dict[str, Any] | None = None
    risk_indicators: list[str] = Field(default_factory=list)
    issue_summary: dict[str, int] | None = None
    artifact_refs: dict[str, str] | None = None
    transport_summary: dict[str, Any] | None = None
    replay_summary: dict[str, Any] | None = None


class GateRequest(BaseModel):
    """Approval request payload emitted when execution needs governance review."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.1", pattern=r"^\d+\.\d+$")
    request_id: str
    run_id: str
    reason: str
    context: GateContext
    priority: GatePriority = GatePriority.NORMAL
    timeout_seconds: int | None = Field(default=None, ge=1)
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    requested_by: str = "system"


class GateDecision(BaseModel):
    """Recorded gate verdict with approver identity and supporting evidence."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    request_id: str
    run_id: str
    verdict: GateVerdict
    approver_id: str
    reason_codes: list[str] = Field(default_factory=list)
    comment: str | None = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evidence_refs: list[str] = Field(default_factory=list)


class GateEvent(BaseModel):
    """Audit event emitted for gate lifecycle transitions."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    event_type: GateEventType
    run_id: str
    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    span_id: str | None = None
