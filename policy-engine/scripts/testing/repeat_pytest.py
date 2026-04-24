#!/usr/bin/env python3
"""Repeat one pytest invocation multiple times and fail on the first red run."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the same pytest command multiple times for race/leak smoke checks."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="How many times to repeat the pytest invocation.",
    )
    parser.add_argument(
        "--working-directory",
        default=".",
        help="Directory in which pytest should run.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop immediately after the first failing repetition.",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to pytest. Prefix with '--' if needed.",
    )
    args = parser.parse_args()
    if args.count <= 0:
        raise SystemExit("--count must be > 0")
    if not args.pytest_args:
        raise SystemExit("Provide at least one pytest argument to repeat")
    if args.pytest_args[0] == "--":
        args.pytest_args = args.pytest_args[1:]
    return args


def main() -> int:
    args = _parse_args()
    cwd = Path(args.working_directory).resolve()
    failures: list[int] = []
    started_at = time.perf_counter()

    for repetition in range(1, args.count + 1):
        print(
            f"[repeat_pytest] run {repetition}/{args.count}: pytest {' '.join(args.pytest_args)}",
            flush=True,
        )
        result = subprocess.run(
            [sys.executable, "-m", "pytest", *args.pytest_args],
            cwd=str(cwd),
            check=False,
        )
        if result.returncode == 0:
            continue
        failures.append(repetition)
        if args.fail_fast:
            break

    elapsed = time.perf_counter() - started_at
    if failures:
        print(
            f"[repeat_pytest] failed on repetitions {failures} after {elapsed:.2f}s",
            flush=True,
        )
        return 1

    print(
        f"[repeat_pytest] all {args.count} repetitions passed in {elapsed:.2f}s",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
