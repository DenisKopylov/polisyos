"""Stable Scientist package facade for workflow execution and run observability.

The root package intentionally exports a small contract surface:
`run_experiment()` for orchestration, `ExperimentState` as the boundary model
passed across DAG nodes, and the shared observability factories used by tests
and embedding runtimes. Imports are resolved lazily so importing
`polisyos.scientist` does not eagerly initialize optional workflow adapters,
Foundry/Fabric bridges, or governance registries.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "ExperimentState",
    "build_governance_pipeline",
    "discover_scientist_nodes",
    "get_metrics",
    "get_tracer",
    "load_governance_passes",
    "run_experiment",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "ExperimentState": ("polisyos.scientist.orchestration.engine.state", "ExperimentState"),
    "build_governance_pipeline": ("polisyos.scientist.api", "build_governance_pipeline"),
    "discover_scientist_nodes": ("polisyos.scientist.api", "discover_scientist_nodes"),
    "get_metrics": ("polisyos.core.observability", "get_metrics"),
    "get_tracer": ("polisyos.core.observability", "get_tracer"),
    "load_governance_passes": ("polisyos.scientist.api", "load_governance_passes"),
    "run_experiment": ("polisyos.scientist.api", "run_experiment"),
}


def __getattr__(name: str) -> Any:
    """Resolve stable facade exports on first access.

    Args:
        name: Public symbol requested from `polisyos.scientist`.

    Returns:
        Imported symbol cached in the module global namespace.

    Raises:
        AttributeError: If `name` is not part of the stable facade contract.
    """
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.scientist' has no attribute '{name}'")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return eager globals plus lazy facade exports for interactive discovery."""
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
