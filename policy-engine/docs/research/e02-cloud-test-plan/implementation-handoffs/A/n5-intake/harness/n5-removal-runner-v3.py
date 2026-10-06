from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path("/Users/deniskopylov/.codex/worktrees/e02-a-n5-verify-current/polisyos/policy-engine")
PYTHON = Path("/Users/deniskopylov/.codex/worktrees/e02-a-full-queue/polisyos/policy-engine/.venv/bin/python")
HARNESS = Path('/Users/deniskopylov/.codex/worktrees/e02-a-full-queue/polisyos/policy-engine/_build/e02-A-full-queue/admission/n5-verify-current/n5_property_removal_probe_refined_v3.py')
EVIDENCE_ROOT = Path(__file__).resolve().parent
SOURCE = PROJECT / "src/polisyos/runtime/quality/generation_cycle.py"
TEST = PROJECT / "tests/unit/remediation/test_cyc_02.py"

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

EXPECTED_ASSERTION = {
    "engine_selection": "removed_property_keep_markers:n8_negative_admitted:identity_multiple_selected_decisions",
    "sibling_receipt_hash": "removed_property_keep_markers:n8_negative_admitted:sibling_digest_mismatch",
    "explicit_empty_atoms": "removed_property_keep_markers:n8_negative_admitted:explicit_empty_candidate_atoms",
    "point_outcome_distribution": "removed_property_keep_markers:n8_negative_admitted:missing_selected_point_outcome",
    "absent_atom_fallback": "removed_property_keep_markers:absent_atom_fallback_lost:",
    "casless_digest": "removed_property_keep_markers:casless_digest_admitted_before_fallback:",
}
EXPECTED_HITS = {key: (2 if key == "explicit_empty_atoms" else 1) for key in EXPECTED_ASSERTION}
TEST_NAME = "test_n5_fresh_process_readback_binds_default_n8_to_cas_identity"


def main() -> int:
    prop = sys.argv[1]
    evidence = EVIDENCE_ROOT / f"removal-refined-v3-{prop}"
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
        "absent_atom_fallback": "replace fallback atom tuple with an empty tuple while retaining the raw_atoms-is-None branch and markers",
        "casless_digest": "bypass simulation_result_ref presence condition in simulation_evaluation_input_ref while retaining branch",
    }
    metadata = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "property": prop,
        "probe_revision": "v3 exact JUnit/assertion/mutation-hit classifier; absent-atom fallback replaced by empty tuple",
        "mutation": mutation_by_property[prop],
        "expected_behavioral_assertion": EXPECTED_ASSERTION[prop],
        "expected_mutation_hits": EXPECTED_HITS[prop],
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
    expected_label = EXPECTED_ASSERTION[prop]
    mutation_marker = f"removed_property_keep_markers:mutation_applied:{prop}:{EXPECTED_HITS[prop]}"
    junit_observation: dict[str, object] = {"available": False}
    junit_valid = False
    if junit.exists():
        junit_root = ET.parse(junit).getroot()
        cases = list(junit_root.iter("testcase"))
        target_cases = [case for case in cases if case.attrib.get("name") == TEST_NAME]
        total_failures = [failure for case in cases for failure in case.findall("failure")]
        total_errors = [error for case in cases for error in case.findall("error")]
        target_case = target_cases[0] if len(target_cases) == 1 else None
        failure = target_case.find("failure") if target_case is not None else None
        error = target_case.find("error") if target_case is not None else None
        failure_text = ""
        if failure is not None:
            failure_text = "\n".join(
                part for part in (failure.attrib.get("message", ""), failure.text or "") if part
            )
        junit_observation = {
            "available": True,
            "testcase_count": len(cases),
            "target_testcase_count": len(target_cases),
            "target_testcase": target_case.attrib if target_case is not None else None,
            "target_has_failure": failure is not None,
            "target_has_error": error is not None,
            "all_failure_count": len(total_failures),
            "all_error_count": len(total_errors),
            "expected_behavioral_assertion_present": expected_label in failure_text,
            "failure_message": failure.attrib.get("message", "") if failure is not None else None,
        }
        junit_valid = (
            len(cases) == 1
            and len(target_cases) == 1
            and failure is not None
            and error is None
            and target_case.find("skipped") is None
            and len(total_failures) == 1
            and len(total_errors) == 0
            and expected_label in failure_text
        )
    mutation_applied = mutation_marker in output
    passed = (
        completed.returncode == 0
        and "REMOVAL_PROBE=PASS" in output
        and mutation_applied
        and junit_valid
    )
    result = {
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed,
        "harness_return_code": completed.returncode,
        "expected_behavioral_assertion": expected_label,
        "expected_behavioral_assertion_in_junit_failure": bool(junit_observation.get("expected_behavioral_assertion_present", False)),
        "mutation_applied_marker_present_with_expected_hit_count": mutation_applied,
        "junit_valid_target_failure_no_collection_error": junit_valid,
        "junit_observation": junit_observation,
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
