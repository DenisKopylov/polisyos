from __future__ import annotations
import hashlib, json, os, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).parent
cwd = root / "source" / "policy-engine"
dist = root / "dist"
dist.mkdir(exist_ok=True)
cache = Path("/Users/deniskopylov/.cache/uv")
pythonpath = ":".join(
    str(cache / "archive-v0" / item)
    for item in (
        "YUs921CMN7bGtgwyMykk3",
        "QE6DREbYsK8sTuZOeKsM8",
        "CYuBuDi6eT8vqgBcw1xmt",
        "0_OIyaIgWrA6UuESVxSKg",
        "fi4dB0uLY-31KEGEb5kjs",
        "tS3T-feL91bRoib57dD1o",
    )
)
argv = ["/opt/homebrew/bin/uv", "build", "--offline", "--no-build-isolation", "--out-dir", str(dist)]
env = dict(os.environ)
env["UV_CACHE_DIR"] = str(cache)
env["PYTHONPATH"] = pythonpath
env.pop("PYTHONHOME", None)
start = datetime.now(timezone.utc).isoformat()
t0 = time.monotonic()
result = subprocess.run(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
elapsed = time.monotonic() - t0
end = datetime.now(timezone.utc).isoformat()
(root / "build.stdout").write_bytes(result.stdout)
(root / "build.stderr").write_bytes(result.stderr)
(root / "build.exit").write_text(str(result.returncode) + "\n")
def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
manifest = {
    "argv": argv,
    "cwd": str(cwd),
    "env_delta": {"UV_CACHE_DIR": str(cache), "PYTHONPATH": pythonpath, "PYTHONHOME": None},
    "started_at_utc": start,
    "ended_at_utc": end,
    "elapsed_seconds": round(elapsed, 3),
    "exit_code": result.returncode,
    "stdout": {"path": str(root / "build.stdout"), "sha256": sha(root / "build.stdout")},
    "stderr": {"path": str(root / "build.stderr"), "sha256": sha(root / "build.stderr")},
}
(root / "build-command.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
print(json.dumps(manifest, sort_keys=True))
if result.returncode:
    raise SystemExit(result.returncode)
