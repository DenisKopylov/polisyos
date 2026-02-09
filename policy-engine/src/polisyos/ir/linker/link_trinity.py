"""Decomposed module wrapper; implementation moved to `link_trinity_parts`."""

from .link_trinity_parts import *  # noqa: F401,F403

try:
    from .link_trinity_parts import __all__ as __all__
except ImportError:
    pass
