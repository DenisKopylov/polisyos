#!/usr/bin/env python3
"""Validate the GY Foundry breadth audit artifact.

This check protects the Task 0 distinction between representative direct
Foundry producer smokes and pinned-route DAG-consumed method truth.

Usage:
    python3 tools/quality/validation/check_layer3_gy_foundry_breadth_audit.py [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_AUDIT = (
    Path(__file__).resolve().parents[3]
    / "architecture"
    / "policy_design_case"
    / "layer3_gy_task0_audit"
    / "layer3_gy_foundry_breadth_audit.json"
)

EXPECTED_PATTERNS = {"P01", "P02", "P03", "P10", "P12", "P14"}
EXPECTED_FAMILIES = {"causal", "econometrics", "forecasting", "ml", "survey", "validation"}
EXPECTED_PINNED_BY_TOP = {
    "causal": 151,
    "econometrics": 1,
    "forecasting": 10,
    "ml": 5,
    "survey": 1,
    "validation": 4,
}
EXPECTED_BROAD_BY_TOP = {
    "bayesian": 19,
    "causal": 151,
    "econometrics": 26,
    "forecasting": 10,
    "microsim": 6,
    "ml": 15,
    "survey": 1,
    "validation": 4,
}
EXPECTED_HASHES = {
    "causal": "sha256:51805880a4682c2bf1e68f0c49ad1e0e3ffc71e9026f5380bd9acce1559bdb65",
    "econometrics": "sha256:aee398df85af558259cfeb56e569f8b815e161455afa2da50381c260bddcac31",
    "forecasting": "sha256:892aa0cceafcb09779551d3e93dfb8aae28bbd409b2ebd1420807d15779fbee5",
    "ml": "sha256:118ea4f1ad3ced65e4b439087039c5428f514f2d92fd434ac4fc45c42d85a057",
    "survey": "sha256:1934b17b5629ea5bd846b2cea0bf76ba009d94e624e44882a3c0fc3f668365d3",
    "validation": "sha256:0b61a38524a75ecbfe3ec86fc9ebc8a7ff43be6fb07d7320611dc946157de279",
}
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _nested(mapping: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = mapping
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _smokes(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = audit.get("direct_smokes")
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("top_family"), str):
            out[str(row["top_family"])] = row
    return out


def validate(audit: dict[str, Any]) -> list[dict[str, Any]]:
    """Return audit integrity violations."""
    violations: list[dict[str, Any]] = []

    if audit.get("schema_version") != "layer3_gy_foundry_breadth_audit.v1":
        violations.append({"code": "bad_schema_version", "detail": audit.get("schema_version")})

    methodology = audit.get("methodology")
    if not isinstance(methodology, dict):
        violations.append({"code": "missing_methodology", "detail": "methodology missing"})
        methodology = {}
    if methodology.get("agents_used") is not False:
        violations.append({"code": "agent_scope_drift", "detail": methodology.get("agents_used")})
    if methodology.get("network_fetches_run") is not False:
        violations.append({"code": "network_scope_laundering", "detail": "network fetches not in scope"})
    if methodology.get("direct_invocation") != "registry.get(fqn).pure_step(state, params)":
        violations.append({"code": "direct_invocation_drift", "detail": methodology.get("direct_invocation")})

    classification = audit.get("classification")
    if not isinstance(classification, dict):
        violations.append({"code": "missing_classification", "detail": "classification missing"})
        classification = {}
    expected_classification = {
        "primary": "representative_direct_smoke_breadth_only",
        "gap_class": "producer_without_consumer",
        "route_pinned": True,
        "registry_catalog_dag_consumed": True,
        "method_outputs_dag_consumed": False,
        "repair_before_downstream_governance": True,
        "capability_label": "direct_producer_smoked_but_route_consumer_blocked_upstream",
    }
    for key, expected in expected_classification.items():
        if classification.get(key) != expected:
            violations.append({
                "code": "classification_drift",
                "detail": f"{key}={classification.get(key)!r}; expected {expected!r}",
            })
    patterns = set(classification.get("patterns") or [])
    if not patterns >= EXPECTED_PATTERNS:
        violations.append({"code": "pattern_coverage_drift", "detail": sorted(patterns)})

    summary = audit.get("summary")
    if not isinstance(summary, dict):
        violations.append({"code": "missing_summary", "detail": "summary missing"})
        summary = {}
    expected_summary = {
        "live_registry_total_including_dev_scan": 390,
        "builtin_registry_total_excluding_example_dev_scan": 389,
        "pinned_route_relevant_count": 172,
        "broad_live_tag_envelope_count": 232,
        "pinned_route_family_count": 6,
        "direct_smoke_family_count": 6,
        "direct_smoke_pass_count": 6,
        "direct_smoke_fail_count": 0,
        "direct_smoke_only": True,
        "dag_consumed_method_outputs_count": 0,
        "dag_blocker_node": "run_hierarchical_policy_search",
        "dag_blocker_error_code": "node.invalid_state",
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            violations.append({
                "code": "summary_semantics_drift",
                "detail": f"{key}={summary.get(key)!r}; expected {expected!r}",
            })
    if summary.get("dag_skipped_method_nodes") != ["compile_foundry", "run_simulation"]:
        violations.append({
            "code": "dag_skip_truth_drift",
            "detail": summary.get("dag_skipped_method_nodes"),
        })
    if "lower >= upper" not in str(summary.get("dag_blocker_message", "")):
        violations.append({"code": "dag_blocker_message_drift", "detail": summary.get("dag_blocker_message")})
    if summary.get("pinned_route_relevant_count") == summary.get("broad_live_tag_envelope_count"):
        violations.append({
            "code": "route_envelope_collapsed",
            "detail": "pinned 172 and broad 232 envelopes must remain distinct",
        })

    pinned = _nested(audit, ("route_relevance", "pinned_legacy_filter"))
    broad = _nested(audit, ("route_relevance", "broad_live_tag_envelope"))
    if not isinstance(pinned, dict):
        violations.append({"code": "missing_pinned_route_filter", "detail": "pinned filter missing"})
        pinned = {}
    if not isinstance(broad, dict):
        violations.append({"code": "missing_broad_route_envelope", "detail": "broad envelope missing"})
        broad = {}
    if pinned.get("count") != 172 or pinned.get("by_top_family") != EXPECTED_PINNED_BY_TOP:
        violations.append({
            "code": "pinned_route_filter_drift",
            "detail": {"count": pinned.get("count"), "by_top_family": pinned.get("by_top_family")},
        })
    if broad.get("count") != 232 or broad.get("by_top_family") != EXPECTED_BROAD_BY_TOP:
        violations.append({
            "code": "broad_route_envelope_drift",
            "detail": {"count": broad.get("count"), "by_top_family": broad.get("by_top_family")},
        })
    if "bayesian" in (pinned.get("by_top_family") or {}):
        violations.append({
            "code": "pinned_filter_overexpanded",
            "detail": "bayesian belongs to broad envelope, not the pinned 172 filter",
        })

    smokes = _smokes(audit)
    if set(smokes) != EXPECTED_FAMILIES:
        violations.append({"code": "direct_smoke_family_drift", "detail": sorted(smokes)})
    for family in EXPECTED_FAMILIES:
        row = smokes.get(family)
        if not isinstance(row, dict):
            continue
        if row.get("status") != "pass":
            violations.append({"code": "direct_smoke_not_pass", "detail": f"{family}={row.get('status')!r}"})
        if row.get("evidence_kind") != "direct_smoke_only":
            violations.append({"code": "direct_smoke_laundered", "detail": f"{family} evidence_kind={row.get('evidence_kind')!r}"})
        if row.get("dag_consumed_on_pinned_route") is not False:
            violations.append({"code": "dag_consumption_greenwash", "detail": f"{family} marked DAG-consumed"})
        output_hash = row.get("output_hash")
        if not isinstance(output_hash, str) or not SHA256_RE.fullmatch(output_hash):
            violations.append({"code": "bad_output_hash", "detail": f"{family}={output_hash!r}"})
        elif output_hash != EXPECTED_HASHES[family]:
            violations.append({
                "code": "output_hash_drift",
                "detail": f"{family}={output_hash!r}; expected {EXPECTED_HASHES[family]!r}",
            })

    dag = audit.get("dag_consumption_truth")
    if not isinstance(dag, dict):
        violations.append({"code": "missing_dag_consumption_truth", "detail": "DAG truth missing"})
        dag = {}
    if dag.get("workflow_status") != "fail":
        violations.append({"code": "workflow_status_greenwash", "detail": dag.get("workflow_status")})
    if dag.get("classification") != "blocked_upstream_not_method_failure":
        violations.append({"code": "dag_classification_drift", "detail": dag.get("classification")})
    expected_support = {
        "build_method_catalog_snapshot": "ok",
        "run_preflight": "ok",
        "bind_foundry_inputs": "ok",
        "run_data_plane_gate": "ok",
    }
    if dag.get("foundry_support_nodes") != expected_support:
        violations.append({"code": "foundry_support_node_drift", "detail": dag.get("foundry_support_nodes")})
    if dag.get("method_execution_nodes") != {"compile_foundry": "skip", "run_simulation": "skip"}:
        violations.append({"code": "method_execution_node_greenwash", "detail": dag.get("method_execution_nodes")})
    if _nested(dag, ("blocking_node", "alias")) != "run_hierarchical_policy_search":
        violations.append({"code": "blocking_node_drift", "detail": dag.get("blocking_node")})

    acceptance = audit.get("acceptance_signal")
    if not isinstance(acceptance, list):
        violations.append({"code": "missing_acceptance_signal", "detail": "acceptance_signal missing"})
        acceptance = []
    required_phrases = {
        "all direct smokes are marked direct_smoke_only",
        "dag_consumed_method_outputs_count remains 0",
        "pinned 172 filter and broad 232 envelope remain distinct",
        "gap_class remains producer_without_consumer",
    }
    acceptance_text = "\n".join(str(item) for item in acceptance)
    for phrase in required_phrases:
        if phrase not in acceptance_text:
            violations.append({"code": "missing_acceptance_guardrail", "detail": phrase})

    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not args.audit.exists():
        print(f"FAIL: Foundry breadth audit not found: {args.audit}", file=sys.stderr)
        return 2
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    violations = validate(audit)
    report = {
        "audit": str(args.audit),
        "status": "pass" if not violations else "fail",
        "violation_count": len(violations),
        "violations": violations,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"GY Foundry breadth audit check: {report['status'].upper()}")
        print(f"  violations={report['violation_count']}")
        for violation in violations:
            print(f"  - {violation['code']}: {violation['detail']}")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
