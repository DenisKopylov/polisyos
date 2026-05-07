"""Compatibility facade for the canonical method registry."""

from ._internal.reexport import reexport_module as _reexport_module

__all__ = _reexport_module(__name__, "polisyos.foundry.methods.selection.registry", globals())
