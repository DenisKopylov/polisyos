from __future__ import annotations

import pytest
from polisyos.ir.analytics.actual_causality import (
    ContingencySet,
    HPResult,
    PNPSBounds,
    PNSResult,
)
from polisyos.ir.analytics.mediation_effects import (
    MediationDecomposition,
    PathSpecificQuery,
)
from pydantic import ValidationError


def test_pns_result_rejects_value_above_pn_and_ps() -> None:
    with pytest.raises(ValidationError, match="pns must not exceed pn"):
        PNSResult(
            treatment="T",
            outcome="Y",
            treatment_value=1.0,
            counterfactual_value=0.0,
            pns=0.7,
            pn=0.6,
            ps=0.8,
        )


def test_pnps_bounds_reject_incorrect_monotone_point() -> None:
    with pytest.raises(ValidationError, match="monotone_pns must equal max"):
        PNPSBounds(
            p_y1_x1=0.8,
            p_y1_x0=0.3,
            pn_lower=0.1,
            pn_upper=1.0,
            ps_lower=0.1,
            ps_upper=1.0,
            pns_lower=0.5,
            pns_upper=0.8,
            monotone_pns=0.6,
            is_monotone_compatible=True,
        )


def test_hp_result_rejects_overlap_between_cause_and_contingency() -> None:
    with pytest.raises(ValidationError, match="must be disjoint"):
        HPResult(
            cause_variable="T",
            cause_variables=["T", "M"],
            cause_value=1.0,
            cause_values={"T": 1.0, "M": 1.0},
            counterfactual_cause_value=0.0,
            counterfactual_cause_values={"T": 0.0, "M": 0.0},
            effect_variable="Y",
            effect_value=1.0,
            ac1_satisfied=True,
            ac2_satisfied=True,
            ac3_satisfied=True,
            is_actual_cause=True,
            contingency=ContingencySet(
                variables=["M"],
                values={"M": 1.0},
                size=1,
            ),
            degree_of_responsibility=0.5,
        )


def test_path_specific_query_rejects_overlapping_active_and_fixed_paths() -> None:
    with pytest.raises(ValidationError, match="active_paths and fixed_paths must be disjoint"):
        PathSpecificQuery(
            treatment="T",
            outcome="Y",
            mediators=("M",),
            active_paths=(("T", "M", "Y"),),
            fixed_paths=(("T", "M", "Y"),),
        )


def test_path_specific_query_rejects_path_with_wrong_endpoints() -> None:
    with pytest.raises(ValidationError, match="must start with treatment"):
        PathSpecificQuery(
            treatment="T",
            outcome="Y",
            mediators=("M",),
            active_paths=(("M", "Y"),),
        )


def test_mediation_decomposition_rejects_identity_violation() -> None:
    with pytest.raises(ValidationError, match="nde \\+ nie must equal total_effect"):
        MediationDecomposition(
            nde=0.2,
            nie=0.3,
            total_effect=0.6,
        )


def test_mediation_decomposition_explicit_factory_sets_proportion_mediated() -> None:
    payload = {"nde": 0.2, "nie": 0.3, "total_effect": 0.5}
    normalized = MediationDecomposition.normalize_payload(payload)
    result = MediationDecomposition.from_effects(**payload)

    assert "proportion_mediated" not in payload
    assert normalized["proportion_mediated"] == pytest.approx(0.6)
    assert result.proportion_mediated == pytest.approx(0.6)
    assert MediationDecomposition.model_validate(
        result.model_dump(mode="json")
    ).proportion_mediated == pytest.approx(0.6)


def test_mediation_decomposition_requires_sensitivity_vectors_to_align() -> None:
    with pytest.raises(ValidationError, match="must align with sensitivity_rho_range length"):
        MediationDecomposition(
            nde=0.2,
            nie=0.3,
            total_effect=0.5,
            sensitivity_rho_range=(0.0, 0.2),
            sensitivity_nde=(0.2,),
            sensitivity_nie=(0.3, 0.25),
        )
