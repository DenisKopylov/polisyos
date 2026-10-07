from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

here = Path(__file__).resolve().parent
root = Path("/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos")
python = root / "policy-engine/.venv/bin/python"
source = here / "candidate/policy-engine/src"
raw = here / "raw"
raw.mkdir(exist_ok=True)
env = os.environ.copy()
run_tag = "attempt2-confidence-annotated"
env.update(
    {
        "PYTHONPATH": str(source),
        "PROBE_RUN_TAG": run_tag,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }
)
command = [str(python), "-B", str(here / "probe.py")]
started = time.time()
start_ns = time.monotonic_ns()
process = subprocess.Popen(
    command,
    cwd=here,
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    start_new_session=True,
)
try:
    stdout, stderr = process.communicate(timeout=90)
    timed_out = False
except subprocess.TimeoutExpired as exc:
    process.kill()
    stdout, stderr = process.communicate()
    timed_out = True
(raw / f"{run_tag}.stdout.txt").write_bytes(stdout)
(raw / f"{run_tag}.stderr.txt").write_bytes(stderr)
execution = {
    "command": command,
    "run_tag": run_tag,
    "cwd": str(here),
    "timeout_seconds": 90,
    "timed_out": timed_out,
    "returncode": process.returncode,
    "started_epoch_seconds": started,
    "elapsed_seconds": (time.monotonic_ns() - start_ns) / 1_000_000_000,
    "environment": {
        key: env.get(key)
        for key in (
            "PYTHONPATH",
            "PROBE_RUN_TAG",
            "PYTHONDONTWRITEBYTECODE",
            "PYTHONNOUSERSITE",
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
        )
    },
    "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
    "stdout_bytes": len(stdout),
    "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
    "stderr_bytes": len(stderr),
}
(raw / f"{run_tag}.execution.json").write_text(json.dumps(execution, sort_keys=True, indent=2) + "\n")
print(json.dumps(execution, sort_keys=True, indent=2))
print(stdout.decode(errors="replace"), end="")
if stderr:
    print("CHILD_STDERR_BEGIN")
    print(stderr.decode(errors="replace"), end="")
print("CHILD_STDERR_END")
raise SystemExit(124 if timed_out else process.returncode)
