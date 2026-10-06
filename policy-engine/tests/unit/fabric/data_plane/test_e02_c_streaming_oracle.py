"""Independent behavioral oracles for the E02 C ingestion findings."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
import pytest_asyncio

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.cursor import (
    CursorState,
    StreamLifecycleState,
    WatermarkType,
    WindowStrategy,
)
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.contracts import (
    ConnectorSchemaContract,
    ContractRegistry,
    DataSchema,
    FieldSpec,
    SchemaType,
    SchemaVersion,
)
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.quarantine import list_quarantine_records, load_quarantine_payload
from polisyos.fabric.data_plane.streaming import (
    StreamingSourceSession,
    StreamRuntimeOptions,
    StreamSchemaBinding,
    process_stream_dataset,
)
from polisyos.fabric.data_plane.watermark import WindowPolicy


class _ProcessDeath(BaseException):
    """Model process loss without entering the runtime's Exception recovery path."""


def _valid_rows(batch: object, **kwargs: object) -> tuple[list[dict[str, Any]], list[str], int]:
    del kwargs
    if isinstance(batch, list):
        return [dict(row) for row in batch if isinstance(row, dict)], [], 0
    return [], [], 0


def _configure_stream_registry(
    registry: ConnectorRegistry,
    path: Path,
    *,
    chunk_size: int = 1,
) -> ConnectorRegistry:
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(
            url=path.as_uri(),
            headers={"X-Stream-ChunkSize": str(chunk_size)},
        ),
    )
    return registry


@pytest_asyncio.fixture
async def stream_registry():
    registry = ConnectorRegistry.get_instance()
    yield registry
    await registry.shutdown_async()


def _window_case(strategy: str) -> tuple[list[dict[str, Any]], WindowPolicy, list[list[str]]]:
    ids = ("a", "b", "c")
    if strategy == "count":
        rows = [{"_message_id": key, "value": index} for index, key in enumerate(ids)]
        return rows, WindowPolicy(strategy=WindowStrategy.COUNT, size=2), [["a", "b"], ["c"]]
    if strategy == "tumbling":
        rows = [
            {"_message_id": "a", "event_time": "2024-01-01T00:00:00Z", "value": 1},
            {"_message_id": "b", "event_time": "2024-01-01T00:00:05Z", "value": 2},
            {"_message_id": "c", "event_time": "2024-01-01T00:01:01Z", "value": 3},
        ]
        return (
            rows,
            WindowPolicy(
                strategy=WindowStrategy.TUMBLING,
                size=60,
                timestamp_field="event_time",
            ),
            [["a", "b"], ["c"]],
        )
    if strategy == "session":
        rows = [
            {"_message_id": "a", "event_time": "2024-01-01T00:00:00Z", "value": 1},
            {"_message_id": "b", "event_time": "2024-01-01T00:00:05Z", "value": 2},
            {"_message_id": "c", "event_time": "2024-01-01T00:01:00Z", "value": 3},
        ]
        return (
            rows,
            WindowPolicy(
                strategy=WindowStrategy.SESSION,
                size=10,
                session_gap_seconds=10,
                timestamp_field="event_time",
            ),
            [["a", "b"], ["c"]],
        )
    if strategy == "sliding":
        rows = [{"_message_id": key, "value": index} for index, key in enumerate(ids)]
        return (
            rows,
            WindowPolicy(strategy=WindowStrategy.SLIDING, size=2, slide=1),
            [["a", "b"], ["b", "c"]],
        )
    raise AssertionError(f"unknown test strategy: {strategy}")


