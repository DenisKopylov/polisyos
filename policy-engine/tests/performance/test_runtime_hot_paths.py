from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fixtures.runtime_http import build_runtime_api_env

from polisyos.common.async_tools import run_blocking_async, run_coro_sync
from polisyos.core.artifacts.async_store import (
    AsyncArtifactStoreAdapter,
    ensure_async_artifact_store,
)
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.contracts.cursor import (
    CursorState,
    StreamCheckpoint,
    StreamLifecycleState,
    WatermarkType,
)
from polisyos.core.contracts.fabric import EvidenceBundle, EvidenceBundleRef
from polisyos.fabric.connectors.base import (
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
)
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.cursor_store import AsyncCursorStoreAdapter, CursorStore
from polisyos.fabric.data_plane.modes import run_streaming_windowed
from polisyos.fabric.data_plane.orchestrator import (
    IngestionResult,
    build_partitioned_ingestion_plan,
    run_orchestrated_ingestion,
    run_partitioned_ingestion,
)
from polisyos.fabric.data_plane.streaming import StreamRuntimeOptions, process_stream_dataset
from polisyos.ir.connectors import DataVersion, VersionStrategy

_INGESTION_VERSION = DataVersion(
    strategy=VersionStrategy.TIMESTAMP,
    value="2024-07-01T00:00:00+00:00",
    timestamp=datetime(2024, 7, 1, 0, 0, 0, tzinfo=UTC),
)


class _PerfIngestionConnector:
    def __init__(self) -> None:
        self.metadata = type(
            "_PerfConnectorMetadata",
            (),
            {
                "data_classification": "public",
                "column_classification": {},
            },
        )()

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return ConnectionHandle(
            connector_id="test.integration_perf",
            config=config,
        )

    async def disconnect(self, handle: ConnectionHandle) -> None:
        del handle

    async def health_check(self, handle: ConnectionHandle) -> None:
        del handle

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[list[dict[str, object]]]:
        del handle
        step = next(
            (next(iter(values), "0") for field, values in request.filters if field == "step"),
            "0",
        )
        rows = [
            {"event_id": f"evt-{step}-0", "metric": 1.0},
            {"event_id": f"evt-{step}-1", "metric": 2.0},
        ]
        return FetchResult(
            data=rows,
            row_count=len(rows),
            schema_id="test.integration_perf.events",
            schema_version="1.0.0",
            version=_INGESTION_VERSION,
            fetched_at=datetime(2024, 7, 1, 0, 0, 0, tzinfo=UTC),
            completeness=1.0,
            quality_flags=frozenset(),
        )


class _PerfRegistryEntry:
    def __init__(self) -> None:
        self.default_config = ConnectionConfig(url="http://localhost:9999/mock")


class _PerfRegistry:
    def __init__(self) -> None:
        self._connector = _PerfIngestionConnector()
        self._entry = _PerfRegistryEntry()

    def get(self, connector_id: str) -> _PerfIngestionConnector:
        del connector_id
        return self._connector

    def get_entry(self, connector_id: str) -> _PerfRegistryEntry:
        del connector_id
        return self._entry

    async def get_connection(
        self,
        connector_id: str,
        config: ConnectionConfig,
    ) -> ConnectionHandle:
        return ConnectionHandle(connector_id=connector_id, config=config)

    async def release_connection(
        self,
        connector_id: str,
        handle: ConnectionHandle,
    ) -> None:
        del connector_id, handle


class _PerfSpan:
    def __enter__(self) -> _PerfSpan:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False

    def set_attribute(self, key: str, value: object) -> None:
        del key, value


class _PerfTracer:
    def start_as_current_span(self, name: str, attributes=None):
        del name, attributes
        return _PerfSpan()


class _PerfMetrics:
    def record_fabric_lineage_graph(self, **kwargs: object) -> None:
        del kwargs


@pytest.mark.performance
@pytest.mark.benchmark
def test_run_index_refresh_hot_path(benchmark, tmp_path) -> None:
    env = build_runtime_api_env(tmp_path, include_test_client=False)
    run_index = env["app"].state.runtime_api_ctx.run_index

    benchmark(lambda: run_index.refresh(force=True))


