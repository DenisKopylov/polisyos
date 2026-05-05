from __future__ import annotations

from polisyos.fabric.security import (
    DataClassification,
    EncryptionMode,
    RetentionPlanner,
    RetentionScope,
    SnapshotRetentionClass,
    build_snapshot_deletion_impact,
    classify_snapshot_retention,
)
from polisyos.fabric.world.materialize import get_world_kuzu_temporal_capability
from polisyos.runtime.http.services.temporal import TemporalService


def test_temporal_capabilities_expose_branch_snapshot_tables_and_index_evidence() -> None:
    capabilities = TemporalService().build_capabilities()

    assert capabilities.branch_support is True
    assert capabilities.snapshot_support is True
    assert capabilities.scenario_branch_support == "explicit_only"
    assert capabilities.graph_temporal_scope == "partial"
    assert "world.world_facts" in capabilities.supported_tables
    assert "artifact_content" in capabilities.unsupported_surfaces
    assert capabilities.nearest_event_points
    assert {
        (evidence.table, evidence.index_name) for evidence in capabilities.slow_query_evidence
    } >= {
        ("world.world_facts", "idx_world_facts_tx_valid"),
        ("world.world_edges", "idx_world_edges_valid_tx"),
    }


def test_kuzu_temporal_capability_is_explicitly_partial_until_r3() -> None:
    capability = get_world_kuzu_temporal_capability()

    assert capability.graph_temporal_scope == "partial"
    assert capability.research_track == "R3"
    assert "world.world_edges" in capability.supported_fact_surfaces


def test_world_snapshot_and_branch_retention_classes_are_governed() -> None:
    planner = RetentionPlanner()
    snapshot_decision = planner.resolve(
        scope=RetentionScope.WORLD_SNAPSHOT,
        classification=DataClassification.CONFIDENTIAL,
    )
    branch_decision = planner.resolve(
        scope=RetentionScope.WORLD_BRANCH,
        classification=DataClassification.PUBLIC,
    )
    impact = build_snapshot_deletion_impact(
        snapshot_id="world_snapshot_old",
        branch_name="main",
        retention_class=SnapshotRetentionClass.AUDIT_TAGGED,
        reason="operator_requested_redaction",
        alternative_retention_ref="cas://sha256/redacted_replay_manifest",
    )

    assert snapshot_decision.encryption_mode == EncryptionMode.ENVELOPE
    assert branch_decision.retention_days >= 365
    assert classify_snapshot_retention(tags=("audit",)) == SnapshotRetentionClass.AUDIT_TAGGED
    assert impact.replay_impacted is True
    assert impact.time_travel_impacted is True
