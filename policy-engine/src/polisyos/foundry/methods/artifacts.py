"""Decomposed module wrapper; implementation moved to `artifacts_parts`."""

from .artifacts_parts import *

try:
    from .artifacts_parts import __all__ as __all__
except ImportError:
    pass
