import pytest

from polisyos.ir.migrations import IR_CURRENT_VERSION, migrate_policy_ir

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
