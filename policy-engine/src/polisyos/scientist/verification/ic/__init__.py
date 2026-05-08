"""Compatibility shim for IC verification moved to validation.verification.ic."""

from __future__ import annotations

from polisyos.scientist._internal.compat import reexport_package as _reexport_package

_reexport_package(__name__, "polisyos.scientist.validation.verification.ic", globals())
