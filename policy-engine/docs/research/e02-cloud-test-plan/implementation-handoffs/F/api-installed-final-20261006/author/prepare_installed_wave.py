"""Prepare exact Git test carriers for a reviewed, immutable composed candidate."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

config_path = Path(sys.argv[1]).resolve()
config = json.loads(config_path.read_text())
root, scratch = Path(config["source_root"]), Path(config["scratch"])
sha = config["source_sha"]
git = lambda *args: subprocess.check_output(["git", *args], cwd=root)
assert git("rev-parse", "HEAD").decode().strip() == sha
assert git("rev-parse", "HEAD^{tree}").decode().strip() == config["source_tree"]
assert git("symbolic-ref", "--short", "HEAD").decode().strip() == config["branch"]
assert not git("status", "--porcelain", "--untracked-files=no")
scratch.mkdir(parents=True, exist_ok=True)
records = []
for kind in ("wheel", "sdist"):
    carrier = scratch / (kind + "-consumer")
    carrier.mkdir(exist_ok=True)
    for role, relative in config["carrier_paths"].items():
        raw = git("show", sha + ":" + relative)
        destination = carrier / Path(relative).name
        assert not destination.exists(), destination
        destination.write_bytes(raw)
        records.append({"kind": kind, "role": role, "git_path": relative,
                        "git_blob": git("rev-parse", sha + ":" + relative).decode().strip(),
                        "path": str(destination), "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest()})
assets = {}
for name in ("worker.py", "protocol.py", "pyproject.toml", "uv.lock", ".python-version", "README.md"):
    path = "policy-engine/workers/dowhy-014/" + name
    raw = git("show", sha + ":" + path)
    assets[name] = {"source_path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
profile = scratch / "profile-expected.json"
profile.write_text(json.dumps({"source_sha": sha, "assets": assets}, indent=2) + "\n")
manifest = {"source_sha": sha, "source_tree": config["source_tree"], "test_carriers": records,
            "profile": str(profile), "assets": assets,
            "scope": "Exact frozen Git fixtures only; authority-positive remains UNRUN."}
(scratch / "carrier-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"source_sha": sha, "carrier_files": len(records), "profile_assets": len(assets)}))
