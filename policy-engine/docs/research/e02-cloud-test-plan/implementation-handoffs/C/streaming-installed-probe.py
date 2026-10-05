from __future__ import annotations

import asyncio
import json
import sys
import sysconfig
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import polisyos.core.artifacts.store as artifact_store_module
import polisyos.fabric.connectors.sources.event_stream as event_stream_module
import polisyos.fabric.data_plane.cursor_store as cursor_store_module
import polisyos.fabric.data_plane.streaming as streaming_module
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.cursor import StreamLifecycleState, WindowStrategy
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.streaming import StreamRuntimeOptions, process_stream_dataset
from polisyos.fabric.data_plane.watermark import WindowPolicy
from loguru import logger as _loguru_logger

_loguru_logger.remove()
_loguru_logger.add(sys.stderr, level="CRITICAL")

from polisyos.fabric.quality.processing_guarantees import (
    BackpressurePolicy,
    BackpressureStrategy,
    stream_processing_contract,
)

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "run-data"
CONNECTOR_ID = "stream.jsonl"
START = datetime(2024, 6, 15, 12, 0, tzinfo=UTC)
EXPECTED_STRATEGIES = tuple(BackpressureStrategy)


def report_modules() -> None:
    target = Path(sysconfig.get_paths()["purelib"]).resolve()
    modules: tuple[ModuleType, ...] = (
        streaming_module,
        cursor_store_module,
        event_stream_module,
        artifact_store_module,
    )
    for module in modules:
        origin = Path(module.__file__).resolve()
        assert origin.is_relative_to(target), f"{module.__name__} escaped wheel target: {origin}"
        print(f"IMPORT {module.__name__}={origin}")
    forbidden = {
        Path("/Users/deniskopylov/polisyos/policy-engine").resolve(),
        Path("/Users/deniskopylov/polisyos/policy-engine/src").resolve(),
    }
    leaked = [entry for entry in sys.path if Path(entry or ".").resolve() in forbidden]
    assert not leaked, f"checkout paths leaked into sys.path: {leaked}"
    assert "PYTHONPATH" not in __import__("os").environ
    print(f"IMPORT_TARGET {target}")
    print("SOURCE_CHECKOUT_PATHS none; PYTHONPATH unset")


def configure_source(
    run_root: Path,
    dataset_id: str,
    rows: list[dict[str, Any]],
) -> tuple[ConnectorRegistry, FileSystemCAS, CursorStore]:
    if run_root.exists():
        raise RuntimeError(f"refusing to reuse probe state: {run_root}")
    run_root.mkdir(parents=True)
    source_path = run_root / f"{dataset_id}.jsonl"
    source_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        CONNECTOR_ID,
        ConnectionConfig(
            url=source_path.as_uri(),
            headers={"X-Stream-ChunkSize": "2"},
        ),
    )
    store = FileSystemCAS(run_root / "cas")
    return registry, store, CursorStore(store)


def make_rows(gaps: tuple[int, ...]) -> list[dict[str, Any]]:
    return [
        {
            "_message_id": f"m{index}",
            "event_time": (START + timedelta(seconds=gap)).isoformat(),
            "value": "x" * 16,
        }
        for index, gap in enumerate(gaps)
    ]


def session_policy() -> WindowPolicy:
    return WindowPolicy(
        strategy=WindowStrategy.SESSION,
        size=300,
        session_gap_seconds=5,
        timestamp_field="event_time",
    )


def count_policy() -> WindowPolicy:
    return WindowPolicy(strategy=WindowStrategy.COUNT, size=2)


def tumbling_policy() -> WindowPolicy:
    return WindowPolicy(
        strategy=WindowStrategy.TUMBLING,
        size=5,
        timestamp_field="event_time",
    )


