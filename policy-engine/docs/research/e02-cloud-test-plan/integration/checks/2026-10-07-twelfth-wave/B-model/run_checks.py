from __future__ import annotations

import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path

ROOT = Path("/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos").resolve()
WORK = ROOT / "policy-engine/_build/e02-g-continuation-20261006/R/incoming-20261007-1311/B-model-local"
CANDIDATE = WORK / "candidate/policy-engine"
RESULTS = WORK / "results"
PYTHON = ROOT / "policy-engine/.venv/bin/python"
RUNTIME = WORK / "candidate_runtime.py"
TIMEOUT_SECONDS = 180


def snapshot(label: str) -> dict[str, object]:
    usage = shutil.disk_usage(ROOT)
    ps = subprocess.run(
        ["/bin/ps", "-axo", "pid,pcpu,rss,command"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    selected = [
        line for line in ps.splitlines()
        if any(token in line.lower() for token in ("pytest", "polisyos", "python", "uv", "ruff"))
    ]
    vm = subprocess.run(["/usr/bin/vm_stat"], check=True, text=True, capture_output=True).stdout
    return {
        "label": label,
        "disk_total_bytes": usage.total,
        "disk_used_bytes": usage.used,
        "disk_free_bytes": usage.free,
        "vm_stat": vm,
        "selected_processes": selected,
        "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def module_versions() -> dict[str, str | None]:
    names = (
        "pytest",
        "pytest-asyncio",
        "pydantic",
        "loguru",
        "opentelemetry-api",
        "opentelemetry-sdk",
    )
    result = {}
    for name in names:
        try:
            result[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            result[name] = None
    return result


def run_action(action: str, env: dict[str, str]) -> dict[str, object]:
    stdout_path = RESULTS / f"{action}.stdout"
    stderr_path = RESULTS / f"{action}.stderr"
    argv = [str(PYTHON), str(RUNTIME), action]
    started = time.monotonic()
    timed_out = False
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            argv,
            cwd=CANDIDATE,
            env=env,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        try:
            returncode = process.wait(timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                returncode = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                returncode = process.wait()
    return {
        "action": action,
        "argv": argv,
        "cwd": str(CANDIDATE),
        "timeout_seconds": TIMEOUT_SECONDS,
        "timed_out": timed_out,
        "returncode": returncode,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
    }


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(CANDIDATE / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_ADDOPTS": "",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    env.pop("PYTEST_DISABLE_PLUGIN_AUTOLOAD", None)
    env.pop("POLISYOS_CANDIDATE_REMOVED_LIVE_PATHS", None)
    context = {
        "root": str(ROOT),
        "g_branch_head": subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
        ).strip(),
        "g_branch": subprocess.check_output(
            ["git", "-C", str(ROOT), "symbolic-ref", "--short", "HEAD"], text=True
        ).strip(),
        "candidate_commit": "d18fe09b5bc0367c966011144a5418f836b9a4b7",
        "candidate_tree": subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "d18fe09b5bc0367c966011144a5418f836b9a4b7^{tree}"],
            text=True,
        ).strip(),
        "python": subprocess.check_output([str(PYTHON), "--version"], text=True).strip(),
        "python_executable": str(PYTHON.resolve()),
        "platform": platform.platform(),
        "runtime_versions": module_versions(),
        "environment_allowlist": {
            key: env.get(key)
            for key in (
                "PYTHONPATH",
                "PYTHONDONTWRITEBYTECODE",
                "PYTEST_ADDOPTS",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
                "OPENBLAS_NUM_THREADS",
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
        "snapshots": [snapshot("before")],
        "actions": [],
    }
    context["actions"].append(run_action("pytest", env))
    context["actions"].append(run_action("probe", env))
    context["snapshots"].append(snapshot("after"))
    status = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain=v1"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    context["g_git_status_after"] = status
    context["g_head_after"] = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
    ).strip()
    context["g_branch_after"] = subprocess.check_output(
        ["git", "-C", str(ROOT), "symbolic-ref", "--short", "HEAD"], text=True
    ).strip()
    path = RESULTS / "execution-context.json"
    path.write_text(json.dumps(context, indent=2, sort_keys=True) + "\n")
    print(json.dumps(context, indent=2, sort_keys=True))
    all_ok = all(
        action["returncode"] == 0 and not action["timed_out"]
        for action in context["actions"]
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
