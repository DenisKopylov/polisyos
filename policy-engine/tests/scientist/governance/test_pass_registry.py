from __future__ import annotations

import pytest

from polisyos.core.governance.profiles import ValidationProfile
from polisyos.scientist.governance.pass_registry import (
    RUNTIME_ALLOWED_PASS_IDS,
    build_governance_pipeline,
    load_governance_passes,
    runtime_profile,
)
from polisyos.scientist.governance.passes.budget_pass import BudgetPass


class _FakeEntryPoint:
    def __init__(self, name: str, target) -> None:
        self.name = name
        self._target = target

    def load(self):
        return self._target


def test_load_governance_passes_contains_required_passes() -> None:
    pass_ids = {validator.pass_id for validator in load_governance_passes()}
    assert {
        "budget",
        "schema",
        "privacy",
        "pii_check",
        "sutva_check",
        "transportability_required",
        "safety",
        "equity",
        "literature_gate",
        "legal",
        "confidence",
        "refutation",
        "human_review_required",
        "quality",
    }.issubset(pass_ids)

    pipeline = build_governance_pipeline()
    assert set(pipeline.available_passes) == pass_ids


def test_runtime_profile_filters_to_runtime_allowed_pass_ids() -> None:
    strict = ValidationProfile.strict()
    filtered = runtime_profile(strict)

    assert filtered.level == strict.level
    assert filtered.short_circuit_on_blocker == strict.short_circuit_on_blocker
    assert filtered.pass_ids.issubset(RUNTIME_ALLOWED_PASS_IDS)
    assert "transportability_required" in filtered.pass_ids
    assert "schema" not in filtered.pass_ids


def test_load_governance_passes_fails_fast_on_duplicate_pass_id(monkeypatch) -> None:
    monkeypatch.setattr(
        "polisyos.scientist.governance.pass_registry.list_entry_points",
        lambda *, group: [
            _FakeEntryPoint("dup_a", lambda: BudgetPass()),
            _FakeEntryPoint("dup_b", lambda: BudgetPass()),
        ],
    )

    with pytest.raises(ValueError, match="Duplicate governance pass_id 'budget'"):
        load_governance_passes()
