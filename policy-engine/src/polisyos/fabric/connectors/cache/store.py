"""Decomposed module wrapper; implementation moved to `store_parts`."""

from .store_parts import *  # noqa: F401,F403

try:
    from .store_parts import __all__ as __all__
except ImportError:
    pass
