import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

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
    PrefetchJob,
    PrefetchScheduler,
    SizeBoundedPolicy,
    SmartExpiryPolicy,
    TTLPolicy,
)
from polisyos.fabric.connectors.cache.store import ResultSerializer
from polisyos.fabric.security import ArtifactGovernanceError, DataClassification
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


class _CounterStub:
    def __init__(self) -> None:
        self.calls: list[tuple[int | float, dict[str, str]]] = []

    def add(self, value: int | float, attrs: dict[str, str]) -> None:
        self.calls.append((value, dict(attrs)))


class _HistogramStub:
    def __init__(self) -> None:
        self.calls: list[tuple[int | float, dict[str, str]]] = []

    def record(self, value: int | float, attrs: dict[str, str]) -> None:
        self.calls.append((value, dict(attrs)))


class _GaugeStub:
    def __init__(self) -> None:
        self.calls: list[tuple[float, dict[str, str]]] = []

    def set(self, value: float, attrs: dict[str, str]) -> None:
        self.calls.append((value, dict(attrs)))


class _SpanStub:
    def __enter__(self) -> "_SpanStub":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def set_attribute(self, key: str, value: object) -> None:
        del key, value

    def set_status(self, status: object) -> None:
        del status

    def record_exception(self, exc: BaseException) -> None:
        del exc


class _TracerStub:
    def __init__(self) -> None:
        self.names: list[str] = []

    def start_as_current_span(self, name: str, attributes=None):  # noqa: ANN001
        del attributes
        self.names.append(name)
        return _SpanStub()


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


def test_cache_store_context_manager_closes_index(tmp_path):
    cas = FileSystemCAS(tmp_path / ".polisyos")
    policy = TTLPolicy(ttl=timedelta(hours=1))
    with ConnectorCacheStore(cas, policy) as cache_store:
        request = FetchRequest(dataset_id="test.context")
        cache_store.put(request, _make_result({"x": 1}), connector_id="test.connector")

    assert cache_store.closed
    with pytest.raises(RuntimeError, match="closed"):
        cache_store.stats()


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


def test_cache_hit_rate_is_atomic_under_concurrency(tmp_path) -> None:
    cache = ConnectorCacheStore(
        FileSystemCAS(tmp_path / ".polisyos"),
        TTLPolicy(ttl=timedelta(hours=1)),
    )
    hit_request = FetchRequest(dataset_id="test.hit")
    miss_request = FetchRequest(dataset_id="test.miss")
    stale_request = FetchRequest(dataset_id="test.stale")

    cache.put(hit_request, _make_result({"x": 1}), connector_id="test.connector")
    cache.put(stale_request, _make_result({"x": 2}), connector_id="test.connector")
    cache.invalidate(dataset_id="test.stale")

    def _hit() -> bool:
        return cache.get(hit_request, connector_id="test.connector") is not None

    def _miss() -> bool:
        return cache.get(miss_request, connector_id="test.connector") is None

    with ThreadPoolExecutor(max_workers=8) as pool:
        hit_results = list(pool.map(lambda _idx: _hit(), range(24)))
        miss_results = list(pool.map(lambda _idx: _miss(), range(16)))

    before_stale_misses = cache._miss_count  # type: ignore[attr-defined]
    assert cache.get(stale_request, connector_id="test.connector") is None
    after_stale_misses = cache._miss_count  # type: ignore[attr-defined]

    assert all(hit_results)
    assert all(miss_results)
    assert after_stale_misses == before_stale_misses + 1

    stats = cache.stats()
    expected_hits = 24
    expected_misses = 17
    assert cache._hit_count == expected_hits  # type: ignore[attr-defined]
    assert cache._miss_count == expected_misses  # type: ignore[attr-defined]
    assert stats.hit_rate == pytest.approx(expected_hits / (expected_hits + expected_misses))


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


def test_size_bounded_eviction_keeps_store_under_limit(tmp_path):
    first_result = _make_result({"blob": "a" * 1024})
    second_result = _make_result({"blob": "b" * 1024})
    first_payload, _ = ResultSerializer.serialize(first_result)
    second_payload, _ = ResultSerializer.serialize(second_result)
    limit_bytes = len(first_payload) + len(second_payload) - 1

    cas = FileSystemCAS(tmp_path / ".polisyos")
    cache = ConnectorCacheStore(
        cas,
        SizeBoundedPolicy(max_size_gb=limit_bytes / float(1024 ** 3)),
    )
    req1 = FetchRequest(dataset_id="test.one")
    req2 = FetchRequest(dataset_id="test.two")

    cache.put(req1, first_result, connector_id="test.connector")
    cache.put(req2, second_result, connector_id="test.connector")

    stats = cache.stats()
    assert stats.total_size_bytes <= limit_bytes
    assert cache.get(req1, connector_id="test.connector") is None
    assert cache.get(req2, connector_id="test.connector") is not None


