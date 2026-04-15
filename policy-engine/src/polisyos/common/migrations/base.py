"""Registers and executes version-to-version migrations for persisted artifacts."""
from __future__ import annotations

import copy
from typing import Callable, Dict, Tuple

MigrationFn = Callable[[dict], dict]

_MIGRATIONS: Dict[str, Dict[str, Tuple[str, MigrationFn]]] = {}


def register_migration(artifact: str, from_version: str, to_version: str):
    """Register migration."""
    def decorator(fn: MigrationFn) -> MigrationFn:
        _MIGRATIONS.setdefault(artifact, {})[from_version] = (to_version, fn)
        return fn

    return decorator


def migrate_artifact(data: dict, artifact: str, target_version: str) -> dict:
    """Apply the registered migration chain without mutating caller-owned input."""
    current_data = copy.deepcopy(data)
    if "schema_version" not in current_data:
        raise ValueError(f"Missing schema_version for artifact '{artifact}'")
    current_version = current_data["schema_version"]
    if current_version == target_version:
        return current_data

    visited = set()
    while current_version != target_version:
        if current_version in visited:
            raise ValueError(
                f"Migration loop detected for '{artifact}': {current_version} -> {target_version}"
            )
        visited.add(current_version)

        artifact_migrations = _MIGRATIONS.get(artifact, {})
        if current_version not in artifact_migrations:
            raise ValueError(
                f"No migrator for '{artifact}' from {current_version} to {target_version}"
            )
        next_version, fn = artifact_migrations[current_version]
        migrated = fn(copy.deepcopy(current_data))
        if not isinstance(migrated, dict):
            raise TypeError(
                f"Migrator for '{artifact}' from {current_version} returned "
                f"{type(migrated).__name__}, expected dict"
            )
        current_data = copy.deepcopy(migrated)
        current_data["schema_version"] = next_version
        current_version = next_version

    return current_data
