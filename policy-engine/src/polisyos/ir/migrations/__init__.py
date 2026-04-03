"""Versioned entrypoints for migrating canonical policy IR payloads between schema releases."""
from __future__ import annotations

import re

from polisyos.ir.migrations.base import migrate_artifact
from polisyos.ir.migrations.base import register_migration as _register_migration
from polisyos.ir.migrations.policy_ir import POLICY_IR_CURRENT_VERSION

IR_ARTIFACT = "policy_ir"
IR_CURRENT_VERSION = POLICY_IR_CURRENT_VERSION

_VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)$")


def parse_version(version: str) -> tuple[int, int]:
    """Parse a schema version string into ``(major, minor)`` for migration comparisons."""
    match = _VERSION_RE.match(version)
    if not match:
        raise ValueError(f"Invalid schema version '{version}'. Expected MAJOR.MINOR.")
    return int(match.group("major")), int(match.group("minor"))


def is_major_bump(from_version: str, to_version: str) -> bool:
    """Return whether is major bump."""
    from_major, _ = parse_version(from_version)
    to_major, _ = parse_version(to_version)
    return to_major != from_major


def register_migration(from_version: str, to_version: str):
    """Register policy IR migration in shared registry."""
    parse_version(from_version)
    parse_version(to_version)
    return _register_migration(IR_ARTIFACT, from_version, to_version)


def migrate_policy_ir(
    data: dict,
    target_version: str | None = None,
    *,
    allow_major: bool = False,
) -> dict:
    """Migrate canonical Trinity payload versions."""
    if "schema_version" not in data:
        raise ValueError("Missing schema_version for policy IR")

    current_version = str(data["schema_version"])
    if current_version.startswith("2.") or "semantic" in data:
        raise ValueError(
            "Legacy non-Trinity payloads are not supported by runtime migrations."
        )

    target = target_version or IR_CURRENT_VERSION
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
