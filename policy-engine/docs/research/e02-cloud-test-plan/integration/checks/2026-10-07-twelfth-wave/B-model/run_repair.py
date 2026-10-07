from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from hashlib import sha1, sha256
from pathlib import Path

ROOT = Path("/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos").resolve()
WORK = ROOT / "policy-engine/_build/e02-g-continuation-20261006/R/incoming-20261007-1311/B-model-local"
CANDIDATE = WORK / "candidate/policy-engine"
ARCHIVE_ROOT = WORK / "candidate"
RESULTS = WORK / "results"
PYTHON = ROOT / "policy-engine/.venv/bin/python"
RUNTIME = WORK / "candidate_runtime.py"
MANIFEST = WORK / "source-manifest-final.json"
TIMEOUT_SECONDS = 180


def snapshot(label: str) -> dict[str, object]:
    disk = shutil.disk_usage(ROOT)
    ps = subprocess.run(["/bin/ps", "-axo", "pid,pcpu,rss,command"], check=True, text=True, capture_output=True).stdout
    return {
        "label": label,
        "disk_total_bytes": disk.total,
        "disk_used_bytes": disk.used,
        "disk_free_bytes": disk.free,
        "python_processes": [line for line in ps.splitlines() if "python" in line.lower() or "pytest" in line.lower()],
        "time_monotonic": time.monotonic(),
    }


def verify_source() -> dict[str, object]:
    manifest = json.loads(MANIFEST.read_text())
    errors = []
    for entry in manifest["files"]:
        path = ARCHIVE_ROOT / entry["path"]
        if not path.is_file():
            errors.append(f"missing {entry['path']}")
            continue
        data = path.read_bytes()
        blob = sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        mode = "100755" if path.stat().st_mode & 0o111 else "100644"
        digest = sha256(data).hexdigest()
        if blob != entry["git_blob"] or mode != entry["mode"] or digest != entry["sha256"]:
            errors.append(f"changed {entry['path']}")
    return {
        "manifest": str(MANIFEST),
        "manifest_sha256": sha256(MANIFEST.read_bytes()).hexdigest(),
        "file_count": manifest["file_count"],
        "total_bytes": manifest["total_bytes"],
        "verified": not errors,
        "errors": errors,
    }


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(CANDIDATE / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_ADDOPTS": "",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    env.pop("PYTEST_DISABLE_PLUGIN_AUTOLOAD", None)
    argv = [str(PYTHON), str(RUNTIME), "pytest-repaired"]
    stdout_path = RESULTS / "pytest-repaired.stdout"
    stderr_path = RESULTS / "pytest-repaired.stderr"
    before_source = verify_source()
    if not before_source["verified"]:
        raise SystemExit(f"source verification failed before test: {before_source}")
    start = time.monotonic()
    timed_out = False
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        proc = subprocess.Popen(
            argv,
            cwd=CANDIDATE,
            env=env,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        try:
            rc = proc.wait(timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                rc = proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                rc = proc.wait()
    elapsed = round(time.monotonic() - start, 3)
    after_source = verify_source()
    status = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain=v1"], check=True, text=True, capture_output=True).stdout
    record = {
        "candidate": "d18fe09b5bc0367c966011144a5418f836b9a4b7",
        "tree": "d4faa64e884c863bdd8c4692432bff4bbd102c54",
        "command": argv,
        "cwd": str(CANDIDATE),
        "timeout_seconds": TIMEOUT_SECONDS,
        "timed_out": timed_out,
        "returncode": rc,
        "elapsed_seconds": elapsed,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "junit": str(RESULTS / "selected-tests-pytest-repaired.junit.xml"),
        "source_before": before_source,
        "source_after": after_source,
        "source_unchanged": before_source["manifest_sha256"] == after_source["manifest_sha256"] and after_source["verified"],
        "g_head_after": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
        "g_branch_after": subprocess.check_output(["git", "-C", str(ROOT), "symbolic-ref", "--short", "HEAD"], text=True).strip(),
        "g_status_after": status,
        "snapshots": [snapshot("after")],
        "repair_reason": "The first exact-source pytest attempt stopped during collection because source-derived dependency-authority import read tracked architecture registry assets outside src; the repair adds only five files from the same d18 commit, including the full declared source-path inputs.",
    }
    out = RESULTS / "repair-context.json"
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if rc == 0 and not timed_out and record["source_unchanged"] and not status else 1


if __name__ == "__main__":
    raise SystemExit(main())
