#!/usr/bin/env python3
"""Validate the GY generated/public lifecycle audit artifact.

This check protects the Task 0 finding that GY audit artifacts are real
evidence but are not yet registered as a generated/public surface family.

Usage:
    python3 tools/quality/validation/check_layer3_gy_generated_public_lifecycle_audit.py [--json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_AUDIT = (
    Path(__file__).resolve().parents[3]
    / "architecture"
    / "policy_design_case"
    / "layer3_gy_task0_audit"
    / "layer3_gy_generated_public_lifecycle_audit.json"
)

REQUIRED_PATTERNS = {"P01", "P03", "P05", "P07", "P10", "P13", "P15", "P25"}
REQUIRED_NEGATIVES = {
    "do_not_count_gx_validator_as_gy_lifecycle_registration",
    "do_not_count_public_surface_contract_as_json_artifact_registry",
    "do_not_count_projection_refs_as_api_dashboard_enforcement",
    "do_not_count_individual_gy_validators_as_family_stale_policy",
    "do_not_publish_gy_audit_outputs_without_explicit_authority_boundary",
}
REQUIRED_ROWS = {
    "layer3_g1_to_g8_and_gl",
    "layer3_gx_hardening",
    "layer3_gy_task0_audit_artifacts",
    "runtime_openapi_snapshot",
    "runtime_api_client",
    "runtime_dashboard_api_types",
    "public_surface_inventory",
    "policy_design_case_inventory",
}
REQUIRED_SURFACES = {
    "policy_design_case_generated_audit_surfaces_section",
    "layer3_public_export_projection_refs",
    "runtime_api_dashboard_public_export_routes",
}
REQUIRED_ACCEPTANCE_PHRASES = {
    "generated-artifacts family row",
    "stale_output_behavior",
    "unregistered new layer3_gy* files",
    "may_not_use_for/candidate_only/not_publishable",
    "Projection-only refs",
}


def _rows_by_id(rows: object, key: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get(key), str):
            out[str(row[key])] = row
    return out


def _list_value(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _expected_file_sets() -> dict[str, list[str]]:
    repo_root = Path(__file__).resolve().parents[3]
    return {
        "paths": sorted(
            path.relative_to(repo_root).as_posix()
            for path in (
                repo_root
                / "architecture"
                / "policy_design_case"
                / "layer3_gy_task0_audit"
            ).glob("layer3_gy*")
            if path.is_file()
        ),
        "validators": sorted(
            path.relative_to(repo_root).as_posix()
            for path in (repo_root / "tools" / "quality" / "validation").glob(
                "check_layer3_gy*.py"
            )
            if path.is_file()
        ),
        "validator_tests": sorted(
            path.relative_to(repo_root).as_posix()
            for path in (repo_root / "tests" / "repo_quality" / "tools").glob(
                "test_layer3_gy*.py"
            )
            if path.is_file()
        ),
    }


def validate(audit: dict[str, Any]) -> list[dict[str, Any]]:
    """Return audit integrity violations."""
    violations: list[dict[str, Any]] = []

    if audit.get("schema_version") != "layer3_gy_generated_public_lifecycle_audit.v1":
        violations.append({"code": "bad_schema_version", "detail": audit.get("schema_version")})

    methodology = audit.get("methodology")
    if not isinstance(methodology, dict):
        violations.append({"code": "missing_methodology", "detail": "methodology missing"})
        methodology = {}
    expected_methodology = {
        "agents_used": False,
        "network_fetches_run": False,
        "runtime_server_started": False,
        "parsed_generated_artifacts_toml": True,
        "parsed_public_surface_contract": True,
        "parsed_public_surface_markdown": True,
        "parsed_policy_design_case_inventory": True,
        "parsed_runtime_openapi_snapshot": True,
        "filesystem_gy_artifact_inventory": True,
        "runtime_route_execution_reused_from_runtime_surface_audit": True,
    }
    for key, expected in expected_methodology.items():
        if methodology.get(key) != expected:
            violations.append({
                "code": "methodology_drift",
                "detail": f"{key}={methodology.get(key)!r}; expected {expected!r}",
            })
    if methodology.get("probe_type") != "source_registry_static_audit":
        violations.append({"code": "probe_type_drift", "detail": methodology.get("probe_type")})

    classification = audit.get("classification")
    if not isinstance(classification, dict):
        violations.append({"code": "missing_classification", "detail": "classification missing"})
        classification = {}
    expected_classification = {
        "primary": "registered_core_layer3_generated_families_but_gy_task0_family_unregistered",
        "gap_class": "partial",
        "capability_label": (
            "layer3_core_and_gx_lifecycle_registered_but_gy_task0_audit_artifacts_surface_missing"
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
    patterns = set(_list_value(classification.get("patterns")))
    if not patterns >= REQUIRED_PATTERNS:
        violations.append({"code": "pattern_coverage_drift", "detail": sorted(patterns)})

    summary = audit.get("summary")
    if not isinstance(summary, dict):
        violations.append({"code": "missing_summary", "detail": "summary missing"})
        summary = {}
    expected_summary = {
        "generated_artifact_family_count": 45,
        "registered_layer3_family_count": 10,
        "registered_layer3_output_count": 243,
        "gx_generated_family_registered": True,
        "gy_generated_family_registered": False,
        "gy_artifact_files_detected": 31,
        "gy_artifact_files_registered_count": 0,
        "gy_validators_detected": 15,
        "gy_validator_tests_detected": 14,
        "runtime_openapi_family_registered": True,
        "runtime_api_client_family_registered": True,
        "runtime_dashboard_api_types_family_registered": True,
        "public_surface_inventory_family_registered": True,
        "public_surface_registers_python_packages_not_json_artifact_families": True,
        "policy_design_case_inventory_artifact_count": 42,
        "policy_design_case_inventory_gy_entries": 0,
        "policy_design_case_inventory_registered_in_generated_artifacts": False,
        "policy_design_case_public_surface_section_hardcoded_in_renderer": True,
        "policy_design_case_public_surface_section_registered_surface_count": 6,
        "layer3_public_export_projection_ref_family_count": 7,
        "runtime_openapi_interesting_surface_route_count": 41,
        "openapi_policy_design_case_projection_has_authority_boundary_fields": True,
        "dashboard_validators_model_runtime_vs_projection_authority": True,
        "gy_public_api_dashboard_surface_registered": False,
        "overall_status": "gy_task0_audit_family_surface_missing",
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            violations.append({
                "code": "summary_semantics_drift",
                "detail": f"{key}={summary.get(key)!r}; expected {expected!r}",
            })

    rows = _rows_by_id(audit.get("lifecycle_matrix"), "row_id")
    missing_rows = sorted(REQUIRED_ROWS - set(rows))
    if missing_rows:
        violations.append({"code": "missing_lifecycle_rows", "detail": missing_rows})

    for row_id in (
        "layer3_g1_to_g8_and_gl",
        "layer3_gx_hardening",
        "runtime_openapi_snapshot",
        "runtime_api_client",
        "runtime_dashboard_api_types",
        "public_surface_inventory",
    ):
        row = rows.get(row_id, {})
        if row.get("registered") is not True:
            violations.append({"code": "registered_family_marked_unregistered", "detail": row_id})
        for field in ("source_of_truth", "verifier", "stale_output_behavior"):
            if not str(row.get(field, "")).strip() or row.get(field) == "missing_registry":
                violations.append({
                    "code": "registered_family_missing_lifecycle_metadata",
                    "detail": f"{row_id}.{field}",
                })
        if int(row.get("outputs_registered_count") or 0) <= 0:
            violations.append({
                "code": "registered_family_missing_outputs",
                "detail": row_id,
            })

    gy_row = rows.get("layer3_gy_task0_audit_artifacts", {})
    if gy_row.get("registered") is not False:
        violations.append({"code": "gy_family_registration_greenwash", "detail": gy_row})
    if gy_row.get("family_id") is not None:
        violations.append({"code": "gy_family_id_greenwash", "detail": gy_row.get("family_id")})
    if gy_row.get("outputs_registered_count") != 0:
        violations.append({
            "code": "gy_registered_output_greenwash",
            "detail": gy_row.get("outputs_registered_count"),
        })
    if gy_row.get("stale_output_behavior") != "missing_registry":
        violations.append({
            "code": "gy_stale_policy_greenwash",
            "detail": gy_row.get("stale_output_behavior"),
        })
    if gy_row.get("public_api_surface") is not False or gy_row.get("dashboard_surface") is not False:
        violations.append({"code": "gy_surface_greenwash", "detail": gy_row})
    if "unregistered_audit_only" not in str(gy_row.get("authority_boundary_status", "")):
        violations.append({
            "code": "gy_authority_boundary_drift",
            "detail": gy_row.get("authority_boundary_status"),
        })

    pdc_row = rows.get("policy_design_case_inventory", {})
    if pdc_row.get("registered") is not False:
        violations.append({"code": "pdc_inventory_registration_greenwash", "detail": pdc_row})
    if pdc_row.get("contains_gy_entries") is not False:
        violations.append({"code": "pdc_inventory_gy_entry_greenwash", "detail": pdc_row})
    if pdc_row.get("artifact_count") != 42:
        violations.append({
            "code": "pdc_inventory_artifact_count_drift",
            "detail": pdc_row.get("artifact_count"),
        })

    public_row = rows.get("public_surface_inventory", {})
    if public_row.get("registers_json_artifact_families") is not False:
        violations.append({
            "code": "public_surface_artifact_registry_laundering",
            "detail": public_row.get("registers_json_artifact_families"),
        })

    surfaces = _rows_by_id(audit.get("public_surface_lifecycle"), "surface_id")
    missing_surfaces = sorted(REQUIRED_SURFACES - set(surfaces))
    if missing_surfaces:
        violations.append({"code": "missing_public_surface_rows", "detail": missing_surfaces})

    pdc_surface = surfaces.get("policy_design_case_generated_audit_surfaces_section", {})
    if pdc_surface.get("gy_surface_registered") is not False:
        violations.append({"code": "gy_public_surface_greenwash", "detail": pdc_surface})
    if pdc_surface.get("derivation_model") != (
        "hardcoded renderer prose, not derived from policy_design_case/inventory.json"
    ):
        violations.append({"code": "pdc_surface_derivation_drift", "detail": pdc_surface})

    projection_surface = surfaces.get("layer3_public_export_projection_refs", {})
    if projection_surface.get("api_dashboard_enforcement") is not False:
        violations.append({
            "code": "projection_refs_api_enforcement_laundering",
            "detail": projection_surface,
        })
    if projection_surface.get("public_export_route_registered") is not False:
        violations.append({
            "code": "projection_refs_public_export_laundering",
            "detail": projection_surface,
        })

    inventory = audit.get("gy_artifact_inventory")
    if not isinstance(inventory, dict):
        violations.append({"code": "missing_gy_artifact_inventory", "detail": "missing"})
        inventory = {}
    expected_files = _expected_file_sets()
    for key, expected in expected_files.items():
        actual = _list_value(inventory.get(key))
        if actual != expected:
            violations.append({
                "code": "gy_detected_artifact_list_drift",
                "detail": {"key": key, "actual": actual, "expected": expected},
            })
    if inventory.get("registered_output_count") != 0:
        violations.append({
            "code": "gy_inventory_registered_output_greenwash",
            "detail": inventory.get("registered_output_count"),
        })

    negatives = _rows_by_id(audit.get("negative_assertions"), "id")
    missing_negatives = sorted(REQUIRED_NEGATIVES - set(negatives))
    if missing_negatives:
        violations.append({"code": "missing_negative_assertions", "detail": missing_negatives})
    for negative_id in REQUIRED_NEGATIVES & set(negatives):
        if negatives[negative_id].get("assertion_holds") is not True:
            violations.append({
                "code": "negative_assertion_not_enforced",
                "detail": negative_id,
            })

    acceptance = _list_value(audit.get("acceptance_signal"))
    acceptance_text = "\n".join(acceptance)
    for phrase in REQUIRED_ACCEPTANCE_PHRASES:
        if phrase not in acceptance_text:
            violations.append({"code": "missing_acceptance_guardrail", "detail": phrase})

    return violations


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    violations = validate(_load(args.audit))
    report = {
        "status": "pass" if not violations else "fail",
        "violation_count": len(violations),
        "violations": violations,
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif violations:
        print("FAIL layer3_gy_generated_public_lifecycle_audit")
        for violation in violations:
            print(f"- {violation['code']}: {violation['detail']}")
    else:
        print("PASS layer3_gy_generated_public_lifecycle_audit")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
