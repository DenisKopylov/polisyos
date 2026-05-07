"""Stable facade for pure causal runners used by Scientist nodes.

These exports operate on IR observation bundles and persist analytics artifacts
without mutating `ExperimentState` directly. Node adapters in
`polisyos.scientist.nodes.builtins.causal` call these runners to prepare
governance-ready readiness bundles and bounded-execution outputs.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "BoundsEstimationRunner",
    "CounterfactualQueryRunner",
    "ProxyIdentificationRunner",
    "StrategicResponseRunner",
    "TransportabilityChecker",
    "build_interference_readiness_entries",
    "persist_causal_validity_bundle",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "BoundsEstimationRunner": ("polisyos.scientist.methods.causal.execution", "BoundsEstimationRunner"),
    "CounterfactualQueryRunner": (
        "polisyos.scientist.methods.causal.readiness",
        "CounterfactualQueryRunner",
    ),
    "ProxyIdentificationRunner": (
        "polisyos.scientist.methods.causal.readiness",
        "ProxyIdentificationRunner",
    ),
    "StrategicResponseRunner": (
        "polisyos.scientist.methods.causal.readiness",
        "StrategicResponseRunner",
    ),
    "TransportabilityChecker": (
        "polisyos.scientist.methods.causal.readiness",
        "TransportabilityChecker",
    ),
    "build_interference_readiness_entries": (
        "polisyos.scientist.methods.causal.readiness",
        "build_interference_readiness_entries",
    ),
    "persist_causal_validity_bundle": (
        "polisyos.scientist.methods.causal.validity",
        "persist_causal_validity_bundle",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.scientist.methods.causal' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
