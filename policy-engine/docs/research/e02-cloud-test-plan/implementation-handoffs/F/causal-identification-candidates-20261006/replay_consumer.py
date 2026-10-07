"""Read-only native replayer; retained output, not copied product source."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path("/workspace/e02-F-tmle-20261006")
SCRATCH = Path(__file__).resolve().parent
G_SHA = "363e7ae0cb2929a92d9667334fdc0ac3087daf5e"
IMPL = "f460bd81b8124be58f890f59a53e2aba9e7ceb76"
PYTHON = "/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python"
TEST = SCRATCH / "test_causal_identification_consumer.py"
ARGV = [PYTHON, "-m", "pytest", "-o", "addopts=", "-q", "-s", str(TEST),
        "tests/unit/foundry/methods/test_value_evidence.py::test_projection_binding_is_intrinsically_nonproduction",
        "tests/unit/foundry/methods/test_value_evidence.py::test_verified_native_intervals_remain_projectable"]


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def digest(data: bytes) -> dict[str, object]:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main() -> None:
    assert git("rev-parse", "HEAD").decode().strip() == IMPL
    assert git("status", "--porcelain=v1") == b""
    providers = []
    for relative in (
        "policy-engine/src/polisyos/ir/analytics/causal.py",
        "policy-engine/src/polisyos/ir/analytics/uncertainty.py",
        "policy-engine/src/polisyos/scientist/governance/passes/confidence_pass.py",
        "policy-engine/src/polisyos/foundry/methods/components/value_evidence.py",
        "policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py",
        "policy-engine/tests/unit/foundry/methods/test_value_evidence.py",
    ):
        own = git("show", f"{IMPL}:{relative}")
        current = (ROOT / relative).read_bytes()
        original = git("show", f"{G_SHA}:{relative}")
        assert current == own
        providers.append({"path": relative, "own_blob": git("rev-parse", f"{IMPL}:{relative}").decode().strip(),
                          "G_blob": git("rev-parse", f"{G_SHA}:{relative}").decode().strip(),
                          "own_matches_G": own == original, **digest(current)})
    env = dict(os.environ, PYTHONPATH="src:.")
    start = time.monotonic()
    completed = subprocess.run(ARGV, cwd=ROOT / "policy-engine", env=env, capture_output=True)
    wall = time.monotonic() - start
    output = {}
    for name, data in (("stdout", completed.stdout), ("stderr", completed.stderr)):
        path = SCRATCH / f"consumer-final-deciding.{name}.txt"
        path.write_bytes(data)
        output[name] = {"path": str(path), **digest(data)}
    record = {
        "scope": "Current shared report/uncertainty/ConfidencePass native provider replay; not whole G Runtime native",
        "source_sha": IMPL, "source_tree": git("rev-parse", f"{IMPL}^{{tree}}").decode().strip(),
        "G_candidate_sha": G_SHA, "providers": providers,
        "argv": ARGV, "cwd": str(ROOT / "policy-engine"), "env": {"PYTHONPATH": "src:."},
        "exit_code": completed.returncode, "wall_seconds": wall, "output": output,
        "test_replayer": {"path": str(TEST), **digest(TEST.read_bytes())},
        "python": {"executable": sys.executable, "version": sys.version,
                   "platform": platform.platform(),
                   "pytest": importlib.metadata.version("pytest"),
                   "pydantic": importlib.metadata.version("pydantic")},
        "historical_harness_limits": [
            "consumer-class-red: invalid ComputeBackend.CPU fixture; other negatives include missing PutOptions",
            "consumer-class-deciding: two direct intake fixture TypeErrors from missing PutOptions",
            "consumer-final-red: two direct raw PutOptions fixtures blocked by canonical forbid_floats policy",
            "direct-consumer-deciding: corrected canonical persistence establishes the two actual counterexamples",
            "consumer-deciding: new resolved-proof fixture missing required ProofBundle fields; 9 actual negatives +9 controls established",
        ],
    }
    path = SCRATCH / "consumer-final-deciding.json"
    path.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"exit_code": completed.returncode, "wall_seconds": wall,
                      "receipt": str(path), "providers_equal_G": all(row["own_matches_G"] for row in providers)}))


if __name__ == "__main__":
    main()
