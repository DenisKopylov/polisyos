from __future__ import annotations

import math

import numpy as np
import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
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
    load_structural_causal_model_spec,
    persist_structural_causal_model_spec,
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
        params={"fit_backend": "native_hybrid"},
    )
    return result["scm_spec"]


def test_twin_query_excludes_missing_disconnected_root_after_perfect_surgery(tmp_path) -> None:
    """A missing unrelated law and the replaced root do not block Y=X²."""
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.canon import CanonSpec, from_canonical_bytes
    from polisyos.foundry.methods.registry import MethodRegistry
    from polisyos.scientist.compute.job_spec import JobSpec
    from polisyos.scientist.compute.runner import run_job

    graph = _graph(("X", "Y"), nodes=["X", "Y", "Z"])
    polynomial = NodeMechanism(
        variable="Y",
        parents=["X"],
        family=MechanismFamily.ADDITIVE_NOISE,
        family_params={
            "fit_mode": "additive_noise_poly",
            "poly_degree": 2,
            "poly_coefficients": {"__intercept__": 0.0, "X^1": 0.0, "X^2": 1.0},
            "noise_std": 0.0,
        },
        source=MechanismSource.DEFAULT,
    )
    scm = StructuralCausalModelSpec(graph=graph, mechanisms=[polynomial], fit_method="manual")
    original = graph.model_dump(mode="json")
    twin_data = TwinNetworkQueryData(
        scm_spec=scm,
        factual_condition={},
        treatment_variable="X",
        factual_treatment_value=1.0,
        counterfactual_treatment_value=2.0,
        outcome_variable="Y",
        n_samples=32,
    )
    result = TwinNetworkQuery.pure_step(twin_data, params={"__seed__": 7})["twin_network_result"]
    assert result.ite_mean == pytest.approx(3.0)
    assert result.po_factual_mean == pytest.approx(1.0)
    assert result.po_counter_mean == pytest.approx(4.0)
    assert graph.model_dump(mode="json") == original
    single = GCMQuery.pure_step(
        SCMQueryData(
            scm_spec=scm,
            query={
                "query_type": "interventional",
                "treatment_variable": "X",
                "treatment_value": 2.0,
                "outcome_variable": "Y",
                "n_samples": 32,
            },
        ),
        params={"__seed__": 7, "enable_dowhy_comparison": False},
    )["query_result"]
    assert single.result_mean == pytest.approx(4.0)

    for irrelevant_value in (0.0, 1.0e9):
        irrelevant = NodeMechanism(
            variable="Z",
            parents=[],
            family=MechanismFamily.LINEAR,
            family_params={"intercept": irrelevant_value, "noise_std": 0.0},
        )
        control = StructuralCausalModelSpec(
            graph=graph, mechanisms=[polynomial, irrelevant], fit_method="manual"
        )
        controlled_twin = TwinNetworkQuery.pure_step(
            twin_data.model_copy(update={"scm_spec": control}), params={"__seed__": 7}
        )["twin_network_result"]
        controlled_query = GCMQuery.pure_step(
            SCMQueryData(scm_spec=control, query=single.query),
            params={"__seed__": 7, "enable_dowhy_comparison": False},
        )["query_result"]
        assert controlled_twin.ite_distribution == result.ite_distribution
        assert controlled_twin.po_factual_distribution == result.po_factual_distribution
        assert controlled_twin.po_counter_distribution == result.po_counter_distribution
        assert controlled_query.result_distribution == single.result_distribution

    store = FileSystemCAS(tmp_path / "cas")
    input_ref = store.put_json(
        twin_data.model_dump(mode="json"),
        PutOptions(
            kind="tests.twin_query_data",
            media_type="application/json",
            schema=SchemaInfo(name="tests.TwinQueryData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    MethodRegistry.get_instance().register(TwinNetworkQuery, override=True)
    job = run_job(
        JobSpec(
            job_kind="method",
            method_fqn=TwinNetworkQuery.signature.fqn,
            input_refs={"twin_network_query_data": input_ref},
            seed=7,
        ),
        cas_root=store.root,
        method_state=twin_data,
    )
    assert not job.issues, job.issues
    assert job.method_result_ref is not None
    registered = from_canonical_bytes(store.get_bytes(job.method_result_ref))["twin_network_result"]
    assert registered["ite_distribution"] == result.ite_distribution
    assert registered["po_factual_distribution"] == result.po_factual_distribution
    assert registered["po_counter_distribution"] == result.po_counter_distribution

    required_graph = _graph(("X", "Y"), ("Z", "Y"), nodes=["X", "Y", "Z"])
    required = polynomial.model_copy(
        update={
            "parents": ["X", "Z"],
            "family_params": {
                "fit_mode": "additive_noise_poly",
                "poly_degree": 2,
                "poly_coefficients": {
                    "__intercept__": 0.0,
                    "X^1": 0.0,
                    "X^2": 1.0,
                    "Z^1": 1.0,
                    "Z^2": 0.0,
                },
                "noise_std": 0.0,
            },
        }
    )
    required_scm = StructuralCausalModelSpec(
        graph=required_graph, mechanisms=[required], fit_method="manual"
    )
    with pytest.raises(ValueError, match=r"required root.*Z"):
        TwinNetworkQuery.pure_step(
            TwinNetworkQueryData(
                scm_spec=required_scm,
                factual_condition={},
                treatment_variable="X",
                factual_treatment_value=1.0,
                counterfactual_treatment_value=2.0,
                outcome_variable="Y",
                n_samples=8,
            ),
            params={"__seed__": 7},
        )


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
    spec = StructuralCausalModelSpec.model_validate_json(spec.model_dump_json())

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

    non_empirical_root = mechanisms["Z"].model_copy(update={"family": MechanismFamily.LINEAR})
    with pytest.raises(ValueError, match="require an EMPIRICAL mechanism"):
        StructuralCausalModelSpec(
            graph=spec.graph,
            source_graph=spec.source_graph,
            source_graph_ref=spec.source_graph_ref,
            graph_projection=spec.graph_projection,
            mechanisms=[mechanism for mechanism in spec.mechanisms if mechanism.variable != "Z"]
            + [non_empirical_root],
            fitted=True,
            fit_method=spec.fit_method,
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
            source_graph=spec.source_graph,
            source_graph_ref=spec.source_graph_ref,
            graph_projection=spec.graph_projection,
            mechanisms=[mechanism for mechanism in spec.mechanisms if mechanism.variable != "Z"]
            + [broken_root],
            fitted=True,
            fit_method=spec.fit_method,
        )

    for field in ("observed_samples_source", "observed_sample_alignment", "joint_sample_group"):
        foreign = mechanisms["Z"].model_copy(
            update={"family_params": {**mechanisms["Z"].family_params, field: "foreign"}}
        )
        with pytest.raises(ValueError, match="share provenance and alignment"):
            StructuralCausalModelSpec(
                graph=spec.graph,
                source_graph=spec.source_graph,
                source_graph_ref=spec.source_graph_ref,
                graph_projection=spec.graph_projection,
                mechanisms=[mechanism for mechanism in spec.mechanisms if mechanism.variable != "Z"]
                + [foreign],
                fitted=True,
                fit_method=spec.fit_method,
            )

    query = SCMQueryData(
        scm_spec=spec,
        query={
            "query_type": "interventional",
            "treatment_variable": "T",
            "treatment_value": 1.0,
            "outcome_variable": "Y",
            "n_samples": 1024,
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
                source=MechanismSource.DEFAULT,
            )
        ],
        fitted=False,
        fit_method="manual",
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
    assert result["query_result"].metadata["declared_root_hypothesis"] == ["Z"]
    assert result["envelope"].gate_eligible is False


def test_declared_polynomial_candidate_executes_and_linear_control_remains_linear() -> None:
    graph = _graph(("X", "Y"), nodes=["X", "Y"])

    polynomial_spec = StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable="X",
                parents=[],
                family=MechanismFamily.EMPIRICAL,
                family_params={"mean": 0.0, "std": 1.0},
                source=MechanismSource.DEFAULT,
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
                source=MechanismSource.DEFAULT,
            ),
        ],
        fitted=False,
        fit_method="manual",
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
                source=MechanismSource.DEFAULT,
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
                source=MechanismSource.DEFAULT,
            ),
        ],
        fitted=False,
        fit_method="manual",
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


