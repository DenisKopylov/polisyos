"""Integration contracts for DDM-15.7."""

from importlib import import_module
from typing import Any

from polisyos.ddm.contracts.events import (
    AffectedFeature,
    AffectedSlice,
    CalibrationAudit,
    DataQualitySignal,
    IncidentPayload,
    MetricDirection,
    MonitoringWindow,
    PerformanceDegradationEvent,
    ReadinessState,
    ReadinessStateEvent,
    RootCauseBundle,
    ShiftDetectedEvent,
    ShiftRiskEvent,
)

_LAZY_EXPORTS = {
    "build_incident_payload": (
        "polisyos.ddm.integration.incident",
        "build_incident_payload",
    ),
    "build_model_registry_record": (
        "polisyos.ddm.integration.model_registry",
        "build_model_registry_record",
    ),
    "build_root_cause_bundle": (
        "polisyos.ddm.integration.incident",
        "build_root_cause_bundle",
    ),
    "evaluate_registry_gate": (
        "polisyos.ddm.integration.model_registry",
        "evaluate_registry_gate",
    ),
    "DDMWindowResult": ("polisyos.ddm.integration.monitor", "DDMWindowResult"),
    "DriftAndDegradationMonitor": (
        "polisyos.ddm.integration.monitor",
        "DriftAndDegradationMonitor",
    ),
    "ModelRegistryReadinessRecord": (
        "polisyos.ddm.integration.model_registry",
        "ModelRegistryReadinessRecord",
    ),
    "RegistryGateDecision": (
        "polisyos.ddm.integration.model_registry",
        "RegistryGateDecision",
    ),
}


def __getattr__(name: str) -> Any:
    """Load incident, registry, and monitor exports on demand."""

    try:
        module_name, attribute_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value

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
    "build_incident_payload",
    "build_model_registry_record",
    "build_root_cause_bundle",
    "evaluate_registry_gate",
]
