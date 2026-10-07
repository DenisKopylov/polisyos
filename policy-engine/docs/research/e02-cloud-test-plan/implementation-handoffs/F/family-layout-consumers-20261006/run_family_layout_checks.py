"""Record native migration consumers, semantic removals, and docs availability."""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path("/workspace/e02-F-fry-20261006")
CWD = ROOT / "policy-engine"
SCRATCH = Path("/tmp/e02-F-continuation-20261006/foundry")
PYTHON = "/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python"
SOURCE = "7f05b6259e0c78fac81a0baa4bff41e648a9d771"


def bound(path):
    content = path.read_bytes()
    return {"path": str(path), "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def check(name, argv, expected=0, backend_error=False):
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if actual != SOURCE:
        raise RuntimeError(f"Wrong frozen source {actual}")
    env = os.environ.copy()
    env["PYTHONPATH"] = "src:tools"
    start = time.monotonic()
    run = subprocess.run(argv, cwd=CWD, env=env, capture_output=True)
    wall = time.monotonic() - start
    stdout, stderr = (SCRATCH / f"{name}.{stream}.txt" for stream in ("stdout", "stderr"))
    stdout.write_bytes(run.stdout)
    stderr.write_bytes(run.stderr)
    receipt = {
        "name": name, "argv": argv, "command": " ".join(argv), "cwd": str(CWD),
        "target_sha": SOURCE, "wall_seconds": wall, "exit_code": run.returncode,
        "outcome": "ERROR" if backend_error and run.returncode else "PASS" if run.returncode == 0
        else "FAIL" if run.returncode == 1 else "ERROR",
        "expected_exit": expected, "deciding_expectation_met": expected == run.returncode,
        "environment": {"interpreter": PYTHON, "PYTHONPATH": "src:tools", "shared_venv_read_only": True},
        "input_closure": "Frozen source and committed synthetic migration consumers; no real data or authority admission.",
        "stdout": bound(stdout), "stderr": bound(stderr), "output": str(stdout),
    }
    (SCRATCH / f"{name}.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    native = check("family-layout-frozen-native", [PYTHON, "-m", "pytest",
        "tests/unit/foundry/methods/catalog/mechanism/test_family_consumer_contract.py",
        "tests/unit/foundry/methods/catalog/mechanism/test_families.py",
        "tests/unit/foundry/mechanisms/test_mechanism_design.py",
        "tests/unit/foundry/contracts/test_layout.py", "tests/unit/foundry/compile/test_trinity_compiler.py",
        "-o", "addopts=", "-q", "-ra", "--basetemp", str(SCRATCH / "family-layout-frozen-tmp")])
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        removals = list(executor.map(lambda control: check(f"family-removal-{control}",
            [PYTHON, str(SCRATCH / "family_layout_removal_replay.py"), control], 1),
            ("catalog_is_ic", "family_owner", "layout_paths")))
    docs = check("family-layout-docs-backend", [PYTHON, "-m", "mkdocs", "--version"], 1, True)
    changed = subprocess.check_output(["git", "diff", "--name-only",
        "ad8f0f7532022014c028d74d872c93fe3349d220", SOURCE], cwd=ROOT, text=True).splitlines()
    report = {
        "source": SOURCE,
        "tree": subprocess.check_output(["git", "rev-parse", f"{SOURCE}^{{tree}}"], cwd=ROOT, text=True).strip(),
        "environment": json.loads((SCRATCH / "monitor-frozen-checks.json").read_text())["environment"],
        "changed_paths": changed, "source_inputs": [bound(ROOT / path) for path in changed],
        "checks": [native, *removals, docs],
        "native_and_removal_expectations_met": all(item["deciding_expectation_met"] for item in [native, *removals]),
        "docs_build": "UNRUN: MkDocs unavailable in admitted readonly application environment; preflight ERROR is not PASS.",
    }
    target = SCRATCH / "family-layout-frozen-checks.json"
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"receipt": str(target), "native_and_removal_expectations_met": report["native_and_removal_expectations_met"],
                     "checks": [{"name": item["name"], "outcome": item["outcome"], "wall_seconds": item["wall_seconds"]} for item in report["checks"]]}, indent=2))


if __name__ == "__main__":
    main()
