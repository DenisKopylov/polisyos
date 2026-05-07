"""Compatibility shim for `polisyos.scientist.engine.runner._activity_worker`.

Canonical module: `polisyos.scientist.orchestration.engine.runner._activity_worker`.
Sunset: 2026-12-31.
"""

from __future__ import annotations

from polisyos.scientist._internal.compat import alias_module as _alias_module

_alias_module(__name__, "polisyos.scientist.orchestration.engine.runner._activity_worker", globals())
