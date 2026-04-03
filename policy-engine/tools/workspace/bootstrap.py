#!/usr/bin/env python3
"""Bootstrap a contributor machine for the policy-engine workspace."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

from _common import (
    DEFAULT_UV_SYNC_PROFILE,
    FRONTEND_ROOT,
    PRODUCT_ROOT,
    PYTHON_BASELINE,
    UV_BASELINE,
    UV_SYNC_PROFILES,
    CommandSpec,
    baseline_uv_binary,
    node_baseline_matches,
    python_baseline_matches,
    run_command,
    uv_command,
    version_text,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install and verify the local contributor prerequisites for policy-engine.",
    )
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="Skip npm install for the dashboard.",
    )
    parser.add_argument(
        "--skip-playwright",
        action="store_true",
        help="Skip Playwright browser installation.",
    )
    parser.add_argument("--skip-hooks", action="store_true", help="Skip pre-commit installation.")
    parser.add_argument("--skip-doctor", action="store_true", help="Do not run doctor at the end.")
    parser.add_argument(
        "--surface",
        action="append",
        default=[],
        help="Optional surface to validate when doctor runs (repeatable).",
    )
    parser.add_argument(
        "--no-install-uv",
        action="store_true",
        help="Fail instead of auto-installing uv when it is missing from PATH.",
    )
    parser.add_argument(
        "--profile",
        choices=sorted(UV_SYNC_PROFILES),
        default=DEFAULT_UV_SYNC_PROFILE,
        help=(
            "Dependency tier to sync before optional frontend/bootstrap steps. "
            f"Default: {DEFAULT_UV_SYNC_PROFILE}."
        ),
    )
    return parser


def _ensure_python_baseline() -> None:
    version_info = (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
    if not python_baseline_matches(version_info):
        rendered = ".".join(str(part) for part in version_info)
        raise SystemExit(
            "bootstrap requires Python "
            f"{PYTHON_BASELINE}.x, but current interpreter is {rendered} "
            f"({sys.executable})."
        )


def _ensure_uv_available(*, allow_install: bool) -> None:
    if baseline_uv_binary():
        return
    if not allow_install:
        raise SystemExit(
            "bootstrap requires uv "
            f"{UV_BASELINE}, but a matching version was not found. Install the pinned "
            "version first, then rerun bootstrap."
        )

    print(
        "[bootstrap] pinned uv "
        f"{UV_BASELINE} not found; installing it via pip for the current Python interpreter."
    )
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--user", f"uv=={UV_BASELINE}"],
        cwd=PRODUCT_ROOT,
        check=True,
    )
    if baseline_uv_binary() is None:
        local_path = str(Path.home() / ".local" / "bin")
        raise SystemExit(
            "Installed uv "
            f"{UV_BASELINE}, but bootstrap could not resolve it. Ensure {local_path} "
            "is available to your shell and rerun bootstrap."
        )


def _ensure_node_baseline(*, skip_frontend: bool) -> None:
    if skip_frontend:
        return
    try:
        node_version = version_text(("node", "--version"))
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SystemExit("bootstrap requires Node 22.x for frontend workflows.") from exc

    if not node_baseline_matches(node_version):
        raise SystemExit(
            f"bootstrap requires Node 22.x for frontend workflows, but found {node_version}."
        )


def _doctor_command(surfaces: list[str]) -> tuple[str, ...]:
    command = [sys.executable, "tools/workspace/doctor.py"]
    for surface in surfaces:
        command.extend(["--surface", surface])
    return tuple(command)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    _ensure_python_baseline()
    _ensure_uv_available(allow_install=not args.no_install_uv)
    _ensure_node_baseline(skip_frontend=args.skip_frontend)

    uv = uv_command()
    sync_args: list[str] = [*uv, "sync", "--frozen"]
    for extra in UV_SYNC_PROFILES[args.profile]:
        sync_args.extend(["--extra", extra])
    commands = [
        CommandSpec(
            label="uv sync",
            argv=tuple(sync_args),
            cwd=PRODUCT_ROOT,
        ),
    ]

    if not args.skip_hooks:
        commands.append(
            CommandSpec(
                label="pre-commit install",
                argv=(*uv, "run", "pre-commit", "install"),
                cwd=PRODUCT_ROOT,
            )
        )

    if not args.skip_frontend:
        commands.append(
            CommandSpec(
                label="npm ci",
                argv=("npm", "ci", "--ignore-scripts"),
                cwd=FRONTEND_ROOT,
            )
        )
        if not args.skip_playwright:
            commands.append(
                CommandSpec(
                    label="Playwright browser install",
                    argv=("npm", "run", "playwright:install"),
                    cwd=FRONTEND_ROOT,
                )
            )

    if not args.skip_doctor:
        commands.append(
            CommandSpec(
                label="doctor",
                argv=_doctor_command(args.surface),
                cwd=PRODUCT_ROOT,
            )
        )

    for command in commands:
        run_command(command)

    print("[bootstrap] contributor machine is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
