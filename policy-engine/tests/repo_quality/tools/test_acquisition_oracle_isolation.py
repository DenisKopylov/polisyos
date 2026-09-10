"""Exercise the independent grader's real process and denied capabilities."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
ORACLE = ROOT / "tools/quality/validation/gy_acquisition_assurance_oracle.py"
EXPECTED = ROOT / "docs/reference/gy-acquisition-assurance-oracle.tsv"


def invoke(observed: str, *, challenge: str | None = None, isolated: bool = True):
    """Launch the independently owned program without loading subject code."""
    assert ORACLE.is_file(), "independent acquisition oracle is missing"
    command = [sys.executable, *(["-I", "-S"] if isolated else []), str(ORACLE)]
    command += [
        "--expectations", str(EXPECTED), "--expected-sha256",
        hashlib.sha256(EXPECTED.read_bytes()).hexdigest(),
    ]
    if challenge is not None:
        command += ["--challenge", challenge]
    return subprocess.run(command, input=observed, text=True, capture_output=True, timeout=30)


def test_oracle_exists_as_an_independent_executable():
    """An oracle cannot be a success marker supplied by its subject."""
    assert ORACLE.is_file(), "independent acquisition oracle is missing"


def test_isolated_oracle_rejects_changed_semantic_observation():
    expected = EXPECTED.read_text()
    good = invoke(expected)
    assert good.returncode == 0, good.stdout + good.stderr
    assert "ORACLE_PASS\t63" in good.stdout
    changed = expected.replace("reentry_closed", "admission_refused", 1)
    bad = invoke(changed)
    assert bad.returncode == 1, bad.stdout + bad.stderr
    assert "happy.grounding_relation\tstate\treentry_closed\tadmission_refused" in bad.stdout


@pytest.mark.parametrize("dependency", ["decoder", "loader", "comparator"])
def test_shared_subject_dependency_is_denied_before_grading(dependency):
    result = invoke(EXPECTED.read_text(), challenge=dependency)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "oracle_shared_dependency_refused:" + dependency in result.stdout
    assert "ORACLE_PASS" not in result.stdout


def test_removing_process_read_boundary_turns_oracle_red():
    result = invoke(EXPECTED.read_text(), challenge="unconfined")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "oracle_isolation_not_enforced:subject_read" in result.stdout


def test_nonisolated_process_is_not_accepted_as_independent():
    result = invoke(EXPECTED.read_text(), isolated=False)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "oracle_isolated_interpreter_required" in result.stdout


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate"])
def test_observed_case_denominator_is_reconciled_completely(change):
    lines = EXPECTED.read_text().splitlines()
    if change == "missing":
        lines.pop()
    elif change == "extra":
        lines.append(lines[-1].replace("capstone.unseen", "forged.case", 1))
    else:
        lines.append(lines[-1])
    result = invoke("\n".join(lines) + "\n")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "ORACLE_PASS" not in result.stdout