def _window_rows_and_lineage(
    store: FileSystemCAS,
    chunk_refs: list[Any],
    window_refs: list[Any],
) -> tuple[list[list[str]], list[tuple[str, ...]]]:
    row_to_chunk: dict[str, str] = {}
    for artifact_id in store.iter_artifact_ids():
        manifest = store.get_manifest(artifact_id)
        if manifest.kind != "fabric.stream_chunk":
            continue
        payload = from_canonical_bytes(store.get_bytes(str(artifact_id)))
        for row in payload["data"]:
            row_to_chunk[str(row["_message_id"])] = str(artifact_id)
    persisted_chunk_ids = set(row_to_chunk.values())
    assert all(str(ref.artifact_id) in persisted_chunk_ids for ref in chunk_refs)

    observed_rows: list[list[str]] = []
    observed_lineage: list[tuple[str, ...]] = []
    for ref in window_refs:
        payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
        ids = [str(row["_message_id"]) for row in payload["data"]]
        expected_refs = tuple(dict.fromkeys(row_to_chunk[row_id] for row_id in ids))
        manifest_refs = tuple(
            str(item.artifact_id) for item in store.get_manifest(ref.artifact_id).inputs
        )
        declared_refs = tuple(payload["lineage"]["contributor_chunk_refs"])
        assert manifest_refs == expected_refs
        assert declared_refs == expected_refs
        observed_rows.append(ids)
        observed_lineage.append(manifest_refs)
    return observed_rows, observed_lineage


async def _run_stream(
    *,
    path: Path,
    dataset_id: str,
    cas_root: Path,
    policy: WindowPolicy,
    registry: ConnectorRegistry,
    options: StreamRuntimeOptions | None = None,
    sanitize_rows: Any = _valid_rows,
    schema_binding: StreamSchemaBinding | None = None,
) -> Any:
    store = FileSystemCAS(cas_root)
    return await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id=dataset_id,
        store=store,
        cursor_store=CursorStore(store),
        sanitize_rows=sanitize_rows,
        runtime_options=options or StreamRuntimeOptions(window_policy=policy),
        registry=registry,
        schema_binding=schema_binding,
    )


