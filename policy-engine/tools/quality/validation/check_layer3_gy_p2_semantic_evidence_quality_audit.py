#!/usr/bin/env python3
"""Validate the GY Task 0 P2 semantic evidence quality audit artifact."""

from __future__ import annotations

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
    / "layer3_gy_p2_semantic_evidence_quality_audit.json"
)

REQUIRED_PATTERNS = {"P01", "P02", "P05", "P10", "P12", "P14", "P15", "P25"}
REQUIRED_NEGATIVES = {
    "do_not_count_unfiltered_catalog_hit_as_route_admissible",
    "do_not_count_metric_binding_presence_as_semantic_relevance",
    "do_not_count_web_evidence_bundle_as_l2_skg",
    "do_not_count_knowledge_toolkit_class_as_route_tooling",
}
EXPECTED_SUMMARY = {
    "catalog_dataset_count": 137176,
    "catalog_distribution_count": 605408,
    "catalog_metric_binding_count": 56846,
    "catalog_schema_profile_count": 176249,
    "catalog_vector_index_files_present": True,
    "catalog_sentence_transformers_available": False,
    "catalog_search_runs_text_only": True,
    "catalog_silver_case_count": 5,
    "catalog_silver_judged_topk_rows": 25,
    "catalog_construct_precision_at_5_micro": 0.56,
    "catalog_scope_precision_at_5_micro": 0.2,
    "catalog_route_admissible_precision_at_5_micro": 0.0,
    "catalog_country_filter_tested_cases": 4,
    "catalog_country_filter_zero_result_cases": 4,
    "catalog_metric_binding_probe_query_count": 9,
    "catalog_semantic_gate_exists": False,
    "catalog_precision_recall_gate_exists": False,
    "scholar_skg_db_present": True,
    "scholar_skg_article_count": 310829,
    "scholar_skg_edge_count": 7607,
    "scholar_skg_parameter_estimate_count": 62248,
    "scholar_route_like_work_queries_returned_total": 0,
    "scholar_canonical_edge_probe_pairs": 6,
    "scholar_canonical_edge_probe_pairs_with_hybrid_hits": 4,
    "scholar_small_business_lending_pairs_with_hits": 0,
    "scholar_web_bundle_persistence_exists": True,
    "scholar_web_bundle_to_research_dag_projection_exists": True,
    "g2_guard_rejects_web_bundle_as_l2_skg": True,
    "knowledge_toolkit_methods_expected": 20,
    "knowledge_toolkit_adapter_tools_registered_with_empty_toolkit": 3,
    "knowledge_toolkit_all_expected_methods_registered": False,
    "knowledge_toolkit_default_runtime_dataset_scholar_graph_injection_found": False,
    "overall_status": "semantic_test_missing_and_tool_bridge_missing",
}


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: object) -> set[str]:
    return {str(item) for item in _list(value)}


def _violation(code: str, detail: object) -> dict[str, Any]:
    return {"code": code, "detail": detail}


