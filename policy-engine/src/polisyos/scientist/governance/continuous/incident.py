"""Incident and withdrawal contracts for continuous governance."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes

from .monitors import (
    DecisionValidityStatus,
    GovernanceMonitorEvent,
    monitor_event_id,
)

INCIDENT_REPORT_KIND = "scientist.incident_report"
INCIDENT_REPORT_SCHEMA_NAME = "polisyos.scientist.IncidentReport"
INCIDENT_REPORT_SCHEMA_VERSION = "1.0"
WITHDRAWAL_RECORD_KIND = "scientist.withdrawal_record"
WITHDRAWAL_RECORD_SCHEMA_NAME = "polisyos.scientist.WithdrawalRecord"
WITHDRAWAL_RECORD_SCHEMA_VERSION = "1.0"


class IncidentSeverity(str, Enum):
    """Operational severity for post-publication incidents."""

    INFO = "info"
    WARNING = "warning"
    BLOCK = "block"


class IncidentReport(BaseModel):
    """Structured incident report for a decision artifact."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    incident_id: str = Field(min_length=1)
    decision_packet_ref: ArtifactRef
    severity: IncidentSeverity
    reason: str = Field(min_length=1)
    affected_claim_ids: list[str] = Field(default_factory=list)
    monitor_event_ref: ArtifactRef | None = None
    opened_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("incident_id", "reason")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("incident text fields cannot be blank")
        return value


class WithdrawalRecord(BaseModel):
    """Explicit audited withdrawal action for a decision artifact."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    withdrawal_id: str = Field(min_length=1)
    decision_packet_ref: ArtifactRef
    status: Literal[DecisionValidityStatus.WITHDRAWN] = DecisionValidityStatus.WITHDRAWN
    actor_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    audit_event_ref: ArtifactRef
    monitor_event_refs: list[ArtifactRef] = Field(default_factory=list)
    human_review_ref: ArtifactRef | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("withdrawal_id", "actor_id", "reason")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("withdrawal text fields cannot be blank")
        return value

    @model_validator(mode="after")
    def _validate_audit_trail(self) -> WithdrawalRecord:
        if not self.monitor_event_refs and self.human_review_ref is None:
            raise ValueError("withdrawal requires monitor_event_refs or human_review_ref")
        return self


def incident_monitor_event(
    *,
    incident: IncidentReport,
    sequence: int = 0,
) -> GovernanceMonitorEvent:
    """Represent an incident report as a continuous-governance monitor event."""

    return GovernanceMonitorEvent(
        event_id=monitor_event_id(
            decision_packet_ref=incident.decision_packet_ref,
            event_type="incident",
            reason=incident.reason,
            sequence=sequence,
        ),
        decision_packet_ref=incident.decision_packet_ref,
        event_type="incident",
        severity=incident.severity.value,
        affected_claim_ids=list(incident.affected_claim_ids),
        reason=incident.reason,
        occurred_at=incident.opened_at,
        metadata={"incident_id": incident.incident_id, **incident.metadata},
    )


def build_withdrawal_record(
    *,
    withdrawal_id: str,
    decision_packet_ref: ArtifactRef,
    actor_id: str,
    reason: str,
    audit_event_ref: ArtifactRef,
    monitor_event_refs: list[ArtifactRef],
    human_review_ref: ArtifactRef | None = None,
    metadata: dict[str, Any] | None = None,
) -> WithdrawalRecord:
    """Build a validated audited withdrawal record."""

    return WithdrawalRecord(
        withdrawal_id=withdrawal_id,
        decision_packet_ref=decision_packet_ref,
        actor_id=actor_id,
        reason=reason,
        audit_event_ref=audit_event_ref,
        monitor_event_refs=list(monitor_event_refs),
        human_review_ref=human_review_ref,
        metadata=metadata or {},
    )


def incident_report_inputs(report: IncidentReport) -> list[InputRef]:
    """Return CAS lineage inputs for an incident report."""

    inputs = [InputRef(artifact_id=report.decision_packet_ref.artifact_id, role="decision_packet")]
    if report.monitor_event_ref is not None:
        inputs.append(InputRef(artifact_id=report.monitor_event_ref.artifact_id, role="monitor_event"))
    return inputs


def withdrawal_record_inputs(record: WithdrawalRecord) -> list[InputRef]:
    """Return CAS lineage inputs for a withdrawal record."""

    inputs = [
        InputRef(artifact_id=record.decision_packet_ref.artifact_id, role="decision_packet"),
        InputRef(artifact_id=record.audit_event_ref.artifact_id, role="audit_event"),
    ]
    if record.human_review_ref is not None:
        inputs.append(
            InputRef(artifact_id=record.human_review_ref.artifact_id, role="human_review")
        )
    for index, ref in enumerate(record.monitor_event_refs):
        inputs.append(InputRef(artifact_id=ref.artifact_id, role=f"monitor_event[{index}]"))
    return inputs


def persist_incident_report(
    store: Any,
    report: IncidentReport,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist an IncidentReport as a CAS sidecar."""

    return store.put_json(
        report,
        PutOptions(
            kind=INCIDENT_REPORT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=INCIDENT_REPORT_SCHEMA_NAME,
                version=INCIDENT_REPORT_SCHEMA_VERSION,
            ),
            inputs=list(inputs) if inputs is not None else incident_report_inputs(report),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_incident_report(store: Any, ref: ArtifactRef) -> IncidentReport:
    """Load a persisted IncidentReport from CAS."""

    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return IncidentReport.model_validate(payload)


def persist_withdrawal_record(
    store: Any,
    record: WithdrawalRecord,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a WithdrawalRecord as a CAS sidecar."""

    return store.put_json(
        record,
        PutOptions(
            kind=WITHDRAWAL_RECORD_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=WITHDRAWAL_RECORD_SCHEMA_NAME,
                version=WITHDRAWAL_RECORD_SCHEMA_VERSION,
            ),
            inputs=list(inputs) if inputs is not None else withdrawal_record_inputs(record),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_withdrawal_record(store: Any, ref: ArtifactRef) -> WithdrawalRecord:
    """Load a persisted WithdrawalRecord from CAS."""

    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return WithdrawalRecord.model_validate(payload)


__all__ = [
    "INCIDENT_REPORT_KIND",
    "INCIDENT_REPORT_SCHEMA_NAME",
    "INCIDENT_REPORT_SCHEMA_VERSION",
    "IncidentReport",
    "IncidentSeverity",
    "WITHDRAWAL_RECORD_KIND",
    "WITHDRAWAL_RECORD_SCHEMA_NAME",
    "WITHDRAWAL_RECORD_SCHEMA_VERSION",
    "WithdrawalRecord",
    "build_withdrawal_record",
    "incident_report_inputs",
    "incident_monitor_event",
    "load_incident_report",
    "load_withdrawal_record",
    "persist_incident_report",
    "persist_withdrawal_record",
    "withdrawal_record_inputs",
]
