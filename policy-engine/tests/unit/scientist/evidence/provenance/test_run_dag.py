"""Tests for RunProvenanceDAG — WS4 provenance tracking."""

from __future__ import annotations

import sys
from datetime import datetime

sys.path.insert(0, "src")

from polisyos.scientist.evidence.provenance.run_dag import RunProvenanceDAG


class _FakeRef:
    """Minimal stand-in for ArtifactRef with an artifact_id attribute."""

    def __init__(self, artifact_id: str) -> None:
        self.artifact_id = artifact_id


class TestEmptyDAG:
    def test_empty_dag(self) -> None:
        dag = RunProvenanceDAG(run_id="run-001")
        graph = dag.finalize()

        # Should contain exactly the system agent
        assert len(graph.agents) == 1
        system_agent_id = "agent:system:run-001"
        assert system_agent_id in graph.agents
        assert graph.agents[system_agent_id].agent_type.value == "system"

        # No activities or entities yet
        assert len(graph.activities) == 0
        assert len(graph.entities) == 0


class TestRecordNodeExecution:
    def test_record_node_execution(self) -> None:
        dag = RunProvenanceDAG(run_id="run-002")
        t0 = datetime(2026, 1, 1, 10, 0, 0)
        t1 = datetime(2026, 1, 1, 10, 5, 0)

        input_ref = _FakeRef("input-artifact-1")
        output_ref = _FakeRef("output-artifact-1")

        dag.record_node_execution(
            alias="data_load",
            node_id="node-abc",
            started_at=t0,
            ended_at=t1,
            input_refs=[input_ref],
            output_refs=[output_ref],
        )

        graph = dag.finalize()

        # Activity should be recorded
        activity_id = "activity:node:run-002:data_load"
        assert activity_id in graph.activities
        act = graph.activities[activity_id]
        assert act.started_at == t0
        assert act.ended_at == t1

        # Input and output entities should be registered
        assert "entity:artifact:input-artifact-1" in graph.entities
        assert "entity:artifact:output-artifact-1" in graph.entities

        # Edges should include usage, generation, derivation, and association
        edge_relations = {(e.source_id, e.target_id, e.relation.value) for e in graph.edges}
        assert (activity_id, "entity:artifact:input-artifact-1", "used") in edge_relations
        assert (
            "entity:artifact:output-artifact-1",
            activity_id,
            "wasGeneratedBy",
        ) in edge_relations


class TestRecordLLMCall:
    def test_record_llm_call(self) -> None:
        dag = RunProvenanceDAG(run_id="run-003")
        dag.record_llm_call(
            node_alias="drafter",
            model_id="gpt-4o",
            temperature=0.7,
            seed=42,
            input_tokens=100,
            output_tokens=200,
        )

        graph = dag.finalize()

        # Model agent should be added
        model_agent_id = "agent:model:gpt-4o"
        assert model_agent_id in graph.agents
        assert graph.agents[model_agent_id].agent_type.value == "model"

        # An LLM call activity should exist
        llm_activities = [a for a in graph.activities.values() if a.activity_type.value == "query"]
        assert len(llm_activities) == 1
        assert "gpt-4o" in llm_activities[0].label

    def test_llm_record_retention_is_bounded(self) -> None:
        dag = RunProvenanceDAG(run_id="run-003b", max_llm_records=2)
        for idx in range(3):
            dag.record_llm_call(
                node_alias=f"drafter_{idx}",
                model_id="gpt-4o",
                temperature=0.1,
                input_tokens=10,
                output_tokens=20,
            )

        assert len(dag.llm_records) == 2
        assert dag.graph.metadata["llm_records_retention_limit"] == 2
        assert dag.graph.metadata["llm_records_dropped"] == 1


class TestToProvJson:
    def test_to_prov_json(self) -> None:
        dag = RunProvenanceDAG(run_id="run-004")
        t0 = datetime(2026, 1, 1, 12, 0, 0)
        t1 = datetime(2026, 1, 1, 12, 1, 0)

        dag.record_node_execution(
            alias="step1",
            node_id="n1",
            started_at=t0,
            ended_at=t1,
            input_refs=["in-1"],
            output_refs=["out-1"],
        )

        prov_json = dag.to_prov_json()

        # PROV-JSON must have required top-level keys
        assert "prefix" in prov_json
        assert "agent" in prov_json
        assert "activity" in prov_json
        assert "entity" in prov_json
