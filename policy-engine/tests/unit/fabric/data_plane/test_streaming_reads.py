"""Fresh selected stream-window reads require every concrete contributor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.cursor import WindowStrategy
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.event_stream import EventStreamConnector
from polisyos.fabric.data_plane import streaming
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.watermark import WindowPolicy
from polisyos.runtime.http.services.lineage import LineageService
from tests._helpers.source_progress import finite_source_reader


def _accept_rows(rows: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], list[str], int]:
    del kwargs
    return [dict(row) for row in rows], [], 0


@pytest.mark.asyncio
async def test_selected_window_withholds_withdrawn_contributor_and_preserves_independent_window(
    tmp_path: Path,
) -> None:
    """A+B cannot borrow valid B, while independent C+D remains readable after removing A."""
    dataset_id = "selected-window-withdrawal"
    rows = [
        {
            "event_id": name,
            "source_version": 1,
            "event_time": f"2026-01-01T00:00:{second:02d}+00:00",
            "value": index,
        }
        for index, (name, second) in enumerate((("A", 0), ("B", 1), ("C", 20), ("D", 21)))
    ]
    stream_path = tmp_path / "events.jsonl"
    stream_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    reader = finite_source_reader(
        tmp_path / "source",
        connector_id="stream.jsonl",
        dataset_id=dataset_id,
        schema_id="fixture.selected_window_withdrawal",
        snapshots=[("finite-current", rows)],
        transport_path=stream_path,
    )
    registry = ConnectorRegistry()
    registry.register(
        EventStreamConnector,
        config=ConnectionConfig(url=stream_path.as_uri(), headers={"X-Stream-ChunkSize": "1"}),
    )
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root)
    try:
        result = await streaming.process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=dataset_id,
            store=store,
            cursor_store=CursorStore(store),
            sanitize_rows=_accept_rows,
            registry=registry,
            source_progress_readers=(reader,),
            runtime_options=streaming.StreamRuntimeOptions(
                batch_size=1,
                window_policy=WindowPolicy(strategy=WindowStrategy.TUMBLING, size=10),
            ),
        )
        assert len(result.chunk_refs) == 4 and len(result.window_refs) == 2
        dependent, independent = result.window_refs
        fresh = FileSystemCAS(cas_root)
        before = streaming.read_stream_window(fresh, dependent)
        assert before["data"] == rows[:2]
        assert streaming.read_stream_window(fresh, independent)["data"] == rows[2:]
        # C triggers emission of A+B but contributes no row to that window.
        manifest = fresh.get_manifest(dependent)
        contributors = [item for item in manifest.inputs or () if item.role == "stream_chunk"]
        assert {str(item.artifact_id) for item in contributors} == {
            str(ref.artifact_id) for ref in result.chunk_refs[:2]
        }
        assert all(item.manifest_profile_sha256 for item in contributors)
        assert LineageService(store=fresh).build_for_artifact_ids([dependent]).is_complete

        # This is an owned temporary CAS blob, never external source or user storage.
        withdrawn = result.chunk_refs[0]
        blob_path, _manifest_path = fresh._paths(withdrawn.artifact_id)
        retained_bytes = blob_path.read_bytes()
        blob_path.unlink()
        try:
            reopened = FileSystemCAS(cas_root)
            with pytest.raises(streaming.StreamWindowBasisUnavailableError, match="basis"):
                streaming.read_stream_window(reopened, dependent)
            affected = LineageService(store=reopened).build_for_artifact_ids([dependent])
            assert not affected.is_complete
            assert streaming.read_stream_window(reopened, independent)["data"] == rows[2:]
            assert LineageService(store=reopened).build_for_artifact_ids([independent]).is_complete
        finally:
            blob_path.write_bytes(retained_bytes)

        # Revalidation consumes the same produced selected basis after exact restoration.
        restored = FileSystemCAS(cas_root)
        assert restored.verify(withdrawn).ok
        assert streaming.read_stream_window(restored, dependent) == before
        assert LineageService(store=restored).build_for_artifact_ids([dependent]).is_complete
        assert result.processing_guarantee == "replay_only"
    finally:
        await registry.shutdown_async()
