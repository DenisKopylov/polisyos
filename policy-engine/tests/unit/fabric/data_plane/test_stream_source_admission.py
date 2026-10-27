"""Baseline-compatible red probe for present but unowned stream key fields."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.cursor import WindowStrategy
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.streaming import (
    StreamDedupeUnsupported,
    StreamRuntimeOptions,
    process_stream_dataset,
)
from polisyos.fabric.data_plane.watermark import WindowPolicy


@pytest.mark.asyncio
async def test_b83_present_transport_id_is_unsupported_without_an_owner_contract(
    tmp_path: Path,
) -> None:
    rows = [
        {"_message_id": "entity", "source_version": 1},
        {"_message_id": "entity", "source_version": 2},
    ]
    path = tmp_path / "events.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config("stream.jsonl", ConnectionConfig(url=path.as_uri()))
    store = FileSystemCAS(tmp_path / "cas")
    before = set(map(str, store.iter_artifact_ids()))

    def valid_rows(batch, **kwargs):
        del kwargs
        return list(batch), [], 0

    try:
        with pytest.raises(StreamDedupeUnsupported):
            await process_stream_dataset(
                connector_id="stream.jsonl",
                dataset_id="events",
                store=store,
                cursor_store=CursorStore(store),
                sanitize_rows=valid_rows,
                runtime_options=StreamRuntimeOptions(
                    window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=1),
                ),
                registry=registry,
            )
        assert set(map(str, store.iter_artifact_ids())) == before
        assert CursorStore(store).find_latest_cursor("stream.jsonl", "events") is None
        assert CursorStore(store).find_latest_stream_checkpoint("stream.jsonl", "events") is None
    finally:
        await registry.shutdown_async()
