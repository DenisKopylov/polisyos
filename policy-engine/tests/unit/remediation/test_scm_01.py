from __future__ import annotations

import math

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
    treatment = np.array([0.0, 0.0, 1.0, 1.0, 2.0, 2.0])
    root = np.array([99.0, 101.0, 99.0, 102.0, 99.0, 100.0])
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
    assert mechanisms["Z"].family_params["observed_samples"] == [
        99.0,
        101.0,
        99.0,
        102.0,
        99.0,
        100.0,
    ]

    non_empirical_root = mechanisms["Z"].model_copy(
        update={"family": MechanismFamily.LINEAR}
    )
    with pytest.raises(ValueError, match="require an EMPIRICAL mechanism"):
        StructuralCausalModelSpec(
            graph=spec.graph,
            mechanisms=[mechanism for mechanism in spec.mechanisms if mechanism.variable != "Z"]
            + [non_empirical_root],
            fitted=True,
            fit_method="gcm",
        )

    broken_root = mechanisms["Z"].model_copy(
        update={
            "family_params": {
                **mechanisms["Z"].family_params,
                "observed_samples": [99.0],
            }
        }
    )
    with pytest.raises(ValueError, match="share one row count"):
        StructuralCausalModelSpec(
            graph=spec.graph,
            mechanisms=[mechanism for mechanism in spec.mechanisms if mechanism.variable != "Z"]
            + [broken_root],
            fitted=True,
            fit_method="gcm",
        )

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
    query_result = result["query_result"]
    expected_support = {float(3.0 + 2.0 * value) for value in root}
    assert query_result.result_distribution is not None
    assert all(
        any(value == pytest.approx(expected, abs=1e-9) for expected in expected_support)
        for value in query_result.result_distribution
    )
    expected_mean = float(3.0 + 2.0 * np.mean(root))
    sample_range = max(expected_support) - min(expected_support)
    confidence = 0.99
    hoeffding_epsilon = sample_range * math.sqrt(
        math.log(2.0 / (1.0 - confidence)) / (2.0 * len(query_result.result_distribution))
    )
    assert abs(query_result.result_mean - expected_mean) <= hoeffding_epsilon

    # The non-intervened root is sampled from aligned observed rows, retaining
    # the observed joint carrier rather than independent Normal draws.
    samples_query = CausalQuery.model_validate(
        {
            "query_type": "soft_intervention",
            "treatment_variable": "T",
            "outcome_variable": "Y",
            "n_samples": 128,
            "intervention_spec": {"type": "shifted", "shift": 0.0},
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
    observed_pairs = set(zip(by_node["T"], by_node["Z"], strict=True))
    allowed_pairs = {
        (0.0, 99.0),
        (0.0, 101.0),
        (1.0, 99.0),
        (1.0, 102.0),
        (2.0, 99.0),
        (2.0, 100.0),
    }
    assert observed_pairs.issubset(allowed_pairs)
    assert (0.0, 102.0) not in observed_pairs


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

    missing_query = SCMQueryData(
        scm_spec=spec,
        query={
            "query_type": "interventional",
            "treatment_variable": "X",
            "treatment_value": 1.0,
            "outcome_variable": "Y",
            "n_samples": 16,
        },
    )
    with pytest.raises(ValueError, match="allow_declared_root_hypothesis"):
        GCMQuery.pure_step(missing_query, params={"__seed__": 3})

    result = GCMQuery.pure_step(
        missing_query,
        params={"__seed__": 3, "allow_declared_root_hypothesis": True},
    )
    assert any(
        "missing mechanism" in warning and "declared hypothesis" in warning
        for warning in result["warnings"]
    )
    assert result["envelope"].gate_eligible is False


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

    invalid_polynomial = spec.mechanisms[1].model_copy(
        update={
            "family_params": {
                "fit_mode": "additive_noise_poly",
                "poly_degree": 2,
                "poly_coefficients": {"__intercept__": 0.0},
                "noise_std": 0.25,
            }
        }
    )
    invalid_spec = StructuralCausalModelSpec(
        graph=spec.graph,
        mechanisms=[spec.mechanisms[0], invalid_polynomial],
        fitted=True,
        fit_method="gcm",
    )
    with pytest.raises(ValueError, match="invalid additive_noise polynomial payload"):
        TwinNetworkQuery.pure_step(
            TwinNetworkQueryData(
                scm_spec=invalid_spec,
                treatment_variable="X",
                outcome_variable="Y",
                factual_treatment_value=1.0,
                counterfactual_treatment_value=2.0,
                n_samples=32,
            ),
            params={"__seed__": 23},
        )

    fractional_polynomial = spec.mechanisms[1].model_copy(
        update={
            "family_params": {
                **spec.mechanisms[1].family_params,
                "poly_degree": 2.5,
            }
        }
    )
    fractional_spec = StructuralCausalModelSpec(
        graph=spec.graph,
        mechanisms=[spec.mechanisms[0], fractional_polynomial],
        fitted=True,
        fit_method="gcm",
    )
    with pytest.raises(ValueError, match="invalid additive_noise polynomial payload"):
        TwinNetworkQuery.pure_step(
            TwinNetworkQueryData(
                scm_spec=fractional_spec,
                treatment_variable="X",
                outcome_variable="Y",
                factual_treatment_value=1.0,
                counterfactual_treatment_value=2.0,
                n_samples=32,
            ),
            params={"__seed__": 23},
        )
