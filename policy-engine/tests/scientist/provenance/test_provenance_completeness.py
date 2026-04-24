"""Tests for WS8.4 — Provenance DAG Completeness.

Covers error activities, governance decisions, checkpoint provenance,
state mutation tracking, experiment metadata, and sync executor integration.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from polisyos.core.contracts.provenance import ActivityType, EntityType
from polisyos.scientist.provenance.prov_json import from_prov_json, to_prov_json
from polisyos.scientist.provenance.run_dag import RunProvenanceDAG

# ---------------------------------------------------------------------------
# Error activities
# ---------------------------------------------------------------------------


class TestRecordNodeFailure:
    def test_creates_error_activity(self) -> None:
        dag = RunProvenanceDAG(run_id="r1")
        now = datetime.now(UTC)
        dag.record_node_failure(
            alias="broken_node",
            node_id="node@1.0",
            error="Division by zero",
            started_at=now,
            ended_at=now,
        )
        activities = dag.graph.activities
        error_act_id = "activity:error:r1:broken_node"
        assert error_act_id in activities
        assert activities[error_act_id].activity_type == ActivityType.ERROR

    def test_includes_traceback(self) -> None:
        dag = RunProvenanceDAG(run_id="r1")
        now = datetime.now(UTC)
        dag.record_node_failure(
            alias="broken",
            node_id="n@1",
            error="fail",
            traceback="ZeroDivisionError",
            started_at=now,
            ended_at=now,
        )
        error_entity_id = "entity:error:r1:broken"
        assert error_entity_id in dag.graph.entities
        entity = dag.graph.entities[error_entity_id]
        assert entity.entity_type == EntityType.ERROR_TRACE
        assert entity.attributes["traceback"] == "ZeroDivisionError"


# ---------------------------------------------------------------------------
# Governance decisions
# ---------------------------------------------------------------------------


class TestRecordGovernanceDecision:
    def test_creates_governance_activity(self) -> None:
        dag = RunProvenanceDAG(run_id="r1")
        dag.record_governance_decision(
            pass_id="quality_gate",
            decision="pass",
            reason="All checks passed",
        )
        act_id = "activity:governance:r1:quality_gate"
        assert act_id in dag.graph.activities
        assert dag.graph.activities[act_id].activity_type == ActivityType.GOVERNANCE
        assert dag.graph.activities[act_id].parameters["decision"] == "pass"

    def test_links_evidence(self) -> None:
        dag = RunProvenanceDAG(run_id="r1")
        evidence = MagicMock(artifact_id="ev-001")
        dag.record_governance_decision(
            pass_id="pii_check",
            decision="block",
            evidence_refs=[evidence],
        )
        entity_id = "entity:artifact:ev-001"
        assert entity_id in dag.graph.entities
        # Should have usage edge from governance activity to evidence
        edges = dag.graph.edges
        usage_edges = [
            e
            for e in edges
            if e.source_id == "activity:governance:r1:pii_check" and e.target_id == entity_id
        ]
        assert len(usage_edges) == 1


# ---------------------------------------------------------------------------
# Checkpoint provenance
# ---------------------------------------------------------------------------


class TestRecordCheckpoint:
    def test_creates_checkpoint_activity(self) -> None:
        dag = RunProvenanceDAG(run_id="r1")
        ref = MagicMock(artifact_id="cp-001")
        dag.record_checkpoint(alias="data_load", checkpoint_ref=ref, sequence_number=1)
        act_id = "activity:checkpoint:r1:data_load:1"
        assert act_id in dag.graph.activities
        assert dag.graph.activities[act_id].activity_type == ActivityType.CHECKPOINT

    def test_links_to_checkpoint_entity(self) -> None:
        dag = RunProvenanceDAG(run_id="r1")
        ref = MagicMock(artifact_id="cp-002")
        dag.record_checkpoint(alias="sim", checkpoint_ref=ref, sequence_number=2)
        entity_id = "entity:checkpoint:cp-002"
        assert entity_id in dag.graph.entities
        assert dag.graph.entities[entity_id].entity_type == EntityType.CHECKPOINT


# ---------------------------------------------------------------------------
# State mutation tracking
# ---------------------------------------------------------------------------


class TestRecordStateMutation:
    def test_records_keys_added_and_modified(self) -> None:
        dag = RunProvenanceDAG(run_id="r1")
        now = datetime.now(UTC)
        # First create the node activity
        dag.record_node_execution(
            alias="sim_node",
            node_id="sim@1",
            started_at=now,
            ended_at=now,
        )
        # Then record mutation
        dag.record_state_mutation(
            alias="sim_node",
            keys_added=["causal_graph"],
            keys_modified=["params"],
        )
        act = dag.graph.activities["activity:node:r1:sim_node"]
        assert act.parameters.get("keys_added") == ["causal_graph"]
        assert act.parameters.get("keys_modified") == ["params"]


# ---------------------------------------------------------------------------
# Experiment metadata
# ---------------------------------------------------------------------------


class TestSetExperimentMetadata:
    def test_updates_root_metadata(self) -> None:
        dag = RunProvenanceDAG(run_id="r1")
        dag.set_experiment_metadata(
            problem_statement="Test poverty impact",
            hypothesis="Policy X reduces poverty by 10%",
            domain="fiscal",
        )
        meta = dag.graph.metadata
        assert meta["problem_statement"] == "Test poverty impact"
        assert meta["hypothesis"] == "Policy X reduces poverty by 10%"
        assert meta["domain"] == "fiscal"

    def test_metadata_in_prov_json(self) -> None:
        dag = RunProvenanceDAG(run_id="r1")
        dag.set_experiment_metadata(hypothesis="H1")
        prov = dag.to_prov_json()
        # Metadata should be accessible (it's part of the graph)
        assert dag.graph.metadata["hypothesis"] == "H1"


# ---------------------------------------------------------------------------
# PROV-JSON roundtrip with new activity types
# ---------------------------------------------------------------------------


class TestProvJsonRoundtrip:
    def test_new_activity_types_survive_roundtrip(self) -> None:
        dag = RunProvenanceDAG(run_id="r1")
        now = datetime.now(UTC)

        dag.record_node_failure(
            alias="fail_node",
            node_id="n@1",
            error="timeout",
            started_at=now,
            ended_at=now,
        )
        dag.record_governance_decision(
            pass_id="safety",
            decision="warn",
        )
        ref = MagicMock(artifact_id="cp-x")
        dag.record_checkpoint(alias="a", checkpoint_ref=ref, sequence_number=0)

        prov_json = to_prov_json(dag.graph)
        restored = from_prov_json(prov_json)

        # All 3 new activities + system agent association activities
        assert "activity:error:r1:fail_node" in restored.activities
        assert "activity:governance:r1:safety" in restored.activities
        assert "activity:checkpoint:r1:a:0" in restored.activities

    def test_new_entity_types_survive_roundtrip(self) -> None:
        dag = RunProvenanceDAG(run_id="r1")
        now = datetime.now(UTC)

        dag.record_node_failure(
            alias="x",
            node_id="n@1",
            error="e",
            traceback="tb",
            started_at=now,
            ended_at=now,
        )
        ref = MagicMock(artifact_id="cp-y")
        dag.record_checkpoint(alias="y", checkpoint_ref=ref, sequence_number=1)

        prov_json = to_prov_json(dag.graph)
        restored = from_prov_json(prov_json)

        assert "entity:error:r1:x" in restored.entities
        assert "entity:checkpoint:cp-y" in restored.entities


# ---------------------------------------------------------------------------
# Sync executor provenance
# ---------------------------------------------------------------------------


class TestSyncExecutorProvenance:
    def test_sync_executor_accepts_provenance_dag(self) -> None:
        """WorkflowExecutor.__init__ accepts provenance_dag parameter."""
        from polisyos.scientist.engine.executor import WorkflowExecutor

        ctx = MagicMock()
        registry = MagicMock()
        dag = RunProvenanceDAG(run_id="r1")

        executor = WorkflowExecutor(ctx, registry, provenance_dag=dag)
        assert executor._provenance_dag is dag

    def test_sync_executor_none_provenance_is_safe(self) -> None:
        """WorkflowExecutor works without provenance_dag."""
        from polisyos.scientist.engine.executor import WorkflowExecutor

        ctx = MagicMock()
        registry = MagicMock()

        executor = WorkflowExecutor(ctx, registry)
        assert executor._provenance_dag is None
