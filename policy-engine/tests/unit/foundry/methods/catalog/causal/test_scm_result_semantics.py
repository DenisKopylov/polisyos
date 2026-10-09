"""Persisted causal distributions cannot become estimator confidence intervals."""

from pathlib import Path

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.gcm_query import GCMQuery
from polisyos.foundry.methods.catalog.causal.protocols import SCMQueryData
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_queries import (
    CausalQuery,
    load_causal_query_result,
    persist_causal_query_result,
)
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    NodeMechanism,
    StructuralCausalModelSpec,
)
from polisyos.ir.analytics.uncertainty import DistributionFamily, IntervalSemantics


def _gaussian_scm() -> StructuralCausalModelSpec:
    return StructuralCausalModelSpec(
        graph=CausalGraphModel(
            nodes=["X", "Y"], edges=[CausalEdge(src="X", dst="Y")], graph_type=GraphType.DAG
        ),
        mechanisms=[
            NodeMechanism(
                variable="X",
                family=MechanismFamily.LINEAR,
                family_params={"intercept": 0.0, "coefficients": {}, "noise_std": 1.0},
            ),
            NodeMechanism(
                variable="Y",
                parents=["X"],
                family=MechanismFamily.LINEAR,
                family_params={"intercept": 0.0, "coefficients": {"X": 1.0}, "noise_std": 1.0},
            ),
        ],
        fitted=True,
        fit_method="manual",
    )


@pytest.mark.parametrize("n_samples", [100, 10000])
def test_fixed_fit_draws_stay_distribution_after_cas(n_samples: int, tmp_path: Path) -> None:
    query = CausalQuery(
        query_type="interventional",
        treatment_variable="X",
        treatment_value=0.0,
        outcome_variable="Y",
        n_samples=n_samples,
    )
    output = GCMQuery.pure_step(
        SCMQueryData(scm_spec=_gaussian_scm(), query=query),
        {"__seed__": 37, "enable_dowhy_comparison": False},
    )
    store = FileSystemCAS(tmp_path / "cas")
    result = load_causal_query_result(
        _ensure_ir_artifact_store(store),
        persist_causal_query_result(_ensure_ir_artifact_store(store), output["query_result"]),
    )
    envelope = result.to_uncertainty_envelope()
    assert envelope.interval_semantics is not IntervalSemantics.CONFIDENCE_INTERVAL
    assert envelope.distribution_family is not DistributionFamily.BOOTSTRAP
    assert envelope.gate_eligible is False
    assert result.result_kind.value == "outcome_distribution"


def test_exact_abduction_is_model_posterior_after_cas(tmp_path: Path) -> None:
    query = CausalQuery(
        query_type="counterfactual",
        treatment_variable="X",
        treatment_value=0.0,
        outcome_variable="Y",
        condition={"Y": 2.0},
        n_samples=8000,
    )
    output = GCMQuery.pure_step(
        SCMQueryData(scm_spec=_gaussian_scm(), query=query),
        {"__seed__": 37, "enable_dowhy_comparison": False},
    )
    store = FileSystemCAS(tmp_path / "cas")
    result = load_causal_query_result(
        _ensure_ir_artifact_store(store),
        persist_causal_query_result(_ensure_ir_artifact_store(store), output["query_result"]),
    )
    assert result.result_mean == pytest.approx(1.0, abs=0.03)
    assert result.result_std**2 == pytest.approx(0.5, abs=0.04)
    assert result.result_kind.value == "posterior_credible_interval"
    envelope = result.to_uncertainty_envelope()
    assert envelope.interval_semantics is IntervalSemantics.CREDIBLE_INTERVAL
    assert envelope.distribution_family is DistributionFamily.BAYESIAN
    assert envelope.gate_eligible is False


import math

import numpy as np

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.foundry.methods.catalog.causal.gcm_query import (
    _linear_gaussian_posterior,
    _sample_stochastic_distribution,
)
from polisyos.foundry.methods.catalog.causal.protocols import TwinNetworkQueryData
from polisyos.foundry.methods.catalog.causal.twin_network_query import TwinNetworkQuery
from polisyos.ir.analytics.twin_network import load_twin_network_result, persist_twin_network_result
from polisyos.ir.registry.refs import CausalQueryResultRef


