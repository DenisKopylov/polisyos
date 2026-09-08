"""Capture a research command, its actual return code, and its complete streams."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time


root = Path(__file__).resolve().parents[5]
output = Path(__file__).resolve().parent
name, *command = sys.argv[1:]
env = dict(os.environ)
env["PATH"] = str(root / ".venv/bin") + os.pathsep + env.get("PATH", "")
env["PYTHONPATH"] = str(root / "src") + os.pathsep + env.get("PYTHONPATH", "")
started = time.time()
completed = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
record = {
    "command": shlex.join(command),
    "cwd": str(root),
    "path_prefix": str(root / ".venv/bin"),
    "pythonpath_prefix": str(root / "src"),
    "returncode": completed.returncode,
    "duration_seconds": round(time.time() - started, 3),
    "stdout": completed.stdout,
    "stderr": completed.stderr,
}
(output / f"{name}.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({key: value for key, value in record.items() if key not in {"stdout", "stderr"}}))
print(completed.stdout, end="")
print(completed.stderr, end="", file=sys.stderr)
sys.exit(completed.returncode)
