"""Validity reports and public redaction helpers for continuous governance."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes

from .monitors import (
    DecisionValidityStatus,
    GovernanceMonitorEvent,
    GovernanceMonitorRecommendation,
    aggregate_validity_status,
    recommend_validity_action,
)

FORBIDDEN_PUBLIC_REF_TOKENS: tuple[str, ...] = (
    "hidden",
    "hidden_eval",
    "hidden_holdout",
    "private_eval",
    "internal_monitor",
    "benchmark_answer",
)
DECISION_VALIDITY_REPORT_KIND = "scientist.continuous_governance_report"
DECISION_VALIDITY_REPORT_SCHEMA_NAME = "polisyos.scientist.DecisionValidityReport"
DECISION_VALIDITY_REPORT_SCHEMA_VERSION = "1.0"


class DecisionValidityReport(BaseModel):
    """Internal validity report for a living decision artifact."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    decision_packet_ref: ArtifactRef
    status: DecisionValidityStatus
    monitor_events: list[GovernanceMonitorEvent] = Field(default_factory=list)
    recommendations: list[GovernanceMonitorRecommendation] = Field(default_factory=list)
    reissue_packet_ref: ArtifactRef | None = None
    withdrawal_ref: ArtifactRef | None = None
    hidden_internal_ref_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def build_validity_report(
    *,
    decision_packet_ref: ArtifactRef,
    monitor_events: list[GovernanceMonitorEvent],
    recommendations: list[GovernanceMonitorRecommendation] | None = None,
    reissue_packet_ref: ArtifactRef | None = None,
    withdrawal_ref: ArtifactRef | None = None,
    hidden_internal_ref_ids: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> DecisionValidityReport:
    """Build an internal validity report from monitor events."""

    resolved_recommendations = recommendations or [
        recommend_validity_action(event) for event in monitor_events
    ]
    status = aggregate_validity_status(resolved_recommendations)
    return DecisionValidityReport(
        decision_packet_ref=decision_packet_ref,
        status=status,
        monitor_events=list(monitor_events),
        recommendations=resolved_recommendations,
        reissue_packet_ref=reissue_packet_ref,
        withdrawal_ref=withdrawal_ref,
        hidden_internal_ref_ids=list(hidden_internal_ref_ids or []),
        metadata=metadata or {},
    )


def validity_report_inputs(report: DecisionValidityReport) -> list[InputRef]:
    """Return CAS lineage inputs for a validity report."""

    inputs: list[InputRef] = []

    def add(ref: ArtifactRef | None, role: str) -> None:
        if ref is not None:
            inputs.append(InputRef(artifact_id=ref.artifact_id, role=role))

    add(report.decision_packet_ref, "decision_packet")
    add(report.reissue_packet_ref, "reissue_packet")
    add(report.withdrawal_ref, "withdrawal_record")
    return inputs


def persist_validity_report(
    store: Any,
    report: DecisionValidityReport,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a DecisionValidityReport as a first-class CAS sidecar."""

    return store.put_json(
        report,
        PutOptions(
            kind=DECISION_VALIDITY_REPORT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=DECISION_VALIDITY_REPORT_SCHEMA_NAME,
                version=DECISION_VALIDITY_REPORT_SCHEMA_VERSION,
            ),
            inputs=list(inputs) if inputs is not None else validity_report_inputs(report),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_validity_report(store: Any, ref: ArtifactRef) -> DecisionValidityReport:
    """Load a persisted DecisionValidityReport from CAS."""

    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return DecisionValidityReport.model_validate(payload)


def export_public_validity_report(report: DecisionValidityReport) -> dict[str, Any]:
    """Return a public validity report with hidden/internal refs removed."""

    _raise_if_forbidden_public_ref(report.decision_packet_ref)
    payload: dict[str, Any] = {
        "schema_version": report.schema_version,
        "decision_packet_ref": str(report.decision_packet_ref.artifact_id),
        "status": report.status.value,
        "event_count": len(report.monitor_events),
        "events": [
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "severity": event.severity,
                "scope": dict(event.scope),
                "affected_claim_ids": list(event.affected_claim_ids),
                "reason": event.reason,
            }
            for event in report.monitor_events
        ],
        "recommendations": [
            {
                "event_id": item.event_id,
                "status": item.status.value,
                "recommended_action": item.recommended_action,
                "human_review_required": item.human_review_required,
                "reissue_recommended": item.reissue_recommended,
                "withdrawal_review_required": item.withdrawal_review_required,
                "reason": item.reason,
            }
            for item in report.recommendations
        ],
        "has_reissue_packet": report.reissue_packet_ref is not None,
        "has_withdrawal_record": report.withdrawal_ref is not None,
    }
    _raise_if_public_payload_contains_forbidden_ref(payload)
    return payload


def _raise_if_forbidden_public_ref(ref: ArtifactRef) -> None:
    text = f"{ref.kind}:{ref.artifact_id}".lower()
    if any(token in text for token in FORBIDDEN_PUBLIC_REF_TOKENS):
        raise ValueError("public validity report contains forbidden hidden/internal ref")


def _raise_if_public_payload_contains_forbidden_ref(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered_key = str(key).lower()
            if any(token in lowered_key for token in FORBIDDEN_PUBLIC_REF_TOKENS):
                raise ValueError("public validity report contains forbidden hidden/internal key")
            _raise_if_public_payload_contains_forbidden_ref(item)
    elif isinstance(value, list | tuple):
        for item in value:
            _raise_if_public_payload_contains_forbidden_ref(item)
    elif isinstance(value, str):
        lowered_value = value.lower()
        if any(token in lowered_value for token in FORBIDDEN_PUBLIC_REF_TOKENS):
            raise ValueError("public validity report contains forbidden hidden/internal ref")


__all__ = [
    "DecisionValidityReport",
    "DECISION_VALIDITY_REPORT_KIND",
    "DECISION_VALIDITY_REPORT_SCHEMA_NAME",
    "DECISION_VALIDITY_REPORT_SCHEMA_VERSION",
    "FORBIDDEN_PUBLIC_REF_TOKENS",
    "build_validity_report",
    "export_public_validity_report",
    "load_validity_report",
    "persist_validity_report",
    "validity_report_inputs",
]
