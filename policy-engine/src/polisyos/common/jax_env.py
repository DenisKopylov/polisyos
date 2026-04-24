"""Apply process-wide JAX backend defaults for safe local execution.

Importing this module is side-effect free; call `apply_jax_env_defaults()`
before importing JAX-heavy stacks if the process should avoid accidental Metal
backend selection on macOS.
"""

from __future__ import annotations

import os
import sys


def apply_jax_env_defaults() -> None:
    """
    Ensure JAX backend selection is stable for local dev/tests.

    On macOS, JAX often auto-selects `METAL`. In our current setup this backend
    can crash even for basic array creation ops. Default to CPU unless the user
    explicitly opts in to Metal.

    Opt-in:
    - Set `POLICY_ENGINE_ALLOW_JAX_METAL=1`
    - And set `JAX_PLATFORMS=metal` or `JAX_PLATFORM_NAME=metal`
    """

    if sys.platform != "darwin":
        return

    if os.environ.get("POLICY_ENGINE_ALLOW_JAX_METAL") == "1":
        return

    requested = (
        os.environ.get("JAX_PLATFORMS") or os.environ.get("JAX_PLATFORM_NAME") or ""
    ).lower()
    if not requested or "metal" in requested:
        os.environ.setdefault("JAX_PLATFORMS", "cpu")
        os.environ.setdefault("JAX_PLATFORM_NAME", "cpu")
