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
    / "layer3_gy_connector_family_truth_audit.json"
)


def _validator() -> Any:
    return import_module(
        "tools.quality.validation.check_layer3_gy_connector_family_truth_audit"
    )


def _load_audit() -> dict[str, Any]:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def _codes(violations: list[dict[str, Any]]) -> set[str]:
    return {str(item["code"]) for item in violations}


def _row(audit: dict[str, Any], connector_id: str) -> dict[str, Any]:
    for item in audit["connector_rows"]:
        if item.get("connector_id") == connector_id:
            return item
    raise AssertionError(f"missing connector row {connector_id}")


def _check(row: dict[str, Any], check_id: str) -> dict[str, Any]:
    for item in row["shape_checks"]:
        if item.get("id") == check_id:
            return item
    raise AssertionError(f"missing shape check {check_id}")


def test_gy_connector_family_truth_audit_validator_passes_current_artifact() -> None:
    validator = _validator()

    assert validator.validate(_load_audit()) == []


def test_gy_connector_family_truth_audit_rejects_missing_connector_row() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["connector_rows"] = [
        row for row in audit["connector_rows"] if row.get("connector_id") != "rest.json"
    ]

    assert "missing_connector_row" in _codes(validator.validate(audit))


def test_gy_connector_family_truth_audit_rejects_all_greenwash() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["shape_status_counts"] = {"shape_pass": 12}
    audit["summary"]["families_with_blocking_shape_gaps"] = []
    audit["summary"]["families_warn_only"] = []
    audit["summary"]["blocking_gap_count"] = 0
    audit["summary"]["warn_gap_count"] = 0
    for row in audit["connector_rows"]:
        row["shape_status"] = "shape_pass"

    codes = _codes(validator.validate(audit))
    assert "shape_status_counts_drift" in codes
    assert "blocking_family_set_drift" in codes
    assert "required_connector_status_changed" in codes


def test_gy_connector_family_truth_audit_rejects_rest_endpoint_gap_removed() -> None:
    validator = _validator()
    audit = _load_audit()
    rest = _row(audit, "rest.json")
    rest["shape_checks"] = copy.deepcopy(rest["shape_checks"])
    _check(rest, "request_dataset_id_controls_endpoint")["status"] = "pass"

    assert "rest_endpoint_contract_gap_missing" in _codes(validator.validate(audit))


def test_gy_connector_family_truth_audit_rejects_unpd_required_filter_gap_removed() -> None:
    validator = _validator()
    audit = _load_audit()
    unpd = _row(audit, "unpd.data")
    unpd["shape_checks"] = copy.deepcopy(unpd["shape_checks"])
    _check(unpd, "location_filter_present")["status"] = "pass"
    _check(unpd, "time_filter_present")["status"] = "pass"

    assert "unpd_required_filter_gap_missing" in _codes(validator.validate(audit))


def test_gy_connector_family_truth_audit_rejects_ukons_catalog_tier_gap_removed() -> None:
    validator = _validator()
    audit = _load_audit()
    ukons = _row(audit, "ukons.datasets")
    ukons["shape_checks"] = copy.deepcopy(ukons["shape_checks"])
    _check(ukons, "binding_execution_tier_fetchable")["status"] = "pass"

    assert "ukons_catalog_tier_gap_missing" in _codes(validator.validate(audit))


def test_gy_connector_family_truth_audit_rejects_sdmx_warning_removed() -> None:
    validator = _validator()
    audit = _load_audit()
    sdmx = _row(audit, "sdmx.source")
    sdmx["shape_checks"] = copy.deepcopy(sdmx["shape_checks"])
    _check(sdmx, "dimension_key_bound")["status"] = "pass"

    assert "sdmx_dimension_warning_missing" in _codes(validator.validate(audit))


def test_gy_connector_family_truth_audit_rejects_network_scope_laundering() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["methodology"]["network_fetches_run"] = True

    assert "network_scope_laundering" in _codes(validator.validate(audit))
