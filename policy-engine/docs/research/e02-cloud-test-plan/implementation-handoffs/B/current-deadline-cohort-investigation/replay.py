"""Replay one unchanged native case against frozen admitted root production."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET


ROOT = Path("/workspace/e02-B-current-coordination")
LANE = Path("/workspace/e02-B-current-execution-state")
OUT = LANE / "_build/current-execution-state/deadline-cohort-investigation/native"
SOURCE = "4e7a4924e6466e1b4eaa39b504435a1243aeb90b"
SELECTOR = "tests/unit/scientist/orchestration/engine/test_workflow_deadline_custody.py::test_workflow_cas_wait_cannot_admit_late_ref_or_next_producer[deadline-scientist.experiment_state]"


def git(root, *args):
    return subprocess.check_output(["git", "--no-optional-locks", *args], cwd=root)


def ref(path):
    b = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}


def main():
    observed_head_before = git(ROOT, "rev-parse", "HEAD").decode().strip()
    runtime_paths = ["policy-engine/src", "policy-engine/tests", "policy-engine/pytest.ini",
                     "policy-engine/pyproject.toml", "policy-engine/uv.lock"]
    assert not git(ROOT, "diff", "--name-only", SOURCE, "--", *runtime_paths)
    OUT.mkdir(parents=True)
    binding_paths = [
        "policy-engine/tests/unit/scientist/orchestration/engine/test_workflow_deadline_custody.py",
        "policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py",
        "policy-engine/src/polisyos/core/artifacts/async_store.py",
        "policy-engine/src/polisyos/common/async_tools.py",
        "policy-engine/src/polisyos/scientist/orchestration/engine/retry.py",
        "policy-engine/pytest.ini",
        "policy-engine/tests/conftest.py",
    ]
    bindings = []
    for path in binding_paths:
        expected = git(ROOT, "show", SOURCE + ":" + path)
        assert expected == (ROOT / path).read_bytes() == (LANE / path).read_bytes()
        bindings.append({"path": path, "target_source": SOURCE,
                         "sha256": hashlib.sha256(expected).hexdigest(), "bytes": len(expected)})
    profile = json.loads((ROOT / ".polisyos/e02-B-current/raw/review/final-B-cohort-profile.json").read_text())
    env = os.environ.copy()
    env.update({key: val for key, val in profile["environment"].items() if val is not None})
    env.pop("E02_B_COHORT_INVENTORY_PATH", None)
    for cap in profile["all_cap_names_absent_in_child"]:
        env.pop(cap, None)
    # Production imports use the immutable admitted root. Test input is the
    # byte-identical own-lane native file; all mutable outputs stay in this lane.
    argv = [str(ROOT / ".polisyos/e02-B-current/environment/bin/python"), "-m", "pytest", "-vv", SELECTOR,
            "--basetemp", str(OUT / "pytest"), "-o", "cache_dir=" + str(OUT / "pytest-cache"),
            "--junitxml=" + str(OUT / "cohort.xml")]
    started = time.perf_counter()
    with (OUT / "stdout.txt").open("wb") as handle:
        result = subprocess.run(argv, cwd=LANE / "policy-engine", env=env, stdout=handle, stderr=subprocess.STDOUT)
    wall = time.perf_counter() - started
    observed_head_after = git(ROOT, "rev-parse", "HEAD").decode().strip()
    assert not git(ROOT, "diff", "--name-only", SOURCE, "--", *runtime_paths)
    for binding in bindings:
        assert ref(ROOT / binding["path"])["sha256"] == binding["sha256"]
        assert ref(LANE / binding["path"])["sha256"] == binding["sha256"]
    cases = []
    if (OUT / "cohort.xml").exists():
        for case in ET.parse(OUT / "cohort.xml").iter("testcase"):
            state = "ERROR" if case.find("error") is not None else "FAIL" if case.find("failure") is not None else "SKIP" if case.find("skipped") is not None else "PASS"
            cases.append({**case.attrib, "state": state})
    receipt = {"schema": "policyos.e02.single_native_replay.v1", "target_source_sha": SOURCE,
               "target_tree_sha": git(ROOT, "rev-parse", SOURCE + "^{tree}").decode().strip(),
               "observed_root_head_before": observed_head_before,
               "observed_root_head_after": observed_head_after,
               "full_runtime_input_byte_equivalence_paths": runtime_paths,
               "test_lane_sha": git(LANE, "rev-parse", "HEAD").decode().strip(),
               "command": argv, "cwd": str(LANE / "policy-engine"),
               "environment": {key: env.get(key) for key in profile["environment"]},
               "all_cap_names_absent": profile["all_cap_names_absent_in_child"],
               "source_test_bindings": bindings, "source_test_unchanged": True,
               "exit_code": result.returncode, "wall_s": wall, "cases": cases,
               "stdout": ref(OUT / "stdout.txt"), "junit": ref(OUT / "cohort.xml"),
               "qualification": "One unmodified native input in unique own-lane scratch; root production/test/config bytes exactly4e before/after, observed later docs-only root HEAD separate. Same installed environment. Does not replace the original whole-cohort FAIL or reproduce its scheduler/load history."}
    (OUT / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
