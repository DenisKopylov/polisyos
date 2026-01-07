import pytest

from polisyos.ir.migrations import IR_CURRENT_VERSION, migrate_policy_ir


def test_migrate_policy_ir_0_9_to_1_0() -> None:
    payload = {
        "schema_version": "0.9",
        "projectName": {"en": "Demo", "ua": "Demo"},
        "globalConstraints": {"min_balance": -100.0},
    }
    migrated = migrate_policy_ir(payload, IR_CURRENT_VERSION)
    assert migrated["schema_version"] == "1.0"
    assert "project_name" in migrated
    assert "projectName" not in migrated
    assert "global_constraints" in migrated


def test_migrate_policy_ir_rejects_invalid_version() -> None:
    payload = {"schema_version": "v1"}
    with pytest.raises(ValueError):
        migrate_policy_ir(payload, IR_CURRENT_VERSION)
