import asyncio
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.fabric.connectors.base import FetchRequest, FetchResult
from polisyos.fabric.connectors.cache import (
    CachingConnectorProxy,
    ConnectorCacheStore,
    InvalidationOrchestrator,
    InvalidationTrigger,
    LRUPolicy,
    PrefetchScheduler,
    TTLPolicy,
)
from polisyos.fabric.connectors.cache.store import ResultSerializer
from polisyos.ir.connectors import (
    ConnectorCapability,
    DataVersion,
    PIIDetectedEntity,
    PIIScanSummary,
    QualityTier,
    VersionStrategy,
)
from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle
from polisyos.fabric.connectors.types import FreshnessResult, FreshnessStatus


def _make_version() -> DataVersion:
    return DataVersion(
        strategy=VersionStrategy.TIMESTAMP,
        value="now",
        timestamp=datetime.now(timezone.utc),
    )


def _make_result(data, *, bytes_transferred: int = 0) -> FetchResult:
    return FetchResult(
        data=data,
        row_count=len(data) if hasattr(data, "__len__") else 1,
        schema_id="test.schema",
        schema_version="1.0",
        version=_make_version(),
        fetched_at=datetime.now(timezone.utc),
        completeness=1.0,
        quality_tier=QualityTier.SILVER,
        bytes_transferred=bytes_transferred,
    )


@pytest.fixture()
def cache(tmp_path):
    cas = FileSystemCAS(tmp_path / ".polisyos")
    policy = TTLPolicy(ttl=timedelta(hours=1))
    return ConnectorCacheStore(cas, policy)


def test_put_get_roundtrip(cache):
    df = pd.DataFrame({"x": [1, 2, 3]})
    request = FetchRequest(dataset_id="test.dataset")
    result = _make_result(df, bytes_transferred=999999)

    metadata = cache.put(request, result, connector_id="test.connector")
    cached = cache.get(request, connector_id="test.connector")

    assert cached is not None
    pd.testing.assert_frame_equal(cached.result.data, df)
    assert metadata.payload_size_bytes != result.bytes_transferred
    data_bytes, _ = ResultSerializer.serialize(result)
    assert metadata.payload_size_bytes == len(data_bytes)


def test_result_serializer_roundtrip_with_pii_scan() -> None:
    result = _make_result(pd.DataFrame({"email": ["john@example.com"]}))
    result = result.model_copy(
        update={
            "pii_scan": PIIScanSummary(
                total_records_scanned=1,
                total_entities_found=1,
                max_severity="medium",
                entities_by_type={"EMAIL_ADDRESS": 1},
                entities_by_severity={"medium": 1},
                entities=[
                    PIIDetectedEntity(
                        entity_type="EMAIL_ADDRESS",
                        severity="medium",
                        score=0.99,
                        column="email",
                        start=0,
                        end=16,
                        redacted_text="***",
                    )
                ],
                scan_duration_ms=5.0,
                sampled=False,
                sample_rate=1.0,
            )
        }
    )

    payload, _ = ResultSerializer.serialize(result)
    restored = ResultSerializer.deserialize(payload)
    assert restored.pii_scan is not None
    assert restored.pii_scan.total_entities_found == 1
    assert restored.pii_scan.max_severity == "medium"


def test_expired_entry_returns_none(tmp_path):
    cas = FileSystemCAS(tmp_path / ".polisyos")
    policy = TTLPolicy(ttl=timedelta(seconds=1))
    cache = ConnectorCacheStore(cas, policy)

    request = FetchRequest(dataset_id="test.expiring")
    result = _make_result(pd.DataFrame({"x": [1]}))

    cache.put(request, result, connector_id="test.connector")
    assert cache.get(request, connector_id="test.connector") is not None

    time.sleep(1.5)
    assert cache.get(request, connector_id="test.connector") is None


def test_cache_key_stability(cache):
    req1 = FetchRequest(
        dataset_id="test",
        filters=(("country", ("USA", "DEU")),),
    )
    req2 = FetchRequest(
        dataset_id="test",
        filters=(("country", ("DEU", "USA")),),
    )

    assert req1.cache_key == req2.cache_key

    cache.put(req1, _make_result({"x": 1}), connector_id="test.connector")
    cached = cache.get(req2, connector_id="test.connector")
    assert cached is not None


