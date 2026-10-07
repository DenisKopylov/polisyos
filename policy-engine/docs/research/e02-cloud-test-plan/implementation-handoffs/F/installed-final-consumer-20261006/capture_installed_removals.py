"""Capture cheap real installed failure probes; never repeat numerical workers."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

config_path = Path(sys.argv[1]).resolve()
config = json.loads(config_path.read_text())
kind = sys.argv[2]
assert kind in ("wheel", "sdist")
root = Path(config["source_root"])
review = Path(config["review_scratch"])
carrier = Path(config["scratch"]) / (kind + "-consumer")
site = Path(config["sites"][kind])
base = Path(__file__).parent
targets = [site / "polisyos/foundry/methods/backends/dispatch.py",
           site / "polisyos/foundry/methods/lifecycle/output_monitor.py"]
before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in targets}

def guard():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root).decode().strip() == config["source_sha"]
    assert subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root).decode().strip() == config["source_tree"]
    assert not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root)
    assert {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in targets} == before

environment = os.environ.copy()
environment.pop("PYTHONPATH", None)
environment["PYTHONDONTWRITEBYTECODE"] = "1"
records = []
for mode in ("raw_keys", "no_raw_numeric", "no_consumption", "broad_identity_skip"):
    guard()
    script = base / ("remove_installed_monitor_property.py" if mode in ("raw_keys", "no_raw_numeric")
                     else "remove_installed_count_property.py")
    argv = [config["installed_pythons"][kind], "-I", str(script), str(config_path), kind, mode]
    started = time.monotonic()
    result = subprocess.run(argv, cwd=carrier, env=environment, capture_output=True)
    record = {"source_sha": config["source_sha"], "source_tree": config["source_tree"],
              "profile": kind, "mode": mode, "argv": argv, "cwd": str(carrier),
              "environment": {"PYTHONPATH": "absent", "PYTHONDONTWRITEBYTECODE": "1"},
              "exit_code": result.returncode, "wall_seconds": time.monotonic() - started,
              "peak_children_rss_kib_cumulative_process": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
              "installed_source_hashes_before_and_after": before,
              "replayer_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
              "expected": "Actual assertion FAIL detects removed implementation with function identity/name/doc/signature retained; no worker or estimator repeat."}
    for stream, raw in (("stdout", result.stdout), ("stderr", result.stderr)):
        path = review / (kind + "-removal-" + mode + "." + stream + ".txt")
        assert not path.exists()
        path.write_bytes(raw)
        record[stream] = {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    guard()
    records.append(record)
    (review / (kind + "-removals.json")).write_text(json.dumps(records, indent=2) + "\n")
    assert result.returncode == 1, record
    assert b" failed" in result.stdout and b"ERROR " not in result.stdout and b" skipped" not in result.stdout, record
print(json.dumps({"source_sha": config["source_sha"], "profile": kind,
                  "actual_negative_runs": len(records), "all_detected_with_exit1": True,
                  "source_bytes_unchanged": True}))