def runtime_options(
    *,
    strategy: BackpressureStrategy,
    max_rows: int,
    max_bytes: int,
    window_policy: WindowPolicy,
) -> StreamRuntimeOptions:
    contract = stream_processing_contract().model_copy(
        update={
            "backpressure": BackpressurePolicy(
                strategy=strategy,
                max_buffered_rows=max_rows,
                max_buffered_bytes=max_bytes,
                pause_seconds=0,
            )
        }
    )
    return StreamRuntimeOptions(
        batch_size=1,
        max_dedupe_keys=8,
        max_buffered_rows=max_rows,
        max_buffered_bytes=max_bytes,
        pause_seconds=0,
        window_policy=window_policy,
        processing_contract=contract,
    )


def sanitize_rows(batch: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], list[str], int]:
    del kwargs
    return [dict(row) for row in batch if isinstance(row, dict)], [], 0


def stream_chunks(store: FileSystemCAS) -> dict[int, tuple[str, dict[str, Any]]]:
    chunks: dict[int, tuple[str, dict[str, Any]]] = {}
    for artifact_id in store.iter_artifact_ids():
        manifest = store.get_manifest(artifact_id)
        if manifest.kind != "fabric.stream_chunk":
            continue
        payload = from_canonical_bytes(store.get_bytes(artifact_id))
        chunks[int(payload["chunk_index"])] = (str(artifact_id), payload)
    return chunks


def emitted_ids(store: FileSystemCAS, result: Any) -> list[str]:
    ids = [
        str(row["_message_id"])
        for ref in result.window_refs
        for row in from_canonical_bytes(store.get_bytes(ref.artifact_id))["data"]
    ]
    return ids


def assert_frontier(
    cursor_store: CursorStore,
    dataset_id: str,
    *,
    expected_offset: int,
) -> tuple[Any, Any]:
    cursor = cursor_store.find_latest_cursor(CONNECTOR_ID, dataset_id)
    checkpoint = cursor_store.find_latest_stream_checkpoint(CONNECTOR_ID, dataset_id)
    assert cursor is not None
    assert checkpoint is not None
    assert cursor.watermark_value == str(expected_offset)
    assert checkpoint.offset == expected_offset
    return cursor, checkpoint


async def stream(
    *,
    dataset_id: str,
    registry: ConnectorRegistry,
    store: FileSystemCAS,
    cursor_store: CursorStore,
    options: StreamRuntimeOptions,
) -> Any:
    return await process_stream_dataset(
        connector_id=CONNECTOR_ID,
        dataset_id=dataset_id,
        store=store,
        cursor_store=cursor_store,
        sanitize_rows=sanitize_rows,
        runtime_options=options,
        registry=registry,
    )


