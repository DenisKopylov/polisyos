"""Decomposed module wrapper; implementation moved to `assembler_parts`."""

from .assembler_parts import *  # noqa: F401,F403

try:
    from .assembler_parts import __all__ as __all__
except ImportError:
    pass
