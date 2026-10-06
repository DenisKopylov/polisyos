"""Execute exact tracked CAS inputs; no process quota or new Git checkout."""
from __future__ import annotations
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import tarfile
import time
from pathlib import Path

SOURCE = "441f79f173df5e0d2a08c161120e634bb0e4f5aa"
BASE = "6b0e799678e3538bb8940b8a4fd6374c6249a3f3"
PYTHON = "/workspace/polisyos/policy-engine/.venv/bin/python"
PRODUCT = Path(__file__).resolve().parents[2]
ROOT = PRODUCT.parent
SCRATCH = PRODUCT / "_build/e02-B-current-cas-generation"
RAW = SCRATCH / "raw"
TEST = "tests/unit/core/artifacts/test_batch_completion_admission.py"
COHORT = [TEST,
 "tests/unit/core/artifacts/test_verification_snapshot_report.py",
 "tests/unit/core/artifacts/test_cas_integrity_report.py",
 "tests/unit/remediation/test_cas_03.py", "tests/unit/remediation/test_cas_02.py",
 "tests/unit/core/artifacts/test_import_admission_noop.py",
 "tests/unit/core/artifacts/test_put_integrity_retry.py",
 "tests/unit/core/artifacts/test_transfer_generation_publication.py",
 "tests/unit/core/artifacts/test_caching_write_through_exact_bytes.py",
 "tests/unit/core/artifacts/backends/test_caching_store.py",
 "tests/unit/core/artifacts/test_multi_tenant_shared_cas.py",
 "tests/unit/core/phase0/test_signing.py", "tests/unit/core/phase0/test_store_signing.py",
 "tests/unit/core/phase0/test_cli_signing.py"]
MODULES = ["src/polisyos/core/artifacts/" + p for p in
 ["store.py", "_signature_ops.py", "_integrity_ops.py", "signing.py", "_transfer_ops.py"]]
MODULES += ["src/polisyos/core/components/_cli_crypto.py"]

def git(*args):
    return subprocess.check_output(["/usr/bin/git", *args], cwd=ROOT)

def run(tag, cwd, argv, *, target=SOURCE, removal=None, closure=None):
    env = dict(os.environ, PYTHONPATH="src")
    env.pop("E02_B_PROPERTY_REMOVAL", None)
    if removal:
        env["E02_B_PROPERTY_REMOVAL"] = removal
    started = time.monotonic()
    with (RAW / (tag + ".txt")).open("wb") as output:
        child = subprocess.Popen(argv, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT)
        waited, status, usage = os.wait4(child.pid, 0)
        if waited != child.pid:
            raise RuntimeError("wait4 returned wrong child")
        child.returncode = os.waitstatus_to_exitcode(status)
    rec = dict(target_sha=target, target_tree=git("rev-parse", target+"^{tree}").decode().strip(),
      cwd=str(cwd), argv=argv, python=PYTHON, python_version=platform.python_version(),
      platform=platform.platform(), PYTHONPATH="src", property_removal=removal,
      returncode=child.returncode, wall_s=time.monotonic()-started, max_rss_kib=usage.ru_maxrss,
      runner_quota=None, rusage_boundary="os.wait4 exact child PID kernel child/descendant accounting; not VM peak",
      input_closure=closure or {"source_and_test_sha": SOURCE,
        "files": [{"ref": "policy-engine/"+p+"@"+SOURCE,
                   "sha256": hashlib.sha256((PRODUCT/p).read_bytes()).hexdigest()}
                  for p in sorted(set(COHORT+MODULES+["tests/unit/core/artifacts/batch_duplicate_worker.py","pytest.ini","pyproject.toml","uv.lock"]))]})
    (RAW/(tag+".run.json")).write_text(json.dumps(rec, indent=2)+"\n")
    print(json.dumps({k: rec[k] for k in ["target_sha","returncode","wall_s","max_rss_kib"]})+" "+tag, flush=True)

def pytest(tag, cwd, inputs, **kwargs):
    run(tag, cwd, [PYTHON,"-m","pytest","-o","addopts=","-q","--tb=short",
      "--import-mode=importlib","--strict-markers","-ra",
      "--benchmark-storage=file://./_cache/benchmarks",*inputs,
      "--basetemp="+str(SCRATCH/(tag+"-tmp")),"-o","cache_dir="+str(SCRATCH/(tag+"-cache")),
      "--junitxml="+str(RAW/(tag+".xml"))], **kwargs)

