#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    target = repo_root / "tools" / "diagnostics" / "gen_schema.py"
    print(
        "[DEPRECATED] tools/diagnostics/generate_ir_schema.py is deprecated. "
        "Use tools/diagnostics/gen_schema.py instead.",
        file=sys.stderr,
    )
    cmd = [sys.executable, str(target), *sys.argv[1:]]
    completed = subprocess.run(cmd, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
