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
    / "layer3_gy_lex_frontier_root_cause_audit.json"
)


def _validator() -> Any:
    return import_module(
        "tools.quality.validation.check_layer3_gy_lex_frontier_root_cause_audit"
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


def test_gy_lex_frontier_root_cause_audit_validator_passes_current_artifact() -> None:
    validator = _validator()

    assert validator.validate(_load_audit()) == []


def test_gy_lex_frontier_root_cause_audit_rejects_bad_upstream_bounds_claim() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["classification"]["primary"] = "bad_bounds"
    audit["classification"]["root_cause_matrix"]["bug"]["primary"] = False
    audit["classification"]["root_cause_matrix"]["bad_bounds"]["primary"] = True
    audit["summary"]["bad_upstream_bounds_observed"] = True
    audit["summary"]["optional_bound_bug_primary"] = False
    audit["probes"]["persisted_trinity_bundle"]["parameter"]["min_value"] = "0.0"
    audit["probes"]["persisted_trinity_bundle"]["parameter"]["max_value"] = "0.0"

    codes = _codes(validator.validate(audit))
    assert "classification_drift" in codes
    assert "root_cause_matrix_drift" in codes
    assert "summary_semantics_drift" in codes
    assert "persisted_parameter_probe_drift" in codes


def test_gy_lex_frontier_root_cause_audit_rejects_frontier_greenwash() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["search_frontier_persisted"] = True
    audit["summary"]["policy_frontier_report_ref_present"] = True
    audit["probes"]["frontier_semantics"]["current_run_frontier_status"] = "persisted"
    row = _row(audit, "scientist.policy_frontier_report.persistence")
    row["execution_status"] = "works"

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "frontier_status_drift" in codes
    assert "frontier_row_greenwash" in codes


def test_gy_lex_frontier_root_cause_audit_rejects_laundering_observed_claim() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["classification"]["root_cause_matrix"]["frontier_objective_laundering"][
        "observed"
    ] = True
    audit["summary"]["frontier_laundering_observed"] = True
    audit["probes"]["frontier_semantics"][
        "current_run_laundering_status"
    ] = "observed"

    codes = _codes(validator.validate(audit))
    assert "root_cause_matrix_drift" in codes
    assert "summary_semantics_drift" in codes
    assert "frontier_laundering_greenwash" in codes


def test_gy_lex_frontier_root_cause_audit_rejects_lost_none_bounds_control() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["persisted_parameter_min_value_is_null"] = False
    audit["summary"]["persisted_parameter_max_value_is_null"] = False
    audit["summary"]["derived_bounds_if_none_preserved"] = [0.0, 0.0]
    direct = copy.deepcopy(audit["probes"]["direct_reproducer"]["observed_values"])
    direct["derived_bounds_from_current_builder"] = [0.08, 0.12]
    audit["probes"]["direct_reproducer"]["observed_values"] = direct

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "none_preserved_bounds_drift" in codes
    assert "direct_reproducer_drift" in codes


def test_gy_lex_frontier_root_cause_audit_rejects_missing_p25_guardrail() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["classification"]["patterns"] = [
        pattern for pattern in audit["classification"]["patterns"] if pattern != "P25"
    ]
    audit["probes"]["frontier_semantics"]["required_repair_acceptance"] = [
        item
        for item in audit["probes"]["frontier_semantics"]["required_repair_acceptance"]
        if "frontier reports must carry search space source" not in item
    ]

    codes = _codes(validator.validate(audit))
    assert "pattern_coverage_drift" in codes
    assert "missing_repair_acceptance_guardrail" in codes


def test_gy_lex_frontier_root_cause_audit_rejects_missing_root_row() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["route_rows"] = [
        row
        for row in audit["route_rows"]
        if row.get("route_id") != "scientist.policy_design.search.optional_bounds"
    ]

    assert "missing_required_route_row" in _codes(validator.validate(audit))


def test_gy_lex_frontier_root_cause_audit_rejects_agent_scope_drift() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["methodology"]["agents_used"] = True

    assert "agent_scope_drift" in _codes(validator.validate(audit))
