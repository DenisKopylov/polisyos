"""
Import this module before importing `jax` anywhere in this repo.

Reason:
On macOS JAX may auto-select the experimental `METAL` backend, which currently
crashes in our environment with: `UNIMPLEMENTED: default_memory_space is not supported.`

This module applies safe defaults (CPU on macOS) unless explicitly overridden.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from polisyos.common.jax_env import apply_jax_env_defaults

apply_jax_env_defaults()
