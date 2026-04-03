#!/usr/bin/env python3
"""Parallel benchmark runner — saturates available CPU cores.

Usage
-----
    # Default: smoke mode, auto-detect workers (CPU count - 2)
    python benchmarks/run_parallel.py

    # Custom settings via env vars
    BENCH_WORKERS=8 BENCH_MODE=acceptance python benchmarks/run_parallel.py

    # Filter by profile / contour
    BENCH_PROFILE=core BENCH_CONTOUR=legacy python benchmarks/run_parallel.py

Environment variables
---------------------
    BENCH_WORKERS   Number of parallel workers (default: cpu_count - 2, min 2)
    BENCH_MODE      Benchmark mode: smoke | acceptance (default: smoke)
    BENCH_RUN_ID    Custom run identifier (default: auto-generated)
    BENCH_PROFILE   Filter suites by profile name
    BENCH_CONTOUR   Filter suites by validation contour
    BENCH_VISIBILITY Filter suites by visibility lane
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
BENCH_DIR = REPO / "benchmarks"
REPORTS = BENCH_DIR / "_reports"
REPORTS.mkdir(exist_ok=True)

_cpu = os.cpu_count() or 4
MAX_WORKERS = int(os.environ.get("BENCH_WORKERS", str(max(2, _cpu - 2))))
MODE = os.environ.get("BENCH_MODE", "smoke")
RUN_ID = os.environ.get(
    "BENCH_RUN_ID",
    f"parallel-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
)

sys.path.insert(0, str(SRC))
sys.path.insert(0, str(REPO))

from benchmarks.suite_registry import emit_registry_tsv


def _parse_suites() -> list[tuple[str, str, str]]:
    """Discover suites from the registry, return (id, label, script) triples."""
    profile = os.environ.get("BENCH_PROFILE") or None
    contour = os.environ.get("BENCH_CONTOUR") or None
    visibility = os.environ.get("BENCH_VISIBILITY") or None
    tsv = emit_registry_tsv(
        profile=profile,
        validation_contour=contour,
        visibility=visibility,
    )
    suites: list[tuple[str, str, str]] = []
    for line in tsv.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        suites.append((parts[0], parts[1], parts[2]))
    return suites


def run_suite(suite_id: str, label: str, script: str) -> dict:
    """Run a single benchmark suite in a subprocess (no timeout)."""
    json_file = str(REPORTS / f"{suite_id}.json")
    log_file = str(REPORTS / f".{suite_id}.log")
    env = {
        **os.environ,
        "PYTHONPATH": f"{SRC}:{REPO}:{os.environ.get('PYTHONPATH', '')}",
        "BENCH_MODE": MODE,
        "BENCH_RUN_ID": RUN_ID,
    }
    t0 = time.monotonic()
    try:
        result = subprocess.run(
            [sys.executable, script, "--mode", MODE, "--json", json_file],
            capture_output=True,
            text=True,
            env=env,
        )
        elapsed = time.monotonic() - t0
        with open(log_file, "w") as f:
            f.write(result.stdout)
            if result.stderr:
                f.write("\n--- STDERR ---\n")
                f.write(result.stderr)
        status = "passed" if result.returncode == 0 else "failed"
        return {
            "suite_id": suite_id,
            "label": label,
            "status": status,
            "exit_code": result.returncode,
            "elapsed_s": round(elapsed, 1),
            "report_exists": Path(json_file).exists(),
        }
    except Exception as e:
        elapsed = time.monotonic() - t0
        return {
            "suite_id": suite_id,
            "label": label,
            "status": f"error: {e}",
            "exit_code": -1,
            "elapsed_s": round(elapsed, 1),
            "report_exists": False,
        }


def main() -> int:
    suites = _parse_suites()
    if not suites:
        print("No suites matched the current filter. Check BENCH_PROFILE / BENCH_CONTOUR / BENCH_VISIBILITY.")
        return 1

    print(f"=== Parallel benchmark run: {len(suites)} suites, {MAX_WORKERS} workers ===")
    print(f"    Run ID : {RUN_ID}")
    print(f"    Mode   : {MODE}")
    print(f"    Python : {sys.executable}")
    print(f"    Reports: {REPORTS}")
    print(f"    No timeout (suites run to completion)")
    print(flush=True)

    results: list[dict] = []
    t_start = time.monotonic()

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(run_suite, sid, lbl, scr): sid
            for sid, lbl, scr in suites
        }
        for future in as_completed(futures):
            r = future.result()
            results.append(r)
            tag = "PASS" if r["status"] == "passed" else "FAIL"
            print(
                f"  [{tag}] {r['suite_id']:50} {r['elapsed_s']:7.1f}s  {r['status']}",
                flush=True,
            )

    wall = time.monotonic() - t_start
    n_pass = sum(1 for r in results if r["status"] == "passed")
    n_total = len(results)

    summary = {
        "run_id": RUN_ID,
        "mode": MODE,
        "workers": MAX_WORKERS,
        "n_total": n_total,
        "n_passed": n_pass,
        "n_failed": n_total - n_pass,
        "pass_rate": round(n_pass / n_total, 4) if n_total else 0,
        "wall_time_s": round(wall, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite_results": sorted(results, key=lambda r: r["elapsed_s"]),
    }
    with open(str(REPORTS / "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    sep = "=" * 72
    print(f"\n{sep}")
    print(f"  DONE in {wall:.0f}s wall time ({MAX_WORKERS} workers)")
    print(f"  Passed: {n_pass}/{n_total}  ({n_pass * 100 / n_total:.1f}%)")
    print(f"  Failed: {n_total - n_pass}")
    if n_total - n_pass > 0:
        print("  Slowest / failed suites:")
        for r in sorted(results, key=lambda r: r["elapsed_s"], reverse=True)[:10]:
            marker = "  " if r["status"] == "passed" else ">>"
            print(f"    {marker} {r['suite_id']:45} {r['elapsed_s']:7.1f}s  {r['status']}")
    print(f"  Summary: {REPORTS / 'summary.json'}")
    print(sep)
    return 0 if n_pass == n_total else 1


if __name__ == "__main__":
    raise SystemExit(main())
