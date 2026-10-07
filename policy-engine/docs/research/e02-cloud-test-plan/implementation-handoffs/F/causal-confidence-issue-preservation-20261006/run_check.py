"""Capture actual source-bound commands without changing their quota or environment."""

import hashlib
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/workspace/e02-F-tmle-20261006")
PRODUCT = ROOT / "policy-engine"
SCRATCH = Path(__file__).resolve().parent


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode().strip()


name, expected, *command = sys.argv[1:]
head = git("rev-parse", "HEAD")
assert head == expected, (head, expected)
paths = [
    "policy-engine/src/polisyos/scientist/governance/passes/confidence_pass.py",
    "policy-engine/src/polisyos/ir/analytics/uncertainty.py",
    "policy-engine/src/polisyos/core/contracts/foundry.py",
    "policy-engine/tests/unit/scientist/governance/test_confidence_pass.py",
    "policy-engine/tests/unit/scientist/governance/test_causal_confidence_candidate.py",
]
optional = "policy-engine/tests/unit/scientist/governance/test_confidence_issue_accumulation.py"
if subprocess.run(["git", "cat-file", "-e", f"{head}:{optional}"], cwd=ROOT, capture_output=True).returncode == 0:
    paths.append(optional)
bindings = []
for path in paths:
    data = (ROOT / path).read_bytes()
    tracked = subprocess.check_output(["git", "show", f"{head}:{path}"], cwd=ROOT)
    assert data == tracked, path
    bindings.append({"path": path, "git_blob": git("rev-parse", f"{head}:{path}"),
                     "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
env = dict(os.environ)
env["PYTHONPATH"] = f"{PRODUCT}:{PRODUCT / 'src'}:{PRODUCT / 'tools'}"
env["TMPDIR"] = "/tmp"
start = time.monotonic()
completed = subprocess.run(command, cwd=PRODUCT, env=env, capture_output=True)
wall = time.monotonic() - start
for suffix, data in [("stdout.txt", completed.stdout), ("stderr.txt", completed.stderr)]:
    (SCRATCH / f"{name}.{suffix}").write_bytes(data)
for entry in bindings:
    assert hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest() == entry["sha256"]
assert git("rev-parse", "HEAD") == head
record = {
    "command": command, "cwd": str(PRODUCT), "target_sha": head,
    "target_tree": git("rev-parse", "HEAD^{tree}"), "branch": git("symbolic-ref", "HEAD"),
    "exit_code": completed.returncode, "wall_seconds": wall,
    "cumulative_child_peak_rss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    "environment": {"PYTHONPATH": env["PYTHONPATH"], "TMPDIR": env["TMPDIR"],
                    "other_environment": "inherited os.environ; no added resource caps"},
    "source_bindings": bindings, "source_status_after": git("status", "--porcelain"),
    "outputs": {suffix: {"path": str(SCRATCH / f"{name}.{suffix}"), "bytes": len(data),
                         "sha256": hashlib.sha256(data).hexdigest()}
                for suffix, data in [("stdout.txt", completed.stdout), ("stderr.txt", completed.stderr)]},
}
(SCRATCH / f"{name}.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({"name": name, "exit": completed.returncode, "wall": wall,
                  "stdout_bytes": len(completed.stdout), "stderr_bytes": len(completed.stderr)}))
sys.exit(completed.returncode)
