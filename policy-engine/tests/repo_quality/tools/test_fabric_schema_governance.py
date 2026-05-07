from __future__ import annotations

from polisyos.fabric.connectors.contracts import (
    ConnectorSchemaContract,
    DataSchema,
    FieldSpec,
    MigrationStatus,
    SchemaApprovalMetadata,
    SchemaRiskLevel,
    SchemaType,
    SchemaVersion,
)
from polisyos.fabric.connectors.sources._contracts import build_builtin_contract_registry
from tools.quality.validation.fabric_schema_governance import (
    build_evidence_payload,
    build_snapshot_payload,
    validate_against_baseline,
)


def _contract(
    *,
    version: SchemaVersion,
    include_extra: bool = False,
    approval: SchemaApprovalMetadata | None = None,
) -> ConnectorSchemaContract:
    fields = [FieldSpec(name="id", data_type=SchemaType.STRING, nullable=False)]
    if include_extra:
        fields.append(FieldSpec(name="value", data_type=SchemaType.FLOAT64, nullable=True))
    return ConnectorSchemaContract(
        contract_id="test.fabric.contract",
        connector_id="test.connector",
        dataset_id="dataset",
        schema=DataSchema(
            schema_id="test.fabric.schema",
            version=version,
            fields=tuple(fields),
            primary_key=("id",),
            required_completeness=0.0,
        ),
        approval=approval or SchemaApprovalMetadata(),
    )


def test_breaking_change_requires_approved_major_bump_metadata() -> None:
    baseline = build_snapshot_payload(
        [_contract(version=SchemaVersion(1, 0, 0), include_extra=True)]
    )
    current = build_snapshot_payload(
        [_contract(version=SchemaVersion(2, 0, 0), include_extra=False)]
    )

    errors, plans = validate_against_baseline(baseline, current)

    assert errors
    assert "approved_major_bump" in errors[0]
    assert "impacted=connector:test.connector" in errors[0]
    assert plans == {}


def test_compatible_addition_produces_migration_plan() -> None:
    baseline = build_snapshot_payload([_contract(version=SchemaVersion(1, 0, 0))])
    current = build_snapshot_payload(
        [_contract(version=SchemaVersion(1, 1, 0), include_extra=True)]
    )

    errors, plans = validate_against_baseline(baseline, current)

    assert errors == []
    plan = plans["test.fabric.contract"]
    assert plan.safe_to_apply is True
    assert any("ADD COLUMN" in sql for sql in plan.sql_statements)


def test_runtime_registry_and_ci_snapshot_share_contract_versions() -> None:
    registry = build_builtin_contract_registry()
    snapshot = build_snapshot_payload()

    first_contract_id = next(iter(snapshot["contracts"]))
    runtime_contract = registry.get(first_contract_id)

    assert snapshot["contracts"][first_contract_id]["schema_version"] == str(
        runtime_contract.schema_version
    )


def test_breaking_change_with_governance_metadata_passes_major_gate() -> None:
    baseline = build_snapshot_payload(
        [_contract(version=SchemaVersion(1, 0, 0), include_extra=True)]
    )
    approval = SchemaApprovalMetadata(
        owner="fabric-owner",
        reviewer="fabric-reviewer",
        risk_level=SchemaRiskLevel.HIGH,
        migration_status=MigrationStatus.PLANNED,
        downstream_impact_summary="world.claims, retrieval projections",
        migration_note="Backfill downstream materialized tables.",
        adr_refs=("ADR-0053",),
        approved_major_bump=True,
    )
    current = build_snapshot_payload(
        [_contract(version=SchemaVersion(2, 0, 0), include_extra=False, approval=approval)]
    )

    errors, _plans = validate_against_baseline(baseline, current)

    assert errors == []


def test_evidence_payload_includes_impacted_surfaces_and_migrations() -> None:
    baseline = build_snapshot_payload([_contract(version=SchemaVersion(1, 0, 0))])
    current = build_snapshot_payload(
        [_contract(version=SchemaVersion(1, 1, 0), include_extra=True)]
    )

    evidence = build_evidence_payload(baseline, current)

    contract_evidence = evidence["contract_evaluations"]["test.fabric.contract"]
    assert evidence["snapshot_out_of_date"] is True
    assert evidence["error_count"] == 0
    assert contract_evidence["impacted_surfaces"] == [
        "connector:test.connector",
        "dataset:dataset",
        "schema:test.fabric.schema",
    ]
    assert contract_evidence["recommended_version_bump"] == "minor"
    assert contract_evidence["migration_plan"]["sql_statements"]
    assert any("ADD COLUMN" in sql for sql in contract_evidence["migration_plan"]["sql_statements"])
