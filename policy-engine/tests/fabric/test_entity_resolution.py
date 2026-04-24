from __future__ import annotations

from pathlib import Path

import pandas as pd

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.entity_resolution import (
    EntityMatchStore,
    EntityRecord,
    ProbabilisticEntityResolver,
)
from polisyos.fabric.world.materialize import (
    WorldGraphEdgeRecord,
    WorldGraphNodeRecord,
    WorldGraphSnapshot,
    build_world_kuzu_conflict_query,
    build_world_kuzu_policy_impact_query,
    query_world_conflict_neighborhood,
    query_world_entity_neighborhood,
    query_world_kuzu_conflict_neighborhood,
    query_world_kuzu_entity_neighborhood,
    query_world_kuzu_policy_impact,
    query_world_kuzu_source_overlap,
    query_world_policy_impact,
    query_world_source_overlap,
)


def test_probabilistic_entity_resolution_is_explainable_and_reversible(tmp_path: Path) -> None:
    resolver = ProbabilisticEntityResolver()
    records = [
        EntityRecord(
            entity_id="wb:usa",
            canonical_name="United States",
            source="worldbank",
            aliases=["USA", "United States of America"],
            identifiers={"iso3": "USA"},
            attributes={"region": "north_america"},
        ),
        EntityRecord(
            entity_id="who:us",
            canonical_name="United States of America",
            source="who",
            aliases=["United States", "USA"],
            identifiers={"iso3": "USA"},
            attributes={"region": "north_america"},
        ),
        EntityRecord(
            entity_id="unesco:fr",
            canonical_name="France",
            source="unesco",
            aliases=["French Republic"],
            identifiers={"iso3": "FRA"},
            attributes={"region": "europe"},
        ),
    ]

    matches = resolver.resolve(records, min_confidence=0.6)

    assert len(matches) == 1
    candidate = matches[0]
    assert candidate.left_source == "worldbank"
    assert candidate.right_source == "who"
    assert candidate.confidence >= 0.6
    assert any(item.evidence_type == "identifier_overlap" for item in candidate.evidence)

    store = EntityMatchStore(FileSystemCAS(tmp_path / "cas"))
    batch_ref = store.persist_candidates(
        matches, method=resolver.method, metadata={"fixture": "true"}
    )
    loaded = store.load_candidates(batch_ref.artifact_id)
    assert loaded.candidates[0].match_id == candidate.match_id

    override_ref = store.persist_override(
        candidate,
        status="accepted",
        provenance_ref="sha256:" + ("a" * 64),
    )
    override_payload = store.load_candidates(batch_ref.artifact_id)
    assert override_ref.kind == "fabric.entity_resolution.override"
    assert override_payload.candidates[0].override_status == "candidate"


def _build_graph_snapshot() -> WorldGraphSnapshot:
    nodes = [
        WorldGraphNodeRecord(node_id="source.worldbank", kind="doc_source", label="World Bank"),
        WorldGraphNodeRecord(node_id="source.unesco", kind="doc_source", label="UNESCO"),
        WorldGraphNodeRecord(node_id="entity.usa", kind="entity.country", label="United States"),
        WorldGraphNodeRecord(node_id="metric.gdp", kind="metric", label="GDP"),
        WorldGraphNodeRecord(node_id="policy.tax", kind="policy_domain", label="Tax Policy"),
        WorldGraphNodeRecord(node_id="conflict.gdp", kind="conflict.record", label="GDP conflict"),
    ]
    edges = [
        WorldGraphEdgeRecord(
            source_id="source.worldbank", target_id="entity.usa", kind="source.describes"
        ),
        WorldGraphEdgeRecord(
            source_id="source.unesco", target_id="entity.usa", kind="source.describes"
        ),
        WorldGraphEdgeRecord(
            source_id="entity.usa", target_id="metric.gdp", kind="metric.references"
        ),
        WorldGraphEdgeRecord(source_id="entity.usa", target_id="policy.tax", kind="policy.impacts"),
        WorldGraphEdgeRecord(
            source_id="entity.usa", target_id="conflict.gdp", kind="conflict.flagged"
        ),
        WorldGraphEdgeRecord(
            source_id="conflict.gdp", target_id="metric.gdp", kind="conflict.about"
        ),
    ]
    return WorldGraphSnapshot(nodes, edges)


def test_world_graph_helpers_answer_overlap_conflict_and_policy_questions() -> None:
    snapshot = _build_graph_snapshot()

    neighborhood = query_world_entity_neighborhood(snapshot, "entity.usa", max_hops=2)
    overlap = query_world_source_overlap(snapshot, "entity.usa", max_hops=1)
    conflicts = query_world_conflict_neighborhood(snapshot, "entity.usa", max_hops=2)
    impact = query_world_policy_impact(snapshot, "entity.usa", max_hops=2)

    assert {node.node_id for node in neighborhood.nodes} >= {
        "entity.usa",
        "source.worldbank",
        "source.unesco",
        "policy.tax",
    }
    assert {node.node_id for node in overlap.overlapping_sources} == {
        "source.worldbank",
        "source.unesco",
    }
    assert {node.node_id for node in conflicts.conflict_nodes} == {"conflict.gdp"}
    assert {node.node_id for node in impact.impacted_nodes} == {"policy.tax"}


