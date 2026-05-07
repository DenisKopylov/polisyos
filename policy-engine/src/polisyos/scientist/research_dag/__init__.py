"""Compatibility shim for `polisyos.scientist.research_dag`.

Canonical package: `polisyos.scientist.methods.research_dag`.
Sunset: 2027-03-02.
"""

from __future__ import annotations

from polisyos.scientist.methods._compat import reexport_package as _reexport_package

_reexport_package(__name__, "polisyos.scientist.methods.research_dag", globals())
