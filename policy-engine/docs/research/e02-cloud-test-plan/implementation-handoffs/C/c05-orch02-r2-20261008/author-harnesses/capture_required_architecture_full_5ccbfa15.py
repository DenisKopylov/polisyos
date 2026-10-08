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
out = Path("/workspace/orch02-r2/c05/required-architecture-full-5ccbfa15")
out.mkdir(parents=True, exist_ok=True)
sha = "5ccbfa15c5671623a4c1ff7a3145460c5ca5a857"
python = "/workspace/polisyos/policy-engine/.venv/bin/python"
workspace = Path("/workspace/orch02-r2/c05/generated-freshness-5ccbfa15")
command = ["/workspace/.polisyos-environment/uv/bin/uv", "run", "--no-sync", "python", "-m", "tools.cli", "architecture", "guardrails", "check", "--generated-freshness-workspace-root", str(workspace), "--generated-freshness-uv-cache-dir", "/workspace/.polisyos-environment/cache/uv"]
env = os.environ.copy()
env["PYTHONPATH"] = str(cwd / "src") + ":" + str(cwd)
env["UV_PROJECT_ENVIRONMENT"] = "/workspace/polisyos/policy-engine/.venv"
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
assert not workspace.exists()
assert subprocess.run(["git", "check-ignore", "-q", "policy-engine/node_modules/.modules.yaml"], cwd=repo).returncode == 0
inputs_before = closure()
(out / "inputs-before.json").write_text(json.dumps(inputs_before, indent=2) + "\n")
probe = subprocess.run([python, "-c", "import hashlib,importlib.util,json,sys; from pathlib import Path; s=importlib.util.find_spec('tools.devx.architecture.guardrails'); p=Path(s.origin); print(json.dumps({'executable':sys.executable,'python':sys.version,'module':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'sys_path':sys.path}))"], cwd=cwd, env=env, capture_output=True)
(out / "resolver-probe.stdout.txt").write_bytes(probe.stdout)
(out / "resolver-probe.stderr.txt").write_bytes(probe.stderr)
assert probe.returncode == 0
record = {"schema": "policyos.e02.c05.required-architecture-full-capture.v1", "state": "RUNNING", "argv": command, "cwd": str(cwd), "source_before": before, "generated_freshness_workspace": str(workspace), "all_default_families_enabled": True, "parent_pid": os.getpid(), "start_utc": datetime.now(UTC).isoformat(), "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "harness_python": sys.version, "platform": platform.platform(), "environment": {k: env.get(k) for k in ["PYTHONPATH", "PATH", "PYTHONDONTWRITEBYTECODE", "PYTHONHOME", "UV_PROJECT_ENVIRONMENT"]}, "timeout": None, "worker_quota": None, "resource_method": "os.wait4 exact direct child, Linux ru_maxrss KiB", "origin_evidence": "Exact executable/PYTHONPATH and separate resolver probe. Architecture import-origin preflight is performed by canonical gate in private copied source. Separate outer resolver probe binds actual gate implementation. No product runtime invocation inferred."}
(out / "command.json").write_text(json.dumps(record, indent=2) + "\n")
# Provision only ignored Node dependencies using the supported locked recipe.
node = {"argv": ["corepack", "pnpm", "install", "--frozen-lockfile", "--ignore-scripts"], "cwd": str(cwd), "state": "RUNNING", "start_utc": datetime.now(UTC).isoformat(), "node_version": subprocess.check_output(["node", "--version"], env=env, text=True).strip(), "timeout": None, "resource_method": "os.wait4 exact direct child; Linux ru_maxrss KiB"}
(out / "node-command.json").write_text(json.dumps(node, indent=2)+"\n")
node_start = time.monotonic()
with (out / "node.stdout.txt").open("wb") as stdout, (out / "node.stderr.txt").open("wb") as stderr:
    child = subprocess.Popen(node["argv"], cwd=cwd, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
    node["child_pid"] = child.pid
    while True:
        pid, status, usage = os.wait4(child.pid, os.WNOHANG)
        if pid:
            child.returncode = os.waitstatus_to_exitcode(status)
            break
        time.sleep(0.1)
node.update({"state": "COMPLETED", "end_utc": datetime.now(UTC).isoformat(), "returncode": child.returncode, "wait_status": status, "wall_seconds": time.monotonic()-node_start, "max_rss_kib": usage.ru_maxrss, "user_seconds": usage.ru_utime, "system_seconds": usage.ru_stime, "source_after": source(), "tracked_python_inputs_intact": inputs_before==closure(), "outputs": {name: {"bytes": (out/name).stat().st_size, "sha256": hashlib.sha256((out/name).read_bytes()).hexdigest()} for name in ["node.stdout.txt", "node.stderr.txt"]}})
(out / "node-command.json").write_text(json.dumps(node, indent=2)+"\n")
assert node["returncode"]==0 and node["source_after"]==before and node["tracked_python_inputs_intact"]
record["phase"]="architecture_full_default"
(out / "command.json").write_text(json.dumps(record, indent=2)+"\n")
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

(out / "command.json").write_text(json.dumps(record, indent=2) + "\n")