def test_polynomial_fitter_payload_survives_fresh_scm_and_query(tmp_path) -> None:
    """A real declared polynomial fitter, persisted model and query retain x²."""
    x = np.linspace(-2.0, 2.0, 101)
    fitted_params = gcm_fit_module._fit_additive_noise_poly(x**2, x.reshape(-1, 1), ["X"], degree=2)
    model = StructuralCausalModelSpec(
        graph=_graph(("X", "Y"), nodes=["X", "Y"]),
        mechanisms=[
            NodeMechanism(
                variable="X",
                parents=[],
                family=MechanismFamily.EMPIRICAL,
                family_params={"mean": 0.0, "std": 1.0},
            ),
            NodeMechanism(
                variable="Y",
                parents=["X"],
                family=MechanismFamily.ADDITIVE_NOISE,
                family_params=fitted_params,
            ),
        ],
        fit_method="manual",
    )
    store = FileSystemCAS(tmp_path / "cas")
    selected = persist_structural_causal_model_spec(ensure_ir_artifact_store(store), model)
    restored = load_structural_causal_model_spec(
        ensure_ir_artifact_store(FileSystemCAS(store.root)), selected
    )
    query = SCMQueryData(
        scm_spec=restored,
        query={
            "query_type": "interventional",
            "treatment_variable": "X",
            "treatment_value": 2.0,
            "outcome_variable": "Y",
            "n_samples": 32,
        },
    )
    result = GCMQuery.pure_step(query, {"__seed__": 17, "enable_dowhy_comparison": False})[
        "query_result"
    ]
    assert result.result_mean == pytest.approx(4.0, abs=1e-10, rel=0)
    assert restored.mechanisms[1].family_params["fit_mode"] == "additive_noise_poly"


