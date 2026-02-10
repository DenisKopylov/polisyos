from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_legacy_cutover_lint_passes() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "lint" / "lint_legacy_cutover.py"
    assert script.exists(), "lint_legacy_cutover.py is missing"

    result = subprocess.run(
        [sys.executable, str(script), "--repo-root", str(repo_root)],
        capture_output=True,
        text=True,
        check=False,
        cwd=repo_root,
    )
    assert result.returncode == 0, (
        "lint_legacy_cutover failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}\n"
    )
