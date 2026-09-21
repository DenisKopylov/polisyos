"""Regression witnesses for SCM-02 factual abduction and attribution."""

from __future__ import annotations

import pytest

from polisyos.foundry.methods.catalog.causal.gcm_query import GCMQuery
from polisyos.foundry.methods.catalog.causal.protocols import SCMQueryData, TwinNetworkQueryData
from polisyos.foundry.methods.catalog.causal.twin_network_query import TwinNetworkQuery
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_queries import CausalQueryResult
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


def _empirical_root_chain() -> StructuralCausalModelSpec:
    """Build the same chain with an empirical, non-Gaussian root carrier."""
    scm = _linear_chain()
    empirical_root = scm.mechanisms[0].model_copy(
        update={
            "family": MechanismFamily.EMPIRICAL,
            "family_params": {"mean": 0.0, "std": 1.0},
        }
    )
    return scm.model_copy(update={"mechanisms": [empirical_root, scm.mechanisms[1]]})


def _empirical_covariate_scm() -> StructuralCausalModelSpec:
    """Build X,Z -> Y with an empirical non-treatment root Z."""
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Z", "Y"],
        edges=[CausalEdge(src="X", dst="Y"), CausalEdge(src="Z", dst="Y")],
    )
    return StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable="X",
                parents=[],
                family=MechanismFamily.LINEAR,
                family_params={"intercept": 0.0, "coefficients": {}, "noise_std": 1.0},
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="Z",
                parents=[],
                family=MechanismFamily.EMPIRICAL,
                family_params={
                    "mean": 0.0,
                    "std": 1.0,
                    "observed_samples": [0.0, 1.0],
                },
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="Y",
                parents=["X", "Z"],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 0.0,
                    "coefficients": {"X": 1.0, "Z": 1.0},
                    "noise_std": 0.0,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        fitted=True,
        fit_method="gcm",
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
    assert result.metadata["abduction_profile"] == "linear_gaussian_posterior"
    assert result.metadata["abduction_observed_nodes"] == ["Y"]
    assert result.metadata["abduction_noise_nodes"] == ["X", "Y"]
    assert result.metadata["abduction_gate_eligible"] is True
    assert output["envelope"].gate_eligible is True


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


def test_full_observed_empirical_root_keeps_exact_residual_fallback() -> None:
    """A fully observed parent remains valid when Gaussian posterior is unavailable."""
    output = _run_query(
        _empirical_root_chain(),
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
    assert result.metadata["abduction_profile"] == "exact_residual_fallback"
    assert result.metadata["abduction_gate_eligible"] is True
    assert output["envelope"].gate_eligible is True


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


def test_twin_partial_gaussian_abduction_reuses_conditioned_noise() -> None:
    """Twin worlds share draws from U|Y=2 instead of a fixed imputed residual."""
    payload = TwinNetworkQueryData(
        scm_spec=_linear_chain(),
        factual_condition={"Y": 2.0},
        treatment_variable="X",
        factual_treatment_value=1.0,
        counterfactual_treatment_value=0.0,
        outcome_variable="Y",
        n_samples=2048,
    )

    output = TwinNetworkQuery.pure_step(payload, params={"__seed__": 117})

    assert output["twin_network_result"].po_counter_mean == pytest.approx(1.0, abs=0.08)
    assert output["twin_network_result"].po_counter_std == pytest.approx(
        2.0**-0.5,
        abs=0.08,
    )
    assert output["twin_network_result"].ite_std == pytest.approx(0.0, abs=1.0e-10)
    assert output["twin_network_result"].po_correlation == pytest.approx(1.0, abs=1.0e-10)
    assert output["twin_network_result"].metadata["n_abduced_nodes"] == 2
    assert output["twin_network_result"].metadata["abduction_profile"] == (
        "linear_gaussian_posterior"
    )
    assert output["envelope"].gate_eligible is True


def test_partial_unsupported_abduction_is_limited_not_gate_eligible() -> None:
    """An empirical hidden parent cannot masquerade as Gaussian evidence."""
    output = _run_query(
        _empirical_root_chain(),
        {
            "query_type": "counterfactual",
            "treatment_variable": "X",
            "treatment_value": 0.0,
            "outcome_variable": "Y",
            "condition": {"Y": 2.0},
            "n_samples": 128,
        },
    )

    result = CausalQueryResult.model_validate(output["query_result"])
    assert result.metadata["abduction_profile"] == "limited_imputed_fallback"
    assert result.metadata["abduction_observed_nodes"] == ["Y"]
    assert result.metadata["abduction_gate_eligible"] is False
    assert "abduction_limitation" in result.metadata
    assert output["envelope"].gate_eligible is False
    assert any("limited abduction" in str(item) for item in output["warnings"])


def test_twin_empirical_factual_root_is_not_claimed_exact() -> None:
    """Twin prediction must not gate an observed root it cannot pin."""
    payload = TwinNetworkQueryData(
        scm_spec=_empirical_covariate_scm(),
        factual_condition={"X": 1.0, "Z": 50.0, "Y": 51.0},
        treatment_variable="X",
        factual_treatment_value=1.0,
        counterfactual_treatment_value=0.0,
        outcome_variable="Y",
        n_samples=128,
    )

    output = TwinNetworkQuery.pure_step(payload, params={"__seed__": 117})

    result = output["twin_network_result"]
    assert result.metadata["abduction_profile"] == "limited_unpinned_empirical_root"
    assert result.metadata["abduction_gate_eligible"] is False
    assert "cannot pin observed empirical root" in result.metadata["abduction_limitation"]
    assert output["envelope"].gate_eligible is False
