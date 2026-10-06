from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(
    "/Users/deniskopylov/.codex/worktrees/e02-a-n5-verify-current/polisyos/policy-engine"
)
PYTHON = Path(
    "/Users/deniskopylov/.codex/worktrees/e02-a-full-queue/polisyos/policy-engine/.venv/bin/python"
)
EVIDENCE = Path(__file__).resolve().parent
TEST_NODE = (
    "tests/unit/remediation/test_cyc_02.py::"
    "test_n5_fresh_process_readback_binds_default_n8_to_cas_identity"
)
BASE_TEMP = EVIDENCE / "basetemp-n5-target"
JUNIT = EVIDENCE / "junit-n5-target.xml"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT.parent,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def test_environment() -> dict[str, str]:
    env = {
        key: os.environ[key]
        for key in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL")
        if key in os.environ
    }
    env.update(
        {
            "PYTHONPATH": f"{PROJECT_ROOT / 'src'}:.",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "JAX_PLATFORM_NAME": "cpu",
            "XLA_FLAGS": (
                "--xla_cpu_multi_thread_eigen=false intra_op_parallelism_threads=1"
            ),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
            "BLIS_NUM_THREADS": "1",
        }
    )
    return env


def cas_inventory() -> list[dict[str, object]]:
    basetemp = BASE_TEMP
    entries: list[dict[str, object]] = []
    for path in sorted(basetemp.rglob("*.blob")):
        entries.append(
            {
                "relative_path": path.relative_to(basetemp).as_posix(),
                "artifact_id": path.stem,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    return entries


def junit_summary() -> dict[str, object]:
    if not JUNIT.exists():
        return {"available": False}
    root = ET.parse(JUNIT).getroot()
    cases = [
        {
            "classname": case.attrib.get("classname"),
            "name": case.attrib.get("name"),
            "time_seconds": float(case.attrib.get("time", "0")),
            "failure": case.find("failure") is not None,
            "error": case.find("error") is not None,
            "skipped": case.find("skipped") is not None,
        }
        for case in root.iter("testcase")
    ]
    return {
        "available": True,
        "suite_attributes": dict(root.attrib),
        "cases": cases,
    }


def main() -> int:
    if not PYTHON.is_file():
        raise SystemExit(f"requested root-owned interpreter missing: {PYTHON}")
    if not PROJECT_ROOT.joinpath("pytest.ini").is_file():
        raise SystemExit(f"pytest.ini missing from verification checkout: {PROJECT_ROOT}")
    if BASE_TEMP.exists() or JUNIT.exists():
        raise SystemExit("refusing to reuse an existing temp root or JUnit result")

    head = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    branch = git("branch", "--show-current")
    status = git("status", "--porcelain")
    if (
        branch != "codex/e02-A-n5-verify-current"
        or head != "7ffbf5c71d6352f7712673a6591be5e553993745"
        or tree != "221f31490189a5a2865f1ce2e4b335d6342d6bd6"
        or status
    ):
        raise SystemExit(
            f"verification checkout changed: branch={branch} head={head} tree={tree} "
            f"status={status!r}"
        )

    tracked_inputs = {
        relative: sha256(PROJECT_ROOT / relative)
        for relative in (
            "src/polisyos/runtime/quality/generation_cycle.py",
            "src/polisyos/runtime/quality/joint_simulation_horizon.py",
            "tests/unit/remediation/test_cyc_02.py",
            "pytest.ini",
        )
    }
    env = test_environment()
    preflight_code = r"""
import importlib
import json
import platform
import sys
import jax

modules = {
    name: importlib.import_module(name).__file__
    for name in (
        "polisyos.runtime.quality.generation_cycle",
        "polisyos.runtime.quality.joint_simulation_horizon",
        "tests.unit.remediation.test_cyc_02",
    )
}
print(json.dumps({
    "sys_executable": sys.executable,
    "python_version": sys.version,
    "platform": platform.platform(),
    "jax_version": jax.__version__,
    "jax_default_backend": jax.default_backend(),
    "jax_devices": [str(device) for device in jax.devices()],
    "module_origins": modules,
}, sort_keys=True))
"""
    preflight = subprocess.run(
        [str(PYTHON), "-B", "-c", preflight_code],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    (EVIDENCE / "preflight.stdout.txt").write_text(preflight.stdout)
    (EVIDENCE / "preflight.stderr.txt").write_text(preflight.stderr)
    if preflight.returncode != 0:
        (EVIDENCE / "preflight.exit_code.txt").write_text(f"{preflight.returncode}\n")
        return preflight.returncode
    import_origin = json.loads(preflight.stdout.strip().splitlines()[-1])
    (EVIDENCE / "import-origin.json").write_text(
        json.dumps(import_origin, indent=2, sort_keys=True) + "\n"
    )

    command = [
        str(PYTHON),
        "-B",
        "-m",
        "pytest",
        "-c",
        "pytest.ini",
        TEST_NODE,
        f"--basetemp={BASE_TEMP}",
        f"--junitxml={JUNIT}",
        "--durations=0",
    ]
    metadata: dict[str, object] = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "checkout_root": str(PROJECT_ROOT),
        "branch": branch,
        "head": head,
        "tree": tree,
        "working_tree_status": status,
        "runner_python": str(PYTHON),
        "working_directory": str(PROJECT_ROOT),
        "pytest_config": str(PROJECT_ROOT / "pytest.ini"),
        "pytest_testpaths": ["tests"],
        "pytest_ini_contents": (PROJECT_ROOT / "pytest.ini").read_text(),
        "test_node": TEST_NODE,
        "command": command,
        "environment": env,
        "source_and_test_file_sha256": tracked_inputs,
        "import_origin": import_origin,
        "fixture_identity": {
            "fixture_factory": "_cyc01_owner_bound_n5_case",
            "tmp_path_basetemp": str(BASE_TEMP),
            "producer_consumer_mode": "separate Python processes",
        },
        "data_requirements": {
            "production_data_required": False,
        },
        "stdout_path": str(EVIDENCE / "pytest.stdout.txt"),
        "stderr_path": str(EVIDENCE / "pytest.stderr.txt"),
        "junit_path": str(JUNIT),
    }
    (EVIDENCE / "pytest-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    )

    (EVIDENCE / "pytest-command.txt").write_text(
        " ".join(command) + "\n"
    )
    print("RUNNING_N5_TARGET=" + json.dumps(metadata, sort_keys=True), flush=True)
    start_utc = datetime.now(timezone.utc)
    start = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.monotonic() - start
    end_utc = datetime.now(timezone.utc)
    (EVIDENCE / "pytest.stdout.txt").write_text(completed.stdout)
    (EVIDENCE / "pytest.stderr.txt").write_text(completed.stderr)
    (EVIDENCE / "pytest.exit_code.txt").write_text(f"{completed.returncode}\n")
    timing = {
        "started_utc": start_utc.isoformat(),
        "finished_utc": end_utc.isoformat(),
        "elapsed_seconds": elapsed,
        "return_code": completed.returncode,
        "junit": junit_summary(),
        "fresh_cas_artifacts": cas_inventory(),
    }
    (EVIDENCE / "pytest-timing-and-cas.json").write_text(
        json.dumps(timing, indent=2, sort_keys=True) + "\n"
    )
    sys.stdout.write(completed.stdout)
    sys.stderr.write(completed.stderr)
    print(
        "N5_TARGET_RESULT="
        + json.dumps(
            {
                "return_code": completed.returncode,
                "elapsed_seconds": elapsed,
                "junit": timing["junit"],
                "cas_artifact_count": len(timing["fresh_cas_artifacts"]),
            },
            sort_keys=True,
        )
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
