"""Async adapter layer for the backend-agnostic artifact store protocol."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeGuard, cast

from polisyos.common.async_tools import run_blocking_async

from .protocol import ArtifactStore, AsyncArtifactStore

if TYPE_CHECKING:
    from polisyos.core.canon.canon_json import CanonSpec

    from ._integrity_ops import VerificationReport
    from .backends.config import ArtifactStoreConfig
    from .ids import ArtifactID
    from .manifest import ArtifactManifest, ArtifactRef
    from .write_contract import ArtifactWriteOptions


def is_async_artifact_store(store: object) -> TypeGuard[AsyncArtifactStore]:
    """Return whether *store* exposes the async CAS contract at runtime."""

    candidate = getattr(store, "put_json", None)
    return inspect.iscoroutinefunction(candidate)


@dataclass(frozen=True, slots=True)
class AsyncArtifactStoreAdapter:
    """Wrap a sync ``ArtifactStore`` with shared-executor async methods."""

    store: ArtifactStore
    timeout_seconds: float | None = None

    async def has(self, artifact_id: ArtifactID) -> bool:
        return cast(
            "bool",
            await run_blocking_async(
                self.store.has,
                artifact_id,
                timeout_seconds=self.timeout_seconds,
            ),
        )

    async def get_bytes(self, artifact_id: ArtifactID) -> bytes:
        return cast(
            "bytes",
            await run_blocking_async(
                self.store.get_bytes,
                artifact_id,
                timeout_seconds=self.timeout_seconds,
            ),
        )

    async def get_manifest(self, artifact_id: ArtifactID) -> ArtifactManifest:
        return await run_blocking_async(
            self.store.get_manifest,
            artifact_id,
            timeout_seconds=self.timeout_seconds,
        )

    async def put_bytes(
        self,
        data: bytes,
        opts: ArtifactWriteOptions,
    ) -> ArtifactRef:
        return await run_blocking_async(
            self.store.put_bytes,
            data,
            opts,
            timeout_seconds=self.timeout_seconds,
        )

    async def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:
        return await run_blocking_async(
            self.store.put_json,
            obj,
            opts,
            canon_spec=canon_spec,
            timeout_seconds=self.timeout_seconds,
        )

    async def verify(self, artifact_id: ArtifactID) -> VerificationReport:
        return await run_blocking_async(
            self.store.verify,
            artifact_id,
            timeout_seconds=self.timeout_seconds,
        )

    async def iter_artifact_ids(self) -> list[ArtifactID]:
        return cast(
            "list[ArtifactID]",
            await run_blocking_async(
                self.store.iter_artifact_ids,
                timeout_seconds=self.timeout_seconds,
            ),
        )

    def artifact_store_config(self) -> ArtifactStoreConfig | None:
        from .backends.config import infer_artifact_store_config

        return infer_artifact_store_config(self.store)


@dataclass(frozen=True, slots=True)
class AsyncFileSystemArtifactStore:
    """First-class async facade for filesystem-backed CAS hot paths."""

    store: ArtifactStore
    timeout_seconds: float | None = None

    async def has(self, artifact_id: ArtifactID) -> bool:
        return cast(
            "bool",
            await run_blocking_async(
                self.store.has,
                artifact_id,
                timeout_seconds=self.timeout_seconds,
            ),
        )

    async def get_bytes(self, artifact_id: ArtifactID) -> bytes:
        return cast(
            "bytes",
            await run_blocking_async(
                self.store.get_bytes,
                artifact_id,
                timeout_seconds=self.timeout_seconds,
            ),
        )

    async def get_manifest(self, artifact_id: ArtifactID) -> ArtifactManifest:
        return await run_blocking_async(
            self.store.get_manifest,
            artifact_id,
            timeout_seconds=self.timeout_seconds,
        )

    async def put_bytes(
        self,
        data: bytes,
        opts: ArtifactWriteOptions,
    ) -> ArtifactRef:
        return await run_blocking_async(
            self.store.put_bytes,
            data,
            opts,
            timeout_seconds=self.timeout_seconds,
        )

    async def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:
        return await run_blocking_async(
            self.store.put_json,
            obj,
            opts,
            canon_spec=canon_spec,
            timeout_seconds=self.timeout_seconds,
        )

    async def verify(self, artifact_id: ArtifactID) -> VerificationReport:
        return await run_blocking_async(
            self.store.verify,
            artifact_id,
            timeout_seconds=self.timeout_seconds,
        )

    async def iter_artifact_ids(self) -> list[ArtifactID]:
        return cast(
            "list[ArtifactID]",
            await run_blocking_async(
                self.store.iter_artifact_ids,
                timeout_seconds=self.timeout_seconds,
            ),
        )

    def artifact_store_config(self) -> ArtifactStoreConfig | None:
        from .backends.config import infer_artifact_store_config

        return infer_artifact_store_config(self.store)


def ensure_async_artifact_store(
    store: ArtifactStore | AsyncArtifactStore,
    *,
    timeout_seconds: float | None = None,
) -> AsyncArtifactStore:
    """Return an async CAS contract, preserving native async stores when already available."""
    if is_async_artifact_store(store):
        return store
    return AsyncArtifactStoreAdapter(
        cast("ArtifactStore", store),
        timeout_seconds=timeout_seconds,
    )


__all__ = [
    "AsyncArtifactStoreAdapter",
    "AsyncFileSystemArtifactStore",
    "ensure_async_artifact_store",
    "is_async_artifact_store",
]
