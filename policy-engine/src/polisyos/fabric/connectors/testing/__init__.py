"""
Connector Testing Infrastructure -- Phase 2.10.

Public API for the shared test harness that gives connector developers
automatic protocol compliance, schema validation, resilience verification,
and consumer-contract checking without boilerplate.
"""

from polisyos.fabric.connectors.testing.conformance import (
    ConformanceIssue,
    ConformanceReport,
    ConnectorConformanceHarnessV2,
    validate_source_conformance_v2,
)
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
    # Simulator -- record / replay / synthetic API mocking
    "APISimulator",
    "ConformanceIssue",
    "ConformanceReport",
    "ConnectorConformanceHarnessV2",
    # Harness -- the primary entry-point for connector developers
    "ConnectorTestHarness",
    "ContractViolation",
    # Fault injection -- chaos testing for resilience verification
    "FaultInjector",
    "FaultProfile",
    "FaultSequence",
    "MissingFixtureError",
    "SimulatedHTTPError",
    "SimulatorFixture",
    "SimulatorMode",
    # Contract verification
    "assert_schema_compliance",
    "validate_source_conformance_v2",
]
