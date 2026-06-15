from __future__ import annotations

import copy
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
    / "layer3_gy_source_contract_admissibility_audit.json"
)


def _validator() -> Any:
    return import_module(
        "tools.quality.validation.check_layer3_gy_source_contract_admissibility_audit"
    )


def _load_audit() -> dict[str, Any]:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def _codes(violations: list[dict[str, Any]]) -> set[str]:
    return {str(item["code"]) for item in violations}


def _row(audit: dict[str, Any], route_id: str) -> dict[str, Any]:
    for item in audit["route_rows"]:
        if item.get("route_id") == route_id:
            return item
    raise AssertionError(f"missing route row {route_id}")


def test_gy_source_contract_admissibility_validator_passes_current_artifact() -> None:
    validator = _validator()

    assert validator.validate(_load_audit()) == []


def test_gy_source_contract_admissibility_rejects_missing_route_row() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["route_rows"] = [
        row
        for row in audit["route_rows"]
        if row.get("route_id") != "fetch.executor.admission_consumer"
    ]

    assert "missing_required_route_row" in _codes(validator.validate(audit))


def test_gy_source_contract_admissibility_rejects_fetch_plan_greenwash() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["fetch_plan_required_facets_present_count"] = 1
    audit["summary"]["license_reaches_fetch_plan"] = True
    probe = audit["probe"]["fetch_admission_probe"]
    probe["required_facets_present_in_plan_payload"] = ["source_rights"]
    probe["required_facets_missing_from_plan_payload"] = [
        facet
        for facet in probe["required_facets_missing_from_plan_payload"]
        if facet != "source_rights"
    ]

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "fetch_plan_facets_unexpectedly_present" in codes
    assert "fetch_plan_missing_facet_set_drift" in codes


def test_gy_source_contract_admissibility_rejects_executor_gate_claim() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["executor_consumes_source_contract_gate"] = True
    row = _row(audit, "fetch.executor.admission_consumer")
    row["capability_state"] = "executor_consumes_source_contract_gate"
    row["gap_labels"] = [
        label for label in row["gap_labels"] if label != "consumer_missing"
    ]

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "required_route_state_changed" in codes
    assert "executor_consumer_gap_missing" in codes


def test_gy_source_contract_admissibility_rejects_strict_missing_candidate_selected() -> None:
    validator = _validator()
    audit = _load_audit()
    strict = audit["probe"]["strict_gate_probe"]
    strict["missing_candidate_reason_code"] = None
    strict["missing_candidate_summary"] = {
        "requirements": 1,
        "selected": 1,
        "rejected": 0,
        "blocked": 0,
        "context_only": 0,
    }

    assert "strict_gate_probe_drift" in _codes(validator.validate(audit))


def test_gy_source_contract_admissibility_rejects_lost_claim_bindability_facet() -> None:
    validator = _validator()
    audit = _load_audit()
    contract = audit["probe"]["data_requirement_contract"]
    contract["mandatory_facets"] = [
        facet for facet in contract["mandatory_facets"] if facet != "claim_bindability_refs"
    ]

    assert "mandatory_facets_drift" in _codes(validator.validate(audit))


def test_gy_source_contract_admissibility_rejects_lost_trace_issue() -> None:
    validator = _validator()
    audit = _load_audit()
    strict = audit["probe"]["strict_gate_probe"]
    strict["source_selection_trace_issue_codes"] = [
        code
        for code in strict["source_selection_trace_issue_codes"]
        if code != "selected_source_missing_freshness_refs"
    ]

    assert "strict_trace_issue_missing" in _codes(validator.validate(audit))


def test_gy_source_contract_admissibility_rejects_network_scope_laundering() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["methodology"] = copy.deepcopy(audit["methodology"])
    audit["methodology"]["network_fetches_run"] = True

    assert "network_scope_laundering" in _codes(validator.validate(audit))
