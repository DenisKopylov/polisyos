"""Expose the stable `execute()` entrypoint for compiled Foundry plans.

`execute` consumes a CAS-backed `ExecuteRequest`, loads the bound runtime
state through the data-plane binding contract, and persists a
`SimulationResult` artifact plus derived runtime artifacts.
"""

import sys

from .api import execute

__all__ = ["execute"]

parent = sys.modules.get("polisyos.foundry")
if parent is not None:
    parent.__dict__["execute"] = execute
