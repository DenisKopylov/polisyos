from __future__ import annotations

import time

import pytest

from polisyos.common.async_tools import run_coro_sync
from polisyos.core.artifacts.async_store import (
    AsyncArtifactStoreAdapter,
    ensure_async_artifact_store,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions


def test_async_artifact_store_round_trip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    adapter = AsyncArtifactStoreAdapter(store)

    async def _exercise():
        ref = await adapter.put_json(
            {"hello": "world"},
            ArtifactWriteOptions(
                kind="test.async_payload",
                media_type="application/json",
                schema=SchemaInfo(name="test.AsyncPayload", version="1.0"),
            ),
        )
        manifest = await adapter.get_manifest(ref.artifact_id)
        payload = await adapter.get_bytes(ref.artifact_id)
        report = await adapter.verify(ref.artifact_id)
        artifact_ids = await adapter.iter_artifact_ids()
        return ref, manifest, payload, report, artifact_ids

    ref, manifest, payload, report, artifact_ids = run_coro_sync(_exercise())

    assert manifest.kind == "test.async_payload"
    assert payload
    assert report.ok is True
    assert ref.artifact_id in artifact_ids


def test_async_artifact_store_times_out_on_slow_backend() -> None:
    class _SlowStore:
        def get_bytes(self, artifact_id):
            del artifact_id
            time.sleep(1.0)
            return b"never"

    adapter = AsyncArtifactStoreAdapter(_SlowStore(), timeout_seconds=0.05)
    artifact_id = ArtifactID.model_validate("sha256:" + ("0" * 64))

    async def _exercise() -> bytes:
        return await adapter.get_bytes(artifact_id)

    with pytest.raises(TimeoutError, match="Blocking call did not complete within"):
        run_coro_sync(_exercise())


def test_ensure_async_artifact_store_reuses_existing_async_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    adapter = AsyncArtifactStoreAdapter(store)

    assert ensure_async_artifact_store(adapter) is adapter
