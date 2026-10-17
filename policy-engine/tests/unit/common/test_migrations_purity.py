from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from polisyos.common import migrations as common_migrations
from polisyos.common.migrations import _engine
from polisyos.ir.migrations import base as ir_migrations


def test_common_facade_exports_shared_migration_engine_without_copying() -> None:
    assert common_migrations.LinearMigrationProfile is _engine.LinearMigrationProfile
    assert common_migrations.run_linear_migration is _engine.run_linear_migration


def test_ir_migration_delegates_to_shared_engine_with_ir_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = "tests.unit.common.test_migrations_purity.ir_delegation"
    source_version = "0.1"
    target_version = "0.2"

    def conflicting_version(data: dict[str, Any]) -> dict[str, Any]:
        return {**data, "schema_version": "9.9"}

    monkeypatch.setitem(ir_migrations._MIGRATIONS, artifact, {})
    monkeypatch.setitem(ir_migrations._SCHEMA_REGISTRY, artifact, {})
    ir_migrations.register_migration(
        artifact,
        source_version,
        target_version,
        compatibility=ir_migrations.CompatibilityMode.FULL,
    )(conflicting_version)

    real_runner = common_migrations.run_linear_migration
    runner_spy = Mock(wraps=real_runner)
    monkeypatch.setattr(common_migrations, "run_linear_migration", runner_spy)

    with pytest.raises(
        ir_migrations.MigrationSchemaVersionError,
        match="returned schema_version",
    ):
        ir_migrations.migrate_artifact(
            {"schema_version": source_version},
            artifact,
            target_version,
        )

    runner_spy.assert_called_once()
    assert runner_spy.call_args is not None
    call_kwargs = runner_spy.call_args.kwargs
    profile = call_kwargs["profile"]

    assert call_kwargs["artifact"] == artifact
    assert call_kwargs["edge_lookup"] is ir_migrations._lookup_ir_edge
    assert isinstance(profile, _engine.LinearMigrationProfile)
    assert profile.prepare is ir_migrations._prepare_ir_payload
    assert profile.edge_target is ir_migrations._ir_edge_target
    assert profile.apply_step is ir_migrations._apply_ir_step
