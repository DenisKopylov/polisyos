from __future__ import annotations

import gc
import time

import polisyos.foundry.methods.catalog.causal.admg_ops as admg_ops
from polisyos.foundry.methods.catalog.causal.id_engine import id_algorithm
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType


def _make_graph(nodes: list[str], edges: list[CausalEdge]) -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=nodes,
        edges=edges,
    )


def _ba_like_graph(n_nodes: int, m: int) -> CausalGraphModel:
    nodes = [f"V{i}" for i in range(n_nodes)]
    edges: list[CausalEdge] = []
    for i in range(1, n_nodes):
        for j in range(max(0, i - m), i):
            edges.append(
                CausalEdge(
                    src=nodes[j],
                    dst=nodes[i],
                    mark_src=EdgeMark.TAIL,
                    mark_dst=EdgeMark.ARROW,
                )
            )
    return _make_graph(nodes, edges)


def _multilayer_graph(n_nodes: int, n_edges: int) -> CausalGraphModel:
    nodes = [f"M{i}" for i in range(n_nodes)]
    edges: list[CausalEdge] = []
    for i in range(n_nodes):
        for j in range(i + 1, n_nodes):
            edges.append(
                CausalEdge(
                    src=nodes[i],
                    dst=nodes[j],
                    mark_src=EdgeMark.TAIL,
                    mark_dst=EdgeMark.ARROW,
                )
            )
            if len(edges) >= n_edges:
                return _make_graph(nodes, edges)
    return _make_graph(nodes, edges)


def _reset_caches() -> None:
    admg_ops._ADJ_CACHE.clear()
    admg_ops._CC_CACHE.clear()
    admg_ops._GRAPH_REFS.clear()


def test_cached_adjacency_reuse() -> None:
    _reset_caches()
    graph = _ba_like_graph(80, 3)
    key = id(graph)
    admg_ops.ancestors(graph, frozenset({"V79"}))
    first = admg_ops._ADJ_CACHE[key]
    admg_ops.ancestors(graph, frozenset({"V79"}))
    second = admg_ops._ADJ_CACHE[key]
    assert first is second


def test_cached_adjacency_eviction() -> None:
    _reset_caches()
    graph = _ba_like_graph(40, 2)
    key = id(graph)
    admg_ops.ancestors(graph, frozenset({"V39"}))
    admg_ops.c_components(graph)
    assert key in admg_ops._ADJ_CACHE
    assert key in admg_ops._CC_CACHE
    del graph
    gc.collect()
    gc.collect()
    assert key not in admg_ops._ADJ_CACHE
    assert key not in admg_ops._CC_CACHE
    assert key not in admg_ops._GRAPH_REFS


def test_c_components_memoized() -> None:
    _reset_caches()
    graph = _make_graph(
        nodes=["A", "B", "C", "D"],
        edges=[
            CausalEdge(src="A", dst="B", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="B", dst="C", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="C", dst="D", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
    )
    first = admg_ops.c_components(graph)
    second = admg_ops.c_components(graph)
    assert first == second
    assert tuple(second) == admg_ops._CC_CACHE[id(graph)]


def test_model_construct_preserves_semantics() -> None:
    graph = _multilayer_graph(30, 120)
    subset = frozenset(graph.nodes[:20])
    optimized = admg_ops.induced_subgraph(graph, subset)

    kept_nodes = [n for n in graph.nodes if n in subset]
    kept_edges = [e for e in graph.edges if e.src in subset and e.dst in subset]
    validated = CausalGraphModel(
        schema_version=graph.schema_version,
        graph_type=graph.graph_type,
        nodes=kept_nodes,
        edges=kept_edges,
        discovery_method=graph.discovery_method,
        skg_version_id=graph.skg_version_id,
        pag_identification_policy=graph.pag_identification_policy,
        id_confidence_under_pag=graph.id_confidence_under_pag,
        metadata=dict(graph.metadata),
    )
    assert optimized.model_dump(mode="json") == validated.model_dump(mode="json")


def test_model_construct_no_validation_overhead() -> None:
    graph = _multilayer_graph(50, 500)
    subset = frozenset(graph.nodes[:35])
    kept_nodes = [n for n in graph.nodes if n in subset]
    kept_edges = [e for e in graph.edges if e.src in subset and e.dst in subset]

    for _ in range(10):
        admg_ops.induced_subgraph(graph, subset)
        CausalGraphModel(
            schema_version=graph.schema_version,
            graph_type=graph.graph_type,
            nodes=kept_nodes,
            edges=kept_edges,
            discovery_method=graph.discovery_method,
            skg_version_id=graph.skg_version_id,
            pag_identification_policy=graph.pag_identification_policy,
            id_confidence_under_pag=graph.id_confidence_under_pag,
            metadata=dict(graph.metadata),
        )

    t0 = time.perf_counter()
    for _ in range(100):
        admg_ops.induced_subgraph(graph, subset)
    optimized_ms = (time.perf_counter() - t0) * 1000.0

    t1 = time.perf_counter()
    for _ in range(100):
        CausalGraphModel(
            schema_version=graph.schema_version,
            graph_type=graph.graph_type,
            nodes=kept_nodes,
            edges=kept_edges,
            discovery_method=graph.discovery_method,
            skg_version_id=graph.skg_version_id,
            pag_identification_policy=graph.pag_identification_policy,
            id_confidence_under_pag=graph.id_confidence_under_pag,
            metadata=dict(graph.metadata),
        )
    validated_ms = (time.perf_counter() - t1) * 1000.0

    assert optimized_ms < validated_ms


def test_id_algorithm_ba_100() -> None:
    graph = _ba_like_graph(100, 3)
    start = time.perf_counter()
    result = id_algorithm(
        treatment=frozenset({"V0"}),
        outcome=frozenset({"V99"}),
        graph=graph,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert result.trace
    assert elapsed_ms < 100.0


def test_id_algorithm_ba_500() -> None:
    graph = _ba_like_graph(500, 3)
    start = time.perf_counter()
    result = id_algorithm(
        treatment=frozenset({"V0"}),
        outcome=frozenset({"V499"}),
        graph=graph,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert result.trace
    assert elapsed_ms < 800.0


def test_id_algorithm_multilayer_50x625() -> None:
    graph = _multilayer_graph(50, 625)
    start = time.perf_counter()
    result = id_algorithm(
        treatment=frozenset({"M0"}),
        outcome=frozenset({"M49"}),
        graph=graph,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert result.trace
    assert elapsed_ms < 250.0
