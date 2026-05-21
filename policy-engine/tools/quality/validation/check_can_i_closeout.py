#!/usr/bin/env python3
"""Validate Can-I-Closeout compatibility for a selected evidence bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.closeout_compatibility import (  # noqa: E402
    build_closeout_compatibility_record_from_bundle_dir,
)


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--require-passing", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    bundle_dir = args.bundle_dir if args.bundle_dir.is_absolute() else repo_root / args.bundle_dir
    if not bundle_dir.exists():
        payload = {
            "schema_version": "policyos.runtime.can_i_closeout_compatibility.v1",
            "status": "fail",
            "issues": [
                {
                    "code": "closeout_bundle_dir_missing",
                    "severity": "fail",
                    "message": "Evidence bundle directory does not exist.",
                    "bundle_dir": str(bundle_dir),
                    "next_action": "Run the canary lane and pass the emitted bundle directory.",
                }
            ],
        }
        exit_code = 3
    else:
        payload = build_closeout_compatibility_record_from_bundle_dir(bundle_dir)
        exit_code = 0 if payload.get("status") == "pass" else 2
    output = args.json_output if args.json_output.is_absolute() else repo_root / args.json_output
    atomic_write_text(
        output,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default)
        + "\n",
    )
    if payload.get("status") != "pass":
        print(
            f"Can-I-Closeout compatibility failed: {output}",
            file=sys.stderr,
        )
    elif args.require_passing:
        print(f"Can-I-Closeout compatibility passed: {output}")
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
