"""Decomposed module wrapper; implementation moved to `registry_core_parts`."""

from .registry_core_parts import *  # noqa: F401,F403

try:
    from .registry_core_parts import __all__ as __all__
except ImportError:
    pass
