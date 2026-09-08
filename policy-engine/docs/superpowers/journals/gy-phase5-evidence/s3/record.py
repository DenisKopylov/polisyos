"""Capture one exact evidence command and its complete separate output streams."""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main() -> None:
    here = Path(__file__).resolve().parent
    label, *command = sys.argv[1:]
    root = here.parents[4]
    environment = os.environ.copy()
    environment["PATH"] = str(root / ".venv/bin") + os.pathsep + environment["PATH"]
    environment["PYTHONPATH"] = str(root / "src") + os.pathsep + str(root)
    started = datetime.datetime.now(datetime.UTC).isoformat()
    measurement_source = (here / "measure.py").read_text()
    clock = time.monotonic()
    result = subprocess.run(command, cwd=root, env=environment, capture_output=True, text=True)
    record = {
        "label": label,
        "cwd": str(root),
        "command": command,
        "PATH": environment["PATH"],
        "PYTHONPATH": environment["PYTHONPATH"],
        "started_at": started,
        "elapsed_seconds": time.monotonic() - clock,
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "measurement_script_source": measurement_source,
    }
    target = here / (label + ".json")
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"record": str(target), "return_code": result.returncode,
                      "elapsed_seconds": record["elapsed_seconds"]}))
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
