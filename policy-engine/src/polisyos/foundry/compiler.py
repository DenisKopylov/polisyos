"""Deprecated Foundry compiler module.

Legacy surface compiler entrypoints were removed in Stage 3.
Use `polisyos.foundry.compile.api.compile` with Trinity artifacts.
"""
from __future__ import annotations

from polisyos.foundry.compile._graph import build_exec_order as _build_exec_order

__all__ = ["_build_exec_order"]


def __getattr__(name: str):
    raise AttributeError(
        "polisyos.foundry.compiler legacy API was removed. "
        "Use polisyos.foundry.compile.api.compile with Trinity CompileRequest."
    )
