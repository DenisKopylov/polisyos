"""Replay actual process effects against an immutable Git base/candidate."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

BASE = "e3fa47ab3004ceed17648fae58ef4a7df9d168cc"
CANDIDATE = "fbc5fb8dc4d300df2b1a81b78c13649e4832ad53"
SOURCE = "policy-engine/src/polisyos/scientist/orchestration/engine/retry.py"
TEST = "policy-engine/tests/unit/scientist/orchestration/engine/test_retry.py"
PYTHON = "/workspace/polisyos/policy-engine/.venv/bin/python"
SELECTOR = "worker_setup_fault"
parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=("base", "candidate"), required=True)
parser.add_argument("--output-dir", type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[7]
product = root / "policy-engine"
out = args.output_dir.resolve()
out.mkdir(parents=True, exist_ok=True)
identity = {"mode": args.mode, "base_sha": BASE, "candidate_sha": CANDIDATE,
            "cwd": str(product), "python": PYTHON, "input_sha256": {}}
for path in (SOURCE, TEST, "policy-engine/tests/unit/scientist/orchestration/engine/_retry_setup_probe.py", "policy-engine/src/polisyos/common/async_tools.py",
             "policy-engine/src/polisyos/scientist/orchestration/engine/runner/serialization.py"):
    expected = subprocess.check_output(["git", "show", CANDIDATE + ":" + path], cwd=root)
    if (root / path).read_bytes() != expected:
        raise SystemExit("immutable input changed: " + path)
    identity["input_sha256"][path] = hashlib.sha256(expected).hexdigest()
env = os.environ.copy()
prefix = []
if args.mode == "base":
    overlay = out / "overlay"
    overlay.mkdir(exist_ok=True)
    source = subprocess.check_output(["git", "show", BASE + ":" + SOURCE], cwd=root)
    (overlay / "base_retry.py").write_bytes(source)
    identity["base_source_sha256"] = hashlib.sha256(source).hexdigest()
    (overlay / "sitecustomize.py").write_text("""import importlib.abc, importlib.util, sys
from pathlib import Path
class PinnedRetry(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'polisyos.scientist.orchestration.engine.retry':
            return importlib.util.spec_from_file_location(fullname, Path(__file__).with_name('base_retry.py'))
sys.meta_path.insert(0, PinnedRetry())
""")
    prefix.append(str(overlay))
env["PYTHONPATH"] = ":".join(prefix + [str(product / "src"), str(product)])
command = [PYTHON, "-m", "pytest", "-o", "addopts=", "-q",
           TEST.removeprefix("policy-engine/"), "-k", SELECTOR,
           "--junitxml=" + str(out / "native.xml")]
identity.update(command=command, PYTHONPATH=env["PYTHONPATH"])
completed = subprocess.run(command, cwd=product, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True)
(out / "native.txt").write_text(completed.stdout)
identity.update(exit_code=completed.returncode,
                stdout_sha256=hashlib.sha256(completed.stdout.encode()).hexdigest())
(out / "receipt.json").write_text(json.dumps(identity, indent=2) + "\n")
print(json.dumps(identity, indent=2))
print(completed.stdout, end="")
sys.exit(completed.returncode)
