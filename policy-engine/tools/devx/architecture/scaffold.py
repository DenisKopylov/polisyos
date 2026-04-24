#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from tools._lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Unified scaffolding entrypoint for architecture-facing templates."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    package_readme = subparsers.add_parser("package-readme", help="Render a package/module README.")
    package_readme.add_argument("--module", required=True, help="Fully qualified module name.")
    package_readme.add_argument("--title", help="Human-readable package title.")
    package_readme.add_argument("--output", type=Path, required=True)
    package_readme.add_argument("--dry-run", action="store_true")

    connector = subparsers.add_parser(
        "connector", help="Delegate to the existing connector scaffold."
    )
    connector.add_argument("--name", required=True)
    connector.add_argument("--type", choices=("REST", "CSV", "SQL", "SDMX"), required=True)
    connector.add_argument("--dry-run", action="store_true")

    governance = subparsers.add_parser(
        "governance-pass", help="Render a governance-pass source and test template."
    )
    governance.add_argument("--name", required=True, help="Pass name in snake_case.")
    governance.add_argument("--class-name", help="Optional explicit class name.")
    governance.add_argument("--output", type=Path, required=True)
    governance.add_argument("--test-output", type=Path)
    governance.add_argument("--dry-run", action="store_true")

    runtime_route = subparsers.add_parser("runtime-route", help="Render a runtime-route template.")
    runtime_route.add_argument("--name", required=True, help="Route name in snake_case.")
    runtime_route.add_argument("--output", type=Path, required=True)
    runtime_route.add_argument("--dry-run", action="store_true")

    benchmark = subparsers.add_parser("benchmark", help="Render a benchmark skeleton.")
    benchmark.add_argument("--suite", required=True, help="Benchmark suite directory name.")
    benchmark.add_argument("--name", required=True, help="Benchmark file name without suffix.")
    benchmark.add_argument("--output", type=Path, required=True)
    benchmark.add_argument("--dry-run", action="store_true")

    adr = subparsers.add_parser("adr", help="Render an ADR markdown template.")
    adr.add_argument("--number", required=True, help="ADR number, e.g. 0097.")
    adr.add_argument("--slug", required=True, help="ADR slug.")
    adr.add_argument("--title", required=True, help="Human-readable ADR title.")
    adr.add_argument("--output", type=Path, required=True)
    adr.add_argument("--dry-run", action="store_true")

    runbook = subparsers.add_parser("runbook", help="Render a runbook markdown template.")
    runbook.add_argument("--name", required=True, help="Runbook short name.")
    runbook.add_argument("--title", required=True, help="Runbook title.")
    runbook.add_argument("--output", type=Path, required=True)
    runbook.add_argument("--dry-run", action="store_true")

    return parser.parse_args()


def _to_class_name(name: str) -> str:
    parts = re.split(r"[_\-\s]+", name)
    return "".join(part.capitalize() for part in parts if part)


def _load_template(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def _render_template(name: str, context: dict[str, str]) -> str:
    content = _load_template(name)
    for key, value in context.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    return content


def _emit(path: Path, content: str, *, dry_run: bool) -> None:
    if dry_run:
        print(f"===== {path}")
        print(content.rstrip())
        print()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_connector(args: argparse.Namespace) -> int:
    command = [
        sys.executable,
        str(REPO_ROOT / "tools" / "connectors" / "scaffold.py"),
        "create",
        "--name",
        args.name,
        "--type",
        args.type,
    ]
    if args.dry_run:
        command.append("--dry-run")
    completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
    return int(completed.returncode)


def _run_package_readme(args: argparse.Namespace) -> int:
    title = args.title or args.module.split(".")[-1].replace("_", " ").title()
    content = _render_template(
        "package_readme.md.tmpl",
        {
            "module": args.module,
            "title": title,
            "today": date.today().isoformat(),
        },
    )
    _emit(args.output, content, dry_run=args.dry_run)
    return 0


def _run_governance_pass(args: argparse.Namespace) -> int:
    class_name = args.class_name or f"{_to_class_name(args.name)}Pass"
    code_prefix = re.sub(r"[^A-Z0-9]+", "_", args.name.upper()).strip("_") or "PASS"
    source = _render_template(
        "governance_pass.py.tmpl",
        {
            "class_name": class_name,
            "pass_id": args.name,
            "issue_code_prefix": code_prefix,
        },
    )
    _emit(args.output, source, dry_run=args.dry_run)
    if args.test_output is not None:
        test_source = _render_template(
            "governance_pass_test.py.tmpl",
            {
                "class_name": class_name,
                "pass_id": args.name,
                "module_name": args.output.stem,
                "issue_code_prefix": code_prefix,
            },
        )
        _emit(args.test_output, test_source, dry_run=args.dry_run)
    return 0


def _run_runtime_route(args: argparse.Namespace) -> int:
    class_stem = _to_class_name(args.name)
    source = _render_template(
        "runtime_route.py.tmpl",
        {
            "route_name": args.name,
            "route_class": class_stem,
        },
    )
    _emit(args.output, source, dry_run=args.dry_run)
    return 0


def _run_benchmark(args: argparse.Namespace) -> int:
    source = _render_template(
        "benchmark.py.tmpl",
        {
            "suite": args.suite,
            "benchmark_name": args.name,
            "benchmark_class": _to_class_name(args.name),
        },
    )
    _emit(args.output, source, dry_run=args.dry_run)
    return 0


def _run_adr(args: argparse.Namespace) -> int:
    source = _render_template(
        "adr.md.tmpl",
        {
            "adr_number": args.number,
            "adr_slug": args.slug,
            "adr_title": args.title,
            "today": date.today().isoformat(),
        },
    )
    _emit(args.output, source, dry_run=args.dry_run)
    return 0


def _run_runbook(args: argparse.Namespace) -> int:
    source = _render_template(
        "runbook.md.tmpl",
        {
            "runbook_name": args.name,
            "runbook_title": args.title,
            "today": date.today().isoformat(),
        },
    )
    _emit(args.output, source, dry_run=args.dry_run)
    return 0


def main() -> int:
    args = _parse_args()
    if args.command == "connector":
        return _run_connector(args)
    if args.command == "package-readme":
        return _run_package_readme(args)
    if args.command == "governance-pass":
        return _run_governance_pass(args)
    if args.command == "runtime-route":
        return _run_runtime_route(args)
    if args.command == "benchmark":
        return _run_benchmark(args)
    if args.command == "adr":
        return _run_adr(args)
    return _run_runbook(args)


if __name__ == "__main__":
    raise SystemExit(main())
