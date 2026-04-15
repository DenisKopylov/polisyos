"""Run the local SOTA benchmark profile through the zoned research tooling surface."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from tools._lib.imports import repo_root_from
from tools._lib.runner import run_command


def main(argv: Sequence[str] | None = None) -> int:
    args = tuple(argv or ())
    repo_root = repo_root_from(__file__)
    script = Path(__file__).resolve().with_name("run_local_sota_profile.sh")
    env = dict(os.environ)
    completed = run_command(
        ["bash", str(script), *args],
        cwd=repo_root,
        env=env,
        check=False,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
