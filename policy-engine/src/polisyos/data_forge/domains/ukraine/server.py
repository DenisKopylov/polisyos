"""Server bootstrap and Part A gate helpers for the Ukraine data stack."""

from __future__ import annotations

import os
import shutil
import socket
import sys
from collections.abc import Callable
from pathlib import Path

from polisyos.data_forge.domains.ukraine.manifests import (
    PartAGateManifest,
    ServerCapabilityManifest,
)
from polisyos.data_forge.domains.ukraine.models import BuildRootConfig, ServerConfig

PartAGateRunner = Callable[[ServerConfig, Path | None], PartAGateManifest]
BootstrapScriptRenderer = Callable[[ServerConfig, BuildRootConfig], str]
ServerCapabilityProbe = Callable[[ServerConfig], ServerCapabilityManifest]


class LocalExecutionBlockedError(RuntimeError):
    """Raised when a server-only command is invoked outside the server context."""


class OpsCompositionRequiredError(RuntimeError):
    """Raised when an operational command is requested without an Ops owner."""


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
    """Retain the legacy export while requiring its operational Ops owner."""

    del config, build_root
    raise OpsCompositionRequiredError(
        "Bootstrap commands are rendered by the Ops composition; "
        "use tools.ops_runners.ukraine_data.server_bootstrap.render_bootstrap_script."
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
    """Retain the legacy export while requiring Ops-owned host inspection."""

    del config
    raise OpsCompositionRequiredError(
        "Server capability probes are Ops-owned; "
        "use tools.ops_runners.ukraine_data.server_bootstrap.probe_local_server_capabilities."
    )


def _unavailable_part_a_gate(
    repo_root: Path | None,
    *,
    reason: str | None = None,
) -> PartAGateManifest:
    """Return a typed non-result when no repository gate is available."""

    if reason is not None:
        detail = reason
    elif repo_root is None:
        reason = "repository checkout is unavailable for the installed package"
        detail = reason
    else:
        detail = f"repository checkout is unavailable at {repo_root}"
    return PartAGateManifest(
        status="unavailable",
        command=[],
        server_only=True,
        passed=False,
        skipped=False,
        notes=[detail],
    )


def run_part_a_gate(
    config: ServerConfig,
    repo_root: Path | None,
    *,
    runner: PartAGateRunner | None = None,
) -> PartAGateManifest:
    """Delegate the C7 gate and return its typed manifest.

    The installed-package path fails closed as ``unavailable`` because it has
    no repository test corpus.  ``runner`` is the composition seam used by
    the Ops runner. The domain never starts repository processes itself.
    """

    if repo_root is None or not is_repository_checkout(repo_root):
        return _unavailable_part_a_gate(repo_root)
    assert_server_execution_allowed(config)
    if runner is None:
        return _unavailable_part_a_gate(
            repo_root,
            reason="Ops-owned repository gate runner is not configured",
        )
    return runner(config, repo_root)


__all__ = [
    "BootstrapScriptRenderer",
    "LocalExecutionBlockedError",
    "OpsCompositionRequiredError",
    "PartAGateRunner",
    "ServerCapabilityProbe",
    "assert_server_execution_allowed",
    "build_bootstrap_script",
    "is_repository_checkout",
    "probe_local_server_capabilities",
    "run_part_a_gate",
]