@pytest.mark.performance
@pytest.mark.benchmark
def test_run_index_list_runs_hot_path(benchmark, tmp_path) -> None:
    env = build_runtime_api_env(tmp_path, include_test_client=False)
    run_index = env["app"].state.runtime_api_ctx.run_index
    run_index.refresh(force=True)

    benchmark(lambda: run_index.list_runs(limit=50, tenant_id=env["tenant_a"]))


@pytest.mark.performance
@pytest.mark.benchmark
def test_run_index_incremental_refresh_cycle_hot_path(benchmark, tmp_path) -> None:
    env = build_runtime_api_env(tmp_path, include_test_client=False)
    run_index = env["app"].state.runtime_api_ctx.run_index
    run_index.refresh(force=True)
    trace_path = run_index.get_run(env["core_run_id"]).run_dir / "trace.jsonl"
    original_bytes = trace_path.read_bytes()

    def _exercise_incremental_cycle() -> int:
        trace_path.write_bytes(original_bytes)
        os.utime(trace_path, None)
        run_index.refresh(force=True)
        return len(run_index.list_runs(limit=50, tenant_id=env["tenant_a"])[0])

    assert benchmark(_exercise_incremental_cycle) >= 1


@pytest.mark.performance
def test_run_index_incremental_refresh_soak_smoke(tmp_path) -> None:
    env = build_runtime_api_env(tmp_path, include_test_client=False)
    run_index = env["app"].state.runtime_api_ctx.run_index
    run_index.refresh(force=True)
    trace_path = run_index.get_run(env["core_run_id"]).run_dir / "trace.jsonl"
    original_bytes = trace_path.read_bytes()

    for _ in range(48):
        trace_path.write_bytes(original_bytes)
        os.utime(trace_path, None)
        run_index.refresh(force=True)
        runs = run_index.list_runs(limit=50, tenant_id=env["tenant_a"])
        assert runs
        assert runs[0][0].run_id == env["core_run_id"]


@pytest.mark.performance
@pytest.mark.benchmark
def test_timeline_build_hot_path(benchmark, tmp_path) -> None:
    env = build_runtime_api_env(tmp_path, include_test_client=False)
    ctx = env["app"].state.runtime_api_ctx
    run = ctx.run_index.get_run(env["core_run_id"])

    benchmark(lambda: ctx.timeline.build_for_run(run))


@pytest.mark.performance
@pytest.mark.benchmark
def test_lineage_build_hot_path(benchmark, tmp_path) -> None:
    env = build_runtime_api_env(tmp_path, include_test_client=False)
    ctx = env["app"].state.runtime_api_ctx
    run = ctx.run_index.get_run(env["core_run_id"])
    root_ids = ctx.run_index.resolve_root_artifact_ids(run)

    benchmark(lambda: ctx.lineage.build_for_artifact_ids(root_ids))


@pytest.mark.performance
@pytest.mark.benchmark
def test_async_artifact_store_round_trip_hot_path(benchmark, tmp_path) -> None:
    env = build_runtime_api_env(tmp_path, include_test_client=False)
    async_store = env["app"].state.runtime_api_ctx.async_store

    def _exercise() -> bytes:
        async def _round_trip() -> bytes:
            ref = await async_store.put_json(
                {"payload": "async-hot-path"},
                ArtifactWriteOptions(
                    kind="test.async_hot_path",
                    media_type="application/json",
                    schema=SchemaInfo(name="test.AsyncHotPath", version="1.0"),
                ),
            )
            return await async_store.get_bytes(ref.artifact_id)

        return run_coro_sync(_round_trip())

    assert benchmark(_exercise)


