from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal import gcm_fit as gcm_fit_module
from polisyos.foundry.methods.catalog.causal.gcm_fit import HybridSCMFit
from polisyos.foundry.methods.catalog.causal.gcm_query import GCMQuery, _simulate_samples
from polisyos.foundry.methods.catalog.causal.protocols import (
    SCMFitData,
    SCMQueryData,
    TwinNetworkQueryData,
)
from polisyos.foundry.methods.catalog.causal.twin_network_query import TwinNetworkQuery
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_queries import CausalQuery
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
)


def _graph(*edges: tuple[str, str], nodes: list[str]) -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=nodes,
        edges=[CausalEdge(src=src, dst=dst) for src, dst in edges],
    )


def _fit(
    graph: CausalGraphModel,
    data: np.ndarray,
    columns: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> StructuralCausalModelSpec:
    monkeypatch.setattr(
        gcm_fit_module,
        "_load_dowhy_gcm_dependencies",
        lambda: (_ for _ in ()).throw(ModuleNotFoundError("dowhy unavailable in remediation")),
    )
    result = HybridSCMFit.pure_step(
        SCMFitData(data=data, column_names=columns, graph=graph),
        params={},
    )
    return result["scm_spec"]


def test_observed_roots_are_carried_into_query_without_normal_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    treatment = np.array([0.0, 0.0, 1.0, 1.0])
    root = np.array([99.0, 101.0, 99.0, 101.0])
    outcome = 3.0 * treatment + 2.0 * root
    spec = _fit(
        _graph(("T", "Y"), ("Z", "Y"), nodes=["T", "Z", "Y"]),
        np.column_stack([treatment, root, outcome]),
        ["T", "Z", "Y"],
        monkeypatch,
    )

    mechanisms = {mechanism.variable: mechanism for mechanism in spec.mechanisms}
    assert mechanisms["T"].family is MechanismFamily.EMPIRICAL
    assert mechanisms["Z"].family is MechanismFamily.EMPIRICAL
    assert mechanisms["Z"].family_params["observed_samples"] == [99.0, 101.0, 99.0, 101.0]

    query = SCMQueryData(
        scm_spec=spec,
        query={
            "query_type": "interventional",
            "treatment_variable": "T",
            "treatment_value": 1.0,
            "outcome_variable": "Y",
            "n_samples": 512,
        },
    )
    result = GCMQuery.pure_step(query, params={"__seed__": 7})
    assert result["query_result"].result_mean == pytest.approx(203.0, abs=1e-9)

    # The non-intervened root is sampled from aligned observed rows, retaining
    # the observed joint carrier rather than independent Normal draws.
    samples_query = CausalQuery.model_validate(
        {
            "query_type": "soft_intervention",
            "treatment_variable": "T",
            "outcome_variable": "Y",
            "n_samples": 128,
        }
    )
    _, by_node = _simulate_samples(
        scm_spec=spec,
        query=samples_query,
        n_samples=128,
        rng=np.random.default_rng(11),
        warnings=[],
        intervention_override=None,
    )
    assert set(zip(by_node["T"], by_node["Z"], strict=True)).issubset(
        {(0.0, 99.0), (0.0, 101.0), (1.0, 99.0), (1.0, 101.0)}
    )


def test_missing_root_is_declared_hypothesis_instead_of_fitted_law() -> None:
    spec = StructuralCausalModelSpec(
        graph=_graph(("X", "Y"), ("Z", "Y"), nodes=["X", "Z", "Y"]),
        mechanisms=[
            NodeMechanism(
                variable="Y",
                parents=["X", "Z"],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 0.0,
                    "coefficients": {"X": 1.0, "Z": 1.0},
                },
                source=MechanismSource.DATA_FITTED,
            )
        ],
        fitted=True,
        fit_method="gcm",
    )

    result = GCMQuery.pure_step(
        SCMQueryData(
            scm_spec=spec,
            query={
                "query_type": "interventional",
                "treatment_variable": "X",
                "treatment_value": 1.0,
                "outcome_variable": "Y",
                "n_samples": 16,
            },
        ),
        params={"__seed__": 3},
    )
    assert any(
        "missing mechanism" in warning and "declared hypothesis" in warning
        for warning in result["warnings"]
    )


def test_fitted_polynomial_executes_as_polynomial_and_linear_control_remains_linear() -> None:
    graph = _graph(("X", "Y"), nodes=["X", "Y"])

    polynomial_spec = StructuralCausalModelSpec(
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
                family=MechanismFamily.ADDITIVE_NOISE,
                family_params={
                    "fit_mode": "additive_noise_poly",
                    "poly_degree": 2,
                    "poly_coefficients": {"__intercept__": 0.0, "X^1": 0.0, "X^2": 1.0},
                    "noise_std": 0.0,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        fitted=True,
        fit_method="gcm",
    )

    polynomial_result = GCMQuery.pure_step(
        SCMQueryData(
            scm_spec=polynomial_spec,
            query={
                "query_type": "interventional",
                "treatment_variable": "X",
                "treatment_value": 2.0,
                "outcome_variable": "Y",
                "n_samples": 256,
            },
        ),
        params={"__seed__": 17},
    )
    assert polynomial_result["query_result"].result_mean == pytest.approx(4.0, abs=1e-9)

    linear_spec = StructuralCausalModelSpec(
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
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 1.0,
                    "coefficients": {"X": 3.0},
                    "noise_std": 0.0,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        fitted=True,
        fit_method="gcm",
    )
    linear = next(item for item in linear_spec.mechanisms if item.variable == "Y")
    assert linear.family is MechanismFamily.LINEAR
    linear_result = GCMQuery.pure_step(
        SCMQueryData(
            scm_spec=linear_spec,
            query={
                "query_type": "interventional",
                "treatment_variable": "X",
                "treatment_value": 2.0,
                "outcome_variable": "Y",
                "n_samples": 256,
            },
        ),
        params={"__seed__": 17},
    )
    assert linear_result["query_result"].result_mean == pytest.approx(7.0, abs=1e-9)


def test_twin_query_reuses_shared_noise_with_polynomial_payload() -> None:
    spec = StructuralCausalModelSpec(
        graph=_graph(("X", "Y"), nodes=["X", "Y"]),
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
                family=MechanismFamily.ADDITIVE_NOISE,
                family_params={
                    "fit_mode": "additive_noise_poly",
                    "poly_degree": 2,
                    "poly_coefficients": {"__intercept__": 0.0, "X^1": 0.0, "X^2": 1.0},
                    "noise_std": 0.25,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        fitted=True,
        fit_method="gcm",
    )
    result = TwinNetworkQuery.pure_step(
        TwinNetworkQueryData(
            scm_spec=spec,
            treatment_variable="X",
            outcome_variable="Y",
            factual_treatment_value=1.0,
            counterfactual_treatment_value=2.0,
            n_samples=512,
        ),
        params={"__seed__": 23},
    )
    twin_result = result["twin_network_result"]
    assert twin_result.ite_mean == pytest.approx(3.0, abs=1e-9)
    assert twin_result.ite_std == pytest.approx(0.0, abs=1e-9)
