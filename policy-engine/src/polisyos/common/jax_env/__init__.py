"""Apply process-wide JAX backend defaults for safe local execution.

Importing this module is side-effect free; call `apply_jax_env_defaults()`
before importing JAX-heavy stacks if the process should avoid accidental Metal
backend selection on macOS.
"""

from __future__ import annotations

import os
import sys

from ._policy import should_default_cpu_backend as _should_default_cpu_backend


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
    if not _should_default_cpu_backend(
        platform=sys.platform,
        allow_metal=os.environ.get("POLICY_ENGINE_ALLOW_JAX_METAL"),
        platforms=os.environ.get("JAX_PLATFORMS"),
        platform_name=os.environ.get("JAX_PLATFORM_NAME"),
    ):
        return
    os.environ.setdefault("JAX_PLATFORMS", "cpu")
    os.environ.setdefault("JAX_PLATFORM_NAME", "cpu")
