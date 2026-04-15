#!/usr/bin/env python3
"""Provision and drive a remote Linux runner for acceptance closeout."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import sys

from tools._lib.imports import repo_root_from, ensure_repo_import_roots

sys.path.insert(0, str(repo_root_from(__file__)))

ensure_repo_import_roots(__file__, include_repo_root=True, include_src_root=False)

from ._common import (
    FRONTEND_ROOT,
    NODE_BASELINE,
    PRODUCT_ROOT,
    PYTHON_BASELINE,
    UV_BASELINE,
)

WORKSPACE_ROOT = PRODUCT_ROOT.parent
DEFAULT_REMOTE_HOST = "204.168.164.187"
DEFAULT_REMOTE_USER = "root"
DEFAULT_REMOTE_PORT = 22
DEFAULT_REMOTE_WORKTREE = "/root/polisyos-work"
DEFAULT_REMOTE_CLEAN_TREE = "/root/polisyos-clean"
DEFAULT_REMOTE_ARTIFACTS = "/root/polisyos-artifacts"
DEFAULT_REMOTE_TOOLCHAIN = "/root/polisyos-toolchain"
REMOTE_NODE_CHANNEL = f"latest-v{NODE_BASELINE}.x"
SNAPSHOT_MANIFESTS = (
    PRODUCT_ROOT / "schemas" / "snapshots" / "fabric" / "_manifest.json",
    PRODUCT_ROOT / "schemas" / "snapshots" / "ir" / "_manifest.json",
)
RSYNC_EXCLUDES = (
    ".git/",
    ".venv*/",
    "__pycache__/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".mypy_cache/",
    ".cache/",
    ".hypothesis/",
    ".polisyos/",
    ".uv-cache/",
    ".tmp*/",
    "node_modules/",
    "logs/",
    "/policy-engine/runs/",
    "site/",
    "data/raw/",
    "benchmark-results/",
    "production_data/",
    "dist/",
    "build/",
    "*.egg-info/",
)
SYNC_ROOT_ENTRIES = ("README.md", "SECURITY.md", "renovate.json", ".github", "policy-engine")


@dataclass(frozen=True, slots=True)
class RemoteAcceptanceConfig:
    """Local view of the remote acceptance runner."""

    host: str = DEFAULT_REMOTE_HOST
    user: str = DEFAULT_REMOTE_USER
    port: int = DEFAULT_REMOTE_PORT
    worktree: str = DEFAULT_REMOTE_WORKTREE
    clean_tree: str = DEFAULT_REMOTE_CLEAN_TREE
    artifacts_root: str = DEFAULT_REMOTE_ARTIFACTS
    toolchain_root: str = DEFAULT_REMOTE_TOOLCHAIN

    @property
    def ssh_target(self) -> str:
        return f"{self.user}@{self.host}"

    @property
    def toolchain_bin(self) -> str:
        return f"{self.toolchain_root}/bin"

    @property
    def toolchain_env(self) -> str:
        return f"{self.toolchain_root}/env.sh"

    @property
    def bundle_dir(self) -> str:
        return f"{self.artifacts_root}/bundles"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provision and drive a Hetzner-backed acceptance runner.",
    )
    parser.add_argument("--host", default=DEFAULT_REMOTE_HOST, help="Remote host or IP.")
    parser.add_argument("--user", default=DEFAULT_REMOTE_USER, help="Remote SSH user.")
    parser.add_argument("--port", type=int, default=DEFAULT_REMOTE_PORT, help="Remote SSH port.")
    parser.add_argument(
        "--worktree",
        default=DEFAULT_REMOTE_WORKTREE,
        help="Remote rsynced worktree root.",
    )
    parser.add_argument(
        "--clean-tree",
        default=DEFAULT_REMOTE_CLEAN_TREE,
        help="Remote committed clean checkout root.",
    )
    parser.add_argument(
        "--artifacts-root",
        default=DEFAULT_REMOTE_ARTIFACTS,
        help="Remote artifacts/logs root.",
    )
    parser.add_argument(
        "--toolchain-root",
        default=DEFAULT_REMOTE_TOOLCHAIN,
        help="Remote isolated toolchain root.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands instead of executing them.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "provision",
        help="Install Docker plus isolated Python, Node, and uv on the remote host.",
    )

    sync = subparsers.add_parser(
        "sync",
        help="Rsync the local workspace into the remote worktree.",
    )
    sync.add_argument(
        "--no-delete",
        action="store_true",
        help="Do not delete stale files from the remote worktree.",
    )

    exec_parser = subparsers.add_parser(
        "exec",
        help="Run a command on the remote host with the isolated toolchain enabled.",
    )
    exec_parser.add_argument(
        "--cwd",
        default=DEFAULT_REMOTE_WORKTREE,
        help="Remote working directory for the command.",
    )
    exec_parser.add_argument(
        "--no-toolchain-env",
        action="store_true",
        help="Skip sourcing the remote toolchain env.sh.",
    )
    exec_parser.add_argument(
        "argv",
        nargs=argparse.REMAINDER,
        help="Command to execute on the remote host.",
    )

    checkout = subparsers.add_parser(
        "clean-checkout",
        help=(
            "Upload a git bundle for the given ref and create a clean detached "
            "checkout on the remote host."
        ),
    )
    checkout.add_argument(
        "--ref",
        default="HEAD",
        help="Git ref or commit to bundle and check out remotely.",
    )

    return parser


def _config_from_args(args: argparse.Namespace) -> RemoteAcceptanceConfig:
    return RemoteAcceptanceConfig(
        host=args.host,
        user=args.user,
        port=args.port,
        worktree=args.worktree,
        clean_tree=args.clean_tree,
        artifacts_root=args.artifacts_root,
        toolchain_root=args.toolchain_root,
    )


def _ssh_argv(config: RemoteAcceptanceConfig) -> list[str]:
    return [
        "ssh",
        "-p",
        str(config.port),
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        config.ssh_target,
    ]


def _run(argv: Sequence[str], *, input_text: str | None = None, dry_run: bool = False) -> None:
    rendered = " ".join(shlex.quote(part) for part in argv)
    if dry_run:
        print(rendered)
        if input_text:
            print("--- remote stdin ---")
            print(input_text.rstrip())
        return
    subprocess.run(
        list(argv),
        input=input_text,
        text=True if input_text is not None else None,
        check=True,
    )


def _run_remote_script(
    config: RemoteAcceptanceConfig,
    script: str,
    *,
    dry_run: bool = False,
) -> None:
    _run([*_ssh_argv(config), "bash", "-se"], input_text=script, dry_run=dry_run)


def _git_rev_parse(ref: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(WORKSPACE_ROOT), "rev-parse", ref],
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout.strip()


def _temporary_bundle_ref(commit: str) -> str:
    """Return a deterministic temporary refname for git bundle creation."""

    return f"refs/codex/remote-acceptance/{commit}"


def _extract_semver(raw: str) -> str:
    match = re.search(r"(\d+\.\d+\.\d+)", raw)
    if match is None:
        raise ValueError(f"Could not extract semantic version from {raw!r}.")
    return match.group(1)


def resolve_playwright_version(
    *,
    package_json: Path = FRONTEND_ROOT / "package.json",
    package_lock: Path = FRONTEND_ROOT / "package-lock.json",
) -> str:
    """Return the exact Playwright version from the dashboard lockfile when available."""

    if package_lock.exists():
        payload = json.loads(package_lock.read_text(encoding="utf-8"))
        packages = payload.get("packages", {})
        if isinstance(packages, dict):
            entry = packages.get("node_modules/@playwright/test", {})
            if isinstance(entry, dict):
                version = entry.get("version")
                if isinstance(version, str) and version:
                    return version

    payload = json.loads(package_json.read_text(encoding="utf-8"))
    dev_dependencies = payload.get("devDependencies", {})
    spec = dev_dependencies.get("@playwright/test")
    if not isinstance(spec, str) or not spec:
        raise ValueError(
            "Could not resolve @playwright/test version from the dashboard package metadata."
        )
    return _extract_semver(spec)


def resolve_remote_python_request(snapshot_manifests: Sequence[Path] = SNAPSHOT_MANIFESTS) -> str:
    """Return the Python request that matches the tracked snapshot manifests when possible."""

    versions: set[str] = set()
    for path in snapshot_manifests:
        payload = json.loads(path.read_text(encoding="utf-8"))
        version = payload.get("python_version")
        if isinstance(version, str) and version:
            versions.add(version)

    if len(versions) == 1:
        version = next(iter(versions))
        if version.startswith(f"{PYTHON_BASELINE}."):
            return version
    return PYTHON_BASELINE


def render_toolchain_env(config: RemoteAcceptanceConfig) -> str:
    """Render the remote environment shim used by repo scripts."""

    return textwrap.dedent(
        f"""\
        export PATH={shlex.quote(config.toolchain_bin)}:\
