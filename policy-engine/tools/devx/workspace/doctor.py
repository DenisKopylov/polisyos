#!/usr/bin/env python3
"""Preflight validation for contributor machines and local quality gates."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass

from tools._lib.imports import ensure_repo_import_roots

ensure_repo_import_roots(__file__, include_src_root=False)

from ._common import (
    FRONTEND_ROOT,
    OPTIONAL_SURFACES,
    PRODUCT_ROOT,
    PYTHON_BASELINE,
    UV_BASELINE,
    node_baseline_matches,
    python_baseline_matches,
    surface_status,
    uv_baseline_matches,
    uv_command,
    version_text,
)

PLAYWRIGHT_SMOKE = """
const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch({ headless: true });
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
""".strip()


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One doctor check outcome."""

    name: str
    ok: bool
    message: str


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate local prerequisites for policy-engine.")
    parser.add_argument(
        "--surface",
        action="append",
        default=[],
        choices=sorted(OPTIONAL_SURFACES),
        help="Optional env surface to validate (repeatable).",
    )
    parser.add_argument(
        "--list-surfaces",
        action="store_true",
        help="Print known optional surfaces and exit.",
    )
    parser.add_argument(
        "--skip-playwright",
        action="store_true",
        help="Skip the Playwright browser smoke-check.",
    )
    parser.add_argument(
        "--skip-lockfile-checks",
        action="store_true",
        help="Skip uv.lock and package-lock freshness checks.",
    )
    parser.add_argument(
        "--skip-contract-checks",
        action="store_true",
        help="Skip generated-contract freshness checks.",
    )
    return parser


def _print_surfaces() -> int:
    for name in sorted(OPTIONAL_SURFACES):
        description = OPTIONAL_SURFACES[name]["description"]
        assert isinstance(description, str)
        print(f"{name}: {description}")
    return 0


def _run_checked(argv: list[str], *, cwd: str | None = None) -> None:
    subprocess.run(argv, cwd=cwd or str(PRODUCT_ROOT), check=True)


def _check_python() -> CheckResult:
    version_info = (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
    rendered = ".".join(str(part) for part in version_info)
    if python_baseline_matches(version_info):
        return CheckResult("python", True, f"Python {rendered} via {sys.executable}")
    return CheckResult(
        "python",
        False,
        f"Expected Python {PYTHON_BASELINE}.x, found {rendered} via {sys.executable}",
    )


def _check_node() -> CheckResult:
    try:
        node_version = version_text(("node", "--version"))
    except (subprocess.CalledProcessError, FileNotFoundError):
        return CheckResult("node", False, "Node is missing from PATH; expected Node 22.x")

    if node_baseline_matches(node_version):
        return CheckResult("node", True, f"Node {node_version}")
    return CheckResult("node", False, f"Expected Node 22.x, found {node_version}")


def _check_uv() -> CheckResult:
    command = uv_command()
    if command[0] == sys.executable:
        return CheckResult("uv", False, "uv is missing from PATH")

    try:
        rendered = version_text((command[0], "--version"))
    except subprocess.CalledProcessError:
        return CheckResult("uv", False, f"uv exists at {command[0]} but failed to execute")

    if not uv_baseline_matches(rendered):
        return CheckResult(
            "uv",
            False,
            f"Expected uv {UV_BASELINE}, found {rendered} at {command[0]}",
        )
    return CheckResult("uv", True, f"{rendered} at {command[0]}")


def _check_playwright() -> CheckResult:
    try:
        _run_checked(["node", "-e", PLAYWRIGHT_SMOKE], cwd=str(FRONTEND_ROOT))
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return CheckResult(
            "playwright",
            False,
            f"Chromium launch smoke-check failed in frontend/runtime-dashboard ({exc})",
        )
    return CheckResult("playwright", True, "Chromium browser is launchable")


def _check_lockfiles() -> list[CheckResult]:
    results: list[CheckResult] = []
    uv = list(uv_command())

    try:
        _run_checked([*uv, "lock", "--check"])
    except subprocess.CalledProcessError as exc:
        results.append(CheckResult("uv.lock", False, f"uv.lock is stale or inconsistent ({exc})"))
    else:
        results.append(CheckResult("uv.lock", True, "uv.lock is up to date"))

    try:
        _run_checked(
            ["npm", "ci", "--dry-run", "--ignore-scripts", "--no-audit", "--no-fund"],
            cwd=str(FRONTEND_ROOT),
        )
    except subprocess.CalledProcessError as exc:
        results.append(
            CheckResult(
                "package-lock",
                False,
                f"package-lock.json is stale or inconsistent ({exc})",
            )
        )
    else:
        results.append(CheckResult("package-lock", True, "package-lock.json matches package.json"))

    return results


def _check_generated_contracts() -> list[CheckResult]:
    results: list[CheckResult] = []
    uv = list(uv_command())

    contract_commands = [
        (
            "schemas",
            [*uv, "run", "--extra", "ml", "python", "tools/diagnostics/gen_schema.py", "--check"],
        ),
        (
            "runtime-openapi",
            [
                *uv,
                "run",
                "--extra",
                "runtime",
                "--extra",
                "ml",
                "python",
                "tools/runtime/check_runtime_api_contract.py",
            ],
        ),
        (
            "frontend-contracts",
            ["npm", "run", "contracts:verify"],
        ),
    ]

    for name, argv in contract_commands:
        try:
            target_root = FRONTEND_ROOT if name == "frontend-contracts" else PRODUCT_ROOT
            _run_checked(argv, cwd=str(target_root))
        except subprocess.CalledProcessError as exc:
            results.append(CheckResult(name, False, f"Generated contract check failed ({exc})"))
        else:
            results.append(CheckResult(name, True, "fresh"))

    return results


def _check_optional_surfaces(surfaces: list[str]) -> list[CheckResult]:
    if not surfaces:
        return [CheckResult("optional-surfaces", True, "No optional surfaces selected")]

    results: list[CheckResult] = []
    for surface in surfaces:
        ok, message = surface_status(surface)
        results.append(CheckResult(surface, ok, message))
    return results


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.list_surfaces:
        return _print_surfaces()

    results = [_check_python(), _check_node(), _check_uv()]

    if not args.skip_playwright:
        results.append(_check_playwright())
    if not args.skip_lockfile_checks:
        results.extend(_check_lockfiles())
    if not args.skip_contract_checks:
        results.extend(_check_generated_contracts())

    results.extend(_check_optional_surfaces(args.surface))

    failures = [result for result in results if not result.ok]
    for result in results:
        marker = "PASS" if result.ok else "FAIL"
        print(f"[{marker}] {result.name}: {result.message}")

    if failures:
        print(f"doctor failed with {len(failures)} issue(s).")
        return 1

    print("doctor passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
