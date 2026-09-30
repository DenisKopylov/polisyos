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

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from polisyos.core.canon.canon_json import CanonSpec

    from ._integrity_ops import VerificationReport
    from .ids import ArtifactID
    from .manifest import ArtifactManifest, ArtifactRef
    from .write_contract import ArtifactWriteOptions


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
