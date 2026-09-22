"""Deprecated Common-owned compatibility callback for legacy manifest callers."""

from __future__ import annotations

from polisyos.common.migrations.base import (
    ArtifactPayload,
    register_migration,
)

MANIFEST_CURRENT_VERSION = "1.0"


@register_migration("dataset_manifest", "0.9", "1.0")
def migrate_manifest_0_9_to_1_0(data: ArtifactPayload) -> ArtifactPayload:
    """Preserve the old callback for explicit legacy-module callers.

    The canonical schema-owner callback lives in Fabric identity.  This
    deprecated duplicate remains only so existing imports retain their
    historical registration side effect while callers migrate; Common's
    engine still owns copying the caller payload and stamping the next
    schema version.
    """
    if "datasetName" in data and "dataset_name" not in data:
        data["dataset_name"] = data.pop("datasetName")
    if "rawHash" in data and "raw_hash" not in data:
        data["raw_hash"] = data.pop("rawHash")
    return data


__all__ = [
    "ArtifactPayload",
    "MANIFEST_CURRENT_VERSION",
    "migrate_manifest_0_9_to_1_0",
    "register_migration",
]
