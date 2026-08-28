"""Red-first semantic boundary tests for DS17 obligation coverage.

These C00 witnesses deliberately fail until C01 provides the derived-negative
coverage contract. They name the production mutations that the eventual
behavioral implementations must reject; C00 does not add a coverage producer.
"""

from __future__ import annotations

import importlib.util

import pytest


def _obligation_coverage_required(test_name: str, mutation: str) -> None:
    """Fail as a collected red until C01 supplies obligation coverage behavior."""
    if importlib.util.find_spec("polisyos.runtime.quality.obligation_coverage") is None:
        pytest.fail(
            "DS17 obligation-coverage behavior is absent for "
            f"{test_name}. Production mutation caught: {mutation}. "
            "C01 must provide the derived-negative coverage contract."
        )


def test_every_delta_amount_requires_the_coverage_envelope_ref_and_rider() -> None:
    """Reject an amount that lacks a resolved, content-bound envelope and rider."""
    _obligation_coverage_required(
        "conditional delta binding",
        "a delta amount can be constructed without its exact envelope reference, "
        "declared-set rider, and local-scope/no-family disclosure",
    )


def test_coverage_assessment_moves_on_admitted_witness() -> None:
    """Require only an admitted exact-scope witness to move the negative arm."""
    _obligation_coverage_required(
        "admitted witness assessment",
        "a label, shaped value, or cross-scope witness changes coverage instead of "
        "a resolved, content-bound, verifier-provenance witness receipt",
    )


def test_negative_coverage_cannot_be_rescued_by_claim_narrowing() -> None:
    """Keep an already-negative action blocked after its displayed claim narrows."""
    _obligation_coverage_required(
        "anti-narrowing coverage veto",
        "a negative envelope becomes satisfied because a caller narrows only the "
        "displayed claim or per-class headroom without admitting a new action",
    )
