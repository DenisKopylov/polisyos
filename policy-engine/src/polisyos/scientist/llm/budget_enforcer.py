"""Compatibility shim for `polisyos.scientist.llm.budget_enforcer`.

Canonical module: `polisyos.scientist.orchestration.llm.budget_enforcer`.
Sunset: 2026-12-31.
"""

from __future__ import annotations

from polisyos.scientist._internal.compat import alias_module as _alias_module

_alias_module(__name__, "polisyos.scientist.orchestration.llm.budget_enforcer", globals())
