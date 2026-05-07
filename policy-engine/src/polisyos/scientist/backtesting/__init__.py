"""Compatibility shim for `polisyos.scientist.backtesting`.

Canonical package: `polisyos.scientist.methods.backtesting`.
Sunset: 2026-12-31.
"""

from __future__ import annotations

from polisyos.scientist._internal.compat import reexport_package as _reexport_package

_reexport_package(__name__, "polisyos.scientist.methods.backtesting", globals())
