"""Retain exact process return code and complete observer output in ignored scratch."""

# ruff: noqa: S603, T201 - exact bounded module invocation and complete captured streams
import json
import os
import subprocess
import time
from pathlib import Path

root = Path.cwd()
argv = [str(root / ".venv/bin/python"), "-m", "gyphase5_promotion_compare_observer"]
env = dict(os.environ)
env["PATH"] = str(root / ".venv/bin") + os.pathsep + env.get("PATH", "")
env["PYTHONPATH"] = str(root / ".tmp") + os.pathsep + str(root / "src") + os.pathsep + str(root)
start = time.monotonic()
result = subprocess.run(argv, cwd=root, env=env, capture_output=True, text=True)
record = {
    "argv": argv,
    "cwd": str(root),
    "PATH": env["PATH"],
    "PYTHONPATH": env["PYTHONPATH"],
    "returncode": result.returncode,
    "elapsed_seconds": time.monotonic() - start,
    "stdout": result.stdout,
    "stderr": result.stderr,
}
destination = root / ".tmp/gyphase5-promotion-comparison-diagnostic"
destination.mkdir(parents=True, exist_ok=True)
(destination / "command.json").write_text(json.dumps(record, indent=2) + "\n")
print(
    json.dumps(
        {
            key: value
            for key, value in record.items()
            if key not in {"stdout", "stderr", "PATH", "PYTHONPATH"}
        },
        indent=2,
    )
)
print(result.stdout)
print(result.stderr)
raise SystemExit(result.returncode)
