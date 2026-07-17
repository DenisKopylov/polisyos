"""Behavioral tests for the raw connector-result sink boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle
from polisyos.fabric.connectors.cache.store import ConnectorCacheStore
from polisyos.fabric.ingestion import IngestionDependencies, run_connectors_ingestion
from polisyos.fabric.ingestion.ingestion import _sync_fetch
from polisyos.ir.connectors import (
    DataVersion,
    FetchRequest,
    FetchResult,
    QualityTier,
    VersionStrategy,
)

if TYPE_CHECKING:
    from pathlib import Path


class _Span:
    def __enter__(self) -> _Span:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        del exc_type, exc, tb
        return False

    def set_attribute(self, key: str, value: object) -> None:
        del key, value


class _Tracer:
    def start_as_current_span(
        self,
        name: str,
        *,
        attributes: dict[str, object] | None = None,
    ) -> _Span:
        del name, attributes
        return _Span()


class _Registry:
    def __init__(self) -> None:
        self.connector = SimpleNamespace(metadata=None)

    def get(self, connector_id: str) -> object:
        assert connector_id == "test.connector"
        return self.connector


class _Metrics:
    pass


def _raw_result() -> FetchResult[list[dict[str, int]]]:
    now = datetime.now(UTC)
    digest = "sha256:" + ("a" * 64)
    return FetchResult(
        data=[{"value": 1}],
        row_count=1,
        schema_id="test.raw",
        schema_version="1.0.0",
        version=DataVersion(
            strategy=VersionStrategy.CONTENT_HASH,
            value=digest,
            timestamp=now,
            content_hash=digest,
        ),
        fetched_at=now,
        completeness=1.0,
        quality_tier=QualityTier.BRONZE,
    )


def _dependencies(cas_root: Path) -> IngestionDependencies:
    return IngestionDependencies(
        registry=_Registry(),  # type: ignore[arg-type]
        tracer=_Tracer(),  # type: ignore[arg-type]
        metrics=_Metrics(),  # type: ignore[arg-type]
        store_factory=lambda _root: FileSystemCAS(cas_root),
    )


def _manifest(*dataset_ids: str) -> dict[str, object]:
    requested_ids = dataset_ids or ("raw.dataset",)
    return {
        "datasets": [
            {"connector_id": "test.connector", "dataset_id": dataset_id}
            for dataset_id in requested_ids
        ],
        "transform_dag": "test-pipeline",
    }


def test_raw_result_sink_runs_once_before_transform_sanitize_and_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _raw_result()
    events: list[str] = []
    seen: list[tuple[str, str, FetchRequest, FetchResult[Any]]] = []

    class _HTTPObserver:
        max_response_bytes = 1024
        max_decompressed_bytes = 2048

        def before_request(
            self,
            connector_id: str,
            url: str,
            params: dict[str, str],
        ) -> None:
            del connector_id, url, params
            events.append("http_before")

        def on_raw_response(
            self,
            connector_id: str,
            url: str,
            params: dict[str, str],
            status_code: int,
            headers: dict[str, str],
            body: bytes,
        ) -> None:
            del connector_id, url, params, status_code, headers, body
            events.append("http_raw")

    http_observer = _HTTPObserver()

    def _fetch(
        registry: object,
        connector_id: str,
        connector: object,
        request: FetchRequest,
        **kwargs: object,
    ) -> FetchResult[Any]:
        del registry, connector
        assert kwargs["raw_http_response_observer"] is http_observer
        http_observer.before_request(connector_id, "https://example.test", {})
        http_observer.on_raw_response(
            connector_id,
            "https://example.test",
            {},
            200,
            {},
            b"{}",
        )
        assert request.dataset_id.startswith("raw.dataset")
        events.append("fetch")
        return raw

    def _sink(
        connector_id: str,
        dataset_id: str,
        request: FetchRequest,
        result: FetchResult[Any],
    ) -> None:
        events.append("sink")
        seen.append((connector_id, dataset_id, request, result))

    def _transform(
        result: FetchResult[Any],
        pipeline: object,
        **kwargs: object,
    ) -> tuple[FetchResult[Any], None, list[str], int]:
        del pipeline, kwargs
        events.append("transform")
        assert result is raw
        return result, None, [], 0

    def _sanitize(
        result: FetchResult[Any],
        **kwargs: object,
    ) -> tuple[FetchResult[Any], list[str], int]:
        del kwargs
        events.append("sanitize")
        return result, [], 0

    original_cache_put = ConnectorCacheStore.put

    def _cache_put(self: ConnectorCacheStore, *args: object, **kwargs: object) -> object:
        events.append("cache")
        return original_cache_put(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("polisyos.fabric.ingestion.ingestion._sync_fetch", _fetch)
    monkeypatch.setattr(
        "polisyos.fabric.ingestion.ingestion._load_transform_pipeline",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        "polisyos.fabric.ingestion.ingestion._apply_transform_pipeline",
        _transform,
    )
    monkeypatch.setattr(
        "polisyos.fabric.ingestion.ingestion._sanitize_fetch_result",
        _sanitize,
    )
    monkeypatch.setattr(
        "polisyos.fabric.pii.PIIDetectionStage.from_env",
        lambda: None,
    )
    monkeypatch.setattr(ConnectorCacheStore, "put", _cache_put)

    result = run_connectors_ingestion(
        connector_manifest=_manifest("raw.dataset", "raw.dataset.second"),
        source="test",
        license_name="CC-BY-4.0",
        cas_root=tmp_path / "cas",
        dependencies=_dependencies(tmp_path / "cas"),
        raw_result_sink=_sink,
        raw_http_response_observer=http_observer,
    )

    assert result is not None
    assert events == [
        "http_before",
        "http_raw",
        "fetch",
        "sink",
        "transform",
        "sanitize",
        "cache",
        "http_before",
        "http_raw",
        "fetch",
        "sink",
        "transform",
        "sanitize",
        "cache",
    ]
    assert len(seen) == 2
    assert [dataset_id for _, dataset_id, _, _ in seen] == [
        "raw.dataset",
        "raw.dataset.second",
    ]
    for connector_id, dataset_id, request, sink_result in seen:
        assert connector_id == "test.connector"
        assert request.dataset_id == dataset_id
        assert sink_result is raw


def test_raw_result_sink_failure_prevents_all_downstream_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _raw_result()
    sink_calls = 0

    def _sink(*args: object) -> None:
        nonlocal sink_calls
        del args
        sink_calls += 1
        raise RuntimeError("journal unavailable")

    def _must_not_run(*args: object, **kwargs: object) -> None:
        del args, kwargs
        pytest.fail("downstream processing ran after the raw-result sink failed")

    monkeypatch.setattr(
        "polisyos.fabric.ingestion.ingestion._sync_fetch",
        lambda *args, **kwargs: raw,
    )
    monkeypatch.setattr(
        "polisyos.fabric.ingestion.ingestion._load_transform_pipeline",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        "polisyos.fabric.ingestion.ingestion._apply_transform_pipeline",
        _must_not_run,
    )
    monkeypatch.setattr(
        "polisyos.fabric.ingestion.ingestion._sanitize_fetch_result",
        _must_not_run,
    )
    monkeypatch.setattr(ConnectorCacheStore, "put", _must_not_run)
    monkeypatch.setattr(
        "polisyos.fabric.ingestion.ingestion.persist_provenance_graph",
        _must_not_run,
    )
    monkeypatch.setattr(
        "polisyos.fabric.ingestion.ingestion.persist_evidence_bundle",
        _must_not_run,
    )

    with pytest.raises(RuntimeError, match="journal unavailable"):
        run_connectors_ingestion(
            connector_manifest=_manifest(),
            source="test",
            license_name="CC-BY-4.0",
            cas_root=tmp_path / "cas",
            dependencies=_dependencies(tmp_path / "cas"),
            raw_result_sink=_sink,
        )

    assert sink_calls == 1


def test_sync_fetch_removes_http_observer_from_handle_when_fetch_fails() -> None:
    config = ConnectionConfig(url="https://example.test")
    handle = ConnectionHandle(connector_id="test.connector", config=config)
    observer = object()
    release_calls = 0

    class _HandleRegistry:
        async def get_connection(
            self,
            connector_id: str,
            connection_config: ConnectionConfig,
        ) -> ConnectionHandle:
            assert connector_id == "test.connector"
            assert connection_config is config
            return handle

        async def release_connection(
            self,
            connector_id: str,
            released_handle: ConnectionHandle,
        ) -> None:
            nonlocal release_calls
            assert connector_id == "test.connector"
            assert released_handle is handle
            assert observer not in released_handle.state.values()
            release_calls += 1

    class _FailingConnector:
        async def fetch(
            self,
            fetch_handle: ConnectionHandle,
            request: FetchRequest,
        ) -> FetchResult[Any]:
            del request
            assert observer in fetch_handle.state.values()
            raise RuntimeError("fetch failed")

    with pytest.raises(RuntimeError, match="fetch failed"):
        _sync_fetch(
            _HandleRegistry(),  # type: ignore[arg-type]
            "test.connector",
            _FailingConnector(),
            FetchRequest(dataset_id="raw.dataset"),
            connection_config=config,
            raw_http_response_observer=observer,  # type: ignore[arg-type]
        )

    assert observer not in handle.state.values()
    assert release_calls == 1
