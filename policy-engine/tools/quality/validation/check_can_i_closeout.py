#!/usr/bin/env python3
"""Validate Can-I-Closeout compatibility for a selected evidence bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.closeout_compatibility import (  # noqa: E402
    build_closeout_compatibility_record_from_bundle_dir,
)
from polisyos.runtime.quality.closeout_reader import (  # noqa: E402
    build_can_i_closeout_verdict,
    build_can_i_closeout_verdict_from_bundle_dir,
    build_closeout_reader_skeleton,
    build_closeout_reader_skeleton_from_bundle_dir,
)


def _json_default(value: object) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--require-passing", action="store_true")
    parser.add_argument(
        "--reader-skeleton",
        action="store_true",
        help=(
            "Emit the W1.D fail-closed closeout reader skeleton instead of the "
            "compatibility-only record."
        ),
    )
    parser.add_argument(
        "--reader-integration",
        action="store_true",
        help=(
            "Emit the W4.D closeout integration verdict over module-owned "
            "quality_evidence records."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.reader_skeleton and args.reader_integration:
        raise SystemExit("--reader-skeleton and --reader-integration are mutually exclusive")
    repo_root = args.repo_root.resolve()
    bundle_dir = (
        args.bundle_dir if args.bundle_dir.is_absolute() else repo_root / args.bundle_dir
    )
    if not bundle_dir.exists():
        compatibility_payload = {
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
        payload = compatibility_payload
        if args.reader_skeleton:
            payload = build_closeout_reader_skeleton(
                compatibility_record=compatibility_payload,
            )
            payload["compatibility_record"] = compatibility_payload
            payload["bundle_dir"] = str(bundle_dir)
        elif args.reader_integration:
            payload = build_can_i_closeout_verdict(
                compatibility_record=compatibility_payload,
            )
            payload["compatibility_record"] = compatibility_payload
            payload["bundle_dir"] = str(bundle_dir)
        exit_code = 3
    else:
        payload = build_closeout_compatibility_record_from_bundle_dir(bundle_dir)
        if args.reader_skeleton:
            payload = build_closeout_reader_skeleton_from_bundle_dir(bundle_dir)
        elif args.reader_integration:
            payload = build_can_i_closeout_verdict_from_bundle_dir(bundle_dir)
        passed = (
            bool(payload.get("can_closeout"))
            if args.reader_skeleton or args.reader_integration
            else payload.get("status") == "pass"
        )
        exit_code = 0 if passed else 2
    output = (
        args.json_output if args.json_output.is_absolute() else repo_root / args.json_output
    )
    atomic_write_text(
        output,
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=_json_default,
        )
        + "\n",
    )
    label = (
        "Can-I-Closeout reader integration"
        if args.reader_integration
        else "Can-I-Closeout reader skeleton"
        if args.reader_skeleton
        else "Can-I-Closeout compatibility"
    )
    if exit_code != 0:
        sys.stderr.write(f"{label} failed: {output}\n")
    elif args.require_passing:
        sys.stdout.write(f"{label} passed: {output}\n")
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
