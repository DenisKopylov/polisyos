from __future__ import annotations

import re
from typing import Callable, Dict, Tuple

MigrationFn = Callable[[dict], dict]

_MIGRATIONS: Dict[str, Tuple[str, MigrationFn]] = {}

_VERSION_RE = re.compile(r"^(?P<major>\\d+)\\.(?P<minor>\\d+)$")


def parse_version(version: str) -> tuple[int, int]:
    match = _VERSION_RE.match(version)
    if not match:
        raise ValueError(f"Invalid schema version '{version}'. Expected MAJOR.MINOR.")
    return int(match.group("major")), int(match.group("minor"))


def is_major_bump(from_version: str, to_version: str) -> bool:
    from_major, _ = parse_version(from_version)
    to_major, _ = parse_version(to_version)
    return to_major != from_major


def register_migration(from_version: str, to_version: str):
    parse_version(from_version)
    parse_version(to_version)

    def decorator(fn: MigrationFn) -> MigrationFn:
        if from_version in _MIGRATIONS:
            raise ValueError(f"Migration from {from_version} already registered.")
        _MIGRATIONS[from_version] = (to_version, fn)
        return fn

    return decorator


def migrate_policy_ir(data: dict, target_version: str, *, allow_major: bool = False) -> dict:
    if "schema_version" not in data:
        raise ValueError("Missing schema_version for policy IR")
    current_version = data["schema_version"]
    parse_version(current_version)
    parse_version(target_version)

    if not allow_major and is_major_bump(current_version, target_version):
        raise ValueError(
            f"Major version change requires --allow-major: {current_version} -> {target_version}"
        )

    visited = set()
    while current_version != target_version:
        if current_version in visited:
            raise ValueError(
                f"Migration loop detected for policy IR: {current_version} -> {target_version}"
            )
        visited.add(current_version)

        if current_version not in _MIGRATIONS:
            raise ValueError(
                f"No migrator for policy IR from {current_version} to {target_version}"
            )
        next_version, fn = _MIGRATIONS[current_version]
        if not allow_major and is_major_bump(current_version, next_version):
            raise ValueError(
                f"Major version migration blocked: {current_version} -> {next_version}"
            )
        data = fn(data)
        data["schema_version"] = next_version
        current_version = next_version

    return data
