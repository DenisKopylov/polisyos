#!/usr/bin/env python3
"""Ops-facing owner for Ukraine server bootstrap composition.

The domain owns the typed configuration and capability manifest contracts.
This module is the executable-side seam that composes those contracts for a
remote server workflow; it intentionally does not import the ops layer from
``src/polisyos``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shlex
import shutil
import socket
from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.data_forge.domains.ukraine.manifests import ServerCapabilityManifest
from polisyos.data_forge.domains.ukraine.orchestrator import (
    UkraineDataOrchestrator,
    load_pipeline_config,
)
from polisyos.data_forge.domains.ukraine.resources import free_disk_gib, total_ram_gib

if TYPE_CHECKING:
    from polisyos.data_forge.domains.ukraine.models import (
        BuildRootConfig,
        PipelineConfig,
        ServerConfig,
    )

__all__ = [
    "build_bootstrap_script",
    "build_orchestrator",
    "probe_local_server_capabilities",
    "render_bootstrap_script",
]


def render_bootstrap_script(config: ServerConfig, build_root: BuildRootConfig) -> str:
    """Render the reviewed server bootstrap command owned by this Ops module."""

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


def build_bootstrap_script(config: ServerConfig, build_root: BuildRootConfig) -> str:
    """Preserve the Ops module's historical builder export."""

    return render_bootstrap_script(config, build_root)


def resolve_workspace_root(workspace_root: Path | None) -> Path:
    """Return the explicit CLI candidate root, defaulting only to the caller's cwd."""

    return (workspace_root if workspace_root is not None else Path.cwd()).expanduser().resolve()


def probe_local_server_capabilities(config: ServerConfig) -> ServerCapabilityManifest:
    """Inspect host prerequisites and return the domain's typed capability record."""

    def has_module(name: str) -> bool:
        return importlib.util.find_spec(name) is not None

    return ServerCapabilityManifest(
        host=socket.gethostname() or config.host,
        python_available=shutil.which(config.python_bin) is not None,
        uv_available=shutil.which(config.uv_bin) is not None,
        duckdb_available=has_module("duckdb"),
        jax_available=has_module("jax"),
        lifelines_available=has_module("lifelines"),
        gdal_available=shutil.which("gdalinfo") is not None,
        osmium_available=shutil.which("osmium") is not None,
        total_ram_gib=total_ram_gib(),
        free_disk_gib=free_disk_gib(config.storage_root),
    )


def build_orchestrator(
    config: PipelineConfig,
    workspace_root: Path | None,
) -> UkraineDataOrchestrator:
    """Compose domain contracts with Ops-owned runtime and process callbacks."""

    from tools.ops_runners.ukraine_data.validate_part_a import run_part_a_gate

    return UkraineDataOrchestrator(
        config,
        workspace_root=resolve_workspace_root(workspace_root),
        part_a_gate_runner=run_part_a_gate,
        bootstrap_script_renderer=render_bootstrap_script,
        server_capability_probe=probe_local_server_capabilities,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--root", type=Path, default=None, help="Artifact/build root.")
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=None,
        help="Repository checkout used for server-side composition.",
    )
    parser.add_argument(
        "--write-capabilities",
        action="store_true",
        help="Write the server capability manifest during bootstrap.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run bootstrap through the ops-owned composition seam."""

    args = _build_parser().parse_args(argv)
    config = load_pipeline_config(args.config, root=args.root)
    summary = build_orchestrator(config, args.workspace_root).bootstrap_server(
        write_capabilities=args.write_capabilities,
    )
    print(json.dumps(summary.manifest.model_dump(mode="json"), ensure_ascii=True, indent=2))
    return 0 if summary.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
