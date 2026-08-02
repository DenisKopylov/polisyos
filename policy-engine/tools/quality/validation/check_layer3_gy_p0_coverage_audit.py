#!/usr/bin/env python3
"""Validate the GY Task 0 P0 coverage audit artifact.

This check protects the follow-up audit from drifting back into aggregate
claims: the production worker/DAG status mismatch, all 406 candidate-positive
firewall rows, blocked state-read mappings, and the depth-2 generalization
probe must remain explicit.
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
    / "layer3_gy_p0_coverage_audit.json"
)

EXPECTED_FIREWALL_COUNTS = {
    "external_request_input_only_status_without_reducer_authority": 1,
    "generic_status_without_producer_or_reducer_provenance": 397,
    "search_health_status_without_producer_or_reducer_provenance": 8,
}
REQUIRED_BLOCKED_INPUTS = {
    "build_literature_prior": "params.causal_variables",
    "reconcile_causal_graph": "params.data_causal_graph",
    "run_causal_evaluation": "observational_data_ref",
}
REQUIRED_PATTERNS = {"P02", "P03", "P05", "P10", "P15", "P25"}


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _violation(code: str, detail: object) -> dict[str, Any]:
    return {"code": code, "detail": detail}


def validate(audit: dict[str, Any]) -> list[dict[str, Any]]:
    """Return audit integrity violations."""
    violations: list[dict[str, Any]] = []

    if audit.get("schema_version") != "policyos.policy_design_case.layer3_gy_p0_coverage_audit.v1":
        violations.append(_violation("bad_schema_version", audit.get("schema_version")))
    if audit.get("status") != "pass":
        violations.append(_violation("audit_status_not_pass", audit.get("status")))
    if audit.get("system_readiness") != "blocked_for_downstream_plan_changes":
        violations.append(_violation("system_readiness_greenwash", audit.get("system_readiness")))

    patterns = {str(item) for item in _as_list(audit.get("pattern_register_ids"))}
    missing_patterns = sorted(REQUIRED_PATTERNS - patterns)
    if missing_patterns:
        violations.append(_violation("missing_pattern_register_ids", missing_patterns))

    summary = _as_dict(audit.get("summary"))
    expected_summary = {
        "production_worker_control_path_executed": True,
        "production_worker_real_dag_reached": True,
        "production_worker_job_state": "completed",
        "production_worker_workflow_report_status": "fail",
        "production_worker_status_mismatch": True,
        "run_lifecycle_call_discards_return": True,
        "nl_pipeline_call_captures_return": True,
        "gy2_target_mismatch": True,
        "candidate_positive_status_count": 406,
        "positive_status_count": 0,
        "excluded_candidate_count": 406,
        "candidate_positive_rows_enumerated": 406,
        "blocked_input_node_count": 3,
        "blocked_input_state_reads_mapped_count": 3,
        "depth2_policy_design_dag_status": "fail_same_lex_optional_bounds_bug",
        "depth2_reducer_generalization_status": "route_omitted_case_not_parameterized",
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            violations.append(
                _violation(
                    "summary_semantics_drift",
                    f"{key}={summary.get(key)!r}; expected {expected!r}",
                )
            )

    worker = _as_dict(audit.get("production_job_worker_dag"))
    real_probe = _as_dict(worker.get("real_dag_probe"))
    if real_probe.get("job_response_state") != "completed":
        violations.append(_violation("worker_job_not_completed", real_probe.get("job_response_state")))
    if real_probe.get("workflow_report_status") != "fail":
        violations.append(
            _violation("worker_workflow_report_not_failed", real_probe.get("workflow_report_status"))
        )
    if real_probe.get("mismatch_observed") in (None, ""):
        violations.append(_violation("missing_worker_status_mismatch_finding", "mismatch_observed"))
    if not worker.get("gy2_implication"):
        violations.append(_violation("missing_gy2_implication", "production worker audit"))

    firewall = _as_dict(audit.get("candidate_positive_firewall"))
    counts = _as_dict(firewall.get("counts"))
    if counts.get("candidate_positive_status_count") != 406:
        violations.append(_violation("candidate_positive_count_drift", counts.get("candidate_positive_status_count")))
    if counts.get("positive_status_count") != 0:
        violations.append(_violation("positive_status_count_not_zero", counts.get("positive_status_count")))
    if counts.get("by_firewall_rule") != EXPECTED_FIREWALL_COUNTS:
        violations.append(_violation("firewall_reason_counts_drift", counts.get("by_firewall_rule")))

    rows = _as_list(firewall.get("rows"))
    if len(rows) != 406:
        violations.append(_violation("candidate_positive_rows_missing", len(rows)))
    seen: set[str] = set()
    for index, row_obj in enumerate(rows):
        row = _as_dict(row_obj)
        row_id = row.get("candidate_positive_status_id")
        if not isinstance(row_id, str) or not row_id.startswith("sha256:"):
            violations.append(_violation("bad_candidate_positive_id", index))
        elif row_id in seen:
            violations.append(_violation("duplicate_candidate_positive_id", row_id))
        seen.add(str(row_id))
        if row.get("firewall_decision") != "excluded_from_production_positive_status_count":
            violations.append(_violation("bad_firewall_decision", row.get("firewall_decision")))
        if row.get("firewall_rule") not in EXPECTED_FIREWALL_COUNTS:
            violations.append(_violation("unknown_firewall_rule", row.get("firewall_rule")))
        triage = _as_dict(row.get("false_exclusion_triage"))
        if "risk" not in triage or "note" not in triage:
            violations.append(_violation("missing_false_exclusion_triage", row_id))

    blocked = _as_dict(audit.get("blocked_dag_state_reads"))
    blocked_inputs = _as_list(blocked.get("blocked_input_nodes"))
    by_alias = {
        str(row.get("alias")): row
        for row in blocked_inputs
        if isinstance(row, dict) and row.get("alias")
    }
    for alias, required_read in REQUIRED_BLOCKED_INPUTS.items():
        row = _as_dict(by_alias.get(alias))
        if not row:
            violations.append(_violation("missing_blocked_input_node", alias))
            continue
        if required_read not in _as_list(row.get("triggering_missing_reads")):
            violations.append(_violation("blocked_input_missing_read_drift", f"{alias}:{required_read}"))
        if not _as_list(row.get("declared_state_reads")):
            violations.append(_violation("blocked_input_declared_reads_missing", alias))
        if not _as_list(row.get("missing_producer_or_ref")):
            violations.append(_violation("blocked_input_producer_mapping_missing", alias))

    upstream = _as_list(blocked.get("blocked_upstream_nodes"))
    if len(upstream) < 19:
        violations.append(_violation("blocked_upstream_inventory_shrunk", len(upstream)))

    depth2 = _as_dict(audit.get("depth2_generalization"))
    catalog = _as_dict(depth2.get("catalog_search"))
    if catalog.get("classification") != "semantic_adequacy_and_jurisdiction_filter_gap":
        violations.append(_violation("depth2_catalog_classification_drift", catalog.get("classification")))
    filtered = _as_list(catalog.get("country_filtered_results"))
    if len(filtered) < 3 or any(_as_dict(row).get("returned") != 0 for row in filtered):
        violations.append(_violation("depth2_country_filter_probe_drift", filtered))
    if not _as_list(catalog.get("unfiltered_top_hits")):
        violations.append(_violation("depth2_unfiltered_hits_missing", "unfiltered_top_hits"))

    dag = _as_dict(depth2.get("dag_probe"))
    if dag.get("status") != "fail":
        violations.append(_violation("depth2_dag_not_failed", dag.get("status")))
    if _as_dict(dag.get("node_status_counts")) != {"fail": 1, "ok": 14, "skip": 22}:
        violations.append(_violation("depth2_dag_counts_drift", dag.get("node_status_counts")))
    if _as_dict(dag.get("failing_node")).get("alias") != "run_hierarchical_policy_search":
        violations.append(_violation("depth2_lex_failure_missing", dag.get("failing_node")))

    reducer = _as_dict(depth2.get("reducer_probe"))
    if reducer.get("cli_accepts_case_input") is not False:
        violations.append(_violation("depth2_reducer_case_input_greenwash", reducer.get("cli_accepts_case_input")))
    if reducer.get("classification") != "route_omitted_case_not_parameterized":
        violations.append(_violation("depth2_reducer_classification_drift", reducer.get("classification")))

    return violations


def main() -> int:
    """Run the audit validator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    violations = validate(audit)
    if args.json:
        print(json.dumps({"status": "fail" if violations else "pass", "violations": violations}, indent=2))
    elif violations:
        print("FAIL")
        for violation in violations:
            print(f"- {violation['code']}: {violation['detail']}")
    else:
        print("PASS")
    return 1 if violations else 0


if __name__ == "__main__":
    import sys

    from tools.lib.timing import run_timed_entrypoint

    raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
