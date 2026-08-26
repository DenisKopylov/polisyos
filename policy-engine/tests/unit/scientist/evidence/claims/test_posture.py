"""Red-first semantic boundary tests for the DS11 trust-claim posture contract.

These tests deliberately fail until C01 supplies the distinct posture contract.
They name the production mutations they must catch; C00 must not implement that
contract or modify the runtime-owned claim registry.
"""

from __future__ import annotations

import importlib.util

import pytest


def _posture_contract_required(test_name: str, mutation: str) -> None:
    """Fail as a collected behavioral red until C01 provides the posture contract."""
    if importlib.util.find_spec("polisyos.scientist.evidence.claims.posture") is None:
        pytest.fail(
            "DS11 posture behavior is absent for "
            f"{test_name}. Production mutation caught: {mutation}. "
            "C01 must provide the distinct posture contract."
        )


def test_blocked_vetoes_planned_and_supported() -> None:
    """Catch a composer mutation that lets a blocked arm lose its veto."""
    _posture_contract_required(
        "blocked veto",
        "effective-state composition accepts a blocked predicate beside planned or supported",
    )


def test_candidate_or_planned_never_composes_to_supported() -> None:
    """Catch a composer mutation that treats candidate or planned as support."""
    _posture_contract_required(
        "candidate/planned promotion",
        "effective-state composition promotes candidate or planned evidence to supported",
    )


def test_grounded_performance_requires_governed_evidence_and_prerequisite() -> None:
    """Catch a mutation that admits a performance claim without governed evidence."""
    _posture_contract_required(
        "grounded-performance prerequisite",
        "posture admission accepts grounded performance without its governed evidence prerequisite",
    )


def test_posture_artifact_cannot_enter_runtime_claim_registry() -> None:
    """Catch an adapter mutation that lets posture artifacts enter the per-run registry."""
    _posture_contract_required(
        "CC09 posture-to-runtime-registry rejection",
        "RuntimeClaimRegistry admits a DS11 posture claim or posture artifact as a per-run binding",
    )
