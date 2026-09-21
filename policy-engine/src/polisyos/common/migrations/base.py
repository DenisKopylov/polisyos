"""Registers and executes version-to-version migrations for persisted artifacts."""

from __future__ import annotations

import copy
from collections.abc import Callable

from polisyos.common.migrations._engine import (
    LinearMigrationProfile,
    run_linear_migration,
)

ArtifactPayload = dict[str, object]
MigrationDecorator = Callable[["MigrationFn"], "MigrationFn"]

MigrationFn = Callable[[ArtifactPayload], ArtifactPayload]

_MIGRATIONS: dict[str, dict[str, tuple[str, MigrationFn]]] = {}


def register_migration(
    artifact: str,
    from_version: str,
    to_version: str,
) -> MigrationDecorator:
    """Register migration."""

    def decorator(fn: MigrationFn) -> MigrationFn:
        _MIGRATIONS.setdefault(artifact, {})[from_version] = (to_version, fn)
        return fn

    return decorator


def _prepare_common_payload(
    data: ArtifactPayload,
    artifact: str,
) -> tuple[ArtifactPayload, str]:
    current_data = copy.deepcopy(data)
    if "schema_version" not in current_data:
        raise ValueError(f"Missing schema_version for artifact '{artifact}'")
    schema_version = current_data["schema_version"]
    if not isinstance(schema_version, str):
        raise TypeError(
            f"schema_version for '{artifact}' must be a string, got {type(schema_version).__name__}"
        )
    return current_data, schema_version


def _lookup_common_edge(
    artifact: str,
    from_version: str,
) -> tuple[str, MigrationFn] | None:
    return _MIGRATIONS.get(artifact, {}).get(from_version)


def _common_edge_target(edge: tuple[str, MigrationFn]) -> str:
    return edge[0]


def _apply_common_step(
    data: ArtifactPayload,
    edge: tuple[str, MigrationFn],
    artifact: str,
    from_version: str,
    to_version: str,
) -> ArtifactPayload:
    del to_version
    next_version, fn = edge
    migrated = fn(copy.deepcopy(data))
    if not isinstance(migrated, dict):
        raise TypeError(
            f"Migrator for '{artifact}' from {from_version} returned "
            f"{type(migrated).__name__}, expected dict"
        )
    current_data = copy.deepcopy(migrated)
    current_data["schema_version"] = next_version
    return current_data


_COMMON_PROFILE = LinearMigrationProfile(
    prepare=_prepare_common_payload,
    no_op=lambda payload: payload,
    edge_target=_common_edge_target,
    apply_step=_apply_common_step,
)


def migrate_artifact(
    data: ArtifactPayload,
    artifact: str,
    target_version: str,
) -> ArtifactPayload:
    """Apply the registered migration chain without mutating caller-owned input."""
    return run_linear_migration(
        data,
        artifact=artifact,
        target_version=target_version,
        edge_lookup=_lookup_common_edge,
        profile=_COMMON_PROFILE,
    )
