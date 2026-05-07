"""Continuous governance monitor contracts for living decision artifacts."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef

CONTINUOUS_GOVERNANCE_FLAG = (
    "scientist.best_in_class.wave2.phase2_6.continuous_governance"
)
ENABLE_REISSUE_WORKFLOW_FLAG = (
    "scientist.best_in_class.wave2.phase2_6.enable_reissue_workflow"
)
ENABLE_WITHDRAWAL_STATUS_FLAG = (
    "scientist.best_in_class.wave2.phase2_6.enable_withdrawal_status"
)

MonitorEventType = Literal[
    "source_invalidation",
    "calibration_drift",
    "fairness_drift",
    "policy_context_drift",
    "incident",
]
MonitorSeverity = Literal["info", "warning", "block"]
MonitorAction = Literal[
    "continue_monitoring",
    "mark_stale",
    "human_review",
    "reissue",
    "withdrawal_review",
]


class DecisionValidityStatus(str, Enum):
    """Public validity status for a decision artifact after publication."""

    VALID = "valid"
    MONITORING = "monitoring"
    STALE = "stale"
    REVIEW_REQUIRED = "review_required"
    REISSUED = "reissued"
    WITHDRAWN = "withdrawn"


class GovernanceMonitorEvent(BaseModel):
    """One continuous-governance signal tied to a decision packet."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    event_id: str = Field(min_length=1)
    decision_packet_ref: ArtifactRef
    event_type: MonitorEventType
    severity: MonitorSeverity
    affected_claim_ids: list[str] = Field(default_factory=list)
    affected_dag_node_ids: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_id", "reason")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("governance monitor text fields cannot be blank")
        return value


