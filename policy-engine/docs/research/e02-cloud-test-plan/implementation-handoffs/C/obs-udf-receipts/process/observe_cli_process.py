from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

root = Path(__file__).resolve().parent
command = [
    sys.executable,
    "-m",
    "polisyos.data_forge.domains.ukraine.cli",
    "--config",
    str(root / "absent-root-config.json"),
    "validate-part-a",
]
env = dict(os.environ)
env["PYTHONPATH"] = str(root / "source" / "policy-engine" / "src")
started_at = datetime.now(UTC).isoformat()
started = time.monotonic()
process = subprocess.Popen(
    command,
    cwd=root,
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
stdout, stderr = process.communicate()
elapsed_s = time.monotonic() - started
finished_at = datetime.now(UTC).isoformat()
(root / "observed-cli.stdout").write_text(stdout, encoding="utf-8")
(root / "observed-cli.stderr").write_text(stderr, encoding="utf-8")
manifest_path = root / "absent-root-build" / "manifests" / "part_a_gate_manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
receipt = {
    "command": command,
    "cwd": str(root),
    "observer_pid": os.getpid(),
    "child_pid": process.pid,
    "started_at": started_at,
    "finished_at": finished_at,
    "elapsed_s": elapsed_s,
    "communicate_completed": True,
    "poll_after_communicate": process.poll(),
    "returncode": process.returncode,
    "stdout_file": "observed-cli.stdout",
    "stderr_file": "observed-cli.stderr",
    "gate_manifest": str(manifest_path),
    "gate_status": manifest["status"],
    "gate_passed": manifest["passed"],
    "gate_skipped": manifest["skipped"],
    "gate_command": manifest["command"],
    "server_process_or_port_started": False,
    "reason": "workspace auto-discovery produced typed unavailable before gate subprocess dispatch",
}
(root / "observed-cli-process.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print(json.dumps({key: receipt[key] for key in ("child_pid", "returncode", "elapsed_s", "gate_status", "gate_command", "server_process_or_port_started")}, sort_keys=True))
