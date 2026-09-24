"""Schema measurement is scheduled independently and required by the aggregate."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[4] / ".github/workflows/abi.yml"


def test_snapshot_job_has_no_prior_gate_that_can_prevent_its_measurement() -> None:
    jobs = yaml.safe_load(WORKFLOW.read_text())["jobs"]
    job = jobs["schema-snapshots"]
    assert not job.get("needs")
    assert not job.get("if")
    steps = job["steps"]
    assert len(steps) == 3
    assert steps[0]["uses"].startswith("actions/checkout@")
    assert steps[1]["uses"] == "./.github/actions/setup-policy-engine-python"
    assert steps[1]["with"]["profile"] == "minimal"
    assert steps[2]["run"] == (
        "uv run --extra ml python tools/quality/diagnostics/gen_schema.py --check"
    )
    assert not steps[2].get("if")


@pytest.mark.parametrize("result", ["success", "failure", "cancelled", "skipped", ""])
def test_actual_aggregate_shell_requires_a_completed_successful_snapshot_verdict(
    result: str,
) -> None:
    jobs = yaml.safe_load(WORKFLOW.read_text())["jobs"]
    gate = jobs["fast-pr-gate"]
    assert "schema-snapshots" in gate["needs"]
    step = gate["steps"][0]
    assert step["env"]["SCHEMA_RESULT"] == "${{ needs.schema-snapshots.result }}"
    executed = subprocess.run(
        ["bash", "-e", "-c", step["run"]],
        env={**os.environ, "RESULTS": "success,skipped", "SCHEMA_RESULT": result},
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert (executed.returncode == 0) == (result == "success"), executed.stdout + executed.stderr
