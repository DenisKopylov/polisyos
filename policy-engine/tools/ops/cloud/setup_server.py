#!/usr/bin/env python3
"""Run the canonical cloud host setup helper."""

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
        print(
            "Usage: polisyos-tools cloud setup-server\n"
            "Runs the reviewed first-boot server setup helper on the target cloud host."
        )
        return 0
    script = Path(__file__).resolve().parent / "deploy" / "setup_server.sh"
    completed = run_command(["bash", str(script), *args], check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
