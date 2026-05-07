"""Compatibility facade for legacy method loss helper."""

from ._internal.reexport import reexport_module as _reexport_module

__all__ = _reexport_module(__name__, "polisyos.foundry.methods._internal.loss", globals())
