"""Deprecated compatibility shim for `catalog.causal.scm`.

Canonical implementation lives in `catalog.causal.synthetic_control`.
"""

from .synthetic_control import *  # noqa: F401,F403

__all__: list[str] = []
