#!/usr/bin/env python3
"""Validate the GY runtime/API/dashboard/public-export surface audit artifact.

The check is intentionally about audit integrity, not product correctness. It
fails when the artifact stops proving the laundering risk that Task 0 needs:
failed workflow fixture, 200 responses across runtime surface probes, critical
surface rows, and explicit gap labels for bridge/consumer/semantic-test holes.

Usage:
    python3 tools/quality/validation/check_layer3_gy_runtime_surface_audit.py [--json]
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
    / "layer3_gy_runtime_surface_audit.json"
)

REQUIRED_SURFACES = {
    "runtime.api.runs.list",
    "runtime.api.runs.details",
    "runtime.api.runs.workflow",
    "runtime.api.artifacts.manifest",
    "runtime.api.artifacts.content",
    "runtime.api.artifacts.lineage",
    "runtime.api.lineage.graph",
    "runtime.api.lineage.openlineage_export",
    "runtime.api.lineage.prov_export",
    "runtime.api.bureaucratic.render",
    "runtime.api.bureaucratic.export",
    "dashboard.workflow_tab",
    "dashboard.run_detail_score_and_explainability",
    "dashboard.public_packet_builder",
    "dashboard.public_viewer",
}

ALLOWED_RISKS = {"low", "medium", "high", "critical"}
HIGH_OR_CRITICAL = {"high", "critical"}
ALLOWED_GAP_LABELS = {
    "bridge_missing",
    "consumer_missing",
    "semantic_test_missing",
    "surface_missing",
    "verification_missing",
}
REQUIRED_CRITICAL_SURFACES = {
    "runtime.api.artifacts.content",
    "runtime.api.lineage.graph",
    "runtime.api.lineage.openlineage_export",
    "runtime.api.bureaucratic.render",
    "runtime.api.bureaucratic.export",
    "dashboard.run_detail_score_and_explainability",
    "dashboard.public_packet_builder",
}


def validate(audit: dict[str, Any]) -> list[dict[str, Any]]:
    """Return audit integrity violations."""
    violations: list[dict[str, Any]] = []
    if audit.get("schema_version") != "layer3_gy_runtime_surface_audit.v1":
        violations.append({
            "code": "bad_schema_version",
            "detail": audit.get("schema_version"),
        })

    probe = audit.get("probe")
    if not isinstance(probe, dict):
        violations.append({"code": "missing_probe", "detail": "probe must be an object"})
        probe = {}

    fixture = probe.get("fixture")
    if not isinstance(fixture, dict):
        violations.append({"code": "missing_fixture", "detail": "probe.fixture must be an object"})
        fixture = {}
    else:
        expected_fixture = {
            "indexed_run_status": "fail",
            "indexed_execution_profile": "governed",
            "indexed_has_workflow_report": True,
            "indexed_decision_validity_status": "warning",
        }
        for key, expected in expected_fixture.items():
            if fixture.get(key) != expected:
                violations.append({
                    "code": "fixture_semantics_drift",
                    "detail": f"{key}={fixture.get(key)!r}; expected {expected!r}",
                })

    route_status_codes = probe.get("route_status_codes")
    if not isinstance(route_status_codes, dict) or not route_status_codes:
        violations.append({
            "code": "missing_route_status_codes",
            "detail": "probe.route_status_codes must be a non-empty object",
        })
        route_status_codes = {}
    declared_route_count = probe.get("route_count")
    if declared_route_count != len(route_status_codes):
        violations.append({
            "code": "route_count_mismatch",
            "detail": f"route_count={declared_route_count!r}; actual={len(route_status_codes)}",
        })
    for route_name, status_code in sorted(route_status_codes.items()):
        if status_code != 200:
            violations.append({
                "code": "probe_route_not_200",
                "detail": f"{route_name} returned {status_code!r}",
            })

    rows = audit.get("surface_rows")
    if not isinstance(rows, list) or not rows:
        return violations + [{"code": "no_surface_rows", "detail": "surface_rows missing"}]

    by_id: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            violations.append({
                "code": "bad_surface_row",
                "detail": f"row {index} is not an object",
            })
            continue
        surface_id = row.get("surface_id")
        if not isinstance(surface_id, str) or not surface_id:
            violations.append({
                "code": "missing_surface_id",
                "detail": f"row {index}",
            })
            continue
        if surface_id in by_id:
            violations.append({
                "code": "duplicate_surface_id",
                "detail": surface_id,
            })
        by_id[surface_id] = row

        for field in (
            "surface_kind",
            "entrypoint",
            "producer_input",
            "observed_projection",
            "authority_projection",
            "laundering_risk",
            "gap_labels",
            "pattern_ids",
            "evidence_refs",
            "next_probe",
        ):
            if field not in row or row[field] in (None, "", [], {}):
                violations.append({
                    "code": "missing_surface_field",
                    "detail": f"{surface_id}.{field}",
                })

        risk = row.get("laundering_risk")
        if risk not in ALLOWED_RISKS:
            violations.append({
                "code": "bad_laundering_risk",
                "detail": f"{surface_id}: {risk!r}",
            })

        labels = row.get("gap_labels")
        if not isinstance(labels, list) or not labels:
            continue
        unknown_labels = sorted(set(labels) - ALLOWED_GAP_LABELS)
        if unknown_labels:
            violations.append({
                "code": "bad_gap_label",
                "detail": f"{surface_id}: {unknown_labels}",
            })
        if "semantic_test_missing" not in labels:
            violations.append({
                "code": "surface_without_semantic_test_gap",
                "detail": surface_id,
            })

    missing = sorted(REQUIRED_SURFACES - set(by_id))
    if missing:
        violations.append({"code": "missing_required_surface", "detail": missing})

    for surface_id in sorted(REQUIRED_CRITICAL_SURFACES):
        row = by_id.get(surface_id)
        if row is None:
            continue
        if row.get("laundering_risk") != "critical":
            violations.append({
                "code": "required_critical_surface_downgraded",
                "detail": f"{surface_id}: {row.get('laundering_risk')!r}",
            })

    content_row = by_id.get("runtime.api.artifacts.content", {})
    content_projection = content_row.get("observed_projection")
    if not isinstance(content_projection, dict):
        content_projection = {}
    if content_projection.get("nested_secret_like_key_observed") != "error.details.api_token":
        violations.append({
            "code": "missing_raw_secret_observation",
            "detail": "runtime.api.artifacts.content must retain the current raw secret leak finding",
        })
    if content_projection.get("preview_status") != "fail":
        violations.append({
            "code": "missing_failed_content_observation",
            "detail": "runtime.api.artifacts.content must show raw preview_status=fail",
        })

    graph_row = by_id.get("runtime.api.lineage.graph", {})
    graph_projection = graph_row.get("observed_projection")
    if not isinstance(graph_projection, dict):
        graph_projection = {}
    if graph_projection.get("status") != "verified":
        violations.append({
            "code": "missing_verified_failed_lineage_observation",
            "detail": "runtime.api.lineage.graph must retain status=verified observation",
        })

    summary = audit.get("summary")
    if not isinstance(summary, dict):
        violations.append({"code": "missing_summary", "detail": "summary must be an object"})
    else:
        critical_count = sum(
            1 for row in rows if isinstance(row, dict) and row.get("laundering_risk") == "critical"
        )
        high_or_critical_count = sum(
            1
            for row in rows
            if isinstance(row, dict) and row.get("laundering_risk") in HIGH_OR_CRITICAL
        )
        if summary.get("surface_count") != len(rows):
            violations.append({
                "code": "surface_count_mismatch",
                "detail": f"summary={summary.get('surface_count')!r}; actual={len(rows)}",
            })
        if summary.get("critical_count") != critical_count:
            violations.append({
                "code": "critical_count_mismatch",
                "detail": f"summary={summary.get('critical_count')!r}; actual={critical_count}",
            })
        if summary.get("high_or_critical_count") != high_or_critical_count:
            violations.append({
                "code": "high_or_critical_count_mismatch",
                "detail": (
                    f"summary={summary.get('high_or_critical_count')!r}; "
                    f"actual={high_or_critical_count}"
                ),
            })

    return violations


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    violations = validate(_load(args.audit))
    payload = {
        "audit": str(args.audit),
        "status": "pass" if not violations else "fail",
        "issue_count": len(violations),
        "issues": violations,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif violations:
        for issue in violations:
            print(f"{issue['code']}: {issue['detail']}")
    else:
        print(f"PASS {args.audit}")
    return 0 if not violations else 1


if __name__ == "__main__":
    import sys

    from tools.lib.timing import run_timed_entrypoint

    raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