def test_soft_invalidation_marks_stale(cache):
    request = FetchRequest(dataset_id="test.dataset")
    cache.put(request, _make_result({"x": 1}), connector_id="test.connector")

    assert cache.get(request, connector_id="test.connector") is not None
    count = cache.invalidate("soft_mark", dataset_id="test.dataset")
    assert count == 1
    assert cache.get(request, connector_id="test.connector") is None


def test_hard_delete_removes_entry(cache):
    request = FetchRequest(dataset_id="test.dataset")
    cache.put(request, _make_result({"x": 1}), connector_id="test.connector")

    count = cache.hard_delete(dataset_id="test.dataset")
    assert count == 1
    assert cache.get(request, connector_id="test.connector") is None


def test_lru_eviction(tmp_path):
    cas = FileSystemCAS(tmp_path / ".polisyos")
    policy = LRUPolicy(max_entries=1)
    cache = ConnectorCacheStore(cas, policy)

    req1 = FetchRequest(dataset_id="test.one")
    req2 = FetchRequest(dataset_id="test.two")

    cache.put(req1, _make_result({"x": 1}), connector_id="test.connector")
    cache.put(req2, _make_result({"x": 2}), connector_id="test.connector")

    assert cache.get(req1, connector_id="test.connector") is None
    assert cache.get(req2, connector_id="test.connector") is not None


def test_caching_connector_proxy(tmp_path):
    class MockConnector:
        connector_id = "test.mock"
        capabilities = ConnectorCapability.FULL_FETCH
        metadata = None

        def __init__(self):
            self.fetch_count = 0

        async def fetch(self, handle, request):
            self.fetch_count += 1
            return _make_result({"count": self.fetch_count})

        async def connect(self, config):
            return None

        async def disconnect(self, handle):
            return None

        async def health_check(self, handle):
            return None

    async def _run():
        cas = FileSystemCAS(tmp_path / ".polisyos")
        cache_store = ConnectorCacheStore(cas, TTLPolicy(ttl=timedelta(hours=1)))
        connector = MockConnector()
        proxy = CachingConnectorProxy(connector, cache_store)

        request = FetchRequest(dataset_id="test.dataset")
        await proxy.fetch(None, request)
        await proxy.fetch(None, request)

        assert connector.fetch_count == 1
        assert proxy.hit_rate == 0.5

    asyncio.run(_run())


def test_invalidation_orchestrator(tmp_path):
    class MockConnector:
        connector_id = "test.mock"
        capabilities = ConnectorCapability.FRESHNESS_CHECK
        metadata = None

        async def fetch(self, handle, request):
            return _make_result({"x": 1})

        async def check_freshness(self, handle, dataset_id, cached_version):
            return FreshnessResult(status=FreshnessStatus.STALE, message="stale")

        async def connect(self, config):
            return None

        async def disconnect(self, handle):
            return None

        async def health_check(self, handle):
            return None

    class MockRegistry:
        def __init__(self, connector):
            self._connector = connector

        def get(self, connector_id):
            return self._connector

        async def get_connection(self, connector_id):
            return ConnectionHandle(
                connector_id=connector_id,
                config=ConnectionConfig(url="http://example.com"),
            )

        async def release_connection(self, connector_id, handle):
            return None

    async def _run():
        cas = FileSystemCAS(tmp_path / ".polisyos")
        cache_store = ConnectorCacheStore(cas, TTLPolicy(ttl=timedelta(hours=1)))
        request = FetchRequest(dataset_id="test.dataset")
        cache_store.put(request, _make_result({"x": 1}), connector_id="test.mock")

        registry = MockRegistry(MockConnector())
        orchestrator = InvalidationOrchestrator(cache_store, registry, InvalidationTrigger())

        events = await orchestrator.scan_and_invalidate()
        assert len(events) == 1
        assert cache_store.get(request, connector_id="test.mock") is None

    asyncio.run(_run())


def test_prefetch_scheduler_enqueues(tmp_path):
    cas = FileSystemCAS(tmp_path / ".polisyos")
    policy = TTLPolicy(ttl=timedelta(minutes=5))
    cache_store = ConnectorCacheStore(cas, policy)

    request = FetchRequest(dataset_id="test.dataset")
    cache_store.put(request, _make_result({"x": 1}), connector_id="test.connector")

    scheduler = PrefetchScheduler(cache_store, registry=None, prefetch_window_minutes=10)

    async def _run():
        await scheduler._schedule_expiring_entries()
        assert scheduler._queue.qsize() >= 1

    asyncio.run(_run())