mode = sys.argv[1]
if mode == "delta":
    pytest("batch-delta-frozen",PRODUCT,[TEST])
    run("batch-delta-mypy",PRODUCT,[PYTHON,"-m","mypy","--follow-imports=silent",*MODULES])
    static=MODULES+[TEST,"tests/unit/core/artifacts/batch_duplicate_worker.py","tests/unit/remediation/test_cas_03.py"]
    run("batch-delta-ruff",PRODUCT,[PYTHON,"-m","ruff","check",*static])
    run("batch-delta-format",PRODUCT,[PYTHON,"-m","ruff","format","--check",*static])
elif mode == "current":
    if git("rev-parse","HEAD").decode().strip() != SOURCE:
        raise RuntimeError("execution checkout is not frozen source")
    for p in COHORT+MODULES+["tests/unit/core/artifacts/batch_duplicate_worker.py"]:
        if (PRODUCT/p).read_bytes() != git("show",SOURCE+":policy-engine/"+p):
            raise RuntimeError("live input differs from immutable source: "+p)
    pytest("batch-release-frozen", PRODUCT, COHORT)
    complete = ["test_real_full_batch_all_confirmations_are_required",
      "test_local_corruption_preserves_full_typed_results_and_refuses_admission",
      "test_cancel_preserves_actual_finished_item_and_explicit_abort",
      "test_deadline_stops_lazy_inventory_before_more_real_verification",
      "test_actual_import_publisher_refuses_unbound_per_item_report",
      "test_global_basis_loss_preserves_finished_row_and_aborts",
      "test_cancel_interrupts_actual_default_name_census",
      "test_selected_and_default_same_blob_remain_two_exact_confirmations"]
    pytest("batch-release-remove-completeness", PRODUCT, [TEST+"::"+n for n in complete], removal="cas-batch-completeness")
    stop = ["test_cancel_preserves_actual_finished_item_and_explicit_abort",
      "test_deadline_stops_lazy_inventory_before_more_real_verification",
      "test_cancel_interrupts_actual_default_name_census",
      "test_late_real_signer_cannot_start_signature_publication",
      "test_duplicate_intake_obeys_each_supplied_item_budget"]
    pytest("batch-release-remove-stop", PRODUCT, [TEST+"::"+n for n in stop], removal="cas-batch-stop")
    pytest("batch-release-remove-window", PRODUCT, [TEST+"::test_real_forty_item_source_waits_for_a_bounded_pending_window"], removal="cas-batch-window")
    run("batch-release-mypy-frozen", PRODUCT,[PYTHON,"-m","mypy","--follow-imports=silent",*MODULES])
elif mode in {"base", "duplicate-base"}:
    if mode == "duplicate-base":
        BASE = "714d602bce509a21e8aa4aabbcca684d505562a4"
    paths = ["policy-engine/"+p for p in ["src","tests","pytest.ini","pyproject.toml","uv.lock"]]
    archive = git("archive", BASE, *paths)
    snapshot = SCRATCH/("batch-release-base-input" if mode=="base" else "batch-duplicate-release-base-input")
    snapshot.mkdir(exist_ok=False)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        source.extractall(snapshot, filter="data")
    overlay_path = "policy-engine/"+TEST
    overlay = git("show",SOURCE+":"+overlay_path)
    (snapshot/overlay_path).write_bytes(overlay)
    worker_path = "policy-engine/tests/unit/core/artifacts/batch_duplicate_worker.py"
    worker = git("show",SOURCE+":"+worker_path)
    (snapshot/worker_path).write_bytes(worker)
    closure = {"base_sha":BASE,"archive": {"paths":paths,"bytes":len(archive),
      "sha256":hashlib.sha256(archive).hexdigest()}, "overlay": {"ref":overlay_path+"@"+SOURCE,
      "sha256":hashlib.sha256(overlay).hexdigest()},
      "worker_overlay": {"ref":worker_path+"@"+SOURCE,"sha256":hashlib.sha256(worker).hexdigest()},
      "custody_boundary":"Tracked projection inside admitted CAS lane ignored scratch; no new Git worktree or precreation claim."}
    for p in MODULES:
        if (snapshot/"policy-engine"/p).read_bytes()!=git("show",BASE+":policy-engine/"+p):
            raise RuntimeError("baseline source differs")
    if mode=="base":
        pytest("batch-release-base-replay", snapshot/"policy-engine", [TEST], target=BASE, closure=closure)
        run("batch-release-base-mypy", snapshot/"policy-engine", [PYTHON,"-m","mypy","--follow-imports=silent",*MODULES], target=BASE, closure=closure)
    else:
        pytest("batch-duplicate-release-base-replay", snapshot/"policy-engine", [TEST,"-k","duplicate_intake"], target=BASE, closure=closure)
else:
    raise ValueError(mode)
