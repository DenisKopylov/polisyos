"""
Comprehensive tests for the Provenance subsystem.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from polisyos.fabric.provenance.core import (
    ActivityType,
    AgentType,
    EntityType,
    ProvenanceActivity,
    ProvenanceAgent,
    ProvenanceCoreGraph,
    ProvenanceCoreRef,
    ProvenanceEntity,
    RelationType,
)
from polisyos.fabric.provenance.export_provo import (
    export_to_prov_json,
    export_to_provo_jsonld,
    export_to_provo_nquads,
)


class TestProvenanceEntity:
    """Tests for ProvenanceEntity dataclass."""

    def test_entity_creation(self) -> None:
        entity = ProvenanceEntity(
            entity_id="test-entity-001",
            entity_type=EntityType.DATASET,
            label="Test Dataset",
            created_at=datetime(2025, 1, 15, 10, 0, 0),
            attributes={"rows": "1000", "format": "parquet"},
        )

        assert entity.entity_id == "test-entity-001"
        assert entity.entity_type == EntityType.DATASET
        assert entity.attributes["rows"] == "1000"

    def test_entity_is_frozen(self) -> None:
        entity = ProvenanceEntity(
            entity_id="frozen-test",
            entity_type=EntityType.METRIC,
            label="Frozen",
            created_at=datetime.now(timezone.utc),
        )

        with pytest.raises(Exception):
            entity.label = "Modified"  # type: ignore[assignment]

    def test_entity_hashable(self) -> None:
        entity1 = ProvenanceEntity(
            entity_id="hash-test",
            entity_type=EntityType.SNAPSHOT,
            label="Hashable",
            created_at=datetime.now(timezone.utc),
        )
        entity2 = ProvenanceEntity(
            entity_id="hash-test",
            entity_type=EntityType.SNAPSHOT,
            label="Different Label",
            created_at=datetime.now(timezone.utc),
        )

        assert hash(entity1) == hash(entity2)

        entity_set = {entity1, entity2}
        assert len(entity_set) == 1


class TestProvenanceCoreGraph:
    """Tests for ProvenanceCoreGraph container."""

    @pytest.fixture
    def sample_graph(self) -> ProvenanceCoreGraph:
        graph = ProvenanceCoreGraph(
            graph_id="test-graph-001",
            created_at=datetime(2025, 1, 15, 10, 0, 0),
        )

        raw_entity = ProvenanceEntity(
            entity_id="raw-data",
            entity_type=EntityType.DATASET,
            label="Raw CSV",
            created_at=datetime(2025, 1, 15, 9, 0, 0),
        )
        curated_entity = ProvenanceEntity(
            entity_id="curated-data",
            entity_type=EntityType.DATASET,
            label="Curated Parquet",
            created_at=datetime(2025, 1, 15, 10, 0, 0),
        )
        graph.add_entity(raw_entity)
        graph.add_entity(curated_entity)

        ingest_activity = ProvenanceActivity(
            activity_id="ingest-001",
            activity_type=ActivityType.INGEST,
            label="Data Ingestion",
            started_at=datetime(2025, 1, 15, 9, 30, 0),
            ended_at=datetime(2025, 1, 15, 10, 0, 0),
        )
        graph.add_activity(ingest_activity)

        system_agent = ProvenanceAgent(
            agent_id="system",
            agent_type=AgentType.SYSTEM,
            label="Policy OS",
        )
        graph.add_agent(system_agent)

        graph.add_usage("ingest-001", "raw-data")
        graph.add_generation("curated-data", "ingest-001")
        graph.add_derivation("curated-data", "raw-data")
        graph.add_association("ingest-001", "system")

        return graph

    def test_node_lookup_o1(self, sample_graph: ProvenanceCoreGraph) -> None:
        entity = sample_graph.get_entity("raw-data")
        assert entity is not None
        assert entity.label == "Raw CSV"

        activity = sample_graph.get_activity("ingest-001")
        assert activity is not None
        assert activity.activity_type == ActivityType.INGEST

        agent = sample_graph.get_agent("system")
        assert agent is not None
        assert agent.agent_type == AgentType.SYSTEM

        assert sample_graph.get_entity("nonexistent") is None

    def test_edge_semantics(self, sample_graph: ProvenanceCoreGraph) -> None:
        edges = sample_graph.edges

        derivation = next(e for e in edges if e.relation == RelationType.WAS_DERIVED_FROM)
        assert derivation.source_id == "curated-data"
        assert derivation.target_id == "raw-data"

        generation = next(e for e in edges if e.relation == RelationType.WAS_GENERATED_BY)
        assert generation.source_id == "curated-data"
        assert generation.target_id == "ingest-001"

        usage = next(e for e in edges if e.relation == RelationType.USED)
        assert usage.source_id == "ingest-001"
        assert usage.target_id == "raw-data"

    def test_stable_id_determinism(self, sample_graph: ProvenanceCoreGraph) -> None:
        id1 = sample_graph.compute_stable_id()
        id2 = sample_graph.compute_stable_id()

        assert id1 == id2
        assert len(id1) == 16

    def test_stable_id_changes_with_content(self) -> None:
        graph1 = ProvenanceCoreGraph(graph_id="test")
        graph1.add_entity(
            ProvenanceEntity(
                entity_id="e1",
                entity_type=EntityType.DATASET,
                label="Entity 1",
                created_at=datetime(2025, 1, 1),
            )
        )

        graph2 = ProvenanceCoreGraph(graph_id="test")
        graph2.add_entity(
            ProvenanceEntity(
                entity_id="e1",
                entity_type=EntityType.DATASET,
                label="Entity 1 Modified",
                created_at=datetime(2025, 1, 1),
            )
        )

        assert graph1.compute_stable_id() != graph2.compute_stable_id()

    def test_serialization_roundtrip(self, sample_graph: ProvenanceCoreGraph) -> None:
        data = sample_graph.to_dict()

        assert "graph_id" in data
        assert "entities" in data
        assert "activities" in data
        assert "agents" in data
        assert "edges" in data

        restored = ProvenanceCoreGraph.from_dict(data)

        assert restored.graph_id == sample_graph.graph_id
        assert len(restored.entities) == len(sample_graph.entities)
        assert len(restored.activities) == len(sample_graph.activities)
        assert len(restored.edges) == len(sample_graph.edges)

        assert restored.compute_stable_id() == sample_graph.compute_stable_id()

    def test_get_ancestors(self, sample_graph: ProvenanceCoreGraph) -> None:
        ancestors = sample_graph.get_ancestors("curated-data")

        assert "raw-data" in ancestors
        assert len(ancestors) == 1

    def test_get_generating_activity(self, sample_graph: ProvenanceCoreGraph) -> None:
        activity_id = sample_graph.get_generating_activity("curated-data")

        assert activity_id == "ingest-001"


class TestProvoExport:
    """Tests for PROV-O JSON-LD export."""

    @pytest.fixture
    def simple_graph(self) -> ProvenanceCoreGraph:
        graph = ProvenanceCoreGraph(graph_id="export-test")

        graph.add_entity(
            ProvenanceEntity(
                entity_id="e1",
                entity_type=EntityType.DATASET,
                label="Source Data",
                created_at=datetime(2025, 1, 1, 12, 0, 0),
            )
        )

        graph.add_activity(
            ProvenanceActivity(
                activity_id="a1",
                activity_type=ActivityType.QUERY,
                label="Transform",
                started_at=datetime(2025, 1, 1, 12, 30, 0),
                ended_at=datetime(2025, 1, 1, 12, 31, 0),
            )
        )

        graph.add_usage("a1", "e1")

        return graph

    def test_jsonld_structure(self, simple_graph: ProvenanceCoreGraph) -> None:
        jsonld = export_to_provo_jsonld(simple_graph)

        assert "@context" in jsonld
        assert "@graph" in jsonld
        assert "prov" in jsonld["@context"]

        nodes = jsonld["@graph"]
        assert len(nodes) == 2

        types = {n["@type"] for n in nodes}
        assert "Entity" in types
        assert "Activity" in types

    def test_jsonld_relations(self, simple_graph: ProvenanceCoreGraph) -> None:
        jsonld = export_to_provo_jsonld(simple_graph)

        activity_node = next(n for n in jsonld["@graph"] if n["@type"] == "Activity")

        assert "used" in activity_node
        assert activity_node["used"]["@id"].endswith("e1")

    def test_nquads_export(self, simple_graph: ProvenanceCoreGraph) -> None:
        nquads = export_to_provo_nquads(simple_graph)

        lines = nquads.strip().split("\n")
        assert len(lines) > 0
        assert any("rdf-syntax-ns#type" in line for line in lines)
        assert any("prov#used" in line for line in lines)

    def test_nquads_escapes_labels_for_strict_rdf_parser(self) -> None:
        rdflib = pytest.importorskip("rdflib")

        graph = ProvenanceCoreGraph(graph_id="escape-test")
        graph.add_entity(
            ProvenanceEntity(
                entity_id="e1",
                entity_type=EntityType.DATASET,
                label='Quoted "label"\nwith carriage\rreturn',
                created_at=datetime(2025, 1, 1, 12, 0, 0),
            )
        )

        nquads = export_to_provo_nquads(graph)
        parsed = rdflib.Dataset()
        parsed.parse(data=nquads, format="nquads")

        assert len(parsed) > 0

    def test_prov_json_export(self, simple_graph: ProvenanceCoreGraph) -> None:
        prov_json = export_to_prov_json(simple_graph, run_id="R_test")

        assert "prefix" in prov_json
        assert "entity" in prov_json
        assert "activity" in prov_json
        assert "used" in prov_json
        assert "bundle" in prov_json


class TestProvenancePersistence:
    """Tests for CAS persistence integration."""

    def test_persist_and_load(self, tmp_path: Path) -> None:
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.fabric.evidence import (
            load_provenance_graph,
            persist_provenance_graph,
        )

        cas_store = FileSystemCAS(tmp_path / ".polisyos")

        graph = ProvenanceCoreGraph(graph_id="persist-test")
        graph.add_entity(
            ProvenanceEntity(
                entity_id="test-entity",
                entity_type=EntityType.METRIC,
                label="Test Metric",
                created_at=datetime.now(timezone.utc),
            )
        )

        ref = persist_provenance_graph(cas_store, graph)

        assert ref.graph_id == "persist-test"
        assert ref.stable_id == graph.compute_stable_id()
        assert ref.artifact_id is not None

        loaded = load_provenance_graph(cas_store, ref)

        assert loaded.graph_id == graph.graph_id
        assert loaded.compute_stable_id() == graph.compute_stable_id()

    def test_integrity_verification_fails_on_tamper(self, tmp_path: Path) -> None:
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.fabric.evidence import (
            load_provenance_graph,
            persist_provenance_graph,
        )

        cas_store = FileSystemCAS(tmp_path / ".polisyos")

        graph = ProvenanceCoreGraph(graph_id="tamper-test")
        ref = persist_provenance_graph(cas_store, graph)

        tampered_ref = ProvenanceCoreRef(
            graph_id=ref.graph_id,
            stable_id="tampered000000",
            artifact_id=ref.artifact_id,
        )

        with pytest.raises(ValueError, match="integrity check failed"):
            load_provenance_graph(cas_store, tampered_ref)

    def test_persist_provenance_graph_rejects_missing_stable_id(self, tmp_path: Path, monkeypatch) -> None:
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.fabric.evidence import EvidencePayloadError, persist_provenance_graph

        cas_store = FileSystemCAS(tmp_path / ".polisyos")
        graph = ProvenanceCoreGraph(graph_id="missing-stable-id")
        monkeypatch.setattr(graph, "to_dict", lambda: {"graph_id": "missing-stable-id"})

        with pytest.raises(EvidencePayloadError, match="stable_id"):
            persist_provenance_graph(cas_store, graph)

    def test_persist_provenance_graph_records_governance_manifest(self, tmp_path: Path) -> None:
        from polisyos.core.artifacts.ids import ArtifactID
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.fabric.evidence import persist_provenance_graph
        from polisyos.fabric.security import DataClassification

        cas_store = FileSystemCAS(tmp_path / ".polisyos")
        graph = ProvenanceCoreGraph(graph_id="governed-provenance")

        ref = persist_provenance_graph(
            cas_store,
            graph,
            classification=DataClassification.INTERNAL,
            encrypted_at_rest=True,
            encryption_key_reference="kms://fabric/evidence",
        )

        manifest = cas_store.get_manifest(ArtifactID.model_validate(ref.artifact_id))

        assert manifest.governance is not None
        assert manifest.governance.classification == "internal"
        assert manifest.governance.retention is not None
        assert manifest.governance.retention.scope == "evidence_bundle"
        assert manifest.governance.encryption is not None
        assert manifest.governance.encryption.mode == "envelope"
        assert manifest.governance.encryption.verified is True


class TestEvidenceBundleIntegration:
    """Tests for EvidenceBundle + Provenance integration."""

    def test_evidence_bundle_with_provenance(self, tmp_path: Path) -> None:
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.fabric.evidence import (
            build_evidence_bundle,
            persist_evidence_bundle,
            persist_provenance_graph,
        )
        from polisyos.core.contracts.fabric import EvidenceStep

        cas_store = FileSystemCAS(tmp_path / ".polisyos")

        graph = ProvenanceCoreGraph(graph_id="evidence-test")
        graph.add_entity(
            ProvenanceEntity(
                entity_id="source",
                entity_type=EntityType.DATASET,
                label="Source",
                created_at=datetime.now(timezone.utc),
            )
        )
        prov_ref = persist_provenance_graph(cas_store, graph)

        bundle = build_evidence_bundle(
            sources=[],
            transforms=[EvidenceStep(op="test", details={})],
            provenance_ref=prov_ref,
        )

        assert bundle.provenance_ref is not None
        assert bundle.provenance_ref.graph_id == "evidence-test"

        bundle_ref = persist_evidence_bundle(cas_store, bundle)
        assert bundle_ref.artifact_id is not None

    def test_persist_evidence_bundle_fails_closed_without_required_encryption(
        self,
        tmp_path: Path,
    ) -> None:
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.fabric.evidence import build_evidence_bundle, persist_evidence_bundle
        from polisyos.fabric.security import ArtifactGovernanceError, DataClassification

        cas_store = FileSystemCAS(tmp_path / ".polisyos")
        bundle = build_evidence_bundle()

        with pytest.raises(ArtifactGovernanceError, match="field-level encryption"):
            persist_evidence_bundle(
                cas_store,
                bundle,
                classification=DataClassification.REGULATED_PII,
            )
