import pytest

from polisyos.ir.migrations import IR_CURRENT_VERSION, migrate_policy_ir


def test_migrate_policy_ir_passthrough_surface() -> None:
    payload = {"schema_version": "2.0", "semantic": {"context_snapshot_ref": "sha256:" + "0" * 64}}
    migrated = migrate_policy_ir(payload, IR_CURRENT_VERSION)
    assert migrated["schema_version"] == "2.0"


def test_migrate_policy_ir_rejects_invalid_version() -> None:
    payload = {"schema_version": "v1"}
    with pytest.raises(ValueError):
        migrate_policy_ir(payload, IR_CURRENT_VERSION)


def test_migrate_policy_ir_rejects_legacy_versions() -> None:
    payload = {"schema_version": "1.0"}
    with pytest.raises(ValueError):
        migrate_policy_ir(payload, IR_CURRENT_VERSION)
