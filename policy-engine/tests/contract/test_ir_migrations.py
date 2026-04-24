import pytest

from polisyos.ir.canon import to_canonical_bytes
from polisyos.ir.migrations import (
    IR_CURRENT_VERSION,
    CompatibilityMode,
    can_read_schema,
    get_schema_rule,
    migrate_policy_ir,
    negotiate_schema_version,
)

ZERO_REF = "sha256:" + "0" * 64


def _canonical_trinity_payload() -> dict:
    return {
        "schema_version": "1.0",
        "problem_frame": {
            "schema_version": "1.0",
            "problem_id": "pf_test",
            "domain": "custom",
            "objectives": [],
            "kpis": [],
            "success_criteria": [],
            "hard_constraints": [],
            "soft_constraints": [],
            "stakeholders": [],
            "labels": [],
            "notes": [],
        },
        "policy_spec": {
            "schema_version": "1.0",
            "policy_id": "ps_test",
            "interventions": [],
            "mechanism_bindings": [],
            "parameters": [],
            "labels": [],
            "notes": [],
        },
        "model_spec": {
            "schema_version": "1.0",
            "model_id": "ms_test",
            "data_snapshot_ref": ZERO_REF,
            "registry_bundle_ref": None,
            "assumptions": [],
            "labels": [],
            "notes": [],
        },
    }


def test_migrate_policy_ir_accepts_canonical_trinity_payload() -> None:
    payload = _canonical_trinity_payload()
    migrated = migrate_policy_ir(payload, IR_CURRENT_VERSION)
    assert migrated["schema_version"] == "1.0"
    assert migrated["policy_spec"]["policy_id"] == "ps_test"


def test_migrate_policy_ir_rejects_invalid_version() -> None:
    payload = {"schema_version": "v1"}
    with pytest.raises(ValueError):
        migrate_policy_ir(payload, IR_CURRENT_VERSION)


def test_migrate_policy_ir_rejects_non_trinity_schema_v2() -> None:
    payload = {
        "schema_version": "2.0",
        "semantic": {"context_snapshot_ref": ZERO_REF},
    }
    with pytest.raises(ValueError, match="Legacy non-Trinity payloads"):
        migrate_policy_ir(payload, IR_CURRENT_VERSION)


def test_migrate_policy_ir_rejects_non_trinity_semantic_surface() -> None:
    payload = {
        "schema_version": "1.0",
        "semantic": {"context_snapshot_ref": ZERO_REF},
    }
    with pytest.raises(ValueError, match="Legacy non-Trinity payloads"):
        migrate_policy_ir(payload, IR_CURRENT_VERSION)


def test_migrate_policy_ir_rejects_missing_schema_version() -> None:
    payload = {"policy_spec": {"schema_version": "1.0"}}
    with pytest.raises(ValueError):
        migrate_policy_ir(payload, IR_CURRENT_VERSION)


def test_schema_registry_answers_backward_compatibility_for_old_payloads() -> None:
    decision = negotiate_schema_version(
        "article_extraction_result",
        producer_version="1.0",
        consumer_version="1.5",
    )

    assert decision.can_read is True
    assert decision.mode is CompatibilityMode.BACKWARD
    assert decision.migration_required is False
    assert can_read_schema("transportability_result", "1.0", "2.0") is True


def test_schema_registry_rejects_unknown_or_cross_major_payloads() -> None:
    unknown = negotiate_schema_version(
        "article_extraction_result",
        producer_version="1.0",
        consumer_version="9.9",
    )
    cross_major = negotiate_schema_version(
        "article_extraction_result",
        producer_version="2.0",
        consumer_version="1.5",
    )

    assert unknown.can_read is False
    assert unknown.reason == "unknown_consumer_version"
    assert cross_major.can_read is False
    assert cross_major.reason == "not_compatible"


def test_schema_registry_records_field_evolution_policy() -> None:
    article_rule = get_schema_rule("article_extraction_result", "1.5")
    transport_rule = get_schema_rule("transportability_result", "2.0")

    assert article_rule is not None
    assert article_rule.mode is CompatibilityMode.BACKWARD
    assert ("publication_year", "year") in article_rule.renamed_fields
    assert "paper_kind" in article_rule.additive_optional_fields
    assert transport_rule is not None
    assert ("formula", "transport_formula") in transport_rule.renamed_fields
    assert ("schema_version", "2.0") in transport_rule.canonical_defaults


def test_old_canonical_fixture_bytes_do_not_silently_degrade() -> None:
    legacy_payload = {
        "schema_version": "1.0",
        "openalex_id": "W1",
        "title": "Legacy",
        "publication_year": 2020,
    }

    assert can_read_schema("article_extraction_result", "1.0", "1.5") is True
    assert to_canonical_bytes(legacy_payload) == (
        b'{"openalex_id":"W1","publication_year":2020,"schema_version":"1.0","title":"Legacy"}'
    )
