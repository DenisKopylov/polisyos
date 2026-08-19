#!/usr/bin/env python3
"""Validate the GY data-requirement compiler audit artifact.

This check protects the Task 0 finding that polisyos.data_requirement is a real
near-route compiler/audit surface, but not yet route-pinned into catalog
FetchPlan admission.

Usage:
    python3 tools/quality/validation/check_layer3_gy_data_requirement_compiler_audit.py [--json]
"""
from __future__ import annotations

from time import perf_counter as _timing_perf_counter

_TIMING_STARTED_AT = _timing_perf_counter()

import argparse
import json
from pathlib import Path
from typing import Any

from tools.lib.timing import run_timed_entrypoint

DEFAULT_AUDIT = (
    Path(__file__).resolve().parents[3]
    / "architecture"
    / "policy_design_case"
    / "layer3_gy_task0_audit"
    / "layer3_gy_data_requirement_compiler_audit.json"
)

REQUIRED_FACETS = {
    "source_contract_ref",
    "source_rights",
    "dictionary_ref",
    "schema_ref",
    "field_refs",
    "unit_refs",
    "geography_refs",
    "time_coverage_refs",
    "freshness_ref",
    "lineage_refs",
    "transformation_refs",
    "quality_assertion_refs",
    "missingness_refs",
    "outlier_refs",
    "construct_validity_refs",
    "claim_bindability_refs",
}

REQUIRED_PREDICATES = {
    "source_family_matches_compiled_requirement",
    "source_contract_active",
    "observation_time_covers_claim_time",
    "lineage_preserves_required_transformations",
    "missingness_within_tolerance",
    "quality_minima_satisfied",
    "claim_bindability_refs_present",
}

REQUIRED_ROUTE_ROWS = {
    "data_requirement.public_api",
    "data_requirement.typed_contracts",
    "data_requirement.compiler.producer",
    "data_requirement.governed_family_projection_rows",
    "data_requirement.audit_and_persistence_surface",
    "runtime_quality.scenario_evidence_contract.consumer",
    "runtime_quality.production_data_contract_index.consumer",
    "fabric.data_requirement_adapter.consumer",
    "runtime_quality.producer_pipeline.consumer",
    "fabric.source_selection_audit.surface",
    "retrieval.catalog_binding_to_fetch_plan.absent_data_requirement_bridge",
    "core.contracts.FetchPlan.contract_absence",
    "fetch.executor.admission_consumer",
    "gy_engine_census.coverage",
}

PINNED_ABSENCE_ROWS = {
    "retrieval.catalog_binding_to_fetch_plan.absent_data_requirement_bridge",
    "core.contracts.FetchPlan.contract_absence",
    "fetch.executor.admission_consumer",
}

ALLOWED_GAP_LABELS = {
    "artifact_missing",
    "bridge_missing",
    "consumer_missing",
    "implemented_but_not_orchestrated",
    "surface_missing",
    "verification_missing",
}


