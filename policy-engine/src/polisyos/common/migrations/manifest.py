"""Public migrations manifest module API."""
from __future__ import annotations

from polisyos.common.migrations.base import ArtifactPayload, register_migration

MANIFEST_CURRENT_VERSION = "1.0"


@register_migration("dataset_manifest", "0.9", "1.0")
def migrate_manifest_0_9_to_1_0(data: ArtifactPayload) -> ArtifactPayload:
    # Placeholder: fill missing manifest fields if older versions differ.
    """Migrate manifest 0 9 to 1 0 helper."""
    if "datasetName" in data and "dataset_name" not in data:
        data["dataset_name"] = data.pop("datasetName")
    if "rawHash" in data and "raw_hash" not in data:
        data["raw_hash"] = data.pop("rawHash")
    return data
