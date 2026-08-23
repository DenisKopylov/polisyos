#!/usr/bin/env python3
"""Run a local validation pass that approximates the main CI surfaces."""

from __future__ import annotations

import argparse
import sys
import textwrap

from ._common import FRONTEND_ROOT, PRODUCT_ROOT, CommandSpec, run_command, uv_command

LAST_MILE_CI_PARITY_HELP = """
Last-mile CI-parity gates:
  - workspace verify fail-fast last-mile gates
  - directory_health.py no-regression ratchet
  - report_test_ratchets.py mirror/property/helper topology ratchets
  - architecture_report_only_contracts.py phase6-1 and module-size contracts
  - check_debt_ledger.py reporting-only reconciliation
  - check_extension_examples.py install/discovery/smoke coverage
  - generate_adr_index.py --check when docs checks are enabled
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a local validation pass that approximates the main CI jobs.",
        epilog=textwrap.dedent(LAST_MILE_CI_PARITY_HELP).strip(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--skip-doctor", action="store_true", help="Skip workstation preflight.")
    parser.add_argument("--backend-only", action="store_true", help="Skip frontend parity checks.")
    parser.add_argument("--frontend-only", action="store_true", help="Skip backend parity checks.")
    parser.add_argument("--skip-docs", action="store_true", help="Skip docs-quality checks.")
    parser.add_argument(
        "--skip-runtime-http",
        action="store_true",
        help="Skip runtime/http pytest coverage.",
    )
    parser.add_argument(
        "--skip-browser",
        action="store_true",
        help="Skip Playwright-backed Storybook and accessibility suites.",
    )
    parser.add_argument(
        "--include-e2e-smoke",
        action="store_true",
        help="Include the Playwright smoke journey suite.",
    )
    parser.add_argument(
        "--include-visual",
        action="store_true",
        help="Include the Playwright visual regression suite.",
    )
    parser.add_argument(
        "--surface",
        action="append",
        default=[],
        help="Optional env surfaces to validate if doctor runs (repeatable).",
    )
    return parser


def _doctor_command(surfaces: list[str]) -> tuple[str, ...]:
    command = [
        sys.executable,
        "-m",
        "tools.devx.workspace.doctor",
    ]
    for surface in surfaces:
        command.extend(["--surface", surface])
    return tuple(command)


def _backend_commands(*, skip_runtime_http: bool, skip_docs: bool) -> list[CommandSpec]:
    uv = uv_command()
    commands = [
        CommandSpec(
            label="verify backend fast gate",
            argv=(
                sys.executable,
                "-m",
                "tools.devx.workspace.verify",
                "--backend-only",
                "--skip-doctor",
            ),
            cwd=PRODUCT_ROOT,
        ),
    ]

    if not skip_runtime_http:
        commands.append(
            CommandSpec(
                label="pytest runtime/http",
                argv=(*uv, "run", "pytest", "tests/unit/runtime/http"),
                cwd=PRODUCT_ROOT,
            )
        )

    commands.extend(_last_mile_policy_commands(skip_docs=skip_docs))

    if not skip_docs:
        commands.extend(
            [
                CommandSpec(
                    label="check docs accuracy",
                    argv=(
                        *uv,
                        "run",
                        "--extra",
                        "docs",
                        "python",
                        "tools/quality/validation/check_docs_accuracy.py",
                        "--repo-root",
                        ".",
                    ),
                    cwd=PRODUCT_ROOT,
                ),
                CommandSpec(
                    label="build docs in strict mode",
                    argv=(
                        *uv,
                        "run",
                        "--extra",
                        "docs",
                        "python",
                        "-m",
                        "mkdocs",
                        "build",
                        "--strict",
                    ),
                    cwd=PRODUCT_ROOT,
                ),
                CommandSpec(
                    label="check semantic docstring quality",
                    argv=(
                        *uv,
                        "run",
                        "--extra",
                        "docs",
                        "python",
                        "tools/quality/validation/check_docstring_quality.py",
                        "--repo-root",
                        ".",
                        "--allowlist",
                        "tools/quality/validation/docstring_quality_allowlist.txt",
                        "--coverage-scope",
                        "public-surface",
                        "--minimum-coverage",
                        "85",
                    ),
                    cwd=PRODUCT_ROOT,
                ),
            ]
        )

    return commands


def _last_mile_policy_commands(*, skip_docs: bool) -> list[CommandSpec]:
    uv = uv_command()
    commands = [
        CommandSpec(
            label="check directory health ratchet",
            argv=(
                *uv,
                "run",
                "python",
                "tools/quality/validation/directory_health.py",
                "--repo-root",
                ".",
                "--json-output",
                "_build/.tmp/last-mile/directory-health.json",
                "--markdown-output",
                "_build/.tmp/last-mile/directory-health.md",
                "--fail-on-regression",
            ),
            cwd=PRODUCT_ROOT,
        ),
        CommandSpec(
            label="check test ratchets and helper topology",
            argv=(
                *uv,
                "run",
                "python",
                "tools/quality/testing/report_test_ratchets.py",
                "--format",
                "json",
                "--output",
                "_build/.tmp/last-mile/test-ratchets.json",
                "--fail-on-regression",
            ),
            cwd=PRODUCT_ROOT,
        ),
        CommandSpec(
            label="check architecture phase6-1 report-only contracts",
            argv=(
                *uv,
                "run",
                "python",
                "tools/quality/validation/architecture_report_only_contracts.py",
                "--report",
                "phase6-1",
                "--json-output",
                "_build/.tmp/last-mile/architecture-phase6-1.json",
                "--fail-on-contract-errors",
            ),
            cwd=PRODUCT_ROOT,
        ),
        CommandSpec(
            label="check validator module-size budget",
            argv=(
                *uv,
                "run",
                "python",
                "tools/quality/validation/architecture_report_only_contracts.py",
                "--report",
                "module-size",
                "--json-output",
                "_build/.tmp/last-mile/module-size.json",
                "--fail-on-contract-errors",
            ),
            cwd=PRODUCT_ROOT,
        ),
        CommandSpec(
            label="report debt ledger reconciliation",
            argv=(
                *uv,
                "run",
                "python",
                "tools/quality/validation/check_debt_ledger.py",
                "--check",
                "--report-only",
            ),
            cwd=PRODUCT_ROOT,
        ),
        CommandSpec(
            label="check extension example installability",
            argv=(
                *uv,
                "run",
                "python",
                "tools/quality/validation/check_extension_examples.py",
            ),
            cwd=PRODUCT_ROOT,
        ),
    ]
    if not skip_docs:
        commands.append(
            CommandSpec(
                label="check ADR thematic index freshness",
                argv=(
                    *uv,
                    "run",
                    "python",
                    "tools/quality/validation/generate_adr_index.py",
                    "--check",
                ),
                cwd=PRODUCT_ROOT,
            )
        )
    return commands


def _frontend_commands(
    *,
    skip_browser: bool,
    include_e2e_smoke: bool,
    include_visual: bool,
) -> list[CommandSpec]:
    commands = [
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
        CommandSpec(label="npm coverage", argv=("npm", "run", "test:coverage"), cwd=FRONTEND_ROOT),
        CommandSpec(label="npm build", argv=("npm", "run", "build"), cwd=FRONTEND_ROOT),
        CommandSpec(
            label="npm build-storybook",
            argv=("npm", "run", "build-storybook"),
            cwd=FRONTEND_ROOT,
        ),
    ]

    if not skip_browser:
        commands.extend(
            [
                CommandSpec(
                    label="Playwright browser install",
                    argv=("npm", "run", "playwright:install"),
                    cwd=FRONTEND_ROOT,
                ),
                CommandSpec(
                    label="npm Storybook interaction tests",
                    argv=("npm", "run", "test:storybook"),
                    cwd=FRONTEND_ROOT,
                ),
                CommandSpec(
                    label="npm accessibility suite",
                    argv=("npm", "run", "test:a11y"),
                    cwd=FRONTEND_ROOT,
                ),
            ]
        )

    if include_e2e_smoke:
        commands.append(
            CommandSpec(
                label="npm Playwright smoke journeys",
                argv=("npm", "run", "test:e2e:smoke"),
                cwd=FRONTEND_ROOT,
            )
        )
    if include_visual:
        commands.append(
            CommandSpec(
                label="npm Playwright visual regression",
                argv=("npm", "run", "test:visual"),
                cwd=FRONTEND_ROOT,
            )
        )

    return commands


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
        commands.extend(
            _backend_commands(
                skip_runtime_http=args.skip_runtime_http,
                skip_docs=args.skip_docs,
            )
        )
    if not args.backend_only:
        commands.extend(
            _frontend_commands(
                skip_browser=args.skip_browser,
                include_e2e_smoke=args.include_e2e_smoke,
                include_visual=args.include_visual,
            )
        )

    for command in commands:
        run_command(command)

    print("[ci-parity] local CI parity checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