def test_general_gaussian_noise_posterior_matches_independent_matrix_oracle():
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "Z"],
        edges=[CausalEdge(src="X", dst="Y"), CausalEdge(src="Y", dst="Z")],
    )
    mechanisms = [
        NodeMechanism(
            variable="X",
            family="linear",
            family_params={"intercept": 0, "coefficients": {}, "noise_std": 1},
        ),
        NodeMechanism(
            variable="Y",
            parents=["X"],
            family="linear",
            family_params={"intercept": 1, "coefficients": {"X": 3}, "noise_std": 2},
        ),
        NodeMechanism(
            variable="Z",
            parents=["Y"],
            family="linear",
            family_params={"intercept": 0, "coefficients": {"Y": 2}, "noise_std": 0.5},
        ),
    ]
    order = ["X", "Y", "Z"]
    parents = {"X": [], "Y": ["X"], "Z": ["Y"]}
    posterior = _linear_gaussian_posterior(
        condition={"Y": 4, "Z": 9},
        order=order,
        parents_map=parents,
        mechanisms={m.variable: m for m in mechanisms},
    )
    # Independent structural equation: observed (Y-1,Z-2)=H U.
    h = np.array([[3.0, 1.0, 0.0], [6.0, 2.0, 1.0]])
    sigma = np.diag([1.0, 4.0, 0.25])
    r = np.array([3.0, 7.0])
    gain = sigma @ h.T @ np.linalg.inv(h @ sigma @ h.T)
    assert posterior is not None
    assert posterior.mean == pytest.approx(gain @ r, abs=1e-10)
    assert posterior.covariance == pytest.approx(sigma - gain @ h @ sigma, abs=1e-10)
    deterministic = [
        mechanisms[0],
        mechanisms[1].model_copy(
            update={"family_params": {"intercept": 1, "coefficients": {"X": 3}, "noise_std": 0}}
        ),
        mechanisms[2].model_copy(
            update={"family_params": {"intercept": 0, "coefficients": {"Y": 2}, "noise_std": 0}}
        ),
    ]
    exact = _linear_gaussian_posterior(
        condition={"Y": 4, "Z": 8},
        order=order,
        parents_map=parents,
        mechanisms={m.variable: m for m in deterministic},
    )
    assert exact.mean == pytest.approx([1, 0, 0], abs=1e-10)
    assert exact.covariance == pytest.approx(np.zeros((3, 3)), abs=1e-10)
    with pytest.raises(ValueError, match="incompatible with the singular Gaussian"):
        _linear_gaussian_posterior(
            condition={"Y": 4, "Z": 9},
            order=order,
            parents_map=parents,
            mechanisms={m.variable: m for m in deterministic},
        )


@pytest.mark.parametrize("counter,expected", [(0.0, 0.0), (2.0, 6.0)])
def test_twin_same_row_noise_same_arm_and_slope_after_fresh_cas(counter, expected, tmp_path):
    scm = _gaussian_scm()
    scm = scm.model_copy(
        update={
            "mechanisms": [
                scm.mechanisms[0],
                scm.mechanisms[1].model_copy(
                    update={
                        "family_params": {
                            "intercept": 1.0,
                            "coefficients": {"X": 3.0},
                            "noise_std": 1.0,
                        }
                    }
                ),
            ]
        }
    )
    output = TwinNetworkQuery.pure_step(
        TwinNetworkQueryData(
            scm_spec=scm,
            treatment_variable="X",
            outcome_variable="Y",
            factual_treatment_value=0.0,
            counterfactual_treatment_value=counter,
            factual_condition={"Y": 4.0},
            n_samples=2500,
        ),
        {"__seed__": 19},
    )
    store = FileSystemCAS(tmp_path / "cas")
    result = load_twin_network_result(
        _ensure_ir_artifact_store(FileSystemCAS(store.root)),
        persist_twin_network_result(
            _ensure_ir_artifact_store(store), output["twin_network_result"]
        ),
    )
    assert result.ite_distribution == pytest.approx(np.full(2500, expected), abs=1e-12)
    assert result.ite_mean == pytest.approx(expected, abs=1e-12)
    assert result.result_kind.value == "posterior_credible_interval"
    assert not result.to_uncertainty_envelope().gate_eligible


def _normal_cdf(value):
    return 0.5 * math.erfc(-value / math.sqrt(2))


def _conditional_normal_cdf(value, lo, hi):
    if lo >= 0:
        sf = lambda x: 0.5 * math.erfc(x / math.sqrt(2))
        return (sf(lo) - sf(value)) / (sf(lo) - sf(hi))
    return (_normal_cdf(value) - _normal_cdf(lo)) / (_normal_cdf(hi) - _normal_cdf(lo))


