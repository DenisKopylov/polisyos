#!/usr/bin/env python3
"""Run the standard fast local gate for policy-engine contributors."""

from __future__ import annotations

import argparse
import os
import sys

from tools._lib.imports import ensure_repo_import_roots

ensure_repo_import_roots(__file__, include_src_root=False)

from ._common import FRONTEND_ROOT, PRODUCT_ROOT, CommandSpec, run_command, uv_command

PYTEST_WORKERS_ENV = "POLISYOS_PYTEST_WORKERS"
PYTEST_DIST_ENV = "POLISYOS_PYTEST_DIST"
DEFAULT_PYTEST_DIST = "worksteal"
PYTEST_NUMERICAL_ENV = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the standard fast local gate.")
    parser.add_argument("--skip-doctor", action="store_true", help="Skip workstation preflight.")
    parser.add_argument("--backend-only", action="store_true", help="Skip frontend checks.")
    parser.add_argument("--frontend-only", action="store_true", help="Skip backend checks.")
    parser.add_argument(
        "--pytest-workers",
        help=(
            "Parallelize non-benchmark backend pytest with pytest-xdist. "
            "Accepts a positive integer or 'auto'. Defaults to "
            f"${PYTEST_WORKERS_ENV} when set."
        ),
    )
    parser.add_argument(
        "--surface",
        action="append",
        default=[],
        help="Optional surfaces to validate if doctor runs (repeatable).",
    )
    return parser


def _doctor_command(surfaces: list[str]) -> tuple[str, ...]:
    command = [
        sys.executable,
        "tools/workspace/doctor.py",
        "--skip-contract-checks",
    ]
    for surface in surfaces:
        command.extend(["--surface", surface])
    return tuple(command)


def _resolve_pytest_workers(requested: str | None) -> str | None:
    raw = requested
    if raw is None:
        raw = os.environ.get(PYTEST_WORKERS_ENV)
    if raw is None:
        return None

    value = raw.strip().lower()
    if not value:
        return None
    if value == "auto":
        return value
    try:
        workers = int(value)
    except ValueError as exc:
        raise SystemExit(
            f"--pytest-workers / ${PYTEST_WORKERS_ENV} must be a positive integer or 'auto'."
        ) from exc
    if workers < 1:
        raise SystemExit(
            f"--pytest-workers / ${PYTEST_WORKERS_ENV} must be a positive integer or 'auto'."
        )
    return str(workers)


def _resolve_pytest_dist() -> str:
    value = os.environ.get(PYTEST_DIST_ENV, DEFAULT_PYTEST_DIST).strip()
    return value or DEFAULT_PYTEST_DIST


def _build_backend_pytest_commands(
    *,
    pytest_workers: str | None,
    pytest_dist: str,
    xdist_available: bool | None = None,
) -> list[CommandSpec]:
    uv = uv_command()
    if xdist_available is None:
        # `uv run pytest` executes inside the project environment, which can have a
        # different package set than the interpreter running this wrapper script.
        # Treat xdist as available by contract when parallel workers are requested.
        xdist_available = True

    base_pytest_args = ("pytest", "-m", "not integration", "--ignore=tests/runtime/http")
    if pytest_workers is None or pytest_workers == "1" or not xdist_available:
        return [
            CommandSpec(
                label="pytest fast backend gate",
                argv=(*uv, "run", *base_pytest_args),
                cwd=PRODUCT_ROOT,
                env=PYTEST_NUMERICAL_ENV,
            )
        ]

    return [
        CommandSpec(
            label="pytest fast backend gate (parallel non-benchmark)",
            argv=(
                *uv,
                "run",
                "pytest",
                "-n",
                pytest_workers,
                "--dist",
                pytest_dist,
                "-m",
                "not integration and not benchmark",
                "--ignore=tests/runtime/http",
            ),
            cwd=PRODUCT_ROOT,
            env=PYTEST_NUMERICAL_ENV,
        ),
        CommandSpec(
            label="pytest fast backend benchmarks",
            argv=(
                *uv,
                "run",
                "pytest",
                "-m",
                "benchmark and not integration",
                "--ignore=tests/runtime/http",
            ),
            cwd=PRODUCT_ROOT,
            env=PYTEST_NUMERICAL_ENV,
        ),
    ]


