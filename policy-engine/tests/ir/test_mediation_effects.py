from __future__ import annotations

import pytest

from polisyos.ir.analytics.mediation_effects import MediationDecomposition, PathSpecificQuery


def test_mediation_decomposition_normalizes_proportion_mediated_consistently() -> None:
    result = MediationDecomposition(
        nde=0.3,
        nie=0.1,
        total_effect=0.4,
        nde_ci=(0.2, 0.4),
        nie_ci=(0.05, 0.15),
    )

    assert result.proportion_mediated == pytest.approx(0.25)
    assert result.model_copy(deep=True).proportion_mediated == pytest.approx(0.25)
    assert (
        MediationDecomposition.model_validate(result.model_dump(mode="json")).proportion_mediated
        == pytest.approx(0.25)
    )


def test_path_specific_query_rejects_paths_without_treatment_and_outcome_endpoints() -> None:
    with pytest.raises(ValueError, match="must start with treatment"):
        PathSpecificQuery(
            treatment="T",
            outcome="Y",
            active_paths=(("M", "Y"),),
        )
