from __future__ import annotations

__all__ = ["DefaultFoundryPort"]


def __getattr__(name: str):
    if name == "DefaultFoundryPort":
        from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort

        return DefaultFoundryPort
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
