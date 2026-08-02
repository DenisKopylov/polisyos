#!/usr/bin/env python3
"""Validate the GY source-contract admissibility audit artifact.

This check protects the Task 0 audit result that rights, freshness, field refs,
time coverage, and claim bindability do not currently reach catalog-derived
fetch admission, even though strict SourceContract gates exist elsewhere.

Usage:
    python3 tools/quality/validation/check_layer3_gy_source_contract_admissibility_audit.py [--json]
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
    / "layer3_gy_source_contract_admissibility_audit.json"
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

REQUIRED_ROUTE_ROWS = {
    "data_requirement.compiler.mandatory_facets",
    "production_catalog.raw_source_metadata",
    "catalog.metric_binding_contract",
    "retrieval.catalog_binding_to_fetch_plan",
    "fetch.executor.admission_consumer",
    "fabric.source_selection_audit.strict_gate",
    "fabric.data_requirement_adapter.strict_gate",
    "retrieval.catalog_freshness_policy",
}

ALLOWED_GAP_LABELS = {
    "artifact_missing",
    "bridge_missing",
    "consumer_missing",
    "implemented_but_not_orchestrated",
    "semantic_test_missing",
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


def validate(audit: dict[str, Any]) -> list[dict[str, Any]]:
    """Return audit integrity violations."""
    violations: list[dict[str, Any]] = []
    if audit.get("schema_version") != "layer3_gy_source_contract_admissibility_audit.v1":
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
            "detail": "pre-fetch admission audit must not claim network replay",
        })

    summary = audit.get("summary")
    if not isinstance(summary, dict):
        violations.append({"code": "missing_summary", "detail": "summary missing"})
        summary = {}

    expected_summary = {
        "route_verdict": "rights_freshness_source_contract_admissibility_missing_at_fetch_admission",
        "fetch_admission_verdict": "source_contract_admissibility_not_enforced",
        "mandatory_facet_count": 16,
        "admissibility_predicates_count": 7,
        "fetch_plan_required_facets_missing_count": 16,
        "fetch_plan_required_facets_present_count": 0,
        "license_reaches_fetch_plan": False,
        "field_refs_reach_fetch_plan": False,
        "time_coverage_reaches_fetch_plan": False,
        "freshness_ref_reaches_fetch_plan": False,
        "watermark_ref_reaches_fetch_plan": False,
        "claim_bindability_reaches_fetch_plan": False,
        "normal_catalog_fetch_admission_blocks_missing_source_contract": False,
        "executor_consumes_source_contract_gate": False,
        "source_contract_strict_binding_gate_exists": True,
        "source_contract_strict_binding_gate_orchestrated_before_fetch": False,
        "strict_missing_candidate_rejected": True,
        "strict_source_selection_trace_fails_missing_facets": True,
        "catalog_raw_metadata_partial": True,
        "production_execution_ready_binding_count": 41976,
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            violations.append({
                "code": "summary_semantics_drift",
                "detail": f"{key}={summary.get(key)!r}; expected {expected!r}",
            })

    facets = set(_nested(audit, ("probe", "data_requirement_contract", "mandatory_facets")) or [])
    if facets != REQUIRED_FACETS:
        violations.append({
            "code": "mandatory_facets_drift",
            "detail": sorted(facets),
        })

    predicates = _nested(audit, ("probe", "data_requirement_contract", "admissibility_predicates"))
    if not isinstance(predicates, list) or len(predicates) != 7:
        violations.append({
            "code": "admissibility_predicates_missing",
            "detail": predicates,
        })
    elif "claim_bindability_refs_present" not in predicates:
        violations.append({
            "code": "claim_bindability_predicate_missing",
            "detail": predicates,
        })

    catalog_counts = _nested(audit, ("probe", "catalog_execution_ready_facet_counts"))
    if not isinstance(catalog_counts, dict):
        violations.append({"code": "missing_catalog_counts", "detail": "catalog counts missing"})
        catalog_counts = {}
    else:
        expected_counts = {
            "total": 41976,
            "has_license": 28426,
            "has_freshness_hint": 41976,
            "has_schema_profile": 41976,
            "has_value_columns": 41976,
            "has_time_start": 4894,
            "has_time_end": 4894,
            "has_geo_column": 22981,
            "has_time_column": 46,
        }
        for key, expected in expected_counts.items():
            if catalog_counts.get(key) != expected:
                violations.append({
                    "code": "catalog_count_drift",
                    "detail": f"{key}={catalog_counts.get(key)!r}; expected {expected!r}",
                })

    source_registry = _nested(audit, ("probe", "catalog_source_registry"))
    if not isinstance(source_registry, dict):
        violations.append({
            "code": "missing_source_registry_probe",
            "detail": "catalog_source_registry missing",
        })
    else:
        expected_registry = {
            "total_sources": 35,
            "rolling_window": 3,
            "full_snapshot": 32,
            "with_default_lookback": 3,
            "publish_blocking": 12,
        }
        for key, expected in expected_registry.items():
            if source_registry.get(key) != expected:
                violations.append({
                    "code": "source_registry_count_drift",
                    "detail": f"{key}={source_registry.get(key)!r}; expected {expected!r}",
                })

    plan_present = set(
        _nested(
            audit,
            ("probe", "fetch_admission_probe", "required_facets_present_in_plan_payload"),
        )
        or []
    )
    plan_missing = set(
        _nested(
            audit,
            ("probe", "fetch_admission_probe", "required_facets_missing_from_plan_payload"),
        )
        or []
    )
    if plan_present:
        violations.append({
            "code": "fetch_plan_facets_unexpectedly_present",
            "detail": sorted(plan_present),
        })
    if plan_missing != REQUIRED_FACETS:
        violations.append({
            "code": "fetch_plan_missing_facet_set_drift",
            "detail": sorted(plan_missing),
        })

    plan_metadata = _nested(
        audit,
        ("probe", "fetch_admission_probe", "plan_dump_excerpt", "metadata"),
    )
    if not isinstance(plan_metadata, dict):
        violations.append({"code": "missing_plan_metadata_probe", "detail": "metadata missing"})
    else:
        forbidden = sorted(REQUIRED_FACETS & set(plan_metadata))
        if forbidden:
            violations.append({
                "code": "plan_metadata_claims_admissibility_facets",
                "detail": forbidden,
            })
        expected_keys = {
            "catalog_dataset_id",
            "distribution_id",
            "execution_tier",
            "source",
            "history_policy",
            "default_lookback_days",
            "manual_backfill_allowed",
            "resolution_route",
        }
        missing_keys = sorted(expected_keys - set(plan_metadata))
        if missing_keys:
            violations.append({
                "code": "plan_metadata_probe_incomplete",
                "detail": missing_keys,
            })

    strict_probe = _nested(audit, ("probe", "strict_gate_probe"))
    if not isinstance(strict_probe, dict):
        violations.append({"code": "missing_strict_gate_probe", "detail": "strict_gate_probe missing"})
        strict_probe = {}
    expected_strict = {
        "missing_candidate_reason_code": "source_contract_facets_missing",
        "complete_candidate_binding_status": "selected",
        "source_selection_trace_status": "fail",
        "source_selection_trace_blocking_issue_count": 18,
    }
    for key, expected in expected_strict.items():
        if strict_probe.get(key) != expected:
            violations.append({
                "code": "strict_gate_probe_drift",
                "detail": f"{key}={strict_probe.get(key)!r}; expected {expected!r}",
            })
    issue_codes = set(strict_probe.get("source_selection_trace_issue_codes") or [])
    for required_code in (
        "selected_source_missing_source_rights",
        "selected_source_missing_field_refs",
        "selected_source_missing_time_coverage_refs",
        "selected_source_missing_freshness_refs",
        "selected_source_missing_data_forge_snapshot_refs",
    ):
        if required_code not in issue_codes:
            violations.append({
                "code": "strict_trace_issue_missing",
                "detail": required_code,
            })

    rows_by_id = _row_map(audit)
    if not rows_by_id:
        violations.append({"code": "missing_route_rows", "detail": "route_rows missing"})
        return violations
    missing_rows = sorted(REQUIRED_ROUTE_ROWS - set(rows_by_id))
    if missing_rows:
        violations.append({"code": "missing_required_route_row", "detail": missing_rows})

    for route_id, row in sorted(rows_by_id.items()):
        for field in (
            "stage",
            "capability_state",
            "observed",
            "gap_labels",
            "pattern_ids",
            "authority_risk",
            "evidence_refs",
            "next_probe",
        ):
            if row.get(field) in (None, "", [], {}):
                violations.append({
                    "code": "missing_route_row_field",
                    "detail": f"{route_id}.{field}",
                })
        labels = row.get("gap_labels")
        if isinstance(labels, list):
            unknown = sorted(set(labels) - ALLOWED_GAP_LABELS)
            if unknown:
                violations.append({
                    "code": "unknown_gap_label",
                    "detail": f"{route_id}: {unknown}",
                })
        else:
            violations.append({"code": "bad_gap_labels", "detail": route_id})

    expected_row_states = {
        "catalog.metric_binding_contract": "binding_contract_drops_source_contract_facets",
        "retrieval.catalog_binding_to_fetch_plan": "fetch_plan_admission_missing_required_facets",
        "fetch.executor.admission_consumer": "executor_consumes_fetch_plan_not_admissibility",
        "fabric.source_selection_audit.strict_gate": "implemented_but_not_orchestrated",
        "fabric.data_requirement_adapter.strict_gate": "implemented_but_not_orchestrated",
        "retrieval.catalog_freshness_policy": "freshness_policy_hint_only",
    }
    for route_id, expected_state in expected_row_states.items():
        row = rows_by_id.get(route_id)
        if row is None:
            continue
        if row.get("capability_state") != expected_state:
            violations.append({
                "code": "required_route_state_changed",
                "detail": f"{route_id}={row.get('capability_state')!r}; expected {expected_state!r}",
            })

    fetch_row = rows_by_id.get("retrieval.catalog_binding_to_fetch_plan", {})
    if set(fetch_row.get("gap_labels") or ()) < {
        "bridge_missing",
        "semantic_test_missing",
        "verification_missing",
    }:
        violations.append({
            "code": "fetch_plan_gap_labels_missing",
            "detail": fetch_row.get("gap_labels"),
        })

    executor_row = rows_by_id.get("fetch.executor.admission_consumer", {})
    if "consumer_missing" not in set(executor_row.get("gap_labels") or ()):
        violations.append({
            "code": "executor_consumer_gap_missing",
            "detail": executor_row.get("gap_labels"),
        })

    findings = audit.get("findings")
    if not isinstance(findings, list) or len(findings) < 6:
        violations.append({
            "code": "missing_findings",
            "detail": "at least six findings required",
        })

    return violations


def main(argv: list[str] | None = None) -> int:
    """Run the validator CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output")
    args = parser.parse_args(argv)

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    violations = validate(audit)
    payload = {
        "status": "pass" if not violations else "fail",
        "issue_count": len(violations),
        "violations": violations,
        "audit": str(args.audit),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    elif violations:
        print(f"FAIL: {len(violations)} violation(s)")
        for item in violations:
            print(f"- {item['code']}: {item.get('detail', '')}")
    else:
        print("PASS: GY source-contract admissibility audit artifact is internally consistent.")
    return 0 if not violations else 1


if __name__ == "__main__":
    import sys

    from tools.lib.timing import run_timed_entrypoint

    raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
