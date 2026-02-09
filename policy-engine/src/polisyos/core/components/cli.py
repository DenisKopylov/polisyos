"""Decomposed module wrapper; implementation moved to `cli_parts`."""

from .cli_parts import *  # noqa: F401,F403

try:
    from .cli_parts import __all__ as __all__
except ImportError:
    pass
