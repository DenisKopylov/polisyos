"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "DecisionFeedbackService",
    "FeedbackArtifacts",
    "build_monitoring_contract_from_packet",
    "build_parameter_override_bundle",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "DecisionFeedbackService": ("polisyos.scientist.feedback.core", "DecisionFeedbackService"),
    "FeedbackArtifacts": ("polisyos.scientist.feedback.core", "FeedbackArtifacts"),
    "build_monitoring_contract_from_packet": (
        "polisyos.scientist.feedback.core",
        "build_monitoring_contract_from_packet",
    ),
    "build_parameter_override_bundle": (
        "polisyos.scientist.feedback.core",
        "build_parameter_override_bundle",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.scientist.feedback' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