@pytest.mark.parametrize("manifest_kind", ["dict", "typed"])
def test_b79_supported_rest_request_uses_the_persisted_etag_cursor(
    tmp_path: Path,
    manifest_kind: str,
) -> None:
    """The supported ingestion route sends the stored source version to REST."""
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.contracts.fabric import EvidenceBundle
    from polisyos.fabric.connectors.cache._store_serialization import ResultSerializer
    from polisyos.fabric.connectors.registry import ConnectorRegistry as IngestionRegistry
    from polisyos.fabric.data_plane.modes import run_batch_incremental
    from polisyos.fabric.ingestion import resolve_ingestion_dependencies

    calls: list[tuple[str, str, dict[str, list[str]]]] = []

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            calls.append((self.command, parsed.path, parse_qs(parsed.query)))
            body = json.dumps({"data": [{"id": "row-1", "value": 7}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("ETag", '"etag-next"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    cas_root = tmp_path / f"cas-{manifest_kind}"
    store = FileSystemCAS(cas_root)
    cursor_store = CursorStore(store)
    prior = '"etag-prior"'
    cursor_store.save_cursor(
        CursorState(
            cursor_id="rest.json:dataset",
            connector_id="rest.json",
            dataset_id="dataset",
            watermark_type=WatermarkType.ETAG,
            watermark_value=prior,
            created_at=datetime(2026, 10, 1, tzinfo=UTC),
        )
    )

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    registry = IngestionRegistry.get_instance()
    thread.start()
    try:
        if manifest_kind == "dict":
            manifest: Any = {"datasets": [{"connector_id": "rest.json", "dataset_id": "dataset"}]}
        else:
            from polisyos.fabric.ingestion import ConnectorManifestSpec
            from polisyos.fabric.ingestion.ingestion import DatasetFetchSpec

            manifest = ConnectorManifestSpec(
                datasets=[DatasetFetchSpec(connector_id="rest.json", dataset_id="dataset")]
            )

        result = run_batch_incremental(
            connector_manifest=manifest,
            source="e02-b79-fixture",
            license_name="fixture-only",
            cas_root=cas_root,
            connection_config=ConnectionConfig(
                url=f"http://127.0.0.1:{server.server_port}/records"
            ),
            produce_snapshot=False,
            ingestion_dependencies=resolve_ingestion_dependencies(registry=registry),
        )

        assert result.datasets_fetched == 1
        assert result.evidence_bundle_ref is not None
        assert result.cursor_ref is None  # No unverified promotion on the same fixture.
        assert len(calls) == 2
        assert all(method == "GET" and path == "/records" for method, path, _ in calls)
        assert [query for _, _, query in calls if "since" in query] == [
            {"limit": ["100"], "page": ["1"], "since": [prior]}
        ]

        evidence = from_canonical_bytes(store.get_bytes(result.evidence_bundle_ref.artifact_id))
        bundle = EvidenceBundle.model_validate(evidence)
        assert len(bundle.sources) == 1
        persisted = ResultSerializer.deserialize(store.get_bytes(bundle.sources[0]))
        assert persisted.data == [{"id": "row-1", "value": 7}]
        after = cursor_store.find_latest_cursor("rest.json", "dataset")
        assert after is not None and after.watermark_value == prior
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        registry.shutdown()


@pytest.mark.parametrize("strategy", ["count", "tumbling", "session", "sliding"])
@pytest.mark.parametrize("crash_boundary", ["after_raw_chunk", "after_window_artifact"])
@pytest.mark.asyncio
async def test_b81_b82_b85_baseexception_restart_replays_actual_cas_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stream_registry: ConnectorRegistry,
    strategy: str,
    crash_boundary: str,
) -> None:
    """Crash at a real CAS write, reopen, and compare windows to an independent oracle."""
    import polisyos.fabric.data_plane.streaming as streaming

    rows, policy, expected = _window_case(strategy)
    stream_path = tmp_path / f"{strategy}-{crash_boundary}.jsonl"
    stream_path.write_text(
        "".join(json.dumps(row, allow_nan=True, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    registry = _configure_stream_registry(stream_registry, stream_path)
    cas_root = tmp_path / f"cas-{strategy}-{crash_boundary}"
    store = FileSystemCAS(cas_root)
    cursor_store = CursorStore(store)
    crashed_artifacts: list[str] = []
    original = (
        streaming._persist_stream_chunk_async
        if crash_boundary == "after_raw_chunk"
        else streaming._persist_stream_window_async
    )

    async def _persist_then_crash(**kwargs: Any):
        ref = await original(**kwargs)
        if not crashed_artifacts:
            crashed_artifacts.append(str(ref.artifact_id))
            raise _ProcessDeath(crash_boundary)
        return ref

    monkeypatch.setattr(
        streaming,
        (
            "_persist_stream_chunk_async"
            if crash_boundary == "after_raw_chunk"
            else "_persist_stream_window_async"
        ),
        _persist_then_crash,
    )
    with pytest.raises(_ProcessDeath):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=f"{strategy}-{crash_boundary}",
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            runtime_options=StreamRuntimeOptions(
                checkpoint_every_chunks=1,
                max_dedupe_keys=32,
                window_policy=policy,
            ),
            registry=registry,
        )

    monkeypatch.setattr(
        streaming,
        (
            "_persist_stream_chunk_async"
            if crash_boundary == "after_raw_chunk"
            else "_persist_stream_window_async"
        ),
        original,
    )
    persisted_crash = FileSystemCAS(cas_root)
    assert persisted_crash.get_manifest(crashed_artifacts[0]).kind == (
        "fabric.stream_chunk" if crash_boundary == "after_raw_chunk" else "fabric.stream_window"
    )
    resumed_cursor_store = CursorStore(persisted_crash)
    result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id=f"{strategy}-{crash_boundary}",
        store=persisted_crash,
        cursor_store=resumed_cursor_store,
        sanitize_rows=_valid_rows,
        runtime_options=StreamRuntimeOptions(
            checkpoint_every_chunks=1,
            max_dedupe_keys=32,
            window_policy=policy,
        ),
        registry=registry,
    )

    actual_rows, actual_lineage = _window_rows_and_lineage(
        persisted_crash,
        result.chunk_refs,
        result.window_refs,
    )
    assert actual_rows == expected
    assert len(actual_lineage) == len(expected)
    assert result.final_checkpoint is not None
    assert result.final_checkpoint.lifecycle_state == StreamLifecycleState.CLOSED
    assert result.final_checkpoint_ref is not None
    persisted_frontier = resumed_cursor_store.find_latest_stream_checkpoint(
        "stream.jsonl",
        f"{strategy}-{crash_boundary}",
    )
    assert persisted_frontier is not None
    assert persisted_frontier.metadata["frontier_intent"]["state"] == "committed"


@pytest.mark.parametrize("strategy", ["count", "tumbling", "session", "sliding"])
@pytest.mark.asyncio
async def test_b84_restored_state_over_new_capacity_refuses_before_source_or_cas_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stream_registry: ConnectorRegistry,
    strategy: str,
) -> None:
    """A smaller restored cap fails before rewind/poll and leaves the old frontier intact."""
    rows, policy, _expected = _window_case(strategy)
    # Force every strategy to retain the first two rows at the crash frontier.
    policy = WindowPolicy(
        strategy=policy.strategy,
        size=4,
        slide=1 if strategy == "sliding" else policy.slide,
        session_gap_seconds=policy.session_gap_seconds,
        timestamp_field=policy.timestamp_field,
    )
    stream_path = tmp_path / f"restore-{strategy}.jsonl"
    stream_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    registry = _configure_stream_registry(stream_registry, stream_path)
    cas_root = tmp_path / f"restore-cas-{strategy}"
    store = FileSystemCAS(cas_root)
    cursor_store = CursorStore(store)
    original_poll = StreamingSourceSession.poll
    state = {"calls": 0}

    async def _crash_before_third_source_chunk(session: StreamingSourceSession):
        if state["calls"] == 2:
            raise _ProcessDeath("leave two committed rows in the operator")
        state["calls"] += 1
        return await original_poll(session)

    monkeypatch.setattr(StreamingSourceSession, "poll", _crash_before_third_source_chunk)
    with pytest.raises(_ProcessDeath):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=f"restore-{strategy}",
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            runtime_options=StreamRuntimeOptions(
                checkpoint_every_chunks=1,
                max_buffered_rows=3,
                max_buffered_bytes=100_000,
                window_policy=policy,
            ),
            registry=registry,
        )

    monkeypatch.setattr(StreamingSourceSession, "poll", original_poll)
    before = CursorStore(FileSystemCAS(cas_root))
    prior_checkpoint = before.find_latest_stream_checkpoint("stream.jsonl", f"restore-{strategy}")
    prior_cursor = before.find_latest_cursor("stream.jsonl", f"restore-{strategy}")
    assert prior_checkpoint is not None
    assert prior_checkpoint.metadata["frontier_intent"]["state"] == "committed"
    prior_ids = set(map(str, FileSystemCAS(cas_root).iter_artifact_ids()))

    effects = {"rewind": 0, "poll": 0, "commit": 0}
    original_rewind = StreamingSourceSession.rewind
    original_poll = StreamingSourceSession.poll
    original_commit = StreamingSourceSession.commit

    async def _count_rewind(session: StreamingSourceSession, checkpoint: Any) -> None:
        effects["rewind"] += 1
        await original_rewind(session, checkpoint)

    async def _count_poll(session: StreamingSourceSession):
        effects["poll"] += 1
        return await original_poll(session)

    async def _count_commit(session: StreamingSourceSession, checkpoint: Any) -> None:
        effects["commit"] += 1
        await original_commit(session, checkpoint)

    monkeypatch.setattr(StreamingSourceSession, "rewind", _count_rewind)
    monkeypatch.setattr(StreamingSourceSession, "poll", _count_poll)
    monkeypatch.setattr(StreamingSourceSession, "commit", _count_commit)
    resumed_store = FileSystemCAS(cas_root)
    with pytest.raises(RuntimeError, match="capacity|retained|buffer"):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=f"restore-{strategy}",
            store=resumed_store,
            cursor_store=CursorStore(resumed_store),
            sanitize_rows=_valid_rows,
            runtime_options=StreamRuntimeOptions(
                checkpoint_every_chunks=1,
                max_buffered_rows=1,
                max_buffered_bytes=100_000,
                window_policy=policy,
            ),
            registry=registry,
        )

    assert effects == {"rewind": 0, "poll": 0, "commit": 0}
    after = CursorStore(FileSystemCAS(cas_root))
    assert after.find_latest_stream_checkpoint("stream.jsonl", f"restore-{strategy}").model_dump(
        mode="json"
    ) == prior_checkpoint.model_dump(mode="json")
    current_cursor = after.find_latest_cursor("stream.jsonl", f"restore-{strategy}")
    assert (current_cursor.model_dump(mode="json") if current_cursor else None) == (
        prior_cursor.model_dump(mode="json") if prior_cursor else None
    )
    assert set(map(str, FileSystemCAS(cas_root).iter_artifact_ids())) == prior_ids

    monkeypatch.setattr(StreamingSourceSession, "rewind", original_rewind)
    monkeypatch.setattr(StreamingSourceSession, "poll", original_poll)
    monkeypatch.setattr(StreamingSourceSession, "commit", original_commit)
    retry_store = FileSystemCAS(cas_root)
    retried = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id=f"restore-{strategy}",
        store=retry_store,
        cursor_store=CursorStore(retry_store),
        sanitize_rows=_valid_rows,
        runtime_options=StreamRuntimeOptions(
            checkpoint_every_chunks=1,
            max_buffered_rows=3,
            max_buffered_bytes=100_000,
            window_policy=policy,
        ),
        registry=registry,
    )
    actual_rows, _lineage = _window_rows_and_lineage(
        retry_store,
        retried.chunk_refs,
        retried.window_refs,
    )
    assert (
        actual_rows
        == {
            "count": [["a", "b", "c"]],
            "tumbling": [["a", "b"], ["c"]],
            "session": [["a", "b"], ["c"]],
            "sliding": [],
        }[strategy]
    )


