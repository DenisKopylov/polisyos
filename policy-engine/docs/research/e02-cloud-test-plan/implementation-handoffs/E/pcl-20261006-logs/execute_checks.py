"""Capture actual PCL command outputs and resources without numerical worker caps."""

from __future__ import annotations

import argparse
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("mode", choices=["native", "controls"])
args = parser.parse_args()
log_root = Path(__file__).resolve().parent
commands = []
if args.mode == "native":
    commands.append(
        (
            "native",
            [
                sys.executable,
                "-m",
                "pytest",
                "-o",
                "addopts=",
                "-q",
                "tests/unit/calibration",
                "tests/unit/scientist/methods/backtesting/test_calibration_curve.py",
                "tests/unit/ir/analytics/test_calibration_diagnostics_report.py",
                "tests/unit/foundry/methods/catalog/validation/test_diagnostics.py",
                "tests/unit/foundry/methods/catalog/econometrics/test_advanced.py",
            ],
        )
    )
else:
    commands.extend(
        (mode, [sys.executable, str(log_root / "property_controls.py"), mode])
        for mode in ("proxy", "removed", "restored")
    )
records = []
for name, argv in commands:
    started = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    proc = subprocess.run(argv, capture_output=True, text=True)  # noqa: S603 - fixed local check argv
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    (log_root / (name + ".txt")).write_text(proc.stdout + proc.stderr)
    record = {
        "name": name,
        "argv": argv,
        "cwd": str(Path.cwd()),
        "exit_code": proc.returncode,
        "wall_s": time.perf_counter() - started,
        "user_cpu_s": after.ru_utime - before.ru_utime,
        "system_cpu_s": after.ru_stime - before.ru_stime,
        "child_max_rss_kib_cumulative": after.ru_maxrss,
        "output": str(log_root / (name + ".txt")),
    }
    records.append(record)
(log_root / (args.mode + "-execution.json")).write_text(json.dumps(records, indent=2) + "\n")
sys.stdout.write(json.dumps(records, indent=2) + "\n")
expected = [0] if args.mode == "native" else [0, 1, 0]
raise SystemExit(0 if [r["exit_code"] for r in records] == expected else 1)
