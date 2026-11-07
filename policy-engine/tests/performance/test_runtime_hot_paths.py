from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from _helpers.runtime_http import (
    _runtime_api_tenant_scope,
    build_runtime_api_env_with_fixture_catalog,
    close_runtime_api_env,
)
from _helpers.source_progress import finite_source_reader

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
from polisyos.fabric.connectors.sources.event_stream import EventStreamConnector
from polisyos.fabric.data_plane.cursor_store import AsyncCursorStoreAdapter, CursorStore
from polisyos.fabric.data_plane.modes import run_streaming_windowed
from polisyos.fabric.data_plane.orchestrator import (
    IngestionResult,
    build_partitioned_ingestion_plan,
    run_orchestrated_ingestion,
    run_partitioned_ingestion,
)
from polisyos.fabric.data_plane.streaming import (
    StreamDedupeUnsupported,
    StreamRuntimeOptions,
    process_stream_dataset,
)
from polisyos.fabric.ingestion import resolve_ingestion_dependencies
from polisyos.ir.connectors import DataVersion, VersionStrategy
from polisyos.runtime.http.services.lineage import LineageSurfaceAdmissionError
from polisyos.runtime.quality.performance_budget import build_canary_performance_budget
from tools.quality.testing import runtime_resilience_matrix

_INGESTION_VERSION = DataVersion(
    strategy=VersionStrategy.TIMESTAMP,
    value="2024-07-01T00:00:00+00:00",
    timestamp=datetime(2024, 7, 1, 0, 0, 0, tzinfo=UTC),
)


@pytest.fixture(scope="module")
def performance_catalog_source(tmp_path_factory, pytestconfig):
    """Publish one isolated test catalog, then reopen it for each Runtime app."""
    catalog_root = tmp_path_factory.mktemp("runtime-performance-catalog").resolve()
    with pytest.MonkeyPatch.context() as fixture_patch:
        fixture_patch.setenv("POLISYOS_PRODUCTION_DATA_ROOT", str(catalog_root / "no-production"))
        fixture_patch.setenv("POLISYOS_CURATED_DIR", str(catalog_root / "no-curated-data"))
        env = build_runtime_api_env_with_fixture_catalog(
            catalog_root,
            include_test_client=False,
            app_kwargs={"repo_root": Path(pytestconfig.rootpath).resolve(strict=True)},
            monkeypatch=fixture_patch,
        )
        try:
            service = env["app"].state._control_service
            selection = service._catalog_source_selection
            database = service.catalog_serving_source.database_path.resolve(strict=True)
            assert database.is_relative_to(catalog_root)
            assert env["_runtime_http_catalog_fixture"].table_counts["datasets"] > 0
            identity = service._retrieval._dataset_catalog.read_source_identity[0]
            assert identity.source_path == str(database)
            return selection, identity.content_sha256
        finally:
            close_runtime_api_env(env)


@pytest.fixture
def performance_runtime_env(
    tmp_path: Path,
    pytestconfig: pytest.Config,
    monkeypatch: pytest.MonkeyPatch,
    performance_catalog_source,
) -> Iterator[dict[str, object]]:
    """Build a fresh Runtime app on the selected fixture catalog and an empty curated root."""
    from tests.unit.runtime.http._published_catalog_fixture import _install_fixture_profiles

    selection, expected_sha256 = performance_catalog_source
    monkeypatch.setenv("POLISYOS_PRODUCTION_DATA_ROOT", str(tmp_path / "no-production"))
    curated = tmp_path / "no-curated-data"
    monkeypatch.setenv("POLISYOS_CURATED_DIR", str(curated))
    _install_fixture_profiles(monkeypatch)
    env = build_runtime_api_env_with_fixture_catalog(
        tmp_path,
        include_test_client=False,
        app_kwargs={
            "repo_root": Path(pytestconfig.rootpath).resolve(strict=True),
            "catalog_source_selection": selection,
        },
        monkeypatch=monkeypatch,
    )
    try:
        service = env["app"].state._control_service
        graph = service._retrieval._dataset_catalog
        assert graph.database_path.resolve(strict=True) == (
            selection.snapshot_root / selection.database_relative_path
        ).resolve(strict=True)
        assert graph.read_source_identity[0].content_sha256 == expected_sha256
        assert service._retrieval._fastlane.binding_registry.curated_dir == curated
        assert service._retrieval._fastlane._contracts.curated_dir == curated
        yield env
    finally:
        close_runtime_api_env(env)