def test_twin_query_reuses_shared_noise_with_polynomial_payload() -> None:
    spec = StructuralCausalModelSpec(
        graph=_graph(("X", "Y"), nodes=["X", "Y"]),
        mechanisms=[
            NodeMechanism(
                variable="X",
                parents=[],
                family=MechanismFamily.EMPIRICAL,
                family_params={"mean": 0.0, "std": 1.0},
                source=MechanismSource.DEFAULT,
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
                source=MechanismSource.DEFAULT,
            ),
        ],
        fitted=False,
        fit_method="manual",
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

    # With X=1,Y=1.25 actually observed, the shared polynomial residual is
    # .25.  Both prediction paths must use that residual rather than a linear
    # surrogate or an imputed parent.
    factual = {"X": 1.0, "Y": 1.25}
    conditioned = TwinNetworkQuery.pure_step(
        TwinNetworkQueryData(
            scm_spec=spec,
            treatment_variable="X",
            outcome_variable="Y",
            factual_treatment_value=1.0,
            counterfactual_treatment_value=2.0,
            factual_condition=factual,
            n_samples=32,
        ),
        params={"__seed__": 23},
    )["twin_network_result"]
    assert conditioned.po_factual_mean == pytest.approx(1.25, abs=1e-12, rel=0)
    assert conditioned.po_counter_mean == pytest.approx(4.25, abs=1e-12, rel=0)
    assert conditioned.metadata["abduction_profile"] == "exact_residual_fallback"
    single = GCMQuery.pure_step(
        SCMQueryData(
            scm_spec=spec,
            query={
                "query_type": "counterfactual",
                "treatment_variable": "X",
                "treatment_value": 2.0,
                "outcome_variable": "Y",
                "condition": factual,
                "n_samples": 32,
            },
        ),
        params={"__seed__": 23, "enable_dowhy_comparison": False},
    )["query_result"]
    assert single.result_mean == pytest.approx(4.25, abs=1e-12, rel=0)

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
        fitted=False,
        fit_method="manual",
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
        fitted=False,
        fit_method="manual",
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
