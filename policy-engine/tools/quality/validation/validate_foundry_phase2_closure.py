#!/usr/bin/env python3
"""Emit a machine-readable closure report for Foundry Phase 2."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_default_repo_root(),
        help="Path to the policy-engine repository root.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Optional override for the Phase 2 manifest path.",
    )
    parser.add_argument(
        "--acceptance-junit-xml",
        type=Path,
        required=True,
        help="JUnit XML containing the enrolled Phase 2 acceptance tests.",
    )
    parser.add_argument(
        "--benchmark-report",
        type=Path,
        required=True,
        help="JSON benchmark summary for the enrolled Phase 2 benchmark entrypoints.",
    )
    parser.add_argument(
        "--evidence-report",
        type=Path,
        required=True,
        help="JSON evidence report with synthetic-world and judge-verdict statuses.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path for the JSON closure report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    sys.path.insert(0, str(repo_root / "src"))

    from polisyos.foundry.validation import (
        build_foundry_phase2_closure_report,
        default_foundry_phase2_manifest_path,
    )

    report = build_foundry_phase2_closure_report(
        repo_root=repo_root,
        manifest_path=(
            args.manifest.resolve()
            if args.manifest is not None
            else default_foundry_phase2_manifest_path(repo_root=repo_root)
        ),
        acceptance_junit_xml=args.acceptance_junit_xml.resolve(),
        benchmark_report=args.benchmark_report.resolve(),
        evidence_report=args.evidence_report.resolve(),
    )
    rendered = json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")

    print(rendered, end="")
    return 0 if report.overall_status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
