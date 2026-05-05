from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

import pytest
from polisyos.core.artifacts import FileSystemCAS
from polisyos.fabric.catalog.source_bindings import SourceBinding, SourceBindingRegistry
from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.bindings.models import BindingProfile
from polisyos.fabric.connectors.bindings.registry import BindingProfileRegistry
from polisyos.fabric.connectors.cache import (
    ConnectorCacheStore,
    PolicyRegistry,
    PrefetchScheduler,
    TTLPolicy,
)
from polisyos.fabric.connectors.pool import (
    BackpressureLevel,
    ConnectionPool,
    PoolClosedError,
    PoolConfig,
)
from polisyos.fabric.connectors.profiles.models import SourceProfile
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
from polisyos.fabric.connectors.reference.sdmx import SDMXConnector
from polisyos.fabric.connectors.reference.static_csv import StaticCSVConnector
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.resilience import RateLimiter
from polisyos.fabric.connectors.sources.graphql_api import GraphQLConnector
from polisyos.fabric.entity_resolution.models import EntityRecord
from polisyos.fabric.entity_resolution.resolver import ProbabilisticEntityResolver
from polisyos.fabric.provenance.lineage import FabricLineageTracker
from polisyos.fabric.world.store import WorldSegmentError, load_world_fact_manifests
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    DataVersion,
    QualityTier,
    TrustLevel,
    VersionStrategy,
    capabilities_from_flags,
)


def _version() -> DataVersion:
    return DataVersion(
        strategy=VersionStrategy.TIMESTAMP,
        value="phase2",
        timestamp=datetime.now(UTC),
    )


def _result(value: int) -> FetchResult[list[dict[str, int]]]:
    return FetchResult(
        data=[{"value": value}],
        row_count=1,
        schema_id="phase2.schema",
        schema_version="1.0",
        version=_version(),
        fetched_at=datetime.now(UTC),
        completeness=1.0,
    )


class _Phase2Connector(BaseConnector[list[dict[str, int]]]):
    connector_id: ClassVar[str] = "phase2_mock"
    capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.FULL_FETCH
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="phase2_mock",
        version="1.0.0",
        namespace="test",
        source_name="Phase 2 Mock",
        source_organization="PolicyOS",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(ConnectorCapability.FULL_FETCH),
    )
    disconnect_count = 0

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return self._create_handle(config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        type(self).disconnect_count += 1

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        return HealthStatus(healthy=True)

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[list[dict[str, int]]]:
        return _result(1)


def test_connection_pool_close_release_contention_and_bounded_tracking() -> None:
    async def _run() -> None:
        _Phase2Connector.disconnect_count = 0
        pool = ConnectionPool(
            connector_factory=_Phase2Connector,
            config=ConnectionConfig(url="https://example.test", max_connections=2),
            pool_config=PoolConfig(
                max_size=2,
                acquire_timeout_seconds=0.2,
                max_lifecycle_session_ids=3,
                max_backpressure_signals=3,
            ),
        )
        handles = await asyncio.gather(pool.acquire(), pool.acquire())
        waiter = asyncio.create_task(pool.acquire())
        await asyncio.sleep(0)

        close_task = asyncio.create_task(pool.close_all())
        await asyncio.sleep(0)
        await asyncio.gather(
            pool.release(handles[0]),
            pool.release(handles[1]),
            close_task,
            pool.close_all(),
        )
        with pytest.raises(PoolClosedError):
            await waiter

        for index in range(8):
            pool.register_backpressure(
                source=f"source-{index}",
                level=BackpressureLevel.ELEVATED,
                reason="phase2-stress",
            )
        snapshot = pool.backpressure_snapshot()

        assert _Phase2Connector.disconnect_count == 2
        assert len(pool._released_session_ids) <= 3  # type: ignore[attr-defined]
        assert len(pool._closed_session_ids) <= 3  # type: ignore[attr-defined]
        assert len(snapshot.active_signals) == 3

    asyncio.run(_run())


def test_ttl_cache_policy_enforces_bounded_entries_under_thread_contention(tmp_path: Path) -> None:
    cache = ConnectorCacheStore(
        FileSystemCAS(tmp_path / ".polisyos"),
        TTLPolicy(ttl=timedelta(hours=1), max_entries=3),
    )

    def _put(index: int) -> None:
        cache.put(
            FetchRequest(dataset_id=f"phase2.dataset.{index}"),
            _result(index),
            connector_id="phase2.connector",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_put, range(24)))

    assert cache.stats().total_entries <= 3
    cache.close()


def test_cache_policy_registry_mappings_are_lru_bounded() -> None:
    registry = PolicyRegistry(
        max_connector_policy_mappings=2,
        max_dataset_policy_mappings=2,
    )

    for index in range(5):
        registry.set_connector_policy(f"connector-{index}", "default")
        registry.set_dataset_policy(f"dataset-{index}", "default")

    assert list(registry._connector_policies) == ["connector-3", "connector-4"]  # type: ignore[attr-defined]
    assert list(registry._dataset_policies) == ["dataset-3", "dataset-4"]  # type: ignore[attr-defined]


