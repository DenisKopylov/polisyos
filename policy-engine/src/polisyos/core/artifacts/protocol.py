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

import inspect
import re
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, TypeGuard, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import PurePosixPath

    from polisyos.core.canon.canon_json import CanonSpec

    from ._integrity_ops import (
        ArtifactBoundedManifestRead,
        ArtifactStoreReadUsage,
        VerificationReport,
    )
    from .ids import ArtifactID
    from .manifest import ArtifactAuthorityInfo, ArtifactManifest, ArtifactRef, InputRef
    from .signing import Ed25519Verifier, SignatureVerificationResult
    from .store import ArtifactMemberReceipt
    from .write_contract import ArtifactWriteOptions


AUTHORITY_ENVELOPE_ARTIFACT_KIND = "runtime_quality.evidence_authority_envelope"
AUTHORITY_ENVELOPE_SCHEMA_NAME = "runtime_quality.evidence_authority_envelope"
AUTHORITY_ENVELOPE_SCHEMA_VERSION = "1.0.0"
_PROTOCOL_BASE_CLASS: object = Protocol


def _fallback_protocol_member_names(protocol: type[Any]) -> frozenset[str]:
    """Read stored Protocol member names on Python versions without the API."""
    names: set[str] = set()
    for owner in protocol.__mro__:
        if owner is _PROTOCOL_BASE_CLASS:
            break
        namespace = vars(owner)
        annotations = namespace.get("__annotations__", {})
        if isinstance(annotations, dict):
            names.update(
                name
                for name in annotations
                if isinstance(name, str) and _is_protocol_member_name(name)
            )
        names.update(
            name for name in namespace if isinstance(name, str) and _is_protocol_member_name(name)
        )
    return frozenset(names)


def _is_protocol_member_name(name: str) -> bool:
    """Exclude typing metadata while retaining declared private members."""
    return (
        not name.startswith("__")
        and not name.startswith("_abc_")
        and name
        not in {
            "_is_protocol",
            "_is_runtime_protocol",
        }
    )


def _protocol_member_names(protocol: type[Any]) -> frozenset[str]:
    """Use the stdlib's complete Protocol member set when it is available."""
    try:
        from typing import get_protocol_members
    except ImportError:
        return _fallback_protocol_member_names(protocol)
    try:
        return get_protocol_members(protocol)
    except TypeError:
        return frozenset()


def runtime_protocol_requirements(protocol: type[Any]) -> dict[str, bool]:
    """Derive callable and data requirements from all Protocol members.

    The standard-library member set includes inherited and annotation-only
    data fields, including deferred annotations. The Python 3.12 fallback reads
    stored annotation keys without evaluating their values. Effective member
    descriptors are resolved statically through the Protocol MRO.
    """
    if not any(owner is _PROTOCOL_BASE_CLASS for owner in protocol.__mro__):
        return {}
    if getattr(protocol, "_is_protocol", False) is not True:
        return {}

    requirements: dict[str, bool] = {}
    for name in _protocol_member_names(protocol):
        member = inspect.getattr_static(protocol, name, None)
        requirements[name] = isinstance(member, (classmethod, staticmethod)) or callable(member)
    return requirements


def matches_runtime_protocol_definition(value: object, protocol: object) -> bool:
    """Check a Protocol's declared surface without narrowing a static type.

    This companion accepts the Protocol class as an object so runtime clients
    can reuse the source-derived member check without MyPy's abstract-class
    argument restriction. Only actual Protocol classes with inherited
    requirements are admitted. It resolves each requirement on the exact
    handle, requires declared methods to be callable, and preserves operational
    exceptions from a present member. It never unwraps or substitutes a facade.

    This is structural presence only. Consumers still execute guarded
    operations and validate their results at the point of use.
    """
    if not isinstance(protocol, type):
        return False
    requirements = runtime_protocol_requirements(protocol)
    if not requirements:
        return False

    for name, must_be_callable in requirements.items():
        try:
            member = getattr(value, name)
        except AttributeError:
            return False
        if must_be_callable and not callable(member):
            return False
    return True


def matches_runtime_protocol[ProtocolT](
    value: object,
    protocol: type[ProtocolT],
) -> TypeGuard[ProtocolT]:
    """Check and statically narrow to one runtime Protocol surface."""
    return matches_runtime_protocol_definition(value, protocol)


@dataclass(frozen=True, slots=True)
class _CASStorageMember:
    """One content-bound final CAS file planned before publication."""

    relative_path: PurePosixPath
    sha256: str
    byte_size: int


class _CASStorageAdmission(Protocol):
    """Private tenant-wrapper hook for exact, batch storage quota admission."""

    def admit(self, members: Sequence[_CASStorageMember]) -> None:
        """Admit the complete set of new immutable CAS files before publication."""
        ...


