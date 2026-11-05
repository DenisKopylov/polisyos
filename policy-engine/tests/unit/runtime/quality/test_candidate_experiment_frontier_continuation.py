"""Deterministic continuation input helpers for candidate experiment history."""

from __future__ import annotations

from types import SimpleNamespace

from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
    _candidate_experiment_inherited_limitations,
)


def test_inherited_limitations_keep_first_encounter_order_across_prefix() -> None:
    """A retry derives the same ordered limitations from its complete prefix."""
    origin = SimpleNamespace(
        candidate_terminal_history_chain=(
            SimpleNamespace(
                selected_basis=SimpleNamespace(limitations=("root", "shared")),
                current_basis=SimpleNamespace(limitations=("current-a", "shared")),
                continuation=SimpleNamespace(limitations=("cheap-a", "shared")),
            ),
            SimpleNamespace(
                selected_basis=SimpleNamespace(limitations=("selected-b", "root")),
                current_basis=SimpleNamespace(limitations=("current-b",)),
                continuation=SimpleNamespace(limitations=("cheap-b", "shared")),
            ),
        )
    )

    assert _candidate_experiment_inherited_limitations(origin) == (
        "root",
        "shared",
        "current-a",
        "cheap-a",
        "selected-b",
        "current-b",
        "cheap-b",
    )
