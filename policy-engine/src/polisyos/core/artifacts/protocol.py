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

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from polisyos.core.canon.canon_json import CanonSpec

from .ids import ArtifactID
from .manifest import ArtifactManifest, ArtifactRef
from .store import PutOptions, VerificationReport


@runtime_checkable
class ArtifactStore(Protocol):
    """Minimal content-addressable store interface.

    Every method must be thread-safe.
    """

    # -- read ----------------------------------------------------------

    def has(self, artifact_id: ArtifactID) -> bool:  # pragma: no cover - protocol
        ...

    def get_bytes(self, artifact_id: ArtifactID) -> bytes:  # pragma: no cover - protocol
        ...

    def get_manifest(self, artifact_id: ArtifactID) -> ArtifactManifest:  # pragma: no cover - protocol
        ...

    # -- write ---------------------------------------------------------

    def put_bytes(self, data: bytes, opts: PutOptions) -> ArtifactRef:  # pragma: no cover - protocol
        ...

    def put_json(
        self,
        obj: Any,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:  # pragma: no cover - protocol
        ...

    # -- integrity -----------------------------------------------------

    def verify(self, artifact_id: ArtifactID) -> VerificationReport:  # pragma: no cover - protocol
        ...

    # -- enumeration ---------------------------------------------------

    def iter_artifact_ids(self) -> list[ArtifactID]:  # pragma: no cover - protocol
        ...