class GovernanceMonitorRecommendation(BaseModel):
    """Action recommendation produced from a monitor event."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    event_id: str = Field(min_length=1)
    status: DecisionValidityStatus
    recommended_action: MonitorAction
    human_review_required: bool = False
    reissue_recommended: bool = False
    withdrawal_review_required: bool = False
    reason: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_recommendation_semantics(self) -> GovernanceMonitorRecommendation:
        if self.recommended_action == "human_review" and not self.human_review_required:
            raise ValueError("human_review recommendation must require human review")
        if self.recommended_action == "reissue" and not self.reissue_recommended:
            raise ValueError("reissue recommendation must set reissue_recommended")
        if (
            self.recommended_action == "withdrawal_review"
            and not self.withdrawal_review_required
        ):
            raise ValueError("withdrawal_review recommendation must require withdrawal review")
        if self.status is DecisionValidityStatus.WITHDRAWN:
            raise ValueError("monitor recommendations cannot directly withdraw artifacts")
        return self


def monitor_event_id(
    *,
    decision_packet_ref: ArtifactRef,
    event_type: MonitorEventType,
    reason: str,
    sequence: int = 0,
) -> str:
    """Return a stable event id for repeatable monitor fixtures."""

    digest = hashlib.sha256(
        json.dumps(
            {
                "decision_packet_ref": str(decision_packet_ref.artifact_id),
                "event_type": event_type,
                "reason": reason,
                "sequence": sequence,
            },
            ensure_ascii=True,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"governance_monitor_{digest}"


def build_drift_monitor_event(
    *,
    decision_packet_ref: ArtifactRef,
    event_type: Literal[
        "calibration_drift",
        "fairness_drift",
        "policy_context_drift",
    ],
    severity: MonitorSeverity,
    reason: str,
    affected_claim_ids: list[str] | None = None,
    metric_name: str | None = None,
    observed_value: float | None = None,
    threshold: float | None = None,
    sequence: int = 0,
) -> GovernanceMonitorEvent:
    """Build a typed drift event with optional metric diagnostics."""

    metadata: dict[str, Any] = {}
    if metric_name is not None:
        metadata["metric_name"] = metric_name
    if observed_value is not None:
        metadata["observed_value"] = observed_value
    if threshold is not None:
        metadata["threshold"] = threshold
    return GovernanceMonitorEvent(
        event_id=monitor_event_id(
            decision_packet_ref=decision_packet_ref,
            event_type=event_type,
            reason=reason,
            sequence=sequence,
        ),
        decision_packet_ref=decision_packet_ref,
        event_type=event_type,
        severity=severity,
        affected_claim_ids=affected_claim_ids or [],
        reason=reason,
        metadata=metadata,
    )


def recommend_validity_action(
    event: GovernanceMonitorEvent,
) -> GovernanceMonitorRecommendation:
    """Convert a monitor event into an auditable review/reissue recommendation."""

    if event.severity == "info":
        return GovernanceMonitorRecommendation(
            event_id=event.event_id,
            status=DecisionValidityStatus.MONITORING,
            recommended_action="continue_monitoring",
            reason=f"{event.event_type} is informational; continue monitoring.",
            metadata={"event_type": event.event_type, "severity": event.severity},
        )

    if event.event_type == "source_invalidation":
        if event.severity == "warning":
            return GovernanceMonitorRecommendation(
                event_id=event.event_id,
                status=DecisionValidityStatus.STALE,
                recommended_action="mark_stale",
                reason="Source invalidation marked dependent claims stale.",
                metadata={"event_type": event.event_type, "severity": event.severity},
            )
        return GovernanceMonitorRecommendation(
            event_id=event.event_id,
            status=DecisionValidityStatus.REVIEW_REQUIRED,
            recommended_action="reissue",
            human_review_required=True,
            reissue_recommended=True,
            reason="Blocking source invalidation requires review and possible reissue.",
            metadata={"event_type": event.event_type, "severity": event.severity},
        )

    if event.event_type in {
        "calibration_drift",
        "fairness_drift",
        "policy_context_drift",
    }:
        if event.severity == "warning":
            return GovernanceMonitorRecommendation(
                event_id=event.event_id,
                status=DecisionValidityStatus.REVIEW_REQUIRED,
                recommended_action="human_review",
                human_review_required=True,
                reason=f"{event.event_type} trigger requires reviewer triage.",
                metadata={"event_type": event.event_type, "severity": event.severity},
            )
        return GovernanceMonitorRecommendation(
            event_id=event.event_id,
            status=DecisionValidityStatus.REVIEW_REQUIRED,
            recommended_action="reissue",
            human_review_required=True,
            reissue_recommended=True,
            reason=f"Blocking {event.event_type} requires review and reissue assessment.",
            metadata={"event_type": event.event_type, "severity": event.severity},
        )

    if event.severity == "block":
        return GovernanceMonitorRecommendation(
            event_id=event.event_id,
            status=DecisionValidityStatus.REVIEW_REQUIRED,
            recommended_action="withdrawal_review",
            human_review_required=True,
            withdrawal_review_required=True,
            reason="Blocking incident requires explicit withdrawal review.",
            metadata={"event_type": event.event_type, "severity": event.severity},
        )
    return GovernanceMonitorRecommendation(
        event_id=event.event_id,
        status=DecisionValidityStatus.REVIEW_REQUIRED,
        recommended_action="human_review",
        human_review_required=True,
        reason="Incident requires reviewer triage.",
        metadata={"event_type": event.event_type, "severity": event.severity},
    )


def aggregate_validity_status(
    recommendations: list[GovernanceMonitorRecommendation],
) -> DecisionValidityStatus:
    """Collapse event-level recommendations into one decision validity status."""

    if not recommendations:
        return DecisionValidityStatus.VALID
    if any(item.withdrawal_review_required for item in recommendations):
        return DecisionValidityStatus.REVIEW_REQUIRED
    if any(item.reissue_recommended for item in recommendations):
        return DecisionValidityStatus.REVIEW_REQUIRED
    if any(item.human_review_required for item in recommendations):
        return DecisionValidityStatus.REVIEW_REQUIRED
    if any(item.status is DecisionValidityStatus.STALE for item in recommendations):
        return DecisionValidityStatus.STALE
    return DecisionValidityStatus.MONITORING


__all__ = [
    "CONTINUOUS_GOVERNANCE_FLAG",
    "ENABLE_REISSUE_WORKFLOW_FLAG",
    "ENABLE_WITHDRAWAL_STATUS_FLAG",
    "DecisionValidityStatus",
    "GovernanceMonitorEvent",
    "GovernanceMonitorRecommendation",
    "MonitorAction",
    "MonitorEventType",
    "MonitorSeverity",
    "aggregate_validity_status",
    "build_drift_monitor_event",
    "monitor_event_id",
    "recommend_validity_action",
]
