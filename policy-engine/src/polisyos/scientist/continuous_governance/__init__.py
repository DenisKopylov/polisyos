"""Compatibility shim for `polisyos.scientist.continuous_governance`."""

from __future__ import annotations

from polisyos.scientist._internal.compat import reexport_package as _reexport_package

_reexport_package(__name__, "polisyos.scientist.governance.continuous", globals())
