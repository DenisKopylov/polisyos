"""Compatibility shim for `polisyos.scientist.search.judge_stack`.

Canonical module: `polisyos.scientist.methods.search.judge_stack`.
Sunset: 2027-03-02.
"""

from __future__ import annotations

from polisyos.scientist.methods._compat import alias_module as _alias_module

_alias_module(__name__, "polisyos.scientist.methods.search.judge_stack", globals())
