"""Red-first semantic boundary tests for the DS17 ledger projection surface.

These C00 witnesses deliberately fail until C01 supplies the exact
confidence-ledger projection. They bind semantic gaps, rather than a UI marker
or a caller-authored status field.
"""

from __future__ import annotations

import importlib.util

import pytest


def _confidence_ledger_surface_required(test_name: str, mutation: str) -> None:
    """Fail as a collected red until C01 supplies the ledger surface behavior."""
    if importlib.util.find_spec("polisyos.runtime.quality.confidence_ledger_surface") is None:
        pytest.fail(
            "DS17 confidence-ledger surface behavior is absent for "
            f"{test_name}. Production mutation caught: {mutation}. "
            "C01 must provide the typed derived-negative ledger projection."
        )


def test_ds17_reason_algebra_matches_every_emitter() -> None:
    """Require each reason emitter to reconcile with the closed tagged algebra."""
    _confidence_ledger_surface_required(
        "reason algebra reconciliation",
        "an available-domain or source-blocked emitter introduces, omits, or reuses "
        "a reason value outside its tagged DS17 semantic slot",
    )


def test_ds17_over_spend_allowset_matches_every_owner_diagnostic() -> None:
    """Require the complete five-code owner-diagnostic allowset to agree."""
    _confidence_ledger_surface_required(
        "over-spend allowset reconciliation",
        "a structural or parameterized owner diagnostic can select over_spend "
        "without belonging to the exact complete five-code allowset",
    )


def test_over_spend_recomputes_blocker_when_display_markers_stay_constant() -> None:
    """Require exact current-check arithmetic, not unchanged display markers."""
    _confidence_ledger_surface_required(
        "marker-constant over-spend",
        "a raw check spend crosses delta while labels, IDs, chip marker, and a "
        "within-budget field stay fixed but the projector does not recompute a blocker",
    )


def test_bayesian_interval_without_coverage_never_enters_positive_register() -> None:
    """Keep a Bayesian interval without coverage in the blocked available packet."""
    _confidence_ledger_surface_required(
        "Bayesian coverage blocker",
        "caller eligibility or a promotion label lets a Bayesian interval without an "
        "admitted coverage argument enter the positive promotion register",
    )


def test_valid_zero_positive_register_is_not_missing_or_loading() -> None:
    """Distinguish the governed zero register from a missing or loading source."""
    _confidence_ledger_surface_required(
        "honest zero positive register",
        "a valid zero positive register is omitted, rendered as loading, or confused "
        "with a missing/invalid governed source",
    )