def verify_overflow_restart(strategy: BackpressureStrategy) -> None:
    dataset_id = f"retry-{strategy.value}"
    rows = make_rows((0, 1, 2, 3))
    run_root = RUNS / dataset_id
    registry, store, cursor_store = configure_source(run_root, dataset_id, rows)
    try:
        asyncio.run(
            stream(
                dataset_id=dataset_id,
                registry=registry,
                store=store,
                cursor_store=cursor_store,
                options=runtime_options(
                    strategy=strategy,
                    max_rows=3,
                    max_bytes=100_000,
                    window_policy=session_policy(),
                ),
            )
        )
    except RuntimeError as exc:
        assert any(token in str(exc) for token in ("capacity", "backpressure", "spill")), str(exc)
        print(f"OVERFLOW {strategy.value}=refused ({exc})")
    else:
        raise AssertionError(f"{strategy.value}: cap 3 admitted four retained session rows")

    cursor, paused = assert_frontier(cursor_store, dataset_id, expected_offset=0)
    assert paused.lifecycle_state == StreamLifecycleState.PAUSED
    assert paused.metadata["observed_offset"] == 1
    assert paused.metadata["frontier_committed"] is True
    prior = paused.metadata["operator_state"]["accumulator"]["session_rows"]
    assert [entry["row"]["_message_id"] for entry in prior] == ["m0", "m1"]
    chunks = stream_chunks(store)
    assert set(chunks) == {0}, f"refused chunk persisted: {sorted(chunks)}"
    first_chunk_ref, first_chunk = chunks[0]
    assert first_chunk["row_count"] == 2
    assert [entry["refs"] for entry in prior] == [[first_chunk_ref], [first_chunk_ref]]
    assert cursor.watermark_value == "0"
    print(
        f"FRONTIER {strategy.value}=cursor:{cursor.watermark_value},"
        f"checkpoint:{paused.offset}/{paused.lifecycle_state.value},"
        f"observed:{paused.metadata['observed_offset']},"
        f"retained:m0,m1,refs:{first_chunk_ref},chunks:0"
    )

    ConnectorRegistry.reset_instance()
    retry_registry = ConnectorRegistry.get_instance()
    retry_registry.set_default_config(
        CONNECTOR_ID,
        ConnectionConfig(
            url=(run_root / f"{dataset_id}.jsonl").as_uri(),
            headers={"X-Stream-ChunkSize": "2"},
        ),
    )
    result = asyncio.run(
        stream(
            dataset_id=dataset_id,
            registry=retry_registry,
            store=store,
            cursor_store=cursor_store,
            options=runtime_options(
                strategy=strategy,
                max_rows=4,
                max_bytes=100_000,
                window_policy=session_policy(),
            ),
        )
    )
    chunks = stream_chunks(store)
    assert set(chunks) == {0, 1}
    assert chunks[1][1]["data"] == rows[2:]
    observed = emitted_ids(store, result)
    assert Counter(observed) == Counter(row["_message_id"] for row in rows)
    final_cursor, final_checkpoint = assert_frontier(
        cursor_store,
        dataset_id,
        expected_offset=1,
    )
    assert final_checkpoint.lifecycle_state == StreamLifecycleState.CLOSED
    print(
        f"RESTART {strategy.value}=chunks:0,1,emitted:{','.join(observed)},"
        f"run_rows_emitted:{result.rows_emitted},cursor:{final_cursor.watermark_value},"
        f"checkpoint:{final_checkpoint.offset}/closed"
    )


def verify_exact_closing(strategy: BackpressureStrategy, policy: WindowPolicy, label: str) -> None:
    dataset_id = f"exact-{strategy.value}-{label}"
    rows = make_rows((0, 1, 10, 11))
    registry, store, cursor_store = configure_source(RUNS / dataset_id, dataset_id, rows)
    result = asyncio.run(
        stream(
            dataset_id=dataset_id,
            registry=registry,
            store=store,
            cursor_store=cursor_store,
            options=runtime_options(
                strategy=strategy,
                max_rows=2,
                max_bytes=100_000,
                window_policy=policy,
            ),
        )
    )
    observed = emitted_ids(store, result)
    assert result.rows_emitted == len(rows)
    assert Counter(observed) == Counter(row["_message_id"] for row in rows)
    cursor, checkpoint = assert_frontier(cursor_store, dataset_id, expected_offset=1)
    assert checkpoint.lifecycle_state == StreamLifecycleState.CLOSED
    print(
        f"EXACT {strategy.value}/{label}=cap_rows:2,rows:{result.rows_emitted},"
        f"window_readback:{','.join(observed)},cursor:{cursor.watermark_value},closed"
    )


