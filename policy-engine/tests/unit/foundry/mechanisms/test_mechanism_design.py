from __future__ import annotations

import pytest
from polisyos.foundry.mechanisms.design import (
    get_mechanism_family_spec,
    mechanism_family_catalog,
)
from polisyos.ir.analytics.mechanism_design import MechanismFamily


def test_mechanism_family_catalog_contains_phase3_entries() -> None:
    names = {entry["mechanism_id"] for entry in mechanism_family_catalog()}
    assert {
        "bayes_tax_affine_v1",
        "bayes_tax_pl_v1",
        "license_myerson_score_v1",
        "license_scoring_reserve_v1",
    } <= names


def test_get_mechanism_family_spec_returns_typed_phase3_surface() -> None:
    spec = get_mechanism_family_spec("bayes_tax_pl_v1")

    assert spec.family is MechanismFamily.TAX_PIECEWISE_LINEAR
    assert spec.parameterization == "monotone_piecewise_linear_earnings"

    with pytest.raises(ValueError, match="Unknown mechanism family"):
        get_mechanism_family_spec("missing_family")
