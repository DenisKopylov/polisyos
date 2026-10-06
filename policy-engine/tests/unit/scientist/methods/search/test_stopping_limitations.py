"""Plateau admission limits do not prevent independent resource stops."""

import pytest

from polisyos.scientist.methods.search.stopping import ImprovementPlateau, StoppingPresets


def test_missing_unit_cannot_claim_objective_convergence() -> None:
    result = ImprovementPlateau(patience=2).check([{"objective_value": 1.0}] * 3, {})
    assert not result.should_stop
    assert result.details["adequacy_status"] == "not_established"


def test_missing_profile_cannot_claim_objective_convergence() -> None:
    result = ImprovementPlateau(patience=2, objective_unit="points", profile_version=None).check(
        [{"objective_value": 1.0}] * 3, {}
    )
    assert not result.should_stop


def test_standard_preset_still_honors_budget_without_objective_unit() -> None:
    stopping = StoppingPresets.default(max_iter=3)
    result = stopping.check([{"objective_value": 1.0}] * 3, {"evaluation_iterations": 3})
    assert result.should_stop
    assert "Maximum iterations" in result.reason


@pytest.mark.parametrize("patience", [True, False, 1.5, "2"])
def test_malformed_patience_is_rejected(patience: object) -> None:
    with pytest.raises(ValueError, match="patience"):
        ImprovementPlateau(patience=patience, objective_unit="points")
