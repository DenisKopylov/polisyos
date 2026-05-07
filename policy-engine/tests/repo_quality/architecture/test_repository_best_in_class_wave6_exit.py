from __future__ import annotations

import datetime as dt
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]

REQUIRED_WAVE6_GATES = {
    "phase6.1.package-import-gates",
    "phase6.2.directory-health",
    "phase6.2.test-ratchets",
    "phase6.3.operability-release-gates",
    "phase6.4.docs-lifecycle",
    "phase6.4.extension-examples",
    "phase6.5.exception-sunset-cleanup",
}


def test_wave6_exit_criteria_have_two_green_runs_or_owner_exception() -> None:
    payload = _read_toml("architecture/wave6_gate_green_runs.toml")
    header = payload["wave6_gate_green_runs"]
    gates = {gate["id"]: gate for gate in payload["gate"]}
    today = dt.date.today()

    assert header["status"] == "completed"
    assert header["wave"] == "6"
    assert header["completed_on"] <= today
    assert header["active_source_move_report_only_blockers"] == []
    assert REQUIRED_WAVE6_GATES <= set(gates)

    for gate_id, gate in gates.items():
        assert gate["owner"].startswith("team-"), gate_id
        assert gate["command"], gate_id
        assert gate["status"] in {"two_consecutive_green_runs", "owner_date_exception"}, gate_id
        if gate["status"] == "two_consecutive_green_runs":
            green_runs = gate.get("green_run", [])
            assert len(green_runs) >= 2, gate_id
            assert [run["sequence"] for run in green_runs[:2]] == [1, 2], gate_id
            assert all(run["result"] == "passed" for run in green_runs[:2]), gate_id
            assert all(_path_exists(run["evidence"]) for run in green_runs[:2]), gate_id
        else:
            exception = gate["exception"]
            assert exception["owner"].startswith("team-"), gate_id
            assert exception["reason"], gate_id
            assert dt.date.fromisoformat(str(exception["expires"])) >= today, gate_id


def _read_toml(path: str) -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


def _path_exists(path: str) -> bool:
    return (REPO_ROOT / path).exists()