@pytest.mark.performance
def test_runtime_fixture_refuses_missing_explicit_catalog(
    tmp_path: Path, pytestconfig: pytest.Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unavailable selected catalog cannot be replaced by the fixture default."""
    from polisyos.runtime.quality.substrate_registry import (
        CatalogServingSourceSelection,
        SubstrateRegistryError,
    )

    monkeypatch.setenv("POLISYOS_PRODUCTION_DATA_ROOT", str(tmp_path / "no-production"))
    monkeypatch.setenv("POLISYOS_CURATED_DIR", str(tmp_path / "no-curated-data"))
    selection = CatalogServingSourceSelection(
        snapshot_root=(tmp_path / "missing-snapshot").resolve(),
        catalog_run_profile="prod_full",
    )
    with pytest.raises(SubstrateRegistryError, match="catalog_source_snapshot_missing"):
        build_runtime_api_env_with_fixture_catalog(
            tmp_path,
            include_test_client=False,
            app_kwargs={
                "repo_root": Path(pytestconfig.rootpath).resolve(strict=True),
                "catalog_source_selection": selection,
            },
            monkeypatch=monkeypatch,
        )
    assert not (tmp_path / "catalog-fixture-owner").exists()


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
def test_canary_performance_budget_report_covers_runtime_hot_path_layers() -> None:
    report = build_canary_performance_budget(
        canary_kind="production",
        job_payload={
            "submitted_at": "2026-05-13T09:00:00Z",
            "started_at": "2026-05-13T09:00:01Z",
            "finished_at": "2026-05-13T09:00:06Z",
        },
        cas_samples=[
            {"duration_ms": 4.0},
            {"observed_duration_ms": 6.0},
        ],
        runtime_observations={
            "run_index_refresh_ms": 17.0,
            "run_index_list_ms": 8.0,
            "timeline_api_ms": 12.0,
            "lineage_api_ms": 22.0,
        },
        evidence_collection_duration_ms=33.0,
        dashboard_evidence={
            "routes": [
                {
                    "path": "/runs/R_hot/overview",
                    "render_duration_ms": 44.0,
                }
            ]
        },
    )

    rows = {row["phase"]: row for row in report["phase_budgets"]}
    required_row_keys = {
        "observed_duration_ms",
        "budget_ms",
        "status",
        "layer",
        "retryable",
        "retryability",
        "next_action",
    }

    assert report["schema_version"] == "policyos.canary_performance_budget.v1"
    assert report["status"] == "pass"
    assert rows["control.job_total"]["observed_duration_ms"] == 6000.0
    assert rows["cas.round_trip_p95"]["observed_duration_ms"] == 6.0
    assert rows["runtime.run_index_refresh"]["layer"] == "runtime_api"
    assert rows["runtime.run_index_list"]["layer"] == "runtime_api"
    assert rows["runtime.timeline_api"]["layer"] == "runtime_api"
    assert rows["runtime.lineage_api"]["layer"] == "runtime_api"
    assert rows["evidence.collection"]["layer"] == "canary_evidence"
    assert rows["dashboard.route_render:/runs/R_hot/overview"]["layer"] == "dashboard"
    assert rows["dashboard.route_render:/runs/R_hot/overview"]["path"] == ("/runs/R_hot/overview")
    assert all(required_row_keys <= set(row) for row in report["phase_budgets"])


@pytest.mark.performance
def test_runtime_resilience_matrix_covers_hot_path_pressure_budgets() -> None:
    payload = runtime_resilience_matrix.build_matrix_payload(deterministic=True)
    budgets = {budget["phase"]: budget for budget in payload["slo_budgets"]}
    scenarios = {scenario["scenario_id"]: scenario for scenario in payload["scenarios"]}

    for phase in (
        "cas.put",
        "cas.get",
        "runtime.run_index_refresh",
        "runtime.run_index_list",
        "runtime.timeline_build",
        "runtime.lineage_build",
        "api.job_detail",
    ):
        assert budgets[phase]["budget_ms"] > 0
        assert budgets[phase]["layer"]
        assert budgets[phase]["next_action"]

    cas_pressure = scenarios["cas_pressure"]
    run_index_pressure = scenarios["run_index_pressure"]
    assert cas_pressure["classification"] == "performance_warning"
    assert cas_pressure["top_bottleneck"]["phase"] == "cas.put"
    assert run_index_pressure["classification"] == "performance_warning"
    assert run_index_pressure["top_bottleneck"]["phase"] == "runtime.run_index_refresh"


@pytest.mark.performance
@pytest.mark.benchmark
def test_run_index_refresh_hot_path(benchmark, performance_runtime_env) -> None:
    env = performance_runtime_env
    run_index = env["app"].state.runtime_api_ctx.run_index

    benchmark(lambda: run_index.refresh(force=True))


@pytest.mark.performance
@pytest.mark.benchmark
def test_run_index_list_runs_hot_path(benchmark, performance_runtime_env) -> None:
    env = performance_runtime_env
    run_index = env["app"].state.runtime_api_ctx.run_index
    run_index.refresh(force=True)

    benchmark(lambda: run_index.list_runs(limit=50, tenant_id=env["tenant_a"]))


@pytest.mark.performance
@pytest.mark.benchmark
def test_run_index_incremental_refresh_cycle_hot_path(benchmark, performance_runtime_env) -> None:
    env = performance_runtime_env
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
def test_run_index_incremental_refresh_soak_smoke(performance_runtime_env) -> None:
    env = performance_runtime_env
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
def test_timeline_build_hot_path(benchmark, performance_runtime_env) -> None:
    env = performance_runtime_env
    ctx = env["app"].state.runtime_api_ctx
    run = ctx.run_index.get_run(env["core_run_id"])

    benchmark(lambda: ctx.timeline.build_for_run(run))


@pytest.mark.performance
@pytest.mark.benchmark
def test_lineage_build_hot_path(benchmark, performance_runtime_env) -> None:
    env = performance_runtime_env
    ctx = env["app"].state.runtime_api_ctx
    run = ctx.run_index.get_run(env["core_run_id"])
    root_refs = ctx.run_index.resolve_root_artifact_refs(run)

    secret_refs = [ref for ref in root_refs if str(ref.artifact_id) == env["secret_artifact_id"]]
    admitted_refs = [ref for ref in root_refs if str(ref.artifact_id) != env["secret_artifact_id"]]
    assert len(secret_refs) == 1
    assert len(admitted_refs) == len(root_refs) - 1
    assert admitted_refs, "lineage benchmark requires an admitted positive substrate"
    with _runtime_api_tenant_scope(env):
        with pytest.raises(LineageSurfaceAdmissionError, match="authority_purpose_forbidden"):
            ctx.lineage.build_for_artifact_ids(secret_refs)
        benchmark(lambda: ctx.lineage.build_for_artifact_ids(admitted_refs))


@pytest.mark.performance
@pytest.mark.benchmark
def test_async_artifact_store_round_trip_hot_path(benchmark, performance_runtime_env) -> None:
    env = performance_runtime_env
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
def test_async_artifact_store_repeated_round_trip_soak_smoke(performance_runtime_env) -> None:
    env = performance_runtime_env
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
def test_async_artifact_store_concurrent_round_trip_soak_smoke(performance_runtime_env) -> None:
    env = performance_runtime_env
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


@pytest.fixture
def performance_stream_registry() -> Iterator[ConnectorRegistry]:
    """Give each benchmark a real connector registry with an independent lifetime."""
    registry = ConnectorRegistry()
    registry.register(EventStreamConnector)
    try:
        yield registry
    finally:
        run_coro_sync(registry.shutdown_async())


def _performance_source_reader(
    root: Path,
    dataset_id: str,
    stream_path: Path,
    event_ids: tuple[str, ...],
    *,
    partition_key: str = "default",
):
    """Bind a synthetic owner's independent event/version set to real JSONL transport."""
    return finite_source_reader(
        root / "source-owners" / dataset_id,
        connector_id="stream.jsonl",
        dataset_id=dataset_id,
        schema_id=f"test.performance.{dataset_id.replace('-', '_')}",
        snapshots=[
            (
                "source-v1",
                [{"event_id": event_id, "source_version": 1} for event_id in event_ids],
            )
        ],
        transport_path=stream_path,
        partition_key=partition_key,
    )


def _write_performance_stream(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _performance_sanitize_rows(
    batch: object, **kwargs: object
) -> tuple[list[dict[str, object]], list[str], int]:
    """Keep valid source records unchanged; malformed records fail the fixture."""
    del kwargs
    if not isinstance(batch, list) or any(type(row) is not dict for row in batch):
        raise TypeError("performance stream requires a list of source record objects")
    return batch, [], 0


def _configure_performance_stream(
    registry: ConnectorRegistry, path: Path, *, chunk_size: int
) -> None:
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(url=path.as_uri(), headers={"X-Stream-ChunkSize": str(chunk_size)}),
    )


@pytest.mark.performance
def test_streaming_async_adapter_resume_cycle_soak_smoke(
    tmp_path: Path, performance_stream_registry: ConnectorRegistry
) -> None:
    stream_path = tmp_path / "stream.jsonl"
    event_ids = tuple(f"m{index}" for index in range(8))
    _write_performance_stream(
        stream_path,
        [
            {"_message_id": event_id, "event_id": event_id, "source_version": 1, "value": index}
            for index, event_id in enumerate(event_ids)
        ],
    )
    _configure_performance_stream(performance_stream_registry, stream_path, chunk_size=2)
    readers = {
        f"events-{cycle}": _performance_source_reader(
            tmp_path, f"events-{cycle}", stream_path, event_ids
        )
        for cycle in range(12)
    }
    sync_store = FileSystemCAS(tmp_path / ".polisyos")
    async_store = AsyncArtifactStoreAdapter(sync_store, timeout_seconds=3.0)
    async_cursor_store = AsyncCursorStoreAdapter(CursorStore(sync_store), timeout_seconds=3.0)

    async def _exercise() -> list[int]:
        emitted: list[int] = []
        for cycle in range(12):
            dataset_id = f"events-{cycle}"
            result = await process_stream_dataset(
                connector_id="stream.jsonl",
                dataset_id=dataset_id,
                store=async_store,
                cursor_store=async_cursor_store,
                sanitize_rows=_performance_sanitize_rows,
                runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
                registry=performance_stream_registry,
                source_progress_readers=(readers[dataset_id],),
            )
            emitted.append(result.rows_emitted)
            if cycle == 0:
                resumed = await process_stream_dataset(
                    connector_id="stream.jsonl",
                    dataset_id=dataset_id,
                    store=async_store,
                    cursor_store=async_cursor_store,
                    sanitize_rows=_performance_sanitize_rows,
                    runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
                    registry=performance_stream_registry,
                    source_progress_readers=(readers[dataset_id],),
                )
                assert result.final_checkpoint is not None
                assert resumed.final_checkpoint is not None
                assert resumed.final_checkpoint.offset == result.final_checkpoint.offset
                assert resumed.rows_emitted == 0
        return emitted

    assert run_coro_sync(_exercise()) == [8] * 12


@pytest.mark.performance
def test_streaming_async_adapter_cdc_round_trip_soak_smoke(
    tmp_path: Path, performance_stream_registry: ConnectorRegistry
) -> None:
    stream_path = tmp_path / "stream-cdc.jsonl"
    event_ids = ("m1", "m2")
    _write_performance_stream(
        stream_path,
        [
            {"_message_id": "m1", "event_id": "m1", "source_version": 1, "value": 1},
            {
                "_message_id": "m2",
                "event_id": "m2",
                "source_version": 1,
                "value": 2,
                "new_field": "x",
            },
        ],
    )
    _configure_performance_stream(performance_stream_registry, stream_path, chunk_size=1)
    readers = {
        f"events-cdc-{cycle}": _performance_source_reader(
            tmp_path, f"events-cdc-{cycle}", stream_path, event_ids
        )
        for cycle in range(12)
    }
    sync_store = FileSystemCAS(tmp_path / ".polisyos")
    async_store = AsyncArtifactStoreAdapter(sync_store, timeout_seconds=3.0)
    async_cursor_store = AsyncCursorStoreAdapter(CursorStore(sync_store), timeout_seconds=3.0)

    async def _exercise() -> list[int]:
        cdc_counts: list[int] = []
        for cycle in range(12):
            dataset_id = f"events-cdc-{cycle}"
            result = await process_stream_dataset(
                connector_id="stream.jsonl",
                dataset_id=dataset_id,
                store=async_store,
                cursor_store=async_cursor_store,
                sanitize_rows=_performance_sanitize_rows,
                runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
                registry=performance_stream_registry,
                source_progress_readers=(readers[dataset_id],),
            )
            cdc_counts.append(len(result.cdc_event_refs))
        return cdc_counts

    assert run_coro_sync(_exercise()) == [1] * 12


@pytest.mark.performance
def test_streaming_async_adapter_combined_resume_cdc_long_soak_smoke(
    tmp_path: Path, performance_stream_registry: ConnectorRegistry
) -> None:
    stream_path = tmp_path / "stream-combined.jsonl"
    event_ids = ("m1", "m2", "m3")
    _write_performance_stream(
        stream_path,
        [
            {"_message_id": "m1", "event_id": "m1", "source_version": 1, "value": 1},
            {"_message_id": "m2", "event_id": "m2", "source_version": 1, "value": 2},
            {"_message_id": "m2", "event_id": "m2", "source_version": 1, "value": 2},
            {
                "_message_id": "m3",
                "event_id": "m3",
                "source_version": 1,
                "value": 3,
                "new_field": "x",
            },
        ],
    )
    _configure_performance_stream(performance_stream_registry, stream_path, chunk_size=2)
    readers = {
        f"events-combined-{cycle}": _performance_source_reader(
            tmp_path, f"events-combined-{cycle}", stream_path, event_ids
        )
        for cycle in range(24)
    }
    sync_store = FileSystemCAS(tmp_path / ".polisyos")
    async_store = AsyncArtifactStoreAdapter(sync_store, timeout_seconds=3.0)
    async_cursor_store = AsyncCursorStoreAdapter(CursorStore(sync_store), timeout_seconds=3.0)

    async def _exercise() -> tuple[list[int], list[int], list[int]]:
        emitted_counts: list[int] = []
        cdc_counts: list[int] = []
        dedupe_counts: list[int] = []
        for cycle in range(24):
            dataset_id = f"events-combined-{cycle}"
            result = await process_stream_dataset(
                connector_id="stream.jsonl",
                dataset_id=dataset_id,
                store=async_store,
                cursor_store=async_cursor_store,
                sanitize_rows=_performance_sanitize_rows,
                runtime_options=StreamRuntimeOptions(checkpoint_every_chunks=1),
                registry=performance_stream_registry,
                source_progress_readers=(readers[dataset_id],),
            )
            emitted_counts.append(result.rows_emitted)
            cdc_counts.append(len(result.cdc_event_refs))
            dedupe_counts.append(result.dedupe_dropped)
        return emitted_counts, cdc_counts, dedupe_counts

    emitted_counts, cdc_counts, dedupe_counts = run_coro_sync(_exercise())
    assert emitted_counts == [3] * 24
    assert cdc_counts == [1] * 24
    assert dedupe_counts == [1] * 24


def _run_owned_windowed_soak(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    registry: ConnectorRegistry,
    *,
    produce_snapshot: bool,
) -> tuple[list[IngestionResult], list[str]]:
    """Exercise real source-admitted windowing through the public mode API."""
    stream_path = tmp_path / "stream-windowed.jsonl"
    _write_performance_stream(
        stream_path,
        [{"_message_id": "event-0", "event_id": "event-0", "source_version": 1, "value": 1}],
    )
    _configure_performance_stream(registry, stream_path, chunk_size=1)
    readers = {
        f"events-{cycle}": _performance_source_reader(
            tmp_path,
            f"events-{cycle}",
            stream_path,
            ("event-0",),
            partition_key=f"events-{cycle}",
        )
        for cycle in range(12)
    }
    seen_kinds: list[str] = []
    original_put_json = AsyncArtifactStoreAdapter.put_json

    async def _tracked_put_json(
        self,
        obj: object,
        opts: object,
        canon_spec: object = None,
        *,
        return_selected_profile: bool = False,
    ):
        seen_kinds.append(str(getattr(opts, "kind", "")))
        return await original_put_json(
            self, obj, opts, canon_spec=canon_spec, return_selected_profile=return_selected_profile
        )

    monkeypatch.setattr(AsyncArtifactStoreAdapter, "put_json", _tracked_put_json)
    results = []
    for cycle in range(12):
        dataset_id = f"events-{cycle}"
        dependencies = resolve_ingestion_dependencies(
            registry=registry, source_progress_readers=(readers[dataset_id],)
        )
        results.append(
            run_streaming_windowed(
                connector_manifest={
                    "datasets": [{"connector_id": "stream.jsonl", "dataset_id": dataset_id}],
                },
                source="test",
                license_name="MIT",
                cas_root=tmp_path / ".polisyos",
                produce_snapshot=produce_snapshot,
                ingestion_dependencies=dependencies,
            )
        )
    return results, seen_kinds


@pytest.mark.performance
def test_streaming_windowed_owned_async_chunk_round_trip_soak_smoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, performance_stream_registry: ConnectorRegistry
) -> None:
    results, seen_kinds = _run_owned_windowed_soak(
        tmp_path, monkeypatch, performance_stream_registry, produce_snapshot=False
    )
    assert all(result.mode_effective == "streaming_windowed" for result in results)
    assert seen_kinds.count("fabric.stream_chunk") == 12