/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
        export UV_PYTHON_INSTALL_DIR={shlex.quote(f"{config.toolchain_root}/python")}
        export UV_PYTHON={shlex.quote(f"{config.toolchain_bin}/python3")}
        export UV_PYTHON_DOWNLOADS=never
        export POLISYOS_PYTEST_WORKERS=auto
        export POLISYOS_PYTEST_DIST=worksteal
        """
    )


def build_remote_prelude(
    config: RemoteAcceptanceConfig,
    *,
    cwd: str | None = None,
    load_toolchain_env: bool = True,
) -> str:
    """Build the standard remote shell prelude."""

    lines = ["set -euo pipefail"]
    if load_toolchain_env:
        lines.append(f"source {shlex.quote(config.toolchain_env)}")
    if cwd:
        lines.append(f"cd {shlex.quote(cwd)}")
    return "\n".join(lines)


def build_provision_script(
    config: RemoteAcceptanceConfig,
    *,
    playwright_version: str,
    python_request: str,
) -> str:
    """Return the remote provisioning script."""

    env_script = render_toolchain_env(config)
    env_lines = [line for line in env_script.strip().splitlines() if line]
    env_printf = " ".join(shlex.quote(line) for line in env_lines)
    python_install_dir = f"{config.toolchain_root}/python"
    node_root = f"{config.toolchain_root}/node"
    node_current = f"{node_root}/current"
    uv_venv = f"{config.toolchain_root}/uv-venv"
    return textwrap.dedent(
        f"""\
        set -euo pipefail
        export DEBIAN_FRONTEND=noninteractive

        apt-get update
        apt-get install -y \\
          ca-certificates \\
          curl \\
          docker.io \\
          docker-compose-v2 \\
          git \\
          libfreetype-dev \\
          libjpeg-dev \\
          libopenjp2-7-dev \\
          libtiff-dev \\
          libwebp-dev \\
          python3-venv \\
          rsync \\
          unzip \\
          xz-utils \\
          zlib1g-dev

        systemctl enable --now docker

        mkdir -p \\
          {shlex.quote(config.toolchain_bin)} \\
          {shlex.quote(node_root)} \\
          {shlex.quote(python_install_dir)} \\
          {shlex.quote(config.artifacts_root)} \\
          {shlex.quote(config.worktree)} \\
          {shlex.quote(config.clean_tree)}

        if [ ! -x {shlex.quote(f"{uv_venv}/bin/uv")} ]; then
          rm -rf {shlex.quote(uv_venv)}
          python3 -m venv {shlex.quote(uv_venv)}
          {shlex.quote(f"{uv_venv}/bin/pip")} install --upgrade pip
          {shlex.quote(f"{uv_venv}/bin/pip")} install uv=={shlex.quote(UV_BASELINE)}
        fi

        ln -sfn {shlex.quote(f"{uv_venv}/bin/uv")} {shlex.quote(f"{config.toolchain_bin}/uv")}
        export PATH={shlex.quote(config.toolchain_bin)}:\