def verify_utf8_json_byte_cap() -> None:
    dataset_id = "utf8-json-byte-cap"
    rows: list[dict[str, Any]] = [
        {
            "_message_id": "m0",
            "event_time": (START + timedelta(seconds=0)).isoformat(),
            "value": 'quote " slash \\ newline\n snowman ☃',
        },
        {
            "_message_id": "m1",
            "event_time": (START + timedelta(seconds=1)).isoformat(),
            "value": {"z": [1, True, None], "a": "café"},
        },
        {
            "_message_id": "m2",
            "event_time": (START + timedelta(seconds=2)).isoformat(),
            "value": ["overshoot", "🧭"],
        },
        {
            "_message_id": "m3",
            "event_time": (START + timedelta(seconds=3)).isoformat(),
            "value": "unreached",
        },
    ]
    sizes = [len(json.dumps(row, sort_keys=True, default=str).encode("utf-8")) for row in rows]
    assert sizes == [119, 115, 104, 86], sizes
    exact_cap = sizes[0] + sizes[1]
    run_root = RUNS / dataset_id
    registry, store, cursor_store = configure_source(run_root, dataset_id, rows)
    try:
        asyncio.run(
            stream(
                dataset_id=dataset_id,
                registry=registry,
                store=store,
                cursor_store=cursor_store,
                options=runtime_options(
                    strategy=BackpressureStrategy.PAUSE,
                    max_rows=10,
                    max_bytes=exact_cap,
                    window_policy=session_policy(),
                ),
            )
        )
    except RuntimeError as exc:
        assert "capacity" in str(exc), str(exc)
        print(f"BYTE_CAP pause=refused exact_json_bytes:{exact_cap} row_sizes:{sizes}")
    else:
        raise AssertionError("UTF-8 JSON byte cap admitted the oversized third retained row")

    _cursor, paused = assert_frontier(cursor_store, dataset_id, expected_offset=0)
    retained = paused.metadata["operator_state"]["accumulator"]["session_rows"]
    assert [entry["row"]["_message_id"] for entry in retained] == ["m0", "m1"]
    retained_bytes = sum(
        len(json.dumps(entry["row"], sort_keys=True, default=str).encode("utf-8"))
        for entry in retained
    )
    assert retained_bytes == exact_cap
    chunks = stream_chunks(store)
    assert set(chunks) == {0}
    chunk_ref = chunks[0][0]
    assert [entry["refs"] for entry in retained] == [[chunk_ref], [chunk_ref]]

    ConnectorRegistry.reset_instance()
    retry_registry = ConnectorRegistry.get_instance()
    retry_registry.set_default_config(
        CONNECTOR_ID,
        ConnectionConfig(
            url=(run_root / f"{dataset_id}.jsonl").as_uri(),
            headers={"X-Stream-ChunkSize": "2"},
        ),
    )
    result = asyncio.run(
        stream(
            dataset_id=dataset_id,
            registry=retry_registry,
            store=store,
            cursor_store=cursor_store,
            options=runtime_options(
                strategy=BackpressureStrategy.PAUSE,
                max_rows=10,
                max_bytes=10_000,
                window_policy=session_policy(),
            ),
        )
    )
    observed = emitted_ids(store, result)
    assert Counter(observed) == Counter(row["_message_id"] for row in rows)
    _cursor, final_checkpoint = assert_frontier(cursor_store, dataset_id, expected_offset=1)
    assert final_checkpoint.lifecycle_state == StreamLifecycleState.CLOSED
    print(
        f"BYTE_RESTART exact_cap:{exact_cap},retained_readback_bytes:{retained_bytes},"
        f"emitted:{','.join(observed)},cursor_offset:1,closed"
    )


def main() -> None:
    RUNS.mkdir(exist_ok=True)
    report_modules()
    print("STRATEGIES " + ",".join(strategy.value for strategy in EXPECTED_STRATEGIES))
    for strategy in EXPECTED_STRATEGIES:
        verify_overflow_restart(strategy)
    for strategy in EXPECTED_STRATEGIES:
        verify_exact_closing(strategy, session_policy(), "session")
        verify_exact_closing(strategy, count_policy(), "count")
        verify_exact_closing(strategy, tumbling_policy(), "tumbling")
    verify_utf8_json_byte_cap()
    print("RESULT PASS installed-wheel JSONL -> process_stream_dataset -> CAS/CursorStore")


if __name__ == "__main__":
    main()
