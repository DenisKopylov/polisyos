"""Server bootstrap and Part A gate helpers for the Ukraine data stack."""

from __future__ import annotations

import importlib.util
import os
import shlex
import shutil
import socket
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from polisyos.data_forge.domains.ukraine.manifests import (
    PartAGateManifest,
    ServerCapabilityManifest,
    utc_now_iso,
)
from polisyos.data_forge.domains.ukraine.models import BuildRootConfig, ServerConfig
from polisyos.data_forge.domains.ukraine.resources import free_disk_gib, total_ram_gib


PartAGateRunner = Callable[[ServerConfig, Path | None], PartAGateManifest]
BootstrapScriptRenderer = Callable[[ServerConfig, BuildRootConfig], str]
ServerCapabilityProbe = Callable[[ServerConfig], ServerCapabilityManifest]


class LocalExecutionBlockedError(RuntimeError):
    """Raised when a server-only command is invoked outside the server context."""


def assert_server_execution_allowed(config: ServerConfig) -> None:
    """Reject server-only commands when the server marker env var is not set."""

    if not config.require_server_for_build:
        return
    if str(shutil.which(config.python_bin) or "").strip() == "":
        raise LocalExecutionBlockedError(f"Missing python executable: {config.python_bin}")
    if sys.platform.startswith("linux") and socket.gethostname():
        marker = config.server_marker_env
        if str(os.environ.get(marker, "")).strip() == "1":
            return
    raise LocalExecutionBlockedError(
        f"Server-only command blocked. Export {config.server_marker_env}=1 on the target server."
    )


def build_bootstrap_script(config: ServerConfig, build_root: BuildRootConfig) -> str:
    """Render the remote bootstrap shell script for a bare CPX62 host."""

    packages = " ".join(shlex.quote(package) for package in config.bootstrap_packages)
    extras = " ".join(f"--extra {shlex.quote(extra)}" for extra in config.bootstrap_extras)
    dirs = [
        build_root.root,
        build_root.raw_dir,
        build_root.normalized_dir,
        build_root.runtime_dir,
        build_root.calibration_dir,
        build_root.bundles_dir,
        build_root.manifests_dir,
        build_root.tmp_dir,
        build_root.logs_dir,
        build_root.resolved_cas_root,
    ]
    mkdir_line = " ".join(shlex.quote(str(item)) for item in dirs)
    env_path = shlex.quote(str(config.env_path))
    storage_root = shlex.quote(str(config.storage_root))
    workdir = shlex.quote(str(config.workdir))
    marker = shlex.quote(config.server_marker_env)
    uv_bin = shlex.quote(config.uv_bin)
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "export DEBIAN_FRONTEND=noninteractive",
            "apt-get update",
            f"apt-get install -y {packages}",
            f"mkdir -p {mkdir_line}",
            f"cat > {env_path} <<'EOF'",
            f"export {marker}=1",
            f"export POLISYOS_UKRAINE_DATA_ROOT={storage_root}",
            f"export POLISYOS_CAS_ROOT={shlex.quote(str(build_root.resolved_cas_root))}",
            "EOF",
            f"cd {workdir}",
            f"{uv_bin} sync {extras}",
            f"{uv_bin} run ukraine-data bootstrap-server --write-capabilities",
        ]
    )


def is_repository_checkout(repo_root: Path | None) -> bool:
    """Return whether ``repo_root`` contains the repository gate inputs.

    The Ukraine domain may be imported from an installed wheel, where the
    package has no checkout or repository integration tests beside it.  Keep
    this check structural and local: a caller must provide both the product
    workspace marker and the exact gate test before the gate can claim to have
    run.  This function deliberately does not infer a repository from a
    package's ``src/polisyos`` directory.
    """

    if repo_root is None or not repo_root.is_dir():
        return False
    return (
        (repo_root / "pyproject.toml").is_file()
        and (repo_root / "src" / "polisyos").is_dir()
        and (repo_root / "tests" / "integration" / "test_c7_synthetic_full_pipeline.py").is_file()
    )


def probe_local_server_capabilities(config: ServerConfig) -> ServerCapabilityManifest:
    """Probe local packages and binary prerequisites for the server manifest."""

    def _has_module(name: str) -> bool:
        return importlib.util.find_spec(name) is not None

    return ServerCapabilityManifest(
        host=socket.gethostname() or config.host,
        python_available=shutil.which(config.python_bin) is not None,
        uv_available=shutil.which(config.uv_bin) is not None,
        duckdb_available=_has_module("duckdb"),
        jax_available=_has_module("jax"),
        lifelines_available=_has_module("lifelines"),
        gdal_available=shutil.which("gdalinfo") is not None,
        osmium_available=shutil.which("osmium") is not None,
        total_ram_gib=total_ram_gib(),
        free_disk_gib=free_disk_gib(config.storage_root),
    )


def _unavailable_part_a_gate(repo_root: Path | None) -> PartAGateManifest:
    """Return a typed non-result when no repository gate is available."""

    if repo_root is None:
        reason = "repository checkout is unavailable for the installed package"
    else:
        reason = f"repository checkout is unavailable at {repo_root}"
    return PartAGateManifest(
        status="unavailable",
        command=[],
        server_only=True,
        passed=False,
        skipped=False,
        notes=[reason],
    )


def run_part_a_gate(
    config: ServerConfig,
    repo_root: Path | None,
    *,
    runner: PartAGateRunner | None = None,
) -> PartAGateManifest:
    """Run or delegate the C7 gate and return its typed manifest.

    The installed-package path fails closed as ``unavailable`` because it has
    no repository test corpus.  ``runner`` is the composition seam used by
    the ops runner; the local subprocess path remains a narrow compatibility
    fallback for existing callers and characterization tests.
    """

    if repo_root is None or not is_repository_checkout(repo_root):
        return _unavailable_part_a_gate(repo_root)
    assert_server_execution_allowed(config)
    if runner is not None:
        return runner(config, repo_root)
    command = [
        config.uv_bin,
        "run",
        "pytest",
        "-q",
        "tests/integration/test_c7_synthetic_full_pipeline.py",
    ]
    env = dict(os.environ)
    env["POLISYOS_RUN_INTEGRATION"] = "1"
    completed = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    stdout = completed.stdout or ""
    skipped = "SKIPPED" in stdout or " skipped" in stdout.lower()
    passed = completed.returncode == 0 and not skipped
    notes = []
    if stdout.strip():
        notes.append(stdout.strip()[-5000:])
    stderr = (completed.stderr or "").strip()
    if stderr:
        notes.append(stderr[-2000:])
    return PartAGateManifest(
        status="passed" if passed else ("skipped" if skipped else "failed"),
        command=command,
        server_only=True,
        passed=passed,
        skipped=skipped,
        created_at=utc_now_iso(),
        notes=notes,
    )


__all__ = [
    "LocalExecutionBlockedError",
    "BootstrapScriptRenderer",
    "PartAGateRunner",
    "ServerCapabilityProbe",
    "assert_server_execution_allowed",
    "build_bootstrap_script",
    "is_repository_checkout",
    "probe_local_server_capabilities",
    "run_part_a_gate",
]
