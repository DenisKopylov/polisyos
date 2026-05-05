#!/usr/bin/env python3
"""Fail-closed Phase 1C cross-package directory-name collision gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from repository_structure_phase0 import _default_repo_root, collect_gate_findings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_default_repo_root(),
        help="Path to the policy-engine product root.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON findings.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    findings = collect_gate_findings(args.repo_root.resolve(), "name_collision")
    if args.json:
        print(json.dumps({"mode": "fail-closed", "findings": findings}, indent=2, sort_keys=True))
    else:
        print(f"name_collision_gate: {len(findings)} finding(s) [fail-closed]")
        for finding in findings:
            print(f"- {finding['message']}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
