"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "WORKSTREAM_IDS",
    "RemediationStatusLevel",
    "ScientistPhaseStatus",
    "ScientistRemediationStatusReport",
    "ScientistWorkstreamStatus",
    "build_scientist_remediation_status_report",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "RemediationStatusLevel": (
        "polisyos.scientist.governance.remediation_status",
        "RemediationStatusLevel",
    ),
    "ScientistPhaseStatus": (
        "polisyos.scientist.governance.remediation_status",
        "ScientistPhaseStatus",
    ),
    "ScientistRemediationStatusReport": (
        "polisyos.scientist.governance.remediation_status",
        "ScientistRemediationStatusReport",
    ),
    "ScientistWorkstreamStatus": (
        "polisyos.scientist.governance.remediation_status",
        "ScientistWorkstreamStatus",
    ),
    "WORKSTREAM_IDS": ("polisyos.scientist.governance.remediation_status", "WORKSTREAM_IDS"),
    "build_scientist_remediation_status_report": (
        "polisyos.scientist.governance.remediation_status",
        "build_scientist_remediation_status_report",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(
            f"module 'polisyos.scientist.remediation_status' has no attribute {name!r}"
        )
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
