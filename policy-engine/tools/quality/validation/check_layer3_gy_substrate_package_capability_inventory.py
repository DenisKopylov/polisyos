#!/usr/bin/env python3
"""Validate the GY substrate package capability inventory.

This check protects the Task 0 finding that large substrate packages are real
capability surfaces, but mostly not GY-censused pinned-route authority.

Usage:
    python3 tools/quality/validation/check_layer3_gy_substrate_package_capability_inventory.py [--json]
"""
from __future__ import annotations

from time import perf_counter as _timing_perf_counter

_TIMING_STARTED_AT = _timing_perf_counter()

import argparse
import json
from pathlib import Path
from typing import Any

from tools.lib.timing import run_timed_entrypoint

DEFAULT_INVENTORY = (
    Path(__file__).resolve().parents[3]
    / "architecture"
    / "policy_design_case"
    / "layer3_gy_task0_audit"
    / "layer3_gy_substrate_package_capability_inventory.json"
)

REQUIRED_PACKAGES = {
    "polisyos.core",
    "polisyos.ir",
    "polisyos.evidence",
    "polisyos.berl",
    "polisyos.calibration",
    "polisyos.ddm",
    "polisyos.data_requirement",
    "polisyos.method_requirement",
    "polisyos.participation_requirement",
    "polisyos.obligation_rules",
    "polisyos.obligation_graph",
}

REQUIRED_PATTERNS = {
    "P01",
    "P02",
    "P03",
    "P05",
    "P07",
    "P10",
    "P13",
    "P14",
    "P15",
    "P20",
    "P21",
    "P22",
    "P25",
}

REQUIRED_NEGATIVES = {
    "do_not_count_zero_gy_rows_as_zero_capability",
    "do_not_count_core_ir_substrate_as_policy_claim_authority",
    "do_not_count_data_requirement_compiler_as_fetch_admission",
    "do_not_count_evidence_conflict_or_raw_count_as_positive_support",
    "do_not_count_berl_display_policy_as_recommendation_authority",
    "do_not_count_ddm_monitoring_as_gy_pinned_route_execution",
    "do_not_count_llm_or_candidate_rules_as_governed_obligations",
    "do_not_count_participation_llm_speculation_as_participation_evidence",
}

REQUIRED_ACCEPTANCE_PHRASES = {
    "All 11 substrate packages are classified",
    "0 GY census rows",
    "data_requirement remains surface_missing/bridge_missing",
    "evidence conflict/effective-independence records cannot be counted",
    "cannot be upgraded to GY route authority",
}


def _rows_by_module(value: object) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("module"), str):
            rows[item["module"]] = item
    return rows


def _list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _labels(row: dict[str, Any]) -> set[str]:
    return set(_list(row.get("missing_labels")))


def _authority_text(row: dict[str, Any]) -> str:
    return str(row.get("authority_boundary_summary") or "").casefold()


def _sum(rows: dict[str, dict[str, Any]], key: str) -> int:
    total = 0
    for module, row in rows.items():
        value = row.get(key)
        if not isinstance(value, int):
            raise TypeError(f"{module}.{key} is not an int")
        total += value
    return total


