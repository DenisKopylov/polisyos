"""Stable facade for Scientist node implementations registered in workflow DAGs.

The package exposes `builtin_nodes()` as the canonical node inventory used by
workflow builders. Individual node classes live under `nodes.builtins.*` and
declare their state contract through `NodeSpec`.
"""

from __future__ import annotations

from polisyos.scientist.nodes.builtins import builtin_nodes

__all__ = ["builtin_nodes"]
