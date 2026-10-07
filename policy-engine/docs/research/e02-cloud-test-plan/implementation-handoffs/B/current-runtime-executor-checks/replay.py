"""Replay the fresh executor input on its pinned base/candidate or removal control."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

BASE = "198076863e143dea9f89f02734b13d50dae3eed5"
CANDIDATE = "fd0a8b0044bb51539d812c2d0957381ed52ed3fd"
SOURCE = "policy-engine/src/polisyos/common/async_tools.py"
TEST = "tests/unit/common/test_async_tools.py"
PYTHON = "/workspace/polisyos/policy-engine/.venv/bin/python"
parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=("base", "candidate", "removed"), required=True)
parser.add_argument("--output-dir", type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[7]
product = root / "policy-engine"
output = args.output_dir.resolve()
output.mkdir(parents=True, exist_ok=True)
identity = {"mode": args.mode, "base_sha": BASE, "candidate_sha": CANDIDATE,
            "source_path": SOURCE, "test_path": "policy-engine/" + TEST,
            "python": PYTHON, "cwd": str(product)}
for path in (SOURCE, "policy-engine/" + TEST):
    expected = subprocess.check_output(["git", "show", CANDIDATE + ":" + path], cwd=root)
    actual = (root / path).read_bytes()
    if expected != actual:
        raise SystemExit("candidate input changed: " + path)
    identity[path] = hashlib.sha256(actual).hexdigest()
env = os.environ.copy()
prefix = []
if args.mode != "candidate":
    overlay = output / "overlay"
    overlay.mkdir(exist_ok=True)
    if args.mode == "base":
        base = subprocess.check_output(["git", "show", BASE + ":" + SOURCE], cwd=root)
        base_file = overlay / "base_async_tools.py"
        base_file.write_bytes(base)
        identity["baseline_source_sha256"] = hashlib.sha256(base).hexdigest()
        startup = """import importlib.util, sys
from pathlib import Path
import polisyos.common
path = Path(__file__).with_name('base_async_tools.py')
spec = importlib.util.spec_from_file_location('polisyos.common.async_tools', path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
polisyos.common.async_tools = module
"""
    else:
        startup = """import concurrent.futures
from polisyos.common import async_tools
async_tools._SharedExecutor = concurrent.futures.ThreadPoolExecutor
"""
    (overlay / "sitecustomize.py").write_text(startup)
    prefix.append(str(overlay))
env["PYTHONPATH"] = ":".join(prefix + [str(product / "src"), str(product)])
command = [PYTHON, "-m", "pytest", "-q", TEST, "--junitxml=" + str(output / "native.xml")]
identity.update(command=command, PYTHONPATH=env["PYTHONPATH"])
completed = subprocess.run(command, cwd=product, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True)
(output / "native.txt").write_text(completed.stdout)
identity.update(exit_code=completed.returncode, stdout_sha256=hashlib.sha256(completed.stdout.encode()).hexdigest())
(output / "receipt.json").write_text(json.dumps(identity, indent=2) + "\n")
print(json.dumps(identity, indent=2))
print(completed.stdout, end="")
sys.exit(completed.returncode)
