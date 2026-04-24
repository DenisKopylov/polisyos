#!/usr/bin/env python3
"""Deploy one prepared shard bundle to a reviewed remote server workflow."""

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
            "Usage: polisyos-tools cloud deploy-to-server <1|2|3> <server_ip>\n"
            "Reads shard/env assets from `tools/cloud/deploy/assets/` by default or "
            "`POLISYOS_CLOUD_ASSETS_DIR` when set."
        )
        return 0
    script = Path(__file__).resolve().parent / "deploy" / "deploy_to_server.sh"
    completed = run_command(["bash", str(script), *args], check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
