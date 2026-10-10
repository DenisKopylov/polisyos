"""Define approval requests, decisions, and audit events for governance gates.

These contracts are emitted when execution pauses for automated or human review
and are consumed by the gate subsystem, audit logs, and replay/reporting tools.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.registry.refs import ArtifactRefModel

GATE_REQUEST_SCHEMA_VERSION = "1.2"
_GATE_REQUEST_REQUIRED_CONTEXT_FIELDS_BY_VERSION = {
    GATE_REQUEST_SCHEMA_VERSION: ("selected_replay_refs",),
}


def _add_gate_request_versioned_context_requirements(schema: dict[str, Any]) -> None:
    """Represent versioned context requirements enforced by GateRequest."""
    versioned_requirements = []
    for version, context_fields in _GATE_REQUEST_REQUIRED_CONTEXT_FIELDS_BY_VERSION.items():
        versioned_requirements.append(
            {
                "if": {"properties": {"schema_version": {"const": version}}},
                "then": {
                    "properties": {
                        "context": {
                            "required": list(context_fields),
                            "properties": {
                                field_name: {"not": {"type": "null"}}
                                for field_name in context_fields
                            },
                        }
                    }
                },
            }
        )
    schema.setdefault("allOf", []).extend(versioned_requirements)


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
    selected_replay_refs: dict[str, ArtifactRefModel] | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    transport_summary: dict[str, Any] | None = None
    replay_summary: dict[str, Any] | None = None


class GateRequest(BaseModel):
    """Approval request payload emitted when execution needs governance review."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra=_add_gate_request_versioned_context_requirements,
    )

    schema_version: str = Field(GATE_REQUEST_SCHEMA_VERSION, pattern=r"^\d+\.\d+$")
    request_id: str
    run_id: str
    reason: str
    context: GateContext
    priority: GatePriority = GatePriority.NORMAL
    timeout_seconds: int | None = Field(default=None, ge=1)
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    requested_by: str = "system"

    @model_validator(mode="after")
    def _require_selected_replay_refs_for_current_schema(self) -> GateRequest:
        """Require selected view bindings on requests emitted under schema 1.2."""
        required_context_fields = _GATE_REQUEST_REQUIRED_CONTEXT_FIELDS_BY_VERSION.get(
            self.schema_version, ()
        )
        missing_context_fields = tuple(
            field_name
            for field_name in required_context_fields
            if getattr(self.context, field_name) is None
        )
        if missing_context_fields:
            raise ValueError(
                f"GateRequest schema {self.schema_version} requires "
                f"{', '.join(missing_context_fields)}"
            )
        return self


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
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evidence_refs: list[str] = Field(default_factory=list)


class GateEvent(BaseModel):
    """Audit event emitted for gate lifecycle transitions."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    event_type: GateEventType
    run_id: str
    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    span_id: str | None = None
