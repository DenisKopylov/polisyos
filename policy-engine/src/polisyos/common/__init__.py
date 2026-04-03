"""Expose side-effect-sensitive common helpers behind a lazy package facade.

`polisyos.common` groups logger setup, environment parsing, serialization,
timestamp helpers, and migration primitives shared across platform packages.
Lazy submodule loading keeps `import polisyos.common` safe in code paths that
do not want `polisyos.common.config` import-time environment mutations.

The subpackages listed in `__all__` form the supported facade surface.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "async_tools",
    "config",
    "jax_env",
    "logger",
    "migrations",
    "serialization",
    "timestamps",
]


def __getattr__(name: str) -> Any:
    """Import one common helper module on demand."""
    if name not in __all__:
        raise AttributeError(f"module 'polisyos.common' has no attribute '{name}'")
    module = importlib.import_module(f"{__name__}.{name}")
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    """Return loaded globals plus lazy helper module names."""
    return sorted(list(globals().keys()) + __all__)
