from __future__ import annotations

import json

from tools.workspace import core_runtime_long_soak


def test_core_runtime_long_soak_writes_machine_readable_outputs(tmp_path) -> None:
    summary = tmp_path / "core-runtime-long-soak.md"
    payload = tmp_path / "core-runtime-long-soak.json"

    exit_code = core_runtime_long_soak.main(
        [
            "--iterations-run-index",
            "8",
            "--iterations-timeline",
            "8",
            "--iterations-async-cas",
            "8",
            "--iterations-checkpoint",
            "8",
            "--iterations-cursor-store",
            "8",
            "--sample-every",
            "4",
            "--summary",
            str(summary),
            "--json-output",
            str(payload),
        ]
    )

    assert exit_code == 0
    assert summary.exists()
    assert payload.exists()

    rendered = summary.read_text(encoding="utf-8")
    assert "Core Runtime Long Soak" in rendered
    assert "run_index_incremental_refresh" in rendered

    report = json.loads(payload.read_text(encoding="utf-8"))
    assert report["failures"] == []
    assert {item["scenario_id"] for item in report["reports"]} == {
        "run_index_incremental_refresh",
        "timeline_build_loops",
        "async_cas_round_trip",
        "async_checkpoint_restore",
        "async_cursor_store_stream_progress",
    }
