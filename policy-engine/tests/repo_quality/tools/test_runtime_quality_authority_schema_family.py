"""Measure the real authority-schema exporter through the generic freshness comparator.

The local comparator tests do not qualify private-environment isolation or authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tools.devx.architecture import guardrails

PRODUCT_ROOT = Path(__file__).resolve().parents[3]
ACTIVE_FAMILY = "runtime-quality-authority-envelope-v2-schema"
HISTORY_FAMILY = "runtime-quality-authority-envelope-v1-history"
ACTIVE_OUTPUT = "schemas/runtime_quality/evidence_authority_envelope_v2.schema.json"
HISTORY_OUTPUT = "schemas/runtime_quality/evidence_authority_envelope_v1.schema.json"
HISTORICAL_SHA256 = "543e7a567b39cbb9cca017dfafa7dfc47053723b98470294e54d2dbe30027d0a"


def _families() -> dict[str, guardrails.GeneratedArtifactFamily]:
    return {
        family.family_id: family
        for family in guardrails._parse_generated_artifacts(
            PRODUCT_ROOT / "architecture/generated_artifacts.toml"
        )
    }


def test_historical_schema_bytes_remain_frozen() -> None:
    family = _families()[HISTORY_FAMILY]
    assert family.lifecycle == "source_committed"
    assert not family.default_freshness_check
    assert family.output_probe_command is None
    assert family.outputs == (PRODUCT_ROOT / HISTORY_OUTPUT,)
    assert hashlib.sha256((PRODUCT_ROOT / HISTORY_OUTPUT).read_bytes()).hexdigest() == (
        HISTORICAL_SHA256
    )


@pytest.mark.parametrize("mutation", ["matching", "type_drift", "required_field_removed"])
def test_actual_v2_exporter_is_compared_by_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    """Keep every property marker while the real gate distinguishes semantic drift."""
    family = _families()[ACTIVE_FAMILY]
    assert family.default_freshness_check
    assert family.outputs == (PRODUCT_ROOT / ACTIVE_OUTPUT,)
    assert family.output_probe_command is not None
    # The registered owner command is executed, only selecting the test interpreter.
    command = tuple(
        sys.executable if part == "python" else part for part in family.output_probe_command
    )
    expected_root = tmp_path / "expected"
    expected_root.mkdir()
    environment = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": os.pathsep.join((str(PRODUCT_ROOT / "src"), str(PRODUCT_ROOT))),
    }
    generated = subprocess.run(
        [part.replace("{output_root}", str(expected_root)) for part in command],
        cwd=PRODUCT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stdout + generated.stderr
    expected_path = expected_root / ACTIVE_OUTPUT
    schema = json.loads(expected_path.read_text(encoding="utf-8"))
    original_properties = set(schema["properties"])
    if mutation == "type_drift":
        schema["properties"]["requested_execution_profile"]["anyOf"] = [
            {"type": "integer"},
            {"type": "null"},
        ]
    elif mutation == "required_field_removed":
        schema["required"].remove("evidence_id")
    assert set(schema["properties"]) == original_properties
    expected_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Confine bookkeeping snapshots to a tiny stand-in. The exporter and comparator
    # are real; this unit witness makes no claim about copied-source import isolation.
    isolated_root = tmp_path / "isolated"
    isolated_root.mkdir()
    monkeypatch.setattr(guardrails, "REPO_ROOT", isolated_root)
    monkeypatch.setattr(
        guardrails, "_snapshot_git_visible_worktree", guardrails._snapshot_filesystem_tree
    )
    measured_family = replace(
        family,
        outputs=(isolated_root / ACTIVE_OUTPUT,),
        output_probe_command=command,
    )
    scratch_root = tmp_path / "probe"
    scratch_root.mkdir()
    cursor = guardrails._GeneratedArtifactMeasurementCursor((measured_family,), [], [])
    guardrails._measure_required_generated_artifact_family(
        measured_family,
        family_index=0,
        cursor=cursor,
        family_scratch_root=scratch_root,
        isolated_repo_root=isolated_root,
        environment=environment,
        expected_root=expected_root,
        expected_outputs={ACTIVE_OUTPUT: expected_path.read_bytes()},
        declared_owners={ACTIVE_OUTPUT: [ACTIVE_FAMILY]},
    )
    assert not cursor.unrun_checks, cursor.unrun_checks
    if mutation == "matching":
        assert cursor.violations == []
    else:
        assert any(
            finding.subject == ACTIVE_FAMILY
            and finding.detail == ACTIVE_OUTPUT
            and "does not match" in finding.message
            for finding in cursor.violations
        ), cursor.violations
