"""Preserve the complete command/output of the one authorized native witness."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


HERE = Path(__file__).resolve().parent
RUN = HERE / "freshpid-native"
INTERPRETER = "/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python"
ARGV = [INTERPRETER, "-I", "-B", str(HERE / "freshpid_producer.py"), str(RUN)]
environment = os.environ.copy()
environment["POLISYOS_METRICS_PORT"] = "9465"
environment["PYTHONDONTWRITEBYTECODE"] = "1"
started = time.monotonic()
result = subprocess.run(ARGV, cwd=HERE, env=environment, capture_output=True, check=False)
(HERE / "freshpid-native.stdout.txt").write_bytes(result.stdout)
(HERE / "freshpid-native.stderr.txt").write_bytes(result.stderr)
record = {
    "schema": "readonly_native_command/1.0",
    "reviewer": "graph_scm",
    "source_sha": "4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d",
    "source_tree": "551d4e760dc1168f6ad8182c9b176f00e94a2281",
    "argv": ARGV,
    "cwd": str(HERE),
    "environment_overrides": {"POLISYOS_METRICS_PORT": "9465", "PYTHONDONTWRITEBYTECODE": "1"},
    "exit_code": result.returncode,
    "wall_s": time.monotonic() - started,
    "stdout": {"path": str(HERE / "freshpid-native.stdout.txt"), "bytes": len(result.stdout), "sha256": hashlib.sha256(result.stdout).hexdigest()},
    "stderr": {"path": str(HERE / "freshpid-native.stderr.txt"), "bytes": len(result.stderr), "sha256": hashlib.sha256(result.stderr).hexdigest()},
    "runtime_result": "UNASSESSED",
}
(HERE / "freshpid-execution.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
print(json.dumps(record, sort_keys=True))
