"""Independent behavioral oracles for the E02 C ingestion findings."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlsplit

import pytest
import pytest_asyncio

from polisyos.core.artifacts.protocol import matches_runtime_protocol
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.cursor import (
    StreamLifecycleState,
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
from polisyos.fabric.connectors.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
)
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.quarantine import (
    IndexedArtifactStore,
    list_quarantine_records,
    load_quarantine_payload,
    quarantine_index_path,
)
from polisyos.fabric.data_plane.streaming import (
    StreamingSourceSession,
    StreamRuntimeOptions,
    StreamSchemaBinding,
    process_stream_dataset,
)
from polisyos.fabric.data_plane.watermark import WindowPolicy
from polisyos.runtime.http.resilience import BlockingDependencyGuard, GuardedDependencyProxy
from tests._helpers.source_progress import finite_source_reader


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


def _over_capacity_window_case(strategy: str) -> tuple[list[dict[str, Any]], WindowPolicy]:
    """Three rows remain live together so the actual retained operator exceeds two."""
    ids = ("a", "b", "c")
    if strategy == "count":
        return (
            [{"_message_id": key, "value": index} for index, key in enumerate(ids)],
            WindowPolicy(strategy=WindowStrategy.COUNT, size=16),
        )
    if strategy == "tumbling":
        return (
            [
                {
                    "_message_id": key,
                    "event_time": f"2024-01-01T00:00:{index * 5:02d}Z",
                    "value": index,
                }
                for index, key in enumerate(ids)
            ],
            WindowPolicy(
                strategy=WindowStrategy.TUMBLING,
                size=60,
                timestamp_field="event_time",
            ),
        )
    if strategy == "session":
        return (
            [
                {
                    "_message_id": key,
                    "event_time": f"2024-01-01T00:00:{index * 5:02d}Z",
                    "value": index,
                }
                for index, key in enumerate(ids)
            ],
            WindowPolicy(
                strategy=WindowStrategy.SESSION,
                size=60,
                session_gap_seconds=60,
                timestamp_field="event_time",
            ),
        )
    if strategy == "sliding":
        return (
            [{"_message_id": key, "value": index} for index, key in enumerate(ids)],
            WindowPolicy(strategy=WindowStrategy.SLIDING, size=4, slide=1),
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


def _dedupe_options(
    *,
    partition_key: str = "default",
    max_dedupe_keys: int = 2,
) -> StreamRuntimeOptions:
    """Build a small runtime profile for the explicit event/version fixture."""
    return StreamRuntimeOptions(
        partition_key=partition_key,
        batch_size=1,
        checkpoint_every_chunks=1,
        dedupe_key_fields=("event_id", "source_version"),
        max_dedupe_keys=max_dedupe_keys,
        max_buffered_rows=16,
        max_buffered_bytes=100_000,
        window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=16),
    )


def _non_deduping_options(**kwargs: Any) -> StreamRuntimeOptions:
    """Keep non-B83 window/CDC/capacity tests separate from source-key authority."""
    options = StreamRuntimeOptions(**kwargs)
    contract = options.processing_contract
    return replace(
        options,
        processing_contract=contract.model_copy(
            update={
                "idempotency": contract.idempotency.model_copy(update={"enabled": False}),
                "guarantee": "at_least_once",
            }
        ),
    )


def _capacity_processing_contract(
    strategy: str,
    *,
    max_rows: int,
    max_bytes: int,
) -> Any:
    """Build the declared backpressure strategy around the requested cap."""
    from polisyos.fabric.quality.processing_guarantees import (
        BackpressureStrategy,
        stream_processing_contract,
    )

    contract = stream_processing_contract(
        max_buffered_rows=max_rows,
        max_buffered_bytes=max_bytes,
    )
    backpressure = contract.backpressure.model_copy(
        update={"strategy": BackpressureStrategy(strategy)}
    )
    return contract.model_copy(update={"backpressure": backpressure})


def _dedupe_horizon_entries(checkpoint: Any) -> dict[tuple[tuple[str, object], ...], datetime]:
    """Decode committed horizon entries to compare event/version meaning."""
    horizon = checkpoint.metadata.get("dedupe_horizon")
    assert isinstance(horizon, dict), "checkpoint must persist the UTC dedupe horizon"
    assert horizon.get("version") == 1
    assert horizon.get("window_seconds") == 86_400
    assert horizon.get("fields") == ["event_id", "source_version"]
    entries = horizon.get("entries")
    assert isinstance(entries, dict)
    return {
        tuple(
            (str(field), value) for field, value in json.loads(encoded_key)
        ): datetime.fromisoformat(str(timestamp))
        for encoded_key, timestamp in entries.items()
    }


def _persisted_stream_rows(store: FileSystemCAS, *, dataset_id: str) -> list[dict[str, Any]]:
    """Read emitted rows from their actual stream-chunk CAS artifacts."""
    indexed_chunks: list[tuple[int, list[dict[str, Any]]]] = []
    for artifact_id in store.iter_artifact_ids():
        if store.get_manifest(artifact_id).kind != "fabric.stream_chunk":
            continue
        payload = from_canonical_bytes(store.get_bytes(artifact_id))
        if payload.get("dataset_id") != dataset_id:
            continue
        indexed_chunks.append((int(payload["chunk_index"]), list(payload["data"])))
    return [row for _index, rows in sorted(indexed_chunks) for row in rows]


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
        runtime_options=options or _non_deduping_options(window_policy=policy),
        registry=registry,
        schema_binding=schema_binding,
    )


@pytest.mark.parametrize("manifest_kind", ["dict", "spec"])
def test_b79_finite_file_replay_uses_only_its_admitted_persisted_cursor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, manifest_kind: str
) -> None:
    """Actual file replay proves portable progress; it makes no live REST claim."""
    from copy import deepcopy

    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.fabric.data_plane.modes import run_batch_incremental
    from polisyos.fabric.ingestion import resolve_ingestion_dependencies
    from polisyos.fabric.ingestion.source_progress import ReconciledSourceFrame
    from tests._helpers.source_progress import write_source_history

    reader = finite_source_reader(
        tmp_path / "owner",
        connector_id="rest.json",
        dataset_id="dataset",
        schema_id="rest.json.dataset",
        snapshots=[('"etag-prior"', [])],
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    config = ConnectionConfig(url=reader.fixture_path.as_uri())
    registry.set_default_config("rest.json", config)
    dependencies = resolve_ingestion_dependencies(
        registry=registry, source_progress_readers=(reader,)
    )
    if manifest_kind == "dict":
        manifest: Any = {"datasets": [{"connector_id": "rest.json", "dataset_id": "dataset"}]}
    else:
        from polisyos.fabric.ingestion import ConnectorManifestSpec, DatasetFetchSpec

        manifest = ConnectorManifestSpec(
            datasets=[DatasetFetchSpec(connector_id="rest.json", dataset_id="dataset")]
        )
    observed = []
    real_fetch = ReconciledSourceFrame.replay_fetch

    def observe(frame, actual_config, request):
        observed.append(request)
        return real_fetch(frame, actual_config, request)

    monkeypatch.setattr(ReconciledSourceFrame, "replay_fetch", observe)
    cas_root = tmp_path / "cas"

    def run(root=cas_root):
        return run_batch_incremental(
            connector_manifest=manifest,
            source="b79-file-replay",
            license_name="fixture-only",
            cas_root=root,
            connection_config=config,
            produce_snapshot=True,
            ingestion_dependencies=dependencies,
        )

    try:
        first = run()
        assert first.status == "completed" and first.cursor_ref is not None
        assert observed[-1].incremental_since is None
        prior = CursorStore(FileSystemCAS(cas_root)).find_latest_cursor("rest.json", "dataset")
        row = {"event_id": "one", "source_version": "1"}
        write_source_history(reader, [('"etag-prior"', []), ('"etag-next"', [row])])
        result = run()
        assert result.status == "completed" and result.cursor_ref is not None
        assert result.evidence_bundle_ref is not None
        assert FileSystemCAS(cas_root).get_manifest(
            result.evidence_bundle_ref
        ).artifact_schema == SchemaInfo(name="fabric.evidence_bundle", version="1.0")
        assert observed[-1].incremental_since.value == '"etag-prior"'
        current = CursorStore(FileSystemCAS(cas_root)).find_latest_cursor("rest.json", "dataset")
        assert current.watermark_value == '"etag-next"'
        assert current.metadata["cache_key"] == observed[-1].cache_key
        from polisyos.core.artifacts import load_core_json_artifact
        from polisyos.core.contracts.fabric import DataSnapshot
        from polisyos.foundry.data_plane.bindings import _load_binding_payload

        store = FileSystemCAS(cas_root)
        snapshot = DataSnapshot.model_validate(
            load_core_json_artifact(store, result.data_snapshot_ref)
        )
        payload = _load_binding_payload(store, snapshot)
        assert payload["admission_scope"] == "finite_source_fixture"
        assert payload["production_currentness"] == "not_established"
        assert {
            r["event_id"] for member in payload["sources"].values() for r in member["data"]
        } == {"one"}
        changed_metadata = deepcopy(current.metadata)
        changed_metadata["source_progress"]["payload_ref"]["manifest_profile_sha256"] = "0" * 64
        changed_profile = current.model_copy(update={"metadata": changed_metadata})
        CursorStore(store).save_cursor(changed_profile)
        negative = run()
        assert negative.status == "partial" and negative.cursor_ref is None
        assert observed[-1].incremental_since is None
        assert CursorStore(store).find_latest_cursor("rest.json", "dataset") == changed_profile
        legacy_root = tmp_path / "legacy"
        legacy = prior.model_copy(update={"metadata": {}, "evidence_bundle_ref": None})
        CursorStore(FileSystemCAS(legacy_root)).save_cursor(legacy)
        refused = run(legacy_root)
        assert refused.status == "partial" and refused.data_snapshot_ref is None
        assert observed[-1].incremental_since is None
        assert (
            CursorStore(FileSystemCAS(legacy_root)).find_latest_cursor("rest.json", "dataset")
            == legacy
        )
    finally:
        registry.shutdown()


def test_b79_matching_finite_file_cannot_authorize_a_live_endpoint(
    tmp_path: Path,
) -> None:
    """Hidden C with unchanged A/B/complete declarations never promotes live progress."""
    from polisyos.fabric.data_plane.modes import run_batch_incremental
    from polisyos.fabric.ingestion import resolve_ingestion_dependencies

    rows = [{"event_id": key, "source_version": "1"} for key in ("A", "B", "C")]
    observed = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            query = parse_qs(urlsplit(self.path).query)
            observed.append(query)
            # The network source has C, but declares A/B to be a complete A9.
            body = json.dumps({"data": rows[:2]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("eTaG", '"a9"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            del format, args

    reader = finite_source_reader(
        tmp_path / "owner",
        connector_id="rest.json",
        dataset_id="dataset",
        schema_id="rest.json.dataset",
        snapshots=[('"a9"', rows[:2])],
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    dependencies = resolve_ingestion_dependencies(
        registry=registry, source_progress_readers=(reader,)
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run_batch_incremental(
            connector_manifest={
                "datasets": [{"connector_id": "rest.json", "dataset_id": "dataset"}]
            },
            source="b79-live-negative",
            license_name="fixture-only",
            cas_root=tmp_path / "cas",
            connection_config=ConnectionConfig(
                url=f"http://127.0.0.1:{server.server_port}/records"
            ),
            produce_snapshot=True,
            ingestion_dependencies=dependencies,
        )
        assert (
            result.status == "partial"
            and result.cursor_ref is None
            and result.data_snapshot_ref is None
        )
        assert observed and all("since" not in query for query in observed)
        assert (
            CursorStore(FileSystemCAS(tmp_path / "cas")).find_latest_cursor("rest.json", "dataset")
            is None
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        registry.shutdown()


def test_b80_two_source_failure_then_fresh_snapshot_consumes_both_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A9/B4 then fresh Snapshot B is A9/B5 through the real Foundry loader."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.fabric.connectors.sources.rest_json import RestJsonConnector
    from polisyos.fabric.data_plane.modes import run_batch_incremental
    from polisyos.fabric.ingestion import resolve_ingestion_dependencies
    from polisyos.fabric.ingestion.source_collection import SourceCollection, source_namespace
    from polisyos.fabric.ingestion.source_progress import (
        ReconciledSourceFrame,
        SourceProgressAdmissionError,
    )
    from polisyos.foundry.data_plane.bindings import _load_binding_payload, _resolve_source_path
    from tests._helpers.source_progress import write_source_history

    a9 = {"event_id": "a-event-9", "source_version": "9", "event_time": "2025-01-01T00:00:00Z"}
    b5 = {"event_id": "b-late-event-5", "source_version": "5", "event_time": "2024-01-01T00:00:00Z"}
    readers = {
        source: finite_source_reader(
            tmp_path / "owner",
            connector_id=f"fixture.{source}",
            dataset_id="events",
            schema_id=f"fixture.{source}.events",
            snapshots=[(version, [])],
        )
        for source, version in (("source_a", "a8"), ("source_b", "b4"))
    }
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    for source, reader in readers.items():
        cls = type(
            source.title() + "Connector",
            (RestJsonConnector,),
            {
                "connector_id": f"fixture.{source}",
                "namespace": "fixture",
                "short_id": source,
                "metadata": RestJsonConnector.metadata.model_copy(
                    update={"connector_id": source, "namespace": "fixture"}
                ),
            },
        )
        registry.register(cls, config=ConnectionConfig(url=reader.fixture_path.as_uri()))
    dependencies = resolve_ingestion_dependencies(
        registry=registry, source_progress_readers=tuple(readers.values())
    )
    manifest = {
        "datasets": [
            {"connector_id": f"fixture.{source}", "dataset_id": "events"} for source in readers
        ]
    }
    observed = []
    phase = {"value": "initial"}
    real_fetch = ReconciledSourceFrame.replay_fetch

    def transient_io(frame, config, request):
        observed.append(
            (
                frame.extension.connector_id,
                request.incremental_since.value if request.incremental_since else None,
            )
        )
        if phase["value"] == "fail-b" and frame.extension.connector_id == "fixture.source_b":
            raise SourceProgressAdmissionError(
                "actual_source_unavailable", connector_id="fixture.source_b", dataset_id="events"
            )
        return real_fetch(frame, config, request)

    monkeypatch.setattr(ReconciledSourceFrame, "replay_fetch", transient_io)
    cas_root = tmp_path / "cas"

    def run():
        return run_batch_incremental(
            connector_manifest=manifest,
            source="b80-file-replay",
            license_name="fixture-only",
            cas_root=cas_root,
            produce_snapshot=True,
            ingestion_dependencies=dependencies,
        )

    try:
        assert run().status == "completed"
        write_source_history(readers["source_a"], [("a8", []), ("a9", [a9])])
        write_source_history(readers["source_b"], [("b4", []), ("b5", [b5])])
        phase["value"] = "fail-b"
        partial = run()
        assert partial.status == "partial" and partial.data_snapshot_ref is None
        after_failure = CursorStore(FileSystemCAS(cas_root))
        assert (
            after_failure.find_latest_cursor("fixture.source_a", "events").watermark_value == "a9"
        )
        assert (
            after_failure.find_latest_cursor("fixture.source_b", "events").watermark_value == "b4"
        )
        phase["value"] = "retry"
        complete = run()
        assert complete.status == "completed" and complete.data_snapshot_ref is not None
        assert complete.evidence_bundle_ref is not None
        assert FileSystemCAS(cas_root).get_manifest(
            complete.evidence_bundle_ref
        ).artifact_schema == SchemaInfo(name="fabric.evidence_bundle", version="1.0")
        assert observed == [
            ("fixture.source_a", None),
            ("fixture.source_b", None),
            ("fixture.source_a", "a8"),
            ("fixture.source_b", "b4"),
            ("fixture.source_a", "a9"),
            ("fixture.source_b", "b4"),
        ]
        # A's successful retry transport delta is empty. Only the newly returned
        # Snapshot B is opened; no union with any earlier bundle/snapshot exists.
        fresh_store = FileSystemCAS(cas_root)
        snapshot = DataSnapshot.model_validate(
            load_core_json_artifact(fresh_store, complete.data_snapshot_ref)
        )
        payload = _load_binding_payload(fresh_store, snapshot)
        a_key = source_namespace("fixture.source_a", "events")
        b_key = source_namespace("fixture.source_b", "events")
        assert _resolve_source_path(payload, f"sources.{a_key}.data", missing=None) == [a9]
        assert _resolve_source_path(payload, f"sources.{b_key}.data", missing=None) == [b5]
        assert payload["composition_semantics"] == "namespaced_collection_no_inferred_join"
        assert payload["production_currentness"] == "not_established"
        # Removal/adversarial control: drop the actual B member while retaining
        # A/B source evidence, all declarations and manifest inputs. The real
        # consumer must refuse rather than publish a superficially complete A.
        collection = SourceCollection.model_validate(payload)
        truncated = collection.model_copy(update={"sources": {a_key: collection.sources[a_key]}})
        manifest_view = fresh_store.get_manifest(snapshot.data_ref)
        bad_ref = fresh_store.put_json(
            truncated,
            ArtifactWriteOptions(
                kind="fabric.source_collection",
                media_type="application/json",
                schema=SchemaInfo(name="fabric.SourceCollection", version="1.0"),
                inputs=manifest_view.inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        with pytest.raises(ValueError, match="omits|duplicates"):
            _load_binding_payload(fresh_store, snapshot.model_copy(update={"data_ref": bad_ref}))
        # Also retain both members while omitting an actual source row.
        wrong_b = collection.sources[b_key].model_copy(update={"data": []})
        wrong_rows = collection.model_copy(
            update={"sources": {**collection.sources, b_key: wrong_b}}
        )
        bad_rows_ref = fresh_store.put_json(
            wrong_rows,
            ArtifactWriteOptions(
                kind="fabric.source_collection",
                media_type="application/json",
                schema=SchemaInfo(name="fabric.SourceCollection", version="1.0"),
                inputs=manifest_view.inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        with pytest.raises(ValueError, match="data differs"):
            _load_binding_payload(
                fresh_store, snapshot.model_copy(update={"data_ref": bad_rows_ref})
            )
        # Preserve the original source-to-artifact counterexample as well as
        # the new actual-consumer controls: valid B6 may advance beside an
        # independently mismatched A10 graph, but A must remain at A9.
        a10 = {"event_id": "a-event-10", "source_version": "10"}
        b6 = {"event_id": "b-event-6", "source_version": "6"}
        write_source_history(readers["source_a"], [("a8", []), ("a9", [a9]), ("a10", [a9, a10])])
        write_source_history(readers["source_b"], [("b4", []), ("b5", [b5]), ("b6", [b5, b6])])
        import polisyos.fabric.ingestion.ingestion as ingestion_module

        original_persist = ingestion_module.persist_provenance_graph

        def mismatch_actual_a(store, graph):
            graph.entities["dataset.fixture.source_a.events"].attributes["data_artifact_id"] = (
                "unbound"
            )
            return original_persist(store, graph)

        with pytest.MonkeyPatch.context() as patcher:
            patcher.setattr(ingestion_module, "persist_provenance_graph", mismatch_actual_a)
            negative = run()
        assert negative.status == "partial" and negative.data_snapshot_ref is None
        cursors = CursorStore(FileSystemCAS(cas_root))
        assert cursors.find_latest_cursor("fixture.source_a", "events").watermark_value == "a9"
        assert cursors.find_latest_cursor("fixture.source_b", "events").watermark_value == "b6"
        partial_evidence = load_core_json_artifact(
            FileSystemCAS(cas_root), negative.evidence_bundle_ref
        )
        assert any("partial evidence" in note.lower() for note in partial_evidence["notes"])
    finally:
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
            runtime_options=_non_deduping_options(
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
        runtime_options=_non_deduping_options(
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
@pytest.mark.parametrize(
    "backpressure_strategy",
    ["pause", "throttle", "fail_closed", "spill_to_disk"],
)
@pytest.mark.asyncio
async def test_b84_restored_state_over_new_capacity_refuses_before_source_or_cas_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stream_registry: ConnectorRegistry,
    strategy: str,
    backpressure_strategy: str,
) -> None:
    """A smaller restored cap fails before rewind/poll and leaves the old frontier intact."""
    rows, policy, _expected = _window_case(strategy)
    # Force every strategy to retain the first two rows at the crash frontier.
    policy = WindowPolicy(
        strategy=policy.strategy,
        # The TUMBLING fixture's first two timestamps are five seconds apart;
        # use one 60-second bucket so this really restores two retained rows.
        size=60 if strategy == "tumbling" else 4,
        slide=1 if strategy == "sliding" else policy.slide,
        session_gap_seconds=policy.session_gap_seconds,
        timestamp_field=policy.timestamp_field,
    )
    dataset_id = f"restore-{strategy}-{backpressure_strategy}"
    stream_path = tmp_path / f"{dataset_id}.jsonl"
    stream_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    registry = _configure_stream_registry(stream_registry, stream_path)
    cas_root = tmp_path / f"restore-cas-{strategy}-{backpressure_strategy}"
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
            dataset_id=dataset_id,
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            runtime_options=_non_deduping_options(
                checkpoint_every_chunks=1,
                max_buffered_rows=3,
                max_buffered_bytes=100_000,
                window_policy=policy,
                processing_contract=_capacity_processing_contract(
                    backpressure_strategy,
                    max_rows=3,
                    max_bytes=100_000,
                ),
            ),
            registry=registry,
        )

    monkeypatch.setattr(StreamingSourceSession, "poll", original_poll)
    before = CursorStore(FileSystemCAS(cas_root))
    prior_checkpoint = before.find_latest_stream_checkpoint("stream.jsonl", dataset_id)
    prior_cursor = before.find_latest_cursor("stream.jsonl", dataset_id)
    assert prior_checkpoint is not None
    assert prior_checkpoint.metadata["frontier_intent"]["state"] == "committed"
    accumulator_state = prior_checkpoint.metadata["operator_state"]["accumulator"]
    retained_row_count = sum(
        len(accumulator_state.get(key, ()))
        for key in (
            "count_buffer",
            "sliding_rows",
            "bucket_rows",
            "session_rows",
            "sliding_time_rows",
        )
    )
    assert retained_row_count == 2, "the lower-cap restore must contain two actual retained rows"
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
            dataset_id=dataset_id,
            store=resumed_store,
            cursor_store=CursorStore(resumed_store),
            sanitize_rows=_valid_rows,
            runtime_options=_non_deduping_options(
                checkpoint_every_chunks=1,
                max_buffered_rows=1,
                max_buffered_bytes=100_000,
                window_policy=policy,
                processing_contract=_capacity_processing_contract(
                    backpressure_strategy,
                    max_rows=1,
                    max_bytes=100_000,
                ),
            ),
            registry=registry,
        )

    assert effects == {"rewind": 0, "poll": 0, "commit": 0}
    after = CursorStore(FileSystemCAS(cas_root))
    assert after.find_latest_stream_checkpoint("stream.jsonl", dataset_id).model_dump(
        mode="json"
    ) == prior_checkpoint.model_dump(mode="json")
    current_cursor = after.find_latest_cursor("stream.jsonl", dataset_id)
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
        dataset_id=dataset_id,
        store=retry_store,
        cursor_store=CursorStore(retry_store),
        sanitize_rows=_valid_rows,
        runtime_options=_non_deduping_options(
            checkpoint_every_chunks=1,
            max_buffered_rows=4,
            max_buffered_bytes=100_000,
            window_policy=policy,
            processing_contract=_capacity_processing_contract(
                backpressure_strategy,
                max_rows=4,
                max_bytes=100_000,
            ),
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
@pytest.mark.parametrize(
    "backpressure_strategy",
    ["pause", "throttle", "fail_closed", "spill_to_disk"],
)
@pytest.mark.asyncio
async def test_b84_capacity_exactly_allows_a_window_closing_transition(
    tmp_path: Path,
    stream_registry: ConnectorRegistry,
    strategy: str,
    backpressure_strategy: str,
) -> None:
    """A row that closes/advances an operator at its declared cap is admissible."""
    rows, policy, expected = _window_case(strategy)
    dataset_id = f"at-cap-{strategy}-{backpressure_strategy}"
    stream_path = tmp_path / f"{dataset_id}.jsonl"
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
    cas_root = tmp_path / f"at-cap-cas-{strategy}-{backpressure_strategy}"
    result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id=dataset_id,
        store=FileSystemCAS(cas_root),
        cursor_store=CursorStore(FileSystemCAS(cas_root)),
        sanitize_rows=_valid_rows,
        runtime_options=_non_deduping_options(
            checkpoint_every_chunks=1,
            max_buffered_rows=2,
            max_buffered_bytes=cap_bytes,
            window_policy=policy,
            processing_contract=_capacity_processing_contract(
                backpressure_strategy,
                max_rows=2,
                max_bytes=cap_bytes,
            ),
        ),
        registry=registry,
    )
    store = FileSystemCAS(cas_root)
    actual_rows, _lineage = _window_rows_and_lineage(store, result.chunk_refs, result.window_refs)
    assert actual_rows == expected


@pytest.mark.parametrize("strategy", ["count", "tumbling", "session", "sliding"])
@pytest.mark.parametrize(
    "backpressure_strategy",
    ["pause", "throttle", "fail_closed", "spill_to_disk"],
)
@pytest.mark.asyncio
async def test_b84_live_operator_over_capacity_refuses_and_preserves_frontier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stream_registry: ConnectorRegistry,
    strategy: str,
    backpressure_strategy: str,
) -> None:
    """A third actually retained row is refused under every strategy."""
    import polisyos.fabric.data_plane.streaming as streaming_module

    rows, policy = _over_capacity_window_case(strategy)
    dataset_id = f"over-cap-{strategy}-{backpressure_strategy}"
    stream_path = tmp_path / f"{dataset_id}.jsonl"
    stream_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    registry = _configure_stream_registry(stream_registry, stream_path)
    cas_root = tmp_path / f"over-cap-cas-{strategy}-{backpressure_strategy}"
    store = FileSystemCAS(cas_root)
    before_third: dict[str, Any] = {}
    poll_calls = {"count": 0}
    original_poll = StreamingSourceSession.poll

    async def capture_predecessor_before_third_poll(session: StreamingSourceSession):
        if poll_calls["count"] == 2:
            before = CursorStore(FileSystemCAS(cas_root))
            checkpoint = before.find_latest_stream_checkpoint("stream.jsonl", dataset_id)
            cursor = before.find_latest_cursor("stream.jsonl", dataset_id)
            assert checkpoint is not None
            before_third["checkpoint"] = checkpoint
            before_third["cursor"] = cursor
            before_third["artifacts"] = set(map(str, FileSystemCAS(cas_root).iter_artifact_ids()))
            accumulator_state = checkpoint.metadata["operator_state"]["accumulator"]
            before_third["retained_rows"] = sum(
                len(accumulator_state.get(key, ()))
                for key in (
                    "count_buffer",
                    "sliding_rows",
                    "bucket_rows",
                    "session_rows",
                    "sliding_time_rows",
                )
            )
        poll_calls["count"] += 1
        return await original_poll(session)

    monkeypatch.setattr(StreamingSourceSession, "poll", capture_predecessor_before_third_poll)
    with pytest.raises(getattr(streaming_module, "StreamCapacityError", RuntimeError)) as exc_info:
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            store=store,
            cursor_store=CursorStore(store),
            sanitize_rows=_valid_rows,
            runtime_options=_non_deduping_options(
                checkpoint_every_chunks=1,
                max_buffered_rows=2,
                max_buffered_bytes=100_000,
                window_policy=policy,
                processing_contract=_capacity_processing_contract(
                    backpressure_strategy,
                    max_rows=2,
                    max_bytes=100_000,
                ),
            ),
            registry=registry,
        )

    assert type(exc_info.value).__name__ == "StreamCapacityError"
    assert exc_info.value.stage == "operator"
    assert exc_info.value.rows == 3
    assert exc_info.value.max_rows == 2
    assert poll_calls["count"] == 3, "admission must inspect the transition that would overflow"
    assert before_third["checkpoint"].offset == 1
    assert before_third["retained_rows"] == 2
    after = CursorStore(FileSystemCAS(cas_root))
    assert after.find_latest_stream_checkpoint("stream.jsonl", dataset_id).model_dump(
        mode="json"
    ) == before_third["checkpoint"].model_dump(mode="json")
    current_cursor = after.find_latest_cursor("stream.jsonl", dataset_id)
    previous_cursor = before_third["cursor"]
    assert (current_cursor.model_dump(mode="json") if current_cursor else None) == (
        previous_cursor.model_dump(mode="json") if previous_cursor else None
    )
    after_store = FileSystemCAS(cas_root)
    current_artifacts = set(map(str, after_store.iter_artifact_ids()))
    extra_artifacts = current_artifacts - before_third["artifacts"]
    extra_details: list[dict[str, Any]] = []
    for artifact_ref in sorted(extra_artifacts):
        manifest = after_store.get_manifest(artifact_ref)
        detail: dict[str, Any] = {"artifact_ref": artifact_ref, "kind": manifest.kind}
        if manifest.kind == "fabric.stream_chunk":
            payload = from_canonical_bytes(after_store.get_bytes(artifact_ref))
            detail["chunk_index"] = payload["chunk_index"]
            detail["message_ids"] = [row.get("_message_id") for row in payload["data"]]
        extra_details.append(detail)
    assert not extra_details, (
        f"capacity refusal persisted rejected-input artifacts: {extra_details}"
    )


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
        runtime_options=_non_deduping_options(
            batch_size=batch_size,
            checkpoint_every_chunks=1,
            dedupe_key_fields=("event_id",),
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


@pytest.mark.asyncio
async def test_guarded_cas_runs_cdc_quarantine_on_exact_root_and_refuses_rootless_proxy(
    tmp_path: Path,
    stream_registry: ConnectorRegistry,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """Dynamic guarded CAS remains usable, while missing rooted capability fails closed."""
    store = FileSystemCAS(tmp_path / "guarded-cdc-cas")
    cursor_store = CursorStore(store)
    guard = BlockingDependencyGuard(
        dependency_name="test-guarded-cdc-cas",
        timeout_seconds=5.0,
        breaker=CircuitBreaker(
            "test-guarded-cdc-cas",
            CircuitBreakerConfig(min_throughput=1),
        ),
    )
    request.addfinalizer(guard.close)
    guard_calls: list[str] = []
    guarded_run = guard.run

    def record_guard_call(
        function: Callable[..., object], *args: object, **kwargs: object
    ) -> object:
        guard_calls.append(function.__name__)
        return guarded_run(function, *args, **kwargs)

    monkeypatch.setattr(guard, "run", record_guard_call)
    guarded_store = GuardedDependencyProxy(target=store, guard=guard)
    assert matches_runtime_protocol(guarded_store, IndexedArtifactStore)

    options = _non_deduping_options(
        batch_size=1,
        checkpoint_every_chunks=1,
        dedupe_key_fields=("event_id",),
        max_dedupe_keys=16,
        window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=32),
    )
    guarded_path = tmp_path / "guarded-cdc.jsonl"
    guarded_path.write_text(
        "\n".join(
            (
                json.dumps({"event_id": "before", "value": 1, "note": "baseline"}),
                json.dumps({"event_id": "after", "value": 2}),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    _configure_stream_registry(stream_registry, guarded_path, chunk_size=1)
    result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id="guarded-cdc",
        store=guarded_store,
        cursor_store=cursor_store,
        sanitize_rows=_valid_rows,
        runtime_options=options,
        registry=stream_registry,
    )

    assert result.quarantined_rows == 1
    assert len(result.cdc_event_refs) == 1
    assert "put_json" in guard_calls
    assert store.root == quarantine_index_path(guarded_store).parents[1]
    assert quarantine_index_path(store).is_file()
    records = list_quarantine_records(store, source="stream:stream.jsonl:guarded-cdc")
    assert len(records) == 1
    assert load_quarantine_payload(store, records[0][1].raw_payload_ref) == [
        {"event_id": "after", "value": 2}
    ]

    class RootlessGuardedProxy(GuardedDependencyProxy):
        def __getattr__(self, name: str) -> Any:
            if name == "root":
                raise AttributeError(name)
            return super().__getattr__(name)

    rootless_store = RootlessGuardedProxy(target=store, guard=guard)
    assert not matches_runtime_protocol(rootless_store, IndexedArtifactStore)
    rootless_path = tmp_path / "rootless-cdc.jsonl"
    rootless_path.write_text(
        "\n".join(
            (
                json.dumps({"event_id": "before", "value": 1, "note": "baseline"}),
                json.dumps({"event_id": "after", "value": 2}),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    _configure_stream_registry(stream_registry, rootless_path, chunk_size=1)
    before_refusal = set(map(str, store.iter_artifact_ids()))
    with pytest.raises(TypeError, match="rooted mutable index"):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="rootless-cdc",
            store=rootless_store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            runtime_options=options,
            registry=stream_registry,
        )
    after_refusal = set(map(str, store.iter_artifact_ids()))
    new_kinds = {
        store.get_manifest(artifact_id).kind for artifact_id in after_refusal - before_refusal
    }
    assert "fabric.cdc_schema_change" not in new_kinds
    assert list_quarantine_records(store, source="stream:stream.jsonl:rootless-cdc") == []


def test_b88_served_replay_uses_owned_fixture_catalog_and_reads_back_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The served replay path runs end to end against a tiny owned catalog."""
    from dataclasses import replace

    from _helpers.runtime_http import build_runtime_api_env, close_runtime_api_env

    from polisyos.core.artifacts.manifest import ArtifactID
    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_forge.read_api import catalog as catalog_api
    from polisyos.fabric.data_plane.replay_store import ReplayStore
    from polisyos.runtime.http.services.control import run_lifecycle as control_lifecycle
    from polisyos.runtime.quality import substrate_registry
    from tests.unit.runtime.http import test_b88_served_replay as b88

    catalog_root = tmp_path / "fixture-catalog"
    catalog_api.build_slice0_fixture_catalog_graph(catalog_root).close()
    original_catalog_paths = substrate_registry.default_substrate_catalog_paths
    # ControlPlaneService resolves its policy-engine root from the owner
    # module, independently of pytest's current working directory.
    runtime_root = Path(control_lifecycle.__file__).resolve().parents[6]
    monkeypatch.setattr(
        substrate_registry,
        "default_substrate_catalog_paths",
        lambda root: (
            replace(
                original_catalog_paths(root),
                l1_dcat_path=catalog_root / "catalog.duckdb",
            )
            if Path(root).resolve() == runtime_root
            else original_catalog_paths(root)
        ),
    )

    ConnectorRegistry.reset_instance()
    env = build_runtime_api_env(tmp_path / "runtime", include_test_client=True)
    try:
        b88._register_connector()
        client, cell_id, headers = b88._secure_control_client(
            env,
            role=PolicyOSRole.ANALYST,
            case_id="e02-b88-fixture-catalog",
        )
        simulators, native_requests = b88._capture_replay(monkeypatch)
        ordinary_calls: list[bool] = []

        import polisyos.fabric.data_plane.orchestrator as orchestrator_module

        original_ordinary = orchestrator_module.run_orchestrated_ingestion

        def observe_ordinary(**kwargs: Any):
            ordinary_calls.append(True)
            return original_ordinary(**kwargs)

        monkeypatch.setattr(
            orchestrator_module,
            "run_orchestrated_ingestion",
            observe_ordinary,
        )
        fixture_body = b'[{"value":714,"marker":"b88-owned-catalog-replay"}]'
        with client:
            container = client.app.state.runtime_container
            assert container.control_service is not None
            assert container.control_service._retrieval_catalog is not None
            assert container.control_service._retrieval_catalog._store._db_path == (
                catalog_root / "catalog.duckdb"
            )
            store = container.runtime_api_context.store
            with tenant_scope(None, tenant_id=env["tenant_a"], cell_id=cell_id):
                replay_ref, request_hash = b88._persist_session(
                    store,
                    response_body=fixture_body,
                )
            response = b88._post_ingest(client, headers, replay_ref=replay_ref)

            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "completed"
            assert body["mode_effective"] == "replay"
            assert body["datasets_fetched"] == 1
            assert body["evidence_bundle_ref"] is not None
            assert len(simulators) == 1
            assert simulators[0].call_count == 1
            assert simulators[0].call_log[0]["hash"] == request_hash
            assert native_requests == []
            assert ordinary_calls == []

            with tenant_scope(None, tenant_id=env["tenant_a"], cell_id=cell_id):
                persisted = ReplayStore(store).load_record_session(
                    ArtifactID.model_validate(replay_ref)
                )
                assert len(persisted.fixtures) == 1
                assert persisted.fixtures[0]["request_hash"] == request_hash
                assert b88.base64.b64decode(persisted.fixtures[0]["body"]) == fixture_body
                b88._assert_evidence_contains_source_bytes(
                    store,
                    body["evidence_bundle_ref"],
                    b"b88-owned-catalog-replay",
                )

            for broken_body in (None, b"not-json"):
                with tenant_scope(None, tenant_id=env["tenant_a"], cell_id=cell_id):
                    broken_ref, _ = b88._persist_session(
                        store,
                        response_body=broken_body,
                    )
                failed = b88._post_ingest(client, headers, replay_ref=broken_ref)
                assert failed.status_code == 200
                failed_body = failed.json()
                assert failed_body["status"] == "failed"
                assert failed_body["mode_effective"] == "replay"
                assert failed_body["datasets_fetched"] == 0
                assert failed_body["evidence_bundle_ref"] is None

            assert len(simulators) == 3
            assert all(simulator.call_count == 1 for simulator in simulators)
            assert native_requests == []
            assert ordinary_calls == []
    finally:
        close_runtime_api_env(env)
        ConnectorRegistry.reset_instance()


