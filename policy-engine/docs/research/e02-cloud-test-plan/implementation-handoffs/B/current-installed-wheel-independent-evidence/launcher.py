"""Build a frozen real wheel and execute the independent installed consumer.

Mutable artifacts and Python environments belong to a new task directory. The
checked source stays read-only; no project sync or global install is performed.
No test runs until source and native-input identities agree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class Inputs:
    """Exact immutable source/input and task-local execution paths."""

    source_root: Path
    source_sha: str
    test_path: Path
    test_sha256: str
    consumer_sha256: str
    task_root: Path
    python: Path
    uv: Path


def _git(inputs: Inputs, *args: str) -> str:
    # Fixed Git operations consume the explicit immutable source identity.
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Git binary is required for immutable source readback")
    return subprocess.check_output(  # noqa: S603
        [git, *args],
        cwd=inputs.source_root.parent,
        text=True,
    ).strip()


def _snapshot(inputs: Inputs) -> dict[str, str]:
    return {
        "head": _git(inputs, "rev-parse", "HEAD"),
        "tree": _git(inputs, "rev-parse", "HEAD^{tree}"),
        "status": _git(inputs, "status", "--porcelain", "--untracked-files=all"),
    }


def _run(inputs: Inputs, name: str, argv: list[str], env: dict[str, str]) -> None:
    output = inputs.task_root / f"{name}.txt"
    started = datetime.now(UTC).isoformat()
    t0 = time.monotonic()
    sys.stdout.write(json.dumps({"check": name, "phase": "started", "argv": argv}) + "\n")
    sys.stdout.flush()
    with output.open("wb") as stream:
        # No shell: argv invokes explicit UV/Python binaries or the frozen test.
        process = subprocess.Popen(  # noqa: S603
            argv, cwd=inputs.task_root, env=env, stdout=stream, stderr=subprocess.STDOUT
        )
        _, status, usage = os.wait4(process.pid, 0)
        process.returncode = os.waitstatus_to_exitcode(status)
    raw = output.read_bytes()
    snapshot = _snapshot(inputs)
    receipt = {
        "command": argv,
        "cwd": str(inputs.task_root),
        "start_utc": started,
        "end_utc": datetime.now(UTC).isoformat(),
        "wall_s": time.monotonic() - t0,
        "child_maxrss_platform_units": usage.ru_maxrss,
        "maxrss_unit": "KiB on Linux; bytes on macOS",
        "exit": process.returncode,
        "output": str(output),
        "output_bytes": len(raw),
        "output_sha256": hashlib.sha256(raw).hexdigest(),
        "source": snapshot,
    }
    (inputs.task_root / f"{name}.json").write_text(json.dumps(receipt, indent=2) + "\n")
    sys.stdout.write(json.dumps({"check": name, "phase": "terminal", **receipt}) + "\n")
    sys.stdout.flush()
    if snapshot["head"] != inputs.source_sha or snapshot["status"] != "":
        raise RuntimeError(f"source identity changed during {name}: {snapshot}")
    if process.returncode:
        raise RuntimeError(f"{name} failed: complete deciding output is {output}")


def main() -> None:
    """Resolve explicit inputs, build/install the real wheel, then run consumers."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--test-path", type=Path, required=True)
    parser.add_argument("--test-sha256", required=True)
    parser.add_argument("--consumer-sha256", required=True)
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--uv", type=Path, required=True)
    args = parser.parse_args()
    inputs = Inputs(
        args.source_root.resolve(strict=True),
        args.source_sha,
        args.test_path.resolve(strict=True),
        args.test_sha256,
        args.consumer_sha256,
        args.task_root.resolve(),
        args.python.resolve(strict=True),
        args.uv.resolve(strict=True),
    )
    if not (
        len(inputs.source_sha) == 40 and all(c in "0123456789abcdef" for c in inputs.source_sha)
    ):
        raise ValueError("source SHA must be a complete lowercase Git commit identity")
    if inputs.source_root.name != "policy-engine":
        raise ValueError("source root must be the policy-engine product directory")
    if (hashlib.sha256(inputs.test_path.read_bytes()).hexdigest() == inputs.test_sha256) is False:
        raise ValueError("outer native input bytes do not match the supplied SHA256")
    consumer = inputs.test_path.with_name("installed_wheel_bridge_consumer.py")
    if hashlib.sha256(consumer.read_bytes()).hexdigest() != inputs.consumer_sha256:
        raise ValueError("installed consumer input bytes do not match the supplied SHA256")
    before = _snapshot(inputs)
    if before["head"] != inputs.source_sha or before["status"] != "":
        raise ValueError(f"source must be clean and attached to the supplied SHA: {before}")
    inputs.task_root.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env.pop("VIRTUAL_ENV", None)
    env.pop("PYTEST_ADDOPTS", None)
    env.pop("PYTEST_PLUGINS", None)
    env["UV_CACHE_DIR"] = str(inputs.task_root / "uv-cache")
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    uv = str(inputs.uv)
    build_env = inputs.task_root / "build-env"
    installed_env = inputs.task_root / "installed-env"
    for name, root in (("build-venv", build_env), ("installed-venv", installed_env)):
        _run(
            inputs,
            name,
            [
                uv,
                "venv",
                "--python",
                str(inputs.python),
                "--no-python-downloads",
                str(root),
            ],
            env,
        )
    build_python = str(build_env / "bin/python")
    installed_python = str(installed_env / "bin/python")
    _run(
        inputs,
        "build-dependencies",
        [uv, "pip", "install", "--python", build_python, "hatchling==1.27.0"],
        env,
    )
    _run(
        inputs,
        "wheel-build",
        [
            uv,
            "build",
            "--wheel",
            "--no-build-isolation",
            "--python",
            build_python,
            "--no-python-downloads",
            "--no-create-gitignore",
            "--out-dir",
            str(inputs.task_root / "wheels"),
            str(inputs.source_root),
        ],
        env,
    )
    (wheel,) = (inputs.task_root / "wheels").glob("*.whl")
    _run(
        inputs,
        "wheel-install",
        [uv, "pip", "install", "--python", installed_python, "--no-deps", str(wheel)],
        env,
    )
    pytest_dependencies = [
        "pytest==9.0.2",
        "iniconfig==2.3.0",
        "packaging==25.0",
        "pluggy==1.6.0",
        "pygments==2.19.2",
    ]
    _run(
        inputs,
        "consumer-dependencies",
        [
            uv,
            "pip",
            "install",
            "--python",
            installed_python,
            "--no-deps",
            *pytest_dependencies,
        ],
        env,
    )
    installed_site = installed_env / "lib/python3.14/site-packages"
    if not installed_site.is_dir():
        raise RuntimeError(f"Python3.14 installed site directory missing: {installed_site}")
    env.update(
        {
            "E02_LA057_WHEEL_PATH": str(wheel),
            "E02_LA057_INSTALLED_SITE": str(installed_site),
            "E02_LA057_SOURCE_ROOT": str(inputs.source_root),
            "E02_LA057_SOURCE_SHA": inputs.source_sha,
            "E02_LA057_INSTALLED_PYTHON": installed_python,
            "E02_LA057_CONSUMER_SHA256": inputs.consumer_sha256,
            "E02_LA057_OUTER_TEST_SHA256": inputs.test_sha256,
        }
    )
    environment_script = (
        "import importlib.metadata,json,sys;"
        "print(json.dumps({'python':sys.executable,'version':sys.version,"
        "'distributions':{d.metadata['Name']:d.version for d in "
        "importlib.metadata.distributions()}},sort_keys=True))"
    )
    for name, python in (
        ("build-environment", build_python),
        ("consumer-environment", installed_python),
    ):
        _run(inputs, name, [python, "-I", "-B", "-c", environment_script], env)
    # The same seven literal inputs also configure the normal source cohort.
    # This profile contains only this outer case and its eight installed children;
    # the root source cohort independently includes the original common whole file.
    (inputs.task_root / "cohort-input-environment.json").write_text(
        json.dumps(
            {k: v for k, v in env.items() if k.startswith("E02_LA057_")},
            indent=2,
        )
        + "\n"
    )
    _run(
        inputs,
        "native",
        [
            installed_python,
            "-I",
            "-B",
            "-m",
            "pytest",
            "-q",
            "-s",
            "--noconftest",
            "--import-mode=importlib",
            "-c",
            "/dev/null",
            "-o",
            "addopts=",
            "-o",
            "pythonpath=",
            "-o",
            f"cache_dir={inputs.task_root / 'pytest-cache'}",
            "--basetemp",
            str(inputs.task_root / "pytest-scratch"),
            "--junitxml",
            str(inputs.task_root / "native.xml"),
            str(inputs.test_path),
        ],
        env,
    )
    (inputs.task_root / "profile.json").write_text(
        json.dumps(
            {
                "source_before": before,
                "source_after": _snapshot(inputs),
                "test_path": str(inputs.test_path),
                "test_sha256": inputs.test_sha256,
                "consumer_path": str(consumer),
                "consumer_sha256": inputs.consumer_sha256,
                "wheel": str(wheel),
                "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                "input_environment": {k: v for k, v in env.items() if k.startswith("E02_LA057_")},
                "cleanup_candidates": [str(inputs.task_root)],
                "runtime_observation": (
                    "Native deciding XML/stdout, not command-exit-alone closure. "
                    "Inspect actual case properties before finding adjudication."
                ),
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
