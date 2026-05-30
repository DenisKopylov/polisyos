from __future__ import annotations

import pytest

from polisyos.runtime.quality.rule_evolution import (
    RULE_EVOLUTION_REGISTRY_SCHEMA_VERSION,
)
from polisyos.runtime.quality.schema_compat import (
    COMPATIBILITY_DECISIONS,
    ReaderSchemaRange,
    SchemaCompatibilityRegistryError,
    evaluate_schema_compatibility,
    load_schema_compatibility_registry,
    reader_schema_ranges,
    stable_payload_sha256,
)


def test_schema_compatibility_decision_taxonomy_is_complete() -> None:
    assert COMPATIBILITY_DECISIONS == (
        "compatible",
        "compatible_with_migration",
        "legacy_quarantined",
        "unknown_schema_blocked",
        "incompatible_blocked",
        "stale_schema_blocked",
    )


def test_required_runtime_quality_readers_declare_schema_ranges() -> None:
    ranges = reader_schema_ranges()

    assert set(ranges) >= {
        "scorecard",
        "readiness",
        "bundle_assembler",
        "dashboard_projection",
        "approval_packet_builder",
    }
    for reader_name in (
        "scorecard",
        "readiness",
        "bundle_assembler",
        "dashboard_projection",
        "approval_packet_builder",
    ):
        assert ranges[reader_name], reader_name
        assert all(declaration.reader == reader_name for declaration in ranges[reader_name])


