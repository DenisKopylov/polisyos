"""Focused checks for the GY-N10 depth-N universality harness."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tools.quality.validation.checkout_guard import assert_current_checkout

REPO_ROOT = Path(__file__).resolve().parents[4]
MAIN_CHECKOUT = REPO_ROOT.parents[2]

# Keep this bootstrap guard above every ``polisyos.*`` owner import added to this harness.
RESOLVED_POLISYOS_PACKAGE = assert_current_checkout(REPO_ROOT)


def _run_checkout_guard_with_pythonpath(
    pythonpath: Path,
    *,
    producer_sentinel: Path,
) -> subprocess.CompletedProcess[str]:
    """Run the worktree guard before a sentinel validator producer."""

    script = f"""
from pathlib import Path
from tools.quality.validation.checkout_guard import assert_current_checkout

repo_root = Path({REPO_ROOT.as_posix()!r})
producer_sentinel = Path({producer_sentinel.as_posix()!r})

def sentinel_validator_producer() -> None:
    producer_sentinel.write_text("producer_reached", encoding="utf-8")

assert_current_checkout(repo_root)
sentinel_validator_producer()
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = pythonpath.as_posix()
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_universality_harness_resolves_current_checkout() -> None:
    """Resolve the package only from this worktree's source root."""

    resolved = assert_current_checkout(REPO_ROOT)

    assert resolved == RESOLVED_POLISYOS_PACKAGE
    assert resolved.is_relative_to((REPO_ROOT / "src").resolve())


def test_wrong_checkout_is_rejected_before_proof_execution(tmp_path: Path) -> None:
    """Reject the main checkout before its sentinel producer can execute."""

    producer_sentinel = tmp_path / "producer-reached"
    result = _run_checkout_guard_with_pythonpath(
        MAIN_CHECKOUT / "policy-engine/src",
        producer_sentinel=producer_sentinel,
    )

    assert result.returncode == 1
    assert "wrong_checkout_resolved" in result.stderr
    assert not producer_sentinel.exists()
