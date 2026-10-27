"""OS-process worker for explicit replay-clock source-key horizon checks."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.cursor import WindowStrategy
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.contracts.source_contract import (
    SourceContract,
    SourceProgressContract,
)
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.streaming import StreamRuntimeOptions, process_stream_dataset
from polisyos.fabric.data_plane.watermark import WindowPolicy
from polisyos.fabric.ingestion.source_progress import FiniteSourceProgressReader


def valid_rows(batch, **kwargs):
    del kwargs
    return list(batch), [], 0


async def main() -> None:
    config = json.loads(Path(sys.argv[1]).read_text())
    root = Path(config["root"])
    source = SourceContract.model_validate(config["source_contract"])
    extension = SourceProgressContract.model_validate(config["extension"])
    reader = FiniteSourceProgressReader(Path(config["source_root"]), source, extension)
    stream_path = root / "stream.jsonl"
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(url=stream_path.as_uri(), headers={"X-Stream-ChunkSize": "1"}),
    )
    results = []
    try:
        for step in config["steps"]:
            if step["append"]:
                with stream_path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(config["event"], sort_keys=True) + "\n")
            at = datetime.fromisoformat(step["at"])
            store = FileSystemCAS(root / "cas")
            result = await process_stream_dataset(
                connector_id="stream.jsonl",
                dataset_id="horizon",
                store=store,
                cursor_store=CursorStore(store),
                sanitize_rows=valid_rows,
                runtime_options=StreamRuntimeOptions(
                    ingestion_clock=lambda now=at: now,
                    checkpoint_every_chunks=1,
                    window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=1),
                ),
                registry=registry,
                source_progress_readers=(reader,),
            )
            results.append(
                {
                    "at": step["at"],
                    "rows_emitted": result.rows_emitted,
                    "dedupe_dropped": result.dedupe_dropped,
                    "guarantee": result.processing_guarantee,
                }
            )
    finally:
        await registry.shutdown_async()
    print(json.dumps({"pid": os.getpid(), "clock_profile": "fixture_utc", "results": results}))


if __name__ == "__main__":
    asyncio.run(main())
