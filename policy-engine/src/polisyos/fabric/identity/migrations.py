"""Schema migrations owned by the Fabric identity manifest model."""

from __future__ import annotations

from typing import Final

from polisyos.common.migrations.base import (
    ArtifactPayload,
    MigrationFn,
    register_migration,
)

MANIFEST_CURRENT_VERSION: Final[str] = "1.0"


def migrate_manifest_0_9_to_1_0(data: ArtifactPayload) -> ArtifactPayload:
    """Rename the supported 0.9 manifest aliases without inventing fields.

    This is a format conversion only.  It deliberately does not validate the
    Fabric DTO, resolve duplicate aliases, or manufacture provenance and
    timestamp fields that were not present in the legacy payload.
    """
    if "datasetName" in data and "dataset_name" not in data:
        data["dataset_name"] = data.pop("datasetName")
    if "rawHash" in data and "raw_hash" not in data:
        data["raw_hash"] = data.pop("rawHash")
    return data


def register_manifest_migration(converter: MigrationFn | None = None) -> None:
    """Register the selected Fabric-owned converter with Common's engine.

    Args:
        converter: Resolved composition-layer implementation. When omitted,
            register this module's canonical 0.9-to-1.0 converter.
    """
    register_migration("dataset_manifest", "0.9", "1.0")(
        converter if converter is not None else migrate_manifest_0_9_to_1_0
    )


__all__ = [
    "MANIFEST_CURRENT_VERSION",
    "migrate_manifest_0_9_to_1_0",
    "register_manifest_migration",
]
