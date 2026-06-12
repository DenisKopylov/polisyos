from __future__ import annotations

from pathlib import Path
from typing import Any

import polisyos.runtime.quality.layer3_health_metric_governance as g8
from tools.quality.validation import check_policy_design_case_layer3_g8_readiness as validator

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_layer3_g8_readiness_declares_exact_artifact_contract() -> None:
    assert validator.G8_SCHEMA_VERSION == g8.G8_SCHEMA_VERSION
    assert validator.G8_RULE_VERSION == g8.G8_RULE_VERSION
    assert validator.G8_GENERATED_ARTIFACT_FAMILY_ID == g8.G8_GENERATED_ARTIFACT_FAMILY_ID
    assert {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS} == {
        "architecture/policy_design_case/layer3_g8_health_metric_registry.json",
        "architecture/policy_design_case/layer3_g8_metric_source_snapshot.json",
        "architecture/policy_design_case/layer3_g8_normalized_metric_signals.json",
        "architecture/policy_design_case/layer3_g8_metric_trend_report.json",
        "architecture/policy_design_case/layer3_g8_cross_metric_diagnosis.json",
        "architecture/policy_design_case/layer3_g8_domain_vs_search_ceiling_gate.json",
        "architecture/policy_design_case/layer3_g8_metric_gaming_firewall.json",
        "architecture/policy_design_case/layer3_g8_warning_lifecycle_ledger.json",
        "architecture/policy_design_case/layer3_g8_d44_corpus_rebasing_rule.json",
        "architecture/policy_design_case/layer3_g8_d44_reannotation_coverage_matrix.json",
        "architecture/policy_design_case/layer3_g8_d44_rebasing_trigger_ledger.json",
        "architecture/policy_design_case/layer3_g8_d44_rebasing_candidate_set.json",
        "architecture/policy_design_case/layer3_g8_d44_rebasing_receipt.json",
        "architecture/policy_design_case/layer3_g8_sealed_battery_integrity_join.json",
        "architecture/policy_design_case/layer3_g8_open_question_answer_ledger.json",
        "architecture/policy_design_case/layer3_g8_metric_governance_audit_surface.json",
        "architecture/policy_design_case/layer3_g8_closeout_signal_consumer_gate.json",
        "architecture/policy_design_case/layer3_g8_public_export_projection_refs.json",
        "architecture/policy_design_case/layer3_g8_replay_manifest.json",
        "architecture/policy_design_case/layer3_g8_conformance_report.json",
        "architecture/policy_design_case/layer3_g8_health_metric_governance_delta.toml",
        (
            "architecture/policy_design_case/"
            "layer3_g8_metric_governance_route_contract_registry.toml"
        ),
        "architecture/policy_design_case/layer3_g8_registry_ratchet_delta.json",
        "architecture/policy_design_case/layer3_g8_readiness_manifest.json",
    }
    assert set(validator.EXPECTED_MANIFEST_DRIFT_KEYS) == set(
        g8.EXPECTED_MANIFEST_DRIFT_KEYS
    )


def test_layer3_g8_readiness_writes_and_passes_current_blocked_value_state() -> None:
    write_report = validator.validate_layer3_g8_readiness(REPO_ROOT, write=True)
    validation = validator.validate_layer3_g8_readiness(REPO_ROOT)

    assert write_report["status"] == "pass"
    assert validation["status"] == "pass"
    assert validation["artifacts"]["missing_persisted_artifact_paths"] == []
    summary = validation["summary"]
    assert summary["g8_metric_governance_status"] == "pass"
    assert summary["g8_canonical_metric_count"] == 5
    assert summary["g8_metric_source_count"] >= 44
    assert summary["g8_metric_trend_report_status"] == "pass"
    assert summary["g8_effective_independence_status"] == "singular"
    assert summary["g8_effective_independent_evidence_count"] == 1
    assert summary["g8_domain_vs_search_ceiling_status"] == (
        "governance_stall_repair_required"
    )
    assert summary["g8_d44_reannotation_coverage_status"] == "pass"
    assert summary["g8_d44_rebasing_trigger_status"] == "pass_no_rebase_due"
    assert summary["g8_d44_rebasing_receipt_status"] == "pass_no_rebase_required"
    assert summary["g8_sealed_battery_integrity_status"] == "pass"
    assert summary["g8_closeout_signal_consumer_status"] == "pass"
    assert summary["g8_open_question_answer_status"] == "pass"
    assert summary["g8_manifest_runtime_drift_key_count"] == 0
    assert summary["expected_artifact_count"] == len(validator.EXPECTED_ARTIFACT_PATHS)


def test_layer3_g8_readiness_requires_registration_inventory_and_docs() -> None:
    validation = validator.validate_layer3_g8_readiness(REPO_ROOT)

    assert validation["status"] == "pass"
    assert validation["summary"]["g8_generated_artifacts_registration_status"] == "pass"
    assert validation["summary"]["g8_inventory_surface_status"] == "pass"
    assert validation["summary"]["g8_reference_docs_status"] == "pass"
    assert validation["summary"]["g8_route_contract_registry_status"] == "pass"
    assert validation["summary"]["g8_registry_ratchet_status"] == "pass"


def test_layer3_g8_write_path_must_include_every_expected_artifact(
    monkeypatch: Any,
) -> None:
    omitted = Path("architecture/policy_design_case/layer3_g8_replay_manifest.json")
    expected_paths = tuple(
        Path(path) for path in sorted({p.as_posix() for p in validator.EXPECTED_ARTIFACT_PATHS})
    )
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", expected_paths)
    monkeypatch.setattr(
        validator,
        "_write_artifacts",
        lambda _repo_root, _bundle: [
            path.as_posix() for path in expected_paths if path != omitted
        ],
    )

    validation = validator.validate_layer3_g8_readiness(REPO_ROOT, write=True)

    assert validation["status"] == "fail"
    assert "layer3_g8_persisted_artifact_missing" in {
        issue["code"] for issue in validation["issues"]
    }


def test_layer3_g8_readiness_fails_when_conformance_negative_is_missing(
    monkeypatch: Any,
) -> None:
    def failing_conformance_report(**_kwargs: Any) -> g8.Layer3G8ConformanceReport:
        return g8.Layer3G8ConformanceReport(
            status="blocked",
            negative_results=(),
            missing_negative_ids=("public_projection_authority_leak",),
            failing_negative_ids=(),
            issue_codes=("layer3_g8_conformance_negative_missing",),
        )

    monkeypatch.setattr(g8, "build_g8_conformance_report", failing_conformance_report)

    validation = validator.validate_layer3_g8_readiness(REPO_ROOT, write=True)

    assert validation["status"] == "fail"
    assert validation["summary"]["g8_conformance_status"] == "blocked"
    assert "layer3_g8_conformance_negative_missing" in {
        issue["code"] for issue in validation["issues"]
    }
