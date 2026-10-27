"""Two actual OS processes reopen the real UTC key horizon and owner witness."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tests._helpers.source_progress import finite_source_reader

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.data_plane.cursor_store import CursorStore


def test_b83_two_os_processes_reopen_horizon_at_86399_and_86400(tmp_path: Path) -> None:
    """Explicit injected UTC proves replay semantics, not elapsed wall time."""
    event = {"event_id": "same-event", "source_version": "1"}
    reader = finite_source_reader(
        tmp_path / "owner",
        connector_id="stream.jsonl",
        dataset_id="horizon",
        schema_id="fixture.horizon",
        snapshots=[("source-current", [event])],
        transport_path=tmp_path / "stream.jsonl",
    )
    (tmp_path / "stream.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
    at = datetime(2026, 1, 1, tzinfo=UTC)
    common = {
        "root": str(tmp_path),
        "source_root": str(reader.source_root),
        "event": event,
        "source_contract": reader.source_contract.model_dump(mode="json", by_alias=True),
        "extension": reader.extension.model_dump(mode="json"),
    }

    def worker(name: str, steps: list[dict[str, object]]) -> dict:
        config = tmp_path / f"{name}.json"
        config.write_text(json.dumps({**common, "steps": steps}), encoding="utf-8")
        product_root = Path(__file__).resolve().parents[4]
        child_env = dict(os.environ)
        child_env["PYTHONPATH"] = os.pathsep.join(
            [str(product_root / "src"), str(product_root), child_env.get("PYTHONPATH", "")]
        )
        completed = subprocess.run(
            [sys.executable, "-m", "tests._helpers.source_progress_stream_worker", str(config)],
            check=False,
            env=child_env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        (tmp_path / f"{name}.stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (tmp_path / f"{name}.stderr.txt").write_text(completed.stderr, encoding="utf-8")
        assert completed.returncode == 0, (completed.returncode, completed.stdout, completed.stderr)
        return json.loads(completed.stdout.splitlines()[-1])

    first = worker("first", [{"at": at.isoformat(), "append": False}])
    second = worker(
        "second",
        [
            {"at": (at + timedelta(seconds=86_399)).isoformat(), "append": True},
            {"at": (at + timedelta(seconds=86_400)).isoformat(), "append": True},
        ],
    )
    assert first["pid"] != second["pid"]
    assert first["clock_profile"] == second["clock_profile"] == "fixture_utc"
    assert [(row["rows_emitted"], row["dedupe_dropped"]) for row in first["results"]] == [(1, 0)]
    assert [(row["rows_emitted"], row["dedupe_dropped"]) for row in second["results"]] == [
        (0, 1),
        (1, 0),
    ]
    assert all(row["guarantee"] == "replay_only" for row in first["results"] + second["results"])

    # Independent oracle: first acceptance is preserved before expiry and is
    # replaced exactly at t+86400; no production key/eviction helper is called.
    reopened = CursorStore(FileSystemCAS(tmp_path / "cas"))
    checkpoint = reopened.find_latest_stream_checkpoint("stream.jsonl", "horizon")
    assert checkpoint is not None
    entries = checkpoint.metadata["dedupe_horizon"]["entries"]
    observed = {
        tuple((field, value) for field, value in json.loads(key)): datetime.fromisoformat(value)
        for key, value in entries.items()
    }
    assert observed == {
        (("event_id", "same-event"), ("source_version", "1")): at + timedelta(seconds=86_400)
    }
    print(json.dumps({"first": first, "second": second, "scope": "replay_clock_semantics"}))
