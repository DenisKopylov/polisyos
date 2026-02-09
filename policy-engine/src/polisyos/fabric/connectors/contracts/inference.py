"""Decomposed module wrapper; implementation moved to `inference_parts`."""

from .inference_parts import *  # noqa: F401,F403

try:
    from .inference_parts import __all__ as __all__
except ImportError:
    pass
