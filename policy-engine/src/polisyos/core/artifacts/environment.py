"""Decomposed module wrapper; implementation moved to `environment_parts`."""

from .environment_parts import *  # noqa: F401,F403

try:
    from .environment_parts import __all__ as __all__
except ImportError:
    pass
