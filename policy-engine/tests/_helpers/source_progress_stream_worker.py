"""OS-process worker for explicit replay-clock source-key horizon checks."""

from __future__ import annotations

import asyncio
import hashlib
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
from polisyos.fabric.data_plane.streaming import (
    StreamDedupeUnsupported,
    StreamRuntimeOptions,
    process_stream_dataset,
)
from polisyos.fabric.data_plane.watermark import WindowPolicy
from polisyos.fabric.ingestion.source_progress import FiniteSourceProgressReader


def _first_party_source_snapshot() -> dict[str, dict[str, str]]:
    """Identify a finite set of loaded product modules used by this worker."""
    names = (
        "polisyos.core.artifacts.store",
        "polisyos.fabric.data_plane.cursor_store",
        "polisyos.fabric.data_plane.streaming",
        "polisyos.fabric.ingestion.source_progress",
    )
    snapshot: dict[str, dict[str, str]] = {}
    for name in names:
        module = sys.modules[name]
        origin = Path(module.__file__).resolve()
        snapshot[name] = {
            "origin": str(origin),
            "sha256": hashlib.sha256(origin.read_bytes()).hexdigest(),
        }
    return snapshot


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
    if config.get("remove_source_binding", False):
        import polisyos.fabric.ingestion.source_progress as source_progress

        def removed_source_binding(*args: object, **kwargs: object) -> None:
            del args, kwargs

        source_progress.resolve_source_progress_frame = removed_source_binding
    results = []
    try:
        for step in config["steps"]:
            if step["append"]:
                with stream_path.open("a", encoding="utf-8") as stream:
                    event = step.get("event", config["event"])
                    stream.write(json.dumps(event, sort_keys=True) + "\n")
            at = datetime.fromisoformat(step["at"])
            ingestion_times = [
                datetime.fromisoformat(value) for value in step.get("ingestion_times", [])
            ]

            def ingestion_clock(
                captured_times: list[datetime] = ingestion_times,
                captured_at: datetime = at,
            ) -> datetime:
                return captured_times.pop(0) if captured_times else captured_at

            store = FileSystemCAS(root / "cas")
            try:
                result = await process_stream_dataset(
                    connector_id="stream.jsonl",
                    dataset_id="horizon",
                    store=store,
                    cursor_store=CursorStore(store),
                    sanitize_rows=valid_rows,
                    runtime_options=StreamRuntimeOptions(
                        ingestion_clock=ingestion_clock,
                        checkpoint_every_chunks=1,
                        window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=1),
                    ),
                    registry=registry,
                    source_progress_readers=(reader,),
                )
            except StreamDedupeUnsupported as exc:
                results.append(
                    {"at": step["at"], "error_type": type(exc).__name__, "error": str(exc)}
                )
            else:
                checkpoint = CursorStore(store).find_latest_stream_checkpoint(
                    "stream.jsonl", "horizon"
                )
                assert checkpoint is not None
                results.append(
                    {
                        "at": step["at"],
                        "rows_emitted": result.rows_emitted,
                        "dedupe_dropped": result.dedupe_dropped,
                        "guarantee": result.processing_guarantee,
                        "dedupe_horizon": checkpoint.metadata["dedupe_horizon"],
                    }
                )
    finally:
        await registry.shutdown_async()
    print(
        json.dumps(
            {
                "pid": os.getpid(),
                "clock_profile": "fixture_utc",
                "source_modules": _first_party_source_snapshot(),
                "results": results,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
