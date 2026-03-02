from __future__ import annotations

import pytest

from polisyos.foundry.methods.catalog.causal.gcm_query import GCMQuery
from polisyos.foundry.methods.catalog.causal.protocols import SCMQueryData
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_queries import CausalQueryResult
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
)


def _simple_scm(*, y_family: MechanismFamily = MechanismFamily.LINEAR) -> StructuralCausalModelSpec:
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
                family=MechanismFamily.EMPIRICAL,
                family_params={"mean": 0.0, "std": 1.0},
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="Y",
                parents=["X"],
                family=y_family,
                family_params={
                    "intercept": 0.5,
                    "coefficients": {"X": 2.0},
                    "noise_std": 0.1,
                    "mean": 0.5,
                    "std": 0.2,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        fitted=True,
        fit_method="gcm",
    )


def _run_query(scm_spec: StructuralCausalModelSpec, query: dict, *, seed: int = 123) -> dict:
    payload = SCMQueryData(scm_spec=scm_spec, query=query)
    return GCMQuery.pure_step(payload, params={"__seed__": seed})


def test_gcm_query_interventional_atomic() -> None:
    result = _run_query(
        _simple_scm(),
        {
            "query_type": "interventional",
            "treatment_variable": "X",
            "treatment_value": 1.0,
            "outcome_variable": "Y",
            "n_samples": 2000,
        },
    )
    query_result = CausalQueryResult.model_validate(result["query_result"])
    assert query_result.result_mean == pytest.approx(2.5, abs=0.15)
    assert query_result.result_std > 0.0


def test_gcm_query_counterfactual_with_condition() -> None:
    result = _run_query(
        _simple_scm(),
        {
            "query_type": "counterfactual",
            "treatment_variable": "X",
            "treatment_value": 0.0,
            "outcome_variable": "Y",
            "condition": {"X": 1.0, "Y": 2.6},
            "n_samples": 512,
        },
    )
    query_result = CausalQueryResult.model_validate(result["query_result"])
    assert query_result.result_mean == pytest.approx(0.6, abs=0.2)


def test_gcm_query_shifted_and_truncated_soft_interventions() -> None:
    scm_spec = _simple_scm()
    shifted = _run_query(
        scm_spec,
        {
            "query_type": "soft_intervention",
            "treatment_variable": "X",
            "outcome_variable": "Y",
            "n_samples": 1024,
            "intervention_spec": {"type": "shifted", "shift": 1.0},
        },
        seed=11,
    )
    truncated = _run_query(
        scm_spec,
        {
            "query_type": "soft_intervention",
            "treatment_variable": "X",
            "outcome_variable": "Y",
            "n_samples": 1024,
            "intervention_spec": {"type": "truncated", "bounds": [-0.2, 0.2]},
        },
        seed=11,
    )

    shifted_result = CausalQueryResult.model_validate(shifted["query_result"])
    truncated_result = CausalQueryResult.model_validate(truncated["query_result"])
    assert shifted_result.result_mean > truncated_result.result_mean
    assert shifted_result.result_mean > 1.5


def test_gcm_query_stochastic_fallback_to_atomic() -> None:
    result = _run_query(
        _simple_scm(),
        {
            "query_type": "interventional",
            "treatment_variable": "X",
            "treatment_value": 1.5,
            "outcome_variable": "Y",
            "n_samples": 512,
            "intervention_spec": {"type": "stochastic", "distribution": "broken("},
        },
        seed=33,
    )
    query_result = CausalQueryResult.model_validate(result["query_result"])
    assert query_result.result_mean == pytest.approx(3.5, abs=0.2)
    warnings = result.get("warnings", [])
    assert any("falling back to atomic" in str(item) for item in warnings)


def test_gcm_query_surfaces_mechanism_fallback_warning() -> None:
    result = _run_query(
        _simple_scm(y_family=MechanismFamily.POST_NONLINEAR),
        {
            "query_type": "interventional",
            "treatment_variable": "X",
            "treatment_value": 1.0,
            "outcome_variable": "Y",
            "n_samples": 256,
        },
    )
    warnings = result.get("warnings", [])
    assert any("not fully supported" in str(item) for item in warnings)


def test_gcm_query_dowhy_parity_optional() -> None:
    pytest.importorskip("dowhy")

    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["Z", "X", "Y"],
        edges=[
            CausalEdge(src="Z", dst="X"),
            CausalEdge(src="Z", dst="Y"),
            CausalEdge(src="X", dst="Y"),
        ],
    )
    scm_spec = StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable="Z",
                parents=[],
                family=MechanismFamily.EMPIRICAL,
                family_params={"mean": 0.0, "std": 1.0},
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="X",
                parents=["Z"],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 0.0,
                    "coefficients": {"Z": 0.8},
                    "noise_std": 0.2,
                },
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="Y",
                parents=["X", "Z"],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 0.0,
                    "coefficients": {"X": 1.2, "Z": 0.7},
                    "noise_std": 0.2,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        fitted=True,
        fit_method="gcm",
    )

    treat = _run_query(
        scm_spec,
        {
            "query_type": "interventional",
            "treatment_variable": "X",
            "treatment_value": 1.0,
            "outcome_variable": "Y",
            "n_samples": 2000,
        },
        seed=77,
    )
    control = _run_query(
        scm_spec,
        {
            "query_type": "interventional",
            "treatment_variable": "X",
            "treatment_value": 0.0,
            "outcome_variable": "Y",
            "n_samples": 2000,
        },
        seed=77,
    )

    treat_res = CausalQueryResult.model_validate(treat["query_result"])
    control_res = CausalQueryResult.model_validate(control["query_result"])
    gcm_ate = treat_res.result_mean - control_res.result_mean
    dowhy_comparison = treat.get("dowhy_comparison")
    assert isinstance(dowhy_comparison, dict)
    assert abs(gcm_ate - float(dowhy_comparison["dowhy_ate"])) < 0.35
