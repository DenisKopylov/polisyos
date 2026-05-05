from __future__ import annotations

import pytest
from polisyos.foundry.contracts.fidelity import FidelityLevel


class TestFidelityLevel:
    def test_fidelity_values_match_expected(self) -> None:
        assert FidelityLevel.SURROGATE_FLUID.value == "fluid"
        assert FidelityLevel.RELAXED_DISCRETE.value == "relaxed"
        assert FidelityLevel.HARD_DISCRETE.value == "hard"
        assert len(FidelityLevel) == 3

    def test_fidelity_from_string(self) -> None:
        assert FidelityLevel("fluid") is FidelityLevel.SURROGATE_FLUID
        assert FidelityLevel("relaxed") is FidelityLevel.RELAXED_DISCRETE
        assert FidelityLevel("hard") is FidelityLevel.HARD_DISCRETE

    def test_fidelity_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            FidelityLevel("nonexistent")
