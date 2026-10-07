"""Build the one immutable composed distribution wave under private /tmp storage.

This scratch orchestration is not executed until the root releases its final
composed source freeze. Every actual command/output is retained on failure.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

config_path = Path(sys.argv[1]).resolve()
config = json.loads(config_path.read_text())
root = Path(config["source_root"])
scratch = Path(config["scratch"])
sha = config["source_sha"]
assert scratch.is_relative_to(Path("/tmp"))
product = root / "policy-engine"
git = lambda *args: subprocess.check_output(["git", "-C", config["git_root"], *args])
entries = [item.split(b"\t", 1)[1].decode() for item in git("ls-tree", "-rz", "--full-tree", sha).split(b"\0") if item]
source_proof = json.loads(Path(config["source_snapshot_proof"]).read_text())

def source_guard(full=False):
    assert git("rev-parse", sha + "^{tree}").decode().strip() == config["source_tree"]
    if full:
        aggregate = hashlib.sha256()
        total = 0
        for name in entries:
            raw = (root / name).read_bytes()
            aggregate.update((name + "\0" + hashlib.sha256(raw).hexdigest() + "\0" + str(len(raw)) + "\n").encode())
            total += len(raw)
        assert aggregate.hexdigest() == source_proof["ordered_path_hash_size_aggregate"]
        assert total == source_proof["complete_original_Git_bytes"]
    for name in ("policy-engine/pyproject.toml", "policy-engine/hatch.toml", "policy-engine/uv.lock"):
        assert (root / name).read_bytes() == git("show", sha + ":" + name)

source_guard(full=True)
assert scratch.is_dir(), "Prepare exact frozen carriers first in this private scratch."
cache = scratch / "uv-cache"
cache.mkdir(exist_ok=False)
env = os.environ.copy()
env.update({"UV_CACHE_DIR": str(cache), "PYTHONDONTWRITEBYTECODE": "1"})
# Build/install subprocesses get no product source fallback from the parent shell.
env.pop("PYTHONPATH", None)
records = []

def run(name, argv, cwd):
    source_guard()
    started = time.monotonic()
    result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True)
    record = {"name": name, "source_sha": sha, "source_tree": config["source_tree"],
              "argv": argv, "cwd": str(cwd), "exit_code": result.returncode,
              "wall_seconds": time.monotonic() - started,
              "environment": {"UV_CACHE_DIR": str(cache), "PYTHONDONTWRITEBYTECODE": "1",
                              "PYTHONPATH": "absent"}}
    for stream, data in (("stdout", result.stdout), ("stderr", result.stderr)):
        path = scratch / (name + "." + stream + ".txt")
        assert not path.exists(), path
        path.write_bytes(data)
        record[stream] = {"path": str(path), "bytes": len(data),
                          "sha256": hashlib.sha256(data).hexdigest()}
    records.append(record)
    (scratch / "setup-command-records.json").write_text(json.dumps(records, indent=2) + "\n")
    source_guard()
    if result.returncode:
        raise SystemExit(result.returncode)
    return result

run("uv-version", ["uv", "--version"], scratch)
run("app-python-version", [config["app_python"], "-I", "-c",
    "import platform,sys;print(platform.python_version());print(sys.executable)"], scratch)
run("worker-python-version", [config["worker_python"], "-I", "-c",
    "import platform,sys;print(platform.python_version());print(sys.executable)"], scratch)
dist = scratch / "dist-source"
assert not dist.exists()
run("build-source", ["uv", "build", "--python", config["app_python"], "--wheel", "--sdist", "--out-dir", str(dist)], product)
wheels, sdists = list(dist.glob("*.whl")), list(dist.glob("*.tar.gz"))
assert len(wheels) == len(sdists) == 1, (wheels, sdists)
wheel, sdist = wheels[0], sdists[0]
run("materialize-actual-sdist", [sys.executable, str(scratch / "materialize_actual_sdist.py"), str(config_path), str(sdist)], scratch)
sdist_proof = json.loads((scratch / "actual-sdist-decoded-payloads.json").read_text())
roots = [Path(sdist_proof["rebuilt_source_root"])]
assert (roots[0] / "pyproject.toml").is_file()
rebuilt = scratch / "dist-rebuilt"
assert not rebuilt.exists()
run("build-rebuilt-sdist-wheel", ["uv", "build", "--python", config["app_python"], "--wheel", "--out-dir", str(rebuilt)], roots[0])
rebuilt_wheels = list(rebuilt.glob("*.whl"))
assert len(rebuilt_wheels) == 1, rebuilt_wheels
config["archives"] = {"wheel": str(wheel), "sdist": str(sdist),
                       "rebuilt_wheel": str(rebuilt_wheels[0])}
config["sdist_decoded_proof"] = str(scratch / "actual-sdist-decoded-payloads.json")
config["sites"] = {}
config["installed_pythons"] = {}
for kind, artifact in (("wheel", wheel), ("sdist", rebuilt_wheels[0])):
    environment = scratch / (kind + "-env")
    assert not environment.exists(), environment
    run(kind + "-create-env", ["uv", "venv", "--python", config["app_python"], str(environment)], scratch)
    python = environment / "bin/python"
    run(kind + "-install", ["uv", "pip", "install", "--python", str(python), "--no-deps", str(artifact)], scratch)
    site = environment / "lib/python3.14/site-packages"
    assert site.is_dir() and Path(config["dependency_site"]).is_dir()
    dependency_path = site / "e02_readonly_dependencies.pth"
    assert not dependency_path.exists()
    dependency_path.write_text(config["dependency_site"] + "\n")
    config["sites"][kind] = str(site)
    config["installed_pythons"][kind] = str(python)
    records.append({"name": kind + "-dependency-site", "source_sha": sha,
        "path": str(dependency_path), "content": config["dependency_site"] + "\n",
        "scope": "One literal dependency directory only; no product .pth, editable install or source path."})
    (scratch / "setup-command-records.json").write_text(json.dumps(records, indent=2) + "\n")
source_guard(full=True)
for name, path in config["archives"].items():
    raw = Path(path).read_bytes()
    records.append({"name": name + "-archive", "source_sha": sha, "path": path,
                    "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
(scratch / "setup-command-records.json").write_text(json.dumps(records, indent=2) + "\n")
final_config = scratch / "installed-config.json"
assert not final_config.exists()
final_config.write_text(json.dumps(config, indent=2) + "\n")
print(json.dumps({"source_sha": sha, "source_tree": config["source_tree"],
                  "installed_config": str(final_config), "archives": config["archives"],
                  "sites": config["sites"], "outcome": "distribution setup complete; native tests UNRUN"}))