@pytest.mark.parametrize("strategy", ["count", "tumbling", "session", "sliding"])
@pytest.mark.asyncio
async def test_b84_capacity_exactly_allows_a_window_closing_transition(
    tmp_path: Path,
    stream_registry: ConnectorRegistry,
    strategy: str,
) -> None:
    """A row that closes/advances an operator at its declared cap is admissible."""
    rows, policy, expected = _window_case(strategy)
    stream_path = tmp_path / f"at-cap-{strategy}.jsonl"
    stream_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    registry = _configure_stream_registry(stream_registry, stream_path)
    # The first two rows fit exactly. For tumbling/session the third row closes
    # that state before starting the next window; count/sliding close at size.
    cap_bytes = sum(
        len(json.dumps(row, sort_keys=True, default=str).encode("utf-8")) for row in rows[:2]
    )
    cas_root = tmp_path / f"at-cap-cas-{strategy}"
    result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id=f"at-cap-{strategy}",
        store=FileSystemCAS(cas_root),
        cursor_store=CursorStore(FileSystemCAS(cas_root)),
        sanitize_rows=_valid_rows,
        runtime_options=StreamRuntimeOptions(
            checkpoint_every_chunks=1,
            max_buffered_rows=2,
            max_buffered_bytes=cap_bytes,
            window_policy=policy,
        ),
        registry=registry,
    )
    store = FileSystemCAS(cas_root)
    actual_rows, _lineage = _window_rows_and_lineage(store, result.chunk_refs, result.window_refs)
    assert actual_rows == expected


