"""Bind typed references to the exact CAS manifest view selected by a producer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from ._manifest_lifecycle import ManifestLifecycle
from .manifest import ArtifactRef

if TYPE_CHECKING:
    from .protocol import ArtifactStore


def profile_bound_ref[TArtifactRef: BaseModel](
    store: ArtifactStore, ref: TArtifactRef
) -> TArtifactRef:
    """Pin a typed ref to the manifest view selected at this producer boundary.

    A profileless input resolves through the store's current default selector.
    This binds new lineage; it does not attest an earlier producer's view.

    Raises:
        ValueError: If manifest identity, exact-profile lookup, or CAS integrity
            does not match the typed reference.
    """
    payload = ref.model_dump(mode="python")
    core_ref = ArtifactRef.model_validate(payload)
    try:
        manifest = store.get_manifest(core_ref)
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError("artifact_manifest_view_unavailable") from exc
    if (
        manifest.artifact_id != core_ref.artifact_id
        or manifest.kind != core_ref.kind
        or manifest.media_type != core_ref.media_type
    ):
        raise ValueError("artifact_manifest_ref_identity_mismatch")
    profile = ManifestLifecycle.profile_sha256(manifest)
    if (
        core_ref.manifest_profile_sha256 is not None
        and core_ref.manifest_profile_sha256 != profile
    ):
        raise ValueError("artifact_manifest_ref_profile_mismatch")
    qualified_payload = {**payload, "manifest_profile_sha256": profile}
    qualified = type(ref).model_validate(qualified_payload)
    exact_ref = ArtifactRef.model_validate(qualified_payload)
    if store.get_manifest(exact_ref) != manifest:
        raise ValueError("artifact_manifest_profile_resolution_mismatch")
    if not store.verify(exact_ref).ok:
        raise ValueError("artifact_manifest_profile_integrity_failed")
    return qualified
