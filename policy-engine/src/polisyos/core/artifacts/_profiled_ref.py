"""Bind typed references to the exact CAS manifest view selected by a producer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel

from ._manifest_lifecycle import ManifestLifecycle
from .ids import ArtifactID
from .manifest import ArtifactRef

if TYPE_CHECKING:
    from ._integrity_ops import VerificationReport
    from .manifest import ArtifactManifest


class _ProfileBoundArtifactReader(Protocol):
    """Core selected-manifest reads required to bind one typed artifact ref."""

    def get_manifest(self, artifact_id: ArtifactID | ArtifactRef) -> ArtifactManifest: ...

    def verify(self, artifact_id: ArtifactRef) -> VerificationReport: ...


def legacy_default_artifact_id(
    store: _ProfileBoundArtifactReader, produced_ref: ArtifactRef
) -> ArtifactID | None:
    """Return a legacy ID only when its default names the verified produced view.

    Selected-view authorization and integrity are required first. A foreign or
    missing default merely makes the optional legacy alias unavailable. An old
    profileless reference explicitly selects the current default; it cannot
    recover an earlier producer's view.

    Args:
        store: Artifact reader enforcing access to each exact manifest view.
        produced_ref: Reference selected by the producer.

    Returns:
        The legacy artifact ID, or None when that alias cannot name this view.

    Raises:
        ArtifactOwnershipError: If the produced view is inaccessible.
        ValueError: If its identity or integrity is invalid, or another default
            read failure prevents establishing the optional alias.
    """
    from ._integrity_ops import ArtifactIntegrityError
    from .ownership import ArtifactOwnershipError

    selected = ArtifactRef.model_validate(produced_ref.model_dump(mode="python"))
    manifest = store.get_manifest(selected)
    if (
        manifest.artifact_id != selected.artifact_id
        or manifest.kind != selected.kind
        or manifest.media_type != selected.media_type
    ):
        raise ValueError("selected_artifact_identity_mismatch")
    profile = ManifestLifecycle.profile_sha256(manifest)
    if selected.manifest_profile_sha256 not in {None, profile}:
        raise ValueError("selected_artifact_profile_mismatch")
    selected = selected.model_copy(update={"manifest_profile_sha256": profile})
    if not store.verify(selected).ok:
        raise ArtifactIntegrityError("selected_artifact_integrity_failed")

    try:
        default = store.get_manifest(selected.artifact_id)
    except (ArtifactOwnershipError, FileNotFoundError):
        return None
    if default.artifact_id != selected.artifact_id:
        raise ValueError("default_artifact_identity_mismatch")
    if (
        default.kind != selected.kind
        or default.media_type != selected.media_type
        or ManifestLifecycle.profile_sha256(default) != profile
    ):
        return None
    return selected.artifact_id


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
