"""Retain actual pytest output and exact child resource use without runner quotas."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

prefix, target, *pytest_args = sys.argv[1:]
if subprocess.check_output(["/usr/bin/git", "rev-parse", "HEAD"], text=True).strip() != target:
    raise RuntimeError("execution checkout does not match the frozen target")
python = Path("/workspace/polisyos/policy-engine/.venv/bin/python")
command = [str(python), "-m", "pytest", "-o", "addopts=", *pytest_args]
started = time.monotonic()
with Path(prefix + ".txt").open("wb") as output:
    # The fixed interpreter receives the recorded author-supplied pytest vector.
    child = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)  # noqa: S603
    waited_pid, status, usage = os.wait4(child.pid, 0)
    if waited_pid != child.pid:
        raise RuntimeError("resource accounting returned a different child")
    child.returncode = os.waitstatus_to_exitcode(status)
record = {
    "target_sha": target,
    "cwd": str(Path.cwd()),
    "argv": command,
    "python": str(python),
    "python_version": subprocess.check_output(
        ["/workspace/polisyos/policy-engine/.venv/bin/python", "--version"], text=True
    ).strip(),
    "platform": platform.platform(),
    "PYTHONPATH": os.environ.get("PYTHONPATH"),
    "property_removal": os.environ.get("E02_B_PROPERTY_REMOVAL"),
    "returncode": child.returncode,
    "wall_s": time.monotonic() - started,
    "max_rss_kib": usage.ru_maxrss,
    "rusage_boundary": (
        "os.wait4 of exact pytest PID, kernel accounting for that child and descendants; "
        "not VM peak"
    ),
    "runner_quota": None,
}
Path(prefix + ".run.json").write_text(json.dumps(record, indent=2) + "\n")
sys.stdout.write(json.dumps(record) + "\n")
sys.exit(child.returncode)
