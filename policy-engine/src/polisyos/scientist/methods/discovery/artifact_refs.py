"""Bind newly written discovery refs to the manifest view the CAS actually stored."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts.manifest import ArtifactRef as CoreArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS

TArtifactRef = TypeVar("TArtifactRef", bound=BaseModel)


def profile_bound_written_ref[TArtifactRef: BaseModel](store: FileSystemCAS, ref: TArtifactRef) -> TArtifactRef:
    """Return the same typed ref pinned to its freshly persisted manifest view.

    The CAS writer intentionally returns ``manifest_profile_sha256=None`` when
    the selected view is also the default alias. Discovery artifacts that form
    a source chain need an exact view, so this helper resolves the returned
    selector, derives the profile from the stored manifest, and verifies that
    exact selected view before returning it.

    Args:
        store: The CAS that accepted the write.
        ref: The typed reference returned by that write.

    Returns:
        The same ref subtype with the computed manifest-profile digest.

    Raises:
        ValueError: If the stored manifest does not match the ref or its exact
            selected view fails CAS integrity verification.
    """
    payload = ref.model_dump(mode="json")
    core_ref = CoreArtifactRef.model_validate(payload)
    manifest = store.get_manifest(core_ref)
    if (
        manifest.artifact_id != core_ref.artifact_id
        or manifest.kind != core_ref.kind
        or manifest.media_type != core_ref.media_type
    ):
        raise ValueError("discovery_written_manifest_ref_identity_mismatch")

    profile_sha256 = artifact_manifest_profile_sha256(manifest)
    qualified_payload = {**payload, "manifest_profile_sha256": profile_sha256}
    qualified_ref = type(ref).model_validate(qualified_payload)
    qualified_core_ref = CoreArtifactRef.model_validate(qualified_payload)
    if store.get_manifest(qualified_core_ref) != manifest:
        raise ValueError("discovery_written_manifest_profile_mismatch")
    if not store.verify(qualified_core_ref).ok:
        raise ValueError("discovery_written_artifact_integrity_failed")
    return qualified_ref
