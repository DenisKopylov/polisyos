from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

raw = Path(__file__).resolve().parent
wheel = raw / "dist" / "policy_engine-0.1.0-py3-none-any.whl"
python = raw / "venv-base" / "bin" / "python"
uv = shutil.which("uv")
if not uv:
    raise SystemExit("uv executable not found")
argv = [uv, "pip", "install", "--offline", "--no-deps", "--reinstall", "--python", str(python), str(wheel)]
env = {
    "HOME": "/Users/deniskopylov",
    "PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
    "TMPDIR": "/tmp",
    "UV_CACHE_DIR": "/Users/deniskopylov/.cache/uv",
}
started = datetime.now(UTC).isoformat()
completed = subprocess.run(argv, cwd="/tmp", env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=300)
finished = datetime.now(UTC).isoformat()
stdout_path = raw / "install-wheel.stdout"
stderr_path = raw / "install-wheel.stderr"
exit_path = raw / "install-wheel.exit"
stdout_path.write_bytes(completed.stdout)
stderr_path.write_bytes(completed.stderr)
exit_path.write_text(f"{completed.returncode}\n", encoding="utf-8")
manifest = {
    "argv": argv,
    "cwd": "/tmp",
    "env": env,
    "started_at_utc": started,
    "finished_at_utc": finished,
    "timeout_seconds": 300,
    "exit_code": completed.returncode,
    "wheel_path": str(wheel),
    "wheel_bytes": wheel.stat().st_size,
    "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
    "stdout_path": str(stdout_path),
    "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
    "stderr_path": str(stderr_path),
    "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
    "exit_path": str(exit_path),
    "exit_sha256": hashlib.sha256(exit_path.read_bytes()).hexdigest(),
    "selected_extras": [],
    "no_dependencies": True,
}
manifest_path = raw / "install-wheel.command.json"
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"exit_code": completed.returncode, "manifest": str(manifest_path), "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}))
if completed.returncode:
    raise SystemExit(completed.returncode)
