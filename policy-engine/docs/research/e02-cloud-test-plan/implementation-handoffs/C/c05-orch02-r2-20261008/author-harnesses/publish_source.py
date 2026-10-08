"""Publish the exact C05 implementation and fetch its independent topic ref."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

repo = Path("/workspace/orch02-c05")
out = Path("/workspace/orch02-r2/c05/publication-source")
out.mkdir(parents=True, exist_ok=True)
branch = "codex/e02-C-orch02-c05-recovery"
expected = "2734ee49f6985ff2bd7ad6e3c4d6089a7d7848ca"
readback = "refs/orch02-r2/readback/c05-source-2734ee49"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=repo)


assert git("rev-parse", "HEAD").decode().strip() == expected
assert not git("status", "--porcelain")
records = []
for name, command in [
    ("push", ["git", "push", "origin", branch]),
    ("fetch-readback", ["git", "fetch", "origin", f"refs/heads/{branch}:{readback}"]),
]:
    start = time.perf_counter()
    result = subprocess.run(command, cwd=repo, capture_output=True)
    (out / f"{name}.stdout.txt").write_bytes(result.stdout)
    (out / f"{name}.stderr.txt").write_bytes(result.stderr)
    records.append({"name": name, "command": command, "cwd": str(repo), "exit_code": result.returncode, "wall_seconds": time.perf_counter()-start, "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(), "stderr_sha256": hashlib.sha256(result.stderr).hexdigest()})
    if result.returncode:
        (out / "receipt.json").write_text(json.dumps({"commands": records, "state": "FAILED"}, indent=2)+"\n")
        raise SystemExit(result.returncode)
assert git("rev-parse", readback).decode().strip() == expected
tree = git("rev-parse", readback+"^{tree}").decode().strip()
assert tree == "dac1d82c7761d0f8e11e19f1ee448133d606d73d"
freeze = json.loads(Path("/workspace/orch02-r2/c05/frozen/source-freeze.json").read_text())
rows = []
for row in freeze["all_binding_rows"]:
    path = row["path"]
    raw = git("show", f"{readback}:{path}")
    identity = row["identities"]["r2_tree"]
    assert hashlib.sha256(raw).hexdigest() == identity["sha256"]
    assert git("rev-parse", f"{readback}:{path}").decode().strip() == identity["blob"]
    rows.append({"path": path, **identity})
document = {"schema": "policyos.e02.c05.r2-source-publication.v1", "branch": branch, "source": expected, "tree": tree, "readback_ref": readback, "state": "NORMAL_PUSH_FETCH_READBACK_MATCHED", "commands": records, "byte_rows": rows, "count": len(rows)}
(out / "receipt.json").write_text(json.dumps(document, indent=2)+"\n")
print(json.dumps({key:document[key] for key in ("branch","source","tree","state","count")},indent=2))
