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
    / "layer3_gy_data_requirement_compiler_audit.json"
)


def _validator() -> Any:
    return import_module(
        "tools.quality.validation.check_layer3_gy_data_requirement_compiler_audit"
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


def test_gy_data_requirement_compiler_audit_validator_passes_current_artifact() -> None:
    validator = _validator()

    assert validator.validate(_load_audit()) == []


def test_gy_data_requirement_compiler_audit_rejects_route_pinned_greenwash() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["classification"]["primary"] = "route_pinned"
    audit["classification"]["route_pinned"] = True
    audit["summary"]["classification"] = "route_pinned"
    audit["summary"]["route_pinned"] = True
    audit["summary"]["normal_fetch_plan_consumes_data_requirement_specs"] = True

    codes = _codes(validator.validate(audit))
    assert "classification_drift" in codes
    assert "summary_semantics_drift" in codes


def test_gy_data_requirement_compiler_audit_rejects_default_compile_spec_claim() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["compiler_default_public_wrapper_emits_specs_for_pinned_scenario"] = True
    audit["summary"]["default_public_scenario_spec_count"] = 3
    audit["probes"]["default_public_scenario_compile"]["spec_count"] = 3

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "default_compile_probe_greenwash" in codes


def test_gy_data_requirement_compiler_audit_rejects_scenario_contract_specs_claim() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["scenario_contract_surfaces_compiled_specs_for_pinned_scenario"] = True
    audit["summary"]["scenario_contract_data_requirement_spec_count"] = 3
    audit["probes"]["scenario_evidence_contract_probe"]["data_requirement_specs_count"] = 3

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "scenario_contract_specs_greenwash" in codes


def test_gy_data_requirement_compiler_audit_rejects_missing_fetch_bridge_row() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["route_rows"] = [
        row
        for row in audit["route_rows"]
        if row.get("route_id")
        != "retrieval.catalog_binding_to_fetch_plan.absent_data_requirement_bridge"
    ]

    assert "missing_required_route_row" in _codes(validator.validate(audit))


def test_gy_data_requirement_compiler_audit_rejects_lost_claim_bindability_facet() -> None:
    validator = _validator()
    audit = _load_audit()
    contract = audit["probes"]["data_requirement_contract"]
    contract["mandatory_facets"] = [
        facet for facet in contract["mandatory_facets"] if facet != "claim_bindability_refs"
    ]

    assert "mandatory_facets_drift" in _codes(validator.validate(audit))


def test_gy_data_requirement_compiler_audit_rejects_fetch_executor_gate_claim() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["normal_fetch_execute_enforces_data_requirement_binding"] = True
    audit["probes"]["fetch_route_absence_probe"] = copy.deepcopy(
        audit["probes"]["fetch_route_absence_probe"]
    )
    audit["probes"]["fetch_route_absence_probe"][
        "fetch_executor_references_data_requirement_or_source_contract_gate"
    ] = True
    row = _row(audit, "fetch.executor.admission_consumer")
    row["gap_labels"] = [
        label for label in row["gap_labels"] if label != "bridge_missing"
    ]

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "fetch_route_absence_drift" in codes
    assert "pinned_bridge_gap_missing" in codes


def test_gy_data_requirement_compiler_audit_rejects_agent_scope_drift() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["methodology"]["agents_used"] = True

    assert "agent_scope_drift" in _codes(validator.validate(audit))
