"""Write-through caching store: local FileSystemCAS + remote ArtifactStore."""

from __future__ import annotations

from typing import Any

from polisyos.core.canon.canon_json import CanonSpec

from ..ids import ArtifactID
from ..manifest import ArtifactManifest, ArtifactRef
from ..protocol import ArtifactStore
from ..store import PutOptions, VerificationReport


class CachingArtifactStore:
    """Composes a local CAS (fast) with a remote store (durable).

    * **Reads**: try local first, fall back to remote (download to local on miss).
    * **Writes**: write to local, then replicate to remote (if ``write_through``).
    * **Verify**: delegates to local if present, otherwise remote.
    """

    def __init__(
        self,
        *,
        remote: ArtifactStore,
        local: ArtifactStore,
        write_through: bool = True,
    ) -> None:
        self._remote = remote
        self._local = local
        self._write_through = write_through

    # -- ArtifactStore protocol ----------------------------------------

    def has(self, artifact_id: ArtifactID) -> bool:
        if self._local.has(artifact_id):
            return True
        return self._remote.has(artifact_id)

    def get_bytes(self, artifact_id: ArtifactID) -> bytes:
        try:
            return self._local.get_bytes(artifact_id)
        except (FileNotFoundError, OSError, KeyError):
            pass
        data = self._remote.get_bytes(artifact_id)
        # Cache locally for subsequent reads.  We need the original
        # ``PutOptions`` to write to the local store, but since CAS is
        # content-addressed the manifest already exists remotely.
        # Write raw blob + manifest via the local store's put_bytes with
        # a generic kind — the manifest will be overwritten below.
        try:
            manifest = self._remote.get_manifest(artifact_id)
            opts = PutOptions(kind=manifest.kind, media_type=manifest.media_type)
            self._local.put_bytes(data, opts)
        except Exception:  # noqa: BLE001 — best-effort cache population
            pass
        return data

    def get_manifest(self, artifact_id: ArtifactID) -> ArtifactManifest:
        try:
            return self._local.get_manifest(artifact_id)
        except (FileNotFoundError, OSError, KeyError):
            pass
        return self._remote.get_manifest(artifact_id)

    def put_bytes(self, data: bytes, opts: PutOptions) -> ArtifactRef:
        ref = self._local.put_bytes(data, opts)
        if self._write_through:
            self._remote.put_bytes(data, opts)
        return ref

    def put_json(
        self,
        obj: Any,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:
        ref = self._local.put_json(obj, opts, canon_spec)
        if self._write_through:
            self._remote.put_json(obj, opts, canon_spec)
        return ref

    def verify(self, artifact_id: ArtifactID) -> VerificationReport:
        if self._local.has(artifact_id):
            return self._local.verify(artifact_id)
        return self._remote.verify(artifact_id)

    def iter_artifact_ids(self) -> list[ArtifactID]:
        local_ids = set(self._local.iter_artifact_ids())
        remote_ids = set(self._remote.iter_artifact_ids())
        return sorted(local_ids | remote_ids, key=lambda a: a.hex)
