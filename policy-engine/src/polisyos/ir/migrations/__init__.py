from __future__ import annotations

import re

from polisyos.ir.migrations.base import migrate_artifact
from polisyos.ir.migrations.base import register_migration as _register_migration
from polisyos.ir.migrations.policy_ir import POLICY_IR_CURRENT_VERSION

IR_ARTIFACT = "policy_ir"
IR_CURRENT_VERSION = POLICY_IR_CURRENT_VERSION

_VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)$")


def parse_version(version: str) -> tuple[int, int]:
    match = _VERSION_RE.match(version)
    if not match:
        raise ValueError(f"Invalid schema version '{version}'. Expected MAJOR.MINOR.")
    return int(match.group("major")), int(match.group("minor"))


def is_major_bump(from_version: str, to_version: str) -> bool:
    from_major, _ = parse_version(from_version)
    to_major, _ = parse_version(to_version)
    # Policy IR versioning treats the stabilization jump 0.x -> 1.x as a
    # backwards-compatible migration path (tests rely on this).
    if from_major == 0 and to_major == 1:
        return False
    return to_major != from_major


def register_migration(from_version: str, to_version: str):
    """
    Backwards-compatible shim that registers policy IR migrations
    using the shared common.migrations registry.
    """
    parse_version(from_version)
    parse_version(to_version)
    return _register_migration(IR_ARTIFACT, from_version, to_version)


def migrate_policy_ir(
    data: dict, target_version: str | None = None, *, allow_major: bool = False
) -> dict:
    """
    Migrate policy IR payload using the shared common.migrations registry.
    """
    if "schema_version" not in data:
        raise ValueError("Missing schema_version for policy IR")
    current_version = data["schema_version"]
    target = target_version or IR_CURRENT_VERSION
    if not str(current_version).startswith("2."):
        raise ValueError("Legacy policy IR versions are not supported; expected 2.x PolicySurfaceIR.")
    if not str(target).startswith("2."):
        raise ValueError("Target policy IR version must be 2.x.")
    parse_version(current_version)
    parse_version(target)

    if not allow_major and is_major_bump(current_version, target):
        raise ValueError(
            f"Major version change requires allow_major=True: {current_version} -> {target}"
        )

    return migrate_artifact(data, IR_ARTIFACT, target)


__all__ = [
    "IR_ARTIFACT",
    "IR_CURRENT_VERSION",
    "is_major_bump",
    "migrate_policy_ir",
    "parse_version",
    "register_migration",
]