@pytest.mark.performance
def test_streaming_windowed_owned_async_snapshot_round_trip_soak_smoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, performance_stream_registry: ConnectorRegistry
) -> None:
    results, seen_kinds = _run_owned_windowed_soak(
        tmp_path, monkeypatch, performance_stream_registry, produce_snapshot=True
    )
    assert all(result.data_snapshot_ref is not None for result in results)
    assert seen_kinds.count("fabric.streaming_run_manifest") == 12
    assert seen_kinds.count("fabric.data_snapshot") == 12


@pytest.mark.performance
def test_streaming_windowed_unowned_legacy_refuses_before_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, performance_stream_registry: ConnectorRegistry
) -> None:
    """The old unregistered path cannot claim deduplication without an owner."""
    from polisyos.fabric.data_plane import modes as modes_mod

    fetched = False

    async def _unowned_fetch(**kwargs: object) -> list[dict[str, object]]:
        nonlocal fetched
        del kwargs
        fetched = True
        return []

    monkeypatch.setattr(modes_mod, "_fetch_stream_for_dataset_async", _unowned_fetch)
    with pytest.raises(StreamDedupeUnsupported, match="legacy streaming has no source-owned"):
        run_streaming_windowed(
            connector_manifest={
                "datasets": [{"connector_id": "legacy.stream", "dataset_id": "events"}]
            },
            source="test",
            license_name="MIT",
            cas_root=tmp_path / ".polisyos",
            produce_snapshot=False,
            ingestion_dependencies=resolve_ingestion_dependencies(
                registry=performance_stream_registry
            ),
        )
    assert fetched is False


