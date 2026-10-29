"""Typed schema access for persisted Fabric source-evidence projections."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.core.artifacts.manifest import ArtifactManifest, SchemaInfo


def require_source_evidence_schema(manifest: ArtifactManifest) -> SchemaInfo:
    """Return the persisted source-evidence schema or refuse an untyped projection.

    Args:
        manifest: Exact manifest returned by the artifact owner's reader.

    Returns:
        SchemaInfo: The manifest's typed schema contract.

    Raises:
        ValueError: If the persisted source-evidence manifest has no schema.
    """
    schema = manifest.artifact_schema
    if schema is None:
        raise ValueError("source evidence manifest has no schema information")
    return schema