/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
        export UV_PYTHON_INSTALL_DIR={shlex.quote(python_install_dir)}

        uv --version
        uv python install \\
          --managed-python \\
          --install-dir {shlex.quote(python_install_dir)} \\
          {shlex.quote(python_request)}

        PYTHON_BIN="$(
          UV_PYTHON_INSTALL_DIR={shlex.quote(python_install_dir)} \\
            uv python find --managed-python --no-project {shlex.quote(python_request)}
        )"
        ln -sfn "$PYTHON_BIN" {shlex.quote(f"{config.toolchain_bin}/python3")}
        ln -sfn "$(dirname "$PYTHON_BIN")/python" {shlex.quote(f"{config.toolchain_bin}/python")}
        if [ -x "$(dirname "$PYTHON_BIN")/pip3" ]; then
          ln -sfn "$(dirname "$PYTHON_BIN")/pip3" {shlex.quote(f"{config.toolchain_bin}/pip3")}
        fi
        if [ -x "$(dirname "$PYTHON_BIN")/pip" ]; then
          ln -sfn "$(dirname "$PYTHON_BIN")/pip" {shlex.quote(f"{config.toolchain_bin}/pip")}
        fi
        export UV_PYTHON={shlex.quote(f"{config.toolchain_bin}/python3")}
        export UV_PYTHON_DOWNLOADS=never

        NODE_TARBALL="$(
          curl -fsSL https://nodejs.org/dist/{REMOTE_NODE_CHANNEL}/SHASUMS256.txt \\
            | awk '/linux-x64\\.tar\\.xz$/ {{print $2; exit}}'
        )"
        if [ -z "$NODE_TARBALL" ]; then
          echo "Failed to resolve a Linux x64 tarball for {REMOTE_NODE_CHANNEL}." >&2
          exit 1
        fi
        rm -f "/tmp/$NODE_TARBALL"
        curl -fsSL "https://nodejs.org/dist/{REMOTE_NODE_CHANNEL}/$NODE_TARBALL" \\
          -o "/tmp/$NODE_TARBALL"
        rm -rf {shlex.quote(node_current)}
        tar -xJf "/tmp/$NODE_TARBALL" -C {shlex.quote(node_root)}
        NODE_EXTRACT_DIR="${{NODE_TARBALL%.tar.xz}}"
        ln -sfn {shlex.quote(node_root)}/"$NODE_EXTRACT_DIR" {shlex.quote(node_current)}
        ln -sfn {shlex.quote(node_current)}/bin/node {shlex.quote(f"{config.toolchain_bin}/node")}
        ln -sfn {shlex.quote(node_current)}/bin/npm {shlex.quote(f"{config.toolchain_bin}/npm")}
        ln -sfn {shlex.quote(node_current)}/bin/npx {shlex.quote(f"{config.toolchain_bin}/npx")}

        printf '%s\\n' {env_printf} > {shlex.quote(config.toolchain_env)}

        source {shlex.quote(config.toolchain_env)}
        python3 --version
        node --version
        uv --version
        docker compose version
        npm exec --yes @playwright/test@{shlex.quote(playwright_version)} -- \\
          install-deps chromium
        """
    )


def build_clean_checkout_script(
    config: RemoteAcceptanceConfig,
    *,
    bundle_path: str,
    commit: str,
) -> str:
    """Return the remote script that expands a committed clean checkout from a git bundle."""

    return textwrap.dedent(
        f"""\
        set -euo pipefail
        mkdir -p {shlex.quote(config.bundle_dir)}
        rm -rf {shlex.quote(config.clean_tree)}
        mkdir -p {shlex.quote(config.clean_tree)}
        git -C {shlex.quote(config.clean_tree)} init
        git -C {shlex.quote(config.clean_tree)} fetch \\
          {shlex.quote(bundle_path)} \\
          {shlex.quote(commit)}
        git -C {shlex.quote(config.clean_tree)} checkout --force FETCH_HEAD
        """
    )


def _rsync_command(config: RemoteAcceptanceConfig, *, delete: bool) -> list[str]:
    argv = [
        "rsync",
        "-az",
        "--compress",
    ]
    if delete:
        argv.append("--delete")
    for pattern in RSYNC_EXCLUDES:
        argv.extend(["--exclude", pattern])
    for entry in SYNC_ROOT_ENTRIES:
        argv.append(str(WORKSPACE_ROOT / entry))
    argv.append(f"{config.ssh_target}:{config.worktree}/")
    return argv


def provision_remote(config: RemoteAcceptanceConfig, *, dry_run: bool = False) -> None:
    """Provision Docker plus the isolated Python/Node/uv toolchain."""

    version = resolve_playwright_version()
    python_request = resolve_remote_python_request()
    script = build_provision_script(
        config,
        playwright_version=version,
        python_request=python_request,
    )
    _run_remote_script(config, script, dry_run=dry_run)


def sync_workspace(config: RemoteAcceptanceConfig, *, delete: bool, dry_run: bool = False) -> None:
    """Sync the local workspace into the remote worktree."""

    prepare = textwrap.dedent(
        f"""\
        set -euo pipefail
        mkdir -p {shlex.quote(config.worktree)} {shlex.quote(config.artifacts_root)}
        find {shlex.quote(config.worktree)} -mindepth 1 -maxdepth 1 \\
          ! -name README.md \\
          ! -name SECURITY.md \\
          ! -name renovate.json \\
          ! -name .github \\
          ! -name policy-engine \\
          -exec rm -rf {{}} +
        for target in \\
          {config.worktree}/policy-engine/.hypothesis \\
          {config.worktree}/policy-engine/.polisyos \\
          {config.worktree}/policy-engine/.uv-cache \\
          {config.worktree}/policy-engine/.tmp* \\
          {config.worktree}/policy-engine/site \\
          {config.worktree}/policy-engine/data/raw \\
          {config.worktree}/policy-engine/runs \\
          {config.worktree}/policy-engine/logs \\
          {config.worktree}/policy-engine/benchmark-results \\
          {config.worktree}/policy-engine/production_data; do
          rm -rf "$target"
        done
        """
    )
    _run_remote_script(config, prepare, dry_run=dry_run)
    _run(_rsync_command(config, delete=delete), dry_run=dry_run)


def exec_remote(
    config: RemoteAcceptanceConfig,
    argv: Sequence[str],
    *,
    cwd: str,
    load_toolchain_env: bool,
    dry_run: bool = False,
) -> None:
    """Execute an arbitrary command on the remote host."""

    normalized_argv = tuple(argv[1:]) if argv and argv[0] == "--" else tuple(argv)
    if not normalized_argv:
        raise SystemExit("remote exec requires a command after `--`.")
    command = " ".join(shlex.quote(part) for part in normalized_argv)
    script = build_remote_prelude(config, cwd=cwd, load_toolchain_env=load_toolchain_env)
    script = f"{script}\n{command}\n"
    _run_remote_script(config, script, dry_run=dry_run)


def create_clean_checkout(
    config: RemoteAcceptanceConfig,
    *,
    ref: str,
    dry_run: bool = False,
) -> None:
    """Upload a git bundle and materialize a detached clean checkout on the remote host."""

    commit = _git_rev_parse(ref)
    bundle_ref = _temporary_bundle_ref(commit)
    with tempfile.TemporaryDirectory(prefix="polisyos-remote-bundle.") as tmpdir:
        bundle = Path(tmpdir) / f"polisyos-{commit[:12]}.bundle"
        try:
            _run(
                [
                    "git",
                    "-C",
                    str(WORKSPACE_ROOT),
                    "update-ref",
                    bundle_ref,
                    commit,
                ],
                dry_run=dry_run,
            )
            _run(
                [
                    "git",
                    "-C",
                    str(WORKSPACE_ROOT),
                    "bundle",
                    "create",
                    str(bundle),
                    bundle_ref,
                ],
                dry_run=dry_run,
            )
        finally:
            _run(
                ["git", "-C", str(WORKSPACE_ROOT), "update-ref", "-d", bundle_ref],
                dry_run=dry_run,
            )
        prepare = textwrap.dedent(
            f"""\
            set -euo pipefail
            mkdir -p {shlex.quote(config.bundle_dir)}
            """
        )
        _run_remote_script(config, prepare, dry_run=dry_run)
        _run(
            [
                "rsync",
                "-az",
                str(bundle),
                f"{config.ssh_target}:{config.bundle_dir}/{bundle.name}",
            ],
            dry_run=dry_run,
        )
        script = build_clean_checkout_script(
            config,
            bundle_path=f"{config.bundle_dir}/{bundle.name}",
            commit=commit,
        )
        _run_remote_script(config, script, dry_run=dry_run)


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config = _config_from_args(args)

    if args.command == "provision":
        provision_remote(config, dry_run=args.dry_run)
        return 0
    if args.command == "sync":
        sync_workspace(config, delete=not args.no_delete, dry_run=args.dry_run)
        return 0
    if args.command == "exec":
        exec_remote(
            config,
            args.argv,
            cwd=args.cwd,
            load_toolchain_env=not args.no_toolchain_env,
            dry_run=args.dry_run,
        )
        return 0
    if args.command == "clean-checkout":
        create_clean_checkout(config, ref=args.ref, dry_run=args.dry_run)
        return 0
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
