"""Compatibility shim for `polisyos.scientist.engine.context`.

Canonical module: `polisyos.scientist.orchestration.engine.context`.
Sunset: 2026-12-31.
"""

from __future__ import annotations

from polisyos.scientist._internal.compat import alias_module as _alias_module

_alias_module(__name__, "polisyos.scientist.orchestration.engine.context", globals())
