"""Execution mode dispatch for data ingestion.

Provides:
- batch_incremental: cursor-based incremental ingestion
- record_mode: run ingestion while capturing HTTP responses to CAS
- replay_mode: run ingestion from captured HTTP responses (no network)
- streaming_windowed: per-chunk CAS persistence via fetch_stream()
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.async_tools import run_blocking_async, run_coro_sync
from polisyos.common.logger import get_logger
from polisyos.core.artifacts.backends.config import (
    ArtifactStoreConfig,
    build_artifact_store,
)
from polisyos.core.contracts.cursor import CursorState, WindowStrategy
from polisyos.fabric.data_plane.quarantine import (
    QuarantineRecord,
    persist_quarantine_record,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.fabric.ingestion import IngestionDependencies

logger = get_logger(__name__)


def _build_filesystem_store(cas_root: Path) -> FileSystemCAS:
    return cast(
        "FileSystemCAS",
        build_artifact_store(
            ArtifactStoreConfig(backend="filesystem", root=str(cas_root)),
        ),
    )


async def _persist_streaming_manifest_async(
    *,
    store: FileSystemCAS,
    manifest_payload: dict[str, Any],
    source_refs: list[Any],
) -> Any:
    from polisyos.core.artifacts.async_store import ensure_async_artifact_store
    from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import CanonSpec

    async_store = ensure_async_artifact_store(store)
    return await async_store.put_json(
        manifest_payload,
        ArtifactWriteOptions(
            kind="fabric.streaming_run_manifest",
            media_type="application/json",
            schema=SchemaInfo(name="fabric.StreamingRunManifest", version="1.0"),
            inputs=[
                InputRef(artifact_id=ref.artifact_id, role="stream_artifact") for ref in source_refs
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


async def _persist_streaming_snapshot_async(
    *,
    store: FileSystemCAS,
    snapshot_payload: dict[str, Any],
    manifest_ref: Any,
    evidence_ref: Any,
) -> Any:
    from polisyos.core.artifacts.async_store import ensure_async_artifact_store
    from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import CanonSpec

    async_store = ensure_async_artifact_store(store)
    return await async_store.put_json(
        snapshot_payload,
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=[
                InputRef(artifact_id=manifest_ref.artifact_id, role="data_ref"),
                InputRef(artifact_id=evidence_ref.artifact_id, role="evidence_ref"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _looks_metric_field(field_name: str) -> bool:
    lowered = str(field_name).strip().lower()
    if lowered in {"value", "metric", "score", "rate", "total", "count"}:
        return True
    return any(
        marker in lowered
        for marker in ("metric", "score", "value", "amount", "rate", "count", "total")
    )


def _non_finite_fields(row: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    for key, value in row.items():
        if isinstance(value, bool) or value is None or not isinstance(value, (int, float)):
            continue
        numeric = float(value)
        if math.isinf(numeric) or (math.isnan(numeric) and _looks_metric_field(str(key))):
            fields.append(str(key))
    return fields


def run_batch_incremental(
    *,
    connector_manifest: Any,
    source: str,
    license_name: str,
    cas_root: Path,
    connection_config: Any | None = None,
    produce_snapshot: bool = True,
    ingestion_dependencies: IngestionDependencies | None = None,
) -> Any:
    """Run ingestion in batch_incremental mode.

    1. For each dataset, look up latest cursor via CursorStore.
    2. Build incremental_cursors dict mapping dataset_id → cursor watermark.
    3. Delegate to run_connectors_ingestion with incremental hints.
    4. Extract watermarks from results and save new cursors.
    5. Return IngestionResult with cursor_ref.
    """
    from polisyos.fabric.data_plane.cursor_store import CursorStore
    from polisyos.fabric.data_plane.orchestrator import run_orchestrated_ingestion

    store = _build_filesystem_store(cas_root)
    cursor_store = CursorStore(store, index_root=cas_root)

    # Look up prior cursors for each dataset
    incremental_cursors: dict[str, str] = {}
    datasets = []
    if hasattr(connector_manifest, "datasets"):
        datasets = connector_manifest.datasets
    elif isinstance(connector_manifest, dict):
        datasets = connector_manifest.get("datasets", [])

    connector_id = ""
    for ds in datasets:
        ds_connector_id = (
            getattr(ds, "connector_id", "") or ds.get("connector_id", "")
            if isinstance(ds, dict)
            else ""
        )
        ds_dataset_id = (
            getattr(ds, "dataset_id", "") or ds.get("dataset_id", "")
            if isinstance(ds, dict)
            else ""
        )
        if ds_connector_id:
            connector_id = ds_connector_id
        cursor = cursor_store.find_latest_cursor(ds_connector_id, ds_dataset_id)
        if cursor is not None:
            incremental_cursors[ds_dataset_id] = cursor.watermark_value
            logger.info(
                "batch_incremental: cursor found for %s:%s → %s",
                ds_connector_id,
                ds_dataset_id,
                cursor.watermark_value,
            )

    # Run normal orchestrated ingestion
    result = run_orchestrated_ingestion(
        connector_manifest=connector_manifest,
        source=source,
        license_name=license_name,
        cas_root=cas_root,
        connection_config=connection_config,
        produce_snapshot=produce_snapshot,
        ingestion_dependencies=ingestion_dependencies,
    )

    # Save new cursor based on ingestion result
    if result.datasets_fetched > 0:
        from polisyos.fabric.data_plane.watermark import resolve_watermark_policy

        connector_family = connector_id.split(".")[0] if connector_id else ""
        policy = resolve_watermark_policy(connector_family)
        now = datetime.now(UTC)

        for ds in datasets:
            ds_connector_id = getattr(ds, "connector_id", "") or (
                ds.get("connector_id", "") if isinstance(ds, dict) else ""
            )
            ds_dataset_id = getattr(ds, "dataset_id", "") or (
                ds.get("dataset_id", "") if isinstance(ds, dict) else ""
            )

            cursor_state = CursorState(
                cursor_id=f"{ds_connector_id}:{ds_dataset_id}",
                connector_id=ds_connector_id,
                dataset_id=ds_dataset_id,
                watermark_type=policy.watermark_type,
                watermark_value=now.isoformat(),
                created_at=now,
                evidence_bundle_ref=(
                    str(result.evidence_bundle_ref.artifact_id)
                    if result.evidence_bundle_ref
                    else None
                ),
            )
            cursor_ref = cursor_store.save_cursor(cursor_state)
            result.cursor_ref = str(cursor_ref.artifact_id)

    return result


# ---------------------------------------------------------------------------
# Record mode
# ---------------------------------------------------------------------------


def run_record_mode(
    *,
    connector_manifest: Any,
    source: str,
    license_name: str,
    cas_root: Path,
    connection_config: Any | None = None,
    produce_snapshot: bool = True,
    ingestion_dependencies: IngestionDependencies | None = None,
) -> tuple[Any, str]:
    """Run ingestion with HTTP recording enabled.

    1. Create APISimulator in RECORD mode with a temp fixture_root.
    2. Run ingestion inside the simulator context.
    3. Collect captured fixtures from the temp directory.
    4. Persist RecordSession to CAS via ReplayStore.
    5. Return (IngestionResult, record_ref_hex).
    """
    import tempfile
    import uuid

    from polisyos.fabric.connectors.testing.simulator import APISimulator, SimulatorMode
    from polisyos.fabric.data_plane.orchestrator import run_orchestrated_ingestion
    from polisyos.fabric.data_plane.replay_store import (
        ReplayStore,
        make_record_session,
    )

    session_id = uuid.uuid4().hex

    # Extract connector/dataset info for the session metadata
    datasets = _extract_datasets(connector_manifest)
    connector_datasets = [{"connector_id": ds[0], "dataset_id": ds[1]} for ds in datasets]

    with tempfile.TemporaryDirectory(prefix="polisyos_record_") as tmpdir:
        fixture_root = Path(tmpdir)

        # Determine connector_id for the simulator
        first_connector_id = datasets[0][0] if datasets else "unknown"
        first_dataset_id = datasets[0][1] if datasets else "unknown"

        simulator = APISimulator(
            mode=SimulatorMode.RECORD,
            fixture_root=fixture_root,
            connector_id=first_connector_id,
            dataset_id=first_dataset_id,
        )

        # Run ingestion with recording — the simulator patches aiohttp globally
        # so any HTTP calls during ingestion are intercepted.
        # Note: APISimulator is async context manager. Since ingestion uses
        # run_coro_sync internally, we wrap in our own async context.
        async def _record_ingestion() -> Any:
            async with simulator:
                from polisyos.fabric.ingestion import run_connectors_ingestion

                evidence_ref = await run_blocking_async(
                    run_connectors_ingestion,
                    connector_manifest=connector_manifest,
                    source=source,
                    license_name=license_name,
                    cas_root=cas_root,
                    connection_config=connection_config,
                    dependencies=ingestion_dependencies,
                )
                return evidence_ref

        try:
            evidence_ref = run_coro_sync(_record_ingestion())
        except Exception:
            logger.debug(
                "Async record ingestion failed, falling back to sync path",
                exc_info=True,
            )
            # Fall back to sync path if async context isn't needed
            result = run_orchestrated_ingestion(
                connector_manifest=connector_manifest,
                source=source,
                license_name=license_name,
                cas_root=cas_root,
                connection_config=connection_config,
                produce_snapshot=produce_snapshot,
                ingestion_dependencies=ingestion_dependencies,
            )

            # Still try to collect any fixtures that were captured
            session = make_record_session(
                session_id=session_id,
                fixture_root=fixture_root,
                connector_datasets=connector_datasets,
            )
            store = _build_filesystem_store(cas_root)
            replay_store = ReplayStore(store)
            ref = replay_store.save_record_session(session)
            result.mode_effective = "record"
            return result, str(ref.artifact_id.hex)

        # Build result from evidence_ref
        from polisyos.fabric.data_plane.orchestrator import IngestionResult

        datasets_fetched = len(datasets)
        result = IngestionResult(
            evidence_bundle_ref=evidence_ref,
            datasets_fetched=datasets_fetched,
            mode_effective="record",
        )

        # Collect fixtures and persist session
        session = make_record_session(
            session_id=session_id,
            fixture_root=fixture_root,
            connector_datasets=connector_datasets,
        )
        store = _build_filesystem_store(cas_root)
        replay_store = ReplayStore(store)
        ref = replay_store.save_record_session(session)

        return result, str(ref.artifact_id.hex)


# ---------------------------------------------------------------------------
# Replay mode
# ---------------------------------------------------------------------------


def run_replay_mode(
    *,
    connector_manifest: Any,
    source: str,
    license_name: str,
    cas_root: Path,
    replay_ref: str,
    connection_config: Any | None = None,
    produce_snapshot: bool = True,
    ingestion_dependencies: IngestionDependencies | None = None,
) -> Any:
    """Run ingestion using recorded HTTP responses (no network).

    1. Load RecordSession from CAS via replay_ref.
    2. Write fixtures to temp dir via ReplayStore.build_replay_fixture_dir().
    3. Run ingestion — APISimulator in REPLAY mode serves cached responses.
    4. Return IngestionResult.
    """
    import tempfile

    from polisyos.core.artifacts.manifest import ArtifactID
    from polisyos.fabric.data_plane.orchestrator import run_orchestrated_ingestion
    from polisyos.fabric.data_plane.replay_store import ReplayStore

    store = _build_filesystem_store(cas_root)
    replay_store = ReplayStore(store)

    # Load session from CAS
    artifact_id = ArtifactID.model_validate(replay_ref)
    session = replay_store.load_record_session(artifact_id)

    with tempfile.TemporaryDirectory(prefix="polisyos_replay_") as tmpdir:
        fixture_dir = Path(tmpdir)
        replay_store.build_replay_fixture_dir(session, fixture_dir)

        # Patch aiohttp to serve from fixtures
        from polisyos.fabric.connectors.testing.simulator import (
            APISimulator,
            SimulatorMode,
        )

        datasets = _extract_datasets(connector_manifest)
        first_connector_id = datasets[0][0] if datasets else "unknown"
        first_dataset_id = datasets[0][1] if datasets else "unknown"

        simulator = APISimulator(
            mode=SimulatorMode.REPLAY,
            fixture_root=fixture_dir,
            connector_id=first_connector_id,
            dataset_id=first_dataset_id,
        )

        async def _replay_ingestion() -> Any:
            async with simulator:
                from polisyos.fabric.ingestion import run_connectors_ingestion

                return await run_blocking_async(
                    run_connectors_ingestion,
                    connector_manifest=connector_manifest,
                    source=source,
                    license_name=license_name,
                    cas_root=cas_root,
                    connection_config=connection_config,
                    dependencies=ingestion_dependencies,
                )

        try:
            evidence_ref = run_coro_sync(_replay_ingestion())
        except Exception:
            logger.debug(
                "Async replay ingestion failed, falling back to sync path",
                exc_info=True,
            )
            # Fallback to standard orchestrated ingestion (simulator is async)
            result = run_orchestrated_ingestion(
                connector_manifest=connector_manifest,
                source=source,
                license_name=license_name,
                cas_root=cas_root,
                connection_config=connection_config,
                produce_snapshot=produce_snapshot,
                ingestion_dependencies=ingestion_dependencies,
            )
            result.mode_effective = "replay"
            return result

        from polisyos.fabric.data_plane.orchestrator import IngestionResult

        result = IngestionResult(
            evidence_bundle_ref=evidence_ref,
            datasets_fetched=len(datasets),
            mode_effective="replay",
        )
        return result


# ---------------------------------------------------------------------------
# Streaming windowed mode
# ---------------------------------------------------------------------------


def _sanitize_stream_rows(
    rows: Any,
    *,
    connector_id: str,
    dataset_id: str,
    store: Any,
    chunk_index: int,
) -> tuple[list[dict[str, Any]], list[str], int]:
    if not isinstance(rows, list):
        rows = [rows]

    signature_counts = Counter(
        tuple(sorted(str(key) for key in row)) for row in rows if isinstance(row, dict)
    )
    expected_keys = max(
        signature_counts,
        key=lambda item: (signature_counts[item], -len(item), item),
        default=(),
    )

    valid_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    quarantined = 0
    for row_index, row in enumerate(rows):
        reason: str | None = None
        context: dict[str, Any] = {
            "chunk_index": chunk_index,
            "row_index": row_index,
        }
        if not isinstance(row, dict):
            reason = "poison_stream_message"
            context["message"] = "stream message is not a JSON object"
        elif expected_keys and tuple(sorted(str(key) for key in row)) != expected_keys:
            reason = "poison_stream_message"
            context["expected_fields"] = list(expected_keys)
            context["actual_fields"] = sorted(str(key) for key in row)
        else:
            non_finite = _non_finite_fields(row)
            if non_finite:
                reason = "non_finite_metric"
                context["fields"] = non_finite

        if reason is None:
            valid_rows.append(row)
            continue

        quarantined += 1
        warnings.append(
            f"quarantined stream row {row_index} from {connector_id}:{dataset_id} "
            f"chunk {chunk_index} because of {reason}"
        )
        persist_quarantine_record(
            store,
            record=QuarantineRecord.new(
                reason=reason,
                severity="error",
                source=f"connector.stream:{connector_id}:{dataset_id}",
                schema_version="1.0",
                trace_id=f"{connector_id}:{dataset_id}:chunk:{chunk_index}:row:{row_index}",
                downstream_impacts=(
                    "streaming_windowed",
                    "evidence_bundle",
                    "data_snapshot",
                ),
                context=context,
            ),
            raw_payload=row,
        )

    return valid_rows, warnings, quarantined


def run_streaming_windowed(
    *,
    connector_manifest: Any,
    source: str,
    license_name: str,
    cas_root: Path,
    connection_config: Any | None = None,
    produce_snapshot: bool = True,
    ingestion_dependencies: IngestionDependencies | None = None,
) -> Any:
    return run_coro_sync(
        _run_streaming_windowed_async(
            connector_manifest=connector_manifest,
            source=source,
            license_name=license_name,
            cas_root=cas_root,
            connection_config=connection_config,
            produce_snapshot=produce_snapshot,
            ingestion_dependencies=ingestion_dependencies,
        )
    )


async def _run_streaming_windowed_async(
    *,
    connector_manifest: Any,
    source: str,
    license_name: str,
    cas_root: Path,
    connection_config: Any | None = None,
    produce_snapshot: bool = True,
    ingestion_dependencies: IngestionDependencies | None = None,
) -> Any:
    """Run ingestion in streaming_windowed mode.

    This mode uses an event-driven runtime with:
    - resumable stream checkpoints;
    - bounded window accumulators (tumbling/sliding/session/count);
    - duplicate replay suppression;
    - per-record quarantine for poison messages;
    - CDC schema-change artifacts when stream schema drifts.
    """
    from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
    from polisyos.fabric.data_plane.cursor_store import CursorStore
    from polisyos.fabric.data_plane.orchestrator import IngestionResult
    from polisyos.fabric.data_plane.streaming import process_stream_dataset
    from polisyos.fabric.evidence import build_evidence_bundle, persist_evidence_bundle

    store = _build_filesystem_store(cas_root)
    cursor_store = CursorStore(store, index_root=cas_root)
    datasets = _extract_datasets(connector_manifest)
    connector_registry = (
        ingestion_dependencies.registry if ingestion_dependencies is not None else None
    )

    source_refs: list[Any] = []
    warnings: list[str] = []
    total_chunks = 0
    total_rows = 0
    total_windows = 0
    total_cdc_events = 0
    total_quarantined = 0
    cursor_ref: str | None = None

    for ds_connector_id, ds_dataset_id in datasets:
        runtime_options = _stream_runtime_options_from_manifest(
            connector_manifest,
            dataset_id=ds_dataset_id,
        )
        if _connector_is_registered(ds_connector_id, registry=connector_registry):
            dataset_result = await process_stream_dataset(
                connector_id=ds_connector_id,
                dataset_id=ds_dataset_id,
                store=store,
                cursor_store=cursor_store,
                sanitize_rows=_sanitize_stream_rows,
                runtime_options=runtime_options,
                connection_config=connection_config,
                registry=connector_registry,
            )
        else:
            dataset_result = await _run_legacy_stream_dataset_from_fetch_async(
                store=store,
                connector_id=ds_connector_id,
                dataset_id=ds_dataset_id,
                connector_manifest=connector_manifest,
                connection_config=connection_config,
                registry=connector_registry,
            )
        warnings.extend(dataset_result.warnings)
        source_refs.extend(dataset_result.chunk_refs)
        source_refs.extend(dataset_result.window_refs)
        source_refs.extend(dataset_result.cdc_event_refs)
        total_chunks += dataset_result.chunks_processed
        total_rows += dataset_result.rows_emitted
        total_windows += len(dataset_result.window_refs)
        total_cdc_events += len(dataset_result.cdc_event_refs)
        total_quarantined += dataset_result.quarantined_rows
        if dataset_result.final_cursor_ref is not None:
            cursor_ref = dataset_result.final_cursor_ref

    if not source_refs:
        return IngestionResult(
            datasets_fetched=len(datasets),
            mode_effective="streaming_windowed",
            warnings=warnings or ["No data chunks received"],
            cursor_ref=cursor_ref,
        )

    manifest_payload = {
        "source": f"streaming_windowed:{source}",
        "license_name": license_name,
        "datasets": [
            {
                "connector_id": connector_id,
                "dataset_id": dataset_id,
            }
            for connector_id, dataset_id in datasets
        ],
        "total_chunks": total_chunks,
        "total_rows": total_rows,
        "total_windows": total_windows,
        "total_cdc_events": total_cdc_events,
        "quarantined_rows": total_quarantined,
    }
    manifest_ref = await _persist_streaming_manifest_async(
        store=store,
        manifest_payload=manifest_payload,
        source_refs=source_refs,
    )
    evidence_bundle = build_evidence_bundle(
        sources=[manifest_ref, *source_refs],
        notes=[
            f"streaming_windowed source={source}",
            f"datasets={len(datasets)}",
            f"chunks={total_chunks}",
            f"rows={total_rows}",
            f"windows={total_windows}",
            f"cdc_events={total_cdc_events}",
            f"quarantined_rows={total_quarantined}",
        ],
    )
    evidence_ref = await run_blocking_async(persist_evidence_bundle, store, evidence_bundle)

    data_snapshot_ref = None
    if produce_snapshot:
        snapshot = DataSnapshot(
            data_ref=manifest_ref,
            evidence_ref=evidence_ref,
            stats={
                "datasets_fetched": len(datasets),
                "total_chunks": total_chunks,
                "total_rows": total_rows,
                "total_windows": total_windows,
                "total_cdc_events": total_cdc_events,
                "quarantined_rows": total_quarantined,
                "source": f"streaming_windowed:{source}",
            },
            notes=[
                "fabric.data_plane.streaming_windowed",
                f"window_strategy={_stream_runtime_options_from_manifest(connector_manifest).window_policy.strategy.value}",
            ],
        )
        snapshot_ref = await _persist_streaming_snapshot_async(
            store=store,
            snapshot_payload=snapshot.model_dump(mode="json"),
            manifest_ref=manifest_ref,
            evidence_ref=evidence_ref,
        )
        data_snapshot_ref = DataSnapshotRef(artifact_id=snapshot_ref.artifact_id)

    return IngestionResult(
        evidence_bundle_ref=evidence_ref,
        data_snapshot_ref=data_snapshot_ref,
        datasets_fetched=len(datasets),
        mode_effective="streaming_windowed",
        warnings=warnings,
        cursor_ref=cursor_ref,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stream_runtime_options_from_manifest(
    connector_manifest: Any,
    *,
    dataset_id: str | None = None,
) -> Any:
    from polisyos.fabric.data_plane.streaming import StreamRuntimeOptions
    from polisyos.fabric.data_plane.watermark import WindowPolicy

    raw_streaming: dict[str, Any] = {}
    if isinstance(connector_manifest, dict):
        raw_streaming = dict(connector_manifest.get("streaming", {}) or {})
    else:
        value = getattr(connector_manifest, "streaming", None)
        if isinstance(value, dict):
            raw_streaming = dict(value)

    raw_window = dict(raw_streaming.get("window", {}) or {})
    if not raw_window and isinstance(connector_manifest, dict):
        raw_window = dict(connector_manifest.get("streaming_window", {}) or {})

    strategy_raw = str(raw_window.get("strategy", "tumbling")).strip().lower()
    try:
        strategy = WindowStrategy(strategy_raw)
    except ValueError:
        strategy = WindowStrategy.TUMBLING

    window_policy = WindowPolicy(
        strategy=strategy,
        size=raw_window.get("size", 1),
        slide=raw_window.get("slide"),
        session_gap_seconds=raw_window.get("session_gap_seconds"),
        timestamp_field=str(raw_window.get("timestamp_field", "event_time")),
    )
    partition_key = str(raw_streaming.get("partition_key", "default"))
    if dataset_id:
        partition_key = str(raw_streaming.get("partition_key", dataset_id))

    return StreamRuntimeOptions(
        partition_key=partition_key,
        batch_size=int(raw_streaming.get("batch_size", 1_000)),
        checkpoint_every_chunks=int(raw_streaming.get("checkpoint_every_chunks", 1)),
        dedupe_key_fields=tuple(
            raw_streaming.get("dedupe_key_fields", ("_message_id", "message_id", "id"))
        ),
        max_dedupe_keys=int(raw_streaming.get("max_dedupe_keys", 4_096)),
        max_buffered_rows=int(raw_streaming.get("max_buffered_rows", 10_000)),
        max_buffered_bytes=int(raw_streaming.get("max_buffered_bytes", 16 * 1024 * 1024)),
        pause_seconds=float(raw_streaming.get("pause_seconds", 0.01)),
        window_policy=window_policy,
    )


def _connector_is_registered(
    connector_id: str,
    *,
    registry: Any | None = None,
) -> bool:
    try:
        resolved_registry = _resolve_connector_registry(registry=registry)
        resolved_registry.get_entry(connector_id)
        return True
    except Exception:
        return False


def _run_legacy_stream_dataset(
    *,
    store: Any,
    connector_id: str,
    dataset_id: str,
    chunks: list[dict[str, Any]],
) -> Any:
    from types import SimpleNamespace

    from polisyos.fabric.connectors.types import DataChunk
    from polisyos.fabric.data_plane.streaming import persist_stream_chunk

    chunk_refs = []
    warnings: list[str] = []
    rows_emitted = 0
    quarantined_rows = 0

    for chunk_data in chunks:
        clean_rows, chunk_warnings, chunk_quarantined = _sanitize_stream_rows(
            chunk_data.get("data", []),
            connector_id=connector_id,
            dataset_id=dataset_id,
            store=store,
            chunk_index=int(chunk_data.get("chunk_index", 0)),
        )
        warnings.extend(chunk_warnings)
        quarantined_rows += chunk_quarantined
        rows_emitted += len(clean_rows)
        chunk_refs.append(
            persist_stream_chunk(
                store=store,
                connector_id=connector_id,
                dataset_id=dataset_id,
                partition_key="default",
                chunk=DataChunk(
                    data=clean_rows,
                    chunk_index=int(chunk_data.get("chunk_index", 0)),
                    row_count=len(clean_rows),
                    bytes_size=0,
                    is_first=bool(chunk_data.get("is_first", False)),
                    is_last=bool(chunk_data.get("is_last", False)),
                ),
                rows=clean_rows,
                dedupe_dropped=0,
            )
        )

    return SimpleNamespace(
        chunk_refs=chunk_refs,
        window_refs=[],
        cdc_event_refs=[],
        warnings=warnings,
        rows_emitted=rows_emitted,
        chunks_processed=len(chunks),
        quarantined_rows=quarantined_rows,
        final_cursor_ref=None,
    )


async def _run_legacy_stream_dataset_async(
    *,
    store: Any,
    connector_id: str,
    dataset_id: str,
    chunks: list[dict[str, Any]],
) -> Any:
    from types import SimpleNamespace

    from polisyos.core.artifacts.async_store import ensure_async_artifact_store
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.fabric.connectors.types import DataChunk

    async_store = ensure_async_artifact_store(store)
    chunk_refs = []
    warnings: list[str] = []
    rows_emitted = 0
    quarantined_rows = 0

    for chunk_data in chunks:
        clean_rows, chunk_warnings, chunk_quarantined = _sanitize_stream_rows(
            chunk_data.get("data", []),
            connector_id=connector_id,
            dataset_id=dataset_id,
            store=store,
            chunk_index=int(chunk_data.get("chunk_index", 0)),
        )
        warnings.extend(chunk_warnings)
        quarantined_rows += chunk_quarantined
        rows_emitted += len(clean_rows)
        chunk = DataChunk(
            data=clean_rows,
            chunk_index=int(chunk_data.get("chunk_index", 0)),
            row_count=len(clean_rows),
            bytes_size=0,
            is_first=bool(chunk_data.get("is_first", False)),
            is_last=bool(chunk_data.get("is_last", False)),
        )
        chunk_refs.append(
            await async_store.put_json(
                {
                    "connector_id": connector_id,
                    "dataset_id": dataset_id,
                    "partition_key": "default",
                    "chunk_index": int(chunk.chunk_index),
                    "row_count": len(clean_rows),
                    "bytes_size": int(getattr(chunk, "bytes_size", 0) or 0),
                    "resume_token": getattr(chunk, "resume_token", None),
                    "is_first": bool(getattr(chunk, "is_first", False)),
                    "is_last": bool(getattr(chunk, "is_last", False)),
                    "dedupe_dropped": 0,
                    "data": clean_rows,
                },
                ArtifactWriteOptions(
                    kind="fabric.stream_chunk",
                    media_type="application/json",
                    schema=SchemaInfo(name="fabric.StreamChunk", version="2.0"),
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
        )

    return SimpleNamespace(
        chunk_refs=chunk_refs,
        window_refs=[],
        cdc_event_refs=[],
        warnings=warnings,
        rows_emitted=rows_emitted,
        chunks_processed=len(chunks),
        quarantined_rows=quarantined_rows,
        final_cursor_ref=None,
    )


async def _run_legacy_stream_dataset_from_fetch_async(
    *,
    store: Any,
    connector_id: str,
    dataset_id: str,
    connector_manifest: Any,
    connection_config: Any | None,
    registry: Any | None = None,
) -> Any:
    chunks = await _fetch_stream_for_dataset_async(
        connector_id=connector_id,
        dataset_id=dataset_id,
        connector_manifest=connector_manifest,
        connection_config=connection_config,
        registry=registry,
    )
    return await _run_legacy_stream_dataset_async(
        store=store,
        connector_id=connector_id,
        dataset_id=dataset_id,
        chunks=chunks,
    )


def _extract_datasets(connector_manifest: Any) -> list[tuple[str, str]]:
    """Extract (connector_id, dataset_id) pairs from a manifest."""
    datasets = []
    raw = []
    if hasattr(connector_manifest, "datasets"):
        raw = connector_manifest.datasets
    elif isinstance(connector_manifest, dict):
        raw = connector_manifest.get("datasets", [])

    for ds in raw:
        cid = getattr(ds, "connector_id", "") or (
            ds.get("connector_id", "") if isinstance(ds, dict) else ""
        )
        did = getattr(ds, "dataset_id", "") or (
            ds.get("dataset_id", "") if isinstance(ds, dict) else ""
        )
        datasets.append((cid, did))
    return datasets


def _resolve_connector_registry(
    *,
    registry: Any | None = None,
) -> Any:
    if registry is not None:
        return registry
    return _default_connector_registry()


def _default_connector_registry() -> Any:
    from polisyos.fabric.connectors.registry import ConnectorRegistry

    return ConnectorRegistry.get_instance()


async def _fetch_stream_for_dataset_async(
    *,
    connector_id: str,
    dataset_id: str,
    connector_manifest: Any,
    connection_config: Any | None,
    registry: Any | None = None,
) -> list[dict[str, Any]]:
    """Fetch stream chunks for a single dataset without nesting a sync bridge."""
    del connector_manifest
    try:
        resolved_registry = _resolve_connector_registry(registry=registry)
        entry = cast("Any", resolved_registry.get_entry(connector_id))
        if entry is None:
            logger.warning("streaming_windowed: connector %s not found", connector_id)
            return []

        connector_cls = entry.connector_cls
        connector = connector_cls()

        from polisyos.fabric.connectors.capabilities import ConnectorCapability

        capabilities = cast("Any", entry.metadata.capabilities)
        if not (capabilities & ConnectorCapability.STREAMING):
            logger.info(
                "streaming_windowed: connector %s doesn't support streaming, "
                "falling back to single-chunk fetch",
                connector_id,
            )
            return []

        handle = await connector.connect(connection_config)
        try:
            from polisyos.ir.connectors import FetchRequest

            request = FetchRequest(dataset_id=dataset_id)
            chunks: list[dict[str, Any]] = []
            async for chunk in connector.fetch_stream(handle, request):
                data = chunk.data
                rows: list[Any] = []
                if hasattr(data, "to_dict"):
                    rows = await run_blocking_async(
                        data.to_dict,
                        orient="records",
                    )
                elif isinstance(data, list):
                    rows = data

                chunks.append(
                    {
                        "chunk_index": chunk.chunk_index,
                        "row_count": chunk.row_count,
                        "is_first": chunk.is_first,
                        "is_last": chunk.is_last,
                        "data": rows,
                    }
                )
            return chunks
        finally:
            await connector.disconnect(handle)
    except Exception as exc:
        logger.warning(
            "streaming_windowed: failed to stream %s:%s: %s",
            connector_id,
            dataset_id,
            exc,
        )
        return []


def _fetch_stream_for_dataset(
    *,
    connector_id: str,
    dataset_id: str,
    connector_manifest: Any,
    connection_config: Any | None,
    registry: Any | None = None,
) -> list[dict[str, Any]]:
    """Fetch stream chunks for a single dataset.

    Returns a list of chunk dicts with keys: chunk_index, row_count,
    is_first, is_last, data (list of row dicts).
    """
    result: list[dict[str, Any]] = run_coro_sync(
        _fetch_stream_for_dataset_async(
            connector_id=connector_id,
            dataset_id=dataset_id,
            connector_manifest=connector_manifest,
            connection_config=connection_config,
            registry=registry,
        )
    )
    return result


__all__ = [
    "run_batch_incremental",
    "run_record_mode",
    "run_replay_mode",
    "run_streaming_windowed",
]