@pytest.mark.parametrize(
    "law,lo,hi,cdf",
    [
        ("Normal(1.5,.7)", None, None, lambda x: _normal_cdf((x - 1.5) / 0.7)),
        ("Uniform(-2,5)", -2.0, 5.0, lambda x: (x + 2) / 7),
        ("TruncNorm(0,1,-1,2)", -1.0, 2.0, lambda x: _conditional_normal_cdf(x, -1, 2)),
        ("TruncNorm(0,1,8,9)", 8.0, 9.0, lambda x: _conditional_normal_cdf(x, 8, 9)),
        ("TruncNorm(0,1,-12,-10)", -12.0, -10.0, lambda x: _conditional_normal_cdf(x, -12, -10)),
    ],
)
def test_declared_static_laws_match_analytic_cdf_including_extreme_tails(law, lo, hi, cdf):
    rng = np.random.default_rng(41)
    draws = np.array(
        [_sample_stochastic_distribution(distribution=law, rng=rng) for _ in range(5000)]
    )
    assert np.isfinite(draws).all()
    if lo is not None:
        assert np.all((draws > lo) & (draws < hi))
    transformed = np.sort(np.array([cdf(float(x)) for x in draws]))
    empirical = (np.arange(len(draws)) + 0.5) / len(draws)
    # DKW finite CDF discriminator with a fixed seed; no population coverage claim.
    assert np.max(np.abs(transformed - empirical)) < 0.03


@pytest.mark.parametrize("law", ["Normal(0,1)", "Uniform(-2,5)", "TruncNorm(0,1,8,9)"])
def test_static_surgery_and_pruning_preserve_public_outcome_draws(law):
    small = StructuralCausalModelSpec(
        graph=CausalGraphModel(
            graph_type=GraphType.DAG, nodes=["X", "Y"], edges=[CausalEdge(src="X", dst="Y")]
        ),
        mechanisms=[
            NodeMechanism(
                variable="X",
                family="linear",
                family_params={"intercept": 0, "coefficients": {}, "noise_std": 1},
            ),
            NodeMechanism(
                variable="Y",
                parents=["X"],
                family="linear",
                family_params={"intercept": 1, "coefficients": {"X": 3}, "noise_std": 0},
            ),
        ],
        fitted=True,
        fit_method="manual",
    )
    full = small.model_copy(
        update={
            "graph": CausalGraphModel(
                graph_type=GraphType.DAG,
                nodes=["Q", "Y", "U", "X"],
                edges=[CausalEdge(src="U", dst="X"), CausalEdge(src="X", dst="Y")],
            ),
            "mechanisms": [
                NodeMechanism(
                    variable="Q",
                    family="linear",
                    family_params={"intercept": 9, "coefficients": {}, "noise_std": 3},
                ),
                small.mechanisms[1],
                NodeMechanism(
                    variable="U",
                    family="linear",
                    family_params={"intercept": 0, "coefficients": {}, "noise_std": 2},
                ),
                small.mechanisms[0].model_copy(
                    update={
                        "parents": ["U"],
                        "family_params": {"intercept": 0, "coefficients": {"U": 5}, "noise_std": 1},
                    }
                ),
            ],
        }
    )
    query = CausalQuery(
        query_type="soft_intervention",
        treatment_variable="X",
        outcome_variable="Y",
        intervention_spec={"type": "stochastic", "distribution": law},
        n_samples=2000,
    )
    results = []
    for model in (small, full):
        out = GCMQuery.pure_step(
            SCMQueryData(scm_spec=model, query=query),
            {"__seed__": 11, "enable_dowhy_comparison": False},
        )
        results.append(out["query_result"].result_distribution)
    assert results[0] == results[1]


def test_historical_schema_replay_remains_nongating_after_republication(tmp_path):
    query = CausalQuery(
        query_type="interventional", treatment_variable="X", outcome_variable="Y", treatment_value=0
    )
    old = {
        "schema_version": "1.1",
        "query": query.model_dump(mode="json"),
        "result_mean": 0,
        "result_std": 1,
        "result_ci": [-2, 2],
        "metadata": {},
    }
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_json(
        old,
        PutOptions(
            kind="ir.causal_query_result",
            media_type="application/json",
            schema=SchemaInfo(name="ir.causal_query_result", version="1.1"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    historical = load_causal_query_result(
        _ensure_ir_artifact_store(store),
        CausalQueryResultRef.model_validate(ref.model_dump(mode="json")),
    )
    assert historical.metadata["source_schema_version"] == "1.1"
    newref = persist_causal_query_result(_ensure_ir_artifact_store(store), historical)
    current = load_causal_query_result(_ensure_ir_artifact_store(FileSystemCAS(store.root)), newref)
    assert current.schema_version == "1.2" and current.estimator_interval is None
    assert current.metadata["historical_schema_replay"]["source_schema_version"] == "1.1"
    assert not current.to_uncertainty_envelope().gate_eligible