@pytest.mark.asyncio
async def test_b83_live_event_key_cap_refuses_without_eviction_and_retries_from_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stream_registry: ConnectorRegistry,
) -> None:
    """A cap of two refuses c without evicting a; a larger retry replays c then a."""
    import polisyos.fabric.data_plane.streaming as streaming_module

    # These are explicit synthetic JSONL event/version fields. Their names do
    # not establish a real source owner's key contract.
    rows = [
        {"event_id": "evt", "source_version": 1, "entity_id": "entity-1", "value": "a"},
        {"event_id": "evt", "source_version": 2, "entity_id": "entity-1", "value": "b"},
        {"event_id": "evt-c", "source_version": 1, "entity_id": "entity-2", "value": "c"},
        {"event_id": "evt", "source_version": 1, "entity_id": "entity-1", "value": "a-redelivery"},
    ]
    dataset_id = "dedupe-live-cap"
    stream_path = tmp_path / "dedupe-live-cap.jsonl"
    stream_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    registry = _configure_stream_registry(stream_registry, stream_path)
    reader = finite_source_reader(
        tmp_path / "source-owner",
        connector_id="stream.jsonl",
        dataset_id=dataset_id,
        schema_id="fixture.source_events",
        snapshots=[("fixture-current", rows[:3])],
        transport_path=stream_path,
    )
    cas_root = tmp_path / "dedupe-live-cap-cas"
    store = FileSystemCAS(cas_root)
    clock = {"now": datetime(2026, 10, 6, tzinfo=UTC)}
    monkeypatch.setattr(
        streaming_module,
        "_ingestion_utc",
        lambda: clock["now"],
        raising=False,
    )
    original_poll = StreamingSourceSession.poll
    poll_state = {"count": 0}

    async def crash_before_third_source_chunk(session: StreamingSourceSession):
        if poll_state["count"] == 2:
            raise _ProcessDeath("leave a and b at the committed horizon")
        poll_state["count"] += 1
        return await original_poll(session)

    monkeypatch.setattr(StreamingSourceSession, "poll", crash_before_third_source_chunk)
    with pytest.raises(_ProcessDeath):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            store=store,
            cursor_store=CursorStore(store),
            sanitize_rows=_valid_rows,
            runtime_options=_dedupe_options(max_dedupe_keys=2),
            registry=registry,
            source_progress_readers=(reader,),
        )

    monkeypatch.setattr(StreamingSourceSession, "poll", original_poll)
    before = CursorStore(FileSystemCAS(cas_root))
    prior_checkpoint = before.find_latest_stream_checkpoint("stream.jsonl", dataset_id)
    prior_cursor = before.find_latest_cursor("stream.jsonl", dataset_id)
    assert prior_checkpoint is not None
    assert prior_cursor is not None
    prior_entries = _dedupe_horizon_entries(prior_checkpoint)
    key_a1 = (("event_id", "evt"), ("source_version", 1))
    key_a2 = (("event_id", "evt"), ("source_version", 2))
    key_c1 = (("event_id", "evt-c"), ("source_version", 1))
    assert set(prior_entries) == {key_a1, key_a2}
    assert prior_checkpoint.metadata["dedupe_horizon"]["scope"] == [
        "stream.jsonl",
        dataset_id,
        "default",
    ]
    prior_ids = set(map(str, FileSystemCAS(cas_root).iter_artifact_ids()))

    unsupported_type = getattr(streaming_module, "StreamDedupeUnsupported", RuntimeError)
    with pytest.raises(unsupported_type) as exc_info:
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            store=FileSystemCAS(cas_root),
            cursor_store=CursorStore(FileSystemCAS(cas_root)),
            sanitize_rows=_valid_rows,
            runtime_options=_dedupe_options(max_dedupe_keys=2),
            registry=registry,
            source_progress_readers=(reader,),
        )
    assert type(exc_info.value).__name__ == "StreamDedupeUnsupported"

    after_refusal = CursorStore(FileSystemCAS(cas_root))
    assert after_refusal.find_latest_stream_checkpoint("stream.jsonl", dataset_id).model_dump(
        mode="json"
    ) == prior_checkpoint.model_dump(mode="json")
    current_cursor = after_refusal.find_latest_cursor("stream.jsonl", dataset_id)
    assert current_cursor.model_dump(mode="json") == prior_cursor.model_dump(mode="json")
    assert set(map(str, FileSystemCAS(cas_root).iter_artifact_ids())) == prior_ids

    retried_store = FileSystemCAS(cas_root)
    retried = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id=dataset_id,
        store=retried_store,
        cursor_store=CursorStore(retried_store),
        sanitize_rows=_valid_rows,
        runtime_options=_dedupe_options(max_dedupe_keys=3),
        registry=registry,
        source_progress_readers=(reader,),
    )
    assert retried.dedupe_dropped == 1
    final_checkpoint = CursorStore(retried_store).find_latest_stream_checkpoint(
        "stream.jsonl",
        dataset_id,
    )
    assert final_checkpoint is not None
    assert set(_dedupe_horizon_entries(final_checkpoint)) == {key_a1, key_a2, key_c1}
    emitted = _persisted_stream_rows(retried_store, dataset_id=dataset_id)
    assert [(row["event_id"], row["source_version"]) for row in emitted] == [
        ("evt", 1),
        ("evt", 2),
        ("evt-c", 1),
    ]


