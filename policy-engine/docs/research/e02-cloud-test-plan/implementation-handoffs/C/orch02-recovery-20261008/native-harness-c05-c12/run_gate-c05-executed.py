"""Run read-only exact-source checks with complete separate deciding outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

SCRATCH = Path(__file__).resolve().parent
PYTHON = SCRATCH / "venv/bin/python"


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--timeout", type=int)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    opts = parser.parse_args()
    root = opts.repo.resolve()
    actual_sha = git(root, "rev-parse", "HEAD")
    if actual_sha != opts.sha:
        raise SystemExit(f"Source freeze mismatch: {actual_sha} != {opts.sha}")
    dirty = git(root, "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise SystemExit(f"Tracked source is dirty: {dirty}")
    out = SCRATCH / "raw" / opts.name
    out.mkdir(parents=True, exist_ok=False)
    cwd = root / "policy-engine"
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": os.pathsep.join([str(cwd / "src"), str(cwd / "tests"), str(SCRATCH)]),
        "PYTHONDONTWRITEBYTECODE": "1",
        "ORCH02_OUTPUT_DIR": str(out),
        "POLISYOS_CAS_DIR": str(out / "cas"),
    })
    argv = opts.args[1:] if opts.args and opts.args[0] == "--" else opts.args
    if not argv:
        raise SystemExit("Specify command after --")
    if argv[0] == "pytest":
        command = [str(PYTHON), "-m", "pytest", "-p", "no:cacheprovider", "-p", "orch02_capture",
                   "--basetemp", str(out / "basetemp"), "--junitxml", str(out / "junit.xml"), *argv[1:]]
    else:
        command = [str(PYTHON), *argv]
    manifest = {
        "schema": "orch02.native-command.v1", "source_sha": actual_sha,
        "source_tree": git(root, "rev-parse", "HEAD^{tree}"),
        "branch": git(root, "symbolic-ref", "--short", "HEAD"), "repo": str(root),
        "cwd": str(cwd), "argv": command, "timeout_seconds": opts.timeout,
        "timeout_basis": "measured prior suite" if opts.timeout else "first wall measurement; no arbitrary cutoff",
        "environment": {k: env[k] for k in ["PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "POLISYOS_CAS_DIR"]},
        "source_status_before": dirty,
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "command_python_input": {
            str(Path(arg)): hashlib.sha256(Path(arg).read_bytes()).hexdigest()
            for arg in command[1:] if arg.endswith(".py") and Path(arg).is_file()
        },
        "disk_available_bytes_before": os.statvfs(SCRATCH).f_bavail * os.statvfs(SCRATCH).f_frsize,
    }
    start = time.monotonic()
    with (out / "stdout.txt").open("wb") as stdout, (out / "stderr.txt").open("wb") as stderr:
        proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout, stderr=stderr,
                                start_new_session=True)
        timed_out = False
        while True:
            pid, status, usage = os.wait4(proc.pid, os.WNOHANG)
            if pid:
                proc.returncode = os.waitstatus_to_exitcode(status)
                break
            if opts.timeout and time.monotonic() - start > opts.timeout and not timed_out:
                timed_out = True
                os.killpg(proc.pid, signal.SIGKILL)
            time.sleep(0.05)
        manifest["exit_code"] = "TIMEOUT" if timed_out else proc.returncode
        resources = {"measurement": "Linux wait4 actual command child usage", "user_seconds": usage.ru_utime,
                     "system_seconds": usage.ru_stime, "maximum_resident_set_size_kib": usage.ru_maxrss,
                     "input_blocks": usage.ru_inblock, "output_blocks": usage.ru_oublock,
                     "voluntary_context_switches": usage.ru_nvcsw,
                     "involuntary_context_switches": usage.ru_nivcsw}
        (out / "resource.json").write_text(json.dumps(resources, indent=2) + "\n")
    manifest["wall_seconds"] = time.monotonic() - start
    manifest["source_status_after"] = git(root, "status", "--porcelain", "--untracked-files=no")
    manifest["source_sha_after"] = git(root, "rev-parse", "HEAD")
    manifest["disk_available_bytes_after"] = os.statvfs(SCRATCH).f_bavail * os.statvfs(SCRATCH).f_frsize
    manifest["outputs"] = {
        p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in out.iterdir() if p.is_file()
    }
    (out / "command.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"name": opts.name, "exit_code": manifest["exit_code"],
                      "wall_seconds": manifest["wall_seconds"], "receipt": str(out / "command.json")}))
    raise SystemExit(0 if manifest["exit_code"] == 0 else 1)


if __name__ == "__main__":
    main()
