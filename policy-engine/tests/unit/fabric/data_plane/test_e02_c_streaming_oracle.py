"""Independent behavioral oracles for the E02 C ingestion findings."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar
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


def _jsonl_raw_byte_oracle(
    payload: bytes,
    *,
    dataset_id: str,
) -> tuple[list[dict[str, Any]], list[tuple[int, int, str]], str]:
    """Parse fixture records from exact byte spans and hash the supplied source bytes."""
    rows: list[dict[str, Any]] = []
    spans: list[tuple[int, int, str]] = []
    offset = 0
    for line_index, line in enumerate(payload.splitlines(keepends=True)):
        end = offset + len(line)
        content = line.strip()
        if content:
            row = json.loads(content.decode("utf-8"))
            if not isinstance(row, dict):
                row = {"value": row}
            row.setdefault("_message_id", f"{dataset_id}:{line_index}")
            rows.append(row)
            spans.append((offset, end, hashlib.sha256(line).hexdigest()))
        offset = end
    return rows, spans, hashlib.sha256(payload).hexdigest()


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
            query = parse_qs(parsed.query)
            calls.append((self.command, parsed.path, query))
            since = query.get("since")
            if since == [prior]:
                rows = [{"id": "row-after-prior", "value": 8}]
            elif since is None:
                # The source's full view contains an older row. A since-aware
                # source must return only the later row to the incremental fetch.
                rows = [{"id": "row-before-prior", "value": 1}]
            else:
                rows = [{"id": "unexpected-since", "value": 999}]
            body = json.dumps({"data": rows}).encode()
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
        assert persisted.data == [{"id": "row-after-prior", "value": 8}]
        after = cursor_store.find_latest_cursor("rest.json", "dataset")
        assert after is not None and after.watermark_value == prior
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        registry.shutdown()


def test_b79_served_incremental_route_filters_source_rows_from_the_stored_etag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public ingestion route uses its stored ETag through the real REST source."""
    from dataclasses import replace

    from _helpers.runtime_http import build_runtime_api_env, close_runtime_api_env

    from polisyos.core.artifacts.manifest import ArtifactID
    from polisyos.core.contracts.fabric import EvidenceBundle
    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_forge.read_api import catalog as catalog_api
    from polisyos.fabric.connectors.cache._store_serialization import ResultSerializer
    from polisyos.fabric.connectors.sources.rest_json import RestJsonConnector
    from polisyos.fabric.storage.tenant_cas import TenantSidecarScope
    from polisyos.runtime.http.services.control import run_lifecycle as control_lifecycle
    from polisyos.runtime.quality import substrate_registry
    from tests.unit.runtime.http.test_control_api import (
        _secure_control_client,
        _with_fresh_step_up,
    )

    prior = '"etag-prior"'
    calls: list[dict[str, list[str]]] = []

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            query = parse_qs(urlsplit(self.path).query)
            calls.append(query)
            if query.get("since") == [prior]:
                rows = [{"id": "served-row-after-prior", "value": 12}]
            elif "since" not in query:
                rows = [{"id": "served-row-before-prior", "value": 2}]
            else:
                rows = [{"id": "served-row-wrong-cursor", "value": 999}]
            body = json.dumps({"data": rows}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("ETag", '"etag-next"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance(bootstrap=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    registry.register(
        RestJsonConnector,
        config=ConnectionConfig(
            url=f"http://127.0.0.1:{server.server_port}/records",
            headers={"X-REST-PageSize": "100"},
        ),
    )

    catalog_root = tmp_path / "fixture-catalog"
    catalog_api.build_slice0_fixture_catalog_graph(catalog_root).close()
    original_catalog_paths = substrate_registry.default_substrate_catalog_paths
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

    env: dict[str, object] | None = None
    try:
        env = build_runtime_api_env(tmp_path / "runtime", include_test_client=True)
        client, cell_id, headers = _secure_control_client(
            env,
            role=PolicyOSRole.ANALYST,
            case_id="e02-b79-served-incremental",
        )
        with client:
            container = client.app.state.runtime_container
            store = container.runtime_api_context.store
            cas_root = Path(env["cas_root"])
            tenant_id = str(env["tenant_a"])
            sidecar_scope = TenantSidecarScope.for_base_root(cas_root, tenant_id)
            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                cursor_store = CursorStore(
                    store,
                    index_root=sidecar_scope.cursor_index_root,
                )
                cursor_store.save_cursor(
                    CursorState(
                        cursor_id="rest.json:served-dataset",
                        connector_id="rest.json",
                        dataset_id="served-dataset",
                        watermark_type=WatermarkType.ETAG,
                        watermark_value=prior,
                        created_at=datetime(2026, 10, 1, tzinfo=UTC),
                    )
                )

            response = client.post(
                "/api/v1/control/data/ingest",
                headers=_with_fresh_step_up(client, headers),
                json={
                    "datasets": [{"connector_id": "rest.json", "dataset_id": "served-dataset"}],
                    "source": "e02-b79-fixture",
                    "license_name": "fixture-only",
                    "execution_mode": "batch_incremental",
                    "produce_data_snapshot": False,
                },
            )
            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "completed"
            assert body["mode_effective"] == "batch_incremental"
            assert body["datasets_fetched"] == 1
            assert body["evidence_bundle_ref"] is not None
            assert body["cursor_ref"] is None
            assert [query for query in calls if "since" in query] == [
                {"limit": ["100"], "page": ["1"], "since": [prior]}
            ]

            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                evidence = EvidenceBundle.model_validate(
                    from_canonical_bytes(
                        store.get_bytes(
                            ArtifactID.model_validate(
                                body["evidence_bundle_ref"]
                                if body["evidence_bundle_ref"].startswith("sha256:")
                                else f"sha256:{body['evidence_bundle_ref']}"
                            )
                        )
                    )
                )
                assert len(evidence.sources) == 1
                persisted = ResultSerializer.deserialize(store.get_bytes(evidence.sources[0]))
                assert persisted.data == [{"id": "served-row-after-prior", "value": 12}]
                latest_cursor = CursorStore(
                    store,
                    index_root=sidecar_scope.cursor_index_root,
                ).find_latest_cursor("rest.json", "served-dataset")
                assert latest_cursor is not None
                assert latest_cursor.watermark_value == prior
    finally:
        if env is not None:
            close_runtime_api_env(env)
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        registry.shutdown()
        ConnectorRegistry.reset_instance()


def test_b80_two_source_failure_keeps_predecessors_and_retry_reads_late_event(
    tmp_path: Path,
) -> None:
    """A failed B fetch preserves both source cursors and replay keeps B's late row."""
    from polisyos.core.contracts.fabric import EvidenceBundle
    from polisyos.fabric.connectors.base import HealthStatus
    from polisyos.fabric.connectors.sources.rest_json import RestJsonConnector
    from polisyos.fabric.connectors.types import FetchError
    from polisyos.fabric.data_plane.modes import run_batch_incremental
    from polisyos.fabric.ingestion import resolve_ingestion_dependencies
    from polisyos.ir.connectors import DataVersion, FetchResult, VersionStrategy

    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    source_events: dict[str, list[tuple[str, dict[str, Any] | None]]] = {
        "source_a": [
            ("etag-a8", None),
            (
                "etag-a9",
                {
                    "id": "a-event-9",
                    "source_version": "etag-a9",
                    "event_time": "2025-01-01T00:00:00Z",
                },
            ),
        ],
        "source_b": [
            ("etag-b4", None),
            (
                "etag-b5",
                {
                    "id": "b-late-event-5",
                    "source_version": "etag-b5",
                    "event_time": "2024-01-01T00:00:00Z",
                },
            ),
        ],
    }
    observed_requests: list[tuple[str, str | None]] = []
    fail_b_once = {"pending": True}
    version_time = datetime(2026, 10, 6, tzinfo=UTC)

    def _fixture_class(source_key: str) -> type[RestJsonConnector]:
        async def _health_check(self: Any, handle: Any) -> HealthStatus:
            del self, handle
            return HealthStatus(healthy=True, message="fixture source is ready")

        async def _fetch(self: Any, handle: Any, request: Any) -> FetchResult[list[dict[str, Any]]]:
            del self, handle
            since = (
                request.incremental_since.value if request.incremental_since is not None else None
            )
            observed_requests.append((source_key, since))
            if source_key == "source_b" and fail_b_once["pending"]:
                fail_b_once["pending"] = False
                raise FetchError(
                    "fixture source_b is temporarily unavailable",
                    connector_id="fixture." + source_key,
                    dataset_id="events",
                )

            versions = [version for version, _row in source_events[source_key]]
            if since in versions:
                start_index = versions.index(since) + 1
            else:
                start_index = 0
            remaining = source_events[source_key][start_index:]
            rows = [row for _version, row in remaining if row is not None]
            current_version = remaining[-1][0] if remaining else (since or versions[0])
            return FetchResult(
                data=rows,
                row_count=len(rows),
                schema_id="fixture.e02.source_events",
                schema_version="1.0",
                version=DataVersion(
                    strategy=VersionStrategy.ETAG,
                    value=current_version,
                    timestamp=version_time,
                ),
                fetched_at=version_time,
                completeness=1.0,
            )

        metadata = RestJsonConnector.metadata.model_copy(
            update={
                "connector_id": source_key,
                "namespace": "fixture",
                "source_name": f"Fixture {source_key}",
                "source_organization": "E02 oracle",
            }
        )
        return type(
            f"{source_key.title()}FixtureConnector",
            (RestJsonConnector,),
            {
                "__module__": __name__,
                "connector_id": f"fixture.{source_key}",
                "namespace": "fixture",
                "short_id": source_key,
                "metadata": metadata,
                "health_check": _health_check,
                "fetch": _fetch,
            },
        )

    config = ConnectionConfig(url="https://fixture.invalid/events")
    for source_key in source_events:
        registry.register(
            _fixture_class(source_key),
            config=config,
        )

    class _DirectFixtureRegistry:
        """Use fixture connectors directly while exercising ingestion/orchestration consumers."""

        def get(self, connector_id: str) -> Any:
            return registry.get(connector_id)

        async def get_connection(
            self,
            connector_id: str,
            connection_config: ConnectionConfig,
        ) -> Any:
            return await self.get(connector_id).connect(connection_config)

        async def release_connection(self, connector_id: str, handle: Any) -> None:
            await self.get(connector_id).disconnect(handle)

    cas_root = tmp_path / "b80-cas"
    store = FileSystemCAS(cas_root)
    cursor_store = CursorStore(store)
    predecessors: dict[str, CursorState] = {}
    for source_key, version in (("source_a", "etag-a8"), ("source_b", "etag-b4")):
        connector_id = f"fixture.{source_key}"
        predecessor = CursorState(
            cursor_id=f"{connector_id}:events",
            connector_id=connector_id,
            dataset_id="events",
            watermark_type=WatermarkType.ETAG,
            watermark_value=version,
            created_at=version_time,
        )
        cursor_store.save_cursor(predecessor)
        predecessors[source_key] = predecessor

    manifest = {
        "datasets": [
            {"connector_id": "fixture.source_a", "dataset_id": "events"},
            {"connector_id": "fixture.source_b", "dataset_id": "events"},
        ]
    }
    fixture_registry = _DirectFixtureRegistry()
    dependencies = resolve_ingestion_dependencies(registry=fixture_registry)  # type: ignore[arg-type]
    try:
        with pytest.raises(FetchError, match="temporarily unavailable"):
            run_batch_incremental(
                connector_manifest=manifest,
                source="e02-b80-fixture",
                license_name="fixture-only",
                cas_root=cas_root,
                connection_config=config,
                produce_snapshot=False,
                ingestion_dependencies=dependencies,
            )

        after_failure = CursorStore(FileSystemCAS(cas_root))
        for _source_key, predecessor in predecessors.items():
            actual = after_failure.find_latest_cursor(
                predecessor.connector_id,
                predecessor.dataset_id,
            )
            assert actual is not None
            assert actual.model_dump(mode="json") == predecessor.model_dump(mode="json")

        result = run_batch_incremental(
            connector_manifest=manifest,
            source="e02-b80-fixture",
            license_name="fixture-only",
            cas_root=cas_root,
            connection_config=config,
            produce_snapshot=False,
            ingestion_dependencies=dependencies,
        )
        assert result.evidence_bundle_ref is not None
        assert observed_requests == [
            ("source_a", "etag-a8"),
            ("source_b", "etag-b4"),
            ("source_a", "etag-a8"),
            ("source_b", "etag-b4"),
        ]

        evidence = EvidenceBundle.model_validate(
            from_canonical_bytes(store.get_bytes(result.evidence_bundle_ref.artifact_id))
        )
        from polisyos.fabric.connectors.cache._store_serialization import ResultSerializer

        observed_row_ids: set[str] = set()
        for source_ref in evidence.sources:
            fetched = ResultSerializer.deserialize(store.get_bytes(source_ref))
            observed_row_ids.update(str(row["id"]) for row in fetched.data)
        expected_row_ids = {
            row["id"]
            for source_events in source_events.values()
            for _version, row in source_events[1:]
            if row is not None
        }
        assert observed_row_ids == expected_row_ids
        assert "b-late-event-5" in observed_row_ids

        # Cursor writes remain fail-closed until the independent evidence binder exists.
        after_retry = CursorStore(FileSystemCAS(cas_root))
        for _source_key, predecessor in predecessors.items():
            actual = after_retry.find_latest_cursor(
                predecessor.connector_id,
                predecessor.dataset_id,
            )
            assert actual is not None
            assert actual.model_dump(mode="json") == predecessor.model_dump(mode="json")
    finally:
        registry.shutdown()
        ConnectorRegistry.reset_instance()


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
    import polisyos.fabric.connectors.sources.event_stream as event_stream
    import polisyos.fabric.data_plane.streaming as streaming

    rows, policy, expected = _window_case(strategy)
    dataset_id = f"{strategy}-{crash_boundary}"
    stream_path = tmp_path / f"{strategy}-{crash_boundary}.jsonl"
    source_bytes = b"".join(
        b" \t" + json.dumps(row, allow_nan=True, sort_keys=True).encode("utf-8") + b" \t\r\n"
        for row in rows
    )
    source_rows, source_spans, source_digest = _jsonl_raw_byte_oracle(
        source_bytes,
        dataset_id=dataset_id,
    )
    assert source_rows == rows
    stream_path.write_bytes(source_bytes)
    registry = _configure_stream_registry(stream_registry, stream_path)
    cas_root = tmp_path / f"cas-{strategy}-{crash_boundary}"
    store = FileSystemCAS(cas_root)
    cursor_store = CursorStore(store)
    crashed_artifacts: list[str] = []
    consumed_source_bytes: list[bytes] = []
    original_source_read = event_stream.read_location_bytes
    original = (
        streaming._persist_stream_chunk_async
        if crash_boundary == "after_raw_chunk"
        else streaming._persist_stream_window_async
    )

    async def _capture_source_bytes(*args: Any, **kwargs: Any):
        payload, headers = await original_source_read(*args, **kwargs)
        consumed_source_bytes.append(bytes(payload))
        return payload, headers

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
    monkeypatch.setattr(event_stream, "read_location_bytes", _capture_source_bytes)
    with pytest.raises(_ProcessDeath):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
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
        dataset_id=dataset_id,
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
    assert len(source_spans) == len(source_rows)
    assert all(
        hashlib.sha256(consumed).hexdigest() == source_digest for consumed in consumed_source_bytes
    )
    assert consumed_source_bytes

    persisted_chunks: list[dict[str, Any]] = []
    for artifact_id in persisted_crash.iter_artifact_ids():
        manifest = persisted_crash.get_manifest(artifact_id)
        if manifest.kind != "fabric.stream_chunk":
            continue
        payload = from_canonical_bytes(persisted_crash.get_bytes(str(artifact_id)))
        if payload.get("dataset_id") == dataset_id:
            persisted_chunks.append(payload)
    persisted_chunks.sort(key=lambda item: int(item["chunk_index"]))
    assert [int(item["chunk_index"]) for item in persisted_chunks] == list(range(len(source_rows)))
    assert [row for item in persisted_chunks for row in item["data"]] == source_rows
    for chunk_index, (byte_start, byte_end, line_digest) in enumerate(source_spans):
        raw_line = source_bytes[byte_start:byte_end]
        assert hashlib.sha256(raw_line).hexdigest() == line_digest
        assert persisted_chunks[chunk_index]["data"] == [json.loads(raw_line.strip())]
    assert persisted_frontier.offset == len(source_rows) - 1
    assert result.final_cursor is not None
    assert result.final_cursor.watermark_value == str(len(source_rows) - 1)


@pytest.mark.asyncio
async def test_b81_raw_byte_oracle_detects_marker_preserving_chunk_content_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stream_registry: ConnectorRegistry,
) -> None:
    """The content oracle rejects changed CAS rows even when artifact markers survive."""
    import polisyos.fabric.data_plane.streaming as streaming

    dataset_id = "raw-byte-removal-control"
    source_bytes = b' { "event_id" : "source-event", "value" : 19 } \r\n'
    expected_rows, source_spans, source_digest = _jsonl_raw_byte_oracle(
        source_bytes,
        dataset_id=dataset_id,
    )
    assert source_spans and source_digest
    stream_path = tmp_path / f"{dataset_id}.jsonl"
    stream_path.write_bytes(source_bytes)
    registry = _configure_stream_registry(stream_registry, stream_path)
    cas_root = tmp_path / f"{dataset_id}-cas"
    store = FileSystemCAS(cas_root)
    original = streaming._persist_stream_chunk_async

    async def _persist_drifted_content(**kwargs: Any):
        changed_rows = [dict(row, value=999) for row in kwargs["rows"]]
        return await original(**{**kwargs, "rows": changed_rows})

    monkeypatch.setattr(streaming, "_persist_stream_chunk_async", _persist_drifted_content)
    result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id=dataset_id,
        store=store,
        cursor_store=CursorStore(store),
        sanitize_rows=_valid_rows,
        runtime_options=StreamRuntimeOptions(
            checkpoint_every_chunks=1,
            window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=1),
        ),
        registry=registry,
    )

    assert len(result.chunk_refs) == 1
    chunk_ref = result.chunk_refs[0]
    assert store.get_manifest(chunk_ref.artifact_id).kind == "fabric.stream_chunk"
    payload = from_canonical_bytes(store.get_bytes(chunk_ref.artifact_id))
    assert payload["dataset_id"] == dataset_id
    assert payload["chunk_index"] == 0
    assert payload["row_count"] == len(expected_rows)
    assert payload["processing"]
    assert payload["data"][0]["event_id"] == expected_rows[0]["event_id"]
    assert payload["data"][0]["value"] == 999
    with pytest.raises(
        AssertionError,
        match="persisted stream rows differ from the raw-byte oracle",
    ):
        assert payload["data"] == expected_rows, (
            "persisted stream rows differ from the raw-byte oracle"
        )