def test_schema_compatibility_registry_rejects_missing_required_reader(tmp_path) -> None:
    registry = tmp_path / "schema_compatibility.toml"
    registry.write_text(
        "\n".join(
            [
                'decisions = ["compatible", "compatible_with_migration", "legacy_quarantined", "unknown_schema_blocked", "incompatible_blocked", "stale_schema_blocked"]',
                "",
                "[[readers]]",
                'name = "scorecard"',
                'consumer = "runtime.scorecard"',
                'production_closeout_policy = "block_non_compatible"',
                'diagnostic_policy = "legacy_readable_only"',
                'accepted_schema_families = ["policyos.quality_scorecard"]',
                'min_version = "1"',
                'max_version = "1"',
                'current_version = "1"',
                'legacy_versions = ["0"]',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(SchemaCompatibilityRegistryError) as exc_info:
        load_schema_compatibility_registry(registry)
    assert exc_info.value.code == "schema_compatibility_required_reader_missing"


def test_current_schema_is_compatible_for_declared_reader() -> None:
    result = evaluate_schema_compatibility(
        {"schema_version": "policyos.quality_scorecard.v1"},
        reader="approval_packet_builder",
    )

    assert result.decision == "compatible"
    assert result.diagnostic_readable is True
    assert result.production_closeout_allowed is True
    assert result.schema_family == "policyos.quality_scorecard"


def test_legacy_bundle_is_diagnostic_readable_but_quarantined_from_closeout() -> None:
    result = evaluate_schema_compatibility(
        {
            "schema_version": "policyos.canary_evidence.v0",
            "quality_status": "pass",
        },
        reader="readiness",
    )

    assert result.decision == "legacy_quarantined"
    assert result.diagnostic_readable is True
    assert result.production_closeout_allowed is False
    assert result.reason == "legacy_schema_version"


def test_unknown_schema_blocks_reader_even_when_payload_claims_pass() -> None:
    result = evaluate_schema_compatibility(
        {
            "schema_version": "policyos.unregistered_quality_report.v99",
            "status": "pass",
        },
        reader="scorecard",
    )

    assert result.decision == "unknown_schema_blocked"
    assert result.diagnostic_readable is False
    assert result.production_closeout_allowed is False


def test_known_schema_for_wrong_reader_is_incompatible() -> None:
    result = evaluate_schema_compatibility(
        {"schema_version": "policyos.canary_evidence.v1"},
        reader="approval_packet_builder",
    )

    assert result.decision == "incompatible_blocked"
    assert result.reason == "reader_does_not_accept_schema_family"


def test_declared_scorecard_aliases_are_compatible() -> None:
    result = evaluate_schema_compatibility(
        {"schema_version": "policyos.runtime_resilience_matrix.v1"},
        reader="scorecard",
        expected_schema_family=(
            "policyos.runtime.resilience_matrix",
            "policyos.runtime_resilience_matrix",
        ),
    )

    assert result.decision == "compatible"
    assert result.production_closeout_allowed is True


def test_rule_evolution_registry_schema_is_scorecard_readable() -> None:
    result = evaluate_schema_compatibility(
        {
            "schema_version": RULE_EVOLUTION_REGISTRY_SCHEMA_VERSION,
            "status": "pass",
        },
        reader="scorecard",
    )

    assert result.decision == "compatible"
    assert result.schema_family == "policyos.runtime.policy_design_case.rule_evolution_registry"
    assert result.production_closeout_allowed is True


def test_migration_and_stale_decisions_are_explicit() -> None:
    migrating_reader = {
        "migration_reader": (
            ReaderSchemaRange(
                reader="migration_reader",
                schema_family="policyos.example_report",
                min_version="1",
                max_version="2",
                current_version="2",
                migration_versions=("1",),
            ),
        ),
        "stale_reader": (
            ReaderSchemaRange(
                reader="stale_reader",
                schema_family="policyos.example_report",
                min_version="2",
                max_version="2",
                current_version="2",
            ),
        ),
    }

    migration = evaluate_schema_compatibility(
        {"schema_version": "policyos.example_report.v1"},
        reader="migration_reader",
        declarations=migrating_reader,
    )
    stale = evaluate_schema_compatibility(
        {"schema_version": "policyos.example_report.v1"},
        reader="stale_reader",
        declarations=migrating_reader,
    )

    assert migration.decision == "legacy_quarantined"
    assert migration.reason == "migration_required_without_verified_payload_identity"
    assert migration.diagnostic_readable is True
    assert migration.production_closeout_allowed is False
    assert migration.migration_required is True
    assert stale.decision == "stale_schema_blocked"
    assert stale.production_closeout_allowed is False


def test_verified_renamed_field_migration_allows_serious_closeout() -> None:
    declarations = {
        "bundle_assembler": (
            ReaderSchemaRange(
                reader="bundle_assembler",
                schema_family="policyos.example_bundle",
                min_version="1",
                max_version="2",
                current_version="2",
                migration_versions=("1",),
            ),
        )
    }
    legacy_payload = {
        "schema_version": "policyos.example_bundle.v1",
        "quality_status": "pass",
        "artifact_ref": "cas://sha256/" + "a" * 64,
    }
    migrated_payload = {
        "schema_version": "policyos.example_bundle.v2",
        "status": "pass",
        "artifact_ref": "cas://sha256/" + "a" * 64,
    }

    result = evaluate_schema_compatibility(
        legacy_payload,
        reader="bundle_assembler",
        declarations=declarations,
        required_semantic_fields=("status",),
        migration={
            "source_payload_sha256": stable_payload_sha256(legacy_payload),
            "target_payload_sha256": stable_payload_sha256(migrated_payload),
            "target_payload": migrated_payload,
            "field_mappings": {"quality_status": "status"},
        },
    )

    assert result.decision == "compatible_with_migration"
    assert result.reason == "verified_lossless_migration"
    assert result.production_closeout_allowed is True
    assert result.migration_required is True
    assert result.migration_verified is True
    assert result.missing_semantic_fields == ()


def test_migration_with_semantic_loss_stays_legacy_quarantined() -> None:
    declarations = {
        "bundle_assembler": (
            ReaderSchemaRange(
                reader="bundle_assembler",
                schema_family="policyos.example_bundle",
                min_version="1",
                max_version="2",
                current_version="2",
                migration_versions=("1",),
            ),
        )
    }
    legacy_payload = {
        "schema_version": "policyos.example_bundle.v1",
        "quality_status": "pass",
        "artifact_ref": "cas://sha256/" + "a" * 64,
    }
    lossy_payload = {
        "schema_version": "policyos.example_bundle.v2",
        "status": "pass",
    }

    result = evaluate_schema_compatibility(
        legacy_payload,
        reader="bundle_assembler",
        declarations=declarations,
        required_semantic_fields=("status", "artifact_ref"),
        migration={
            "source_payload_sha256": stable_payload_sha256(legacy_payload),
            "target_payload_sha256": stable_payload_sha256(lossy_payload),
            "target_payload": lossy_payload,
            "semantic_loss": True,
            "lost_fields": ["artifact_ref"],
        },
    )

    assert result.decision == "legacy_quarantined"
    assert result.reason == "legacy_migration_semantic_loss"
    assert result.production_closeout_allowed is False
    assert result.migration_required is True
    assert result.migration_verified is False


def test_migration_missing_status_is_quarantined_as_semantic_loss() -> None:
    declarations = {
        "scorecard": (
            ReaderSchemaRange(
                reader="scorecard",
                schema_family="policyos.example_report",
                min_version="1",
                max_version="2",
                current_version="2",
                migration_versions=("1",),
            ),
        )
    }
    legacy_payload = {
        "schema_version": "policyos.example_report.v1",
        "quality_status": "pass",
    }
    migrated_payload = {
        "schema_version": "policyos.example_report.v2",
    }

    result = evaluate_schema_compatibility(
        legacy_payload,
        reader="scorecard",
        declarations=declarations,
        required_semantic_fields=("status",),
        migration={
            "source_payload_sha256": stable_payload_sha256(legacy_payload),
            "target_payload_sha256": stable_payload_sha256(migrated_payload),
            "target_payload": migrated_payload,
            "field_mappings": {"quality_status": "status"},
        },
    )

    assert result.decision == "legacy_quarantined"
    assert result.reason == "missing_required_semantic_fields"
    assert result.production_closeout_allowed is False
    assert result.missing_semantic_fields == ("status",)
