"""Shared fixtures for Foundry methods property tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_backend_circuit_breakers():
    """Keep backend circuit-breaker state from leaking across property cases."""
    from polisyos.foundry.methods.backends.circuit_breaker import CircuitBreakerRegistry

    CircuitBreakerRegistry.reset_instance()
    yield
    CircuitBreakerRegistry.reset_instance()


@pytest.fixture
def isolated_registry():
    """Provide an isolated, fully populated method registry for one test."""
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered
    from polisyos.foundry.methods.registry import registry_scope

    with registry_scope() as reg:
        ensure_all_methods_registered(reg)
        yield reg


fresh_registry = isolated_registry
