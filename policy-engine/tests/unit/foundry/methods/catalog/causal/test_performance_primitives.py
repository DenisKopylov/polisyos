from __future__ import annotations

import gc
import time
import weakref

import pytest

import polisyos.foundry.methods.catalog.causal.admg_ops as admg_ops
from polisyos.foundry.methods.catalog.causal.id_engine import id_algorithm
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    EdgeSource,
    GraphType,
)


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


def _cache_probe_graph(index: int) -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
        metadata={"cache-probe-index": index},
    )


def test_cached_adjacency_reuse() -> None:
    _reset_caches()
    graph = _ba_like_graph(80, 3)
    key = admg_ops._graph_content_cache_key(admg_ops.canonical_scalar_query_graph(graph))
    admg_ops.ancestors(graph, frozenset({"V79"}))
    first = admg_ops._ADJ_CACHE[key]
    admg_ops.ancestors(graph, frozenset({"V79"}))
    second = admg_ops._ADJ_CACHE[key]
    assert first is second
    equivalent = _ba_like_graph(80, 3)
    assert admg_ops._get_cached_adjacency(equivalent) is first


def test_cached_adjacency_and_components_are_content_lru_bounded() -> None:
    _reset_caches()
    capacity = admg_ops._STATIC_GRAPH_CACHE_CAPACITY
    graphs = [_cache_probe_graph(index) for index in range(capacity + 2)]
    source_refs = [weakref.ref(graph) for graph in graphs]
    keys = [
        admg_ops._graph_content_cache_key(admg_ops.canonical_scalar_query_graph(graph))
        for graph in graphs
    ]

    for graph in graphs:
        admg_ops._get_cached_adjacency(graph)
        admg_ops.c_components(graph)
    del graph

    assert len(graphs) > capacity
    assert all(reference() is not None for reference in source_refs)
    assert len(admg_ops._ADJ_CACHE) == capacity
    assert len(admg_ops._CC_CACHE) == capacity
    assert keys[0] not in admg_ops._ADJ_CACHE and keys[0] not in admg_ops._CC_CACHE
    assert keys[1] not in admg_ops._ADJ_CACHE and keys[1] not in admg_ops._CC_CACHE
    assert keys[2] in admg_ops._ADJ_CACHE and keys[2] in admg_ops._CC_CACHE

    most_recent_graph = graphs[2]
    most_recent_adjacency = admg_ops._ADJ_CACHE[keys[2]]
    most_recent_components = admg_ops._CC_CACHE[keys[2]]
    assert admg_ops._get_cached_adjacency(most_recent_graph) is most_recent_adjacency
    assert tuple(admg_ops.c_components(most_recent_graph)) == most_recent_components

    extra = _cache_probe_graph(capacity + 2)
    extra_key = admg_ops._graph_content_cache_key(admg_ops.canonical_scalar_query_graph(extra))
    admg_ops._get_cached_adjacency(extra)
    admg_ops.c_components(extra)
    assert len(admg_ops._ADJ_CACHE) == capacity
    assert len(admg_ops._CC_CACHE) == capacity
    assert keys[2] in admg_ops._ADJ_CACHE and keys[2] in admg_ops._CC_CACHE
    assert keys[3] not in admg_ops._ADJ_CACHE and keys[3] not in admg_ops._CC_CACHE
    assert extra_key in admg_ops._ADJ_CACHE and extra_key in admg_ops._CC_CACHE

    duplicate = _cache_probe_graph(capacity + 2)
    assert admg_ops._get_cached_adjacency(duplicate) is admg_ops._ADJ_CACHE[extra_key]
    assert tuple(admg_ops.c_components(duplicate)) == admg_ops._CC_CACHE[extra_key]
    assert len(admg_ops._ADJ_CACHE) == capacity
    assert len(admg_ops._CC_CACHE) == capacity

    retained_key = keys[-1]
    retained_source = graphs[-1]
    retained_ref = weakref.ref(retained_source)
    del retained_source
    del graphs[-1]
    gc.collect()
    assert retained_ref() is None
    assert retained_key in admg_ops._ADJ_CACHE
    assert retained_key in admg_ops._CC_CACHE


@pytest.mark.parametrize(
    "mutation",
    [
        "nodes_append",
        "edges_clear",
        "edge_sources_append",
        "edge_metadata_nested_append",
        "graph_metadata_nested_append",
    ],
)
def test_published_graph_rejects_nested_topology_mutation(mutation: str) -> None:
    """Frozen publication rejects hostile mutations of every topology container."""
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["A", "B"],
        edges=[
            CausalEdge(
                src="A",
                dst="B",
                sources=[EdgeSource.DATA],
                metadata={"lineage": {"tags": ["source"]}},
            )
        ],
        metadata={"lineage": {"tags": ["source"]}},
    )
    mutations = {
        "nodes_append": lambda: graph.nodes.append("C"),
        "edges_clear": graph.edges.clear,
        "edge_sources_append": lambda: graph.edges[0].sources.append(EdgeSource.EXPERT),
        "edge_metadata_nested_append": lambda: graph.edges[0]
        .metadata["lineage"]["tags"]
        .append("hostile"),
        "graph_metadata_nested_append": lambda: graph.metadata["lineage"]["tags"].append("hostile"),
    }

    with pytest.raises((AttributeError, TypeError)):
        mutations[mutation]()


def test_warmed_derived_rows_are_not_reused_after_copy_update() -> None:
    """A new graph version has cold export rows and cold read-only adjacency state."""
    _reset_caches()
    graph = _make_graph(
        nodes=["A", "B"],
        edges=[CausalEdge(src="A", dst="B")],
    )
    assert graph.kuzu_edge_rows[0]["src"] == "A"

    updated = graph.model_copy(update={"edges": []})

    assert updated.kuzu_edge_rows == ()
    assert admg_ops.extract_directed_edges(updated) == frozenset()
    assert admg_ops.ancestors(updated, frozenset({"B"})) == frozenset({"B"})


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
    key = admg_ops._graph_content_cache_key(admg_ops.canonical_scalar_query_graph(graph))
    assert tuple(second) == admg_ops._CC_CACHE[key]


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