def validate(audit: dict[str, Any]) -> list[dict[str, Any]]:
    """Return audit integrity violations."""

    violations: list[dict[str, Any]] = []

    if audit.get("schema_version") != (
        "policyos.policy_design_case.layer3_gy_p2_semantic_evidence_quality_audit.v1"
    ):
        violations.append(_violation("bad_schema_version", audit.get("schema_version")))
    if audit.get("status") != "pass":
        violations.append(_violation("audit_status_not_pass", audit.get("status")))
    if audit.get("system_readiness") != "blocked_for_semantic_adequacy_and_evidence_quality":
        violations.append(_violation("system_readiness_greenwash", audit.get("system_readiness")))

    methodology = _dict(audit.get("methodology"))
    for key in (
        "catalog_production_duckdb_queried",
        "catalog_search_api_executed",
        "catalog_metric_binding_api_executed",
        "catalog_silver_benchmark_labeled",
        "scholar_production_skg_duckdb_queried",
        "scholar_query_api_executed",
        "knowledge_toolkit_registry_probe_run",
    ):
        if methodology.get(key) is not True:
            violations.append(_violation("methodology_probe_missing", key))
    for key in ("agents_used", "network_fetches_run", "runtime_server_started", "fixes_made"):
        if methodology.get(key) is not False:
            violations.append(_violation("methodology_scope_drift", f"{key}={methodology.get(key)!r}"))
    if methodology.get("probe_digest") != (
        "sha256:714dfe6ec3df783f10d55613aa968e77f086ba42c08d890c3dcef3cddcd3e2b6"
    ):
        violations.append(_violation("probe_digest_drift", methodology.get("probe_digest")))

    classification = _dict(audit.get("classification"))
    if classification.get("primary") != "semantic_adequacy_and_tool_bridge_missing":
        violations.append(_violation("classification_drift", classification.get("primary")))
    if classification.get("repair_before_downstream_governance") is not True:
        violations.append(_violation("missing_repair_before_governance", classification))
    missing_patterns = sorted(REQUIRED_PATTERNS - _strings(classification.get("patterns")))
    if missing_patterns:
        violations.append(_violation("missing_pattern_register_ids", missing_patterns))
    labels = _strings(classification.get("capability_labels"))
    for label in ("semantic_test_missing", "bridge_missing", "implemented_but_not_orchestrated"):
        if label not in labels:
            violations.append(_violation("missing_capability_label", label))

    summary = _dict(audit.get("summary"))
    for key, expected in EXPECTED_SUMMARY.items():
        if summary.get(key) != expected:
            violations.append(
                _violation(
                    "summary_semantics_drift",
                    f"{key}={summary.get(key)!r}; expected {expected!r}",
                )
            )
    if set(summary.get("catalog_metric_binding_zero_result_queries") or []) != {
        "cash transfer",
        "firm survival",
    }:
        violations.append(
            _violation(
                "metric_zero_result_query_drift",
                summary.get("catalog_metric_binding_zero_result_queries"),
            )
        )

    catalog = _dict(audit.get("catalog_semantic_adequacy"))
    production = _dict(catalog.get("production_catalog"))
    if production.get("embedding_runtime") != "text_only_sentence_transformers_missing":
        violations.append(_violation("catalog_embedding_status_greenwash", production))
    benchmark = _dict(catalog.get("silver_benchmark"))
    aggregate = _dict(benchmark.get("aggregate"))
    if aggregate.get("route_admissible_precision_at_5_micro") != 0.0:
        violations.append(_violation("catalog_route_precision_greenwash", aggregate))
    if aggregate.get("country_filter_zero_result_cases") != 4:
        violations.append(_violation("catalog_country_filter_drift", aggregate))
    cases = {str(row.get("case_id")): row for row in _list(benchmark.get("cases")) if isinstance(row, dict)}
    expected_case_precisions = {
        "ua_msme_credit": (0.4, 0.0, 0.0),
        "pl_energy_affordability": (0.4, 0.0, 0.0),
        "pk_cash_transfer": (1.0, 0.0, 0.0),
        "ua_displacement": (1.0, 0.0, 0.0),
        "firm_survival": (0.0, 1.0, 0.0),
    }
    for case_id, expected in expected_case_precisions.items():
        row = _dict(cases.get(case_id))
        actual = (
            row.get("construct_precision_at_5"),
            row.get("scope_precision_at_5"),
            row.get("route_admissible_precision_at_5"),
        )
        if actual != expected:
            violations.append(_violation("catalog_case_precision_drift", {case_id: actual}))
        if case_id != "firm_survival" and row.get("country_filter_returned") != 0:
            violations.append(_violation("catalog_case_country_filter_greenwash", case_id))
        if not str(row.get("route_diagnosis") or "").strip():
            violations.append(_violation("catalog_case_missing_diagnosis", case_id))

    metric_rows = {
        str(row.get("query")): row
        for row in _list(catalog.get("metric_binding_comparison"))
        if isinstance(row, dict)
    }
    expected_metric_counts = {
        "msme credit": 8,
        "credit access": 8,
        "firm survival": 0,
        "poverty": 8,
        "energy poverty": 8,
        "electricity price": 8,
        "displacement": 8,
        "social protection": 8,
        "cash transfer": 0,
    }
    for query, expected_count in expected_metric_counts.items():
        row = _dict(metric_rows.get(query))
        if row.get("returned") != expected_count:
            violations.append(_violation("metric_binding_count_drift", {query: row.get("returned")}))
        if not str(row.get("diagnosis") or "").strip():
            violations.append(_violation("metric_binding_missing_diagnosis", query))

    scholar = _dict(audit.get("scholar_openalex_knowledge_toolkit"))
    substrate = _dict(scholar.get("openalex_batch_and_skg_substrate"))
    counts = _dict(substrate.get("table_counts"))
    if counts.get("ac_skg_articles") != 310829 or counts.get("ac_skg_edges") != 7607:
        violations.append(_violation("scholar_skg_count_drift", counts))
    route_probe = _dict(scholar.get("route_like_query_probe"))
    for row_obj in _list(route_probe.get("work_search_route_like_queries")):
        row = _dict(row_obj)
        if row.get("returned") != 0:
            violations.append(_violation("scholar_route_like_query_greenwash", row))
    edge_rows = _list(scholar.get("canonical_edge_query_probe"))
    if len(edge_rows) != 6:
        violations.append(_violation("scholar_edge_probe_count_drift", len(edge_rows)))
    small_business_hits = [
        _dict(row)
        for row in edge_rows
        if str(_dict(row).get("cause")) == "finance.small_business_lending"
        and (
            int(_dict(row).get("exact") or 0)
            + int(_dict(row).get("family") or 0)
            + int(_dict(row).get("hybrid") or 0)
        )
        > 0
    ]
    if small_business_hits:
        violations.append(_violation("scholar_small_business_greenwash", small_business_hits))
    web_path = _dict(scholar.get("web_evidence_runtime_path"))
    if web_path.get("classification") != "near_route_evidence_tool_not_canonical_l2_skg_authority":
        violations.append(_violation("web_evidence_boundary_drift", web_path))
    toolkit = _dict(scholar.get("knowledge_toolkit_probe"))
    if toolkit.get("registered_count") != 3 or toolkit.get("missing_registered_count") != 17:
        violations.append(_violation("knowledge_toolkit_registry_count_drift", toolkit))
    if "TYPE_CHECKING" not in str(toolkit.get("failure_mode") or ""):
        violations.append(_violation("knowledge_toolkit_failure_mode_drift", toolkit.get("failure_mode")))
    if toolkit.get("classification") != "tool_facade_built_but_route_bridge_and_registry_completeness_missing":
        violations.append(_violation("knowledge_toolkit_classification_drift", toolkit))

    findings = {str(row.get("id")): row for row in _list(audit.get("findings")) if isinstance(row, dict)}
    for finding_id in ("P2-1", "P2-2", "P2-3", "P2-4", "P2-5"):
        if finding_id not in findings:
            violations.append(_violation("missing_finding", finding_id))
    negatives = {
        str(row.get("id")): row
        for row in _list(audit.get("negative_assertions"))
        if isinstance(row, dict)
    }
    missing_negatives = sorted(REQUIRED_NEGATIVES - set(negatives))
    if missing_negatives:
        violations.append(_violation("missing_negative_assertions", missing_negatives))
    for negative_id in REQUIRED_NEGATIVES & set(negatives):
        if negatives[negative_id].get("assertion_holds") is not True:
            violations.append(_violation("negative_assertion_not_enforced", negative_id))

    acceptance = "\n".join(str(item) for item in _list(audit.get("acceptance_signal_for_future_repairs")))
    for phrase in (
        "route_admissible_precision_at_k",
        "FetchPlan admission",
        "SKGQuery",
        "web bundles remain citation/tool evidence",
        "KnowledgeToolkit adapter registers",
    ):
        if phrase not in acceptance:
            violations.append(_violation("missing_acceptance_signal", phrase))

    return violations


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    """Run the P2 semantic evidence quality audit validator."""

    parser = argparse.ArgumentParser(description=__doc__)
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
        print("FAIL layer3_gy_p2_semantic_evidence_quality_audit")
        for violation in violations:
            print(f"- {violation['code']}: {violation['detail']}")
    else:
        print("PASS layer3_gy_p2_semantic_evidence_quality_audit")
    return 0 if not violations else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
