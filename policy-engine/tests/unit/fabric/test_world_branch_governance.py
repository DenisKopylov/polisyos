from __future__ import annotations

from pathlib import Path

import pytest
from polisyos.fabric.world.store import (
    WorldSegmentError,
    WorldSnapshotRecord,
    create_world_branch,
    delete_world_branch,
    emit_attr_fact,
    export_world_branch_governance,
    parse_world_mutation_notes,
    register_world_snapshot_record,
    resolve_world_snapshot,
    stable_world_provenance_v1,
    update_world_branch_head,
)


def test_world_correction_mutation_requires_provenance_and_is_parseable() -> None:
    fact = emit_attr_fact(
        subject_id="node.phase7",
        predicate_id="world.label",
        object_value="Corrected label",
        provenance=stable_world_provenance_v1(),
        valid_time="2024-01-01T00:00:00Z",
        mutation_kind="correction",
        corrects_fact_ref="world.fact:old",
        reason="late_arriving_source_revision",
        source_evidence_refs=("cas://sha256/source_revision",),
        lineage_ref="lin_correction_123",
        actor="fabric.ingestion.worldbank",
    )

    mutations = parse_world_mutation_notes(fact.provenance)

    assert len(mutations) == 1
    mutation = mutations[0]
    assert mutation.mutation_kind == "correction"
    assert mutation.corrects_fact_ref == "world.fact:old"
    assert mutation.source_evidence_refs == ("cas://sha256/source_revision",)
    assert mutation.lineage_ref == "lin_correction_123"
    assert mutation.actor == "fabric.ingestion.worldbank"


def test_world_correction_mutation_fails_without_reason_or_evidence() -> None:
    with pytest.raises(WorldSegmentError, match="correction world mutations require"):
        emit_attr_fact(
            subject_id="node.phase7",
            predicate_id="world.label",
            object_value="Corrected label",
            provenance=stable_world_provenance_v1(),
            mutation_kind="correction",
            corrects_fact_ref="world.fact:old",
            actor="fabric.ingestion.worldbank",
        )


def test_scenario_branch_governance_is_retained_and_deletion_is_reviewable(
    tmp_path: Path,
) -> None:
    snapshot_root = tmp_path / "branch_governance"
    base = register_world_snapshot_record(
        snapshot_root,
        WorldSnapshotRecord(
            snapshot_id="world_snapshot_base",
            snapshot_path="s3://warehouse/world/base",
            created_at="2026-04-01T00:00:00Z",
            branch_name="main",
            base_snapshot_id="world_snapshot_base",
            storage_adapter="iceberg_table",
        ),
    )

    branch = create_world_branch(
        snapshot_root,
        branch_name="scenario.tax_shift",
        base_snapshot_id=base.snapshot_id,
        branch_kind="scenario",
        scenario_ref="scenario.tax_shift.v1",
        assumption_lineage_refs=("lin.assumption.tax_shift",),
        model_lineage_refs=("lin.model.counterfactual",),
        valid_from="2026-04-01T00:00:00Z",
        actor="analyst.phase7",
        reason="counterfactual review",
        retained_audit_ref="cas://sha256/audit_branch",
    )

    assert branch.observed_state == "simulated"
    assert (
        branch.provenance["scenario_contract"]["source_marker"]
        == "scenario_state_not_observed_world"
    )
    assert branch.provenance["scenario_contract"]["scenario_ref"] == "scenario.tax_shift.v1"

    head = register_world_snapshot_record(
        snapshot_root,
        WorldSnapshotRecord(
            snapshot_id="world_snapshot_scenario_head",
            snapshot_path="s3://warehouse/world/scenario-head",
            created_at="2026-04-02T00:00:00Z",
            branch_name="scenario.tax_shift",
            base_snapshot_id=base.snapshot_id,
            storage_adapter="iceberg_table",
            provenance={"actor": "analyst.phase7", "reason": "scenario materialized"},
        ),
    )
    updated = update_world_branch_head(
        snapshot_root,
        branch_name="scenario.tax_shift",
        head_snapshot_id=head.snapshot_id,
        actor="reviewer.phase7",
        reason="reviewed scenario head",
        retained_audit_ref="cas://sha256/audit_head",
    )
    deleted = delete_world_branch(
        snapshot_root,
        branch_name="scenario.tax_shift",
        actor="reviewer.phase7",
        reason="scenario superseded",
        retained_audit_ref="cas://sha256/audit_delete",
    )
    payload = export_world_branch_governance(snapshot_root, "scenario.tax_shift")
    event_kinds = [event["event_kind"] for event in payload["governance_events"]]

    assert updated.head_snapshot_id == head.snapshot_id
    assert deleted.deleted_at is not None
    assert "branch_created" in event_kinds
    assert "branch_head_updated" in event_kinds
    assert "branch_deleted" in event_kinds
    assert payload["observed_state"] == "simulated"

    with pytest.raises(FileNotFoundError, match="world branch was deleted"):
        resolve_world_snapshot(snapshot_root, branch_name="scenario.tax_shift")
