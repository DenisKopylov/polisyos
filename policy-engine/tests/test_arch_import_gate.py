from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_arch_import_gate() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "tools" / "lint" / "lint_imports.py"
    if not script.exists():
        script = repo_root / "tools" / "lint_imports.py"
    policy = repo_root / "import_policy.toml"
    exceptions = repo_root / "import_exceptions.toml"

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
        "Import gate failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}\n"
    )
