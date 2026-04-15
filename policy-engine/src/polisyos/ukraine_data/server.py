"""Server bootstrap and Part A gate helpers for the Ukraine data stack."""

from __future__ import annotations

import importlib.util
import shlex
import shutil
import socket
import subprocess
import sys
from pathlib import Path

from polisyos.ukraine_data.manifests import PartAGateManifest, ServerCapabilityManifest, utc_now_iso
from polisyos.ukraine_data.models import BuildRootConfig, ServerConfig
from polisyos.ukraine_data.resources import free_disk_gib, total_ram_gib


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
        if str(__import__("os").environ.get(marker, "")).strip() == "1":
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


def run_part_a_gate(config: ServerConfig, repo_root: Path) -> PartAGateManifest:
    """Run the C7 integration gate and return a typed manifest payload."""

    assert_server_execution_allowed(config)
    command = [
        config.uv_bin,
        "run",
        "pytest",
        "-q",
        "tests/integration/test_c7_synthetic_full_pipeline.py",
    ]
    env = dict(__import__("os").environ)
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
        passed=passed,
        skipped=skipped,
        created_at=utc_now_iso(),
        notes=notes,
    )


__all__ = [
    "LocalExecutionBlockedError",
    "assert_server_execution_allowed",
    "build_bootstrap_script",
    "probe_local_server_capabilities",
    "run_part_a_gate",
]
