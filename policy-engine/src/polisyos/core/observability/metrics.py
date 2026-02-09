"""Decomposed module wrapper; implementation moved to `metrics_parts`."""

from .metrics_parts import *  # noqa: F401,F403

try:
    from .metrics_parts import __all__ as __all__
except ImportError:
    pass
