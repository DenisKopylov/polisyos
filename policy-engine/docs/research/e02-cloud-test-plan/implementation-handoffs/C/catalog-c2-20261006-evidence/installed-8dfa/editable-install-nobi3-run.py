from __future__ import annotations
import hashlib, json, os, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
root = Path(__file__).parent
source = root / "source" / "policy-engine"
venv = root / "venv-base"
cache = Path("/Users/deniskopylov/.cache/uv")
python = venv / "bin" / "python"
build_roots = tuple("YUs921CMN7bGtgwyMykk3 QE6DREbYsK8sTuZOeKsM8 CYuBuDi6eT8vqgBcw1xmt 0_OIyaIgWrA6UuESVxSKg fi4dB0uLY-31KEGEb5kjs tS3T-feL91bRoib57dD1o uCD3kqxmr_S4Krxz4Y5Mq".split())
pythonpath = ":".join(str(cache / "archive-v0" / item) for item in build_roots)
argv = ["/opt/homebrew/bin/uv", "pip", "install", "--offline", "--no-deps", "--no-build-isolation", "--editable", str(source), "--python", str(python)]
env = dict(os.environ)
env["UV_CACHE_DIR"] = str(cache)
env["PYTHONPATH"] = pythonpath
env.pop("PYTHONHOME", None)
start = datetime.now(timezone.utc).isoformat()
t0 = time.monotonic()
result = subprocess.run(argv, cwd=source, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
elapsed = time.monotonic() - t0
end = datetime.now(timezone.utc).isoformat()
(root / "editable-install-nobi3.stdout").write_bytes(result.stdout)
(root / "editable-install-nobi3.stderr").write_bytes(result.stderr)
(root / "editable-install-nobi3.exit").write_text(str(result.returncode) + "\n")
def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
manifest = {
    "argv": argv, "cwd": str(source),
    "env_delta": {"UV_CACHE_DIR": str(cache), "PYTHONPATH": pythonpath, "PYTHONHOME": None},
    "started_at_utc": start, "ended_at_utc": end, "elapsed_seconds": round(elapsed, 3),
    "exit_code": result.returncode,
    "stdout": {"path": str(root / "editable-install-nobi3.stdout"), "sha256": sha(root / "editable-install-nobi3.stdout")},
    "stderr": {"path": str(root / "editable-install-nobi3.stderr"), "sha256": sha(root / "editable-install-nobi3.stderr")},
}
(root / "editable-install-nobi3-command.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
print(json.dumps(manifest, sort_keys=True))
if result.returncode: raise SystemExit(result.returncode)
