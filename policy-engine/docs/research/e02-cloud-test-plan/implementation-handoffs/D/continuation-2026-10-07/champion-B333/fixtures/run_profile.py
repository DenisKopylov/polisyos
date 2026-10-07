"""Run the reviewed bounded sync profile at one clean immutable D source."""

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time

root = Path("/dev/shm/e02-D-oct07-continuation")
expected, mode = sys.argv[1:]
scratch = Path(__file__).parent
pair = Path("/dev/shm/e02-D-transfer-empty-intake-w7x85jux/B333-pair")


def git(*args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


source = git("rev-parse", "HEAD")
tree = git("rev-parse", "HEAD^{tree}")
status = git("status", "--porcelain")
if source != expected or status:
    raise SystemExit("Exact clean immutable D source precondition failed")
receipt = Path(tempfile.mkdtemp(prefix="e02-D-champion-" + mode + "-", dir="/dev/shm"))
(receipt / "tmp").mkdir()
base = "tests/unit/scientist/methods/autotune/test_champion_verified_snapshot.py::"
selectors = {
    "B333-combined5": [
        base
        + "test_native_evaluator_registry_and_fresh_process_read_exact_profiles_and_immutable_inputs",
        base
        + "test_actual_reused_content_keeps_old_qualified_view_and_refuses_wrong_candidate_profile",
        base
        + "test_competing_native_writer_refuses_actual_stale_pair_after_lock_held_reread",
        str(scratch / "test_combined_champion.py")
        + "::test_actual_owner_lock_blocks_child_publication_then_current_basis_commits",
        str(scratch / "test_combined_champion.py")
        + "::test_same_exact_evaluation_ref_changed_bytes_refuses_without_pointer_effect",
    ],
    "B333-lock-removal1": [
        str(scratch / "test_combined_champion.py")
        + "::test_actual_owner_lock_blocks_child_publication_then_current_basis_commits",
    ],
}[mode]
argv = [
    "/workspace/e02-D-locked-env/bin/python",
    "-m",
    "pytest",
    "-p",
    "no:cacheprovider",
    "-p",
    "champion_receipts",
    "-o",
    "junit_family=xunit1",
    "-o",
    "junit_logging=all",
    "-o",
    "junit_log_passing_tests=true",
    "--basetemp",
    str(receipt / "basetemp"),
    "--junitxml",
    str(receipt / "junit.xml"),
    "-q",
    *selectors,
]
env_patch = {
    "PYTHONDONTWRITEBYTECODE": "1",
    "TMPDIR": str(receipt / "tmp"),
    "PYTHONPATH": ":".join(
        [
            str(pair),
            str(scratch),
            str(root / "policy-engine/src"),
            str(root / "policy-engine"),
        ]
    ),
    "E02_CHAMPION_REPOSITORY": str(root),
    "E02_CHAMPION_EVIDENCE": str(receipt),
    "E02_CAS_PAIR_ORIGINS": str(receipt / "module-origins"),
}
if mode == "B333-lock-removal1":
    env_patch["E02_REMOVE_CHAMPION_LOCK"] = "1"
paths = [
    "policy-engine/src/polisyos/scientist/methods/autotune/registry.py",
    "policy-engine/src/polisyos/scientist/methods/autotune/models.py",
    "policy-engine/src/polisyos/scientist/methods/autotune/runtime.py",
    "policy-engine/tests/unit/scientist/methods/autotune/test_champion_verified_snapshot.py",
    "policy-engine/tests/conftest.py",
    "policy-engine/pyproject.toml",
]
mapped = json.loads((pair / "B333-module-map.json").read_text())
files = [
    Path(__file__),
    scratch / "test_combined_champion.py",
    scratch / "champion_receipts.py",
    pair / "sitecustomize.py",
    pair / "B333-module-map.json",
]
launch = {
    "argv": argv,
    "cwd": str(root / "policy-engine"),
    "source": source,
    "tree": tree,
    "mode": mode,
    "classification": "combined_dependency_profile",
    "accepted_in_G": False,
    "B_exact_source": mapped["source"],
    "B_module_map": mapped,
    "D_inputs": {
        path: {
            "blob": git("rev-parse", source + ":" + path),
            "sha256": hashlib.sha256((root / path).read_bytes()).hexdigest(),
        }
        for path in paths
    },
    "fixture_inputs": [
        {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
        for path in files
    ],
    "environment_overrides": env_patch,
    "start_utc": datetime.now(timezone.utc).isoformat(),
    "backend": "actual canonical B333 FileSystemCAS + current D ChampionRegistry local POSIX lock/atomic pointer; Python3.14.7 locked profile",
    "inputs_and_law": "Existing controlled two-row immutable dataset/split, fixture value times holdout weight; actual evaluations 1/2/3. No production quality or evaluator appointment asserted.",
    "compute_limits_introduced": False,
    "barrier_timeout_scope": "0.5s observes the actual lock-held publication refusal; 10s child completion guard. No numerical CPU/worker/process quota.",
    "remaining_scope": [
        "not whole B adoption",
        "not a default factory integration candidate",
        "not distributed/power-loss publication guarantee",
        "not original OPT04 formal closure or G acceptance",
    ],
}
(receipt / "launch.json").write_text(json.dumps(launch, indent=2) + "\n")
env = os.environ.copy()
env.update(env_patch)
start = time.monotonic()
with (
    (receipt / "stdout.txt").open("w") as stdout,
    (receipt / "stderr.txt").open("w") as stderr,
):
    result = subprocess.run(
        argv, cwd=root / "policy-engine", env=env, stdout=stdout, stderr=stderr
    )
groups = []
for path in sorted(receipt.glob("module-origins.*.jsonl")):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    actual = {row["module"]: row for row in rows}
    valid = set(actual) == set(mapped["modules"]) and all(
        actual[name]["source"] == mapped["source"]
        and actual[name]["blob"] == required["B_blob"]
        and actual[name]["sha256"] == required["B_sha256"]
        and actual[name]["bytes"] == required["B_bytes"]
        for name, required in mapped["modules"].items()
    )
    groups.append(
        {
            "path": str(path),
            "pid": rows[0]["pid"] if rows else None,
            "valid": valid,
            "modules": sorted(actual),
        }
    )
minimum = 9 if mode == "B333-combined5" else 2
origin = {
    "groups": groups,
    "minimum_processes": minimum,
    "accepted": len(groups) >= minimum and all(row["valid"] for row in groups),
}
(receipt / "origin-admission.json").write_text(json.dumps(origin, indent=2) + "\n")
after_source = git("rev-parse", "HEAD")
after_status = git("status", "--porcelain")
exit_result = {
    "returncode": result.returncode,
    "elapsed_seconds": time.monotonic() - start,
    "end_utc": datetime.now(timezone.utc).isoformat(),
    "source_after": after_source,
    "status_after": after_status,
    "source_unchanged": after_source == source and not after_status,
    "origin_admission": origin,
}
(receipt / "exit.json").write_text(json.dumps(exit_result, indent=2) + "\n")
print(json.dumps({"receipt": str(receipt), **exit_result}))
print((receipt / "stdout.txt").read_text()[-2500:])
