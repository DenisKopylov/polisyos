"""Continuous governance and reissue loop for Scientist decision artifacts."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "CONTINUOUS_GOVERNANCE_FLAG",
    "ENABLE_REISSUE_WORKFLOW_FLAG",
    "ENABLE_WITHDRAWAL_STATUS_FLAG",
    "ContinuousInvalidationResult",
    "DecisionValidityReport",
    "DecisionValidityStatus",
    "GovernanceMonitorEvent",
    "GovernanceMonitorRecommendation",
    "IncidentReport",
    "IncidentSeverity",
    "ReissuePacket",
    "WithdrawalRecord",
    "aggregate_validity_status",
    "build_drift_monitor_event",
    "build_reissue_packet",
    "build_validity_report",
    "build_withdrawal_record",
    "export_public_validity_report",
    "governance_event_from_source_invalidation",
    "incident_monitor_event",
    "load_incident_report",
    "load_reissue_packet",
    "load_validity_report",
    "load_withdrawal_record",
    "mark_dependent_claims_stale",
    "monitor_event_id",
    "persist_incident_report",
    "persist_reissue_packet",
    "persist_validity_report",
    "persist_withdrawal_record",
    "recommend_validity_action",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "CONTINUOUS_GOVERNANCE_FLAG": (
        "polisyos.scientist.governance.continuous.monitors",
        "CONTINUOUS_GOVERNANCE_FLAG",
    ),
    "ENABLE_REISSUE_WORKFLOW_FLAG": (
        "polisyos.scientist.governance.continuous.monitors",
        "ENABLE_REISSUE_WORKFLOW_FLAG",
    ),
    "ENABLE_WITHDRAWAL_STATUS_FLAG": (
        "polisyos.scientist.governance.continuous.monitors",
        "ENABLE_WITHDRAWAL_STATUS_FLAG",
    ),
    "DecisionValidityStatus": (
        "polisyos.scientist.governance.continuous.monitors",
        "DecisionValidityStatus",
    ),
    "GovernanceMonitorEvent": (
        "polisyos.scientist.governance.continuous.monitors",
        "GovernanceMonitorEvent",
    ),
    "GovernanceMonitorRecommendation": (
        "polisyos.scientist.governance.continuous.monitors",
        "GovernanceMonitorRecommendation",
    ),
    "aggregate_validity_status": (
        "polisyos.scientist.governance.continuous.monitors",
        "aggregate_validity_status",
    ),
    "build_drift_monitor_event": (
        "polisyos.scientist.governance.continuous.monitors",
        "build_drift_monitor_event",
    ),
    "monitor_event_id": (
        "polisyos.scientist.governance.continuous.monitors",
        "monitor_event_id",
    ),
    "recommend_validity_action": (
        "polisyos.scientist.governance.continuous.monitors",
        "recommend_validity_action",
    ),
    "IncidentReport": (
        "polisyos.scientist.governance.continuous.incident",
        "IncidentReport",
    ),
    "IncidentSeverity": (
        "polisyos.scientist.governance.continuous.incident",
        "IncidentSeverity",
    ),
    "WithdrawalRecord": (
        "polisyos.scientist.governance.continuous.incident",
        "WithdrawalRecord",
    ),
    "build_withdrawal_record": (
        "polisyos.scientist.governance.continuous.incident",
        "build_withdrawal_record",
    ),
    "incident_monitor_event": (
        "polisyos.scientist.governance.continuous.incident",
        "incident_monitor_event",
    ),
    "load_incident_report": (
        "polisyos.scientist.governance.continuous.incident",
        "load_incident_report",
    ),
    "load_withdrawal_record": (
        "polisyos.scientist.governance.continuous.incident",
        "load_withdrawal_record",
    ),
    "persist_incident_report": (
        "polisyos.scientist.governance.continuous.incident",
        "persist_incident_report",
    ),
    "persist_withdrawal_record": (
        "polisyos.scientist.governance.continuous.incident",
        "persist_withdrawal_record",
    ),
    "ContinuousInvalidationResult": (
        "polisyos.scientist.governance.continuous.invalidation",
        "ContinuousInvalidationResult",
    ),
    "governance_event_from_source_invalidation": (
        "polisyos.scientist.governance.continuous.invalidation",
        "governance_event_from_source_invalidation",
    ),
    "mark_dependent_claims_stale": (
        "polisyos.scientist.governance.continuous.invalidation",
        "mark_dependent_claims_stale",
    ),
    "ReissuePacket": (
        "polisyos.scientist.governance.continuous.reissue",
        "ReissuePacket",
    ),
    "build_reissue_packet": (
        "polisyos.scientist.governance.continuous.reissue",
        "build_reissue_packet",
    ),
    "load_reissue_packet": (
        "polisyos.scientist.governance.continuous.reissue",
        "load_reissue_packet",
    ),
    "persist_reissue_packet": (
        "polisyos.scientist.governance.continuous.reissue",
        "persist_reissue_packet",
    ),
    "DecisionValidityReport": (
        "polisyos.scientist.governance.continuous.reports",
        "DecisionValidityReport",
    ),
    "build_validity_report": (
        "polisyos.scientist.governance.continuous.reports",
        "build_validity_report",
    ),
    "export_public_validity_report": (
        "polisyos.scientist.governance.continuous.reports",
        "export_public_validity_report",
    ),
    "load_validity_report": (
        "polisyos.scientist.governance.continuous.reports",
        "load_validity_report",
    ),
    "persist_validity_report": (
        "polisyos.scientist.governance.continuous.reports",
        "persist_validity_report",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
