"""Compatibility facade for method selection history."""

from ._internal.reexport import reexport_module as _reexport_module

__all__ = _reexport_module(__name__, "polisyos.foundry.methods.selection.history", globals())
