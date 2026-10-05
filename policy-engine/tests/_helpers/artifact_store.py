from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactManifest,
    ArtifactRef,
    ArtifactStore,
    FileSystemCAS,
    VerificationReport,
)
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.security import (
    AccessScope,
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)


class RecordingArtifactStore:
    """Observe the exact protocol instance used by one artifact owner."""

    def __init__(self, delegate: ArtifactStore) -> None:
        if not isinstance(delegate, ArtifactStore):
            raise TypeError("artifact_store_protocol_required")
        self._delegate = delegate
        self.written_ids: set[str] = set()
        self.byte_read_ids: set[str] = set()
        self.manifest_read_ids: set[str] = set()
        self.path_lookups: dict[str, tuple[Path, Path]] = {}

    @staticmethod
    def _key(artifact_id: ArtifactID | ArtifactRef | str) -> str:
        return str(artifact_id.artifact_id) if isinstance(artifact_id, ArtifactRef) else str(artifact_id)

    def has(self, artifact_id: ArtifactID | ArtifactRef) -> bool:
        return self._delegate.has(artifact_id)

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef) -> bytes:
        self.byte_read_ids.add(self._key(artifact_id))
        return self._delegate.get_bytes(artifact_id)

    def get_manifest(self, artifact_id: ArtifactID | ArtifactRef) -> ArtifactManifest:
        self.manifest_read_ids.add(self._key(artifact_id))
        return self._delegate.get_manifest(artifact_id)

    def get_paths(self, artifact_id: ArtifactID | ArtifactRef | str) -> tuple[Path, Path]:
        """Forward Foundry's optional local-CAS layout probe and record its path."""

        paths = self._delegate.get_paths(artifact_id)  # type: ignore[attr-defined]
        self.path_lookups[self._key(artifact_id)] = paths
        return paths

    def put_bytes(self, data: bytes, opts: ArtifactWriteOptions) -> ArtifactRef:
        ref = self._delegate.put_bytes(data, opts)
        self.written_ids.add(self._key(ref))
        return ref

    def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:
        ref = self._delegate.put_json(obj, opts, canon_spec=canon_spec)
        self.written_ids.add(self._key(ref))
        return ref

    def verify(self, artifact_id: ArtifactID | ArtifactRef) -> VerificationReport:
        return self._delegate.verify(artifact_id)

    def iter_artifact_ids(self) -> list[ArtifactID]:
        return self._delegate.iter_artifact_ids()


@contextmanager
def authenticated_tenant_scope(*, tenant_id: str, cell_id: str) -> Iterator[None]:
    """Install authenticated tenant identity for guarded store operations."""

    access_scope = AccessScope.for_service(
        tenant_id=tenant_id,
        cell_id=cell_id,
        spiffe_id="spiffe://tests/policyos/n3-store-witness",
    )
    token = set_current_access_scope(access_scope)
    try:
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            yield
    finally:
        reset_current_access_scope(token)


__all__ = ["RecordingArtifactStore", "authenticated_tenant_scope"]
