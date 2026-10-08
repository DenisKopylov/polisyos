"""Durably capture the exact required C05 diagnostic process with Linux wait4."""
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

repo = Path("/workspace/orch02-c05")
cwd = repo / "policy-engine"
out = Path("/workspace/orch02-r2/c05/required-invocation-5ccbfa15")
out.mkdir(parents=True, exist_ok=True)
sha = "5ccbfa15c5671623a4c1ff7a3145460c5ca5a857"
python = "/workspace/polisyos/policy-engine/.venv/bin/python"
raw_receipt = cwd / "_build/orch02-r2-c05/5ccbfa15/production-invocation.json"
command = [python, "-m", "polisyos.runtime.quality.production_invocation", "--repo-root", str(cwd), "--base", "8dfa7f3c544461c0ff081861848fcc5d8523da5b", "--receipt", str(raw_receipt)]
env = os.environ.copy()
env["PYTHONPATH"] = str(cwd / "src") + ":" + str(cwd)
env["PATH"] = "/workspace/.polisyos-environment/node-v22.23.3-linux-x64/bin:/workspace/.polisyos-environment/uv/bin:" + env["PATH"]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=repo)


def source():
    return {"sha": git("rev-parse", "HEAD").decode().strip(), "tree": git("rev-parse", "HEAD^{tree}").decode().strip(), "status": git("status", "--porcelain").decode()}


def closure():
    paths = git("ls-files", "-z", "policy-engine/src", "policy-engine/tools", "policy-engine/tests").decode().split("\0")
    result = {}
    for path in paths:
        if path.endswith(".py"):
            content = (repo / path).read_bytes()
            result[path] = {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    return result


before = source()
assert before["sha"] == sha and before["status"] == ""
assert subprocess.run(["git", "check-ignore", "-q", str(raw_receipt)], cwd=repo).returncode == 0
inputs_before = closure()
(out / "inputs-before.json").write_text(json.dumps(inputs_before, indent=2) + "\n")
probe = subprocess.run([python, "-c", "import hashlib,importlib.util,json,sys; from pathlib import Path; s=importlib.util.find_spec('polisyos.runtime.quality.production_invocation'); p=Path(s.origin); print(json.dumps({'executable':sys.executable,'python':sys.version,'module':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'sys_path':sys.path}))"], cwd=cwd, env=env, capture_output=True)
(out / "resolver-probe.stdout.txt").write_bytes(probe.stdout)
(out / "resolver-probe.stderr.txt").write_bytes(probe.stderr)
assert probe.returncode == 0
record = {"schema": "policyos.e02.c05.required-invocation-capture.v2", "state": "RUNNING", "argv": command, "cwd": str(cwd), "source_before": before, "base": command[6], "raw_receipt": str(raw_receipt), "raw_receipt_is_ignored": True, "parent_pid": os.getpid(), "start_utc": datetime.now(UTC).isoformat(), "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "harness_python": sys.version, "platform": platform.platform(), "environment": {k: env.get(k) for k in ["PYTHONPATH", "PATH", "PYTHONDONTWRITEBYTECODE", "PYTHONHOME", "UV_PROJECT_ENVIRONMENT"]}, "timeout": None, "worker_quota": None, "resource_method": "os.wait4 exact direct child, Linux ru_maxrss KiB", "origin_evidence": "Exact executable/PYTHONPATH and separate resolver probe. Tool remains a static path diagnostic; no business runtime invocation inferred."}
(out / "command.json").write_text(json.dumps(record, indent=2) + "\n")
start = time.monotonic()
with (out / "stdout.txt").open("wb") as stdout, (out / "stderr.txt").open("wb") as stderr:
    child = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
    record["child_pid"] = child.pid
    (out / "command.json").write_text(json.dumps(record, indent=2) + "\n")
    while True:
        pid, status, usage = os.wait4(child.pid, os.WNOHANG)
        if pid:
            child.returncode = os.waitstatus_to_exitcode(status)
            break
        time.sleep(0.1)
after = source()
inputs_after = closure()
(out / "inputs-after.json").write_text(json.dumps(inputs_after, indent=2) + "\n")
record.update({"state": "COMPLETED", "end_utc": datetime.now(UTC).isoformat(), "wall_seconds": time.monotonic()-start, "returncode": child.returncode, "wait_status": status, "signal": os.WTERMSIG(status) if os.WIFSIGNALED(status) else None, "max_rss_kib": usage.ru_maxrss, "user_seconds": usage.ru_utime, "system_seconds": usage.ru_stime, "source_after": after, "source_binding_intact": before == after, "tracked_python_input_count": len(inputs_before), "tracked_python_inputs_intact": inputs_before == inputs_after, "runtime_invocation_established": False, "outputs": {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in out.iterdir() if p.is_file() and p.name != "command.json"}})
if raw_receipt.exists():
    record["complete_raw_receipt"] = {"bytes": raw_receipt.stat().st_size, "sha256": hashlib.sha256(raw_receipt.read_bytes()).hexdigest()}
(out / "command.json").write_text(json.dumps(record, indent=2) + "\n")
