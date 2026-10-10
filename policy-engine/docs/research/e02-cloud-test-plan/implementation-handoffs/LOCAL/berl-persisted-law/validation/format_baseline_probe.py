"""Compare formatter findings in the current tree with the checked-out base."""

from __future__ import annotations

import shutil
import subprocess
import sys

PATHS = (
    "policy-engine/src/polisyos/berl/contracts/validation_rules.py",
    "policy-engine/src/polisyos/scientist/validation/phase5_preflight.py",
    "policy-engine/src/polisyos/runtime/quality/explanation_reliability.py",
    "policy-engine/tests/unit/berl/test_contracts.py",
    "policy-engine/tests/integration/scientist_berl/test_explanation_reliability_bridge.py",
    "policy-engine/tests/unit/scientist/validation/test_phase5_preflight.py",
    "policy-engine/tests/unit/runtime/quality/test_berl_warrant_reliability.py",
)


def main() -> None:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git executable is unavailable")
    for path in PATHS:
        source = subprocess.run(  # noqa: S603 -- fixed read-only Git blob query.
            [git, "show", f"HEAD:{path}"],
            check=True,
            capture_output=True,
        ).stdout
        formatted = subprocess.run(  # noqa: S603 -- fixed local Ruff formatter invocation.
            [
                sys.executable,
                "-m",
                "ruff",
                "format",
                "--diff",
                "--stdin-filename",
                path,
                "-",
            ],
            input=source,
            capture_output=True,
        )
        diff = formatted.stdout.decode("utf-8")
        _emit(
            f"{path}: baseline format diff exit={formatted.returncode}; "
            f"diff bytes={len(formatted.stdout)}"
        )
        if diff:
            _emit(diff)
        error = formatted.stderr.decode("utf-8")
        if error:
            _emit(error)


def _emit(value: object) -> None:
    sys.stdout.write(f"{value}\n")


if __name__ == "__main__":
    main()
