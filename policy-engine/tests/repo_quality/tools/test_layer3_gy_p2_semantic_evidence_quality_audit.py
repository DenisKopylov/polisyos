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
    / "layer3_gy_p2_semantic_evidence_quality_audit.json"
)


def _validator() -> Any:
    return import_module(
        "tools.quality.validation.check_layer3_gy_p2_semantic_evidence_quality_audit"
    )


def _load_audit() -> dict[str, Any]:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def _codes(violations: list[dict[str, Any]]) -> set[str]:
    return {str(item["code"]) for item in violations}


def _catalog_case(audit: dict[str, Any], case_id: str) -> dict[str, Any]:
    for row in audit["catalog_semantic_adequacy"]["silver_benchmark"]["cases"]:
        if row.get("case_id") == case_id:
            return row
    raise AssertionError(f"missing case {case_id}")


def _metric_row(audit: dict[str, Any], query: str) -> dict[str, Any]:
    for row in audit["catalog_semantic_adequacy"]["metric_binding_comparison"]:
        if row.get("query") == query:
            return row
    raise AssertionError(f"missing metric row {query}")


def _negative(audit: dict[str, Any], negative_id: str) -> dict[str, Any]:
    for row in audit["negative_assertions"]:
        if row.get("id") == negative_id:
            return row
    raise AssertionError(f"missing negative assertion {negative_id}")


def test_gy_p2_semantic_evidence_quality_validator_passes_current_artifact() -> None:
    validator = _validator()

    assert validator.validate(_load_audit()) == []


def test_gy_p2_semantic_evidence_quality_rejects_catalog_precision_greenwash() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["catalog_route_admissible_precision_at_5_micro"] = 0.8
    aggregate = audit["catalog_semantic_adequacy"]["silver_benchmark"]["aggregate"]
    aggregate["route_admissible_precision_at_5_micro"] = 0.8
    _catalog_case(audit, "ua_msme_credit")["route_admissible_precision_at_5"] = 0.4

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "catalog_route_precision_greenwash" in codes
    assert "catalog_case_precision_drift" in codes


def test_gy_p2_semantic_evidence_quality_rejects_country_filter_greenwash() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["catalog_country_filter_zero_result_cases"] = 0
    aggregate = audit["catalog_semantic_adequacy"]["silver_benchmark"]["aggregate"]
    aggregate["country_filter_zero_result_cases"] = 0
    _catalog_case(audit, "pl_energy_affordability")["country_filter_returned"] = 3

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "catalog_country_filter_drift" in codes
    assert "catalog_case_country_filter_greenwash" in codes


def test_gy_p2_semantic_evidence_quality_rejects_metric_binding_greenwash() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["catalog_metric_binding_zero_result_queries"] = []
    firm_survival = _metric_row(audit, "firm survival")
    firm_survival["returned"] = 4
    firm_survival["top_metric_ids"] = ["firm_survival"]

    codes = _codes(validator.validate(audit))
    assert "metric_zero_result_query_drift" in codes
    assert "metric_binding_count_drift" in codes


def test_gy_p2_semantic_evidence_quality_rejects_scholar_web_bundle_laundering() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["g2_guard_rejects_web_bundle_as_l2_skg"] = False
    web_path = audit["scholar_openalex_knowledge_toolkit"]["web_evidence_runtime_path"]
    web_path["classification"] = "canonical_l2_skg_authority"
    _negative(audit, "do_not_count_web_evidence_bundle_as_l2_skg")[
        "assertion_holds"
    ] = False

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "web_evidence_boundary_drift" in codes
    assert "negative_assertion_not_enforced" in codes


def test_gy_p2_semantic_evidence_quality_rejects_knowledge_toolkit_greenwash() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["knowledge_toolkit_adapter_tools_registered_with_empty_toolkit"] = 20
    audit["summary"]["knowledge_toolkit_all_expected_methods_registered"] = True
    toolkit = audit["scholar_openalex_knowledge_toolkit"]["knowledge_toolkit_probe"]
    toolkit["registered_count"] = 20
    toolkit["missing_registered_count"] = 0
    toolkit["classification"] = "implemented"

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "knowledge_toolkit_registry_count_drift" in codes
    assert "knowledge_toolkit_classification_drift" in codes


def test_gy_p2_semantic_evidence_quality_rejects_missing_acceptance_signal() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["acceptance_signal_for_future_repairs"] = [
        item
        for item in audit["acceptance_signal_for_future_repairs"]
        if "SKGQuery" not in item
    ]

    assert "missing_acceptance_signal" in _codes(validator.validate(audit))