@pytest.mark.asyncio
async def test_b83_nonempty_legacy_dedupe_keys_without_utc_time_refuse_before_rewind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stream_registry: ConnectorRegistry,
) -> None:
    """A legacy key list cannot be resumed by inventing ingestion timestamps."""
    import polisyos.fabric.data_plane.streaming as streaming_module

    row = {"event_id": "evt", "source_version": 1, "entity_id": "entity"}
    dataset_id = "dedupe-legacy-no-time"
    stream_path = tmp_path / f"{dataset_id}.jsonl"
    stream_path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    registry = _configure_stream_registry(stream_registry, stream_path)
    reader = finite_source_reader(
        tmp_path / "source-owner",
        connector_id="stream.jsonl",
        dataset_id=dataset_id,
        schema_id="fixture.source_events",
        snapshots=[("fixture-current", [row])],
        transport_path=stream_path,
    )
    cas_root = tmp_path / f"{dataset_id}-cas"
    store = FileSystemCAS(cas_root)
    runtime_options = _dedupe_options(max_dedupe_keys=2)
    result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id=dataset_id,
        store=store,
        cursor_store=CursorStore(store),
        sanitize_rows=_valid_rows,
        runtime_options=runtime_options,
        registry=registry,
        source_progress_readers=(reader,),
    )
    assert result.final_checkpoint is not None
    checkpoint = result.final_checkpoint
    assert checkpoint.dedupe_keys
    assert "dedupe_horizon" in checkpoint.metadata

    legacy_metadata = dict(checkpoint.metadata)
    legacy_metadata.pop("dedupe_horizon")
    legacy_metadata.pop("frontier_intent", None)
    legacy_checkpoint = checkpoint.model_copy(update={"metadata": legacy_metadata})
    before = CursorStore(FileSystemCAS(cas_root))
    before.save_stream_checkpoint(legacy_checkpoint)
    prior_cursor = before.find_latest_cursor("stream.jsonl", dataset_id)
    assert prior_cursor is not None
    seeded_checkpoint = before.find_latest_stream_checkpoint("stream.jsonl", dataset_id)
    assert seeded_checkpoint is not None
    assert seeded_checkpoint.dedupe_keys
    assert "dedupe_horizon" not in seeded_checkpoint.metadata
    prior_ids = set(map(str, FileSystemCAS(cas_root).iter_artifact_ids()))

    effects = {"rewind": 0, "poll": 0, "commit": 0}
    original_rewind = StreamingSourceSession.rewind
    original_poll = StreamingSourceSession.poll
    original_commit = StreamingSourceSession.commit

    async def count_rewind(session: StreamingSourceSession, prior: Any) -> None:
        effects["rewind"] += 1
        await original_rewind(session, prior)

    async def count_poll(session: StreamingSourceSession):
        effects["poll"] += 1
        return await original_poll(session)

    async def count_commit(session: StreamingSourceSession, prior: Any) -> None:
        effects["commit"] += 1
        await original_commit(session, prior)

    monkeypatch.setattr(StreamingSourceSession, "rewind", count_rewind)
    monkeypatch.setattr(StreamingSourceSession, "poll", count_poll)
    monkeypatch.setattr(StreamingSourceSession, "commit", count_commit)
    unsupported_type = getattr(streaming_module, "StreamDedupeUnsupported", RuntimeError)
    with pytest.raises(unsupported_type, match="UTC|ingestion time|horizon") as exc_info:
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            store=FileSystemCAS(cas_root),
            cursor_store=CursorStore(FileSystemCAS(cas_root)),
            sanitize_rows=_valid_rows,
            runtime_options=runtime_options,
            registry=registry,
            source_progress_readers=(reader,),
        )

    assert type(exc_info.value).__name__ == "StreamDedupeUnsupported"
    assert effects == {"rewind": 0, "poll": 0, "commit": 0}
    after = CursorStore(FileSystemCAS(cas_root))
    assert after.find_latest_stream_checkpoint("stream.jsonl", dataset_id).model_dump(
        mode="json"
    ) == seeded_checkpoint.model_dump(mode="json")
    current_cursor = after.find_latest_cursor("stream.jsonl", dataset_id)
    assert current_cursor.model_dump(mode="json") == prior_cursor.model_dump(mode="json")
    assert set(map(str, FileSystemCAS(cas_root).iter_artifact_ids())) == prior_ids


