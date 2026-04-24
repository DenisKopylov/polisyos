"""Tests for PROV-JSON round-trip serialization — WS4 provenance."""

from __future__ import annotations

import sys
from datetime import datetime

sys.path.insert(0, "src")

from polisyos.core.contracts.provenance import (
    ActivityType,
    AgentType,
    EntityType,
    ProvenanceActivity,
    ProvenanceAgent,
    ProvenanceCoreGraph,
    ProvenanceEntity,
)
from polisyos.scientist.provenance.prov_json import from_prov_json, to_prov_json


def _build_sample_graph() -> ProvenanceCoreGraph:
    """Build a minimal ProvenanceCoreGraph for round-trip testing."""
    graph = ProvenanceCoreGraph(graph_id="test-graph")

    t0 = datetime(2026, 3, 1, 10, 0, 0)
    t1 = datetime(2026, 3, 1, 10, 5, 0)

    # Entities
    graph.add_entity(
        ProvenanceEntity(
            entity_id="entity:ds1",
            entity_type=EntityType.DATASET,
            label="Dataset 1",
            created_at=t0,
            attributes={"source": "test"},
        )
    )
    graph.add_entity(
        ProvenanceEntity(
            entity_id="entity:ds2",
            entity_type=EntityType.METRIC,
            label="Metric output",
            created_at=t1,
        )
    )

    # Activities
    graph.add_activity(
        ProvenanceActivity(
            activity_id="activity:etl1",
            activity_type=ActivityType.ETL,
            label="ETL step 1",
            started_at=t0,
            ended_at=t1,
            parameters={"batch_size": 100},
        )
    )

    # Agents
    graph.add_agent(
        ProvenanceAgent(
            agent_id="agent:sys1",
            agent_type=AgentType.SYSTEM,
            label="Test system",
            metadata={"env": "test"},
        )
    )

    # Relations
    graph.add_usage(
        activity_id="activity:etl1",
        entity_id="entity:ds1",
        timestamp=t0,
    )
    graph.add_generation(
        entity_id="entity:ds2",
        activity_id="activity:etl1",
        timestamp=t1,
    )
    graph.add_derivation(
        derived_id="entity:ds2",
        source_id="entity:ds1",
        timestamp=t1,
    )
    graph.add_association(
        activity_id="activity:etl1",
        agent_id="agent:sys1",
        timestamp=t0,
    )

    return graph


class TestProvJsonRoundTrip:
    def test_round_trip_preserves_entities(self) -> None:
        original = _build_sample_graph()
        serialized = to_prov_json(original)
        restored = from_prov_json(serialized)

        assert set(restored.entities.keys()) == set(original.entities.keys())
        for eid in original.entities:
            assert restored.entities[eid].entity_type == original.entities[eid].entity_type
            assert restored.entities[eid].label == original.entities[eid].label

    def test_round_trip_preserves_activities(self) -> None:
        original = _build_sample_graph()
        serialized = to_prov_json(original)
        restored = from_prov_json(serialized)

        assert set(restored.activities.keys()) == set(original.activities.keys())
        for aid in original.activities:
            assert restored.activities[aid].activity_type == original.activities[aid].activity_type
            assert restored.activities[aid].label == original.activities[aid].label

    def test_round_trip_preserves_agents(self) -> None:
        original = _build_sample_graph()
        serialized = to_prov_json(original)
        restored = from_prov_json(serialized)

        assert set(restored.agents.keys()) == set(original.agents.keys())
        for gid in original.agents:
            assert restored.agents[gid].agent_type == original.agents[gid].agent_type
            assert restored.agents[gid].label == original.agents[gid].label

    def test_round_trip_preserves_edge_relations(self) -> None:
        original = _build_sample_graph()
        serialized = to_prov_json(original)
        restored = from_prov_json(serialized)

        original_tuples = {(e.source_id, e.target_id, e.relation) for e in original.edges}
        restored_tuples = {(e.source_id, e.target_id, e.relation) for e in restored.edges}

        assert original_tuples == restored_tuples

    def test_serialized_has_prov_json_keys(self) -> None:
        graph = _build_sample_graph()
        doc = to_prov_json(graph)

        assert "prefix" in doc
        assert "entity" in doc
        assert "activity" in doc
        assert "agent" in doc
        assert "used" in doc
        assert "wasGeneratedBy" in doc
        assert "wasDerivedFrom" in doc
        assert "wasAssociatedWith" in doc
