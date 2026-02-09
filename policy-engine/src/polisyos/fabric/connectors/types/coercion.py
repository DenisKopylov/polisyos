"""Decomposed module wrapper; implementation moved to `coercion_parts`."""

from .coercion_parts import *  # noqa: F401,F403

try:
    from .coercion_parts import __all__ as __all__
except ImportError:
    pass