@pytest.mark.asyncio
async def test_b83_first_accepted_key_expires_at_utc_86400_seconds_after_restart(
    tmp_path: Path,
) -> None:
    """Independent processes reopen one CAS across the exact UTC expiry boundary."""
    first_accepted = datetime(2026, 1, 1, tzinfo=UTC)
    duplicate_v1 = {
        "event_id": "entity-event",
        "source_version": 1,
        "entity_id": "same-entity",
        "value": "version-1",
    }
    version_v2 = {**duplicate_v1, "source_version": 2, "value": "version-2"}
    root = tmp_path / "process-horizon"
    root.mkdir()
    (root / "stream.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in (duplicate_v1, version_v2)),
        encoding="utf-8",
    )
    reader = finite_source_reader(
        root / "source-owner",
        connector_id="stream.jsonl",
        dataset_id="horizon",
        schema_id="fixture.source_events",
        snapshots=[("fixture-current", [duplicate_v1, version_v2])],
        transport_path=root / "stream.jsonl",
    )
    common = {
        "root": str(root),
        "source_root": str(reader.source_root),
        "source_contract": reader.source_contract.model_dump(mode="json"),
        "extension": reader.extension.model_dump(mode="json"),
        "event": duplicate_v1,
    }

    child_artifacts = tmp_path / "child-process-artifacts"
    child_artifacts.mkdir()
    first_child_elapsed: float | None = None

    def run_worker(name: str, **updates: Any) -> tuple[subprocess.CompletedProcess[str], Any]:
        nonlocal first_child_elapsed
        artifact_dir = child_artifacts / name
        artifact_dir.mkdir()
        config_path = artifact_dir / "config.json"
        config_bytes = json.dumps({**common, **updates}, sort_keys=True).encode("utf-8")
        config_path.write_bytes(config_bytes)
        argv = [
            sys.executable,
            "-B",
            "-m",
            "tests._helpers.source_progress_stream_worker",
            str(config_path),
        ]
        cwd = Path(__file__).parents[4].resolve()
        # Use a generous first-run guard; later bounds derive from the measured first child.
        timeout_seconds = (
            120.0
            if first_child_elapsed is None
            else max(60.0, min(300.0, first_child_elapsed * 5.0 + 10.0))
        )
        started = time.monotonic()
        with subprocess.Popen(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as child:
            try:
                stdout, stderr = child.communicate(timeout=timeout_seconds)
                timed_out = False
            except subprocess.TimeoutExpired:
                child.kill()
                stdout, stderr = child.communicate()
                timed_out = True
            elapsed_seconds = time.monotonic() - started
            completed = subprocess.CompletedProcess(argv, child.returncode, stdout, stderr)
            child_pid = child.pid
        if first_child_elapsed is None:
            first_child_elapsed = elapsed_seconds
        (artifact_dir / "stdout.txt").write_text(stdout, encoding="utf-8")
        (artifact_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
        try:
            child_result = json.loads(stdout)
        except json.JSONDecodeError:
            child_result = None
        (artifact_dir / "run.json").write_text(
            json.dumps(
                {
                    "argv": argv,
                    "cwd": str(cwd),
                    "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
                    "returncode": child.returncode,
                    "elapsed_seconds": elapsed_seconds,
                    "timeout_seconds": timeout_seconds,
                    "timed_out": timed_out,
                    "pid": child_pid,
                    "reported_pid": (
                        child_result.get("pid") if isinstance(child_result, dict) else None
                    ),
                    "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
                    "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        assert not timed_out, f"child timed out; complete evidence: {artifact_dir}"
        assert completed.returncode == 0, (
            f"child failed; complete evidence: {artifact_dir}\n{stderr}"
        )
        assert isinstance(child_result, dict), f"child emitted no JSON; evidence: {artifact_dir}"
        assert child_result["pid"] == child_pid
        return completed, child_result

    _initial_process, initial = run_worker(
        "initial",
        steps=[
            {
                "at": first_accepted.isoformat(),
                "append": False,
                "ingestion_times": [
                    first_accepted.isoformat(),
                    (first_accepted + timedelta(seconds=10)).isoformat(),
                ],
            }
        ],
    )
    assert initial["pid"] != os.getpid()
    assert initial["clock_profile"] == "fixture_utc"
    assert all("error_type" not in item for item in initial["results"]), initial
    assert [(item["rows_emitted"], item["dedupe_dropped"]) for item in initial["results"]] == [
        (2, 0),
    ]
    cas_root = root / "cas"
    prior_checkpoint = CursorStore(FileSystemCAS(cas_root)).find_latest_stream_checkpoint(
        "stream.jsonl", "horizon"
    )
    assert prior_checkpoint is not None
    key_v1 = (("event_id", "entity-event"), ("source_version", 1))
    key_v2 = (("event_id", "entity-event"), ("source_version", 2))
    assert _dedupe_horizon_entries(prior_checkpoint) == {
        key_v1: first_accepted,
        key_v2: first_accepted + timedelta(seconds=10),
    }

    index_path = cas_root / "stream_checkpoint_index.json"
    index_before_removal = index_path.read_bytes()
    artifact_ids_before_removal = tuple(map(str, FileSystemCAS(cas_root).iter_artifact_ids()))
    _removed_process, removed = run_worker(
        "binding-removed",
        remove_source_binding=True,
        steps=[{"at": first_accepted.isoformat(), "append": False}],
    )
    assert removed["pid"] not in {os.getpid(), initial["pid"]}
    assert removed["results"][0]["error_type"] == "StreamDedupeUnsupported"
    assert index_path.read_bytes() == index_before_removal
    assert (
        tuple(map(str, FileSystemCAS(cas_root).iter_artifact_ids())) == artifact_ids_before_removal
    )

    _boundary_process, boundary = run_worker(
        "boundary",
        steps=[
            {
                "at": (first_accepted + timedelta(seconds=86_399)).isoformat(),
                "append": True,
                "event": {**duplicate_v1, "value": "redelivery-before-expiry"},
            },
            {
                "at": (first_accepted + timedelta(seconds=86_400)).isoformat(),
                "append": True,
                "event": {**duplicate_v1, "value": "redelivery-at-expiry"},
            },
        ],
    )
    assert boundary["pid"] not in {
        os.getpid(),
        initial["pid"],
        removed["pid"],
    }
    expected_source_modules = {
        "polisyos.core.artifacts.store",
        "polisyos.fabric.data_plane.cursor_store",
        "polisyos.fabric.data_plane.streaming",
        "polisyos.fabric.ingestion.source_progress",
    }
    for child_result in (initial, removed, boundary):
        assert set(child_result["source_modules"]) == expected_source_modules
        for module_identity in child_result["source_modules"].values():
            assert Path(module_identity["origin"]).is_absolute()
            assert len(module_identity["sha256"]) == 64
            int(module_identity["sha256"], 16)
    assert [(item["rows_emitted"], item["dedupe_dropped"]) for item in boundary["results"]] == [
        (0, 1),
        (1, 0),
    ]
    boundary_before_expiry = boundary["results"][0]["dedupe_horizon"]
    assert {
        tuple(
            (str(field), value) for field, value in json.loads(encoded_key)
        ): datetime.fromisoformat(timestamp)
        for encoded_key, timestamp in boundary_before_expiry["entries"].items()
    } == {key_v1: first_accepted, key_v2: first_accepted + timedelta(seconds=10)}

    expiry_store = FileSystemCAS(cas_root)
    final_checkpoint = CursorStore(expiry_store).find_latest_stream_checkpoint(
        "stream.jsonl", "horizon"
    )
    assert final_checkpoint is not None
    assert _dedupe_horizon_entries(final_checkpoint) == {
        key_v1: first_accepted + timedelta(seconds=86_400),
        key_v2: first_accepted + timedelta(seconds=10),
    }
    emitted = _persisted_stream_rows(expiry_store, dataset_id="horizon")
    assert [(row["event_id"], row["source_version"]) for row in emitted] == [
        ("entity-event", 1),
        ("entity-event", 2),
        ("entity-event", 1),
    ]


@pytest.mark.parametrize(
    ("row", "case_id"),
    [
        ({"source_version": 1, "entity_id": "e"}, "missing-event-id"),
        ({"event_id": "evt", "source_version": True}, "boolean-version"),
        ({"event_id": "evt", "source_version": [1]}, "list-version"),
        ({"event_id": "evt", "source_version": 2, "entity_id": "e"}, "unowned-version"),
    ],
    ids=lambda value: str(value)[:40],
)
@pytest.mark.asyncio
async def test_b83_missing_or_nonprimitive_event_version_refuses_without_fallback_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stream_registry: ConnectorRegistry,
    row: dict[str, Any],
    case_id: str,
) -> None:
    """A missing or non-primitive configured key never falls back to a payload hash."""
    import polisyos.fabric.data_plane.streaming as streaming_module

    monkeypatch.setattr(
        streaming_module,
        "_ingestion_utc",
        lambda: datetime(2026, 10, 6, tzinfo=UTC),
        raising=False,
    )
    dataset_id = f"dedupe-invalid-{case_id}"
    stream_path = tmp_path / f"{dataset_id}.jsonl"
    stream_path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    registry = _configure_stream_registry(stream_registry, stream_path)
    reader = finite_source_reader(
        tmp_path / "source-owner",
        connector_id="stream.jsonl",
        dataset_id=dataset_id,
        schema_id="fixture.source_events",
        snapshots=[
            ("fixture-current", [{"event_id": "evt", "source_version": 1, "entity_id": "e"}])
        ],
        transport_path=stream_path,
    )
    cas_root = tmp_path / f"dedupe-invalid-cas-{case_id}"
    store = FileSystemCAS(cas_root)
    before_ids = set(map(str, store.iter_artifact_ids()))
    unsupported_type = getattr(streaming_module, "StreamDedupeUnsupported", RuntimeError)

    with pytest.raises(
        unsupported_type, match="event/version|event-key|dedupe|transport"
    ) as exc_info:
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            store=store,
            cursor_store=CursorStore(store),
            sanitize_rows=_valid_rows,
            runtime_options=_dedupe_options(max_dedupe_keys=2),
            registry=registry,
            source_progress_readers=(reader,),
        )

    assert type(exc_info.value).__name__ == "StreamDedupeUnsupported"
    after = CursorStore(FileSystemCAS(cas_root))
    assert after.find_latest_stream_checkpoint("stream.jsonl", dataset_id) is None
    assert after.find_latest_cursor("stream.jsonl", dataset_id) is None
    assert set(map(str, FileSystemCAS(cas_root).iter_artifact_ids())) == before_ids


@pytest.mark.asyncio
async def test_b83_event_stream_preserves_absent_provider_identity(
    tmp_path: Path,
) -> None:
    """The EventStream producer must not turn a row position into source identity."""
    from polisyos.fabric.connectors.base import FetchRequest
    from polisyos.fabric.connectors.sources.event_stream import EventStreamConnector

    dataset_id = "event-stream-missing-identity"
    source_row = {"entity_id": "entity-1", "value": 1}
    stream_path = tmp_path / "event-stream-missing-identity.jsonl"
    stream_path.write_text(json.dumps(source_row, sort_keys=True) + "\n", encoding="utf-8")
    connector = EventStreamConnector()
    handle = await connector.connect(
        ConnectionConfig(
            url=stream_path.as_uri(),
            headers={"X-Stream-ChunkSize": "1"},
        )
    )
    rows: list[dict[str, Any]] = []
    try:
        async for chunk in connector.fetch_stream(handle, FetchRequest(dataset_id=dataset_id)):
            rows.extend(chunk.data)
    finally:
        await connector.disconnect(handle)

    assert rows == [source_row]


@pytest.mark.parametrize(
    "source_row",
    [
        {"entity_id": "entity-1", "value": 1},
        {"_message_id": "present-but-unowned", "source_version": 1},
        {"event_id": "present-but-unowned", "source_version": 1},
    ],
    ids=["absent", "present-transport-id", "present-event-version-names"],
)
@pytest.mark.asyncio
async def test_b83_missing_owner_identity_refuses_before_checkpoint_or_artifact(
    tmp_path: Path,
    stream_registry: ConnectorRegistry,
    source_row: dict[str, Any],
) -> None:
    """A valid positional transport ID cannot substitute for an owner key contract."""
    import polisyos.fabric.data_plane.streaming as streaming_module

    dataset_id = "default-key-without-owner-contract"
    stream_path = tmp_path / f"{dataset_id}.jsonl"
    stream_path.write_text(
        json.dumps(source_row, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    registry = _configure_stream_registry(stream_registry, stream_path)
    cas_root = tmp_path / f"{dataset_id}-cas"
    store = FileSystemCAS(cas_root)
    prior_artifact_ids = set(map(str, store.iter_artifact_ids()))
    unsupported_type = getattr(streaming_module, "StreamDedupeUnsupported", RuntimeError)

    with pytest.raises(unsupported_type) as exc_info:
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            store=store,
            cursor_store=CursorStore(store),
            sanitize_rows=_valid_rows,
            runtime_options=StreamRuntimeOptions(
                window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=1),
            ),
            registry=registry,
        )

    assert type(exc_info.value).__name__ == "StreamDedupeUnsupported"
    after = CursorStore(FileSystemCAS(cas_root))
    assert after.find_latest_stream_checkpoint("stream.jsonl", dataset_id) is None
    assert after.find_latest_cursor("stream.jsonl", dataset_id) is None
    assert set(map(str, FileSystemCAS(cas_root).iter_artifact_ids())) == prior_artifact_ids


@pytest.mark.asyncio
async def test_b83_horizon_scope_isolated_by_connector_dataset_and_partition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stream_registry: ConnectorRegistry,
) -> None:
    """The same fixture key is admitted independently in each declared scope."""
    import polisyos.fabric.data_plane.streaming as streaming_module
    from polisyos.fabric.connectors.sources.event_stream import EventStreamConnector
    from polisyos.ir.connectors import ConnectorMetadataSpec

    monkeypatch.setattr(
        streaming_module,
        "_ingestion_utc",
        lambda: datetime(2026, 10, 6, tzinfo=UTC),
        raising=False,
    )
    row = {"event_id": "evt", "source_version": 1, "entity_id": "entity"}
    stream_path = tmp_path / "dedupe-scope.jsonl"
    stream_path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    registry = _configure_stream_registry(stream_registry, stream_path)

    class _OtherFixtureConnector(EventStreamConnector):
        namespace = "oracle"
        short_id = "jsonl"
        connector_id = "oracle.jsonl"
        metadata: ClassVar[ConnectorMetadataSpec] = EventStreamConnector.metadata.model_copy(
            update={"namespace": "oracle"}
        )

    registry.register(
        _OtherFixtureConnector,
        config=ConnectionConfig(
            url=stream_path.as_uri(),
            headers={"X-Stream-ChunkSize": "1"},
        ),
    )

    store = FileSystemCAS(tmp_path / "dedupe-scope-cas")
    cursor_store = CursorStore(store)
    scopes = (
        ("stream.jsonl", "dataset-a", "partition-a"),
        ("stream.jsonl", "dataset-a", "partition-b"),
        ("stream.jsonl", "dataset-b", "partition-a"),
        ("oracle.jsonl", "dataset-a", "partition-a"),
    )
    for connector_id, dataset_id, partition_key in scopes:
        reader = finite_source_reader(
            tmp_path / "source-owner",
            connector_id=connector_id,
            dataset_id=dataset_id,
            schema_id=(connector_id + "." + dataset_id).replace("-", "_"),
            snapshots=[("fixture-current", [row])],
            transport_path=stream_path,
            partition_key=partition_key,
        )
        result = await process_stream_dataset(
            connector_id=connector_id,
            dataset_id=dataset_id,
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            runtime_options=_dedupe_options(
                partition_key=partition_key,
                max_dedupe_keys=2,
            ),
            registry=registry,
            source_progress_readers=(reader,),
        )
        assert result.dedupe_dropped == 0
        assert result.rows_emitted == 1
        checkpoint = cursor_store.find_latest_stream_checkpoint(
            connector_id,
            dataset_id,
            partition_key=partition_key,
        )
        assert checkpoint is not None
        assert checkpoint.metadata["dedupe_horizon"]["scope"] == [
            connector_id,
            dataset_id,
            partition_key,
        ]
        assert len(_dedupe_horizon_entries(checkpoint)) == 1
