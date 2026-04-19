"""Expose the stable Core platform surface with lazy package imports.

The Core package owns CAS artifacts, component discovery, registry assembly,
security/observability primitives, and cross-layer contracts shared by runtime
and domain subsystems. Subpackages are imported lazily so `import polisyos.core`
remains safe in CLI/bootstrap paths that do not need optional heavy dependencies.

Only names listed in `__all__` are considered stable package-level API.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from . import (
        artifacts,
        backends,
        cache,
        canon,
        components,
        contracts,
        discovery,
        errors,
        evaluation,
        llm,
        observability,
        pipeline,
        registry,
        resilience,
        run,
    )

__all__ = [
    "artifacts",
    "backends",
    "cache",
    "canon",
    "components",
    "contracts",
    "discovery",
    "evaluation",
    "errors",
    "llm",
    "observability",
    "pipeline",
    "resilience",
    "registry",
    "run",
]


def __getattr__(name: str) -> Any:
    """Import one exported Core subpackage on first attribute access.

    Args:
        name: Subpackage name listed in `__all__`.

    Returns:
        The imported module cached on the package namespace.

    Raises:
        AttributeError: If `name` is not part of the stable facade surface.
    """
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(f"{__name__}.{name}")
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    """Return regular globals plus lazily exported subpackage names."""
    return sorted(list(globals().keys()) + __all__)
