"""Compatibility shim for `polisyos.scientist.workflows.engine_langgraph`.

Canonical module: `polisyos.scientist.orchestration.workflows.engine_langgraph`.
Sunset: 2026-12-31.
"""

from __future__ import annotations

from polisyos.scientist._internal.compat import alias_module as _alias_module

_alias_module(__name__, "polisyos.scientist.orchestration.workflows.engine_langgraph", globals())
