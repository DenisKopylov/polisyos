#!/usr/bin/env python3
"""Run the canonical diagnostic cloud pipeline wrapper."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from tools._lib.imports import repo_root_from

sys.path.insert(0, str(repo_root_from(__file__)))

from tools._lib.runner import run_command


def main(argv: Sequence[str] | None = None) -> int:
    args = tuple(argv or ())
    if any(arg in {"-h", "--help"} for arg in args):
        print(
            "Usage: polisyos-tools cloud run-diagnostic\n"
            "Runs the reviewed diagnostic cloud pipeline wrapper inside the remote host context."
        )
        return 0
    script = Path(__file__).resolve().parent / "pipeline" / "run_diagnostic.sh"
    completed = run_command(["bash", str(script), *args], check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
