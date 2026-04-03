"""Expose the stable `execute()` entrypoint for compiled Foundry plans.

`execute` consumes a CAS-backed `ExecuteRequest`, loads the bound runtime
state through the data-plane binding contract, and persists a
`SimulationResult` artifact plus derived runtime artifacts.
"""
from .api import execute

__all__ = ["execute"]
