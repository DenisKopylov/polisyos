from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_arch_import_gate() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "quality" / "lint" / "lint_imports.py"
    policy = repo_root / "architecture" / "imports" / "policy.toml"
    exceptions = repo_root / "architecture" / "imports" / "exceptions.toml"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--policy",
            str(policy),
            "--exceptions",
            str(exceptions),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=repo_root,
    )

    assert result.returncode == 0, (
        f"Import gate failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}\n"
    )
