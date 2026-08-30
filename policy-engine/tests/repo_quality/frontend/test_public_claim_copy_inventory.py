"""Behavioral closure checks for the bounded DS11 public-copy surface."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TRUST_COPY_BEHAVIOR_TESTS = (
    "src/features/trust/routes/TrustPosturePage.test.tsx",
    "src/features/trust/components/ClaimPostureRegister.free-growth.test.tsx",
    "src/features/trust/export/trustPostureTwin.test.ts",
    "src/features/trust/routes/TrustPosturePage.route-contract.test.tsx",
)


def test_every_public_capability_assertion_resolves_to_claim_posture() -> None:
    """Exercise the renderer, exact DOM twin, free growth, and sole neutral entry."""
    completed = subprocess.run(  # noqa: S603 - fixed repository-local test command.
        [
            "corepack",
            "pnpm",
            "--filter",
            "@polisyos/runtime-dashboard",
            "exec",
            "vitest",
            "run",
            *TRUST_COPY_BEHAVIOR_TESTS,
            "--maxWorkers=1",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, (
        "The bounded public-copy behavior contract failed.\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
