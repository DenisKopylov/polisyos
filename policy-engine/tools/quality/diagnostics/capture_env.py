#!/usr/bin/env python3
"""
CLI tool to capture and compare environment manifests.

Usage:
  python -m tools.capture_env capture --output env.json
  python -m tools.capture_env compare baseline.json current.json
  python -m tools.capture_env validate env.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import NoReturn

from polisyos.core.artifacts.environment import (
    EnvironmentManifest,
    RiskLevel,
    capture_environment,
    compare_environments,
)


class Colors:
    RED = "\033[91m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def color_for_risk(risk: RiskLevel) -> str:
    return {
        RiskLevel.CRITICAL: Colors.RED,
        RiskLevel.HIGH: Colors.RED,
        RiskLevel.MEDIUM: Colors.YELLOW,
        RiskLevel.LOW: Colors.CYAN,
        RiskLevel.INFO: Colors.BLUE,
    }[risk]


def format_diff_line(diff) -> str:
    color = color_for_risk(diff.risk_level)
    risk_str = f"[{diff.risk_level.value.upper()}]"
    value_a = str(diff.value_a)
    value_b = str(diff.value_b)
    return (
        f"{color}{Colors.BOLD}{risk_str:12}{Colors.RESET} "
        f"{diff.field_name}: "
        f"{Colors.RED}{value_a}{Colors.RESET} -> "
        f"{Colors.GREEN}{value_b}{Colors.RESET}\n"
        f"             {Colors.CYAN}{diff.explanation}{Colors.RESET}"
    )


def cmd_capture(args: argparse.Namespace) -> int:
    manifest = capture_environment(
        project_root=Path(args.project_root) if args.project_root else None,
        include_git=not args.no_git,
        include_dependencies=not args.no_deps,
        include_system_libraries=not args.no_system_libs,
    )

    output = manifest.model_dump_json(indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Environment manifest written to: {args.output}", file=sys.stderr)
    else:
        print(output)

    if not args.quiet:
        print("\n--- Environment Summary ---", file=sys.stderr)
        print(f"Fingerprint: {manifest.fingerprint}", file=sys.stderr)
        print(
            f"CPU: {manifest.cpu.architecture} ({manifest.cpu.model_name})",
            file=sys.stderr,
        )
        print(f"GPU: {manifest.gpu.model_name or 'None'}", file=sys.stderr)
        print(f"JAX: {manifest.jax.jax_version or 'Not installed'}", file=sys.stderr)
        print(f"Python: {manifest.python.version}", file=sys.stderr)
        if manifest.git:
            dirty_marker = " (dirty)" if manifest.git.dirty else ""
            print(f"Git: {manifest.git.commit_short}{dirty_marker}", file=sys.stderr)

    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    try:
        manifest_a = EnvironmentManifest.model_validate_json(
            Path(args.file_a).read_text(encoding="utf-8")
        )
        manifest_b = EnvironmentManifest.model_validate_json(
            Path(args.file_b).read_text(encoding="utf-8")
        )
    except Exception as exc:
        print(f"Error loading manifests: {exc}", file=sys.stderr)
        return 1

    diffs = compare_environments(manifest_a, manifest_b)
    score = manifest_a.compatibility_score(manifest_b)

    if args.json:
        result = {
            "compatibility_score": score,
            "fingerprint_a": manifest_a.fingerprint,
            "fingerprint_b": manifest_b.fingerprint,
            "differences": [diff.model_dump() for diff in diffs],
        }
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"\n{Colors.BOLD}=== Environment Comparison ==={Colors.RESET}\n")
        print(f"File A: {args.file_a}")
        print(f"File B: {args.file_b}")
        print(f"\nFingerprint A: {manifest_a.fingerprint}")
        print(f"Fingerprint B: {manifest_b.fingerprint}")

        if manifest_a.fingerprint == manifest_b.fingerprint:
            print(f"\n{Colors.GREEN}OK: environments are identical{Colors.RESET}")
            return 0

        print(f"\n{Colors.BOLD}Compatibility Score: {score:.1%}{Colors.RESET}")

        if not diffs:
            print(f"\n{Colors.GREEN}OK: no significant differences found{Colors.RESET}")
            return 0

        print(f"\n{Colors.BOLD}Differences ({len(diffs)} found):{Colors.RESET}\n")

        for diff in diffs:
            print(format_diff_line(diff))
            print()

        risk_counts: dict[RiskLevel, int] = {}
        for diff in diffs:
            risk_counts[diff.risk_level] = risk_counts.get(diff.risk_level, 0) + 1

        print(f"\n{Colors.BOLD}Summary:{Colors.RESET}")
        for risk in [RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW]:
            count = risk_counts.get(risk, 0)
            if count > 0:
                color = color_for_risk(risk)
                print(f"  {color}{risk.value.upper()}: {count}{Colors.RESET}")

    has_critical = any(diff.risk_level == RiskLevel.CRITICAL for diff in diffs)
    return 2 if has_critical else 0


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        manifest = EnvironmentManifest.model_validate_json(
            Path(args.file).read_text(encoding="utf-8")
        )
        print(f"{Colors.GREEN}OK: valid EnvironmentManifest{Colors.RESET}")
        print(f"  Fingerprint: {manifest.fingerprint}")
        print(f"  Captured at: {manifest.captured_at}")
        return 0
    except Exception as exc:
        print(f"{Colors.RED}ERROR: invalid manifest: {exc}{Colors.RESET}", file=sys.stderr)
        return 1


def main() -> NoReturn:
    parser = argparse.ArgumentParser(
        description="Capture and compare environment manifests for reproducibility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tools.capture_env capture --output baseline.json
  python -m tools.capture_env compare baseline.json current.json
  python -m tools.capture_env validate baseline.json
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    capture_parser = subparsers.add_parser("capture", help="Capture current environment")
    capture_parser.add_argument("--output", "-o", type=str, help="Output file path")
    capture_parser.add_argument(
        "--project-root", type=str, help="Project root for git/lockfile detection"
    )
    capture_parser.add_argument("--no-git", action="store_true", help="Skip git capture")
    capture_parser.add_argument(
        "--no-deps", action="store_true", help="Skip dependency lockfile capture"
    )
    capture_parser.add_argument(
        "--no-system-libs",
        action="store_true",
        help="Skip system library hash capture",
    )
    capture_parser.add_argument("--quiet", "-q", action="store_true", help="Suppress summary")
    capture_parser.set_defaults(func=cmd_capture)

    compare_parser = subparsers.add_parser("compare", help="Compare two environment manifests")
    compare_parser.add_argument("file_a", type=str, help="First manifest file (baseline)")
    compare_parser.add_argument("file_b", type=str, help="Second manifest file (current)")
    compare_parser.add_argument(
        "--json", action="store_true", help="Output as JSON instead of formatted text"
    )
    compare_parser.set_defaults(func=cmd_compare)

    validate_parser = subparsers.add_parser("validate", help="Validate a manifest file")
    validate_parser.add_argument("file", type=str, help="Manifest file to validate")
    validate_parser.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    if args.command is None:
        args.command = "capture"
        args.output = None
        args.project_root = None
        args.no_git = False
        args.no_deps = False
        args.no_system_libs = False
        args.quiet = False
        args.func = cmd_capture

    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
