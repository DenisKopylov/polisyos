from __future__ import annotations

# ruff: noqa: S101
import os
from pathlib import Path

import pytest

from tools.quality.validation import build_policy_design_case_wave35b as build

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


def test_wave35b_outputs_close_adversarial_cluster(tmp_path: Path) -> None:
    outputs = build.build_wave35b_outputs(
        repo_root=REPO_ROOT,
        wave35b_dir=tmp_path / "wave-35B",
    )

    adversarial = outputs["adversarial_matrix"]
    assert adversarial["status"] == "complete"
    assert adversarial["final_claim_authority_promotion_count"] == 0
    assert adversarial["failed_closed_count"] == adversarial["row_count"]
    assert set(adversarial["required_probe_categories"]) <= set(
        adversarial["observed_probe_categories"]
    )
    assert all(row["observed_runtime_code"] for row in adversarial["rows"])

    cache = outputs["cache_controls"]
    assert cache["status"] == "complete"
    assert cache["rejected_or_quarantined_count"] == cache["control_count"]
    assert cache["accepted_blocker_honesty"]
    assert all(
        row["expected_rejection_code"] == row["observed_rejection_code"]
        for row in cache["rows"]
    )

    taxonomy = outputs["error_taxonomy"]
    assert taxonomy["status"] == "complete"
    assert set(taxonomy["required_components"]) <= set(taxonomy["observed_components"])
    assert (
        taxonomy["positive_evidence_preserved"]["status"]
        == "preserved_as_false_alarm_positive_evidence"
    )
    assert (
        taxonomy["readiness_dashboard_projection_contract"][
            "generic_failure_only_allowed"
        ]
        is False
    )

    strategic = outputs["strategic_ledger"]
    assert strategic["status"] == "complete"
    assert {"gaming", "fraud", "arbitrage", "monitoring"} <= set(
        strategic["risk_classes"]
    )
    assert (
        strategic["generic_monitoring_prose_disposition"]["status"]
        == "rejected_as_insufficient"
    )
    assert all(row["mechanism_bound"] for row in strategic["rows"])

    update = outputs["disposition_update"]
    assert update["status"] == "resolved"
    assert update["updated_finding_count"] == 12
    assert update["unresolved_cluster_findings"] == []
    assert update["after_classification_counts"] == {
        "false_alarm_with_evidence": 1,
        "must_fix_before_closeout": 11,
    }
