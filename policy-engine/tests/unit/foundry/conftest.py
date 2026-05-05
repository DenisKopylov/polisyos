"""Foundry test fixtures shared across tests/unit/foundry/."""

from __future__ import annotations

import pytest
from polisyos.foundry.methods.backends.circuit_breaker import CircuitBreakerRegistry
from polisyos.foundry.methods.registry import registry_scope


@pytest.fixture(autouse=True)
def _isolated_backend_circuit_breakers():
    """Keep backend circuit-breaker state from leaking across Foundry tests."""
    CircuitBreakerRegistry.reset_instance()
    yield
    CircuitBreakerRegistry.reset_instance()


@pytest.fixture(scope="module")
def module_registry():
    """
    Module-scoped registry with all catalog methods registered.

    Used by tests that need a fully-populated registry but don't need
    per-test isolation (avoids re-registering 200+ methods per test).
    """
    with registry_scope() as reg:
        from polisyos.foundry.methods.catalog import ensure_all_methods_registered

        ensure_all_methods_registered(reg)
        yield reg
