from __future__ import annotations

from datetime import datetime

from polisyos.core.contracts.provenance import (
    ActivityType as CoreActivityType,
)
from polisyos.core.contracts.provenance import (
    EntityType as CoreEntityType,
)
from polisyos.core.contracts.provenance import (
    ProvenanceActivity as CoreProvenanceActivity,
)
from polisyos.core.contracts.provenance import (
    ProvenanceCoreGraph as CoreProvenanceCoreGraph,
)
from polisyos.core.contracts.provenance import (
    ProvenanceEntity as CoreProvenanceEntity,
)
from polisyos.fabric.provenance.core import (
    ActivityType as FabricActivityType,
)
from polisyos.fabric.provenance.core import (
    EntityType as FabricEntityType,
)
from polisyos.fabric.provenance.core import (
    ProvenanceActivity as FabricProvenanceActivity,
)
from polisyos.fabric.provenance.core import (
    ProvenanceCoreGraph as FabricProvenanceCoreGraph,
)
from polisyos.fabric.provenance.core import (
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
