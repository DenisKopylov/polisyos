"""Tests for data-plane execution modes."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactID
from polisyos.fabric.connectors.contracts import (
    DataSchema,
    FieldSpec,
    SchemaType,
    SchemaVersion,
)


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
        return SimpleNamespace(
            artifact_id=ArtifactID.model_validate("sha256:" + "b" * 64)
        )

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
    assert record_ref == "sha256:" + "b" * 64


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


def test_run_replay_mode_does_not_fallback_to_live_after_fixture_failure(
    monkeypatch,
    tmp_path,
) -> None:
    """A missing/corrupt replay fixture must not invoke ordinary ingestion."""
    from polisyos.fabric.data_plane import modes as modes_mod

    async def _fail_replay_ingestion(
        func: Any,
        /,
        *args: Any,
        timeout_seconds: float | None = None,
        **kwargs: Any,
    ) -> Any:
        del func, args, timeout_seconds, kwargs
        raise RuntimeError("replay fixture missing")

    live_calls: list[bool] = []

    def _live_delegate(**kwargs: Any) -> Any:
        del kwargs
        live_calls.append(True)
        raise AssertionError("ordinary ingestion must not run in replay mode")

    monkeypatch.setattr(modes_mod, "run_blocking_async", _fail_replay_ingestion)
    monkeypatch.setattr(
        "polisyos.fabric.connectors.testing.simulator.APISimulator",
        _NoopSimulator,
    )
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.replay_store.ReplayStore",
        _ReplayStoreStub,
    )
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
        _live_delegate,
    )

    with pytest.raises(RuntimeError, match="replay fixture missing"):
        modes_mod.run_replay_mode(
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

    assert live_calls == []



def _make_real_replay_case(tmp_path, fixture_body: bytes | None):
    import base64
    from datetime import UTC, datetime
    from typing import cast

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle
    from polisyos.fabric.connectors.testing.simulator import (
        SimulatorFixture,
        _canonicalize_url,
        _request_hash,
    )
    from polisyos.fabric.data_plane.replay_store import RecordSession, ReplayStore
    from polisyos.fabric.ingestion import resolve_ingestion_dependencies
    from polisyos.ir.connectors import DataVersion, FetchResult, QualityTier, VersionStrategy

    connector_id = "test.http_replay"
    dataset_id = "rows"
    url = "https://replay-fixture.invalid/data"
    canonical_url = _canonicalize_url(url, None)
    request_hash = _request_hash("GET", canonical_url, "none", b"")
    fixtures = []
    if fixture_body is not None:
        fixtures.append(
            SimulatorFixture(
                status_code=200,
                headers={"Content-Type": "application/json"},
                body=base64.b64encode(fixture_body).decode("ascii"),
                captured_at="2026-09-26T00:00:00+00:00",
                request_url=canonical_url,
                request_method="GET",
                request_hash=request_hash,
                connector_id=connector_id,
                dataset_id=dataset_id,
            ).to_dict()
        )
    cas_root = tmp_path / "cas"
    replay_ref = ReplayStore(FileSystemCAS(cas_root)).save_record_session(
        RecordSession(session_id="test-replay-session", fixtures=fixtures)
    )

    class _HTTPFixtureConnector:
        metadata = None

        async def fetch(self, handle, request):
            import aiohttp

            del request
            async with aiohttp.ClientSession() as session:
                async with session.get(handle.config.url) as response:
                    rows = await response.json()
            now = datetime.now(UTC)
            digest = "sha256:" + "a" * 64
            return FetchResult(
                data=rows,
                row_count=len(rows),
                schema_id="test.http-replay",
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

    class _Registry:
        def get(self, requested_connector_id: str) -> _HTTPFixtureConnector:
            assert requested_connector_id == connector_id
            return _HTTPFixtureConnector()

        async def get_connection(
            self,
            requested_connector_id: str,
            config: ConnectionConfig,
        ) -> ConnectionHandle:
            return ConnectionHandle(connector_id=requested_connector_id, config=config)

        async def release_connection(
            self,
            requested_connector_id: str,
            handle: ConnectionHandle,
        ) -> None:
            del requested_connector_id, handle

    return {
        "cas_root": cas_root,
        "replay_ref": str(replay_ref.artifact_id),
        "dependencies": resolve_ingestion_dependencies(registry=cast("Any", _Registry())),
        "connection_config": ConnectionConfig(url=url),
        "connector_id": connector_id,
        "dataset_id": dataset_id,
        "url": url,
        "canonical_url": canonical_url,
    }


def _capture_replay_boundaries(monkeypatch):
    import aiohttp

    from polisyos.fabric.connectors.testing import simulator as simulator_mod

    simulators = []
    native_requests: list[tuple[str, str]] = []
    ordinary_ingestion_calls: list[bool] = []
    actual_simulator = simulator_mod.APISimulator

    def _capture_simulator(**kwargs):
        simulator = actual_simulator(**kwargs)
        simulators.append(simulator)
        return simulator

    async def _forbid_native_request(self, method: str, url: str, **kwargs):
        del self, kwargs
        native_requests.append((method, url))
        raise AssertionError("native transport must not run outside replay simulation")

    def _ordinary_ingestion(**kwargs):
        del kwargs
        ordinary_ingestion_calls.append(True)
        raise AssertionError("replay must not call ordinary ingestion")

    monkeypatch.setattr(aiohttp.ClientSession, "_request", _forbid_native_request)
    monkeypatch.setattr(simulator_mod, "APISimulator", _capture_simulator)
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
        _ordinary_ingestion,
    )
    return simulators, native_requests, ordinary_ingestion_calls


@pytest.mark.parametrize(
    ("fixture_body", "expected_error"),
    [
        (None, "missing"),
        (b"not-json", "corrupt"),
    ],
    ids=["missing-fixture", "corrupt-fixture"],
)
def test_run_replay_mode_fixture_failure_stays_in_replay_transport(
    monkeypatch,
    tmp_path,
    fixture_body,
    expected_error,
) -> None:
    """Real replay owner fails closed through the simulator, without live egress."""
    import json

    from polisyos.fabric.connectors.testing.simulator import MissingFixtureError
    from polisyos.fabric.data_plane import modes as modes_mod

    case = _make_real_replay_case(tmp_path, fixture_body)
    simulators, native_requests, ordinary_calls = _capture_replay_boundaries(monkeypatch)
    error_type = MissingFixtureError if expected_error == "missing" else json.JSONDecodeError

    with pytest.raises(error_type):
        modes_mod.run_replay_mode(
            connector_manifest={
                "datasets": [
                    {
                        "connector_id": case["connector_id"],
                        "dataset_id": case["dataset_id"],
                    }
                ],
            },
            source="test",
            license_name="MIT",
            cas_root=case["cas_root"],
            replay_ref=case["replay_ref"],
            connection_config=case["connection_config"],
            produce_snapshot=False,
            ingestion_dependencies=case["dependencies"],
        )

    assert len(simulators) == 1
    assert simulators[0].call_count == 1
    assert simulators[0].call_log[0]["url"] == case["canonical_url"]
    assert native_requests == []
    assert ordinary_calls == []


def test_run_replay_mode_uses_recorded_bytes_without_native_transport(
    monkeypatch,
    tmp_path,
) -> None:
    """A real stored response is replayed through the same runtime owner."""
    from polisyos.fabric.data_plane import modes as modes_mod

    case = _make_real_replay_case(tmp_path, b'[{"value":7}]')
    simulators, native_requests, ordinary_calls = _capture_replay_boundaries(monkeypatch)
    result = modes_mod.run_replay_mode(
        connector_manifest={
            "datasets": [
                {"connector_id": case["connector_id"], "dataset_id": case["dataset_id"]},
            ],
        },
        source="test",
        license_name="MIT",
        cas_root=case["cas_root"],
        replay_ref=case["replay_ref"],
        connection_config=case["connection_config"],
        produce_snapshot=False,
        ingestion_dependencies=case["dependencies"],
    )

    assert result.mode_effective == "replay"
    assert result.datasets_fetched == 1
    assert result.evidence_bundle_ref is not None
    assert len(simulators) == 1
    assert simulators[0].call_count == 1
    assert simulators[0].call_log[0]["url"] == case["canonical_url"]
    assert native_requests == []
    assert ordinary_calls == []

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


def test_connector_is_registered_uses_explicit_registry_without_default_helper(
    monkeypatch,
) -> None:
    from polisyos.fabric.data_plane import modes as modes_mod

    registry = SimpleNamespace(
        get_entry=lambda connector_id: {"connector_id": connector_id},
    )

    monkeypatch.setattr(
        modes_mod,
        "_default_connector_registry",
        lambda: (_ for _ in ()).throw(AssertionError("global registry should not be used")),
    )

    assert modes_mod._connector_is_registered("stream.injected", registry=registry) is True


def test_stream_sanitizer_optional_field_membership_is_independent_of_batch_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown-schema rows are not made poisonous by technical batching."""
    from polisyos.fabric.data_plane import modes as modes_mod
    from polisyos.fabric.data_plane.streaming import iter_record_batches

    rows = [
        {"id": "a", "value": 1.0, "note": "first"},
        {"id": "b", "value": 2.0, "note": "second"},
        {"id": "c", "value": 3.0},
    ]
    quarantine_records: list[tuple[str, dict[str, Any]]] = []

    def _capture_quarantine(
        store: Any,
        *,
        record: Any,
        raw_payload: Any | None = None,
        **kwargs: Any,
    ) -> None:
        del store, raw_payload, kwargs
        quarantine_records.append((str(record.reason), dict(record.context)))

    monkeypatch.setattr(modes_mod, "persist_quarantine_record", _capture_quarantine)

    async def _run(batch_size: int) -> tuple[list[str], int]:
        accepted_ids: list[str] = []
        quarantined = 0
        async for batch in iter_record_batches(rows, batch_size=batch_size):
            valid_rows, _warnings, batch_quarantined = modes_mod._sanitize_stream_rows(
                batch,
                connector_id="test.stream",
                dataset_id="events",
                store=object(),
                chunk_index=0,
            )
            accepted_ids.extend(str(row["id"]) for row in valid_rows)
            quarantined += batch_quarantined
        return accepted_ids, quarantined

    observed = {batch_size: asyncio.run(_run(batch_size)) for batch_size in (1, 3)}

    # Without an admitted schema, shape variance is diagnostic rather than
    # evidence that the minority row is a poison message.
    expected = (["a", "b", "c"], 0)
    assert observed[1] == expected
    assert observed[3] == expected
    assert quarantine_records == []


