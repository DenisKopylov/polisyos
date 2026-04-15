"""Tests for data-plane execution modes."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any


def _fake_evidence_ref() -> SimpleNamespace:
    return SimpleNamespace(artifact_id=SimpleNamespace(hex="evidence-ref"))


class _NoopSimulator:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    async def __aenter__(self) -> _NoopSimulator:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False


class _ReplayStoreStub:
    def __init__(self, store: object) -> None:
        self._store = store

    def save_record_session(self, session: object) -> SimpleNamespace:
        del session
        return SimpleNamespace(artifact_id=SimpleNamespace(hex="record-ref"))

    def load_record_session(self, artifact_id: object) -> object:
        del artifact_id
        return {"session": "replay"}

    def build_replay_fixture_dir(self, session: object, fixture_dir: object) -> None:
        del session, fixture_dir


def test_run_record_mode_uses_shared_blocking_bridge(
    monkeypatch,
    tmp_path,
) -> None:
    from polisyos.fabric.data_plane import modes as modes_mod

    blocking_calls: list[str] = []

    async def _fake_run_blocking_async(
        func: Any,
        /,
        *args: Any,
        timeout_seconds: float | None = None,
        **kwargs: Any,
    ) -> Any:
        del timeout_seconds
        blocking_calls.append(getattr(func, "__name__", type(func).__name__))
        return func(*args, **kwargs)

    def _fake_run_connectors_ingestion(**kwargs: Any) -> SimpleNamespace:
        del kwargs
        return _fake_evidence_ref()

    monkeypatch.setattr(modes_mod, "run_blocking_async", _fake_run_blocking_async)
    monkeypatch.setattr(
        "polisyos.fabric.ingestion.run_connectors_ingestion",
        _fake_run_connectors_ingestion,
    )
    monkeypatch.setattr(
        "polisyos.fabric.connectors.testing.simulator.APISimulator",
        _NoopSimulator,
    )
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.replay_store.make_record_session",
        lambda **kwargs: dict(kwargs),
    )
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.replay_store.ReplayStore",
        _ReplayStoreStub,
    )

    result, record_ref = modes_mod.run_record_mode(
        connector_manifest={
            "datasets": [
                {"connector_id": "test.integration_mock", "dataset_id": "events"},
            ],
        },
        source="test",
        license_name="MIT",
        cas_root=tmp_path / ".polisyos",
    )

    assert blocking_calls == ["_fake_run_connectors_ingestion"]
    assert result.mode_effective == "record"
    assert record_ref == "record-ref"


def test_run_replay_mode_uses_shared_blocking_bridge(
    monkeypatch,
    tmp_path,
) -> None:
    from polisyos.fabric.data_plane import modes as modes_mod

    blocking_calls: list[str] = []

    async def _fake_run_blocking_async(
        func: Any,
        /,
        *args: Any,
        timeout_seconds: float | None = None,
        **kwargs: Any,
    ) -> Any:
        del timeout_seconds
        blocking_calls.append(getattr(func, "__name__", type(func).__name__))
        return func(*args, **kwargs)

    def _fake_run_connectors_ingestion(**kwargs: Any) -> SimpleNamespace:
        del kwargs
        return _fake_evidence_ref()

    monkeypatch.setattr(modes_mod, "run_blocking_async", _fake_run_blocking_async)
    monkeypatch.setattr(
        "polisyos.fabric.ingestion.run_connectors_ingestion",
        _fake_run_connectors_ingestion,
    )
    monkeypatch.setattr(
        "polisyos.fabric.connectors.testing.simulator.APISimulator",
        _NoopSimulator,
    )
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.replay_store.ReplayStore",
        _ReplayStoreStub,
    )

    result = modes_mod.run_replay_mode(
        connector_manifest={
            "datasets": [
                {"connector_id": "test.integration_mock", "dataset_id": "events"},
            ],
        },
        source="test",
        license_name="MIT",
        cas_root=tmp_path / ".polisyos",
        replay_ref="sha256:" + ("0" * 64),
    )

    assert blocking_calls == ["_fake_run_connectors_ingestion"]
    assert result.mode_effective == "replay"


def test_run_streaming_windowed_legacy_path_uses_async_store_adapter(
    monkeypatch,
    tmp_path,
) -> None:
    from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
    from polisyos.fabric.data_plane import modes as modes_mod

    seen_kinds: list[str] = []
    original_put_json = AsyncArtifactStoreAdapter.put_json

    async def _tracked_put_json(self, obj: object, opts: Any, canon_spec: Any = None):
        seen_kinds.append(str(opts.kind))
        return await original_put_json(self, obj, opts, canon_spec=canon_spec)

    async def _fake_fetch_stream_for_dataset_async(**kwargs: Any) -> list[dict[str, Any]]:
        del kwargs
        return [
            {
                "chunk_index": 0,
                "row_count": 1,
                "is_first": True,
                "is_last": True,
                "data": [{"value": 1}],
            }
        ]

    monkeypatch.setattr(AsyncArtifactStoreAdapter, "put_json", _tracked_put_json)
    monkeypatch.setattr(modes_mod, "_connector_is_registered", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        modes_mod,
        "_fetch_stream_for_dataset_async",
        _fake_fetch_stream_for_dataset_async,
    )
    monkeypatch.setattr(modes_mod, "run_coro_sync", lambda coro: asyncio.run(coro))

    result = modes_mod.run_streaming_windowed(
        connector_manifest={
            "datasets": [
                {"connector_id": "legacy.stream", "dataset_id": "events"},
            ],
        },
        source="test",
        license_name="MIT",
        cas_root=tmp_path / ".polisyos",
        produce_snapshot=False,
    )

    assert result.mode_effective == "streaming_windowed"
    assert "fabric.stream_chunk" in seen_kinds


def test_run_streaming_windowed_persists_manifest_and_snapshot_via_async_store_adapter(
    monkeypatch,
    tmp_path,
) -> None:
    from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
    from polisyos.fabric.data_plane import modes as modes_mod

    seen_kinds: list[str] = []
    original_put_json = AsyncArtifactStoreAdapter.put_json

    async def _tracked_put_json(self, obj: object, opts: Any, canon_spec: Any = None):
        seen_kinds.append(str(opts.kind))
        return await original_put_json(self, obj, opts, canon_spec=canon_spec)

    async def _fake_fetch_stream_for_dataset_async(**kwargs: Any) -> list[dict[str, Any]]:
        del kwargs
        return [
            {
                "chunk_index": 0,
                "row_count": 1,
                "is_first": True,
                "is_last": True,
                "data": [{"value": 1}],
            }
        ]

    monkeypatch.setattr(AsyncArtifactStoreAdapter, "put_json", _tracked_put_json)
    monkeypatch.setattr(modes_mod, "_connector_is_registered", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        modes_mod,
        "_fetch_stream_for_dataset_async",
        _fake_fetch_stream_for_dataset_async,
    )
    monkeypatch.setattr(modes_mod, "run_coro_sync", lambda coro: asyncio.run(coro))

    result = modes_mod.run_streaming_windowed(
        connector_manifest={
            "datasets": [
                {"connector_id": "legacy.stream", "dataset_id": "events"},
            ],
        },
        source="test",
        license_name="MIT",
        cas_root=tmp_path / ".polisyos",
        produce_snapshot=True,
    )

    assert result.mode_effective == "streaming_windowed"
    assert "fabric.streaming_run_manifest" in seen_kinds
    assert "fabric.data_snapshot" in seen_kinds


def test_run_streaming_windowed_legacy_path_uses_async_fetch_helper(
    monkeypatch,
    tmp_path,
) -> None:
    from polisyos.fabric.data_plane import modes as modes_mod

    async_calls: list[tuple[str, str]] = []

    async def _fake_fetch_stream_for_dataset_async(**kwargs: Any) -> list[dict[str, Any]]:
        async_calls.append((kwargs["connector_id"], kwargs["dataset_id"]))
        return [
            {
                "chunk_index": 0,
                "row_count": 1,
                "is_first": True,
                "is_last": True,
                "data": [{"value": 1}],
            }
        ]

    monkeypatch.setattr(modes_mod, "_connector_is_registered", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        modes_mod,
        "_fetch_stream_for_dataset_async",
        _fake_fetch_stream_for_dataset_async,
    )
    monkeypatch.setattr(
        modes_mod,
        "_fetch_stream_for_dataset",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("legacy sync fetch helper should not run inside async path")
        ),
    )
    monkeypatch.setattr(modes_mod, "run_coro_sync", lambda coro: asyncio.run(coro))

    result = modes_mod.run_streaming_windowed(
        connector_manifest={
            "datasets": [
                {"connector_id": "legacy.stream", "dataset_id": "events"},
            ],
        },
        source="test",
        license_name="MIT",
        cas_root=tmp_path / ".polisyos",
        produce_snapshot=False,
    )

    assert result.mode_effective == "streaming_windowed"
    assert async_calls == [("legacy.stream", "events")]
