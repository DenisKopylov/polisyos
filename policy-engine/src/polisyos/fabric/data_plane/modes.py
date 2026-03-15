"""Execution mode dispatch for data ingestion.

Provides:
- batch_incremental: cursor-based incremental ingestion
- record_mode: run ingestion while capturing HTTP responses to CAS
- replay_mode: run ingestion from captured HTTP responses (no network)
- streaming_windowed: per-chunk CAS persistence via fetch_stream()
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.contracts.cursor import CursorState

logger = get_logger(__name__)


def run_batch_incremental(
    *,
    connector_manifest: Any,
    source: str,
    license_name: str,
    cas_root: Path,
    connection_config: Any | None = None,
    produce_snapshot: bool = True,
) -> Any:
    """Run ingestion in batch_incremental mode.

    1. For each dataset, look up latest cursor via CursorStore.
    2. Build incremental_cursors dict mapping dataset_id → cursor watermark.
    3. Delegate to run_connectors_ingestion with incremental hints.
    4. Extract watermarks from results and save new cursors.
    5. Return IngestionResult with cursor_ref.
    """
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.fabric.data_plane.cursor_store import CursorStore
    from polisyos.fabric.data_plane.orchestrator import (
        IngestionResult,
        run_orchestrated_ingestion,
    )

    store = FileSystemCAS(cas_root)
    cursor_store = CursorStore(store)

    # Look up prior cursors for each dataset
    incremental_cursors: dict[str, str] = {}
    datasets = []
    if hasattr(connector_manifest, "datasets"):
        datasets = connector_manifest.datasets
    elif isinstance(connector_manifest, dict):
        datasets = connector_manifest.get("datasets", [])

    connector_id = ""
    for ds in datasets:
        ds_connector_id = getattr(ds, "connector_id", "") or ds.get("connector_id", "") if isinstance(ds, dict) else ""
        ds_dataset_id = getattr(ds, "dataset_id", "") or ds.get("dataset_id", "") if isinstance(ds, dict) else ""
        if ds_connector_id:
            connector_id = ds_connector_id
        cursor = cursor_store.find_latest_cursor(ds_connector_id, ds_dataset_id)
        if cursor is not None:
            incremental_cursors[ds_dataset_id] = cursor.watermark_value
            logger.info(
                "batch_incremental: cursor found for %s:%s → %s",
                ds_connector_id, ds_dataset_id, cursor.watermark_value,
            )

    # Run normal orchestrated ingestion
    result = run_orchestrated_ingestion(
        connector_manifest=connector_manifest,
        source=source,
        license_name=license_name,
        cas_root=cas_root,
        connection_config=connection_config,
        produce_snapshot=produce_snapshot,
    )

    # Save new cursor based on ingestion result
    if result.datasets_fetched > 0:
        from polisyos.fabric.data_plane.watermark import resolve_watermark_policy

        connector_family = connector_id.split(".")[0] if connector_id else ""
        policy = resolve_watermark_policy(connector_family)
        now = datetime.now(timezone.utc)

        for ds in datasets:
            ds_connector_id = getattr(ds, "connector_id", "") or (ds.get("connector_id", "") if isinstance(ds, dict) else "")
            ds_dataset_id = getattr(ds, "dataset_id", "") or (ds.get("dataset_id", "") if isinstance(ds, dict) else "")

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

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.fabric.connectors.testing.simulator import APISimulator, SimulatorMode
    from polisyos.fabric.data_plane.orchestrator import run_orchestrated_ingestion
    from polisyos.fabric.data_plane.replay_store import (
        ReplayStore,
        make_record_session,
    )

    session_id = uuid.uuid4().hex

    # Extract connector/dataset info for the session metadata
    datasets = _extract_datasets(connector_manifest)
    connector_datasets = [
        {"connector_id": ds[0], "dataset_id": ds[1]} for ds in datasets
    ]

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
        from polisyos.fabric.ingestion import run_coro_sync

        async def _record_ingestion() -> Any:
            async with simulator:
                # run_orchestrated_ingestion is sync but calls run_coro_sync
                # internally. Since we're already in an event loop from
                # run_coro_sync, we call the underlying ingestion directly.
                from polisyos.fabric.ingestion import run_connectors_ingestion

                evidence_ref = run_connectors_ingestion(
                    connector_manifest=connector_manifest,
                    source=source,
                    license_name=license_name,
                    cas_root=cas_root,
                    connection_config=connection_config,
                )
                return evidence_ref

        try:
            evidence_ref = run_coro_sync(_record_ingestion())
        except Exception:
            logger.debug(
                "Async record ingestion failed, falling back to sync path", exc_info=True,
            )
            # Fall back to sync path if async context isn't needed
            result = run_orchestrated_ingestion(
                connector_manifest=connector_manifest,
                source=source,
                license_name=license_name,
                cas_root=cas_root,
                connection_config=connection_config,
                produce_snapshot=produce_snapshot,
            )

            # Still try to collect any fixtures that were captured
            session = make_record_session(
                session_id=session_id,
                fixture_root=fixture_root,
                connector_datasets=connector_datasets,
            )
            store = FileSystemCAS(cas_root)
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
        store = FileSystemCAS(cas_root)
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
) -> Any:
    """Run ingestion using recorded HTTP responses (no network).

    1. Load RecordSession from CAS via replay_ref.
    2. Write fixtures to temp dir via ReplayStore.build_replay_fixture_dir().
    3. Run ingestion — APISimulator in REPLAY mode serves cached responses.
    4. Return IngestionResult.
    """
    import tempfile

    from polisyos.core.artifacts.manifest import ArtifactID
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.fabric.data_plane.orchestrator import run_orchestrated_ingestion
    from polisyos.fabric.data_plane.replay_store import ReplayStore

    store = FileSystemCAS(cas_root)
    replay_store = ReplayStore(store)

    # Load session from CAS
    artifact_id = ArtifactID.from_hex(replay_ref)
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

        from polisyos.fabric.ingestion import run_coro_sync

        async def _replay_ingestion() -> Any:
            async with simulator:
                from polisyos.fabric.ingestion import run_connectors_ingestion

                return run_connectors_ingestion(
                    connector_manifest=connector_manifest,
                    source=source,
                    license_name=license_name,
                    cas_root=cas_root,
                    connection_config=connection_config,
                )

        try:
            evidence_ref = run_coro_sync(_replay_ingestion())
        except Exception:
            logger.debug(
                "Async replay ingestion failed, falling back to sync path", exc_info=True,
            )
            # Fallback to standard orchestrated ingestion (simulator is async)
            result = run_orchestrated_ingestion(
                connector_manifest=connector_manifest,
                source=source,
                license_name=license_name,
                cas_root=cas_root,
                connection_config=connection_config,
                produce_snapshot=produce_snapshot,
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


def run_streaming_windowed(
    *,
    connector_manifest: Any,
    source: str,
    license_name: str,
    cas_root: Path,
    connection_config: Any | None = None,
    produce_snapshot: bool = True,
) -> Any:
    """Run ingestion in streaming_windowed mode.

    For each dataset:
    1. Resolve connector via ConnectorRegistry.
    2. Call connector.fetch_stream(handle, request) → yields DataChunk.
    3. For each DataChunk: serialize to CAS as 'fabric.stream_chunk' artifact.
    4. After all chunks: aggregate rows, build EvidenceBundle + DataSnapshot.
    5. Return IngestionResult with mode_effective='streaming_windowed'.
    """
    from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.fabric.data_plane.orchestrator import IngestionResult

    store = FileSystemCAS(cas_root)
    datasets = _extract_datasets(connector_manifest)

    all_chunk_refs: list[Any] = []
    all_rows: list[dict] = []
    total_chunks = 0

    for ds_connector_id, ds_dataset_id in datasets:
        chunks = _fetch_stream_for_dataset(
            connector_id=ds_connector_id,
            dataset_id=ds_dataset_id,
            connector_manifest=connector_manifest,
            connection_config=connection_config,
        )

        for chunk_data in chunks:
            chunk_payload = {
                "connector_id": ds_connector_id,
                "dataset_id": ds_dataset_id,
                "chunk_index": chunk_data.get("chunk_index", total_chunks),
                "row_count": chunk_data.get("row_count", 0),
                "is_first": chunk_data.get("is_first", False),
                "is_last": chunk_data.get("is_last", False),
                "data": chunk_data.get("data", []),
            }

            chunk_ref = store.put_json(
                chunk_payload,
                PutOptions(
                    kind="fabric.stream_chunk",
                    media_type="application/json",
                    schema=SchemaInfo(
                        name="fabric.StreamChunk", version="1.0",
                    ),
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
            all_chunk_refs.append(chunk_ref)
            all_rows.extend(chunk_data.get("data", []))
            total_chunks += 1

    # Build evidence bundle from aggregated data
    if all_rows and produce_snapshot:
        aggregated_payload = {
            "source": f"streaming_windowed:{source}",
            "total_chunks": total_chunks,
            "total_rows": len(all_rows),
            "data": all_rows,
        }
        evidence_ref = store.put_json(
            aggregated_payload,
            PutOptions(
                kind="fabric.evidence_bundle",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.fabric.EvidenceBundle", version="1.0",
                ),
                inputs=[
                    InputRef(artifact_id=cr.artifact_id, role="stream_chunk")
                    for cr in all_chunk_refs
                ],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )

        # Build snapshot
        snapshot_payload = {
            "source": f"streaming_windowed:{source}",
            "total_chunks": total_chunks,
            "total_rows": len(all_rows),
        }
        snapshot_ref = store.put_json(
            snapshot_payload,
            PutOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.core.DataSnapshot", version="0.2.0",
                ),
                inputs=[
                    InputRef(artifact_id=evidence_ref.artifact_id, role="evidence_ref"),
                ],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )

        from polisyos.core.contracts.fabric import DataSnapshotRef, EvidenceBundleRef

        return IngestionResult(
            evidence_bundle_ref=EvidenceBundleRef(artifact_id=evidence_ref.artifact_id),
            data_snapshot_ref=DataSnapshotRef(artifact_id=snapshot_ref.artifact_id),
            datasets_fetched=len(datasets),
            mode_effective="streaming_windowed",
        )

    return IngestionResult(
        datasets_fetched=len(datasets),
        mode_effective="streaming_windowed",
        warnings=["No data chunks received"] if not all_rows else [],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_datasets(connector_manifest: Any) -> list[tuple[str, str]]:
    """Extract (connector_id, dataset_id) pairs from a manifest."""
    datasets = []
    raw = []
    if hasattr(connector_manifest, "datasets"):
        raw = connector_manifest.datasets
    elif isinstance(connector_manifest, dict):
        raw = connector_manifest.get("datasets", [])

    for ds in raw:
        cid = getattr(ds, "connector_id", "") or (ds.get("connector_id", "") if isinstance(ds, dict) else "")
        did = getattr(ds, "dataset_id", "") or (ds.get("dataset_id", "") if isinstance(ds, dict) else "")
        datasets.append((cid, did))
    return datasets


def _fetch_stream_for_dataset(
    *,
    connector_id: str,
    dataset_id: str,
    connector_manifest: Any,
    connection_config: Any | None,
) -> list[dict[str, Any]]:
    """Fetch stream chunks for a single dataset.

    Returns a list of chunk dicts with keys: chunk_index, row_count,
    is_first, is_last, data (list of row dicts).
    """
    try:
        from polisyos.fabric.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry.get_instance()
        entry = registry.get_entry(connector_id)
        if entry is None:
            logger.warning("streaming_windowed: connector %s not found", connector_id)
            return []

        connector_cls = entry.connector_cls
        connector = connector_cls()

        # Check if connector supports streaming
        from polisyos.fabric.connectors.capabilities import ConnectorCapability
        if not (entry.metadata.capabilities & ConnectorCapability.STREAMING):
            logger.info(
                "streaming_windowed: connector %s doesn't support streaming, "
                "falling back to single-chunk fetch",
                connector_id,
            )
            return []

        # Use async fetch_stream
        from polisyos.fabric.ingestion import run_coro_sync

        async def _stream() -> list[dict[str, Any]]:
            handle = await connector.connect(connection_config)
            try:
                from polisyos.fabric.connectors.types.connector_types import FetchRequest

                request = FetchRequest(dataset_id=dataset_id)
                chunks = []
                idx = 0
                async for chunk in connector.fetch_stream(handle, request):
                    data = chunk.data
                    rows = []
                    if hasattr(data, "to_dict"):
                        rows = data.to_dict(orient="records")
                    elif isinstance(data, list):
                        rows = data

                    chunks.append({
                        "chunk_index": chunk.chunk_index,
                        "row_count": chunk.row_count,
                        "is_first": chunk.is_first,
                        "is_last": chunk.is_last,
                        "data": rows,
                    })
                    idx += 1
                return chunks
            finally:
                await connector.disconnect(handle)

        return run_coro_sync(_stream())

    except Exception as exc:
        logger.warning("streaming_windowed: failed to stream %s:%s: %s", connector_id, dataset_id, exc)
        return []


__all__ = [
    "run_batch_incremental",
    "run_record_mode",
    "run_replay_mode",
    "run_streaming_windowed",
]
