"""Forty-one-row window recovery across actual OS process death.

These finite, synthetic JSONL fixtures qualify the supported file-token profile,
not an external connector's delivery guarantees. Stage-specific fault and
compensation coverage remains in ``test_e02_c_streaming_oracle.py``.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.cursor import StreamLifecycleState, WindowStrategy
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.contracts.source_contract import (
    SourceContract,
    SourceProgressContract,
)
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.streaming import (
    StreamingSourceSession,
    StreamRuntimeOptions,
    StreamWindowAccumulator,
    process_stream_dataset,
    read_stream_window,
)
from polisyos.fabric.data_plane.watermark import WindowPolicy
from polisyos.fabric.ingestion.source_progress import FiniteSourceProgressReader
from tests._helpers.source_progress import finite_source_reader

_ROW_COUNT = 41
_INTERRUPTION = 19
_DATASET = "native-crash-41"
_ORIGIN = datetime(2026, 1, 1, tzinfo=UTC)
_WORKER_TIMEOUT = 90


def _rows(strategy: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(_ROW_COUNT):
        row: dict[str, Any] = {"event_id": f"e{index:02d}", "source_version": 1, "value": index}
        if strategy == "tumbling":
            row["event_time"] = (_ORIGIN + timedelta(seconds=index * 2)).isoformat()
        elif strategy == "session":
            # Seven one-second events per session, separated by an actual gap.
            row["event_time"] = (_ORIGIN + timedelta(seconds=index + (index // 7) * 20)).isoformat()
        rows.append(row)
    return rows


def _policy(strategy: str) -> WindowPolicy:
    if strategy == "count":
        return WindowPolicy(strategy=WindowStrategy.COUNT, size=7)
    if strategy == "sliding":
        return WindowPolicy(strategy=WindowStrategy.SLIDING, size=7, slide=3)
    if strategy == "tumbling":
        return WindowPolicy(strategy=WindowStrategy.TUMBLING, size=14)
    if strategy == "session":
        return WindowPolicy(strategy=WindowStrategy.SESSION, size=10, session_gap_seconds=10)
    raise AssertionError(strategy)


def _expected_windows(strategy: str) -> list[dict[str, Any]]:
    """Calculate this declared fixture's groups without a production windower."""
    rows = _rows(strategy)
    groups = (
        [rows[start : start + 7] for start in range(0, _ROW_COUNT - 6, 3)]
        if strategy == "sliding"
        else [rows[start : start + 7] for start in range(0, _ROW_COUNT, 7)]
    )
    expected = []
    for ordinal, group in enumerate(groups):
        start_at = end_at = None
        if strategy == "tumbling":
            start_at = (_ORIGIN + timedelta(seconds=ordinal * 14)).isoformat()
            end_at = (_ORIGIN + timedelta(seconds=(ordinal + 1) * 14)).isoformat()
        elif strategy == "session":
            start_at, end_at = group[0]["event_time"], group[-1]["event_time"]
        expected.append(
            {
                "ordinal": ordinal,
                "strategy": strategy,
                "start_at": start_at,
                "end_at": end_at,
                "data": group,
                "row_count": len(group),
            }
        )
    return expected


def _selected_manifest_ref(store: FileSystemCAS, artifact_id: Any) -> ArtifactRef:
    """Select the persisted view in this fixture's single-view-per-output CAS."""
    manifest = store.get_manifest(artifact_id)
    return ArtifactRef(
        artifact_id=manifest.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=ManifestLifecycle.profile_sha256(manifest),
    )


