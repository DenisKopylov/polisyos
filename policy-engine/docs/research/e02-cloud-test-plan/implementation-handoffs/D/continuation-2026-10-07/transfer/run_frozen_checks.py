"""Run one explicitly pinned D transfer check, preserving complete deciding streams."""
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
source = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
tree = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD^{tree}"], text=True).strip()
status = subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True)
if source != expected or status:
    raise SystemExit("Pinned immutable D source/clean tree precondition failed")
scratch = Path(__file__).parent
receipt = Path(tempfile.mkdtemp(prefix="e02-D-transfer-"+mode+"-", dir="/dev/shm"))
(receipt/"tmp").mkdir()
base = "tests/unit/scientist/agent/test_vector_generation_consumer.py::"
selectors = {
 "empty4": [base+"test_persisted_empty_transfer_history_is_not_a_rejected_or_unavailable_intake"],
 "empty-removal4": [base+"test_persisted_empty_transfer_history_is_not_a_rejected_or_unavailable_intake"],
 "B333-pair2": [base+"test_exact_transfer_reference_beyond_1000_keys_survives_fresh_native_reader", base+"test_valid_cas_legacy_native_nonfinite_refuses_before_pointer_publication"],
 "B333-removal1": [base+"test_valid_cas_legacy_native_nonfinite_refuses_before_pointer_publication"],
}[mode]
python = "/workspace/e02-D-locked-env/bin/python"
argv = [python, "-m", "pytest", "-p", "no:cacheprovider", "-o", "junit_family=xunit1", "-o", "junit_logging=all", "-o", "junit_log_passing_tests=true", "--basetemp", str(receipt/"basetemp"), "--junitxml", str(receipt/"junit.xml"), "-q"]
paths = [str(root/"policy-engine/src"), str(root/"policy-engine")]
if mode.startswith("B333-"):
    paths.insert(0, str(scratch/"B333-pair"))
if mode == "empty-removal4":
    paths.insert(0, str(scratch))
    argv += ["-p", "remove_intake_distinction"]
if mode == "B333-removal1":
    paths.insert(0, "/dev/shm/e02-D-transfer-frozen469-06qbulta")
    argv += ["-p", "remove_private_finite"]
argv += selectors
env_patch = {"PYTHONDONTWRITEBYTECODE":"1", "TMPDIR":str(receipt/"tmp"), "PYTHONPATH":":".join(paths)}
if mode.startswith("B333-"):
    env_patch["E02_CAS_PAIR_ORIGINS"] = str(receipt/"module-origins")
inputs = {}
for rel in ["policy-engine/tests/unit/scientist/agent/test_vector_generation_consumer.py", "policy-engine/tests/unit/scientist/agent/vector_generation_reader.py", "policy-engine/tests/unit/scientist/methods/search/strategies/test_transfer.py", "policy-engine/src/polisyos/scientist/agent/vector_memory.py", "policy-engine/src/polisyos/scientist/methods/search/strategies/transfer.py", "policy-engine/src/polisyos/scientist/methods/autotune/warm_start.py", "policy-engine/src/polisyos/core/artifacts/store.py", "policy-engine/src/polisyos/core/artifacts/_integrity_ops.py"]:
    inputs[rel] = subprocess.check_output(["git", "-C", str(root), "rev-parse", source+":"+rel], text=True).strip()
fixture_files = [Path(__file__)]
if mode.startswith("B333-"):
    fixture_files += [scratch/"B333-pair/sitecustomize.py", scratch/"B333-pair/B333-module-map.json"]
if mode == "empty-removal4":
    fixture_files += [scratch/"remove_intake_distinction.py"]
if mode == "B333-removal1":
    fixture_files += [Path("/dev/shm/e02-D-transfer-frozen469-06qbulta/remove_private_finite.py")]
launch = {"argv":argv, "cwd":str(root/"policy-engine"), "source":source, "tree":tree, "status_porcelain":status, "mode":mode, "environment_overrides":env_patch, "inputs":inputs, "fixture_inputs":[{"path":str(f), "sha256":hashlib.sha256(f.read_bytes()).hexdigest(), "bytes":f.stat().st_size} for f in fixture_files], "backend_profile":"actual HNSW0.8.0, NumPy2.3.5, Python3.14.7 locked environment; ordinary FileSystemCAS exact refs", "seed_inputs":"Native default100, original deterministic measured2 donor rows; explicit empty/invalid/unsupported codec controls or ordinary1002 discovery snapshots, no production or scientific authority", "compute_limits_introduced":False, "classification":"combined_dependency_profile" if mode.startswith("B333-") else "current_D_persisted_intake_control", "accepted_in_G":False, "start_utc":datetime.now(timezone.utc).isoformat()}
if mode.startswith("B333-"):
    launch["B_canonical_module_map"] = json.loads((scratch/"B333-pair/B333-module-map.json").read_text())
(receipt/"launch.json").write_text(json.dumps(launch, indent=2)+"\n")
env = os.environ.copy(); env.update(env_patch)
start = time.monotonic()
with (receipt/"stdout.txt").open("w") as stdout, (receipt/"stderr.txt").open("w") as stderr:
    result = subprocess.run(argv, cwd=root/"policy-engine", env=env, stdout=stdout, stderr=stderr)
origin_admission = None
if mode.startswith("B333-"):
    mapped = json.loads((scratch/"B333-pair/B333-module-map.json").read_text())
    origin_groups = []
    for f in sorted(receipt.glob("module-origins.*.jsonl")):
        rows = [json.loads(line) for line in f.read_text().splitlines()]
        actual = {row["module"]:row for row in rows}
        valid = set(actual) == set(mapped["modules"]) and all(
            actual[name]["source"] == mapped["source"]
            and actual[name]["sha256"] == required["B_sha256"]
            and actual[name]["blob"] == required["B_blob"]
            and actual[name]["bytes"] == required["B_bytes"]
            for name, required in mapped["modules"].items()
        )
        origin_groups.append({"path":str(f), "valid":valid, "pid":rows[0]["pid"] if rows else None, "modules":sorted(actual)})
    minimum_processes = 4 if mode == "B333-pair2" else 1
    origin_admission = {"groups":origin_groups, "minimum_processes":minimum_processes,
                        "accepted":len(origin_groups)>=minimum_processes and all(row["valid"] for row in origin_groups)}
    (receipt/"origin-admission.json").write_text(json.dumps(origin_admission,indent=2)+"\n")
source_after = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
status_after = subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True)
(receipt/"exit.json").write_text(json.dumps({"returncode":result.returncode, "elapsed_seconds":time.monotonic()-start, "end_utc":datetime.now(timezone.utc).isoformat(), "source_after":source_after, "status_after":status_after, "combined_source_admission":origin_admission},indent=2)+"\n")
print(json.dumps({"receipt":str(receipt), "returncode":result.returncode, "source":source, "source_unchanged":source_after==source and not status_after}))
print((receipt/"stdout.txt").read_text()[-2500:])
