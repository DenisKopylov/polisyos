"""Foundry test fixtures shared across tests/foundry/."""
from __future__ import annotations

import pytest

from polisyos.foundry.methods.registry import MethodRegistry, registry_scope


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