def _fresh_outputs(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Use fresh selected consumers and reconcile all concrete contributor refs."""
    store = FileSystemCAS(root / "cas")
    chunks: list[tuple[int, list[dict[str, Any]]]] = []
    windows: list[dict[str, Any]] = []
    for artifact_id in store.iter_artifact_ids():
        manifest = store.get_manifest(artifact_id)
        if manifest.kind == "fabric.stream_chunk":
            ref = _selected_manifest_ref(store, artifact_id)
            assert store.verify(ref).ok
            payload = from_canonical_bytes(store.get_bytes(ref))
            if payload["dataset_id"] == _DATASET:
                chunks.append((payload["chunk_index"], payload["data"]))
        elif manifest.kind == "fabric.stream_window":
            selected = _selected_manifest_ref(store, artifact_id)
            payload = read_stream_window(store, selected)
            if payload["dataset_id"] != _DATASET:
                continue
            contributors = [
                ArtifactRef.model_validate(value)
                for value in payload["lineage"]["selected_contributor_chunk_refs"]
            ]
            assert all(ref.manifest_profile_sha256 is not None for ref in contributors)
            contributor_rows = []
            for ref in contributors:
                contributor_rows.extend(from_canonical_bytes(store.get_bytes(ref))["data"])
            assert contributor_rows == payload["data"]
            edges = {
                (str(edge.artifact_id), edge.manifest_profile_sha256)
                for edge in store.get_manifest(selected).inputs
                if edge.role == "stream_chunk"
            }
            assert edges == {
                (str(ref.artifact_id), ref.manifest_profile_sha256) for ref in contributors
            }
            windows.append(
                {name: payload[name] for name in _expected_windows(payload["strategy"])[0]}
            )
    chunks.sort(key=lambda item: item[0])
    assert [index for index, _ in chunks] == list(range(len(chunks)))
    windows.sort(key=lambda value: (value["ordinal"], value["data"][0]["value"]))
    return [row for _index, batch in chunks for row in batch], windows


def _prepare(root: Path, strategy: str) -> dict[str, Any]:
    root.mkdir()
    stream_path = root / "stream.jsonl"
    rows = _rows(strategy)
    stream_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    owner = finite_source_reader(
        root / "owner",
        connector_id="stream.jsonl",
        dataset_id=_DATASET,
        schema_id="fixture.native_crash_41",
        snapshots=[("fixture-current", rows)],
        transport_path=stream_path,
    )
    return {
        "root": str(root),
        "strategy": strategy,
        "source_root": str(owner.source_root),
        "source_contract": owner.source_contract.model_dump(mode="json", by_alias=True),
        "extension": owner.extension.model_dump(mode="json"),
    }


def _child_env() -> dict[str, str]:
    product = Path(__file__).resolve().parents[4]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        (str(product / "src"), str(product), env.get("PYTHONPATH", ""))
    )
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        env[name] = "1"
    env["JAX_PLATFORMS"] = "cpu"
    return env


def _run_worker(config: dict[str, Any], *, pause: bool = False) -> dict[str, Any]:
    root = Path(config["root"])
    phase = "interrupted" if pause else "completed"
    if config.get("remove_restore"):
        phase = "removed-restore"
    config = {**config, "pause": pause}
    config_path = root / f"{phase}.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    argv = [sys.executable, str(Path(__file__).resolve()), str(config_path)]
    with (
        (root / f"{phase}.stdout.txt").open("w", encoding="utf-8") as stdout,
        (root / f"{phase}.stderr.txt").open("w", encoding="utf-8") as stderr,
        subprocess.Popen(argv, env=_child_env(), stdout=stdout, stderr=stderr) as child,
    ):
        try:
            if pause:
                marker = root / "ready.json"
                deadline = time.monotonic() + _WORKER_TIMEOUT
                while not marker.exists():
                    assert child.poll() is None, (root / f"{phase}.stderr.txt").read_text()
                    assert time.monotonic() < deadline, "child did not reach committed row19"
                    time.sleep(0.01)
                ready = json.loads(marker.read_text())
                assert ready["pid"] == child.pid
                _assert_paused_frontier(root, config["strategy"])
                # SIGKILL cannot enter Python Exception/BaseException/finally cleanup.
                child.kill()
                assert child.wait(timeout=10) == -signal.SIGKILL
                return ready
            assert child.wait(timeout=_WORKER_TIMEOUT) == 0, (
                (root / f"{phase}.stdout.txt").read_text(),
                (root / f"{phase}.stderr.txt").read_text(),
            )
            return json.loads((root / "result.json").read_text())
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)


def _assert_paused_frontier(root: Path, strategy: str) -> None:
    cursors = CursorStore(FileSystemCAS(root / "cas"))
    checkpoint = cursors.find_latest_stream_checkpoint("stream.jsonl", _DATASET)
    cursor = cursors.find_latest_cursor("stream.jsonl", _DATASET)
    assert checkpoint is not None and cursor is not None
    assert checkpoint.offset == _INTERRUPTION - 1
    assert cursor.watermark_value == str(_INTERRUPTION - 1)
    assert checkpoint.metadata["frontier_committed"] is True
    assert checkpoint.metadata["frontier_intent"]["state"] == "committed"
    assert checkpoint.metadata["rows_emitted"] == _INTERRUPTION
    accumulator = checkpoint.metadata["operator_state"]["accumulator"]
    assert accumulator["version"] == 1
    assert accumulator["policy"]["strategy"] == strategy
    assert accumulator["ordinal"] == (5 if strategy == "sliding" else 2)
    pending_field = {
        "count": "count_buffer",
        "tumbling": "bucket_rows",
        "session": "session_rows",
        "sliding": "sliding_rows",
    }[strategy]
    pending = accumulator[pending_field]
    expected_indices = list(range(12, 19)) if strategy == "sliding" else list(range(14, 19))
    assert [entry["row"]["value"] for entry in pending] == expected_indices
    assert all(
        ArtifactRef.model_validate(ref).manifest_profile_sha256 is not None
        for entry in pending
        for ref in entry["refs"]
    )
    assert len(checkpoint.metadata["dedupe_horizon"]["entries"]) == _INTERRUPTION
    rows, windows = _fresh_outputs(root)
    assert rows == _rows(strategy)[:_INTERRUPTION]
    # Process death must not flush the unfinished window.
    completed = 5 if strategy == "sliding" else 2
    assert windows == _expected_windows(strategy)[:completed]


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX SIGKILL process semantics")
@pytest.mark.parametrize("strategy", ["count", "session", "sliding", "tumbling"])
def test_41_rows_resume_after_sigkill_at_committed_row19(tmp_path: Path, strategy: str) -> None:
    """Continuous and killed/reopened runs preserve exact windows and selected inputs."""
    baseline_root, interrupted_root = tmp_path / "continuous", tmp_path / "interrupted"
    baseline = _run_worker(_prepare(baseline_root, strategy))
    config = _prepare(interrupted_root, strategy)
    killed = _run_worker(config, pause=True)
    resumed = _run_worker(config)
    assert len({baseline["pid"], killed["pid"], resumed["pid"]}) == 3
    assert resumed["rows_emitted"] == _ROW_COUNT - _INTERRUPTION
    assert resumed["dedupe_dropped"] == 0
    assert baseline["guarantee"] == resumed["guarantee"] == "replay_only"
    expected = (_rows(strategy), _expected_windows(strategy))
    assert _fresh_outputs(baseline_root) == expected
    assert _fresh_outputs(interrupted_root) == expected
    checkpoint = CursorStore(FileSystemCAS(interrupted_root / "cas")).find_latest_stream_checkpoint(
        "stream.jsonl", _DATASET
    )
    assert checkpoint is not None
    assert checkpoint.lifecycle_state == StreamLifecycleState.CLOSED
    assert checkpoint.offset == _ROW_COUNT - 1


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX SIGKILL process semantics")
def test_missing_operator_restore_breaks_41_row_recovery_oracle(tmp_path: Path) -> None:
    """Keep commits/dedupe/row count intact while removing pending-window restoration."""
    root = tmp_path / "removed"
    config = _prepare(root, "count")
    _run_worker(config, pause=True)
    result = _run_worker({**config, "remove_restore": True})
    assert result["rows_emitted"] == _ROW_COUNT - _INTERRUPTION
    raw_rows, windows = _fresh_outputs(root)
    assert raw_rows == _rows("count")
    with pytest.raises(AssertionError):
        assert windows == _expected_windows("count")
    assert not any(row["value"] == 14 for window in windows for row in window["data"])


async def _worker(config: dict[str, Any]) -> None:
    root = Path(config["root"])
    owner = FiniteSourceProgressReader(
        Path(config["source_root"]),
        SourceContract.model_validate(config["source_contract"]),
        SourceProgressContract.model_validate(config["extension"]),
    )
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(url=(root / "stream.jsonl").as_uri(), headers={"X-Stream-ChunkSize": "1"}),
    )
    if config.get("pause"):
        original_poll = StreamingSourceSession.poll
        polls = 0

        async def poll_until_committed_row19(session: StreamingSourceSession):
            nonlocal polls
            if polls == _INTERRUPTION:
                _assert_paused_frontier(root, config["strategy"])
                temporary = root / "ready.tmp"
                temporary.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
                temporary.replace(root / "ready.json")
                await asyncio.Event().wait()
                raise AssertionError("paused worker must be terminated by the parent")
            polls += 1
            return await original_poll(session)

        StreamingSourceSession.poll = poll_until_committed_row19
    if config.get("remove_restore"):

        def removed_restore(self: StreamWindowAccumulator, state: dict[str, Any]) -> None:
            del self, state

        StreamWindowAccumulator.restore = removed_restore

    def valid_rows(batch: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], list[str], int]:
        del kwargs
        return [dict(row) for row in batch], [], 0

    store = FileSystemCAS(root / "cas")
    try:
        result = await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id=_DATASET,
            store=store,
            cursor_store=CursorStore(store),
            sanitize_rows=valid_rows,
            runtime_options=StreamRuntimeOptions(
                batch_size=1,
                checkpoint_every_chunks=1,
                max_dedupe_keys=64,
                max_buffered_rows=64,
                max_buffered_bytes=100_000,
                ingestion_clock=lambda: _ORIGIN + timedelta(days=1),
                window_policy=_policy(config["strategy"]),
            ),
            registry=registry,
            source_progress_readers=(owner,),
        )
    finally:
        await registry.shutdown_async()
    (root / "result.json").write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "rows_emitted": result.rows_emitted,
                "dedupe_dropped": result.dedupe_dropped,
                "guarantee": result.processing_guarantee,
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    asyncio.run(_worker(json.loads(Path(sys.argv[1]).read_text())))