def test_prefetch_scheduler_connector_semaphores_are_lru_bounded(tmp_path: Path) -> None:
    scheduler = PrefetchScheduler(
        ConnectorCacheStore(
            FileSystemCAS(tmp_path / ".polisyos"),
            TTLPolicy(ttl=timedelta(minutes=5)),
        ),
        registry=None,
        max_connector_semaphores=2,
    )

    for index in range(6):
        scheduler._connector_semaphore(f"connector-{index}")  # type: ignore[attr-defined]

    assert list(scheduler._semaphores) == ["connector-4", "connector-5"]  # type: ignore[attr-defined]
    asyncio.run(scheduler.stop())


def test_connector_registry_connection_pools_are_lru_bounded() -> None:
    async def _run() -> None:
        _Phase2Connector.disconnect_count = 0
        registry = ConnectorRegistry()
        registry._max_connection_pools = 2  # type: ignore[attr-defined]
        registry.register(
            _Phase2Connector,
            config=ConnectionConfig(url="https://example.test/default", max_connections=1),
        )

        for index in range(3):
            config = ConnectionConfig(
                url=f"https://example.test/{index}",
                max_connections=1,
            )
            handle = await registry.get_connection("phase2_mock", config=config)
            await registry.release_connection("phase2_mock", handle)

        assert len(registry._connection_pools) == 2  # type: ignore[attr-defined]
        assert _Phase2Connector.disconnect_count >= 1
        await registry.shutdown_async()

    asyncio.run(_run())


def test_reference_connectors_reuse_handle_owned_http_sessions() -> None:
    async def _run() -> None:
        for connector in (SDMXConnector(), StaticCSVConnector()):
            handle = await connector.connect(ConnectionConfig(url="https://example.test"))
            first = await connector._get_session(handle)  # type: ignore[attr-defined]
            second = await connector._get_session(handle)  # type: ignore[attr-defined]

            assert first is second

            await connector.disconnect(handle)
            assert first.closed

    asyncio.run(_run())


def test_graphql_connector_reuses_handle_owned_http_session() -> None:
    async def _run() -> None:
        connector = GraphQLConnector()
        handle = await connector.connect(
            ConnectionConfig(
                url="https://example.test/graphql",
                headers={"X-GraphQL-Query": "query { records { id } }"},
            )
        )
        first = await connector._get_session(handle)  # type: ignore[attr-defined]
        second = await connector._get_session(handle)  # type: ignore[attr-defined]

        assert first is second

        await connector.disconnect(handle)
        assert first.closed

    asyncio.run(_run())


def test_rate_limiter_rejects_unserviceable_token_request() -> None:
    limiter = RateLimiter(rate_limit_rps=1.0, burst_size=1.0)

    async def _run() -> None:
        with pytest.raises(ValueError, match="burst_size"):
            await limiter.acquire(tokens=2.0)

    asyncio.run(_run())


def test_entity_resolver_bounds_pair_scan_and_candidate_state() -> None:
    records = [
        EntityRecord(
            entity_id=f"entity-{index}",
            canonical_name="Shared Name",
            source=f"source-{index % 3}",
        )
        for index in range(20)
    ]
    resolver = ProbabilisticEntityResolver(max_pairs=12, max_candidates=2)

    matches = resolver.resolve(records, min_confidence=0.0)

    assert len(matches) <= 2


def test_lineage_tracker_bounds_runtime_lookup_maps() -> None:
    tracker = FabricLineageTracker("phase2-lineage", max_tracked_nodes=2)

    tracker.register_source_dataset(
        connector_id="phase2",
        dataset_id="dataset",
        fields=[f"field_{index}" for index in range(6)],
    )

    assert len(tracker._current_field_nodes) == 2  # type: ignore[attr-defined]
    assert {"field_4", "field_5"} == set(tracker._current_field_nodes)  # type: ignore[attr-defined]
    assert len(tracker.graph.entities) >= 7


def test_source_profile_registry_is_locked_under_concurrent_registration() -> None:
    registry = SourceProfileRegistry()

    def _register(index: int) -> None:
        registry.register(
            SourceProfile(
                profile_id=f"profile_{index}",
                display_name=f"Profile {index}",
                connector_family="phase2",
                base_url=f"https://example.test/{index}",
            )
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_register, range(32)))

    assert len(registry.list_all()) == 32


def test_binding_profile_registry_is_locked_under_concurrent_registration() -> None:
    registry = BindingProfileRegistry()

    def _register(index: int) -> None:
        registry.register(
            BindingProfile(
                profile_id=f"profile_{index}",
                display_name=f"Profile {index}",
                schema_family="phase2",
            )
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_register, range(32)))

    assert len(registry.list_all()) == 32


def test_source_binding_registry_persists_atomically(tmp_path: Path) -> None:
    registry = SourceBindingRegistry(tmp_path, strict=False)
    registry.upsert(
        SourceBinding(
            metric_id="metric.phase2",
            connector_id="phase2.connector",
            dataset_id="phase2.dataset",
        )
    )

    registry.persist()
    reloaded = SourceBindingRegistry(tmp_path, strict=True)

    assert reloaded.stats()["docs_total"] == 1
    assert not list(tmp_path.rglob("*.tmp"))


def test_partial_segment_index_entry_fails_closed_instead_of_becoming_current(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "world" / "_segments.jsonl"
    index_path.parent.mkdir(parents=True)
    index_path.write_text(
        "\n".join(
            [
                (
                    '{"segment_id":"stable","path":"/tmp/stable.parquet",'
                    '"row_count":1,"sha256":"' + ("a" * 64) + '"}'
                ),
                '{"segment_id":"partial"',
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(WorldSegmentError):
        load_world_fact_manifests(tmp_path)
