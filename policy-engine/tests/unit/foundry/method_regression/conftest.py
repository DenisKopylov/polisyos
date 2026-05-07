"""Fixtures for YAML-based golden regression tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.methods.testing.golden_yaml import GoldenRegistry


@pytest.fixture(scope="session")
def golden_registry() -> GoldenRegistry:
    """Session-scoped registry of all YAML golden test cases."""
    return GoldenRegistry(Path(__file__).resolve().parents[3] / "_golden" / "foundry" / "methods")


@pytest.fixture(scope="session")
def full_method_registry() -> MethodRegistry:
    """Session-scoped method registry with all catalog domains loaded."""
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered

    reg = MethodRegistry.get_instance()
    ensure_all_methods_registered(reg)
    return reg
