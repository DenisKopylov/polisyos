#!/usr/bin/env python3
"""Validate the GY Lex/frontier root-cause audit artifact.

This check protects the Task 0 finding that the pinned Lex DAG failure is a
Scientist search-spec optional-bound bug, not bad upstream bounds and not an
observed frontier laundering event.

Usage:
    python3 tools/quality/validation/check_layer3_gy_lex_frontier_root_cause_audit.py [--json]
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
    / "layer3_gy_lex_frontier_root_cause_audit.json"
)

REQUIRED_ROUTE_ROWS = {
    "scientist.workflow.policy_design.lex_node",
    "lex.adapter.run_search",
    "scientist.policy_design.search.optional_bounds",
    "scientist.methods.search.ParameterBounds",
    "scientist.policy_verified.formalize_policy_option_set",
    "scientist.policy_frontier_report.persistence",
    "scientist.policy_design.frontier_unevaluated_candidate_fallback",
}

REQUIRED_PATTERNS = {"P01", "P02", "P03", "P10", "P12", "P25"}

REQUIRED_ACCEPTANCE_PHRASES = {
    "missing min_value/max_value must remain None",
    "bad explicit equal bounds must still fail closed",
    "frontier reports must carry search space source",
    "unevaluated candidates must not be marked feasible",
    "downstream governance must stay blocked",
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


def _codes(violations: list[dict[str, Any]]) -> set[str]:
    return {str(item["code"]) for item in violations}


def validate(audit: dict[str, Any]) -> list[dict[str, Any]]:
    """Return audit integrity violations."""
    violations: list[dict[str, Any]] = []

    if audit.get("schema_version") != "layer3_gy_lex_frontier_root_cause_audit.v1":
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
            "detail": "audit must not imply live network/fetch coverage",
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
        "primary": "implementation_bug_optional_bounds_none_normalized_to_zero",
        "lex_node_gap_class": "wired_but_rotten",
        "route_pinned": True,
        "repair_before_downstream_governance": True,
    }
    for key, expected in expected_classification.items():
        if classification.get(key) != expected:
            violations.append({
                "code": "classification_drift",
                "detail": f"{key}={classification.get(key)!r}; expected {expected!r}",
            })

    patterns = set(classification.get("patterns") or [])
    if not patterns >= REQUIRED_PATTERNS:
        violations.append({
            "code": "pattern_coverage_drift",
            "detail": sorted(patterns),
        })

    root_matrix = classification.get("root_cause_matrix")
    if not isinstance(root_matrix, dict):
        violations.append({"code": "missing_root_cause_matrix", "detail": "matrix missing"})
        root_matrix = {}

    matrix_expectations = {
        ("bug", "primary"): True,
        ("thin_input", "primary"): False,
        ("bad_bounds", "primary"): False,
        ("frontier_objective_laundering", "observed"): False,
        ("frontier_objective_laundering", "risk_after_repair"): True,
        ("synthetic_scaffold", "primary"): False,
        ("synthetic_scaffold", "contributing"): True,
    }
    for (outer, inner), expected in matrix_expectations.items():
        value = _nested(root_matrix, (outer, inner))
        if value != expected:
            violations.append({
                "code": "root_cause_matrix_drift",
                "detail": f"{outer}.{inner}={value!r}; expected {expected!r}",
            })

    summary = audit.get("summary")
    if not isinstance(summary, dict):
        violations.append({"code": "missing_summary", "detail": "summary missing"})
        summary = {}

    expected_summary = {
        "workflow_id": "scientist_policy_design",
        "workflow_status": "fail",
        "workflow_node_count": 37,
        "workflow_ok_nodes": 14,
        "workflow_fail_nodes": 1,
        "workflow_skip_nodes": 22,
        "failing_node": "run_hierarchical_policy_search",
        "failing_node_status": "fail",
        "failing_node_error_code": "node.invalid_state",
        "failing_parameter": "verified_policy_option_rate",
        "trinity_bundle_artifact_id": (
            "sha256:9497cb4c5c629e004a322836112ad361f44618132346b019433620a6e58333cf"
        ),
        "persisted_parameter_default_value": "0.1",
        "persisted_parameter_min_value_is_null": True,
        "persisted_parameter_max_value_is_null": True,
        "persisted_parameter_tunable": True,
        "normalized_default_value": 0.1,
        "normalized_min_value": 0.0,
        "normalized_max_value": 0.0,
        "parameter_bounds_validator_correct": True,
        "lex_adapter_invoked": True,
        "lex_adapter_swallows_invalid_bounds": False,
        "node_catches_value_error_as_fail": True,
        "search_frontier_persisted": False,
        "policy_frontier_report_ref_present": False,
        "frontier_laundering_observed": False,
        "frontier_laundering_risk_after_repair": True,
        "bad_upstream_bounds_observed": False,
        "thin_input_primary": False,
        "synthetic_scaffold_primary": False,
        "synthetic_scaffold_contributing": True,
        "optional_bound_bug_primary": True,
        "downstream_skips_blocked_upstream": True,
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            violations.append({
                "code": "summary_semantics_drift",
                "detail": f"{key}={summary.get(key)!r}; expected {expected!r}",
            })

    if summary.get("failure_message") != (
        "Hierarchical policy search failed: Invalid bounds for "
        "'verified_policy_option_rate': lower >= upper"
    ):
        violations.append({
            "code": "failure_message_drift",
            "detail": summary.get("failure_message"),
        })

    if summary.get("derived_bounds_from_current_builder") != [0.0, 0.0]:
        violations.append({
            "code": "current_builder_bounds_drift",
            "detail": summary.get("derived_bounds_from_current_builder"),
        })
    if summary.get("derived_bounds_if_none_preserved") != [0.08, 0.12000000000000001]:
        violations.append({
            "code": "none_preserved_bounds_drift",
            "detail": summary.get("derived_bounds_if_none_preserved"),
        })

    parameter = _nested(audit, ("probes", "persisted_trinity_bundle", "parameter"))
    if not isinstance(parameter, dict):
        violations.append({"code": "missing_persisted_parameter_probe", "detail": "probe missing"})
        parameter = {}
    parameter_expectations = {
        "param_id": "verified_policy_option_rate",
        "default_value": "0.1",
        "min_value": None,
        "max_value": None,
        "tunable": True,
    }
    for key, expected in parameter_expectations.items():
        if parameter.get(key) != expected:
            violations.append({
                "code": "persisted_parameter_probe_drift",
                "detail": f"{key}={parameter.get(key)!r}; expected {expected!r}",
            })

    direct = _nested(audit, ("probes", "direct_reproducer", "observed_values"))
    if not isinstance(direct, dict):
        violations.append({"code": "missing_direct_reproducer", "detail": "probe missing"})
        direct = {}
    direct_expectations = {
        "normalized_min": 0.0,
        "normalized_max": 0.0,
        "derived_bounds_from_current_builder": [0.0, 0.0],
        "exception_type": "ValueError",
        "exception_message": "Invalid bounds for 'verified_policy_option_rate': lower >= upper",
    }
    for key, expected in direct_expectations.items():
        if direct.get(key) != expected:
            violations.append({
                "code": "direct_reproducer_drift",
                "detail": f"{key}={direct.get(key)!r}; expected {expected!r}",
            })

    frontier = _nested(audit, ("probes", "frontier_semantics"))
    if not isinstance(frontier, dict):
        violations.append({"code": "missing_frontier_semantics", "detail": "probe missing"})
        frontier = {}
    if frontier.get("current_run_frontier_status") != "absent_due_to_node_fail":
        violations.append({
            "code": "frontier_status_drift",
            "detail": frontier.get("current_run_frontier_status"),
        })
    if frontier.get("current_run_laundering_status") != "not_observed":
        violations.append({
            "code": "frontier_laundering_greenwash",
            "detail": frontier.get("current_run_laundering_status"),
        })

    acceptance_text = "\n".join(str(item) for item in frontier.get("required_repair_acceptance") or [])
    for phrase in REQUIRED_ACCEPTANCE_PHRASES:
        if phrase not in acceptance_text:
            violations.append({
                "code": "missing_repair_acceptance_guardrail",
                "detail": phrase,
            })

    rows = _row_map(audit)
    missing_rows = REQUIRED_ROUTE_ROWS - set(rows)
    for route_id in sorted(missing_rows):
        violations.append({"code": "missing_required_route_row", "detail": route_id})

    root_row = rows.get("scientist.policy_design.search.optional_bounds", {})
    if root_row.get("classification") != "root_cause":
        violations.append({
            "code": "root_row_classification_drift",
            "detail": root_row.get("classification"),
        })
    if root_row.get("execution_status") != "fails":
        violations.append({
            "code": "root_row_execution_drift",
            "detail": root_row.get("execution_status"),
        })

    frontier_row = rows.get("scientist.policy_frontier_report.persistence", {})
    if frontier_row.get("execution_status") != "not_reached":
        violations.append({
            "code": "frontier_row_greenwash",
            "detail": frontier_row.get("execution_status"),
        })

    strict_row = rows.get("scientist.methods.search.ParameterBounds", {})
    if strict_row.get("execution_status") != "works":
        violations.append({
            "code": "bounds_validator_blame_drift",
            "detail": strict_row.get("execution_status"),
        })

    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    violations = validate(audit)
    payload = {
        "status": "pass" if not violations else "fail",
        "violation_count": len(violations),
        "violations": violations,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif violations:
        for violation in violations:
            print(f"{violation['code']}: {violation['detail']}")
    else:
        print("PASS: GY Lex/frontier root-cause audit is internally consistent.")
    return 1 if violations else 0


if __name__ == "__main__":
    import sys

    from tools.lib.timing import run_timed_entrypoint

    raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