def _backend_commands(*, pytest_workers: str | None, pytest_dist: str) -> list[CommandSpec]:
    uv = uv_command()
    return [
        CommandSpec(
            label="lint imports",
            argv=(
                *uv,
                "run",
                "python",
                "tools/lint/lint_imports.py",
                "--policy",
                "import_policy.toml",
                "--exceptions",
                "import_exceptions.toml",
            ),
            cwd=PRODUCT_ROOT,
        ),
        CommandSpec(
            label="lint foundry",
            argv=(*uv, "run", "python", "tools/lint/lint_foundry.py", "--repo-root", "."),
            cwd=PRODUCT_ROOT,
        ),
        CommandSpec(
            label="check state reads",
            argv=(*uv, "run", "python", "tools/diagnostics/check_state_reads.py"),
            cwd=PRODUCT_ROOT,
        ),
        CommandSpec(
            label="check scholar imports",
            argv=(*uv, "run", "python", "tools/lint/check_scholar_imports.py"),
            cwd=PRODUCT_ROOT,
        ),
        CommandSpec(
            label="check connector contracts",
            argv=(*uv, "run", "python", "tools/connectors/check_contracts.py", "--check"),
            cwd=PRODUCT_ROOT,
        ),
        CommandSpec(
            label="check schema freshness",
            argv=(
                *uv,
                "run",
                "--extra",
                "ml",
                "python",
                "tools/diagnostics/gen_schema.py",
                "--check",
            ),
            cwd=PRODUCT_ROOT,
        ),
        CommandSpec(
            label="check runtime API contract",
            argv=(
                *uv,
                "run",
                "--extra",
                "runtime",
                "--extra",
                "ml",
                "python",
                "tools/runtime/check_runtime_api_contract.py",
            ),
            cwd=PRODUCT_ROOT,
        ),
        *_build_backend_pytest_commands(
            pytest_workers=pytest_workers,
            pytest_dist=pytest_dist,
        ),
    ]


def _frontend_commands() -> list[CommandSpec]:
    return [
        CommandSpec(label="npm typecheck", argv=("npm", "run", "typecheck"), cwd=FRONTEND_ROOT),
        CommandSpec(label="npm lint", argv=("npm", "run", "lint"), cwd=FRONTEND_ROOT),
        CommandSpec(
            label="npm format check",
            argv=("npm", "run", "format:check"),
            cwd=FRONTEND_ROOT,
        ),
        CommandSpec(
            label="npm architecture check",
            argv=("npm", "run", "check:architecture"),
            cwd=FRONTEND_ROOT,
        ),
        CommandSpec(
            label="npm contract fixtures",
            argv=("npm", "run", "contracts:verify"),
            cwd=FRONTEND_ROOT,
        ),
        CommandSpec(label="npm test", argv=("npm", "run", "test"), cwd=FRONTEND_ROOT),
    ]


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.backend_only and args.frontend_only:
        raise SystemExit("--backend-only and --frontend-only are mutually exclusive.")
    pytest_workers = _resolve_pytest_workers(args.pytest_workers)
    pytest_dist = _resolve_pytest_dist()

    commands: list[CommandSpec] = []
    if not args.skip_doctor:
        commands.append(
            CommandSpec(
                label="doctor",
                argv=_doctor_command(args.surface),
                cwd=PRODUCT_ROOT,
            )
        )

    if not args.frontend_only:
        commands.extend(
            _backend_commands(
                pytest_workers=pytest_workers,
                pytest_dist=pytest_dist,
            )
        )
    if not args.backend_only:
        commands.extend(_frontend_commands())

    for command in commands:
        run_command(command)

    print("[verify] fast local gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
