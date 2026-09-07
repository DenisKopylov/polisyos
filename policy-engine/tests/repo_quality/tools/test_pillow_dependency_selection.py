"""Exercise frozen dependency selection for CI and the existing cloud launcher.

These four selector cases use the native pinned resolver offline. They verify
lock projections, not package installation or the complete set of CI profiles.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from tools.devx.workspace._common import UV_BASELINE, baseline_uv_binary
from tools.ops_runners.experiments import run_msme_final_v3_cloud_rerun

_PRODUCT_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def native_uv() -> str:
    executable = baseline_uv_binary()
    assert executable is not None, f"Provision uv {UV_BASELINE} on PATH before this regression"
    return executable


def _export_requirements(native_uv: str, selector: tuple[str, ...]) -> list[Requirement]:
    lock_path = _PRODUCT_ROOT / "uv.lock"
    original_lock = lock_path.read_bytes()
    completed = subprocess.run(
        [
            native_uv,
            "export",
            "--frozen",
            "--offline",
            "--no-hashes",
            "--no-annotate",
            "--no-header",
            "--no-emit-project",
            "--python",
            sys.executable,
            *selector,
        ],
        cwd=_PRODUCT_ROOT,
        env={key: value for key, value in os.environ.items() if not key.startswith("UV_")},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert lock_path.read_bytes() == original_lock, "Frozen export changed the repository lock"
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return [Requirement(line) for line in completed.stdout.splitlines() if line.strip()]


def _versions(requirements: list[Requirement], package: str) -> set[Version]:
    versions: set[Version] = set()
    for requirement in requirements:
        if canonicalize_name(requirement.name) != package:
            continue
        pins = list(requirement.specifier)
        assert len(pins) == 1 and pins[0].operator == "==", str(requirement)
        versions.add(Version(pins[0].version))
    return versions


@pytest.mark.parametrize(
    "selector",
    [
        pytest.param((), id="bare-default"),
        pytest.param(("--extra", "dev", "--extra", "test"), id="contributor-dev-test"),
        pytest.param(
            ("--group", "ci", "--extra", "dev", "--extra", "test"), id="explicit-ci-group"
        ),
    ],
)
def test_ci_selectors_use_modern_pillow(native_uv: str, selector: tuple[str, ...]) -> None:
    requirements = _export_requirements(native_uv, selector)
    pillow_versions = _versions(requirements, "pillow")
    assert pillow_versions and all(version >= Version("12") for version in pillow_versions)
    assert not _versions(requirements, "marker-pdf")


def test_existing_cloud_selector_preserves_marker(native_uv: str) -> None:
    args = run_msme_final_v3_cloud_rerun.build_parser().parse_args([])
    script = run_msme_final_v3_cloud_rerun.remote_script(args, "dependency-selection-regression")
    commands = [shlex.split(line) for line in script.splitlines() if line.strip()]
    sync_commands = [command for command in commands if command[:2] == ["uv", "sync"]]
    assert len(sync_commands) == 1, "Expected the cloud launcher's real dependency sync command"

    requirements = _export_requirements(native_uv, tuple(sync_commands[0][2:]))
    assert _versions(requirements, "marker-pdf"), "Cloud installation lost its Marker producer"
    pillow_versions = _versions(requirements, "pillow")
    assert pillow_versions and all(version < Version("11") for version in pillow_versions)
