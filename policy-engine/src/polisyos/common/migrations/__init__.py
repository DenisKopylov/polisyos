"""Public common migrations package API."""
from polisyos.common.migrations.base import migrate_artifact, register_migration
from polisyos.common.migrations.manifest import MANIFEST_CURRENT_VERSION

__all__ = [
    "migrate_artifact",
    "register_migration",
    "MANIFEST_CURRENT_VERSION",
]