def _presence_schema() -> DataSchema:
    return DataSchema(
        schema_id="test.stream.events",
        version=SchemaVersion(1, 0, 0),
        fields=(
            FieldSpec(name="id", data_type=SchemaType.STRING, nullable=False),
            FieldSpec(name="value", data_type=SchemaType.FLOAT64, nullable=False),
            FieldSpec(
                name="note",
                data_type=SchemaType.STRING,
                nullable=False,
                presence="optional",
            ),
        ),
        primary_key=("id",),
        required_completeness=0.0,
    )


def test_stream_sanitizer_bound_presence_accepts_missing_optional_and_rejects_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Optional absence is distinct from an explicit null value."""
    from polisyos.fabric.data_plane import modes as modes_mod

    records: list[tuple[str, dict[str, Any]]] = []

    def _capture_quarantine(
        store: Any,
        *,
        record: Any,
        raw_payload: Any | None = None,
        **kwargs: Any,
    ) -> None:
        del store, raw_payload, kwargs
        records.append((str(record.reason), dict(record.context)))

    monkeypatch.setattr(modes_mod, "persist_quarantine_record", _capture_quarantine)

    valid_rows, _warnings, quarantined = modes_mod._sanitize_stream_rows(
        [
            {"id": "missing", "value": 1.0},
            {"id": "null", "value": 2.0, "note": None},
            {"id": "present", "value": 3.0, "note": "ok"},
        ],
        connector_id="test.stream",
        dataset_id="events",
        store=object(),
        chunk_index=0,
        schema=_presence_schema(),
    )

    assert [row["id"] for row in valid_rows] == ["missing", "present"]
    assert quarantined == 1
    assert records == [
        (
            "poison_stream_message",
            {
                "chunk_index": 0,
                "row_index": 1,
                "non_nullable_fields": ["note"],
            },
        )
    ]


def test_stream_sanitizer_bound_presence_is_batch_invariant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fixed contract, not batch majority, determines accepted membership."""
    from polisyos.fabric.data_plane import modes as modes_mod
    from polisyos.fabric.data_plane.streaming import iter_record_batches

    rows = [
        {"id": "a", "value": 1.0, "note": "first"},
        {"id": "b", "value": 2.0, "note": "second"},
        {"id": "c", "value": 3.0},
    ]
    quarantine_records: list[dict[str, Any]] = []

    def _capture_quarantine(
        store: Any,
        *,
        record: Any,
        raw_payload: Any | None = None,
        **kwargs: Any,
    ) -> None:
        del store, raw_payload, kwargs
        quarantine_records.append(dict(record.context))

    monkeypatch.setattr(modes_mod, "persist_quarantine_record", _capture_quarantine)

    async def _run(batch_size: int) -> tuple[list[str], int]:
        accepted_ids: list[str] = []
        quarantined = 0
        async for batch in iter_record_batches(rows, batch_size=batch_size):
            valid_rows, _warnings, batch_quarantined = modes_mod._sanitize_stream_rows(
                batch,
                connector_id="test.stream",
                dataset_id="events",
                store=object(),
                chunk_index=0,
                schema=_presence_schema(),
            )
            accepted_ids.extend(str(row["id"]) for row in valid_rows)
            quarantined += batch_quarantined
        return accepted_ids, quarantined

    observed = {batch_size: asyncio.run(_run(batch_size)) for batch_size in (1, 3)}

    assert observed == {1: (["a", "b", "c"], 0), 3: (["a", "b", "c"], 0)}
    assert quarantine_records == []


