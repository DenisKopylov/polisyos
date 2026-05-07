"""Compatibility facade for method compatibility matrix helpers."""

from ._internal.reexport import reexport_module as _reexport_module

__all__ = _reexport_module(
    __name__, "polisyos.foundry.methods.lifecycle.compat_matrix", globals()
)
