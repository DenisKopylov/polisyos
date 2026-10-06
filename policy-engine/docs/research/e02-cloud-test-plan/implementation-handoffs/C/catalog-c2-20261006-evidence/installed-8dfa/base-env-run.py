from __future__ import annotations
import hashlib, json, os, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).parent
cwd = root / "source" / "policy-engine"
venv = root / "venv-base"
cache = Path("/Users/deniskopylov/.cache/uv")
argv = ["/opt/homebrew/bin/uv", "sync", "--offline", "--frozen", "--no-dev", "--no-install-project", "--python", "/opt/homebrew/bin/python3"]
env = dict(os.environ)
env["UV_CACHE_DIR"] = str(cache)
env["UV_PROJECT_ENVIRONMENT"] = str(venv)
env.pop("PYTHONPATH", None)
env.pop("PYTHONHOME", None)
start = datetime.now(timezone.utc).isoformat()
t0 = time.monotonic()
result = subprocess.run(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
elapsed = time.monotonic() - t0
end = datetime.now(timezone.utc).isoformat()
(root / "base-sync.stdout").write_bytes(result.stdout)
(root / "base-sync.stderr").write_bytes(result.stderr)
(root / "base-sync.exit").write_text(str(result.returncode) + "\n")
def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
manifest = {
    "argv": argv, "cwd": str(cwd),
    "env_delta": {"UV_CACHE_DIR": str(cache), "UV_PROJECT_ENVIRONMENT": str(venv), "PYTHONPATH": None, "PYTHONHOME": None},
    "started_at_utc": start, "ended_at_utc": end, "elapsed_seconds": round(elapsed, 3),
    "exit_code": result.returncode,
    "stdout": {"path": str(root / "base-sync.stdout"), "sha256": sha(root / "base-sync.stdout")},
    "stderr": {"path": str(root / "base-sync.stderr"), "sha256": sha(root / "base-sync.stderr")},
}
(root / "base-sync-command.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
print(json.dumps(manifest, sort_keys=True))
if result.returncode: raise SystemExit(result.returncode)
