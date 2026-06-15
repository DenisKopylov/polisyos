from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
AUDIT_PATH = (
    REPO_ROOT
    / "architecture"
    / "policy_design_case"
    / "layer3_gy_task0_audit"
    / "layer3_gy_p0_coverage_audit.json"
)


def _validator() -> Any:
    return import_module("tools.quality.validation.check_layer3_gy_p0_coverage_audit")


def _load_audit() -> dict[str, Any]:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def _codes(violations: list[dict[str, Any]]) -> set[str]:
    return {str(item["code"]) for item in violations}


def _blocked_input(audit: dict[str, Any], alias: str) -> dict[str, Any]:
    for row in audit["blocked_dag_state_reads"]["blocked_input_nodes"]:
        if row.get("alias") == alias:
            return row
    raise AssertionError(f"missing blocked input {alias}")


def test_gy_p0_coverage_audit_validator_passes_current_artifact() -> None:
    validator = _validator()

    assert validator.validate(_load_audit()) == []


def test_gy_p0_coverage_audit_rejects_worker_mismatch_greenwash() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["production_worker_workflow_report_status"] = "ok"
    audit["production_job_worker_dag"]["real_dag_probe"]["workflow_report_status"] = "ok"

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "worker_workflow_report_not_failed" in codes


def test_gy_p0_coverage_audit_rejects_missing_candidate_positive_row() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["candidate_positive_firewall"]["rows"] = audit["candidate_positive_firewall"][
        "rows"
    ][:-1]
    audit["summary"]["candidate_positive_rows_enumerated"] = 405

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "candidate_positive_rows_missing" in codes


def test_gy_p0_coverage_audit_rejects_firewall_reason_drift() -> None:
    validator = _validator()
    audit = _load_audit()
    counts = audit["candidate_positive_firewall"]["counts"]["by_firewall_rule"]
    counts["generic_status_without_producer_or_reducer_provenance"] = 396

    assert "firewall_reason_counts_drift" in _codes(validator.validate(audit))


def test_gy_p0_coverage_audit_rejects_lost_blocked_state_read_mapping() -> None:
    validator = _validator()
    audit = _load_audit()
    row = _blocked_input(audit, "run_causal_evaluation")
    row["triggering_missing_reads"] = []

    assert "blocked_input_missing_read_drift" in _codes(validator.validate(audit))


def test_gy_p0_coverage_audit_rejects_depth2_reducer_greenwash() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["depth2_reducer_generalization_status"] = "pass"
    audit["depth2_generalization"]["reducer_probe"]["cli_accepts_case_input"] = True
    audit["depth2_generalization"]["reducer_probe"]["classification"] = "pass"

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "depth2_reducer_case_input_greenwash" in codes
    assert "depth2_reducer_classification_drift" in codes
