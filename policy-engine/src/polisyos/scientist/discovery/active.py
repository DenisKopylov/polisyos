"""Compatibility shim for `polisyos.scientist.discovery.active`.

Canonical module: `polisyos.scientist.methods.discovery.active`.
Sunset: 2027-03-02.
"""

from __future__ import annotations

from polisyos.scientist.methods._compat import alias_module as _alias_module

_alias_module(__name__, "polisyos.scientist.methods.discovery.active", globals())
