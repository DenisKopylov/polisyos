"""Exercise the reused capture owner on a deliberately timed-out child."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

CAPTURE = "docs.superpowers.journals.gy-phase5-evidence.shared.capture"
with tempfile.TemporaryDirectory(dir=Path.cwd() / ".tmp", prefix="corr-capture-") as scratch:
    path = Path(scratch) / "capture.json"
    child = subprocess.run(  # noqa: S603 - constant probe argv, no shell
        [sys.executable, "-m", CAPTURE, str(path), sys.executable, "-c",
         "import time; print('partial-output-before-timeout', flush=True); time.sleep(1)"],
        env={**os.environ, "GY_CAPTURE_TIMEOUT_SECONDS": "0.2"},
        capture_output=True, text=True, check=False,
    )
    record = json.loads(path.read_text())
    sys.stdout.write(
        json.dumps({"capture_exit": child.returncode, "record": record}, sort_keys=True) + "\n"
    )
    if record.get("timed_out") is not True:
        raise AssertionError("configured_capture_timeout_was_not_enforced")
    if record["returncode"] != -9:
        raise AssertionError("actual_child_returncode_not_retained")
    if child.returncode != 124:
        raise AssertionError("capture_timeout_exit_not_distinguished")
    if record["stdout"] != "partial-output-before-timeout\n":
        raise AssertionError("partial_capture_output_lost")
