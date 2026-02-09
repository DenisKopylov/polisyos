"""Decomposed module wrapper; implementation moved to `units_parts`."""

from .units_parts import *  # noqa: F401,F403

try:
    from .units_parts import __all__ as __all__
except ImportError:
    pass
