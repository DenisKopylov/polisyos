from __future__ import annotations

from polisyos.common import migrations as common_migrations
from polisyos.common.migrations import _engine
from polisyos.ir.migrations import base as ir_migrations


def test_shared_migration_engine_is_exported_without_copying() -> None:
    assert common_migrations.LinearMigrationProfile is _engine.LinearMigrationProfile
    assert common_migrations.run_linear_migration is _engine.run_linear_migration
    assert ir_migrations.LinearMigrationProfile is _engine.LinearMigrationProfile
    assert ir_migrations.run_linear_migration is _engine.run_linear_migration
