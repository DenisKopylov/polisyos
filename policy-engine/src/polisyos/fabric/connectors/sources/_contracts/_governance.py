"""Shared governance metadata for built-in source contract schema bumps."""

from __future__ import annotations

from polisyos.fabric.connectors.contracts import (
    MigrationStatus,
    SchemaApprovalMetadata,
    SchemaRiskLevel,
)

FIELD_ID_MAJOR_BUMP_APPROVAL = SchemaApprovalMetadata(
    owner="team-fabric",
    reviewer="team-architecture",
    risk_level=SchemaRiskLevel.MODERATE,
    migration_status=MigrationStatus.PLANNED,
    downstream_impact_summary=(
        "Built-in connector contracts now publish schema-qualified stable field IDs; "
        "payload field names and source mappings are unchanged."
    ),
    migration_note=(
        "Refresh connector contract snapshots and downstream generated schema consumers "
        "so they use field_id as the stable key where available."
    ),
    adr_refs=("ADR-0021",),
    approved_major_bump=True,
)

__all__ = ["FIELD_ID_MAJOR_BUMP_APPROVAL"]
