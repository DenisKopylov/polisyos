#!/usr/bin/env python3
"""Inspect remote shard progress through the canonical shard helper surface."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from tools.lib.imports import repo_root_from

sys.path.insert(0, str(repo_root_from(__file__)))

from tools.lib.runner import run_command


def main(argv: Sequence[str] | None = None) -> int:
    args = tuple(argv or ())
    if any(arg in {"-h", "--help"} for arg in args):
        print("Usage: polisyos-tools cloud check-progress <ip1> [ip2 ...]")
        return 0
    script = Path(__file__).resolve().parent / "shards" / "check_progress.sh"
    completed = run_command(["bash", str(script), *args], check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
