"""Public scientist adapters package API."""
from __future__ import annotations

__all__ = ["DefaultFabricPort", "DefaultFoundryPort"]


def __getattr__(name: str):
    if name == "DefaultFabricPort":
        from polisyos.scientist.adapters.fabric_bridge import DefaultFabricPort

        return DefaultFabricPort
    if name == "DefaultFoundryPort":
        from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort

        return DefaultFoundryPort
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