@pytest.mark.performance
def test_async_artifact_store_repeated_round_trip_soak_smoke(tmp_path) -> None:
    env = build_runtime_api_env(tmp_path, include_test_client=False)
    async_store = env["app"].state.runtime_api_ctx.async_store

    async def _round_trip(index: int) -> bytes:
        ref = await async_store.put_json(
            {"payload": f"async-soak-{index}"},
            ArtifactWriteOptions(
                kind="test.async_soak_path",
                media_type="application/json",
                schema=SchemaInfo(name="test.AsyncSoakPath", version="1.0"),
            ),
        )
        return await async_store.get_bytes(ref.artifact_id)

    for index in range(48):
        payload = run_coro_sync(_round_trip(index))
        assert payload


@pytest.mark.performance
def test_async_artifact_store_concurrent_round_trip_soak_smoke(tmp_path) -> None:
    env = build_runtime_api_env(tmp_path, include_test_client=False)
    async_store = ensure_async_artifact_store(
        env["app"].state.runtime_api_ctx.async_store,
        timeout_seconds=3.0,
    )

    async def _round_trip(index: int) -> bytes:
        ref = await async_store.put_json(
            {"payload": f"async-concurrent-{index}"},
            ArtifactWriteOptions(
                kind="test.async_concurrent_path",
                media_type="application/json",
                schema=SchemaInfo(name="test.AsyncConcurrentPath", version="1.0"),
            ),
        )
        return await async_store.get_bytes(ref.artifact_id)

    async def _exercise() -> list[bytes]:
        payloads: list[bytes] = []
        for batch in range(4):
            payloads.extend(
                await asyncio.gather(*(_round_trip(batch * 4 + item) for item in range(4)))
            )
        return payloads

    payloads = run_coro_sync(_exercise())
    assert len(payloads) == 16
    assert all(payloads)


@pytest.mark.performance
def test_async_connector_ingestion_round_trip_soak_smoke(tmp_path) -> None:
    from polisyos.fabric.ingestion import (
        ConnectorManifestSpec,
        DatasetFetchSpec,
        IngestionDependencies,
        run_connectors_ingestion,
    )

    cas_root = tmp_path / ".polisyos"
    async_store = AsyncArtifactStoreAdapter(
        FileSystemCAS(cas_root),
        timeout_seconds=3.0,
    )
    dependencies = IngestionDependencies(
        registry=_PerfRegistry(),  # type: ignore[arg-type]
        tracer=_PerfTracer(),  # type: ignore[arg-type]
        metrics=_PerfMetrics(),  # type: ignore[arg-type]
        store_factory=lambda root: FileSystemCAS(root),
    )

    async def _exercise() -> list[bytes]:
        payloads: list[bytes] = []
        for index in range(16):
            manifest = ConnectorManifestSpec(
                datasets=[
                    DatasetFetchSpec(
                        connector_id="test.integration_perf",
                        dataset_id="events",
                        filters={"step": [str(index)]},
                    )
                ]
            )
            evidence_ref = await run_blocking_async(
                run_connectors_ingestion,
                connector_manifest=manifest,
                source="performance_test",
                license_name="MIT",
                cas_root=cas_root,
                dependencies=dependencies,
                timeout_seconds=5.0,
            )
            assert evidence_ref is not None
            payloads.append(await async_store.get_bytes(evidence_ref.artifact_id))
        return payloads

    payloads = run_coro_sync(_exercise())
    assert len(payloads) == 16
    assert all(payloads)