def validate(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    """Return inventory integrity violations."""
    violations: list[dict[str, Any]] = []

    if inventory.get("schema_version") != "layer3_gy_substrate_package_capability_inventory.v1":
        violations.append({
            "code": "bad_schema_version",
            "detail": inventory.get("schema_version"),
        })

    methodology = inventory.get("methodology")
    if not isinstance(methodology, dict):
        violations.append({"code": "missing_methodology", "detail": "methodology missing"})
        methodology = {}
    expected_methodology = {
        "agents_used": False,
        "network_fetches_run": False,
        "runtime_server_started": False,
        "parsed_failure_register": True,
        "parsed_public_surface_contract": True,
        "parsed_package_contracts": True,
        "parsed_package_readmes": True,
        "ast_inventory": True,
        "cross_package_import_inventory": True,
        "gy_engine_census_reference_scan": True,
        "runtime_execution": False,
    }
    for key, expected in expected_methodology.items():
        if methodology.get(key) != expected:
            violations.append({
                "code": "methodology_drift",
                "detail": f"{key}={methodology.get(key)!r}; expected {expected!r}",
            })
    if methodology.get("probe_type") != "source_static_package_capability_inventory":
        violations.append({"code": "probe_type_drift", "detail": methodology.get("probe_type")})

    classification = inventory.get("classification")
    if not isinstance(classification, dict):
        violations.append({"code": "missing_classification", "detail": "classification missing"})
        classification = {}
    expected_classification = {
        "primary": "substrate_packages_real_but_not_gy_censused_route_assets",
        "gap_class": "mixed",
        "capability_label": (
            "route_pinned_core_ir_plus_near_route_requirement_evidence_calibration_substrates_"
            "with_bridge_and_surface_gaps"
        ),
        "route_pinned": True,
        "repair_before_downstream_governance": True,
    }
    for key, expected in expected_classification.items():
        if classification.get(key) != expected:
            violations.append({
                "code": "classification_drift",
                "detail": f"{key}={classification.get(key)!r}; expected {expected!r}",
            })
    patterns = set(_list(classification.get("patterns")))
    if not patterns >= REQUIRED_PATTERNS:
        violations.append({"code": "pattern_coverage_drift", "detail": sorted(patterns)})

    summary = inventory.get("summary")
    if not isinstance(summary, dict):
        violations.append({"code": "missing_summary", "detail": "summary missing"})
        summary = {}
    expected_summary = {
        "packages_in_scope": 11,
        "public_stable_count": 2,
        "public_experimental_count": 2,
        "internal_count": 6,
        "public_surface_absent_count": 1,
        "package_contract_missing_count": 1,
        "total_python_files": 466,
        "total_root_facade_exports": 435,
        "total_classes": 2639,
        "total_top_level_functions": 2114,
        "gy_engine_census_rows_in_scope": 0,
        "route_pinned_substrate_count": 2,
        "near_route_package_count": 6,
        "broader_system_support_count": 2,
        "out_of_route_monitoring_count": 1,
        "data_requirement_public_surface_registered": False,
        "data_requirement_package_contract_registered": False,
        "overall_status": "package_capabilities_real_but_not_pinned_route_authority",
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            violations.append({
                "code": "summary_semantics_drift",
                "detail": f"{key}={summary.get(key)!r}; expected {expected!r}",
            })

    rows = _rows_by_module(inventory.get("package_inventory"))
    missing = sorted(REQUIRED_PACKAGES - set(rows))
    extra = sorted(set(rows) - REQUIRED_PACKAGES)
    if missing:
        violations.append({"code": "missing_package_rows", "detail": missing})
    if extra:
        violations.append({"code": "unexpected_package_rows", "detail": extra})

    if rows:
        try:
            count_checks = {
                "total_python_files": _sum(rows, "python_files"),
                "total_root_facade_exports": _sum(rows, "root_facade_exports"),
                "total_classes": _sum(rows, "classes"),
                "total_top_level_functions": _sum(rows, "top_level_functions"),
                "gy_engine_census_rows_in_scope": _sum(rows, "gy_engine_census_row_count"),
            }
        except TypeError as exc:
            violations.append({"code": "row_count_type_error", "detail": str(exc)})
            count_checks = {}
        for key, actual in count_checks.items():
            if summary.get(key) != actual:
                violations.append({
                    "code": "summary_row_count_mismatch",
                    "detail": f"{key}={summary.get(key)!r}; row sum {actual!r}",
                })

    for module, row in rows.items():
        for key in (
            "package_contract_registered",
            "public_surface_registered",
            "public_surface_classification",
            "primary_contracts",
            "producers",
            "persisted_artifacts_or_events",
            "consumers",
            "verification",
            "public_or_audit_surface",
            "route_participation",
            "capability_state",
            "missing_labels",
            "authority_boundary_summary",
            "evidence_refs",
        ):
            if key not in row:
                violations.append({
                    "code": "package_row_missing_field",
                    "detail": f"{module}.{key}",
                })
        if not _list(row.get("primary_contracts")):
            violations.append({"code": "package_missing_contracts", "detail": module})
        if not _list(row.get("producers")):
            violations.append({"code": "package_missing_producers", "detail": module})
        if not _list(row.get("consumers")):
            violations.append({"code": "package_missing_consumers", "detail": module})
        if not _list(row.get("verification")):
            violations.append({"code": "package_missing_verification", "detail": module})
        if not str(row.get("authority_boundary_summary") or "").strip():
            violations.append({"code": "package_missing_authority_boundary", "detail": module})

    core = rows.get("polisyos.core", {})
    ir = rows.get("polisyos.ir", {})
    for module, row in (("polisyos.core", core), ("polisyos.ir", ir)):
        if row.get("route_participation") not in {
            "route_pinned_substrate",
            "route_pinned_contract_substrate",
        }:
            violations.append({"code": "core_ir_route_classification_drift", "detail": module})
        if "claim authority" in _authority_text(row) and "may not" not in _authority_text(row):
            violations.append({"code": "core_ir_authority_laundering", "detail": module})
        if row.get("public_surface_classification") != "public_stable":
            violations.append({"code": "core_ir_public_surface_drift", "detail": module})

    data_requirement = rows.get("polisyos.data_requirement", {})
    if data_requirement:
        if data_requirement.get("package_contract_registered") is not False:
            violations.append({
                "code": "data_requirement_package_contract_greenwash",
                "detail": data_requirement.get("package_contract_registered"),
            })
        if data_requirement.get("public_surface_registered") is not False:
            violations.append({
                "code": "data_requirement_public_surface_greenwash",
                "detail": data_requirement.get("public_surface_registered"),
            })
        required_labels = {"bridge_missing", "implemented_but_not_orchestrated", "surface_missing"}
        if not _labels(data_requirement) >= required_labels:
            violations.append({
                "code": "data_requirement_missing_label_drift",
                "detail": sorted(_labels(data_requirement)),
            })
        if data_requirement.get("route_participation") != "near_route_fetch_admission_bridge":
            violations.append({
                "code": "data_requirement_route_classification_drift",
                "detail": data_requirement.get("route_participation"),
            })
        if "fetchexecutor already consumes" in _authority_text(data_requirement):
            violations.append({
                "code": "data_requirement_fetch_admission_greenwash",
                "detail": data_requirement.get("authority_boundary_summary"),
            })

    evidence = rows.get("polisyos.evidence", {})
    if evidence:
        if not _labels(evidence) >= {"bridge_missing", "surface_missing", "semantic_test_missing"}:
            violations.append({
                "code": "evidence_missing_label_drift",
                "detail": sorted(_labels(evidence)),
            })
        boundary = _authority_text(evidence)
        if "support strength" not in boundary or "may not" not in boundary:
            violations.append({
                "code": "evidence_support_authority_greenwash",
                "detail": evidence.get("authority_boundary_summary"),
            })

    berl = rows.get("polisyos.berl", {})
    if berl:
        if berl.get("route_participation") == "route_pinned_substrate":
            violations.append({
                "code": "berl_route_greenwash",
                "detail": berl.get("route_participation"),
            })
        if "recommendation" not in _authority_text(berl):
            violations.append({
                "code": "berl_authority_boundary_drift",
                "detail": berl.get("authority_boundary_summary"),
            })

    calibration = rows.get("polisyos.calibration", {})
    if calibration:
        if "bridge_missing" not in _labels(calibration):
            violations.append({
                "code": "calibration_bridge_gap_erased",
                "detail": sorted(_labels(calibration)),
            })
        if "route consumer" not in _authority_text(calibration):
            violations.append({
                "code": "calibration_authority_boundary_drift",
                "detail": calibration.get("authority_boundary_summary"),
            })

    ddm = rows.get("polisyos.ddm", {})
    if ddm:
        if ddm.get("route_participation") != "out_of_route_production_monitoring":
            violations.append({
                "code": "ddm_route_greenwash",
                "detail": ddm.get("route_participation"),
            })
        if "surface_out_of_scope" not in _labels(ddm):
            violations.append({
                "code": "ddm_surface_scope_drift",
                "detail": sorted(_labels(ddm)),
            })

    participation = rows.get("polisyos.participation_requirement", {})
    if participation and "llm speculation" not in _authority_text(participation):
        violations.append({
            "code": "participation_llm_boundary_drift",
            "detail": participation.get("authority_boundary_summary"),
        })

    obligation_rules = rows.get("polisyos.obligation_rules", {})
    if obligation_rules and "rulegovernancedecision" not in _authority_text(obligation_rules):
        violations.append({
            "code": "obligation_rules_governance_boundary_drift",
            "detail": obligation_rules.get("authority_boundary_summary"),
        })

    obligation_graph = rows.get("polisyos.obligation_graph", {})
    if obligation_graph:
        boundary = _authority_text(obligation_graph)
        for phrase in ("legal authority", "method validity", "projection authority"):
            if phrase not in boundary:
                violations.append({
                    "code": "obligation_graph_authority_boundary_drift",
                    "detail": phrase,
                })

    negatives = inventory.get("negative_assertions")
    if not isinstance(negatives, list):
        violations.append({"code": "missing_negative_assertions", "detail": "missing"})
        negatives = []
    negative_ids = {
        str(item.get("id"))
        for item in negatives
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    missing_negatives = sorted(REQUIRED_NEGATIVES - negative_ids)
    if missing_negatives:
        violations.append({"code": "missing_negative_assertions", "detail": missing_negatives})
    for item in negatives:
        if not isinstance(item, dict):
            continue
        if item.get("assertion_holds") is not True:
            violations.append({
                "code": "negative_assertion_not_enforced",
                "detail": item.get("id"),
            })

    acceptance = "\n".join(_list(inventory.get("acceptance_signal")))
    for phrase in REQUIRED_ACCEPTANCE_PHRASES:
        if phrase not in acceptance:
            violations.append({"code": "missing_acceptance_guardrail", "detail": phrase})

    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Emit JSON result.")
    parser.add_argument(
        "--inventory",
        type=Path,
        default=DEFAULT_INVENTORY,
        help="Path to substrate package capability inventory JSON.",
    )
    args = parser.parse_args()

    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    violations = validate(inventory)
    result = {
        "status": "pass" if not violations else "fail",
        "issue_count": len(violations),
        "issues": violations,
        "inventory": str(args.inventory),
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif violations:
        for violation in violations:
            print(f"{violation['code']}: {violation['detail']}")
    else:
        print("PASS: GY substrate package capability inventory is internally consistent.")
    return 0 if not violations else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(
        run_timed_entrypoint(
            main,
            script_path=__file__,
            argv=sys.argv[1:],
            started_perf_counter=_TIMING_STARTED_AT,
        )
    )
