"""Stable adapter facade for default Foundry and Fabric runtime ports.

The package exports the production bridge classes used by workflow builders.
Both bridges are imported lazily so environments that only need Scientist state
or workflow specs do not pay the import cost of connector/security stacks.
"""

from __future__ import annotations

from typing import Any

__all__ = ["DefaultFabricPort", "DefaultFoundryPort"]


def __getattr__(name: str) -> Any:
    """Resolve adapter classes lazily and preserve the package-level contract."""
    if name == "DefaultFabricPort":
        from polisyos.scientist.adapters.fabric_bridge import DefaultFabricPort

        return DefaultFabricPort
    if name == "DefaultFoundryPort":
        from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort

        return DefaultFoundryPort
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