def test_stream_sanitizer_bound_presence_rejects_missing_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A required field omission remains a quarantined schema violation."""
    from polisyos.fabric.data_plane import modes as modes_mod

    records: list[dict[str, Any]] = []

    def _capture_quarantine(
        store: Any,
        *,
        record: Any,
        raw_payload: Any | None = None,
        **kwargs: Any,
    ) -> None:
        del store, raw_payload, kwargs
        records.append(dict(record.context))

    monkeypatch.setattr(modes_mod, "persist_quarantine_record", _capture_quarantine)

    valid_rows, _warnings, quarantined = modes_mod._sanitize_stream_rows(
        [{"id": "missing-value"}, {"id": "valid", "value": 1.0}],
        connector_id="test.stream",
        dataset_id="events",
        store=object(),
        chunk_index=2,
        schema=_presence_schema(),
    )

    assert [row["id"] for row in valid_rows] == ["valid"]
    assert quarantined == 1
    assert records == [
        {
            "chunk_index": 2,
            "row_index": 0,
            "missing_required_fields": ["value"],
        }
    ]


def test_stream_sanitizer_keeps_non_finite_metric_guard_across_batch_sizes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Batch invariance must not weaken quarantine of non-finite metrics."""
    from polisyos.fabric.data_plane import modes as modes_mod
    from polisyos.fabric.data_plane.streaming import iter_record_batches

    rows = [
        {"id": "ok", "value": 1.0},
        {"id": "bad", "value": float("nan")},
    ]
    quarantine_reasons: list[str] = []

    def _capture_quarantine(
        store: Any,
        *,
        record: Any,
        raw_payload: Any | None = None,
        **kwargs: Any,
    ) -> None:
        del store, raw_payload, kwargs
        quarantine_reasons.append(str(record.reason))

    monkeypatch.setattr(modes_mod, "persist_quarantine_record", _capture_quarantine)

    async def _run(batch_size: int) -> tuple[list[str], int]:
        accepted_ids: list[str] = []
        quarantined = 0
        async for batch in iter_record_batches(rows, batch_size=batch_size):
            valid_rows, _warnings, batch_quarantined = modes_mod._sanitize_stream_rows(
                batch,
                connector_id="test.stream",
                dataset_id="events",
                store=object(),
                chunk_index=0,
                schema=_presence_schema(),
            )
            accepted_ids.extend(str(row["id"]) for row in valid_rows)
            quarantined += batch_quarantined
        return accepted_ids, quarantined

    observed = {batch_size: asyncio.run(_run(batch_size)) for batch_size in (1, 3)}

    assert observed == {1: (["ok"], 1), 3: (["ok"], 1)}
    assert quarantine_reasons == ["non_finite_metric", "non_finite_metric"]
