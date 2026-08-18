# ruff: noqa: S101

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import yaml

PRODUCT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = PRODUCT_ROOT.parent


def _load_yaml(relative_path: str) -> dict[str, Any]:
    path = WORKSPACE_ROOT / relative_path
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), path
    return loaded


def _steps(relative_path: str) -> list[dict[str, Any]]:
    loaded = _load_yaml(relative_path)
    steps = loaded["runs"]["steps"]
    assert isinstance(steps, list), relative_path
    return steps


def test_python_profile_bootstrap_is_dependency_free_before_sync() -> None:
    steps = _steps(".github/actions/setup-policy-engine-python/action.yml")
    sync_step = next(
        step
        for step in steps
        if step.get("name") == "Sync environment from workspace bootstrap profile"
    )
    command = str(sync_step["run"])

    assert "python3 -m tools.devx.workspace.bootstrap" in command
    assert "python3 -m tools.cli" not in command

    completed = subprocess.run(
        [
            sys.executable,
            "-S",
            "-m",
            "tools.devx.workspace.bootstrap",
            "--help",
        ],
        cwd=PRODUCT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Workspace bootstrap profile" not in completed.stderr
    assert "--profile" in completed.stdout


def test_dashboard_setup_never_requests_pnpm_cache_before_pnpm_exists() -> None:
    steps = _steps(".github/actions/setup-runtime-dashboard/action.yml")
    pnpm_available = False

    for step in steps:
        uses = str(step.get("uses", ""))
        command = str(step.get("run", ""))
        inputs = step.get("with", {})
        assert isinstance(inputs, dict), step

        if str(inputs.get("cache", "")).strip().lower() == "pnpm":
            assert pnpm_available, (
                "actions/setup-node cannot query the pnpm cache before a prior step "
                "has provisioned pnpm on PATH"
            )

        if uses.startswith("pnpm/action-setup@") or any(
            provisioner in command
            for provisioner in (
                "corepack enable",
                "corepack prepare",
                "corepack install",
            )
        ):
            pnpm_available = True

    install_step = next(
        step for step in steps if step.get("name") == "Install workspace dependencies"
    )
    assert "corepack pnpm install --frozen-lockfile" in str(install_step["run"])


def test_release_checksum_glob_is_option_safe() -> None:
    workflow = _load_yaml(".github/workflows/release.yml")
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    release_steps = jobs["build-artifacts"]["steps"]
    assemble_step = next(
        step for step in release_steps if step.get("name") == "Assemble release assets"
    )
    command = str(assemble_step["run"])

    assert "sha256sum -- ./* > SHA256SUMS" in command
    assert "sha256sum * > SHA256SUMS" not in command


def test_python_314_lock_uses_supported_pillow_line() -> None:
    project = tomllib.loads((PRODUCT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((PRODUCT_ROOT / "uv.lock").read_text(encoding="utf-8"))

    assert project["project"]["requires-python"] == ">=3.14,<3.15"
    pillow = next(package for package in lock["package"] if package["name"] == "pillow")
    pillow_major = int(str(pillow["version"]).split(".", maxsplit=1)[0])

    assert pillow_major >= 12, (
        "Pillow 10/11 do not support the repository's Python 3.14 baseline; "
        "the clean runner must resolve a Python-3.14-supported Pillow line"
    )


def test_ci_test_extra_installs_required_unconditional_test_backends() -> None:
    project = tomllib.loads((PRODUCT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    test_dependencies = set(project["project"]["optional-dependencies"]["test"])

    assert {
        "policy-engine[ml]",
        "policy-engine[solvers]",
    } <= test_dependencies
