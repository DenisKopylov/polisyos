"""Bind typed references to the exact CAS manifest view selected by a producer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel

from ._manifest_lifecycle import ManifestLifecycle
from .manifest import ArtifactRef

if TYPE_CHECKING:
    from ._integrity_ops import VerificationReport
    from .manifest import ArtifactManifest


class _ProfileBoundArtifactReader(Protocol):
    """Core selected-manifest reads required to bind one typed artifact ref."""

    def get_manifest(self, artifact_id: ArtifactRef) -> ArtifactManifest: ...

    def verify(self, artifact_id: ArtifactRef) -> VerificationReport: ...


def profile_bound_ref[TArtifactRef: BaseModel](
    store: _ProfileBoundArtifactReader, ref: TArtifactRef
) -> TArtifactRef:
    """Pin a typed ref to the manifest view selected at this producer boundary.

    A profileless input resolves through the store's current default selector.
    This binds new lineage; it does not attest an earlier producer's view.

    Raises:
        ValueError: If manifest identity, exact-profile lookup, or CAS integrity
            does not match the typed reference.
    """
    from polisyos.ir.artifacts.contracts import normalize_artifact_ref

    try:
        payload = normalize_artifact_ref(ref)
    except (TypeError, ValueError) as exc:
        raise ValueError("artifact_manifest_ref_identity_mismatch") from exc
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
    if core_ref.manifest_profile_sha256 is not None and core_ref.manifest_profile_sha256 != profile:
        raise ValueError("artifact_manifest_ref_profile_mismatch")
    qualified_payload = {**payload, "manifest_profile_sha256": profile}
    try:
        qualified = type(ref).model_validate(qualified_payload)
        qualified_identity = normalize_artifact_ref(qualified)
    except (TypeError, ValueError) as exc:
        raise ValueError("artifact_manifest_ref_identity_mismatch") from exc
    if qualified_identity != qualified_payload:
        raise ValueError("artifact_manifest_ref_identity_mismatch")
    exact_ref = ArtifactRef.model_validate(qualified_payload)
    if store.get_manifest(exact_ref) != manifest:
        raise ValueError("artifact_manifest_profile_resolution_mismatch")
    if not store.verify(exact_ref).ok:
        raise ValueError("artifact_manifest_profile_integrity_failed")
    return qualified
