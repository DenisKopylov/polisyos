"""Exports the artifact-migration registry used to upgrade stored payload schemas."""

from polisyos.common.migrations.base import migrate_artifact, register_migration
from polisyos.common.migrations.manifest import MANIFEST_CURRENT_VERSION

__all__ = [
    "MANIFEST_CURRENT_VERSION",
    "migrate_artifact",
    "register_migration",
]
