#!/usr/bin/env python3
"""Ops-facing owner for Ukraine server bootstrap composition.

The domain owns the typed configuration and capability manifest contracts.
This module is the executable-side seam that composes those contracts for a
remote server workflow; it intentionally does not import the ops layer from
``src/polisyos``.
"""

from __future__ import annotations

from polisyos.data_forge.domains.ukraine.models import BuildRootConfig, ServerConfig
from polisyos.data_forge.domains.ukraine.server import (
    build_bootstrap_script,
    probe_local_server_capabilities,
)

__all__ = [
    "build_bootstrap_script",
    "probe_local_server_capabilities",
    "render_bootstrap_script",
]


def render_bootstrap_script(config: ServerConfig, build_root: BuildRootConfig) -> str:
    """Render the reviewed server bootstrap command through the ops seam."""

    return build_bootstrap_script(config, build_root)
