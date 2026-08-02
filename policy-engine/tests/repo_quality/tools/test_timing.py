from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

from tools.lib.timing import ToolRunRecord, summarize_timing_records

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATION_ROOT = REPO_ROOT / "tools" / "quality" / "validation"
TIMED_SUITE_RUNNER = REPO_ROOT / "tools" / "quality" / "testing" / "run_timed_suite.py"


def _run_direct_guard(path: Path, *args: str, timing_log: Path) -> subprocess.CompletedProcess[str]:
    """Run a direct guard with an isolated real timing log."""

    environment = os.environ.copy()
    environment["POLISYOS_TOOLS_TIMING_LOG"] = str(timing_log)
    return subprocess.run(  # noqa: S603 - trusted repository-local validator subprocess.
        [sys.executable, str(path), *args],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def _records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_direct_gy_guard_persists_default_mode_without_changing_success_output(tmp_path: Path) -> None:
    """Catch a direct-entry timing-wrapper bypass for a successful no-flag guard."""

    timing_log = tmp_path / "timing.jsonl"
    result = _run_direct_guard(
        VALIDATION_ROOT / "check_layer3_gy_p0_coverage_audit.py",
        timing_log=timing_log,
    )

    assert result.returncode == 0
    assert result.stdout == "PASS\n"
    assert result.stderr == ""
    records = _records(timing_log)
    assert len(records) == 1
    assert records[0]["tool"] == "quality.validation.check_layer3_gy_p0_coverage_audit"
    assert records[0]["mode"] == "default"
    assert records[0]["status"] == "ok"
    assert records[0]["exit_code"] == 0


def test_direct_gy_guard_persists_action_mode_for_successful_json_run(tmp_path: Path) -> None:
    """Catch a wrapper that records a mode other than the direct action flag."""

    timing_log = tmp_path / "timing.jsonl"
    result = _run_direct_guard(
        VALIDATION_ROOT / "check_layer3_gy_p0_coverage_audit.py",
        "--json",
        timing_log=timing_log,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "pass"
    records = _records(timing_log)
    assert len(records) == 1
    assert records[0]["mode"] == "json"
    assert records[0]["status"] == "ok"
    assert records[0]["exit_code"] == 0


def test_direct_gy_guard_persists_expected_nonzero_exception_result(tmp_path: Path) -> None:
    """Catch a wrapper that changes a direct guard's exception exit code or output."""

    timing_log = tmp_path / "timing.jsonl"
    missing_audit = tmp_path / "missing.json"
    result = _run_direct_guard(
        VALIDATION_ROOT / "check_layer3_gy_p0_coverage_audit.py",
        "--audit",
        str(missing_audit),
        timing_log=timing_log,
    )

    assert result.returncode == 1
    assert "FileNotFoundError" in result.stderr
    records = _records(timing_log)
    assert len(records) == 1
    assert records[0]["mode"] == "audit"
    assert records[0]["status"] == "failed"
    assert records[0]["exit_code"] == 1


def test_every_direct_gy_guard_routes_through_the_shared_timing_entrypoint() -> None:
    """Catch a sibling direct guard that bypasses the structural timing chokepoint."""

    guard_paths = sorted(VALIDATION_ROOT.glob("check_layer3_gy_*.py"))
    unwrapped: list[str] = []
    for path in guard_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        wrapper_bindings = {
            imported.asname or imported.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "tools.lib.timing"
            for imported in node.names
            if imported.name == "run_timed_entrypoint"
        }
        if not wrapper_bindings:
            unwrapped.append(f"{path.name}:missing_canonical_wrapper_import")
            continue
        main_guards = [
            node
            for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ]
        assert len(main_guards) == 1, path
        calls = [
            node
            for node in ast.walk(main_guards[0])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in wrapper_bindings
        ]
        if len(calls) != 1:
            unwrapped.append(f"{path.name}:missing_canonical_wrapper_call")

    assert guard_paths
    assert unwrapped == []


def test_timing_summary_keeps_all_modes_in_one_tool_denominator() -> None:
    """Catch summaries that redefine a tool's counts and percentiles by splitting its modes."""

    summaries = summarize_timing_records(
        [
            ToolRunRecord(
                tool="quality.validation.example",
                category="quality",
                output_format="text",
                status="ok",
                preflight_status="ok",
                started_at="2026-08-02T10:00:00+00:00",
                duration_ms=100.0,
                exit_code=0,
                mode="check",
            ),
            ToolRunRecord(
                tool="quality.validation.example",
                category="quality",
                output_format="text",
                status="failed",
                preflight_status="ok",
                started_at="2026-08-02T10:01:00+00:00",
                duration_ms=300.0,
                exit_code=1,
                mode="write",
            ),
        ],
        budgets_ms={"quality.validation.example": 250.0},
    )

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.runs == 2
    assert summary.failures == 1
    assert summary.average_duration_ms == 200.0
    assert summary.p95_duration_ms == 300.0
    assert summary.over_budget_runs == 1
    assert summary.latest_mode == "write"


def test_external_suite_runner_preserves_child_streams_and_nonzero_exit(tmp_path: Path) -> None:
    """Catch an external runner that changes child semantics or skips timing persistence."""

    timing_log = tmp_path / "timing.jsonl"
    environment = os.environ.copy()
    environment["POLISYOS_TOOLS_TIMING_LOG"] = str(timing_log)
    result = subprocess.run(  # noqa: S603 - trusted local runner and interpreter fixture.
        [
            sys.executable,
            str(TIMED_SUITE_RUNNER),
            "--lane",
            "tests.external.failure",
            "--",
            sys.executable,
            "-c",
            "import sys; print('child-out'); print('child-err', file=sys.stderr); raise SystemExit(7)",
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 7
    assert result.stdout == "child-out\n"
    assert result.stderr == "child-err\n"
    records = _records(timing_log)
    assert len(records) == 1
    assert records[0]["tool"] == "tests.external.failure"
    assert records[0]["mode"] == "default"
    assert records[0]["status"] == "failed"
    assert records[0]["exit_code"] == 7
