"""Decomposed module wrapper; implementation moved to `executor_parts`."""

from .executor_parts import *  # noqa: F401,F403

try:
    from .executor_parts import __all__ as __all__
except ImportError:
    pass
