"""Regression witnesses for SCM-02 factual abduction and attribution."""

from __future__ import annotations

import pytest

from polisyos.foundry.methods.catalog.causal.gcm_query import GCMQuery
from polisyos.foundry.methods.catalog.causal.protocols import SCMQueryData
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_queries import (
    CausalAttributionSpec,
    CausalContrastRegime,
    CausalQuery,
    CausalQueryResult,
    InterventionSpec,
    InterventionType,
    QueryType,
)
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
)


def _linear_chain(*, noise_std: float = 1.0, coefficient: float = 1.0) -> StructuralCausalModelSpec:
    """Build X -> Y with independent Gaussian structural noise."""
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    return StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable="X",
                parents=[],
                family=MechanismFamily.LINEAR,
                family_params={"intercept": 0.0, "coefficients": {}, "noise_std": noise_std},
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="Y",
                parents=["X"],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 0.0,
                    "coefficients": {"X": coefficient},
                    "noise_std": noise_std,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        fitted=True,
        fit_method="gcm",
    )


def _run_query(scm_spec: StructuralCausalModelSpec, query: dict[str, object]) -> dict[str, object]:
    """Run the public GCM query entrypoint with the optional comparison disabled."""
    payload = SCMQueryData(scm_spec=scm_spec, query=query)
    return GCMQuery.pure_step(
        payload,
        params={"__seed__": 117, "enable_dowhy_comparison": False},
    )


def test_partial_gaussian_abduction_conditions_unobserved_parent() -> None:
    """Y=2 alone yields U_Y|Y=2 with mean 1 and variance 0.5 under do(X=0)."""
    output = _run_query(
        _linear_chain(),
        {
            "query_type": "counterfactual",
            "treatment_variable": "X",
            "treatment_value": 0.0,
            "outcome_variable": "Y",
            "condition": {"Y": 2.0},
            "n_samples": 2048,
        },
    )

    result = CausalQueryResult.model_validate(output["query_result"])
    assert result.result_mean == pytest.approx(1.0, abs=0.08)
    assert result.result_std == pytest.approx(2.0**-0.5, abs=0.08)


def test_full_linear_factual_inputs_keep_exact_residual_control() -> None:
    """X=1,Y=2 fully observed keeps the exact residual Y(0)=1 control."""
    output = _run_query(
        _linear_chain(),
        {
            "query_type": "counterfactual",
            "treatment_variable": "X",
            "treatment_value": 0.0,
            "outcome_variable": "Y",
            "condition": {"X": 1.0, "Y": 2.0},
            "n_samples": 64,
        },
    )

    result = CausalQueryResult.model_validate(output["query_result"])
    assert result.result_mean == pytest.approx(1.0)
    assert result.result_std == pytest.approx(0.0)


def test_attribution_uses_a_distinct_observational_baseline() -> None:
    """Y=1+3X with target do(X=2) has attribution contrast 6, not zero."""
    output = _run_query(
        _linear_chain(noise_std=0.0, coefficient=3.0),
        {
            "query_type": "attribution",
            "treatment_variable": "X",
            "treatment_value": 2.0,
            "outcome_variable": "Y",
            "n_samples": 64,
        },
    )

    result = CausalQueryResult.model_validate(output["query_result"])
    assert result.result_mean == pytest.approx(6.0)
    assert result.result_std == pytest.approx(0.0)


def test_contrast_regime_requires_a_matching_intervention_payload() -> None:
    atomic = InterventionSpec(type=InterventionType.ATOMIC, value=0.0)

    with pytest.raises(ValueError, match="intervention is required"):
        CausalContrastRegime(kind="interventional")
    with pytest.raises(ValueError, match="must not carry an intervention"):
        CausalContrastRegime(kind="observational", intervention=atomic)


def test_attribution_target_must_be_interventional() -> None:
    with pytest.raises(ValueError, match="target regime must be interventional"):
        CausalAttributionSpec(
            target=CausalContrastRegime(kind="observational"),
            comparator=CausalContrastRegime(kind="observational"),
        )


def test_legacy_attribution_is_normalized_to_explicit_observational_comparator() -> None:
    query = CausalQuery(
        query_type=QueryType.ATTRIBUTION,
        treatment_variable="X",
        treatment_value=2.0,
        outcome_variable="Y",
    )

    assert query.contrast is not None
    assert query.contrast.target.kind == "interventional"
    assert query.contrast.target.intervention is not None
    assert query.contrast.target.intervention.value == pytest.approx(2.0)
    assert query.contrast.comparator.kind == "observational"
    assert query.contrast.comparator.intervention is None


def test_attribution_contrast_serialization_roundtrip_preserves_both_sides() -> None:
    query = CausalQuery(
        query_type=QueryType.ATTRIBUTION,
        treatment_variable="X",
        treatment_value=2.0,
        outcome_variable="Y",
        contrast=CausalAttributionSpec(
            target=CausalContrastRegime(
                kind="interventional",
                intervention=InterventionSpec(type=InterventionType.ATOMIC, value=2.0),
            ),
            comparator=CausalContrastRegime(
                kind="interventional",
                intervention=InterventionSpec(type=InterventionType.ATOMIC, value=0.0),
            ),
        ),
    )

    restored = CausalQuery.model_validate(query.model_dump(mode="json"))

    assert restored.contrast == query.contrast
