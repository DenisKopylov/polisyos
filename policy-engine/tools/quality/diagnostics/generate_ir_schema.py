#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys

from tools.lib.imports import repo_root_from


def main() -> int:
    repo_root = repo_root_from(__file__)
    target = repo_root / "tools" / "quality" / "diagnostics" / "gen_schema.py"
    print(
        "[DEPRECATED] tools/quality/diagnostics/generate_ir_schema.py is deprecated. "
        "Use tools/quality/diagnostics/gen_schema.py instead.",
        file=sys.stderr,
    )
    cmd = [sys.executable, str(target), *sys.argv[1:]]
    completed = subprocess.run(cmd, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
