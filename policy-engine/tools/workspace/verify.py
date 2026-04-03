#!/usr/bin/env python3
"""Run the standard fast local gate for policy-engine contributors."""

from __future__ import annotations

import argparse
import sys

from _common import FRONTEND_ROOT, PRODUCT_ROOT, CommandSpec, run_command, uv_command


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the standard fast local gate.")
    parser.add_argument("--skip-doctor", action="store_true", help="Skip workstation preflight.")
    parser.add_argument("--backend-only", action="store_true", help="Skip frontend checks.")
    parser.add_argument("--frontend-only", action="store_true", help="Skip backend checks.")
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


def _backend_commands() -> list[CommandSpec]:
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
        CommandSpec(
            label="pytest fast backend gate",
            argv=(*uv, "run", "pytest", "-m", "not integration", "--ignore=tests/runtime/http"),
            cwd=PRODUCT_ROOT,
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
        commands.extend(_backend_commands())
    if not args.backend_only:
        commands.extend(_frontend_commands())

    for command in commands:
        run_command(command)

    print("[verify] fast local gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
