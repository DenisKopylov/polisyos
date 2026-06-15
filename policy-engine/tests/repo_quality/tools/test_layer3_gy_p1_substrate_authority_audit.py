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
    / "layer3_gy_p1_substrate_authority_audit.json"
)


def _validator() -> Any:
    return import_module("tools.quality.validation.check_layer3_gy_p1_substrate_authority_audit")


def _load_audit() -> dict[str, Any]:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def _codes(violations: list[dict[str, Any]]) -> set[str]:
    return {str(item["code"]) for item in violations}


def _risk_row(audit: dict[str, Any], area: str) -> dict[str, Any]:
    for row in audit["substrate_authority_risk_matrix"]:
        if row.get("area") == area:
            return row
    raise AssertionError(f"missing risk row {area}")


def test_gy_p1_substrate_authority_validator_passes_current_artifact() -> None:
    validator = _validator()

    assert validator.validate(_load_audit()) == []


def test_gy_p1_substrate_authority_rejects_dag_authority_greenwash() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["p0_dag_cas_authority_manifest_count"] = 178
    audit["cas_integrity_dedup_gc_tamper_evidence"]["p0_dag_manifest_scan"][
        "authority_manifest_count"
    ] = 178
    audit["cas_integrity_dedup_gc_tamper_evidence"]["authority_bridge_map"] = [
        {
            "surface": "scientist_workflow_report_final_state_run_dag",
            "status": "event_backed_authority_manifest",
        }
    ]

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "dag_authority_manifest_greenwash" in codes
    assert "missing_dag_authority_gap_row" in codes


def test_gy_p1_substrate_authority_rejects_raw_route_redaction_greenwash() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["artifact_raw_content_route_unredacted"] = False
    audit["summary"]["artifact_download_route_unredacted"] = False
    route = audit["secrets_pii_scan"]["route_behavior"]
    route["artifact_raw_content_route_unredacted"] = False
    route["artifact_download_route_unredacted"] = False

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "raw_content_route_greenwash" in codes
    assert "download_route_greenwash" in codes


def test_gy_p1_substrate_authority_rejects_temporal_surface_greenwash() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["runtime_workflow_temporal_surface_supported"] = True
    unsupported = audit["time_semantics_bitemporality"]["runtime_temporal_capabilities"][
        "unsupported_surfaces"
    ]
    unsupported.remove("run_workflow")

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "temporal_unsupported_surface_greenwash" in codes


def test_gy_p1_substrate_authority_rejects_g5_s12_measured_greenwash() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["g5_s12_pass_refs_exact_producer_artifacts_found"] = True
    audit["summary"]["g5_s12_pass_uses_authorial_refs"] = False
    g5_refs = audit["cost_voi_budget_honesty"]["g5_s12_pass_exact_refs"]
    g5_refs["exact_producer_artifacts_found"] = True
    g5_refs["classification"] = "measured_s12_objects"

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "g5_s12_exact_ref_greenwash" in codes
    assert "g5_s12_classification_drift" in codes


def test_gy_p1_substrate_authority_rejects_missing_negative_boundary() -> None:
    validator = _validator()
    audit = _load_audit()
    _risk_row(audit, "secrets/PII")["must_not_count_as"] = ""

    assert "risk_row_missing_negative_boundary" in _codes(validator.validate(audit))
