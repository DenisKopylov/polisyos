#!/usr/bin/env python3
"""Emit a machine-readable closure report for the causal research phases."""
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
        "--output",
        type=Path,
        default=None,
        help="Optional output path for the JSON closure report.",
    )
    parser.add_argument(
        "--previous-snapshot",
        type=Path,
        default=None,
        help="Optional previous JSON report used to compute regression deltas.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = args.repo_root.resolve()
    sys.path.insert(0, str(repo_root / "src"))

    from polisyos.ir.analytics.frontier import build_phase_closure_validation_report

    report = build_phase_closure_validation_report(
        repo_root=repo_root,
        previous_snapshot=args.previous_snapshot,
    )
    payload = report.model_dump(mode="json")
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")

    print(rendered, end="")
    return 0 if report.overall_status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
