from __future__ import annotations

# ruff: noqa: S101
from pathlib import Path

from tools.quality.validation import build_policy_design_case_wave35d as build

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_wave35d_outputs_close_operational_recovery_cluster(tmp_path: Path) -> None:
    outputs = build.build_wave35d_outputs(
        repo_root=REPO_ROOT,
        wave35d_dir=tmp_path / "wave-35D",
    )

    root_cause = outputs["operator_root_cause"]
    assert root_cause["status"] == "complete"
    assert set(root_cause["required_failure_classes"]) <= set(
        root_cause["observed_failure_classes"]
    )
    assert root_cause["top_level_diagnostic_command_list"]
    assert all(row["first_missing_producer"] for row in root_cause["scorecard_failure_breadcrumb_rows"])
    assert all(row["next_command"] for row in root_cause["scorecard_failure_breadcrumb_rows"])
    assert all(row["event_refs"] for row in root_cause["scorecard_failure_breadcrumb_rows"])
    assert all(row["timeline_refs"] for row in root_cause["scorecard_failure_breadcrumb_rows"])

    restore = outputs["restore_drill"]
    assert restore["status"] == "complete"
    assert restore["retained_copy_hashes"]
    assert all(row["match"] for row in restore["archive_hash_verification"])
    assert restore["corruption_injection"]["status"] == "injected_and_detected"
    assert restore["recovery_result"]["status"] == "pass"
    assert restore["restored_dashboard_verification"]["status"] == "pass"
    assert restore["restored_lineage_verification"]["status"] == "pass"
    assert restore["restored_scorecard_verification"]["status"] == "pass"
    assert restore["restored_final_artifact_verification"]["status"] == "pass"

    resource = outputs["resource_exhaustion"]
    assert resource["status"] == "complete"
    assert set(resource["required_limit_types"]) == set(resource["observed_limit_types"])
    assert resource["partial_evidence_negative_scenario_count"] == len(
        resource["required_limit_types"]
    )
    assert all(
        row["degradation_behavior"]["partial_evidence_promoted"] is False
        for row in resource["rows"]
    )
    assert all(row["downstream_claim_impact"] for row in resource["rows"])
    assert all(row["scorecard_impact"] for row in resource["rows"])

    parity = outputs["live_polling_parity"]
    assert parity["status"] == "complete"
    assert parity["sse_websocket_cursor_state"]["authoritative_cursor"]
    assert parity["replay_cursor"]["event_count"] > 0
    assert parity["polling_snapshot"]["snapshot_hash"]
    assert len(parity["snapshot_hash_trail"]) == 3
    assert all(
        row["parity_status"] == "pass"
        for row in parity["dropped_reordered_reconnect_scenarios"]
    )
    assert parity["governance_wait_parity"]["status"] == "pass"
    assert parity["terminal_state_parity"]["status"] == "pass"
    assert parity["operator_visible_fallback_explanation"]["status"] == "present"

    archive = outputs["archive_reproducibility"]
    assert archive["status"] == "complete"
    assert set(archive["legal_data_model_provider_source_version_trust_store_snapshots"]) == {
        "legal",
        "data",
        "model",
        "provider",
        "source",
        "version",
        "trust_store",
    }
    assert archive["verifier"]["status"] == "pass"
    assert archive["signature"]["status"] == "present"
    assert archive["lockfile"]["sha256"]
    assert archive["schema_refs"]
    assert archive["redaction_refs"]["provenance_redaction_policies"]
    assert archive["long_horizon_restore_replay_drill"]["status"] == "pass"
    assert archive["retention_jurisdiction"]["jurisdiction"] == "Ukraine"
    assert archive["deterministic_replay_inputs"]["cas_refs"]
    assert archive["bounded_drift_explanation"]["status"] == "typed_bounded_drift_recorded"

    update = outputs["disposition_update"]
    assert update["status"] == "resolved"
    assert update["updated_finding_count"] == 29
    assert update["unresolved_cluster_findings"] == []
    assert update["after_classification_counts"] == {"must_fix_before_closeout": 29}
