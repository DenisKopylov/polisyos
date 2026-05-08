"""Compatibility shim for IC verification services."""

from __future__ import annotations

from polisyos.scientist._internal.compat import alias_module as _alias_module

_alias_module(__name__, "polisyos.scientist.validation.verification.ic.service", globals())