@pytest.mark.parametrize(
    "mismatch",
    ["source_schema", "window_policy", "idempotency_fields", "dedupe_window"],
)
@pytest.mark.asyncio
async def test_b82_resume_refuses_source_schema_window_or_idempotency_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stream_registry: ConnectorRegistry,
    mismatch: str,
) -> None:
    """A committed partial window cannot resume under a different bound contract."""
    import polisyos.fabric.data_plane.streaming as streaming
    from polisyos.fabric.data_plane.cursor_store import CursorStoreError

    dataset_id = f"contract-mismatch-{mismatch}"
    rows = [
        {
            "event_id": f"event-{index}",
            "source_version": index,
            "entity_id": f"entity-{index}",
            "value": index + 1,
        }
        for index in range(3)
    ]
    stream_path = tmp_path / f"{dataset_id}.jsonl"
    stream_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    registry = _configure_stream_registry(stream_registry, stream_path)

    def _register_schema(contract_suffix: str, *, include_note: bool) -> StreamSchemaBinding:
        fields = [
            FieldSpec(name="event_id", data_type=SchemaType.STRING, nullable=False),
            FieldSpec(name="source_version", data_type=SchemaType.INT64, nullable=False),
            FieldSpec(name="entity_id", data_type=SchemaType.STRING, nullable=False),
            FieldSpec(name="value", data_type=SchemaType.FLOAT64, nullable=False),
        ]
        if include_note:
            fields.append(
                FieldSpec(
                    name="note",
                    data_type=SchemaType.STRING,
                    presence="optional",
                    nullable=True,
                )
            )
        schema = DataSchema(
            schema_id=f"test.e02.contract_mismatch.{contract_suffix}",
            version=SchemaVersion(1, 0, 0),
            fields=tuple(fields),
            primary_key=("event_id", "source_version"),
            required_completeness=0.0,
        )
        contract = ConnectorSchemaContract(
            contract_id=f"test.e02.contract_mismatch.{contract_suffix}.contract",
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            schema=schema,
            created_by="test_e02_c_streaming_oracle",
        )
        next_registry = ContractRegistry()
        next_registry.register(contract)
        registry.configure_contracts(next_registry)
        return StreamSchemaBinding.from_contract(
            contract,
            registry_revision=next_registry.revision,
        )

    original_binding = _register_schema("source_v1", include_note=False)
    original_options = StreamRuntimeOptions(
        batch_size=1,
        checkpoint_every_chunks=1,
        dedupe_key_fields=("event_id", "source_version"),
        max_dedupe_keys=16,
        max_buffered_rows=8,
        max_buffered_bytes=100_000,
        window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=16),
    )
    cas_root = tmp_path / f"{dataset_id}-cas"
    store = FileSystemCAS(cas_root)
    cursor_store = CursorStore(store)
    original_poll = StreamingSourceSession.poll
    poll_state = {"calls": 0}

    async def _crash_before_third_poll(session: StreamingSourceSession):
        if poll_state["calls"] == 2:
            raise _ProcessDeath("leave two rows under the old contract")
        poll_state["calls"] += 1
        return await original_poll(session)

    monkeypatch.setattr(StreamingSourceSession, "poll", _crash_before_third_poll)
    with pytest.raises(_ProcessDeath):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=_valid_rows,
            runtime_options=original_options,
            registry=registry,
            schema_binding=original_binding,
        )

    monkeypatch.setattr(StreamingSourceSession, "poll", original_poll)
    before_store = FileSystemCAS(cas_root)
    before_cursor_store = CursorStore(before_store)
    before_checkpoint = before_cursor_store.find_latest_stream_checkpoint(
        "stream.jsonl",
        dataset_id,
    )
    before_cursor = before_cursor_store.find_latest_cursor("stream.jsonl", dataset_id)
    assert before_checkpoint is not None
    assert before_checkpoint.offset == 1
    assert before_cursor is not None
    assert len(before_checkpoint.metadata["operator_state"]["accumulator"]["count_buffer"]) == 2
    before_artifacts = set(map(str, before_store.iter_artifact_ids()))

    changed_binding = original_binding
    changed_options = original_options
    expected_error: type[Exception]
    expected_message: str
    if mismatch == "source_schema":
        changed_binding = _register_schema("source_v2", include_note=True)
        expected_error = CursorStoreError
        expected_message = "stream schema binding changed before resume"
    elif mismatch == "window_policy":
        changed_options = StreamRuntimeOptions(
            **{
                **original_options.__dict__,
                "window_policy": WindowPolicy(strategy=WindowStrategy.COUNT, size=8),
            }
        )
        expected_error = CursorStoreError
        expected_message = "corrupt stream operator state"
    elif mismatch == "idempotency_fields":
        changed_options = StreamRuntimeOptions(
            **{
                **original_options.__dict__,
                "dedupe_key_fields": ("event_id", "entity_id"),
            }
        )
        expected_error = getattr(streaming, "StreamDedupeUnsupported", RuntimeError)
        expected_message = "dedupe UTC horizon/scope contract is unavailable"
    else:
        changed_idempotency = original_options.processing_contract.idempotency.model_copy(
            update={"dedupe_window_seconds": 3_600}
        )
        changed_contract = original_options.processing_contract.model_copy(
            update={"idempotency": changed_idempotency}
        )
        changed_options = StreamRuntimeOptions(
            **{
                **original_options.__dict__,
                "processing_contract": changed_contract,
            }
        )
        expected_error = getattr(streaming, "StreamDedupeUnsupported", RuntimeError)
        expected_message = "dedupe UTC horizon/scope contract is unavailable"

    source_progress = {"rewinds": 0, "polls": 0}

    async def _observe_rewind(session: StreamingSourceSession, checkpoint: Any) -> None:
        source_progress["rewinds"] += 1
        await original_rewind(session, checkpoint)

    async def _observe_poll(session: StreamingSourceSession):
        source_progress["polls"] += 1
        return await original_poll(session)

    original_rewind = StreamingSourceSession.rewind
    monkeypatch.setattr(StreamingSourceSession, "rewind", _observe_rewind)
    monkeypatch.setattr(StreamingSourceSession, "poll", _observe_poll)
    with pytest.raises(expected_error, match=expected_message):
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            store=FileSystemCAS(cas_root),
            cursor_store=CursorStore(FileSystemCAS(cas_root)),
            sanitize_rows=_valid_rows,
            runtime_options=changed_options,
            registry=registry,
            schema_binding=changed_binding,
        )

    assert source_progress == {"rewinds": 0, "polls": 0}
    after_store = FileSystemCAS(cas_root)
    after_cursor_store = CursorStore(after_store)
    after_checkpoint = after_cursor_store.find_latest_stream_checkpoint(
        "stream.jsonl",
        dataset_id,
    )
    after_cursor = after_cursor_store.find_latest_cursor("stream.jsonl", dataset_id)
    assert after_checkpoint is not None
    assert after_checkpoint.model_dump(mode="json") == before_checkpoint.model_dump(mode="json")
    assert after_cursor is not None
    assert after_cursor.model_dump(mode="json") == before_cursor.model_dump(mode="json")
    assert set(map(str, after_store.iter_artifact_ids())) == before_artifacts


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
            runtime_options=StreamRuntimeOptions(
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
            runtime_options=StreamRuntimeOptions(
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
        runtime_options=StreamRuntimeOptions(
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
        runtime_options=StreamRuntimeOptions(
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
            runtime_options=StreamRuntimeOptions(
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


@pytest.mark.asyncio
async def test_b84_output_reference_cap_refuses_before_cas_and_detects_gate_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stream_registry: ConnectorRegistry,
) -> None:
    """Output-reference bounds cover actual CAS writes and returned references."""
    import polisyos.fabric.data_plane.streaming as streaming

    dataset_id = "output-reference-cap"
    stream_path = tmp_path / f"{dataset_id}.jsonl"
    stream_path.write_text('{"event_id":"out-row","value":1}\n', encoding="utf-8")
    registry = _configure_stream_registry(stream_registry, stream_path)
    options = StreamRuntimeOptions(
        checkpoint_every_chunks=1,
        max_output_refs=1,
        window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=1),
    )

    refused_root = tmp_path / "output-cap-refused-cas"
    refused_store = FileSystemCAS(refused_root)
    with pytest.raises(streaming.StreamCapacityError) as refused:
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            store=refused_store,
            cursor_store=CursorStore(refused_store),
            sanitize_rows=_valid_rows,
            runtime_options=options,
            registry=registry,
        )
    assert (refused.value.stage, refused.value.rows, refused.value.max_rows) == (
        "output",
        2,
        1,
    )
    assert list(FileSystemCAS(refused_root).iter_artifact_ids()) == []

    exact_options = StreamRuntimeOptions(**{**options.__dict__, "max_output_refs": 2})
    exact_root = tmp_path / "output-cap-exact-cas"
    exact_store = FileSystemCAS(exact_root)
    exact_result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id=dataset_id,
        store=exact_store,
        cursor_store=CursorStore(exact_store),
        sanitize_rows=_valid_rows,
        runtime_options=exact_options,
        registry=registry,
    )
    exact_ref_ids = {
        str(ref.artifact_id)
        for ref in (
            *exact_result.chunk_refs,
            *exact_result.window_refs,
            *exact_result.cdc_event_refs,
        )
    }
    assert len(exact_result.chunk_refs) == 1
    assert len(exact_result.window_refs) == 1
    assert exact_result.cdc_event_refs == []
    assert exact_ref_ids == {
        str(exact_result.chunk_refs[0].artifact_id),
        str(exact_result.window_refs[0].artifact_id),
    }
    chunk = from_canonical_bytes(exact_store.get_bytes(exact_result.chunk_refs[0].artifact_id))
    window = from_canonical_bytes(exact_store.get_bytes(exact_result.window_refs[0].artifact_id))
    assert chunk["data"] == window["data"]
    assert window["lineage"]["contributor_chunk_refs"] == [
        str(exact_result.chunk_refs[0].artifact_id)
    ]
    output_artifacts = {
        str(artifact_id)
        for artifact_id in exact_store.iter_artifact_ids()
        if exact_store.get_manifest(artifact_id).kind
        in {"fabric.stream_chunk", "fabric.stream_window", "fabric.cdc_schema_change"}
    }
    assert output_artifacts == exact_ref_ids

    original_admission = streaming._admit_output_ref
    monkeypatch.setattr(streaming, "_admit_output_ref", lambda *_args, **_kwargs: None)
    removed_root = tmp_path / "output-cap-removed-cas"
    removed_store = FileSystemCAS(removed_root)
    removed_result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id=dataset_id,
        store=removed_store,
        cursor_store=CursorStore(removed_store),
        sanitize_rows=_valid_rows,
        runtime_options=options,
        registry=registry,
    )
    removed_ref_count = (
        len(removed_result.chunk_refs)
        + len(removed_result.window_refs)
        + len(removed_result.cdc_event_refs)
    )
    removed_output_artifacts = {
        str(artifact_id)
        for artifact_id in removed_store.iter_artifact_ids()
        if removed_store.get_manifest(artifact_id).kind
        in {"fabric.stream_chunk", "fabric.stream_window", "fabric.cdc_schema_change"}
    }
    assert removed_ref_count == 2
    assert removed_ref_count > options.max_output_refs
    assert removed_output_artifacts == {
        str(ref.artifact_id)
        for ref in (
            *removed_result.chunk_refs,
            *removed_result.window_refs,
            *removed_result.cdc_event_refs,
        )
    }
    monkeypatch.setattr(streaming, "_admit_output_ref", original_admission)

    with pytest.raises(AssertionError, match="retained stream output refs exceed declared cap"):
        assert removed_ref_count <= options.max_output_refs, (
            "retained stream output refs exceed declared cap"
        )


