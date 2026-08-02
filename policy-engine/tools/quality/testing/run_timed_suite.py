#!/usr/bin/env python3
"""Run an external verification suite while persisting one timing record."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from tools.lib.timing import run_timed_operation

REPO_ROOT = Path(__file__).resolve().parents[3]


def _validated_repo_path(raw_path: str) -> Path:
    """Resolve a repository-relative working directory and reject path escapes."""

    candidate = (REPO_ROOT / raw_path).resolve()
    try:
        candidate.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--cwd must stay within the repository") from exc
    if not candidate.is_dir():
        raise argparse.ArgumentTypeError(f"--cwd is not a directory: {raw_path}")
    return candidate


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", required=True, help="Stable timing key for this command lane.")
    parser.add_argument("--cwd", default=".", help="Repository-relative working directory.")
    parser.add_argument("argv", nargs=argparse.REMAINDER, help="Command to run after '--'.")
    args = parser.parse_args()
    if args.argv[:1] == ["--"]:
        args.argv = args.argv[1:]
    if not args.argv:
        parser.error("provide a command after '--'")
    args.cwd = _validated_repo_path(args.cwd)
    return args


def main() -> int:
    """Run the requested command without a shell and preserve its exit code."""

    args = _parse_args()

    def _operation() -> int:
        result = subprocess.run(args.argv, shell=False, cwd=args.cwd, check=False)
        return result.returncode

    return run_timed_operation(
        _operation,
        tool=args.lane,
        category="external",
    )


if __name__ == "__main__":
    raise SystemExit(main())