@pytest.mark.performance
def test_streaming_async_adapter_rejects_foreign_source_event(
    tmp_path: Path, performance_stream_registry: ConnectorRegistry
) -> None:
    """The admitted owner's event/version census is checked before stream output."""
    stream_path = tmp_path / "foreign.jsonl"
    _write_performance_stream(
        stream_path, [{"event_id": "foreign", "source_version": 1, "value": 1}]
    )
    _configure_performance_stream(performance_stream_registry, stream_path, chunk_size=1)
    reader = _performance_source_reader(tmp_path, "events", stream_path, ("owned",))
    store = FileSystemCAS(tmp_path / ".polisyos")

    async def _exercise() -> None:
        with pytest.raises(StreamDedupeUnsupported, match="source replay transport"):
            await process_stream_dataset(
                connector_id="stream.jsonl",
                dataset_id="events",
                store=store,
                cursor_store=CursorStore(store),
                sanitize_rows=_performance_sanitize_rows,
                registry=performance_stream_registry,
                source_progress_readers=(reader,),
            )

    run_coro_sync(_exercise())
    assert list(store.iter_artifact_ids()) == []


@pytest.mark.performance
def test_orchestrated_ingestion_async_snapshot_round_trip_soak_smoke(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.contracts.fabric import DataSnapshot, RetrievalSummary

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

    async def _tracked_put_json(
        self,
        obj: object,
        opts: object,
        canon_spec: object = None,
        *,
        return_selected_profile: bool = False,
    ):
        seen_kinds.append(str(getattr(opts, "kind", "")))
        return await original_put_json(
            self,
            obj,
            opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )

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
    assert seen_kinds.count("fabric.retrieval_summary") == 12
    assert seen_kinds.count("fabric.data_snapshot") == 12
    snapshot_ref = results[0].data_snapshot_ref
    assert snapshot_ref is not None
    snapshot = DataSnapshot.model_validate(from_canonical_bytes(store.get_bytes(snapshot_ref)))
    assert snapshot.quality_report_ref is not None
    assert snapshot.quality_report_ref.manifest_profile_sha256 is not None
    summary = RetrievalSummary.model_validate(
        from_canonical_bytes(store.get_bytes(snapshot.quality_report_ref))
    )
    assert summary.assessment_status == "not_assessed"
    assert summary.source_refs == [data_ref]
