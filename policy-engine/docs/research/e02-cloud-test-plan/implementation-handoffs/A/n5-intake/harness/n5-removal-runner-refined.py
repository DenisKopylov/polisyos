from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path("/Users/deniskopylov/.codex/worktrees/e02-a-n5-verify-current/polisyos/policy-engine")
PYTHON = Path("/Users/deniskopylov/.codex/worktrees/e02-a-full-queue/polisyos/policy-engine/.venv/bin/python")
HARNESS = Path('/Users/deniskopylov/.codex/worktrees/e02-a-full-queue/polisyos/policy-engine/_build/e02-A-full-queue/admission/n5-verify-current/n5_property_removal_probe_refined.py')
EVIDENCE_ROOT = Path(__file__).resolve().parent
SOURCE = PROJECT / "src/polisyos/runtime/quality/generation_cycle.py"
TEST = PROJECT / "tests/unit/remediation/test_cyc_02.py"

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> int:
    prop = sys.argv[1]
    evidence = EVIDENCE_ROOT / f"removal-refined-{prop}"
    evidence.mkdir(parents=True, exist_ok=False)
    basetemp = evidence / "pytest-basetemp"
    junit = evidence / "junit.xml"
    env = dict(os.environ)
    env.update({
        "PYTHONPATH": f"{PROJECT / 'src'}:{PROJECT}",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "JAX_PLATFORM_NAME": "cpu",
        "XLA_FLAGS": "--xla_cpu_multi_thread_eigen=false intra_op_parallelism_threads=1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
        "BLIS_NUM_THREADS": "1",
        "PYTEST_ADDOPTS": f"-c {PROJECT / 'pytest.ini'} --basetemp={basetemp} --junitxml={junit} --durations=0",
    })
    command = [str(PYTHON), str(HARNESS), "--project-root", str(PROJECT), "--property", prop]
    mutation_by_property = {
        "engine_selection": "replace len(selected_decisions) != 1 with len(selected_decisions) == 0; retain zero-selected fail-closed branch and source error marker, remove only uniqueness rejection",
        "sibling_receipt_hash": "bypass sibling receipt-payload-hash comparison in load_joint_simulation_result while retaining branch and error marker",
        "explicit_empty_atoms": "remove explicit-empty atom rejection terms in conditional consumer and loaded-result atom binding while retaining branch/error markers",
        "point_outcome_distribution": "bypass selected-outcome subset check against point.outcomes while retaining branch and error marker",
        "absent_atom_fallback": "bypass raw_atoms absence/fallback condition while retaining branch",
        "casless_digest": "bypass simulation_result_ref presence condition in simulation_evaluation_input_ref while retaining branch",
    }
    metadata = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "property": prop,
        "mutation": mutation_by_property[prop],
        "expected_behavioral_assertion_prefix": "removed_property_keep_markers:",
        "harness_sha256": sha256(HARNESS),
        "project_root": str(PROJECT),
        "working_directory": str(PROJECT),
        "python": str(PYTHON),
        "harness": str(HARNESS),
        "command": command,
        "pytest_config": str(PROJECT / "pytest.ini"),
        "pytest_addopts": env["PYTEST_ADDOPTS"],
        "controlled_environment": {key: env[key] for key in ("PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "PYTHONHASHSEED", "JAX_PLATFORM_NAME", "XLA_FLAGS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS", "PYTEST_ADDOPTS")},
        "source_sha256": sha256(SOURCE),
        "test_sha256": sha256(TEST),
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT.parent, capture_output=True, text=True, check=True).stdout.strip(),
        "git_tree": subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=PROJECT.parent, capture_output=True, text=True, check=True).stdout.strip(),
        "basetemp": str(basetemp),
        "junit": str(junit),
    }
    (evidence / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    start = time.monotonic()
    completed = subprocess.run(command, cwd=PROJECT, env=env, capture_output=True, text=True, check=False)
    elapsed = time.monotonic() - start
    (evidence / "stdout.txt").write_text(completed.stdout)
    (evidence / "stderr.txt").write_text(completed.stderr)
    (evidence / "exit_code.txt").write_text(f"{completed.returncode}\n")
    output = completed.stdout + completed.stderr
    expected_label = "removed_property_keep_markers:"
    passed = completed.returncode == 0 and "REMOVAL_PROBE=PASS" in output and expected_label in output
    result = {
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed,
        "harness_return_code": completed.returncode,
        "expected_removal_failure_label_present": expected_label in output,
        "pass": passed,
        "junit_available": junit.exists(),
        "junit_sha256": sha256(junit) if junit.exists() else None,
        "stdout_sha256": sha256(evidence / "stdout.txt"),
        "stderr_sha256": sha256(evidence / "stderr.txt"),
    }
    (evidence / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"property": prop, **result}, sort_keys=True))
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