def test_cache_put_records_governance_manifest(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path / ".polisyos")
    cache = ConnectorCacheStore(cas, TTLPolicy(ttl=timedelta(hours=1)))
    request = FetchRequest(dataset_id="test.governed")

    metadata = cache.put(
        request,
        _make_result({"ssn": ["123-45-6789"]}),
        connector_id="test.connector",
        classification=DataClassification.INTERNAL,
        column_classification={"ssn": DataClassification.REGULATED_PII},
        encrypted_at_rest=True,
        encryption_key_reference="kms://fabric/cache",
    )

    payload_manifest = cas.get_manifest(metadata.payload_artifact_id)
    assert metadata.metadata_artifact_id is not None
    metadata_manifest = cas.get_manifest(metadata.metadata_artifact_id)

    assert payload_manifest.governance is not None
    assert payload_manifest.governance.classification == "internal"
    assert payload_manifest.governance.column_classification == {"ssn": "regulated_pii"}
    assert payload_manifest.governance.retention is not None
    assert payload_manifest.governance.retention.scope == "cache"
    assert metadata_manifest.governance is not None
    assert metadata_manifest.governance.encryption is not None
    assert metadata_manifest.governance.encryption.mode == "none"


def test_cache_put_fails_closed_when_policy_requires_field_level_encryption(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path / ".polisyos")
    cache = ConnectorCacheStore(cas, TTLPolicy(ttl=timedelta(hours=1)))
    request = FetchRequest(dataset_id="test.pii")

    with pytest.raises(ArtifactGovernanceError, match="field-level encryption"):
        cache.put(
            request,
            _make_result({"email": ["user@example.com"]}),
            connector_id="test.connector",
            classification=DataClassification.REGULATED_PII,
        )