@pytest.mark.performance
@pytest.mark.benchmark
def test_async_cursor_store_stream_progress_hot_path(benchmark, tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    cursor_store = AsyncCursorStoreAdapter(CursorStore(store), timeout_seconds=2.0)
    sequence = {"value": 0}

    def _exercise() -> tuple[str, int]:
        async def _round_trip() -> tuple[str, int]:
            index = sequence["value"]
            sequence["value"] += 1
            cursor = CursorState(
                cursor_id="stream.jsonl:events",
                connector_id="stream.jsonl",
                dataset_id="events",
                watermark_type=WatermarkType.OFFSET,
                watermark_value=str(index),
                created_at=datetime.now(UTC),
            )
            checkpoint = StreamCheckpoint(
                checkpoint_id=f"stream.jsonl:events:default:{index}",
                stream_id="stream.jsonl:events:default",
                connector_id="stream.jsonl",
                dataset_id="events",
                partition_key="default",
                offset=index,
                resume_token=f"resume-{index}",
                lifecycle_state=StreamLifecycleState.ACTIVE,
                created_at=datetime.now(UTC),
            )
            await cursor_store.commit_stream_progress(cursor=cursor, checkpoint=checkpoint)
            latest = await cursor_store.find_latest_stream_checkpoint("stream.jsonl", "events")
            assert latest is not None
            return cursor.watermark_value, latest.offset

        return run_coro_sync(_round_trip())

    assert benchmark(_exercise)[1] >= 0


@pytest.mark.performance
def test_async_cursor_store_stream_progress_soak_smoke(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    cursor_store = AsyncCursorStoreAdapter(CursorStore(store), timeout_seconds=2.0)

    async def _exercise() -> list[int]:
        offsets: list[int] = []
        for index in range(64):
            cursor = CursorState(
                cursor_id="stream.jsonl:events",
                connector_id="stream.jsonl",
                dataset_id="events",
                watermark_type=WatermarkType.OFFSET,
                watermark_value=str(index),
                created_at=datetime.now(UTC),
            )
            checkpoint = StreamCheckpoint(
                checkpoint_id=f"stream.jsonl:events:default:{index}",
                stream_id="stream.jsonl:events:default",
                connector_id="stream.jsonl",
                dataset_id="events",
                partition_key="default",
                offset=index,
                resume_token=f"resume-{index}",
                lifecycle_state=StreamLifecycleState.ACTIVE,
                created_at=datetime.now(UTC),
            )
            await cursor_store.commit_stream_progress(cursor=cursor, checkpoint=checkpoint)
            latest = await cursor_store.find_latest_stream_checkpoint("stream.jsonl", "events")
            assert latest is not None
            offsets.append(latest.offset)
        return offsets

    assert run_coro_sync(_exercise()) == list(range(64))


@pytest.mark.performance
def test_partitioned_ingestion_resume_cycle_soak_smoke(tmp_path) -> None:
    def _handler(partition) -> IngestionResult:
        return IngestionResult(
            datasets_fetched=1,
            cursor_ref=f"cursor:{partition.partition_id}",
        )

    cas_root = tmp_path / ".polisyos"
    for batch in range(16):
        plan = build_partitioned_ingestion_plan(
            connector_id="stream.jsonl",
            dataset_id=f"events-{batch}",
            partition_key="region",
            partitions=[
                {"partition_id": f"p{batch}-0", "bounds": {"region": "ua"}},
                {"partition_id": f"p{batch}-1", "bounds": {"region": "pl"}},
            ],
        )
        results = run_partitioned_ingestion(
            plan=plan,
            connector_manifest={"datasets": []},
            source="test",
            license_name="open",
            cas_root=cas_root,
            partition_handler=_handler,
        )
        assert [result.status for result in results] == ["succeeded", "succeeded"]

    states = CursorStore(FileSystemCAS(cas_root)).list_partition_states()
    assert len(states) >= 32


@pytest.mark.performance
def test_streaming_async_adapter_resume_cycle_soak_smoke(tmp_path) -> None:
    stream_path = tmp_path / "stream.jsonl"
    stream_path.write_text(
        "\n".join(f'{{"_message_id":"m{index}","value":{index}}}' for index in range(8)) + "\n",
        encoding="utf-8",
    )

    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(
            url=stream_path.as_uri(),
            headers={"X-Stream-ChunkSize": "2"},
        ),
    )

    sync_store = FileSystemCAS(tmp_path / ".polisyos")
    async_store = AsyncArtifactStoreAdapter(sync_store, timeout_seconds=3.0)
    async_cursor_store = AsyncCursorStoreAdapter(
        CursorStore(sync_store),
        timeout_seconds=3.0,
    )

    def _sanitize_rows(batch, **kwargs):
        del kwargs
        return [dict(row) for row in batch if isinstance(row, dict)], [], 0

    async def _exercise() -> list[int]:
        emitted: list[int] = []
        for cycle in range(12):
            result = await process_stream_dataset(
                connector_id="stream.jsonl",
                dataset_id=f"events-{cycle}",
                store=async_store,
                cursor_store=async_cursor_store,
                sanitize_rows=_sanitize_rows,
                runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
                registry=registry,
            )
            emitted.append(result.rows_emitted)
        return emitted

    assert run_coro_sync(_exercise()) == [8] * 12


@pytest.mark.performance
def test_streaming_async_adapter_cdc_round_trip_soak_smoke(tmp_path) -> None:
    stream_path = tmp_path / "stream-cdc.jsonl"
    stream_path.write_text(
        "\n".join(
            [
                '{"_message_id":"m1","value":1}',
                '{"_message_id":"m2","value":2,"new_field":"x"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(
            url=stream_path.as_uri(),
            headers={"X-Stream-ChunkSize": "1"},
        ),
    )

    sync_store = FileSystemCAS(tmp_path / ".polisyos")
    async_store = AsyncArtifactStoreAdapter(sync_store, timeout_seconds=3.0)
    async_cursor_store = AsyncCursorStoreAdapter(
        CursorStore(sync_store),
        timeout_seconds=3.0,
    )

    def _sanitize_rows(batch, **kwargs):
        del kwargs
        return [dict(row) for row in batch if isinstance(row, dict)], [], 0

    async def _exercise() -> list[int]:
        cdc_counts: list[int] = []
        for cycle in range(12):
            result = await process_stream_dataset(
                connector_id="stream.jsonl",
                dataset_id=f"events-cdc-{cycle}",
                store=async_store,
                cursor_store=async_cursor_store,
                sanitize_rows=_sanitize_rows,
                runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
                registry=registry,
            )
            cdc_counts.append(len(result.cdc_event_refs))
        return cdc_counts

    assert run_coro_sync(_exercise()) == [1] * 12


@pytest.mark.performance
def test_streaming_async_adapter_combined_resume_cdc_long_soak_smoke(tmp_path) -> None:
    stream_path = tmp_path / "stream-combined.jsonl"
    stream_path.write_text(
        "\n".join(
            [
                '{"_message_id":"m1","value":1}',
                '{"_message_id":"m2","value":2}',
                '{"_message_id":"m2","value":2}',
                '{"_message_id":"m3","value":3,"new_field":"x"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(
            url=stream_path.as_uri(),
            headers={"X-Stream-ChunkSize": "2"},
        ),
    )

    sync_store = FileSystemCAS(tmp_path / ".polisyos")
    async_store = AsyncArtifactStoreAdapter(sync_store, timeout_seconds=3.0)
    async_cursor_store = AsyncCursorStoreAdapter(
        CursorStore(sync_store),
        timeout_seconds=3.0,
    )

    def _sanitize_rows(batch, **kwargs):
        del kwargs
        return [dict(row) for row in batch if isinstance(row, dict)], [], 0

    async def _exercise() -> tuple[list[int], list[int], list[int]]:
        emitted_counts: list[int] = []
        cdc_counts: list[int] = []
        dedupe_counts: list[int] = []
        for cycle in range(24):
            result = await process_stream_dataset(
                connector_id="stream.jsonl",
                dataset_id=f"events-combined-{cycle}",
                store=async_store,
                cursor_store=async_cursor_store,
                sanitize_rows=_sanitize_rows,
                runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
                registry=registry,
            )
            emitted_counts.append(result.rows_emitted)
            cdc_counts.append(len(result.cdc_event_refs))
            dedupe_counts.append(result.dedupe_dropped)
        return emitted_counts, cdc_counts, dedupe_counts

    emitted_counts, cdc_counts, dedupe_counts = run_coro_sync(_exercise())
    assert emitted_counts == [3] * 24
    assert cdc_counts == [1] * 24
    assert dedupe_counts == [1] * 24


@pytest.mark.performance
def test_streaming_windowed_legacy_async_chunk_round_trip_soak_smoke(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
    from polisyos.fabric.data_plane import modes as modes_mod

    seen_kinds: list[str] = []
    original_put_json = AsyncArtifactStoreAdapter.put_json

    async def _tracked_put_json(self, obj: object, opts: object, canon_spec: object = None):
        kind = getattr(opts, "kind", "")
        seen_kinds.append(str(kind))
        return await original_put_json(self, obj, opts, canon_spec=canon_spec)

    async def _fake_fetch_stream_for_dataset_async(**kwargs: object) -> list[dict[str, object]]:
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

    results = [
        run_streaming_windowed(
            connector_manifest={
                "datasets": [
                    {"connector_id": "legacy.stream", "dataset_id": f"events-{cycle}"},
                ],
            },
            source="test",
            license_name="MIT",
            cas_root=tmp_path / ".polisyos",
            produce_snapshot=False,
        )
        for cycle in range(12)
    ]

    assert all(result.mode_effective == "streaming_windowed" for result in results)
    assert seen_kinds.count("fabric.stream_chunk") == 12


@pytest.mark.performance
def test_streaming_windowed_async_snapshot_round_trip_soak_smoke(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
    from polisyos.fabric.data_plane import modes as modes_mod

    seen_kinds: list[str] = []
    original_put_json = AsyncArtifactStoreAdapter.put_json

    async def _tracked_put_json(self, obj: object, opts: object, canon_spec: object = None):
        seen_kinds.append(str(getattr(opts, "kind", "")))
        return await original_put_json(self, obj, opts, canon_spec=canon_spec)

    async def _fake_fetch_stream_for_dataset_async(**kwargs: object) -> list[dict[str, object]]:
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

    results = [
        run_streaming_windowed(
            connector_manifest={
                "datasets": [
                    {"connector_id": "legacy.stream", "dataset_id": f"events-{cycle}"},
                ],
            },
            source="test",
            license_name="MIT",
            cas_root=tmp_path / ".polisyos",
            produce_snapshot=True,
        )
        for cycle in range(12)
    ]

    assert all(result.data_snapshot_ref is not None for result in results)
    assert seen_kinds.count("fabric.streaming_run_manifest") == 12
    assert seen_kinds.count("fabric.data_snapshot") == 12


@pytest.mark.performance
def test_orchestrated_ingestion_async_snapshot_round_trip_soak_smoke(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter

    cas_root = tmp_path / ".polisyos"
    store = FileSystemCAS(cas_root)
    data_ref = store.put_json(
        {"rows": [{"value": 1}]},
        ArtifactWriteOptions(kind="fabric.data_payload", media_type="application/json"),
    )
    evidence_ref_payload = store.put_json(
        EvidenceBundle(sources=[data_ref], notes=["perf"]),
        ArtifactWriteOptions(kind="fabric.evidence_bundle", media_type="application/json"),
    )
    evidence_ref = EvidenceBundleRef(artifact_id=evidence_ref_payload.artifact_id)

    seen_kinds: list[str] = []
    original_put_json = AsyncArtifactStoreAdapter.put_json

    async def _tracked_put_json(self, obj: object, opts: object, canon_spec: object = None):
        seen_kinds.append(str(getattr(opts, "kind", "")))
        return await original_put_json(self, obj, opts, canon_spec=canon_spec)

    monkeypatch.setattr(AsyncArtifactStoreAdapter, "put_json", _tracked_put_json)

    with patch(
        "polisyos.fabric.ingestion.run_connectors_ingestion",
        return_value=evidence_ref,
    ):
        results = [
            run_orchestrated_ingestion(
                connector_manifest={
                    "datasets": [{"connector_id": "test", "dataset_id": f"ds-{cycle}"}]
                },
                source="test",
                license_name="MIT",
                cas_root=cas_root,
                produce_snapshot=True,
            )
            for cycle in range(12)
        ]

    assert all(result.data_snapshot_ref is not None for result in results)
    assert seen_kinds.count("fabric.quality_report") == 12
    assert seen_kinds.count("fabric.data_snapshot") == 12
