"""Capture one exact C05 gate with per-process resource usage."""
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

out = Path(sys.argv[1])
cwd = Path(sys.argv[2])
cmd = json.loads(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env["PYTHONPATH"] = str(cwd / "src") + ":" + str(cwd)
env["PYTHONDONTWRITEBYTECODE"] = "1"
start = time.perf_counter()
result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True)
wall = time.perf_counter() - start
usage = resource.getrusage(resource.RUSAGE_CHILDREN)
(out / "stdout.txt").write_bytes(result.stdout)
(out / "stderr.txt").write_bytes(result.stderr)
record = {
    "command": cmd,
    "cwd": str(cwd),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd, text=True).strip(),
    "tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=cwd, text=True).strip(),
    "status": subprocess.check_output(["git", "status", "--porcelain"], cwd=cwd, text=True),
    "pythonpath": env["PYTHONPATH"],
    "exit_code": result.returncode,
    "wall_seconds": wall,
    "max_rss_kib": usage.ru_maxrss,
    "user_seconds": usage.ru_utime,
    "system_seconds": usage.ru_stime,
    "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
    "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
}
(out / "command.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
sys.exit(result.returncode)
