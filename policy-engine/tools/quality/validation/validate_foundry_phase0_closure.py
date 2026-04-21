#!/usr/bin/env python3
"""Emit a machine-readable closure report for Foundry Phase 0."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_default_repo_root(),
        help="Path to the policy-engine repository root.",
    )
    parser.add_argument(
        "--benchmark-report",
        type=Path,
        required=True,
        help="Path to the synthetic-world Phase-0 smoke benchmark JSON report.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path for the JSON closure report.",
    )
    return parser.parse_args()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args() if argv is None else _parse_args_from(argv)
    repo_root = args.repo_root.resolve()
    sys.path.insert(0, str(repo_root / "src"))

    from polisyos.foundry.validation import build_foundry_phase0_closure_report

    report = build_foundry_phase0_closure_report(
        repo_root=repo_root,
        benchmark_report=args.benchmark_report.resolve(),
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")

    print(rendered, end="")
    return 0 if report["overall_status"] == "complete" else 1


def _parse_args_from(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_default_repo_root(),
        help="Path to the policy-engine repository root.",
    )
    parser.add_argument(
        "--benchmark-report",
        type=Path,
        required=True,
        help="Path to the synthetic-world Phase-0 smoke benchmark JSON report.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path for the JSON closure report.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
