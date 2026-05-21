from __future__ import annotations

# ruff: noqa: S101
from pathlib import Path

from tools.quality.validation import build_policy_design_case_wave35e as build

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_wave35e_outputs_close_human_facing_cluster(tmp_path: Path) -> None:
    outputs = build.build_wave35e_outputs(
        repo_root=REPO_ROOT,
        wave35e_dir=tmp_path / "wave-35E",
    )

    projection = outputs["projection_operator_truthfulness"]
    assert projection["status"] == "complete"
    assert set(projection["observed_projection_states"]) == set(
        build.REQUIRED_PROJECTION_STATES
    )
    assert {
        row["masking_case"]
        for row in projection["projection_masking_negative_controls"]
    } == set(build.PROJECTION_MASKING_FAILURES)
    assert all(
        row["projection_promotion_allowed"] is False
        for row in projection["projection_masking_negative_controls"]
    )
    assert projection["dashboard_to_readiness_diff"]["status"] == "pass"
    assert projection["dashboard_to_readiness_diff"]["missing_in_dashboard_count"] == 0
    assert projection["failure_class_journey"]["status"] == "covered"
    assert projection["denominator_caveats"]["zero_review_caveat_required"] is True
    assert projection["runtime_enforcement_evidence"]["status"] == "test_observed"
    assert (
        projection["runtime_enforcement_evidence"]["evidence_authority_class"]
        == "test_observed"
    )
    assert any(
        "publicationPacket.test.ts" in ref
        for ref in projection["runtime_enforcement_evidence"]["test_refs"]
    )
    projection_only_control = next(
        row
        for row in projection["projection_masking_negative_controls"]
        if row["masking_case"] == "projection_only"
    )
    assert projection_only_control["evidence_authority_class"] == "test_observed"
    assert "publicationPacket.ts#buildProjectionSemantics" in projection_only_control[
        "runtime_enforcement_ref"
    ]

    memory = outputs["memory_authority"]
    assert memory["status"] == "complete"
    assert memory["memory_decision"]["decision"] == "no_memory_abstention"
    assert memory["memory_decision"]["memory_used"] is False
    assert memory["memory_decision"]["empty_replay_surfaces_close_finding"] is False
    assert memory["replay_refs"]["empty_replay_surfaces_do_not_close_finding"] is True
    assert all(row["contamination_detected"] is False for row in memory["contamination_checks"])

    implementation = outputs["implementation_feasibility"]
    assert implementation["status"] == "complete"
    assert implementation["row_count"] == 1
    impl_row = implementation["rows"][0]
    assert impl_row["recommendation_id"]
    assert impl_row["implementation_actor"]
    assert impl_row["feasibility_evidence"]
    assert impl_row["risk_evidence"]
    assert impl_row["monitoring_evidence"]
    assert impl_row["source_refs"]
    assert impl_row["method_refs"]
    assert impl_row["norm_refs"]
    assert impl_row["claim_binding"]["generic_final_text_sufficient"] is False

    contestability = outputs["contestability_appeals"]
    assert contestability["status"] == "complete"
    assert contestability["row_count"] >= 3
    assert {"reissue_required", "stale_required", "withdrawal_required"} <= {
        row["lifecycle_transition"] for row in contestability["rows"]
    }
    assert all(row["standing"] for row in contestability["rows"])
    assert all(row["grounds"] for row in contestability["rows"])
    assert all(row["deadline"] for row in contestability["rows"])
    assert all(row["submitted_evidence"] for row in contestability["rows"])
    assert all(row["owner"] for row in contestability["rows"])
    assert all(row["sla"] for row in contestability["rows"])
    assert all(row["disposition"] for row in contestability["rows"])
    assert all(row["outcome_refs"] for row in contestability["rows"])
    assert all(row["monitoring_changes"] for row in contestability["rows"])

    trust = outputs["trust_framing_ui_negative_tests"]
    assert trust["status"] == "complete"
    assert {row["scenario"] for row in trust["rows"]} == set(
        build.TRUST_NEGATIVE_SCENARIOS
    )
    assert all(row["label"] for row in trust["rows"])
    assert all(row["icon"] for row in trust["rows"])
    assert all(row["color"] for row in trust["rows"])
    assert all(row["badge"] for row in trust["rows"])
    assert all(row["copy"] for row in trust["rows"])
    assert all(row["confidence_label"] for row in trust["rows"])
    assert all(row["signature_cue"] for row in trust["rows"])
    assert all(row["authority_caveat"] for row in trust["rows"])
    assert all(row["zero_review_caveat"] for row in trust["rows"])
    assert all(row["expected_ui_state"] == row["observed_ui_state"] for row in trust["rows"])
    assert all(row["screenshot_or_trace_ref"] for row in trust["rows"])
    assert trust["runtime_enforcement_evidence"]["status"] == "partially_test_observed"
    assert (
        trust["runtime_enforcement_evidence"]["evidence_authority_class"]
        == "mixed_test_observed_and_synthetic_remediation_overlay"
    )
    assert (
        trust["runtime_enforcement_evidence"]["scenario_specific_screenshot_coverage"]
        is False
    )

    update = outputs["disposition_update"]
    assert update["status"] == "resolved"
    assert update["updated_finding_count"] == 19
    assert update["unresolved_cluster_findings"] == []
    assert update["after_classification_counts"] == {
        "must_fix_before_closeout": 19,
    }
