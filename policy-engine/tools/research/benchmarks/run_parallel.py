#!/usr/bin/env python3
"""Parallel benchmark runner with worker and memory-aware scheduling."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.imports import repo_root_from

REPO = repo_root_from(__file__)
SRC = REPO / "src"
BENCH_DIR = REPO / "benchmarks"
REPORTS = BENCH_DIR / "_reports"
REPORTS.mkdir(exist_ok=True)

_cpu = os.cpu_count() or 4
MAX_WORKERS = int(os.environ.get("BENCH_WORKERS", str(max(2, _cpu - 2))))
MODE = os.environ.get("BENCH_MODE", "smoke")
RUN_ID = os.environ.get(
    "BENCH_RUN_ID",
    f"parallel-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
)

sys.path.insert(0, str(SRC))
sys.path.insert(0, str(REPO))

from benchmarks.reporting import suite_overall_status_from_payload
from benchmarks.suite_registry import filtered_suite_specs


@dataclass(frozen=True)
class SuiteJob:
    suite_id: str
    label: str
    script: str
    memory_gib_hint: float


@dataclass
class RunningSuite:
    job: SuiteJob
    process: subprocess.Popen[str]
    started_at: float
    json_file: Path
    log_file: Path


def _system_memory_gib() -> int:
    if "BENCH_MEMORY_BUDGET_GIB" in os.environ:
        return max(1, int(float(os.environ["BENCH_MEMORY_BUDGET_GIB"])))
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        total_bytes = int(page_size) * int(pages)
        return max(1, int((total_bytes / (1024**3)) * 0.8))
    except (AttributeError, ValueError, OSError):
        return max(4, MAX_WORKERS * 2)


MEMORY_BUDGET_GIB = _system_memory_gib()


def _parse_suites() -> list[SuiteJob]:
    profile = os.environ.get("BENCH_PROFILE") or None
    contour = os.environ.get("BENCH_CONTOUR") or None
    visibility = os.environ.get("BENCH_VISIBILITY") or None
    specs = filtered_suite_specs(
        profile=profile,
        validation_contour=contour,
        visibility=visibility,
    )
    ordered = sorted(
        specs,
        key=lambda spec: (-float(spec.memory_gib_hint), spec.suite_id),
    )
    return [
        SuiteJob(
            suite_id=spec.suite_id,
            label=spec.label,
            script=str(spec.script_path),
            memory_gib_hint=float(spec.memory_gib_hint),
        )
        for spec in ordered
    ]


def _suite_env() -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONPATH": f"{SRC}:{REPO}:{os.environ.get('PYTHONPATH', '')}",
        "BENCH_MODE": MODE,
        "BENCH_RUN_ID": RUN_ID,
    }


def _launch_suite(job: SuiteJob) -> RunningSuite:
    json_file = REPORTS / f"{job.suite_id}.json"
    log_file = REPORTS / f".{job.suite_id}.log"
    if json_file.exists():
        json_file.unlink()
    if log_file.exists():
        log_file.unlink()
    process = subprocess.Popen(
        [sys.executable, job.script, "--mode", MODE, "--json", str(json_file)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_suite_env(),
    )
    return RunningSuite(
        job=job,
        process=process,
        started_at=time.monotonic(),
        json_file=json_file,
        log_file=log_file,
    )


def _write_log(path: Path, stdout: str, stderr: str) -> None:
    path.write_text(
        stdout + (("\n--- STDERR ---\n" + stderr) if stderr else ""),
        encoding="utf-8",
    )


def _suite_status_from_artifacts(
    json_file: Path, exit_code: int
) -> tuple[str, dict[str, Any] | None]:
    if not json_file.exists():
        return ("passed" if exit_code == 0 else "error"), None
    try:
        payload = json.loads(json_file.read_text(encoding="utf-8"))
    except Exception:
        return ("passed" if exit_code == 0 else "error"), None
    if not isinstance(payload, dict):
        return ("passed" if exit_code == 0 else "error"), None
    return suite_overall_status_from_payload(payload), payload


def _finalize_suite(running: RunningSuite) -> dict[str, Any]:
    stdout, stderr = running.process.communicate()
    _write_log(running.log_file, stdout, stderr)
    elapsed = round(time.monotonic() - running.started_at, 1)
    status, payload = _suite_status_from_artifacts(running.json_file, running.process.returncode)
    counts = {
        "n_total": payload.get("n_total", 0) if payload else 0,
        "n_passed": payload.get("n_passed", 0) if payload else 0,
        "n_failed": payload.get("n_failed", 0) if payload else 0,
        "n_errors": payload.get("n_errors", 0) if payload else 0,
        "n_skipped": payload.get("n_skipped", 0) if payload else 0,
        "n_over_budget": payload.get("n_over_budget", 0) if payload else 0,
    }
    return {
        "suite_id": running.job.suite_id,
        "label": running.job.label,
        "status": status,
        "exit_code": int(running.process.returncode or 0),
        "elapsed_s": elapsed,
        "report_exists": running.json_file.exists(),
        "report_path": str(running.json_file),
        "log_path": str(running.log_file),
        "memory_gib_hint": running.job.memory_gib_hint,
        **counts,
    }


def _status_tag(status: str) -> str:
    return {
        "passed": "PASS",
        "over_budget": "BUDGET",
        "skipped": "SKIP",
        "failed": "FAIL",
        "error": "ERROR",
    }.get(status, status.upper())


def _can_launch(job: SuiteJob, *, running: dict[str, RunningSuite]) -> bool:
    if len(running) >= MAX_WORKERS:
        return False
    used_memory = sum(item.job.memory_gib_hint for item in running.values())
    if not running:
        return True
    return used_memory + job.memory_gib_hint <= MEMORY_BUDGET_GIB


def _pick_launchable_job(
    pending: deque[SuiteJob], *, running: dict[str, RunningSuite]
) -> SuiteJob | None:
    for _ in range(len(pending)):
        job = pending[0]
        if _can_launch(job, running=running):
            return pending.popleft()
        pending.rotate(-1)
    return None


def main() -> int:
    suites = _parse_suites()
    if not suites:
        print(
            "No suites matched the current filter. Check BENCH_PROFILE / BENCH_CONTOUR / BENCH_VISIBILITY."
        )
        return 1

    print(f"=== Parallel benchmark run: {len(suites)} suites, {MAX_WORKERS} workers ===")
    print(f"    Run ID        : {RUN_ID}")
    print(f"    Mode          : {MODE}")
    print(f"    Python        : {sys.executable}")
    print(f"    Reports       : {REPORTS}")
    print(f"    Memory budget : {MEMORY_BUDGET_GIB} GiB")
    print("    Timeout mode  : informational only")
    print(flush=True)

    pending: deque[SuiteJob] = deque(suites)
    running: dict[str, RunningSuite] = {}
    results: list[dict[str, Any]] = []
    started = time.monotonic()

    while pending or running:
        launched = False
        while pending:
            job = _pick_launchable_job(pending, running=running)
            if job is None:
                break
            running[job.suite_id] = _launch_suite(job)
            launched = True
            print(
                f"  [RUN ] {job.suite_id:50} hint={job.memory_gib_hint:>4.1f}GiB"
                f" active={len(running):>2}/{MAX_WORKERS}",
                flush=True,
            )

        completed_ids: list[str] = []
        for suite_id, item in running.items():
            if item.process.poll() is None:
                continue
            result = _finalize_suite(item)
            results.append(result)
            completed_ids.append(suite_id)
            print(
                f"  [{_status_tag(result['status'])}] {result['suite_id']:50}"
                f" {result['elapsed_s']:7.1f}s  {result['status']}",
                flush=True,
            )
        for suite_id in completed_ids:
            running.pop(suite_id, None)

        if running and not launched and not completed_ids:
            time.sleep(1.0)

    wall = round(time.monotonic() - started, 1)
    by_status = {
        key: sum(1 for item in results if item["status"] == key)
        for key in ("passed", "over_budget", "skipped", "failed", "error")
    }
    blocking = by_status["failed"] + by_status["error"]
    summary = {
        "run_id": RUN_ID,
        "mode": MODE,
        "workers": MAX_WORKERS,
        "memory_budget_gib": MEMORY_BUDGET_GIB,
        "n_total": len(results),
        "n_passed": by_status["passed"],
        "n_over_budget": by_status["over_budget"],
        "n_skipped": by_status["skipped"],
        "n_failed": by_status["failed"],
        "n_errors": by_status["error"],
        "n_blocking": blocking,
        "pass_rate": round(by_status["passed"] / len(results), 4) if results else 0.0,
        "wall_time_s": wall,
        "timestamp": datetime.now(UTC).isoformat(),
        "suite_results": sorted(results, key=lambda item: item["elapsed_s"]),
    }
    (REPORTS / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    sep = "=" * 72
    print(f"\n{sep}")
    print(f"  DONE in {wall:.0f}s wall time ({MAX_WORKERS} workers)")
    print(f"  Passed     : {by_status['passed']}")
    print(f"  Over budget: {by_status['over_budget']}")
    print(f"  Skipped    : {by_status['skipped']}")
    print(f"  Failed     : {by_status['failed']}")
    print(f"  Errors     : {by_status['error']}")
    if blocking > 0:
        print("  Blocking suites:")
        for item in sorted(
            [result for result in results if result["status"] in {"failed", "error"}],
            key=lambda result: result["elapsed_s"],
            reverse=True,
        )[:10]:
            print(f"    >> {item['suite_id']:45} {item['elapsed_s']:7.1f}s  {item['status']}")
    print(f"  Summary    : {REPORTS / 'summary.json'}")
    print(sep)
    return 0 if blocking == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
