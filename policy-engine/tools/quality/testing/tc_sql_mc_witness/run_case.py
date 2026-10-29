"""Run one selected pytest phase, preserving complete output and sampled process use."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--phase", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--scratch", required=True)
ap.add_argument("--memory-cap-bytes", required=True, type=int)
ap.add_argument("--disk-floor-bytes", required=True, type=int)
ap.add_argument("--output-floor-bytes", required=True, type=int)
ap.add_argument("--timeout-seconds", required=True, type=int)
ap.add_argument("selectors", nargs="+")
a = ap.parse_args()
out, scratch = Path(a.out).resolve(), Path(a.scratch).resolve()
root = Path(os.environ["E02C_ROOT"]).resolve()
engine = root / "policy-engine"
(out / "commands").mkdir(parents=True, exist_ok=True)
(scratch / a.phase).mkdir(parents=True, exist_ok=True)
argv = [
    sys.executable,
    "-B",
    "-m",
    "pytest",
    "-p",
    "cloud_observer",
    "-q",
    "-ra",
    "--tb=short",
    "-o",
    f"cache_dir={scratch / a.phase / 'pytest-cache'}",
    f"--benchmark-storage=file://{scratch / a.phase / 'benchmarks'}",
    f"--basetemp={scratch / a.phase / 'pytest-tmp'}",
    f"--junitxml={out / 'commands' / (a.phase + '.junit.xml')}",
    *a.selectors,
]
env = dict(os.environ)
env["E02C_PHASE"] = a.phase
env["PYTHONDONTWRITEBYTECODE"] = "1"
env["PYTHONPYCACHEPREFIX"] = str(scratch / a.phase / "pycache")
env["TMPDIR"] = str(scratch / a.phase)
env["XDG_CACHE_HOME"] = str(scratch / a.phase / "xdg")
env["POLISYOS_CACHE_HOME"] = str(scratch / a.phase / "cache")
curated = scratch / a.phase / "empty-curated"
production = scratch / a.phase / "empty-production-data"
curated.mkdir()
production.mkdir()
env["POLISYOS_CURATED_DIR"] = str(curated)
env["POLISYOS_FABRIC_CURATED_DIR"] = str(curated)
env["POLISYOS_PRODUCTION_DATA_ROOT"] = str(production)
env["HYPOTHESIS_STORAGE_DIRECTORY"] = str(scratch / a.phase / "hypothesis")
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    env[key] = "1"
started = time.monotonic()
stop_reason = None
peak = 0
seen = {}


def snapshot(pid: int) -> dict[int, dict[str, int | str]] | None:
    """Sample the observable process tree; short-lived children remain unobserved."""
    proc = Path("/proc")
    if not proc.is_dir():
        return None
    table = {}
    for path in proc.iterdir():
        if not path.name.isdigit():
            continue
        try:
            lines = (path / "status").read_text().splitlines()
            values = {
                k: v.strip() for line in lines if ":" in line for k, v in [line.split(":", 1)]
            }
            table[int(path.name)] = {
                "ppid": int(values["PPid"]),
                "name": values.get("Name", ""),
                "rss": int(values.get("VmRSS", "0 kB").split()[0]) * 1024,
            }
        except (OSError, KeyError, ValueError, IndexError):
            continue
    members = {pid}
    while True:
        new = {child for child, row in table.items() if row["ppid"] in members}
        if new <= members:
            break
        members |= new
    return {p: table[p] for p in members if p in table}


with (
    (out / "commands" / (a.phase + ".stdout")).open("wb") as stdout,
    (out / "commands" / (a.phase + ".stderr")).open("wb") as stderr,
):
    proc = subprocess.Popen(
        argv, cwd=engine, env=env, stdout=stdout, stderr=stderr, start_new_session=True
    )
    while proc.poll() is None:
        rows = snapshot(proc.pid)
        if rows is not None:
            peak = max(peak, sum(row["rss"] for row in rows.values()))
            for pid, row in rows.items():
                seen[str(pid)] = {"ppid": row["ppid"], "name": row["name"]}
        if peak > a.memory_cap_bytes:
            stop_reason = "sampled_process_tree_rss_above_cap"
        elif shutil.disk_usage(scratch).free < a.disk_floor_bytes:
            stop_reason = "scratch_free_disk_below_floor"
        elif shutil.disk_usage(out).free < a.output_floor_bytes:
            stop_reason = "output_free_disk_below_floor"
        elif time.monotonic() - started > a.timeout_seconds:
            stop_reason = "protective_timeout"
        if stop_reason:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=10)
            except ProcessLookupError:
                pass
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            break
        time.sleep(0.25)
    code = proc.wait()
result = {
    "phase": a.phase,
    "argv": argv,
    "cwd": str(engine),
    "pid": proc.pid,
    "exit_code": code,
    "elapsed_seconds": round(time.monotonic() - started, 3),
    "stop_reason": stop_reason,
    "sampled_peak_process_tree_rss_bytes": peak if Path("/proc").is_dir() else None,
    "sampled_processes": seen,
    "memory_cap_bytes": a.memory_cap_bytes,
    "disk_floor_bytes": a.disk_floor_bytes,
    "output_floor_bytes": a.output_floor_bytes,
    "timeout_seconds": a.timeout_seconds,
    "junit_present": (out / "commands" / (a.phase + ".junit.xml")).is_file(),
    "limitations": "0.25s /proc RSS/process samples are lower bounds and may miss transient or reparented children; no OS-I/O or exact peak claim.",
}
(out / "commands" / (a.phase + ".command.json")).write_text(
    json.dumps(result, indent=2, sort_keys=True) + "\n"
)
print(json.dumps(result, sort_keys=True))
raise SystemExit(code if code >= 0 else 128 - code)
