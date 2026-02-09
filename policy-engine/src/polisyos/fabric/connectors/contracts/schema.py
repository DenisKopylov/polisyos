"""Decomposed module wrapper; implementation moved to `schema_parts`."""

from .schema_parts import *  # noqa: F401,F403

try:
    from .schema_parts import __all__ as __all__
except ImportError:
    pass
