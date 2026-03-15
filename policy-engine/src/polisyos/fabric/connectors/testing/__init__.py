"""
Connector Testing Infrastructure -- Phase 2.10.

Public API for the shared test harness that gives connector developers
automatic protocol compliance, schema validation, resilience verification,
and consumer-contract checking without boilerplate.
"""

from polisyos.fabric.connectors.testing.contracts import (
    ContractViolation,
    assert_schema_compliance,
)
from polisyos.fabric.connectors.testing.fixtures import (
    FaultInjector,
    FaultProfile,
    FaultSequence,
    SimulatedHTTPError,
)
from polisyos.fabric.connectors.testing.harness import ConnectorTestHarness
from polisyos.fabric.connectors.testing.simulator import (
    APISimulator,
    MissingFixtureError,
    SimulatorFixture,
    SimulatorMode,
)

__all__ = [
    # Harness -- the primary entry-point for connector developers
    "ConnectorTestHarness",
    # Simulator -- record / replay / synthetic API mocking
    "APISimulator",
    "SimulatorMode",
    "SimulatorFixture",
    "MissingFixtureError",
    # Fault injection -- chaos testing for resilience verification
    "FaultInjector",
    "FaultProfile",
    "FaultSequence",
    "SimulatedHTTPError",
    # Contract verification
    "assert_schema_compliance",
    "ContractViolation",
]