@pytest.mark.asyncio
async def test_b86_schema_membership_and_quarantine_do_not_depend_on_batch_size(
    tmp_path: Path,
    stream_registry: ConnectorRegistry,
) -> None:
    """Membership, semantic data, and keyed quarantine reasons survive batch changes."""
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
    accepted_expected = [
        {"event_id": "valid-absent-note", "value": 1},
        {"event_id": "valid-note", "value": 2, "note": "present"},
        {"event_id": "valid-null-note", "value": 3, "note": None},
    ]
    expected_reasons = {
        "missing-event-id": "poison_stream_message",
        "missing-value": "poison_stream_message",
        "non-finite": "non_finite_metric",
        "wrong-type": "poison_stream_message",
    }
    expected_digest = hashlib.sha256(
        json.dumps(accepted_expected, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    reference_summary: tuple[str, tuple[tuple[str, str], ...]] | None = None
    for batch_size in (1, 2, 8):
        dataset_id = f"schema-{batch_size}"
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
            dataset_id=dataset_id,
            schema=schema,
            created_by="test_e02_c_streaming_oracle",
        )
        contracts.register(contract)
        registry.configure_contracts(contracts)
        binding = StreamSchemaBinding.from_contract(
            contract,
            registry_revision=contracts.revision,
        )
        cas_root = tmp_path / f"schema-cas-{batch_size}"
        store = FileSystemCAS(cas_root)
        result = await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
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

        accepted_rows = [
            row
            for ref in result.chunk_refs
            for row in from_canonical_bytes(store.get_bytes(ref.artifact_id))["data"]
        ]
        accepted_semantics = [
            {key: value for key, value in row.items() if key != "_message_id"}
            for row in accepted_rows
        ]
        accepted_digest = hashlib.sha256(
            json.dumps(
                accepted_semantics,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        assert accepted_semantics == accepted_expected
        assert accepted_digest == expected_digest

        records = list_quarantine_records(
            store,
            source=f"connector.stream:stream.jsonl:{dataset_id}",
        )
        keyed_reasons: dict[str, str] = {}
        for _record_id, record in records:
            raw_row = load_quarantine_payload(store, record.raw_payload_ref)
            assert isinstance(raw_row, dict)
            key = (
                str(raw_row["event_id"])
                if raw_row.get("event_id") is not None
                else "missing-event-id"
            )
            assert key not in keyed_reasons
            keyed_reasons[key] = record.reason
        assert keyed_reasons == expected_reasons
        assert result.quarantined_rows == 4

        summary = (accepted_digest, tuple(sorted(keyed_reasons.items())))
        if reference_summary is None:
            reference_summary = summary
        else:
            assert summary == reference_summary


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
    monkeypatch: pytest.MonkeyPatch,
    stream_registry: ConnectorRegistry,
) -> None:
    """A duplicate near expiry does not refresh the first-accepted timestamp."""
    import polisyos.fabric.data_plane.streaming as streaming_module

    first_accepted = datetime(2026, 1, 1, tzinfo=UTC)
    initial_times = [first_accepted, first_accepted + timedelta(seconds=10)]
    clock = {"now": first_accepted}

    def ingestion_time() -> datetime:
        if initial_times:
            return initial_times.pop(0)
        return clock["now"]

    monkeypatch.setattr(streaming_module, "_ingestion_utc", ingestion_time, raising=False)
    duplicate_v1 = {
        "event_id": "entity-event",
        "source_version": 1,
        "entity_id": "same-entity",
        "value": "version-1",
    }
    rows = [
        duplicate_v1,
        {
            "event_id": "entity-event",
            "source_version": 2,
            "entity_id": "same-entity",
            "value": "version-2",
        },
        {**duplicate_v1, "value": "redelivery-before-expiry"},
    ]
    dataset_id = "dedupe-expiry-restart"
    stream_path = tmp_path / "dedupe-expiry-restart.jsonl"
    stream_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    registry = _configure_stream_registry(stream_registry, stream_path)
    cas_root = tmp_path / "dedupe-expiry-cas"
    store = FileSystemCAS(cas_root)
    original_poll = StreamingSourceSession.poll
    poll_state = {"count": 0}

    async def crash_before_third_source_chunk(session: StreamingSourceSession):
        if poll_state["count"] == 2:
            raise _ProcessDeath("leave both versions in the persisted horizon")
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
        )

    monkeypatch.setattr(StreamingSourceSession, "poll", original_poll)
    before = CursorStore(FileSystemCAS(cas_root))
    prior_checkpoint = before.find_latest_stream_checkpoint("stream.jsonl", dataset_id)
    assert prior_checkpoint is not None
    key_v1 = (("event_id", "entity-event"), ("source_version", 1))
    key_v2 = (("event_id", "entity-event"), ("source_version", 2))
    assert _dedupe_horizon_entries(prior_checkpoint) == {
        key_v1: first_accepted,
        key_v2: first_accepted + timedelta(seconds=10),
    }

    clock["now"] = first_accepted + timedelta(seconds=86_399)
    resumed_store = FileSystemCAS(cas_root)
    before_expiry = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id=dataset_id,
        store=resumed_store,
        cursor_store=CursorStore(resumed_store),
        sanitize_rows=_valid_rows,
        runtime_options=_dedupe_options(max_dedupe_keys=2),
        registry=registry,
    )
    assert before_expiry.dedupe_dropped == 1
    before_expiry_checkpoint = CursorStore(resumed_store).find_latest_stream_checkpoint(
        "stream.jsonl",
        dataset_id,
    )
    assert before_expiry_checkpoint is not None
    assert _dedupe_horizon_entries(before_expiry_checkpoint) == {
        key_v1: first_accepted,
        key_v2: first_accepted + timedelta(seconds=10),
    }

    rows.append({**duplicate_v1, "value": "redelivery-at-expiry"})
    stream_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    clock["now"] = first_accepted + timedelta(seconds=86_400)
    expiry_store = FileSystemCAS(cas_root)
    at_expiry = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id=dataset_id,
        store=expiry_store,
        cursor_store=CursorStore(expiry_store),
        sanitize_rows=_valid_rows,
        runtime_options=_dedupe_options(max_dedupe_keys=2),
        registry=registry,
    )
    assert at_expiry.dedupe_dropped == 0
    final_checkpoint = CursorStore(expiry_store).find_latest_stream_checkpoint(
        "stream.jsonl",
        dataset_id,
    )
    assert final_checkpoint is not None
    assert _dedupe_horizon_entries(final_checkpoint) == {
        key_v1: first_accepted + timedelta(seconds=86_400),
        key_v2: first_accepted + timedelta(seconds=10),
    }
    emitted = _persisted_stream_rows(expiry_store, dataset_id=dataset_id)
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
    cas_root = tmp_path / f"dedupe-invalid-cas-{case_id}"
    store = FileSystemCAS(cas_root)
    before_ids = set(map(str, store.iter_artifact_ids()))
    unsupported_type = getattr(streaming_module, "StreamDedupeUnsupported", RuntimeError)

    with pytest.raises(unsupported_type, match="event/version|event-key|dedupe") as exc_info:
        await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            store=store,
            cursor_store=CursorStore(store),
            sanitize_rows=_valid_rows,
            runtime_options=_dedupe_options(max_dedupe_keys=2),
            registry=registry,
        )

    assert type(exc_info.value).__name__ == "StreamDedupeUnsupported"
    after = CursorStore(FileSystemCAS(cas_root))
    assert after.find_latest_stream_checkpoint("stream.jsonl", dataset_id) is None
    assert after.find_latest_cursor("stream.jsonl", dataset_id) is None
    assert set(map(str, FileSystemCAS(cas_root).iter_artifact_ids())) == before_ids


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