def test_smart_expiry_policy_treats_future_windows_as_short_lived():
    policy = SmartExpiryPolicy()
    request = FetchRequest(
        dataset_id="test.stream",
        date_start=datetime.now(timezone.utc) - timedelta(hours=1),
        date_end=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    expires_at = policy.compute_expiry(request, _make_result({"x": 1}))
    ttl = expires_at - datetime.now(timezone.utc)

    assert ttl <= timedelta(minutes=6)


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


def test_cache_components_use_injected_observability(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = SimpleNamespace(
        connector_cache_operations_total=_CounterStub(),
        connector_cache_latency_seconds=_HistogramStub(),
        connector_cache_entries_total=_GaugeStub(),
        connector_cache_size_bytes=_GaugeStub(),
        connector_cache_hit_rate=_GaugeStub(),
        set_fabric_prefetch_backlog=lambda value: None,
    )
    tracer = _TracerStub()

    monkeypatch.setattr(
        "polisyos.fabric.connectors.cache._store_core.get_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global cache metrics should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.fabric.connectors.cache._store_core.get_tracer",
        lambda: (_ for _ in ()).throw(AssertionError("global cache tracer should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.fabric.connectors.cache.proxy.get_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global proxy metrics should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.fabric.connectors.cache.prefetch.get_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global prefetch metrics should not be used")),
    )

    class MockConnector:
        connector_id = "test.mock"
        capabilities = ConnectorCapability.FULL_FETCH
        metadata = None

        async def fetch(self, handle, request):
            del handle, request
            return _make_result({"value": 1})

        async def connect(self, config):
            del config
            return None

        async def disconnect(self, handle):
            del handle
            return None

        async def health_check(self, handle):
            del handle
            return None

    async def _run() -> None:
        cache_store = ConnectorCacheStore(
            FileSystemCAS(tmp_path / ".polisyos"),
            TTLPolicy(ttl=timedelta(hours=1)),
            metrics=metrics,
            tracer=tracer,
        )
        proxy = CachingConnectorProxy(
            MockConnector(),
            cache_store,
            metrics=metrics,
        )
        request = FetchRequest(dataset_id="test.dataset")
        await proxy.fetch(None, request)
        await proxy.fetch(None, request)

        scheduler = PrefetchScheduler(
            cache_store,
            registry=None,
            prefetch_window_minutes=10,
            metrics=metrics,
        )
        await scheduler._schedule_expiring_entries()
        await scheduler.stop()

        assert tracer.names
        assert metrics.connector_cache_operations_total.calls
        assert metrics.connector_cache_entries_total.calls

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


def test_invalidation_orchestrator_uses_file_signatures(tmp_path):
    source_file = tmp_path / "dataset.json"
    source_file.write_text('{"value": 1}', encoding="utf-8")

    class MockConnector:
        connector_id = "test.mock"
        capabilities = ConnectorCapability.FULL_FETCH
        metadata = None

        async def fetch(self, handle, request):
            return _make_result({"x": 1})

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
                config=ConnectionConfig(url="file:///tmp"),
            )

        async def release_connection(self, connector_id, handle):
            return None

    async def _run():
        cas = FileSystemCAS(tmp_path / ".polisyos")
        cache_store = ConnectorCacheStore(cas, TTLPolicy(ttl=timedelta(hours=1)))
        request = FetchRequest(dataset_id=str(source_file))
        cache_store.put(request, _make_result({"x": 1}), connector_id="test.mock")

        source_file.write_text('{"value": 2, "extra": true}', encoding="utf-8")
        orchestrator = InvalidationOrchestrator(cache_store, MockRegistry(MockConnector()), InvalidationTrigger())

        events = await orchestrator.scan_and_invalidate()
        assert len(events) == 1
        assert events[0].trigger_type == "file_signature"
        assert cache_store.get(request, connector_id="test.mock") is None

    asyncio.run(_run())


def test_invalidation_orchestrator_does_not_leak_handle_on_acquire_failure(tmp_path):
    class MockConnector:
        connector_id = "test.mock"
        capabilities = ConnectorCapability.FULL_FETCH
        metadata = None

        async def fetch(self, handle, request):
            return _make_result({"x": 1})

        async def connect(self, config):
            return None

        async def disconnect(self, handle):
            return None

        async def health_check(self, handle):
            return None

    class MockRegistry:
        def __init__(self):
            self.release_calls = 0

        def get(self, connector_id):
            return MockConnector()

        async def get_connection(self, connector_id):
            raise RuntimeError("boom")

        async def release_connection(self, connector_id, handle):
            self.release_calls += 1

    async def _run():
        cas = FileSystemCAS(tmp_path / ".polisyos")
        cache_store = ConnectorCacheStore(cas, TTLPolicy(ttl=timedelta(hours=1)))
        request = FetchRequest(dataset_id="test.dataset")
        cache_store.put(request, _make_result({"x": 1}), connector_id="test.mock")

        registry = MockRegistry()
        orchestrator = InvalidationOrchestrator(cache_store, registry, InvalidationTrigger())
        events = await orchestrator.scan_and_invalidate()

        assert events == []
        assert registry.release_calls == 0

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


def test_prefetch_scheduler_stop_cancels_requeue_tasks(tmp_path):
    cas = FileSystemCAS(tmp_path / ".polisyos")
    scheduler = PrefetchScheduler(
        ConnectorCacheStore(cas, TTLPolicy(ttl=timedelta(minutes=5))),
        registry=None,
        backoff_seconds=60.0,
    )
    job = PrefetchJob(
        dataset_id="test.dataset",
        connector_id="test.connector",
        request=FetchRequest(dataset_id="test.dataset"),
        cache_key="cache-key",
    )

    async def _run():
        await scheduler._maybe_retry(job)
        assert scheduler._requeue_tasks
        await scheduler.stop()
        assert not scheduler._requeue_tasks
        assert scheduler._queue.empty()
        assert not scheduler._queue_keys
        assert not scheduler._inflight_keys

    asyncio.run(_run())


def test_prefetch_scheduler_dedupes_jobs_without_explicit_cache_key(tmp_path):
    cas = FileSystemCAS(tmp_path / ".polisyos")
    scheduler = PrefetchScheduler(
        ConnectorCacheStore(cas, TTLPolicy(ttl=timedelta(minutes=5))),
        registry=None,
        max_queued_jobs=2,
    )
    request = FetchRequest(dataset_id="test.dataset")
    first = PrefetchJob(
        dataset_id="test.dataset",
        connector_id="test.connector",
        request=request,
        cache_key=None,
    )
    second = PrefetchJob(
        dataset_id="test.dataset",
        connector_id="test.connector",
        request=request,
        cache_key=None,
    )

    async def _run():
        assert await scheduler._enqueue_job(first) is True
        assert await scheduler._enqueue_job(second) is False
        assert scheduler._queue.qsize() == 1
        await scheduler.stop()

    asyncio.run(_run())
