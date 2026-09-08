"""Capture exact child status/streams, with an optional measured process-group timeout."""
from __future__ import annotations

import json
import math
import os
import shlex
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path

name, *command = sys.argv[1:]
configured_timeout = os.environ.get("GY_CAPTURE_TIMEOUT_SECONDS")
timeout = float(configured_timeout) if configured_timeout is not None else None
if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
    raise ValueError("capture_timeout_must_be_finite_and_positive")
start = time.monotonic()
timed_out = False
with subprocess.Popen(  # noqa: S603 - explicitly supplied argv, never shell text
    command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    start_new_session=True,
) as child:
    try:
        stdout, stderr = child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        # Kill only the process group created for this invocation, including
        # child test workers; retain the complete streams already emitted.
        with suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)
        stdout, stderr = child.communicate()
    returncode = child.returncode
capture_returncode = 124 if timed_out else returncode
record = {
    "cwd": str(Path.cwd()), "command": shlex.join(command), "argv": command,
    "PATH": os.environ.get("PATH"), "PYTHONPATH": os.environ.get("PYTHONPATH"),
    "returncode": returncode, "capture_returncode": capture_returncode,
    "elapsed_seconds": time.monotonic() - start,
    "timeout_seconds": timeout, "timed_out": timed_out,
    "stdout": stdout, "stderr": stderr,
}
Path(name).write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
sys.stdout.write(json.dumps({key: record[key] for key in (
    "command", "returncode", "capture_returncode", "elapsed_seconds", "timed_out",
)}) + "\n")
sys.stdout.flush()
sys.stdout.write(stdout)
sys.stderr.write(stderr)
raise SystemExit(capture_returncode)
