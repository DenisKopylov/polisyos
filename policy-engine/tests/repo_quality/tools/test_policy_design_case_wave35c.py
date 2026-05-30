from __future__ import annotations

# ruff: noqa: S101
import os
from pathlib import Path

import pytest

from tools.quality.validation import build_policy_design_case_wave35c as build

REPO_ROOT = Path(__file__).resolve().parents[3]
WAVE35_STAGE_PREREQUISITES = (
    REPO_ROOT / "_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json",
)
pytestmark = pytest.mark.skipif(
    os.environ.get("POLISYOS_RUN_STAGED_REBASELINE_TESTS") != "1"
    or not all(path.exists() for path in WAVE35_STAGE_PREREQUISITES),
    reason=(
        "staged Wave 35 rebaseline check; set POLISYOS_RUN_STAGED_REBASELINE_TESTS=1 "
        "after running the policy-design-case rebaseline pipeline"
    ),
)


def test_wave35c_outputs_close_claim_authority_and_semantic_clusters(
    tmp_path: Path,
) -> None:
    outputs = build.build_wave35c_outputs(
        repo_root=REPO_ROOT,
        wave35c_dir=tmp_path / "wave-35C",
    )

    claim = outputs["claim_authority"]
    assert claim["status"] == "complete"
    assert claim["section_count"] == len(build.REQUIRED_FINAL_SECTIONS)
    assert set(claim["bound_sections"]) == set(build.REQUIRED_FINAL_SECTIONS)
    assert all(row["runtime_claim_registry_id"] for row in claim["rows"])
    assert all(row["claim_argument_id"] for row in claim["rows"])
    assert all(row["warrant_id"] for row in claim["rows"])
    assert all(row["producer_evidence_refs"] for row in claim["rows"])
    assert claim["scorecard_blocker_boundary"]["not_treated_as_remediation"] is True

    extraction = outputs["extraction_authority"]
    assert extraction["status"] == "complete"
    assert extraction["row_count"] > 0
    assert extraction["claim_selected_qc_count"] == extraction["row_count"]
    assert all(row["retrieval_locator"] for row in extraction["rows"])
    assert all(row["ocr_confidence"] for row in extraction["rows"])
    assert all(row["skipped_content_record"] for row in extraction["rows"])
    assert (
        extraction["adjacent_qc_promotion_policy"]["scholar_qc"]["status"]
        == "not_promoted_no_final_claim_selection"
    )

    measurement = outputs["measurement_validity"]
    assert measurement["status"] == "complete"
    assert measurement["survey_selected"] is False
    assert measurement["survey_design_rows"] == []
    abstention = measurement["non_survey_abstentions"][0]
    assert abstention["type"] == "typed_non_survey_abstention"
    assert abstention["future_survey_guard_evidence"]["status"] == "active"

    semantic = outputs["semantic_readiness"]
    assert semantic["status"] == "complete"
    assert set(semantic["pdd_ids"]) == {
        "PDD-048",
        "PDD-050",
        "PDD-051",
        "PDD-057",
        "PDD-087",
    }
    required_keys = set(semantic["required_semantic_ref_keys"])
    assert required_keys <= set(semantic["rows"][0])

    update = outputs["disposition_update"]
    assert update["status"] == "resolved"
    assert update["updated_finding_count"] == 22
    assert update["unresolved_cluster_findings"] == []
    assert update["after_classification_counts"] == {
        "must_fix_before_closeout": 22,
    }
    assert update["pdd088_boundary_status"] == "preserved_not_triggered_no_explanation_support"
