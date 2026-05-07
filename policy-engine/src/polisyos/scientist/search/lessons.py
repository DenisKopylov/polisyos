"""Compatibility shim for `polisyos.scientist.search.lessons`.

Canonical module: `polisyos.scientist.methods.search.lessons`.
Sunset: 2027-03-02.
"""

from __future__ import annotations

from polisyos.scientist.methods._compat import alias_module as _alias_module

_alias_module(__name__, "polisyos.scientist.methods.search.lessons", globals())
