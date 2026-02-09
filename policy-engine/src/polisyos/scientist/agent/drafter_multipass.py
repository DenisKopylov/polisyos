"""Decomposed module wrapper; implementation moved to `drafter_multipass_parts`."""

from .drafter_multipass_parts import *  # noqa: F401,F403

try:
    from .drafter_multipass_parts import __all__ as __all__
except ImportError:
    pass
