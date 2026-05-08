"""Compatibility facade for :mod:`polisyos.ddm`.

The implementation moved to the unversioned package name during Repository
Structure Remediation Phase 4A. Keep this root import available until the
2026-07-31 shim sunset; deep ``polisyos.ddm_15_7.*`` imports are internal and
must migrate to ``polisyos.ddm.*``.
"""

from polisyos.ddm import (
    AffectedFeature,
    AffectedSlice,
    CalibrationAudit,
    DataQualitySignal,
    DDMWindowResult,
    DriftAndDegradationMonitor,
    IncidentPayload,
    MetricDirection,
    ModelRegistryReadinessRecord,
    MonitoringWindow,
    PerformanceDegradationEvent,
    ReadinessState,
    ReadinessStateEvent,
    RegistryGateDecision,
    RootCauseBundle,
    ShiftDetectedEvent,
    ShiftRiskEvent,
)

__all__ = [
    "AffectedFeature",
    "AffectedSlice",
    "CalibrationAudit",
    "DDMWindowResult",
    "DataQualitySignal",
    "DriftAndDegradationMonitor",
    "IncidentPayload",
    "MetricDirection",
    "ModelRegistryReadinessRecord",
    "MonitoringWindow",
    "PerformanceDegradationEvent",
    "ReadinessState",
    "ReadinessStateEvent",
    "RegistryGateDecision",
    "RootCauseBundle",
    "ShiftDetectedEvent",
    "ShiftRiskEvent",
]