def test_world_kuzu_query_builders_encode_conflict_and_policy_filters() -> None:
    conflict_query, conflict_params = build_world_kuzu_conflict_query("entity.usa", max_hops=2)
    impact_query, impact_params = build_world_kuzu_policy_impact_query("entity.usa", max_hops=3)

    assert "CONTAINS 'conflict'" in conflict_query
    assert "neighbor.kind CONTAINS 'policy'" in impact_query
    assert conflict_params == {"node_id": "entity.usa"}
    assert impact_params == {"node_id": "entity.usa"}


class _FakeKuzuResult:
    def __init__(self, frame: pd.DataFrame) -> None:
        self._frame = frame

    def get_as_df(self) -> pd.DataFrame:
        return self._frame


class _FakeKuzuConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def execute(self, query: str, params: dict[str, object]) -> _FakeKuzuResult:
        self.calls.append((query, params))
        if "UNWIND NODES(path) AS node" in query:
            return _FakeKuzuResult(
                pd.DataFrame(
                    [
                        {
                            "node_id": "entity.usa",
                            "kind": "entity.country",
                            "label": "United States",
                            "artifact_id": None,
                        },
                        {
                            "node_id": "source.worldbank",
                            "kind": "doc_source",
                            "label": "World Bank",
                            "artifact_id": None,
                        },
                        {
                            "node_id": "source.unesco",
                            "kind": "doc_source",
                            "label": "UNESCO",
                            "artifact_id": None,
                        },
                        {
                            "node_id": "policy.tax",
                            "kind": "policy_domain",
                            "label": "Tax Policy",
                            "artifact_id": None,
                        },
                        {
                            "node_id": "conflict.gdp",
                            "kind": "conflict.record",
                            "label": "GDP conflict",
                            "artifact_id": None,
                        },
                    ]
                )
            )
        if "RETURN DISTINCT edge.edge_id AS edge_id" in query:
            return _FakeKuzuResult(
                pd.DataFrame(
                    [
                        {"edge_id": "edge.source.worldbank"},
                        {"edge_id": "edge.source.unesco"},
                        {"edge_id": "edge.policy.tax"},
                        {"edge_id": "edge.conflict.gdp"},
                    ]
                )
            )
        if "WHERE edge.edge_id IN $edge_ids" in query:
            assert params["edge_ids"] == [
                "edge.conflict.gdp",
                "edge.policy.tax",
                "edge.source.unesco",
                "edge.source.worldbank",
            ]
            return _FakeKuzuResult(
                pd.DataFrame(
                    [
                        {
                            "source_id": "source.worldbank",
                            "target_id": "entity.usa",
                            "kind": "source.describes",
                            "predicate_id": None,
                            "tx_time": None,
                            "valid_time": None,
                            "confidence": None,
                            "weight": None,
                            "event_id": None,
                        },
                        {
                            "source_id": "source.unesco",
                            "target_id": "entity.usa",
                            "kind": "source.describes",
                            "predicate_id": None,
                            "tx_time": None,
                            "valid_time": None,
                            "confidence": None,
                            "weight": None,
                            "event_id": None,
                        },
                        {
                            "source_id": "entity.usa",
                            "target_id": "policy.tax",
                            "kind": "policy.impacts",
                            "predicate_id": None,
                            "tx_time": None,
                            "valid_time": None,
                            "confidence": None,
                            "weight": None,
                            "event_id": None,
                        },
                        {
                            "source_id": "entity.usa",
                            "target_id": "conflict.gdp",
                            "kind": "conflict.flagged",
                            "predicate_id": None,
                            "tx_time": None,
                            "valid_time": None,
                            "confidence": None,
                            "weight": None,
                            "event_id": None,
                        },
                    ]
                )
            )
        raise AssertionError(f"Unexpected Kuzu query: {query}")


def test_live_kuzu_helpers_execute_graph_reasoning_queries() -> None:
    conn = _FakeKuzuConnection()

    neighborhood = query_world_kuzu_entity_neighborhood(conn, "entity.usa", max_hops=2)
    overlap = query_world_kuzu_source_overlap(conn, "entity.usa", max_hops=2)
    conflicts = query_world_kuzu_conflict_neighborhood(conn, "entity.usa", max_hops=2)
    impact = query_world_kuzu_policy_impact(conn, "entity.usa", max_hops=2)

    assert {node.node_id for node in neighborhood.nodes} >= {
        "entity.usa",
        "source.worldbank",
        "source.unesco",
        "policy.tax",
    }
    assert {node.node_id for node in overlap.overlapping_sources} == {
        "source.worldbank",
        "source.unesco",
    }
    assert {node.node_id for node in conflicts.conflict_nodes} == {"conflict.gdp"}
    assert {node.node_id for node in impact.impacted_nodes} == {"policy.tax"}
    assert any("UNWIND NODES(path) AS node" in query for query, _ in conn.calls)
    assert any("WHERE edge.edge_id IN $edge_ids" in query for query, _ in conn.calls)
