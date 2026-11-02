"""Canonical owner and schema admission for persisted Fabric source evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.core.artifacts import load_core_json_artifact
from polisyos.core.contracts.fabric import EvidenceBundle

if TYPE_CHECKING:
    from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef, SchemaInfo
    from polisyos.core.artifacts.protocol import ArtifactStore


def require_source_evidence_schema(manifest: ArtifactManifest) -> SchemaInfo:
    """Require the actual source-evidence owner and supported schema contract.

    Args:
        manifest: Exact manifest returned by the artifact owner's reader.

    Returns:
        SchemaInfo: The supported manifest schema contract.

    Raises:
        ValueError: If the selected view has a different owner or schema.
    """
    schema = manifest.artifact_schema
    if schema is None:
        raise ValueError("source evidence manifest has no schema information")
    if (
        manifest.kind != "fabric.evidence_bundle"
        or manifest.media_type != "application/json"
        or schema.name != "fabric.evidence_bundle"
        or schema.version not in {"1.0", "2.0"}
    ):
        raise ValueError("source evidence selected view has an unsupported owner or schema")
    return schema


def load_source_evidence_bundle(
    store: ArtifactStore,
    ref: ArtifactRef,
    *,
    require_selected_profile: bool = False,
) -> tuple[EvidenceBundle, ArtifactManifest]:
    """Read source evidence through its exact owner, schema and Core byte boundary.

    Args:
        store: Artifact store containing the selected evidence view.
        ref: Evidence selector; an unqualified reference means the current default.
        require_selected_profile: Require an explicit selected view for source binding.

    Returns:
        tuple[EvidenceBundle, ArtifactManifest]: Verified payload and its exact manifest.

    Raises:
        ValueError: If the selector, owner, schema or selected bytes are invalid.
        FileNotFoundError: If the selected artifact is unavailable.
        PermissionError: If the selected artifact is not accessible to this caller.
    """
    if require_selected_profile and ref.manifest_profile_sha256 is None:
        raise ValueError("source evidence requires an explicit selected manifest profile")
    manifest = store.get_manifest(ref)
    require_source_evidence_schema(manifest)
    if (
        manifest.artifact_id != ref.artifact_id
        or manifest.kind != ref.kind
        or manifest.media_type != ref.media_type
    ):
        raise ValueError("source evidence selector differs from its selected manifest")
    bundle = EvidenceBundle.model_validate(load_core_json_artifact(store, ref))
    return bundle, manifest
