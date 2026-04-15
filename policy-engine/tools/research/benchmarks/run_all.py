#!/usr/bin/env python3
"""Run the benchmark suite registry through the canonical tools surface."""

from __future__ import annotations

from collections.abc import Sequence
import os
from pathlib import Path
from tools._lib.imports import repo_root_from
import sys

sys.path.insert(0, str(repo_root_from(__file__)))

from tools._lib.runner import run_command


def main(argv: Sequence[str] | None = None) -> int:
    args = tuple(argv or ())
    if any(arg in {"-h", "--help"} for arg in args):
        print(
            "Usage: polisyos-tools benchmarks run-all [--circuit ID] [--mode MODE] "
            "[--tier TIER] [--profile PROFILE] [--json-dir PATH]\n"
            "Delegates to the canonical tools benchmark runner and writes reports to "
            "`tools/benchmarks/_reports/` by default."
        )
        return 0
    repo_root = repo_root_from(__file__)
    script = Path(__file__).resolve().with_name("run_all_benchmarks.sh")
    env = dict(os.environ)
    env.setdefault("BENCH_JSON_DIR", str(Path(__file__).resolve().parent / "_reports"))
    completed = run_command(
        ["bash", str(script), *args],
        cwd=repo_root,
        env=env,
        check=False,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
