#!/usr/bin/env python3
"""Prepare canonical shard assets under ``tools/cloud/deploy/assets``."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from tools._lib.imports import repo_root_from

sys.path.insert(0, str(repo_root_from(__file__)))

from tools._lib.runner import run_command


def main(argv: Sequence[str] | None = None) -> int:
    script = Path(__file__).resolve().parent / "shards" / "prepare_shards.sh"
    completed = run_command(["bash", str(script), *(argv or ())], check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
