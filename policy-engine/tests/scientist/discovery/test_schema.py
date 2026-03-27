from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_discovery import CausalDiscoveryReport
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.scientist.discovery.schema import (
    ComputeFootprint,
    DiscoveryAlgorithmFamily,
    DiscoveryMethod,
    GraphHypothesis,
    edge_key_for_edge,
    infer_algorithm_family,
    graph_hypothesis_from_report,
    load_graph_hypothesis,
    persist_graph_hypothesis,
)


def _graph(
    *,
    graph_type: GraphType,
    edges: list[CausalEdge],
    nodes: list[str] | None = None,
    discovery_method: str = "",
) -> CausalGraphModel:
    resolved_nodes = nodes or sorted({node for edge in edges for node in (edge.src, edge.dst)})
    return CausalGraphModel(
        graph_type=graph_type,
        nodes=resolved_nodes,
        edges=edges,
        discovery_method=discovery_method,
    )


def test_graph_hypothesis_uses_shared_bootstrap_then_combined_then_data_confidence() -> None:
    edge = CausalEdge(
        src="X",
        dst="Y",
        lag=2,
        combined_confidence=0.81,
        data_confidence=0.37,
    )
    report = CausalDiscoveryReport(
        method="pc",
        graph=_graph(graph_type=GraphType.CPDAG, edges=[edge], discovery_method="pc"),
        bootstrap_stability={edge_key_for_edge(edge): 0.99},
    )

    hypothesis_with_shared = graph_hypothesis_from_report(
        report,
        hypothesis_id="shared",
        shared_bootstrap_stability={edge_key_for_edge(edge): 0.62},
    )
    hypothesis_without_shared = graph_hypothesis_from_report(
        report,
        hypothesis_id="local",
    )

    assert edge_key_for_edge(edge) == "X->Y@lag=2"
    assert hypothesis_with_shared.edge_confidence["X->Y@lag=2"] == 0.62
    assert hypothesis_without_shared.edge_confidence["X->Y@lag=2"] == 0.81


def test_graph_hypothesis_persists_and_loads_from_cas(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    graph = _graph(
        graph_type=GraphType.DAG,
        edges=[CausalEdge(src="X", dst="Y", combined_confidence=0.7)],
        discovery_method="dagma",
    )
    hypothesis = GraphHypothesis(
        hypothesis_id="dagma_0",
        algorithm_family=DiscoveryAlgorithmFamily.SCORE_BASED,
        method=DiscoveryMethod.DAGMA,
        graph=graph,
        edge_confidence={"X->Y": 0.7},
        assumptions=["continuous optimization over DAG structure"],
        compute_footprint=ComputeFootprint(
            runtime_seconds=1.25,
            timeout_seconds=30.0,
            n_samples=100,
            n_variables=2,
            n_bootstrap=0,
            random_seed=7,
            backend="optimizer=dagma",
            method_params={"alpha": 0.1},
            metadata={"report_method": "dagma"},
        ),
        metadata={"source": "unit_test"},
    )

    ref = persist_graph_hypothesis(store, hypothesis)
    loaded = load_graph_hypothesis(store, ref)

    assert ref.kind == "scientist.graph_hypothesis"
    assert loaded == hypothesis


def test_graph_hypothesis_extracts_failure_reasons_from_report_warnings() -> None:
    report = CausalDiscoveryReport(
        method="fci",
        graph=_graph(
            graph_type=GraphType.PAG,
            edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW)],
            discovery_method="fci",
        ),
        warnings=[
            "algorithm_failed:TimeoutError: backend timed out",
            "soft warning that should remain informational",
        ],
        metadata={"backend": "optional"},
    )

    hypothesis = graph_hypothesis_from_report(report, hypothesis_id="fci_0")

    assert hypothesis.method is DiscoveryMethod.FCI
    assert hypothesis.algorithm_family is DiscoveryAlgorithmFamily.CONSTRAINT_BASED
    assert hypothesis.failure_reasons == ["algorithm_failed:TimeoutError: backend timed out"]
    assert "soft warning that should remain informational" in hypothesis.warnings


def test_infer_algorithm_family_supports_functional_methods() -> None:
    assert infer_algorithm_family(DiscoveryMethod.ANM) is DiscoveryAlgorithmFamily.FUNCTIONAL
    assert (
        infer_algorithm_family(DiscoveryMethod.PAIRWISE_HEURISTIC)
        is DiscoveryAlgorithmFamily.FUNCTIONAL
    )
