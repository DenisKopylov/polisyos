# ruff: noqa: S101

from __future__ import annotations

import json
from pathlib import Path

from tests._helpers.hds_quality import complete_job_payload, complete_quality_evidence
from tools.ops_runners.runtime.canary_evidence import assemble_canary_evidence
from tools.quality.validation.inspect_evidence_bundles import (
    SCHEMA_VERSION,
    build_evidence_bundle_inspection_report,
    main,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _fresh_serious_bundle(tmp_path: Path, *, canary_kind: str = "research") -> Path:
    bundle = assemble_canary_evidence(
        output_root=tmp_path,
        output_dir=tmp_path / f"{canary_kind}-bundle",
        canary_kind=canary_kind,
        command_metadata={
            "argv": ["policyos-canary", "--real"],
            "matrix_lane_id": (
                f"profile-{canary_kind}__provider-simulated__data-canonical_production"
                "__scenario-public_golden__ui-api_only"
            ),
        },
        request_payload={"request": "Evaluate Ukraine MSME support."},
        job_payload=complete_job_payload(),
        provider_preflight={"status": "passed"},
        quality_evidence=complete_quality_evidence(),
    )
    bundle_payload_path = bundle / "bundle.json"
    bundle_payload = json.loads(bundle_payload_path.read_text(encoding="utf-8"))
    bundle_payload["quality_status"] = "pass"
    bundle_payload_path.write_text(json.dumps(bundle_payload), encoding="utf-8")

    scorecard_path = bundle / "quality_evidence" / "quality_scorecard.json"
    scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
    scorecard["quality_status"] = "pass"
    scorecard["approval_state"] = "approval_ready"
    scorecard["blocking_quality_failures"] = []
    scorecard_path.write_text(json.dumps(scorecard), encoding="utf-8")

    public_export_path = bundle / "quality_evidence" / "public_export_bundle.json"
    public_export = json.loads(public_export_path.read_text(encoding="utf-8"))
    public_export["artifacts"]["quality_scorecard_summary"]["quality_status"] = "pass"
    public_export["artifacts"]["quality_scorecard_summary"]["approval_state"] = (
        "approval_ready"
    )
    public_export["artifacts"]["quality_scorecard_summary"]["blocking_failure_count"] = 0
    public_export_path.write_text(json.dumps(public_export), encoding="utf-8")
    return bundle


def _failure_codes(report: dict[str, object]) -> set[str]:
    return {
        str(finding["code"])
        for finding in report["findings"]
        if isinstance(finding, dict) and finding.get("status") == "fail"
    }


def test_phase64_inspection_accepts_complete_selected_serious_bundle(
    tmp_path: Path,
) -> None:
    bundle = _fresh_serious_bundle(tmp_path, canary_kind="research")
    matrix_run = {
        "schema_version": "policyos.canary_matrix_run.v1",
        "selected_lane_ids": [
            "profile-research__provider-simulated__data-canonical_production"
            "__scenario-public_golden__ui-api_only"
        ],
        "lanes": [
            {
                "lane_id": (
                    "profile-research__provider-simulated__data-canonical_production"
                    "__scenario-public_golden__ui-api_only"
                ),
                "declared_status": "ready",
                "status": "passed",
                "bundle_path": str(bundle),
                "scorecard_status": "pass",
            }
        ],
    }

    report = build_evidence_bundle_inspection_report(
        repo_root=REPO_ROOT,
        matrix_run_payload=matrix_run,
    )

    assert report["schema_version"] == SCHEMA_VERSION
    assert report["status"] == "pass"
    assert report["summary"]["selected_serious_count"] == 1
    assert report["summary"]["closeout_ready_count"] == 1
    assert report["findings"] == []
    assert report["bundle_inspections"][0]["closeout_ready"] is True
    assert {
        component["component_id"]
        for component in report["bundle_inspections"][0]["components"]
        if component["status"] == "pass"
    } >= {
        "evidence_provenance_manifest",
        "authority_envelopes",
        "diagnostic_events",
        "diagnostic_event_type_registry_version",
        "provider_model_quality_ledger",
        "performance_budget_evidence",
        "cas_producer_governance_metadata",
        "effective_mode_ledger",
        "fallback_degradation_ledger",
        "semantic_binding_ledger",
        "prompt_tool_parser_ledger",
        "source_truth_conflict_records",
        "adapter_preservation_records",
        "schema_compatibility_decisions",
        "invariant_proof_harness_report",
        "replay_evidence",
        "resilience_evidence",
        "privacy_security_evidence",
        "human_review_evidence",
        "decision_quality_evidence",
        "assurance_case",
        "diagnostic_slo_evidence",
        "attestation_records",
        "continuous_governance_lifecycle_evidence",
        "data_forge_snapshot_binding",
        "scholar_academic_evidence",
        "policy_design_concept_spine_boundary",
        "policy_design_jurisdiction_spine_boundary",
        "runtime_orchestration_continuity",
    }


def test_w4a_inspection_flags_missing_runtime_orchestration_continuity(
    tmp_path: Path,
) -> None:
    bundle = _fresh_serious_bundle(tmp_path, canary_kind="research")
    continuity = bundle / "quality_evidence" / "runtime_orchestration_continuity.json"
    continuity.unlink()

    report = build_evidence_bundle_inspection_report(
        repo_root=REPO_ROOT,
        bundle_dirs=[bundle],
    )

    assert report["status"] == "fail"
    assert "phase64_component_missing" in _failure_codes(report)
    assert report["bundle_inspections"][0]["closeout_ready"] is False


def test_phase64_inspection_flags_missing_data_forge_snapshot_boundary(
    tmp_path: Path,
) -> None:
    bundle = _fresh_serious_bundle(tmp_path, canary_kind="research")
    snapshot = bundle / "quality_evidence" / "data_forge_snapshot_binding.json"
    snapshot.unlink()
    assert (bundle / "quality_evidence" / "production_data_quality.json").is_file()

    report = build_evidence_bundle_inspection_report(
        repo_root=REPO_ROOT,
        bundle_dirs=[bundle],
    )

    assert report["status"] == "fail"
    assert "data_forge_snapshot_binding_missing" in _failure_codes(report)
    assert report["bundle_inspections"][0]["closeout_ready"] is False


def test_phase64_inspection_flags_missing_scholar_academic_boundary(
    tmp_path: Path,
) -> None:
    bundle = _fresh_serious_bundle(tmp_path, canary_kind="research")
    scholar = bundle / "quality_evidence" / "scholar_academic_evidence.json"
    scholar.unlink()

    report = build_evidence_bundle_inspection_report(
        repo_root=REPO_ROOT,
        bundle_dirs=[bundle],
    )

    assert report["status"] == "fail"
    assert "policy_design_scholar_academic_evidence_missing" in _failure_codes(report)
    assert report["bundle_inspections"][0]["closeout_ready"] is False


def test_phase64_inspection_flags_borrowed_report_authority_envelope(
    tmp_path: Path,
) -> None:
    bundle = _fresh_serious_bundle(tmp_path, canary_kind="research")
    production_data = json.loads(
        (bundle / "quality_evidence" / "production_data_quality.json").read_text(
            encoding="utf-8"
        )
    )
    stale_path = bundle / "quality_evidence" / "continuous_governance_stale_report.json"
    stale = json.loads(stale_path.read_text(encoding="utf-8"))
    borrowed = dict(production_data["authority_envelope"])
    runtime_ref = stale["continuous_governance_stale_report_ref"]
    borrowed["artifact_ref"] = runtime_ref
    borrowed["cas_ref"] = runtime_ref
    borrowed["payload_sha256"] = runtime_ref
    borrowed["output_refs"] = [runtime_ref]
    stale["authority_envelope"] = borrowed
    stale_path.write_text(json.dumps(stale), encoding="utf-8")

    report = build_evidence_bundle_inspection_report(
        repo_root=REPO_ROOT,
        bundle_dirs=[bundle],
    )

    assert report["status"] == "fail"
    assert "hds_borrowed_authority_envelope" in _failure_codes(report)
    assert report["bundle_inspections"][0]["closeout_ready"] is False


def test_phase64_inspection_blocks_missing_required_component_and_public_leak(
    tmp_path: Path,
) -> None:
    bundle = _fresh_serious_bundle(tmp_path, canary_kind="production")
    (bundle / "quality_evidence" / "prompt_tool_ledger.json").unlink()
    public_export = bundle / "quality_evidence" / "public_export_bundle.json"
    payload = json.loads(public_export.read_text(encoding="utf-8"))
    payload["artifacts"]["unsafe_debug"] = {
        "provider_credential": "sk-test-should-never-be-public"
    }
    public_export.write_text(json.dumps(payload), encoding="utf-8")

    report = build_evidence_bundle_inspection_report(
        repo_root=REPO_ROOT,
        bundle_dirs=[bundle],
    )

    assert report["status"] == "fail"
    assert _failure_codes(report) >= {
        "phase64_component_missing",
        "phase64_public_bundle_leak",
    }
    assert report["bundle_inspections"][0]["closeout_ready"] is False


def test_phase64_matrix_non_ready_governed_production_uses_typed_setup_evidence(
    tmp_path: Path,
) -> None:
    bundle = _fresh_serious_bundle(tmp_path, canary_kind="research")
    matrix_run = {
        "schema_version": "policyos.canary_matrix_run.v1",
        "selected_lane_ids": [
            "profile-research__provider-simulated__data-canonical_production"
            "__scenario-public_golden__ui-api_only",
            "profile-production__provider-simulated__data-canonical_production"
            "__scenario-public_golden__ui-api_only",
        ],
        "lanes": [
            {
                "lane_id": (
                    "profile-research__provider-simulated__data-canonical_production"
                    "__scenario-public_golden__ui-api_only"
                ),
                "declared_status": "ready",
                "status": "passed",
                "bundle_path": str(bundle),
                "scorecard_status": "pass",
            },
            {
                "lane_id": (
                    "profile-production__provider-simulated__data-canonical_production"
                    "__scenario-public_golden__ui-api_only"
                ),
                "declared_status": "quarantined",
                "status": "blocked",
                "bundle_path": None,
                "scorecard_status": "not_run",
                "failure_envelope": {
                    "type": "local_backing_service_unavailable",
                    "code": "canary_postgresql_state_store_unavailable",
                    "readiness_state": "not_ready",
                    "phase": "setup",
                    "owner": "runtime-platform",
                    "next_action": "Start PostgreSQL-backed control-plane state.",
                },
            },
        ],
    }

    report = build_evidence_bundle_inspection_report(
        repo_root=REPO_ROOT,
        matrix_run_payload=matrix_run,
    )

    production = next(
        item
        for item in report["bundle_inspections"]
        if item["profile"] == "production"
    )
    assert report["status"] == "pass"
    assert report["summary"]["selected_serious_count"] == 2
    assert report["summary"]["closeout_ready_count"] == 1
    assert production["status"] == "blocked"
    assert production["closeout_ready"] is False
    assert production["setup_evidence"]["readiness_state"] == "not_ready"

    del matrix_run["lanes"][1]["failure_envelope"]["type"]
    failed = build_evidence_bundle_inspection_report(
        repo_root=REPO_ROOT,
        matrix_run_payload=matrix_run,
    )

    assert failed["status"] == "fail"
    assert _failure_codes(failed) >= {"phase64_typed_setup_evidence_missing"}
    assert failed["summary"]["closeout_ready_count"] == 1


def test_phase64_matrix_failed_research_lane_preserves_typed_failure_envelope(
    tmp_path: Path,
) -> None:
    matrix_run = {
        "schema_version": "policyos.canary_matrix_run.v1",
        "selected_lane_ids": [
            "profile-research__provider-live_gonka_proxy__data-canonical_production"
            "__scenario-public_golden__ui-api_only"
        ],
        "lanes": [
            {
                "lane_id": (
                    "profile-research__provider-live_gonka_proxy__data-canonical_production"
                    "__scenario-public_golden__ui-api_only"
                ),
                "declared_status": "ready",
                "status": "failed",
                "bundle_path": None,
                "scorecard_status": "fail",
                "failure_envelope": {
                    "type": "runtime_domain_failure",
                    "code": "source_family_mismatch",
                    "readiness_state": "not_ready",
                    "phase": "fabric_source_selection",
                    "owner": "team-fabric",
                    "root_cause_class": "runtime_domain_failure",
                    "next_action": "Bind Fabric to the scenario source contract.",
                },
            }
        ],
    }

    report = build_evidence_bundle_inspection_report(
        repo_root=REPO_ROOT,
        matrix_run_payload=matrix_run,
    )

    inspection = report["bundle_inspections"][0]
    assert report["status"] == "fail"
    assert inspection["status"] == "failed"
    assert inspection["setup_evidence"]["code"] == "source_family_mismatch"
    assert inspection["matrix_failure_envelope"]["root_cause_class"] == (
        "runtime_domain_failure"
    )
    assert _failure_codes(report) >= {"phase64_matrix_lane_not_passed"}
    finding = next(
        item for item in report["findings"] if item["code"] == "phase64_matrix_lane_not_passed"
    )
    assert finding["failure_envelope_code"] == "source_family_mismatch"
    assert finding["owner"] == "team-fabric"


def test_phase64_inspection_rejects_public_export_scorecard_promotion(
    tmp_path: Path,
) -> None:
    bundle = _fresh_serious_bundle(tmp_path, canary_kind="research")
    scorecard_path = bundle / "quality_evidence" / "quality_scorecard.json"
    scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
    scorecard["quality_status"] = "fail"
    scorecard_path.write_text(json.dumps(scorecard), encoding="utf-8")
    public_export = bundle / "quality_evidence" / "public_export_bundle.json"
    payload = json.loads(public_export.read_text(encoding="utf-8"))
    payload["artifacts"]["quality_scorecard_summary"]["quality_status"] = "pass"
    public_export.write_text(json.dumps(payload), encoding="utf-8")

    report = build_evidence_bundle_inspection_report(
        repo_root=REPO_ROOT,
        bundle_dirs=[bundle],
    )

    assert report["status"] == "fail"
    assert _failure_codes(report) >= {"phase64_public_export_truth_mismatch"}


def test_phase64_inspection_preserves_operator_triage_ledger_for_failed_scorecard(
    tmp_path: Path,
) -> None:
    bundle = _fresh_serious_bundle(tmp_path, canary_kind="research")
    scorecard_path = bundle / "quality_evidence" / "quality_scorecard.json"
    scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
    root_cause = {
        "triage_id": "triage:team-fabric:runtime_domain_failure:source_family_mismatch",
        "owner": "team-fabric",
        "root_cause_class": "runtime_domain_failure",
        "first_failing_artifact_ref": "sha256:" + "7" * 64,
        "next_action": "Bind Fabric to an admissible scenario source contract.",
        "failure_codes": ["source_family_mismatch"],
        "gates": ["fabric_retrieval_trace_present"],
        "collapsed_failure_count": 2,
    }
    scorecard["quality_status"] = "fail"
    scorecard["blocking_quality_failures"] = [
        {
            "gate": "fabric_retrieval_trace_present",
            "code": "source_family_mismatch",
            "layer": "fabric_retrieval",
            "phase": "fabric_source_selection",
            "message": "Fabric source-selection evidence failed.",
            "evidence_ref": "quality_evidence/fabric_retrieval_trace.json",
            "next_action": root_cause["next_action"],
            "owner": "team-fabric",
            "root_cause_class": "runtime_domain_failure",
            "first_failing_artifact_ref": root_cause["first_failing_artifact_ref"],
        }
    ]
    scorecard["operator_triage_ledger"] = {
        "schema_version": "policyos.operator_triage_ledger.v1",
        "root_cause_count": 1,
        "root_causes": [root_cause],
    }
    scorecard_path.write_text(json.dumps(scorecard), encoding="utf-8")

    report = build_evidence_bundle_inspection_report(
        repo_root=REPO_ROOT,
        bundle_dirs=[bundle],
    )

    inspection = report["bundle_inspections"][0]
    assert report["status"] == "fail"
    assert inspection["operator_triage_ledger"]["root_causes"][0] == root_cause
    assert "phase64_operator_triage_ledger_missing" not in _failure_codes(report)
    assert "phase64_scorecard_not_pass" in _failure_codes(report)


def test_phase64_cli_writes_inspection_report(tmp_path: Path) -> None:
    bundle = _fresh_serious_bundle(tmp_path, canary_kind="research")
    output = tmp_path / "phase64_inspection.json"

    code = main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--bundle-dir",
            str(bundle),
            "--json-output",
            str(output),
            "--require-passing",
        ]
    )

    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "pass"
