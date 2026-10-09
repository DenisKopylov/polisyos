from __future__ import annotations

from copy import deepcopy

from polisyos.common import migrations as common_migrations
from polisyos.common.migrations import _engine
from polisyos.common.migrations.base import migrate_artifact
from polisyos.common.migrations.manifest import MANIFEST_CURRENT_VERSION
from polisyos.ir.migrations import base as ir_migrations


def test_shared_migration_engine_is_exported_without_copying() -> None:
    assert common_migrations.LinearMigrationProfile is _engine.LinearMigrationProfile
    assert common_migrations.run_linear_migration is _engine.run_linear_migration
    assert ir_migrations.LinearMigrationProfile is _engine.LinearMigrationProfile
    assert ir_migrations.run_linear_migration is _engine.run_linear_migration


def test_migrate_artifact_does_not_mutate_input() -> None:
    original = {
        "schema_version": "0.9",
        "datasetName": "baseline",
        "rawHash": "sha256:abc",
        "nested": {"keep": True},
    }
    before = deepcopy(original)

    migrated = migrate_artifact(
        original,
        artifact="dataset_manifest",
        target_version=MANIFEST_CURRENT_VERSION,
    )

    assert original == before
    assert migrated["schema_version"] == MANIFEST_CURRENT_VERSION
    assert migrated["dataset_name"] == "baseline"
    assert migrated["raw_hash"] == "sha256:abc"


def test_migrate_artifact_is_idempotent_for_current_version() -> None:
    current = {
        "schema_version": MANIFEST_CURRENT_VERSION,
        "dataset_name": "baseline",
        "raw_hash": "sha256:abc",
    }

    first = migrate_artifact(
        current,
        artifact="dataset_manifest",
        target_version=MANIFEST_CURRENT_VERSION,
    )
    second = migrate_artifact(
        first,
        artifact="dataset_manifest",
        target_version=MANIFEST_CURRENT_VERSION,
    )

    assert first == second
    assert first is not current