@pytest.mark.parametrize("batch_size", [1, 2, 8])
@pytest.mark.asyncio
async def test_b86_schema_membership_and_quarantine_do_not_depend_on_batch_size(
    tmp_path: Path,
    stream_registry: ConnectorRegistry,
    batch_size: int,
) -> None:
    """The declared schema, not a technical batch vote, determines row membership."""
    from polisyos.fabric.data_plane.modes import _bind_stream_sanitizer

    source_rows: list[dict[str, Any]] = [
        {"event_id": "valid-absent-note", "value": 1},
        {"event_id": "valid-note", "value": 2, "note": "present"},
        {"event_id": "valid-null-note", "value": 3, "note": None},
        {"event_id": "missing-value", "note": "required field missing"},
        {"event_id": None, "value": 4.0},
        {"event_id": "wrong-type", "value": "not-a-float"},
        {"event_id": "non-finite", "value": float("nan")},
    ]
    stream_path = tmp_path / f"schema-batch-{batch_size}.jsonl"
    stream_path.write_text(
        "".join(json.dumps(row, allow_nan=True, sort_keys=True) + "\n" for row in source_rows),
        encoding="utf-8",
    )
    registry = _configure_stream_registry(
        stream_registry,
        stream_path,
        chunk_size=len(source_rows),
    )
    schema = DataSchema(
        schema_id="test.e02.stream_rows",
        version=SchemaVersion(1, 0, 0),
        fields=(
            FieldSpec(name="event_id", data_type=SchemaType.STRING, nullable=False),
            FieldSpec(name="value", data_type=SchemaType.FLOAT64, nullable=False),
            FieldSpec(
                name="note",
                data_type=SchemaType.STRING,
                presence="optional",
                nullable=True,
            ),
        ),
        primary_key=("event_id",),
        required_completeness=0.0,
    )
    contracts = ContractRegistry()
    contract = ConnectorSchemaContract(
        contract_id="test.e02.stream_rows.contract",
        connector_id="stream.jsonl",
        dataset_id=f"schema-{batch_size}",
        schema=schema,
        created_by="test_e02_c_streaming_oracle",
    )
    contracts.register(contract)
    registry.configure_contracts(contracts)
    binding = StreamSchemaBinding.from_contract(contract, registry_revision=contracts.revision)
    cas_root = tmp_path / f"schema-cas-{batch_size}"
    store = FileSystemCAS(cas_root)
    result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id=f"schema-{batch_size}",
        store=store,
        cursor_store=CursorStore(store),
        sanitize_rows=_bind_stream_sanitizer(binding),
        runtime_options=StreamRuntimeOptions(
            batch_size=batch_size,
            checkpoint_every_chunks=1,
            max_dedupe_keys=16,
            window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=32),
        ),
        registry=registry,
        schema_binding=binding,
    )

    accepted_ids = {
        str(row["event_id"])
        for ref in result.chunk_refs
        for row in from_canonical_bytes(store.get_bytes(ref.artifact_id))["data"]
    }
    records = list_quarantine_records(
        store,
        source="connector.stream:stream.jsonl:" + f"schema-{batch_size}",
    )
    rejected = [load_quarantine_payload(store, record.raw_payload_ref) for _, record in records]
    rejected_ids = {row.get("event_id") for row in rejected if isinstance(row, dict)}
    assert accepted_ids == {"valid-absent-note", "valid-note", "valid-null-note"}
    assert "missing-value" in rejected_ids
    assert "wrong-type" in rejected_ids
    assert "non-finite" in rejected_ids
    assert any(row.get("event_id") is None and row.get("value") == 4.0 for row in rejected)
    assert len(records) == 4
    non_finite_records = [record for _, record in records if record.reason == "non_finite_metric"]
    assert len(non_finite_records) == 1
    assert result.quarantined_rows == 4
