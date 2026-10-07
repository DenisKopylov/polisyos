"""Exercise phase-journal preservation with real native pytest processes.

This verifies an observation tool, not runtime code or finding closure. Each
fixture and artifact remains preserved under a fresh Git-ignored output root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _require(condition: bool, diagnostic: str) -> None:
    if not condition:
        raise RuntimeError(diagnostic)


def main() -> None:
    """Compare abrupt-death reports with and without the optional journal."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[6]
    output = args.output
    if not output.is_absolute() or output.exists():
        raise ValueError("A fresh absolute output directory is required")
    output.mkdir(parents=True)
    instrument = Path(__file__).with_name("current-cohort-inventory.py")
    loaded = output / "current_cohort_inventory.py"
    loaded.write_bytes(instrument.read_bytes())
    fixture = output / "test_real_phase_journal.py"
    fixture.write_text(
        "import os, signal, pytest\n"
        "def test_first():\n    assert 7 * 6 == 42\n"
        "def test_explicit_death():\n    os.kill(os.getpid(), signal.SIGKILL)\n"
    )
    records = []
    for label, journal_enabled in (("journal", True), ("without-journal", False)):
        run = output / label
        run.mkdir()
        inventory = run / "inventory.json"
        journal = run / "reports.jsonl"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(output)
        env["E02_B_COHORT_INVENTORY_PATH"] = str(inventory)
        env.pop("E02_B_COHORT_REPORT_JOURNAL_PATH", None)
        if journal_enabled:
            env["E02_B_COHORT_REPORT_JOURNAL_PATH"] = str(journal)
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "current_cohort_inventory",
            "-vv",
            "-o",
            "addopts=",
            "-o",
            "cache_dir=" + str(run / "cache"),
            "--rootdir",
            str(repo),
            "--basetemp",
            str(run / "pytest"),
            str(fixture),
        ]
        result = subprocess.run(  # noqa: S603 - argv-only isolated real native test
            command, cwd=repo, env=env, capture_output=True, check=False
        )
        (run / "stdout.txt").write_bytes(result.stdout)
        (run / "stderr.txt").write_bytes(result.stderr)
        payload = json.loads(inventory.read_bytes())
        observed = (
            [json.loads(line) for line in journal.read_bytes().splitlines()]
            if journal_enabled
            else []
        )
        _require(result.returncode == -9, "Explicit test death must report SIGKILL")
        _require(
            payload["state"] == "collection_finished_runtime_pending",
            "Session must remain incomplete",
        )
        _require(payload["counts"]["session_items"] == 2, "Both actual cases must be collected")
        _require(payload["runtime_phase_reports"] == [], "Final snapshot must not be fabricated")
        _require(
            len(observed) == (4 if journal_enabled else 0), "Unexpected surviving journal prefix"
        )
        if journal_enabled:
            expected = [
                ("setup", "passed"),
                ("call", "passed"),
                ("teardown", "passed"),
                ("setup", "passed"),
            ]
            _require(
                [(r["when"], r["outcome"]) for r in observed] == expected, "Actual phases differ"
            )
            _require(
                observed[1]["nodeid"].endswith("::test_first"), "Completed case identity differs"
            )
            _require(
                observed[-1]["nodeid"].endswith("::test_explicit_death"),
                "Incomplete case identity differs",
            )
        records.append(
            {
                "label": label,
                "command": command,
                "cwd": str(repo),
                "exit": result.returncode,
                "stdout_bytes": len(result.stdout),
                "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
                "stderr_bytes": len(result.stderr),
                "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
                "collected_cases": 2,
                "preserved_runtime_phases": len(observed),
                "completed_cases": 1 if journal_enabled else "not_established",
                "incomplete_case": "test_explicit_death",
                "terminal_status_partition": "not_established",
                "signal_sender": "explicit test os.kill(self, SIGKILL)",
                "artifact_directory": str(run),
            }
        )
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Read-only Git identity unavailable")
    summary = {
        "source_sha": subprocess.check_output(  # noqa: S603 - fixed read-only Git argv
            [git, "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip(),
        "source_tree": subprocess.check_output(  # noqa: S603 - fixed read-only Git argv
            [git, "rev-parse", "HEAD^{tree}"], cwd=repo, text=True
        ).strip(),
        "instrument_sha256": hashlib.sha256(instrument.read_bytes()).hexdigest(),
        "oracle": (
            "actual four phase reports before explicit process death; "
            "missing journal control retains none"
        ),
        "finding_closure": False,
        "claim_boundary": (
            "Process-death flushed report prefix, not power-loss durability "
            "or whole-session completion"
        ),
        "runs": records,
    }
    (output / "oracle.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))  # noqa: T201 - deciding probe stdout


if __name__ == "__main__":
    main()
