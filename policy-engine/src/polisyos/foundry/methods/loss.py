"""Compatibility facade for the named economics loss baseline."""

from ._internal.reexport import reexport_module as _reexport_module

__all__ = _reexport_module(__name__, "polisyos.foundry.methods._internal.loss", globals())