def _validate_return_selected_profile(value: bool) -> bool:
    """Reject non-bool values for the selected-profile write option."""
    if type(value) is not bool:
        raise TypeError("return_selected_profile must be a bool")
    return value


def _require_return_selected_profile_writer(store: object, method_name: str) -> None:
    """Preflight the writer signature for the selected-profile keyword.

    This checks that the named method accepts an explicit keyword parameter. It
    does not verify that a write honored the option or returned a selected view.
    Callers must inspect and validate the result from the actual write.
    """
    method = getattr(store, method_name, None)
    if not callable(method):
        raise NotImplementedError("artifact_store_return_selected_profile_unsupported")
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError) as exc:
        raise NotImplementedError("artifact_store_return_selected_profile_unsupported") from exc
    parameter = signature.parameters.get("return_selected_profile")
    if parameter is None or parameter.kind not in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    ):
        raise NotImplementedError("artifact_store_return_selected_profile_unsupported")


# Public package-facade aliases preserve one implementation for current callers.
validate_return_selected_profile = _validate_return_selected_profile
require_return_selected_profile_writer = _require_return_selected_profile_writer


@runtime_checkable
class RawManifestBytesReader(Protocol):
    """Optional capability for reading the selected raw manifest sidecar safely."""

    def get_raw_manifest_bytes(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        *,
        manifest_profile_sha256: str | None = None,
    ) -> bytes: ...


@runtime_checkable
class AsyncRawManifestBytesReader(Protocol):
    """Optional async capability for exact selected sidecar bytes."""

    async def get_raw_manifest_bytes(
        self,
        artifact_id: ArtifactID | ArtifactRef,
        *,
        manifest_profile_sha256: str | None = None,
    ) -> bytes: ...


@runtime_checkable
class ArtifactReader(Protocol):
    """Typed read-only view of one content-addressed artifact store."""

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


@runtime_checkable
class VerifiableArtifactReader(ArtifactReader, Protocol):
    """Offer read operations and integrity verification without writer methods.

    This is a capability contract, not a claim that a read is already verified.
    Consumers still invoke verification and their exact selected-profile checks.
    """

    def verify(self, artifact_id: ArtifactID | ArtifactRef) -> VerificationReport: ...


