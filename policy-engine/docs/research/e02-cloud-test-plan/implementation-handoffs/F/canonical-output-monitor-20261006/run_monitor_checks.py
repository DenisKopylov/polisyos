"""Record complete native and memory-only property removal executions."""

from __future__ import annotations

import concurrent.futures
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path("/workspace/e02-F-fry-20261006")
CWD = ROOT / "policy-engine"
SCRATCH = Path("/tmp/e02-F-continuation-20261006/foundry")
PYTHON = "/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python"
SOURCE = "ec6944c8c5b4807f291c96919309472de60de127"


def artifact(path: Path) -> dict:
    content = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}


def check(name: str, argv: list[str], expected_exit: int = 0) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src:tools"
    before = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if before != SOURCE:
        raise RuntimeError(f"Wrong frozen implementation: {before}")
    started = time.monotonic()
    run = subprocess.run(argv, cwd=CWD, env=env, capture_output=True)
    wall = time.monotonic() - started
    stdout = SCRATCH / f"{name}.stdout.txt"
    stderr = SCRATCH / f"{name}.stderr.txt"
    stdout.write_bytes(run.stdout)
    stderr.write_bytes(run.stderr)
    after = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    receipt = {
        "name": name, "argv": argv, "command": " ".join(argv), "cwd": str(CWD),
        "target_sha": SOURCE, "after_sha": after, "wall_seconds": wall,
        "exit_code": run.returncode, "expected_exit_code": expected_exit,
        "outcome": "PASS" if run.returncode == 0 else "FAIL" if run.returncode == 1 else "ERROR",
        "deciding_expectation_met": run.returncode == expected_exit,
        "environment": {"python": PYTHON, "PYTHONPATH": "src:tools", "shared_venv_read_only": True},
        "input_closure": "Frozen native source and committed synthetic tests; removal changes Python objects in memory only.",
        "stdout": artifact(stdout), "stderr": artifact(stderr), "output": str(stdout),
    }
    (SCRATCH / f"{name}.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> None:
    native = [PYTHON, "-m", "pytest", "tests/unit/foundry/methods/backends/test_dispatch_output_contract.py",
              "tests/unit/foundry/methods/test_output_monitor.py",
              "tests/unit/foundry/methods/backends/test_backends.py",
              "-o", "addopts=", "-q", "-ra", "--basetemp", str(SCRATCH / "monitor-frozen-tmp")]
    checks = [check("monitor-frozen-native", native)]
    controls = ("raw_keys", "no_raw_numeric", "no_slot_keys", "no_array_types", "metadata_float", "no_flags")
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(controls)) as executor:
        checks += list(executor.map(
            lambda control: check(f"monitor-removal-{control}",
                                  [PYTHON, str(SCRATCH / "monitor_removal_replay.py"), control], 1),
            controls,
        ))
    versions = {}
    for package in ("numpy", "jax", "jaxlib", "scipy", "scikit-learn", "statsmodels", "pytest", "pymc", "dowhy", "econml"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not_installed"
    changed = subprocess.check_output(["git", "diff", "--name-only", "f4fa51e6dd247cfd967450263579d67233a743d6", SOURCE], cwd=ROOT, text=True).splitlines()
    summary = {
        "schema": "policyos.e02.foundry_monitor_run.v1", "implementation_sha": SOURCE,
        "implementation_tree": subprocess.check_output(["git", "rev-parse", f"{SOURCE}^{{tree}}"], cwd=ROOT, text=True).strip(),
        "environment": {"interpreter": PYTHON, "python": sys.version, "platform": platform.platform(),
                        "packages": versions, "thread_environment": {key: os.environ.get(key) for key in
                            ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "XLA_FLAGS")},
                        "cloud_quota_introduced": False},
        "source_inputs": [artifact(ROOT / path) for path in changed],
        "checks": checks,
        "all_deciding_expectations_met": all(item["deciding_expectation_met"] for item in checks),
    }
    target = SCRATCH / "monitor-frozen-checks.json"
    target.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"receipt": str(target), "all_deciding_expectations_met": summary["all_deciding_expectations_met"],
                      "checks": [{"name": item["name"], "outcome": item["outcome"], "wall_seconds": item["wall_seconds"]} for item in checks]}, indent=2))


if __name__ == "__main__":
    main()
