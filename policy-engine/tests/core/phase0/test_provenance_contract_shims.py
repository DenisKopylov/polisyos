from __future__ import annotations

from datetime import datetime

from polisyos.core.contracts.provenance import (
    ActivityType as CoreActivityType,
    EntityType as CoreEntityType,
    ProvenanceActivity as CoreProvenanceActivity,
    ProvenanceCoreGraph as CoreProvenanceCoreGraph,
    ProvenanceEntity as CoreProvenanceEntity,
)
from polisyos.fabric.provenance.core import (
    ActivityType as FabricActivityType,
    EntityType as FabricEntityType,
    ProvenanceActivity as FabricProvenanceActivity,
    ProvenanceCoreGraph as FabricProvenanceCoreGraph,
    ProvenanceEntity as FabricProvenanceEntity,
)


def test_fabric_provenance_core_is_thin_reexport_of_core_contracts() -> None:
    assert FabricEntityType is CoreEntityType
    assert FabricActivityType is CoreActivityType
    assert FabricProvenanceEntity is CoreProvenanceEntity
    assert FabricProvenanceActivity is CoreProvenanceActivity
    assert FabricProvenanceCoreGraph is CoreProvenanceCoreGraph


def test_provenance_stable_id_is_preserved_via_fabric_compat_path() -> None:
    graph = FabricProvenanceCoreGraph(graph_id="shim-test")
    graph.add_entity(
        FabricProvenanceEntity(
            entity_id="source",
            entity_type=FabricEntityType.DATASET,
            label="Source",
            created_at=datetime(2026, 2, 9, 20, 0, 0),
        )
    )
    graph.add_activity(
        FabricProvenanceActivity(
            activity_id="ingest",
            activity_type=FabricActivityType.INGEST,
            label="Ingest",
            started_at=datetime(2026, 2, 9, 20, 0, 1),
            ended_at=datetime(2026, 2, 9, 20, 0, 2),
        )
    )
    graph.add_generation("source", "ingest")

    stable_id = graph.compute_stable_id()
    rebuilt = CoreProvenanceCoreGraph.from_dict(graph.to_dict())

    assert rebuilt.compute_stable_id() == stable_id
    assert rebuilt.to_dict()["stable_id"] == stable_id

