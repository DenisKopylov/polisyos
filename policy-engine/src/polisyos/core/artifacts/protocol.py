"""ArtifactStore protocol — backend-agnostic CAS interface.

``FileSystemCAS`` (the original implementation) satisfies this protocol
structurally.  Cloud backends (S3, GCS) and the ``CachingArtifactStore``
composite implement it too, giving the scientist engine a single,
pluggable storage abstraction.

Only the *read/write/verify* surface is included.  Filesystem-specific
helpers (``root``, ``export_subgraph``, signing) are intentionally
excluded — they belong to separate, optional protocols if needed.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from polisyos.core.canon.canon_json import CanonSpec

    from ._integrity_ops import VerificationReport
    from .ids import ArtifactID
    from .manifest import ArtifactAuthorityInfo, ArtifactManifest, ArtifactRef
    from .signing import Ed25519Verifier, SignatureVerificationResult
    from .write_contract import ArtifactWriteOptions


AUTHORITY_ENVELOPE_ARTIFACT_KIND = "runtime_quality.evidence_authority_envelope"
AUTHORITY_ENVELOPE_SCHEMA_NAME = "runtime_quality.evidence_authority_envelope"
AUTHORITY_ENVELOPE_SCHEMA_VERSION = "1.0.0"


@runtime_checkable
class ArtifactStore(Protocol):
    """Minimal content-addressable store interface.

    Every method must be thread-safe.
    """

    # -- read ----------------------------------------------------------

    def has(self, artifact_id: ArtifactID | ArtifactRef) -> bool:  # pragma: no cover - protocol
        """Check availability for the default ID view or exact typed `ArtifactRef` view."""
        ...

    def get_bytes(
        self,
        artifact_id: ArtifactID | ArtifactRef,
    ) -> bytes:  # pragma: no cover - protocol
        """Return raw blob bytes for one artifact ID."""
        ...

    def get_manifest(
        self,
        artifact_id: ArtifactID | ArtifactRef,
    ) -> ArtifactManifest:  # pragma: no cover - protocol
        """Return the authorized default or exact typed-view manifest."""
        ...

    # -- write ---------------------------------------------------------

    def put_bytes(
        self,
        data: bytes,
        opts: ArtifactWriteOptions,
    ) -> ArtifactRef:  # pragma: no cover - protocol
        """Persist raw bytes and return the resulting content-addressed artifact reference."""
        ...

    def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:  # pragma: no cover - protocol
        """Canonicalize and persist a JSON payload as one artifact reference."""
        ...

    # -- integrity -----------------------------------------------------

    def verify(
        self,
        artifact_id: ArtifactID | ArtifactRef,
    ) -> VerificationReport:  # pragma: no cover - protocol
        """Return byte/manifest integrity status for one artifact."""
        ...

    # -- enumeration ---------------------------------------------------

    def iter_artifact_ids(self) -> list[ArtifactID]:  # pragma: no cover - protocol
        """List artifact IDs known to the backend."""
        ...


class ProfileAddressedManifestStore(Protocol):
    """Optional store capability for resolving a selected view without its kind."""

    def get_manifest_by_profile(
        self,
        artifact_id: ArtifactID | str,
        manifest_profile_sha256: str,
    ) -> ArtifactManifest:  # pragma: no cover - protocol
        """Resolve the manifest sidecar addressed by artifact ID and exact profile digest."""
        ...


def resolve_manifest_by_profile(
    store: ArtifactStore,
    artifact_id: ArtifactID | str,
    manifest_profile_sha256: str,
) -> ArtifactManifest:
    """Resolve and content-verify one selected manifest view from its lineage edge.

    ``InputRef`` carries the artifact ID and profile digest but not the selected
    manifest's kind or media type. Stores with the optional profile-addressed
    capability can resolve those fields from the exact sidecar. Older custom
    stores remain compatible only when the requested profile is their default;
    a non-default view fails closed when its sidecar cannot be addressed.
    """
    if (
        not isinstance(manifest_profile_sha256, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", manifest_profile_sha256) is None
    ):
        raise ValueError("manifest_profile_sha256 must be sha256:<64 lowercase hex>")

    from ._manifest_lifecycle import ManifestLifecycle
    from .ids import ArtifactID as RuntimeArtifactID
    from .manifest import ArtifactManifest as RuntimeArtifactManifest
    from .manifest import ArtifactRef as RuntimeArtifactRef

    aid = RuntimeArtifactID.model_validate(artifact_id)
    resolver = getattr(store, "get_manifest_by_profile", None)
    if callable(resolver):
        manifest = RuntimeArtifactManifest.model_validate(resolver(aid, manifest_profile_sha256))
    else:
        manifest = RuntimeArtifactManifest.model_validate(store.get_manifest(aid))
        if ManifestLifecycle.profile_sha256(manifest) != manifest_profile_sha256:
            raise TypeError(
                "Artifact store cannot resolve a non-default manifest profile by digest"
            )

    if manifest.artifact_id != aid:
        raise ValueError("selected manifest artifact ID does not match its lineage edge")
    if ManifestLifecycle.profile_sha256(manifest) != manifest_profile_sha256:
        raise ValueError("selected manifest profile digest does not match its lineage edge")
    selected_ref = RuntimeArtifactRef(
        artifact_id=aid,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=manifest_profile_sha256,
    )
    # The sidecar digest identifies metadata, not the blob's current bytes. Bind
    # the resolution to the actual CAS read before allowing it to reconstruct a ref.
    store.get_bytes(selected_ref)
    return manifest


def resolve_authority_envelope_ref(
    store: ArtifactStore,
    authority: ArtifactAuthorityInfo,
) -> ArtifactRef:
    """Resolve an authority envelope from its producer-persisted manifest link.

    A profile-bearing link resolves that exact manifest view. A profileless
    legacy link explicitly uses the store's default view.

    Args:
        store: Artifact store that owns the authority-linked envelope.
        authority: Authority link from the payload's persisted manifest.

    Returns:
        ArtifactRef: A typed ref for the selected authority-envelope view.

    Raises:
        ValueError: If the linked view is missing or has a different contract.
    """
    from .ids import ArtifactID as RuntimeArtifactID
    from .manifest import ArtifactAuthorityInfo as RuntimeArtifactAuthorityInfo
    from .manifest import ArtifactRef as RuntimeArtifactRef

    link = RuntimeArtifactAuthorityInfo.model_validate(authority)
    artifact_id = RuntimeArtifactID.model_validate(link.authority_envelope_ref)
    profile = link.authority_envelope_manifest_profile_sha256
    try:
        if profile is None:
            manifest = store.get_manifest(artifact_id)
        else:
            manifest = resolve_manifest_by_profile(store, artifact_id, profile)
    except (FileNotFoundError, TypeError, ValueError) as exc:
        raise ValueError("authority_envelope_manifest_resolution_failed") from exc

    schema = manifest.artifact_schema
    if (
        manifest.artifact_id != artifact_id
        or manifest.kind != AUTHORITY_ENVELOPE_ARTIFACT_KIND
        or manifest.media_type != "application/json"
        or schema is None
        or schema.name != AUTHORITY_ENVELOPE_SCHEMA_NAME
        or schema.version != AUTHORITY_ENVELOPE_SCHEMA_VERSION
    ):
        raise ValueError("authority_envelope_manifest_contract_mismatch")

    return RuntimeArtifactRef(
        artifact_id=artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=profile,
    )


class SignatureVerifyingArtifactStore(Protocol):
    """Optional signature verification bound to one composed artifact store.

    Implementations expose their exact guarded store handle so composition can
    reject a verifier that would read through a parallel or less-custodied path.
    This capability is intentionally separate from the backend-neutral
    ``ArtifactStore`` contract.
    """

    @property
    def guarded_store(self) -> ArtifactStore:  # pragma: no cover - protocol
        """Return the exact store whose reads are guarded by this verifier."""
        ...

    def verify_signature(
        self,
        artifact_id: ArtifactID,
        verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:  # pragma: no cover - protocol
        """Verify the signed snapshot for one normalized artifact ID."""
        ...


@runtime_checkable
class RootedArtifactStore(ArtifactStore, Protocol):
    """Artifact store that also exposes its backing root for local sidecars."""

    @property
    def root(self) -> Path:  # pragma: no cover - protocol
        """Return the configured backing root used by this store."""
        ...


@runtime_checkable
class AsyncArtifactStore(Protocol):
    """Async sibling contract for callers that already run inside an event loop."""

    async def has(
        self,
        artifact_id: ArtifactID | ArtifactRef,
    ) -> bool:  # pragma: no cover - protocol
        ...

    async def get_bytes(
        self,
        artifact_id: ArtifactID | ArtifactRef,
    ) -> bytes:  # pragma: no cover - protocol
        ...

    async def get_manifest(
        self,
        artifact_id: ArtifactID | ArtifactRef,
    ) -> ArtifactManifest:  # pragma: no cover - protocol
        ...

    async def put_bytes(
        self,
        data: bytes,
        opts: ArtifactWriteOptions,
    ) -> ArtifactRef:  # pragma: no cover - protocol
        ...

    async def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:  # pragma: no cover - protocol
        ...

    async def verify(
        self,
        artifact_id: ArtifactID | ArtifactRef,
    ) -> VerificationReport:  # pragma: no cover - protocol
        ...

    async def iter_artifact_ids(self) -> list[ArtifactID]:  # pragma: no cover - protocol
        ...
