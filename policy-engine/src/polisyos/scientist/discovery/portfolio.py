"""Compatibility shim for `polisyos.scientist.discovery.portfolio`.

Canonical module: `polisyos.scientist.methods.discovery.portfolio`.
Sunset: 2027-03-02.
"""

from __future__ import annotations

from polisyos.scientist.methods._compat import alias_module as _alias_module

_alias_module(__name__, "polisyos.scientist.methods.discovery.portfolio", globals())
