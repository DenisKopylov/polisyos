"""Retain one complete deciding command receipt, without duplicating artifacts."""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment.update({
        "PATH": f"{root / '.venv/bin'}:{environment['PATH']}",
        "PYTHONPATH": f"{root / 'src'}:{root}",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_ADDOPTS": "-p no:cacheprovider",
        "TMPDIR": str(root / "_build/gy-gaps/tmp"),
        "POLISYOS_CACHE_HOME": str(root / "_build/gy-gaps/cache"),
    })
    Path(environment["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    started = datetime.datetime.now(datetime.UTC).isoformat()
    clock = time.monotonic()
    try:
        run = subprocess.run(command, cwd=root, env=environment, text=True,
                             capture_output=True, timeout=args.timeout)
        rc, stdout, stderr = run.returncode, run.stdout, run.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        rc, timed_out = 124, True
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
    receipt = {"command": command, "cwd": str(root), "started_utc": started,
               "elapsed_seconds": round(time.monotonic() - clock, 3), "returncode": rc,
               "timed_out": timed_out,
               "environment": {key: environment[key] for key in
                               ("PATH", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "PYTEST_ADDOPTS",
                                "TMPDIR", "POLISYOS_CACHE_HOME")},
               "stdout": stdout, "stderr": stderr}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in receipt.items() if key not in {"stdout", "stderr", "environment"}}))
    print(f"Complete output: {args.output}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
