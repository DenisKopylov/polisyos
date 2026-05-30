from __future__ import annotations

# ruff: noqa: S101
import json
import os
import shutil
from pathlib import Path

import pytest

from tools.quality.validation import build_policy_design_case_wave35h_provenance as build
from tools.quality.validation import check_policy_design_case_wave35h_provenance as check

REPO_ROOT = Path(__file__).resolve().parents[3]
WAVE35_STAGE_PREREQUISITES = (
    REPO_ROOT / "_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json",
    REPO_ROOT / "_build/policy-design-case/rebaseline/wave-35G/institutional_provenance_boundary_ledger.json",
)
pytestmark = pytest.mark.skipif(
    os.environ.get("POLISYOS_RUN_STAGED_REBASELINE_TESTS") != "1"
    or not all(path.exists() for path in WAVE35_STAGE_PREREQUISITES),
    reason=(
        "staged Wave 35H rebaseline check; set POLISYOS_RUN_STAGED_REBASELINE_TESTS=1 "
        "after running the policy-design-case rebaseline pipeline"
    ),
)
RUNTIME_FINDINGS = {
    "PDD-097-F001",
    "PDD-097-F002",
    "PDD-097-F003",
    "PDD-099-F001",
    "PDD-099-F002",
    "PDD-099-F003",
}
INSTITUTIONAL_LEDGER_FILES = {
    "implementation_feasibility_ledger.json",
    "contestability_appeals_ledger.json",
}


def test_wave35h_builder_runtime_owns_all_institutional_boundary_findings(
    tmp_path: Path,
) -> None:
    fake_repo = _copy_rebaseline_inputs(tmp_path)

    outputs = build.build_wave35h_provenance_outputs(
        repo_root=fake_repo,
        refresh_wave35g_backfill=False,
    )

    ownership = outputs["runtime_ownership_ledger"]
    assert ownership["status"] == "pass"
    assert ownership["summary"]["runtime_owned_provenance_count"] == 6
    assert ownership["summary"]["not_closeout_authority_count"] == 0
    assert {row["finding_id"] for row in ownership["rows"]} == RUNTIME_FINDINGS
    assert all(row["evidence_authority"] == "runtime_emitted" for row in ownership["rows"])
    assert all(row["command"]["exit_code"] == 0 for row in ownership["rows"])
    assert all(row["trace_refs"] for row in ownership["rows"])

    wave35e = fake_repo / "_build/policy-design-case/rebaseline/wave-35E"
    implementation = json.loads((wave35e / "implementation_feasibility_ledger.json").read_text())
    contestability = json.loads((wave35e / "contestability_appeals_ledger.json").read_text())
    assert implementation["runtime_enforcement_evidence"]["evidence_authority_class"] == (
        "runtime_emitted"
    )
    assert contestability["runtime_enforcement_evidence"]["evidence_authority_class"] == (
        "runtime_emitted"
    )
    assert all(row["runtime_owned_provenance"] for row in implementation["rows"])
    assert all(row["runtime_owned_provenance"] for row in contestability["rows"])

    boundary = json.loads(
        (
            fake_repo
            / "_build/policy-design-case/rebaseline/wave-35G/"
            "institutional_provenance_boundary_ledger.json"
        ).read_text()
    )
    assert boundary["summary"]["runtime_owned_provenance_count"] == 6
    assert boundary["summary"]["not_closeout_authority_count"] == 0
    assert boundary["publication_and_closeout_decision"]["boundary_decision"] == (
        "runtime_owned_provenance_required"
    )

    classification = outputs["wave35f_outputs"]["classification"]
    institutional_rows = [
        row
        for row in classification["rows"]
        if Path(row["artifact_path"]).name in INSTITUTIONAL_LEDGER_FILES
    ]
    assert institutional_rows
    assert all(
        row["evidence_authority_class"] in {"runtime_emitted", "runtime_derived"}
        for row in institutional_rows
        if row["finding_id"].startswith(("PDD-097", "PDD-099"))
    )

    assert check.validate_wave35h_provenance(repo_root=fake_repo) == []


def test_wave35h_checker_rejects_runtime_owned_rows_missing_required_fields(
    tmp_path: Path,
) -> None:
    fake_repo = _copy_rebaseline_inputs(tmp_path)
    build.build_wave35h_provenance_outputs(
        repo_root=fake_repo,
        refresh_wave35g_backfill=False,
    )
    implementation_path = (
        fake_repo
        / "_build/policy-design-case/rebaseline/wave-35E/"
        "implementation_feasibility_ledger.json"
    )
    implementation = json.loads(implementation_path.read_text())
    implementation["rows"][0]["runtime_owned_provenance"].pop("claim_binding")
    implementation_path.write_text(json.dumps(implementation, indent=2) + "\n")

    errors = check.validate_wave35h_provenance(repo_root=fake_repo)

    assert any("claim_binding" in error for error in errors)


def _copy_rebaseline_inputs(tmp_path: Path) -> Path:
    fake_repo = tmp_path / "repo"
    rebaseline_src = REPO_ROOT / "_build/policy-design-case/rebaseline"
    rebaseline_dst = fake_repo / "_build/policy-design-case/rebaseline"
    rebaseline_dst.parent.mkdir(parents=True)
    for wave in (
        "wave-35",
        "wave-35A",
        "wave-35B",
        "wave-35C",
        "wave-35D",
        "wave-35E",
        "wave-35F",
        "wave-35G",
    ):
        shutil.copytree(rebaseline_src / wave, rebaseline_dst / wave)
    return fake_repo
