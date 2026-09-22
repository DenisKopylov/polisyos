"""Exports the artifact-migration registry used to upgrade stored payload schemas."""

from polisyos.common.migrations.base import migrate_artifact, register_migration

MANIFEST_CURRENT_VERSION = "1.0"

__all__ = [
    "MANIFEST_CURRENT_VERSION",
    "migrate_artifact",
    "register_migration",
]
