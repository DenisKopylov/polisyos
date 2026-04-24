"""
Golden regression tests — YAML-driven known-answer verification.

Each test case is defined in a YAML file in this directory and verified
against the corresponding FoundryMethod.pure_step output.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.foundry.methods.testing.golden_yaml import (
    GoldenRegistry,
    GoldenTestCase,
)


def _load_all_cases() -> list[GoldenTestCase]:
    """Load cases at module level for parametrize (runs once at collection)."""
    reg = GoldenRegistry(Path(__file__).parent)
    return reg.all_cases()


_ALL_CASES = _load_all_cases()


@pytest.mark.parametrize("case", _ALL_CASES, ids=lambda c: c.id)
def test_golden_case(case, full_method_registry, golden_registry):
    """Verify a single golden test case."""
    if case.skip_reason:
        pytest.skip(case.skip_reason)
    result = golden_registry.verify_case(case, full_method_registry)
    assert result.passed, (
        f"Golden regression FAILED for {case.id} ({case.method_fqn}):\n"
        f"  {result.message}\n" + "\n".join(f"  - {m}" for m in result.mismatches)
    )
