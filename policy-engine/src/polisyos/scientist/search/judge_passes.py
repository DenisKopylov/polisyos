"""Compatibility shim for `polisyos.scientist.search.judge_passes`.

Canonical module: `polisyos.scientist.methods.search.judge_passes`.
Sunset: 2027-03-02.
"""

from __future__ import annotations

from polisyos.scientist.methods._compat import alias_module as _alias_module

_alias_module(__name__, "polisyos.scientist.methods.search.judge_passes", globals())
