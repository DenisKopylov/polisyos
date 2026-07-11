"""Focused checks for the GY-N10 depth-N universality harness."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import tools.quality.validation.universality_preflight as universality_preflight_module
from tools.quality.validation.universality_preflight import (
    assert_universality_preflight,
)

REPO_ROOT = Path(__file__).resolve().parents[4]

# This preserves local import ordering only. Fresh child processes below provide the authority proof
# because pytest startup plugins may already have imported ``polisyos.*`` in this parent process.
assert_universality_preflight(REPO_ROOT)


def _create_wrong_checkout_package(tmp_path: Path) -> Path:
    """Create a standalone adversarial ``polisyos`` package and return its source root."""

    wrong_src = (tmp_path / "wrong-checkout" / "policy-engine" / "src").resolve()
    package_root = wrong_src / "polisyos"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text(
        '"""Standalone wrong-checkout sentinel package."""\n',
        encoding="utf-8",
    )
    return wrong_src


def _run_universality_preflight_with_pythonpath(
    pythonpath: Path,
    *,
    producer_sentinel: Path,
    block_ortools: bool = False,
    python_executable: str = sys.executable,
    force_base_prefixes: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run the universality preflight before a sentinel validator producer."""

    script = f"""
import sys
from pathlib import Path

if {force_base_prefixes!r}:
    sys.prefix = sys.base_prefix
    sys.exec_prefix = sys.base_exec_prefix

from tools.quality.validation.universality_preflight import assert_universality_preflight

repo_root = Path({REPO_ROOT.as_posix()!r})
producer_sentinel = Path({producer_sentinel.as_posix()!r})

if {block_ortools!r}:
    class BlockOrtools:
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "ortools" or fullname.startswith("ortools."):
                raise ModuleNotFoundError("blocked_by_n10_preflight_test")
            return None

    sys.meta_path.insert(0, BlockOrtools())

resolved_package_path, backend = assert_universality_preflight(repo_root)

def sentinel_validator_producer() -> None:
    producer_sentinel.write_text("producer_reached", encoding="utf-8")

sys.stdout.write(f"checkout_resolved:{{resolved_package_path}}\\n")
sys.stdout.write(f"cg_backend:{{backend.required_backend_status}}\\n")
sentinel_validator_producer()
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = pythonpath.as_posix()
    return subprocess.run(
        [python_executable, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_repository_interpreter_accepts_current_repository_venv() -> None:
    """Accept the repository venv even when its interpreter binary resolves to the base."""

    expected_prefix = (REPO_ROOT / ".venv").resolve()

    assert (
        universality_preflight_module.assert_repository_interpreter(REPO_ROOT)
        == expected_prefix
    )


def test_fresh_checkout_harness_resolves_current_checkout(tmp_path: Path) -> None:
    """Prove checkout and required CG backend resolution in a fresh process."""

    producer_sentinel = tmp_path / "producer-reached"
    result = _run_universality_preflight_with_pythonpath(
        REPO_ROOT / "src",
        producer_sentinel=producer_sentinel,
    )
    expected_package_path = (REPO_ROOT / "src/polisyos/__init__.py").resolve()

    assert result.returncode == 0
    assert result.stdout == (
        f"checkout_resolved:{expected_package_path}\n"
        "cg_backend:available\n"
    )
    assert producer_sentinel.read_text(encoding="utf-8") == "producer_reached"


def test_cg_substrate_unavailable_is_rejected_before_proof_execution(
    tmp_path: Path,
) -> None:
    """Reject a missing owner-required CG backend before proof production."""

    producer_sentinel = tmp_path / "producer-reached"
    result = _run_universality_preflight_with_pythonpath(
        REPO_ROOT / "src",
        producer_sentinel=producer_sentinel,
        block_ortools=True,
    )

    assert result.returncode == 1
    assert (
        "cg_substrate_unavailable:ortools_cp_sat:ModuleNotFoundError"
        in result.stderr
    )
    assert not producer_sentinel.exists()


def test_bare_base_interpreter_is_rejected_before_proof_execution(
    tmp_path: Path,
) -> None:
    """Reject the real base interpreter selected by ``sys._base_executable``."""

    producer_sentinel = tmp_path / "producer-reached"
    result = _run_universality_preflight_with_pythonpath(
        REPO_ROOT / "src",
        producer_sentinel=producer_sentinel,
        python_executable=sys._base_executable,
    )

    assert result.returncode == 1
    assert "wrong_interpreter_resolved:" in result.stderr
    assert f"expected_prefix={(REPO_ROOT / '.venv').resolve()}" in result.stderr
    assert "observed_prefix=" in result.stderr
    assert "sys_executable=" in result.stderr
    assert "base_prefix=" in result.stderr
    assert not producer_sentinel.exists()


def test_deterministic_wrong_prefix_is_rejected_before_proof_execution(
    tmp_path: Path,
) -> None:
    """Reject base prefixes injected into an otherwise valid repository-venv child."""

    producer_sentinel = tmp_path / "producer-reached"
    result = _run_universality_preflight_with_pythonpath(
        REPO_ROOT / "src",
        producer_sentinel=producer_sentinel,
        force_base_prefixes=True,
    )

    assert result.returncode == 1
    assert "wrong_interpreter_resolved:" in result.stderr
    assert f"observed_prefix={Path(sys.base_prefix).resolve()}" in result.stderr
    assert f"expected_prefix={(REPO_ROOT / '.venv').resolve()}" in result.stderr
    assert not producer_sentinel.exists()


def test_adversarial_checkout_package_is_independent_of_repository_ancestry(
    tmp_path: Path,
) -> None:
    """Create the adversarial package without deriving a checkout from repository parents."""

    simulated_repo_root = tmp_path / "normal-checkout/policy-engine"
    wrong_src = _create_wrong_checkout_package(tmp_path)

    assert wrong_src == (tmp_path / "wrong-checkout/policy-engine/src").resolve()
    assert not wrong_src.is_relative_to(simulated_repo_root)
    assert not wrong_src.is_relative_to(REPO_ROOT)


def test_wrong_checkout_is_rejected_before_proof_execution(tmp_path: Path) -> None:
    """Reject a standalone wrong checkout before its sentinel producer can execute."""

    producer_sentinel = tmp_path / "producer-reached"
    wrong_src = _create_wrong_checkout_package(tmp_path)
    result = _run_universality_preflight_with_pythonpath(
        wrong_src,
        producer_sentinel=producer_sentinel,
    )

    assert result.returncode == 1
    assert f"wrong_checkout_resolved:{wrong_src / 'polisyos/__init__.py'}" in result.stderr
    assert not producer_sentinel.exists()


def test_wrong_checkout_precedes_wrong_interpreter_prefix(tmp_path: Path) -> None:
    """Report checkout failure before inspecting an invalid interpreter prefix."""

    producer_sentinel = tmp_path / "producer-reached"
    wrong_src = _create_wrong_checkout_package(tmp_path)
    result = _run_universality_preflight_with_pythonpath(
        wrong_src,
        producer_sentinel=producer_sentinel,
        force_base_prefixes=True,
    )

    assert result.returncode == 1
    assert f"wrong_checkout_resolved:{wrong_src / 'polisyos/__init__.py'}" in result.stderr
    assert "wrong_interpreter_resolved:" not in result.stderr
    assert not producer_sentinel.exists()
