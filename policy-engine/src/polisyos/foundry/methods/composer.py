"""Compatibility facade for method composition APIs."""

from ._internal.reexport import reexport_module as _reexport_module

__all__ = _reexport_module(__name__, "polisyos.foundry.methods.components.composer", globals())