def _nested(mapping: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = mapping
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _row_map(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = audit.get("route_rows")
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        route_id = row.get("route_id")
        if isinstance(route_id, str) and route_id:
            out[route_id] = row
    return out


def _labels(row: dict[str, Any]) -> set[str]:
    labels = row.get("gap_labels")
    return set(labels) if isinstance(labels, list) else set()


def validate(audit: dict[str, Any]) -> list[dict[str, Any]]:
    """Return audit integrity violations."""
    violations: list[dict[str, Any]] = []
    if audit.get("schema_version") != "layer3_gy_data_requirement_compiler_audit.v1":
        violations.append({
            "code": "bad_schema_version",
            "detail": audit.get("schema_version"),
        })

    methodology = audit.get("methodology")
    if not isinstance(methodology, dict):
        violations.append({"code": "missing_methodology", "detail": "methodology missing"})
        methodology = {}
    if methodology.get("network_fetches_run") is not False:
        violations.append({
            "code": "network_scope_laundering",
            "detail": "audit must not imply live connector fetch coverage",
        })
    if methodology.get("agents_used") is not False:
        violations.append({
            "code": "agent_scope_drift",
            "detail": "user requested independent audit without agents",
        })

    classification = audit.get("classification")
    if not isinstance(classification, dict):
        violations.append({"code": "missing_classification", "detail": "classification missing"})
        classification = {}
    expected_classification = {
        "primary": "near_route",
        "route_pinned": False,
        "near_route": True,
        "built_not_wired": False,
        "out_of_route": False,
        "secondary_capability_state": (
            "implemented_but_not_orchestrated_to_pinned_fetch_admission"
        ),
    }
    for key, expected in expected_classification.items():
        if classification.get(key) != expected:
            violations.append({
                "code": "classification_drift",
                "detail": f"{key}={classification.get(key)!r}; expected {expected!r}",
            })

    summary = audit.get("summary")
    if not isinstance(summary, dict):
        violations.append({"code": "missing_summary", "detail": "summary missing"})
        summary = {}

    expected_summary = {
        "classification": "near_route",
        "route_pinned": False,
        "near_route": True,
        "built_not_wired": False,
        "out_of_route": False,
        "compiler_public_surface_present": True,
        "typed_contracts_present": True,
        "compiler_producer_present": True,
        "audit_surface_present": True,
        "deterministic_writer_present": True,
        "fabric_adapter_consumes_specs": True,
        "production_data_contract_index_consumes_specs": True,
        "producer_pipeline_consumes_specs": True,
        "source_selection_audit_can_surface_binding_failures": True,
        "compiler_default_public_wrapper_emits_specs_for_pinned_scenario": False,
        "scenario_contract_surfaces_compiled_specs_for_pinned_scenario": False,
        "scenario_contract_legacy_projection_present": True,
        "g1_release_backed_mapped_compile_emits_specs": True,
        "g1_release_backed_unmapped_credit_access_emits_specs": False,
        "normal_fetch_plan_consumes_data_requirement_specs": False,
        "normal_fetch_plan_carries_source_contract_binding_status": False,
        "normal_fetch_execute_enforces_data_requirement_binding": False,
        "gy_engine_census_contains_data_requirement_compiler": False,
        "mandatory_facet_count": 16,
        "admissibility_predicate_count": 7,
        "mapped_g1_spec_count": 9,
        "default_public_scenario_spec_count": 0,
        "scenario_contract_data_requirement_spec_count": 0,
        "census_data_requirement_row_count": 0,
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            violations.append({
                "code": "summary_semantics_drift",
                "detail": f"{key}={summary.get(key)!r}; expected {expected!r}",
            })

    statuses = set(summary.get("mapped_g1_binding_statuses") or [])
    if statuses != {"blocked_construct_not_observed"}:
        violations.append({
            "code": "mapped_g1_status_drift",
            "detail": sorted(statuses),
        })

    facets = set(_nested(audit, ("probes", "data_requirement_contract", "mandatory_facets")) or [])
    if facets != REQUIRED_FACETS:
        violations.append({
            "code": "mandatory_facets_drift",
            "detail": sorted(facets),
        })

    predicates = set(
        _nested(audit, ("probes", "data_requirement_contract", "admissibility_predicates"))
        or []
    )
    if predicates != REQUIRED_PREDICATES:
        violations.append({
            "code": "admissibility_predicates_drift",
            "detail": sorted(predicates),
        })

    default_probe = _nested(audit, ("probes", "default_public_scenario_compile"))
    if not isinstance(default_probe, dict):
        violations.append({"code": "missing_default_compile_probe", "detail": "probe missing"})
        default_probe = {}
    if default_probe.get("spec_count") != 0 or default_probe.get("resolver_injected") is not False:
        violations.append({
            "code": "default_compile_probe_greenwash",
            "detail": default_probe,
        })

    scenario_probe = _nested(audit, ("probes", "scenario_evidence_contract_probe"))
    if not isinstance(scenario_probe, dict):
        violations.append({"code": "missing_scenario_contract_probe", "detail": "probe missing"})
        scenario_probe = {}
    if scenario_probe.get("data_requirement_specs_count") != 0:
        violations.append({
            "code": "scenario_contract_specs_greenwash",
            "detail": scenario_probe.get("data_requirement_specs_count"),
        })

    fetch_probe = _nested(audit, ("probes", "fetch_route_absence_probe"))
    if not isinstance(fetch_probe, dict):
        violations.append({"code": "missing_fetch_route_probe", "detail": "probe missing"})
        fetch_probe = {}
    fetch_expectations = {
        "fetch_plan_schema_has_typed_data_requirement_fields": False,
        "fetch_plan_metadata_is_untyped_escape_hatch": True,
        "retrieval_service_references_data_requirement": False,
        "fetch_executor_references_data_requirement_or_source_contract_gate": False,
    }
    for key, expected in fetch_expectations.items():
        if fetch_probe.get(key) != expected:
            violations.append({
                "code": "fetch_route_absence_drift",
                "detail": f"{key}={fetch_probe.get(key)!r}; expected {expected!r}",
            })

    rows = _row_map(audit)
    missing_rows = REQUIRED_ROUTE_ROWS - set(rows)
    for route_id in sorted(missing_rows):
        violations.append({"code": "missing_required_route_row", "detail": route_id})

    for route_id in PINNED_ABSENCE_ROWS:
        row = rows.get(route_id)
        if row is None:
            continue
        if row.get("reaches_pinned_fetch_admission") is not True:
            violations.append({
                "code": "pinned_absence_row_not_on_route",
                "detail": route_id,
            })
        labels = _labels(row)
        if "bridge_missing" not in labels:
            violations.append({
                "code": "pinned_bridge_gap_missing",
                "detail": route_id,
            })

    census_row = rows.get("gy_engine_census.coverage")
    if census_row is not None and "verification_missing" not in _labels(census_row):
        violations.append({
            "code": "census_verification_gap_missing",
            "detail": census_row.get("gap_labels"),
        })

    for row in rows.values():
        labels = _labels(row)
        unknown = labels - ALLOWED_GAP_LABELS
        if unknown:
            violations.append({
                "code": "unknown_gap_label",
                "detail": sorted(unknown),
            })

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    violations = validate(audit)
    if args.json:
        print(json.dumps({"status": "pass" if not violations else "fail", "violations": violations}, indent=2, sort_keys=True))
    elif violations:
        for violation in violations:
            print(f"{violation['code']}: {violation.get('detail', '')}")
    else:
        print("PASS layer3 GY data-requirement compiler audit")
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
