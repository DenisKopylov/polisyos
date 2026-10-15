"""Exports the artifact-migration registry used to upgrade stored payload schemas."""

from polisyos.common.migrations._engine import (
    LinearMigrationProfile,
    run_linear_migration,
)
from polisyos.common.migrations.base import (
    ArtifactPayload as ArtifactPayload,
)
from polisyos.common.migrations.base import (
    migrate_artifact,
    register_migration,
)

MANIFEST_CURRENT_VERSION = "1.0"

__all__ = [
    "MANIFEST_CURRENT_VERSION",
    "ArtifactPayload",
    "LinearMigrationProfile",
    "migrate_artifact",
    "register_migration",
    "run_linear_migration",
]