@runtime_checkable
class ArtifactStore(ArtifactReader, Protocol):
    """Read/write content-addressable store interface.

    Every method must be thread-safe.
    """

    # -- write ---------------------------------------------------------

    def put_bytes(
        self,
        data: bytes,
        opts: ArtifactWriteOptions,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:  # pragma: no cover - protocol
        """Persist bytes, optionally returning the exact profile selected by this write."""
        ...

    def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:  # pragma: no cover - protocol
        """Persist Core JSON after declared-profile byte conformance succeeds.

        Implementations must decode and re-encode the emitted bytes with the
        selected Core profile before backend mutation. The return flag controls
        only the selector returned to the caller; it never disables this check.
        """
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


@runtime_checkable
class CoreJSONArtifactProfileReader(ArtifactReader, RawManifestBytesReader, Protocol):
    """Read-only profile-aware Core artifact view used by strict JSON readers.

    This composes the existing read and exact-raw-manifest contracts without
    adding write requirements to a reader.
    """


@runtime_checkable
class CoreJSONArtifactStore(ArtifactStore, CoreJSONArtifactProfileReader, Protocol):
    """Store with the raw-manifest capability required for semantic Core JSON reads.

    ``ArtifactStore`` remains the minimal producer and storage contract. Readers
    that admit Core JSON against its declared canonical profile require this
    stronger boundary so they can inspect the exact persisted manifest bytes
    before reading or validating the payload. Existing structural members are
    unchanged; this protocol composes the profile-read contract with writes.
    """


class CoreJSONArtifactMemberStream(Protocol):
    """Minimal read surface consumed from one owner-held Core artifact member."""

    def read(self, size: int = -1) -> bytes: ...


@runtime_checkable
class CoreJSONArtifactBoundedMemberStream(CoreJSONArtifactMemberStream, Protocol):
    """Owner-measured selected blob stream whose reads and full receipt are bounded."""

    @property
    def member_size_bytes(self) -> int:
        """Return the exact regular-file size checked against the selected manifest."""
        ...

    @property
    def observed_manifest_verification_bytes(self) -> int:
        """Return exact selected-manifest bytes transferred during owner verification."""
        ...

    @property
    def observed_payload_bytes(self) -> int:
        """Return exact payload bytes returned to the bounded reader so far."""
        ...

    @property
    def payload_integrity_verified(self) -> bool:
        """Return whether full member size and digest verification has completed."""
        ...

    @property
    def receipt(self) -> ArtifactMemberReceipt:
        """Return the full content receipt, available only after verified EOF."""
        ...


@runtime_checkable
class CoreJSONArtifactBoundedManifestReader(Protocol):
    """Read one exact profile-qualified raw manifest under a caller byte limit.

    Implementations inspect actual regular-file size before allocating the sidecar
    and raise ``ArtifactReadBoundsError`` with the observed size when it exceeds
    the selected limit.
    """

    def get_raw_manifest_bytes_bounded(
        self,
        artifact_id: ArtifactID | ArtifactRef,
        *,
        max_manifest_bytes: int,
        manifest_profile_sha256: str | None = None,
    ) -> bytes:
        """Read the default or exact manifest under a pre-allocation byte limit."""
        ...


@runtime_checkable
class CoreJSONArtifactBoundedInputManifestReader(Protocol):
    """Read a bounded selected manifest from an ID and explicit profile edge.

    ``InputRef`` intentionally does not carry kind or media type. The Core
    owner resolves those fields from the exact bounded manifest bytes; callers
    must validate any role-specific expectations against the returned ref.
    """

    def get_raw_manifest_bytes_bounded_for_input(
        self,
        input_ref: InputRef,
        *,
        max_manifest_bytes: int,
    ) -> bytes:
        """Read the exact profile-qualified manifest selected by one input edge."""
        ...


@runtime_checkable
class CoreJSONArtifactBoundedManifestReceiptReader(Protocol):
    """Additive exact-usage companion to legacy bytes-only bounded manifest reads."""

    def read_raw_manifest_bytes_bounded(
        self,
        artifact_id: ArtifactID | ArtifactRef,
        *,
        max_manifest_bytes: int,
        manifest_profile_sha256: str | None = None,
    ) -> ArtifactBoundedManifestRead:
        """Read the default or exact manifest with owner-measured transfers.

        An ArtifactID without a profile explicitly selects its default view. Supplying a
        profile selects that exact sidecar without first resolving or falling back to the
        default. ArtifactRef continues to mean its exact full selected view.
        """
        ...


@runtime_checkable
class CoreJSONArtifactBoundedInputManifestReceiptReader(Protocol):
    """Owner-measured bounded manifest reads selected by one explicit input edge."""

    def read_raw_manifest_bytes_bounded_for_input(
        self,
        input_ref: InputRef,
        *,
        max_manifest_bytes: int,
    ) -> ArtifactBoundedManifestRead:
        """Read one exact input-selected sidecar with an immutable owner receipt."""
        ...


@runtime_checkable
class CoreJSONArtifactStreamingReader(
    CoreJSONArtifactProfileReader,
    CoreJSONArtifactBoundedManifestReader,
    Protocol,
):
    """Profile-aware read-only view with bounded metadata and selected blob stream."""

    def open_member(
        self,
        artifact_id: ArtifactID | ArtifactRef,
        member: Literal["blob"],
        *,
        max_manifest_bytes: int | None = None,
        expected_manifest_sha256: str | None = None,
    ) -> AbstractContextManager[CoreJSONArtifactMemberStream]:
        """Open the blob after checking its bounded manifest against an optional exact hash.

        When supplied, the manifest limit is enforced before typed parsing. The
        expected digest must match the exact manifest bytes observed at open time
        before the selected blob stream becomes available.
        """
        ...


@runtime_checkable
class CoreJSONArtifactBoundedMemberReader(
    CoreJSONArtifactStreamingReader,
    CoreJSONArtifactBoundedManifestReceiptReader,
    Protocol,
):
    """Add a no-drain owner seam for strict bounded selected blob reads."""

    def open_member_bounded(
        self,
        artifact_id: ArtifactRef,
        member: Literal["blob"],
        *,
        max_manifest_bytes: int,
        expected_manifest_sha256: str,
        max_member_bytes: int,
    ) -> CoreJSONArtifactBoundedMemberAttempt:
        """Open only a size-known selected blob under an exact manifest/profile check.

        The owner refuses an over-cap regular-file size before returning payload
        bytes. It exposes exact selected-store transfer counts and closes without
        draining when the caller aborts the context.
        """
        ...


@runtime_checkable
class CoreJSONArtifactBoundedMemberAttempt(
    AbstractContextManager[CoreJSONArtifactBoundedMemberStream], Protocol
):
    """Bounded member context whose exact usage receipt exists before entry."""

    @property
    def usage(self) -> ArtifactStoreReadUsage:
        """Return owner-measured transfers or explicit unknown phase counts."""
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
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:  # pragma: no cover - protocol
        ...

    async def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:  # pragma: no cover - protocol
        ...

    async def verify(
        self,
        artifact_id: ArtifactID | ArtifactRef,
    ) -> VerificationReport:  # pragma: no cover - protocol
        ...

    async def iter_artifact_ids(
        self,
    ) -> list[ArtifactID]:  # pragma: no cover - protocol
        ...
