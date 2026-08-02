#!/usr/bin/env python3
"""Validate the GY catalog-binding -> fetch -> measurement-root audit artifact.

This check protects Task 0 audit integrity. It does not assert that the product
is correct; it asserts that the artifact still records the current mechanical
truth: real catalog binding works under injection, real connector fetch works,
and the retrieval execution path still lacks a persisted measurement root.

Usage:
    python3 tools/quality/validation/check_layer3_gy_catalog_fetch_audit.py [--json]
"""
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
    / "layer3_gy_catalog_fetch_audit.json"
)

REQUIRED_ROUTE_ROWS = {
    "catalog.store.resolve_metric_bindings",
    "retrieval.service.catalog_bridge",
    "runtime.control.data_resolve.default_composition",
    "runtime.nl_pipeline.retrieval_service.default_composition",
    "fetch.executor.preview_execute.real_connector",
    "fetch.executor.persist_payload_true",
    "contracts.data_context_metric_surface",
    "nl.retrieval_materialization.derived_snapshot",
    "ingest.fetch_plan_root_producer",
    "source_contract.admissibility_join",
    "replay.conformance.measurement_equivalence",
}

REQUIRED_GAP_LABELS = {
    "implemented_but_not_orchestrated",
    "artifact_missing",
    "bridge_missing",
    "surface_missing",
    "verification_missing",
    "semantic_test_missing",
}


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


def _nested(mapping: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = mapping
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def validate(audit: dict[str, Any]) -> list[dict[str, Any]]:
    """Return audit integrity violations."""
    violations: list[dict[str, Any]] = []
    if audit.get("schema_version") != "layer3_gy_catalog_fetch_audit.v1":
        violations.append({
            "code": "bad_schema_version",
            "detail": audit.get("schema_version"),
        })

    probe = audit.get("probe")
    if not isinstance(probe, dict):
        violations.append({"code": "missing_probe", "detail": "probe must be an object"})
        probe = {}

    summary = audit.get("summary")
    if not isinstance(summary, dict):
        violations.append({"code": "missing_summary", "detail": "summary must be an object"})
        summary = {}

    expected_summary = {
        "route_verdict": "partial_route_measurement_root_missing",
        "catalog_binding_runs_on_real_catalog": True,
        "catalog_to_fetch_plan_runs_when_dataset_catalog_injected": True,
        "default_runtime_injects_dataset_catalog": False,
        "default_nl_pipeline_injects_dataset_catalog": False,
        "real_connector_fetch_runs_for_probe_plan": True,
        "fetch_executor_persist_payload_true_writes_cas": False,
        "fetch_executor_metric_exposes_payload_or_root_ref": False,
        "normal_nl_fetch_execute_persist_payload": False,
        "ingestion_root_producer_exists_separately": True,
        "retrieval_to_ingestion_bridge_exists": False,
        "measurement_root_chain_status": "missing_on_retrieval_execute_path",
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            violations.append({
                "code": "summary_semantics_drift",
                "detail": f"{key}={summary.get(key)!r}; expected {expected!r}",
            })

    declared_gap_labels = summary.get("critical_gap_labels")
    if not isinstance(declared_gap_labels, list):
        violations.append({
            "code": "missing_critical_gap_labels",
            "detail": "summary.critical_gap_labels must be a list",
        })
    else:
        missing_labels = sorted(REQUIRED_GAP_LABELS - set(declared_gap_labels))
        if missing_labels:
            violations.append({
                "code": "missing_critical_gap_label",
                "detail": missing_labels,
            })

    counts = _nested(probe, ("production_catalog", "counts"))
    if not isinstance(counts, dict):
        violations.append({
            "code": "missing_catalog_counts",
            "detail": "probe.production_catalog.counts missing",
        })
    else:
        for table in ("ds_datasets", "ds_distributions", "ds_metric_bindings"):
            if int(counts.get(table) or 0) <= 0:
                violations.append({
                    "code": "empty_catalog_count",
                    "detail": f"{table}={counts.get(table)!r}",
                })

    if int(_nested(probe, ("real_catalog_binding", "binding_count")) or 0) <= 0:
        violations.append({
            "code": "catalog_binding_not_proven",
            "detail": "real_catalog_binding.binding_count must be positive",
        })

    if int(_nested(probe, ("catalog_to_fetch_plan", "fetch_plan_count")) or 0) <= 0:
        violations.append({
            "code": "catalog_fetch_plan_not_proven",
            "detail": "catalog_to_fetch_plan.fetch_plan_count must be positive",
        })
    if _nested(probe, ("catalog_to_fetch_plan", "lane_used")) != "catalog":
        violations.append({
            "code": "catalog_lane_not_selected",
            "detail": _nested(probe, ("catalog_to_fetch_plan", "lane_used")),
        })
    if _nested(probe, ("catalog_to_fetch_plan", "top_plan", "source_lane")) != "catalog":
        violations.append({
            "code": "top_plan_not_catalog_lane",
            "detail": _nested(probe, ("catalog_to_fetch_plan", "top_plan", "source_lane")),
        })

    if _nested(probe, ("real_connector_persist_payload_true", "status")) != "ok":
        violations.append({
            "code": "real_connector_fetch_not_ok",
            "detail": _nested(probe, ("real_connector_persist_payload_true", "status")),
        })
    if int(_nested(probe, ("real_connector_persist_payload_true", "row_count")) or 0) <= 0:
        violations.append({
            "code": "real_connector_rows_missing",
            "detail": _nested(probe, ("real_connector_persist_payload_true", "row_count")),
        })

    for path, code in (
        (("fake_connector_persist_payload_true", "cas_file_delta_count"), "fake_persist_payload_wrote_cas"),
        (("real_connector_persist_payload_true", "cas_file_delta_count"), "real_persist_payload_wrote_cas"),
    ):
        if _nested(probe, path) != 0:
            violations.append({"code": code, "detail": f"{'.'.join(path)} changed"})

    if _nested(probe, ("fake_connector_persist_payload_true", "data_context_metric_has_artifact_ref")) is not False:
        violations.append({
            "code": "data_context_metric_artifact_ref_changed",
            "detail": "artifact/root fields changed without updating the audit",
        })

    ingestion_static = probe.get("separate_ingestion_root_producer_static")
    if not isinstance(ingestion_static, dict):
        violations.append({
            "code": "missing_ingestion_static",
            "detail": "probe.separate_ingestion_root_producer_static missing",
        })
    else:
        expected = {
            "status": "implemented_separately_not_bridged",
            "ingest_request_accepts_fetch_plans": True,
            "normal_retrieval_calls_ingest": False,
        }
        for key, value in expected.items():
            if ingestion_static.get(key) != value:
                violations.append({
                    "code": "ingestion_bridge_semantics_drift",
                    "detail": f"{key}={ingestion_static.get(key)!r}; expected {value!r}",
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
            unknown = sorted(set(labels) - REQUIRED_GAP_LABELS)
            if unknown:
                violations.append({
                    "code": "unknown_gap_label",
                    "detail": f"{route_id}: {unknown}",
                })
        else:
            violations.append({
                "code": "bad_gap_labels",
                "detail": route_id,
            })

    expected_row_states = {
        "runtime.control.data_resolve.default_composition": "implemented_but_not_orchestrated",
        "runtime.nl_pipeline.retrieval_service.default_composition": "implemented_but_not_orchestrated",
        "fetch.executor.persist_payload_true": "artifact_missing",
        "nl.retrieval_materialization.derived_snapshot": "artifact_missing_for_raw_fetch_root",
        "ingest.fetch_plan_root_producer": "producer_present_but_not_bridged_to_retrieval_execute",
        "source_contract.admissibility_join": "verification_missing",
        "replay.conformance.measurement_equivalence": "verification_missing",
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

    persist_row = rows_by_id.get("fetch.executor.persist_payload_true", {})
    persist_labels = set(persist_row.get("gap_labels") or [])
    for label in ("artifact_missing", "bridge_missing", "surface_missing", "semantic_test_missing"):
        if label not in persist_labels:
            violations.append({
                "code": "persist_payload_gap_label_missing",
                "detail": label,
            })

    ingest_row = rows_by_id.get("ingest.fetch_plan_root_producer", {})
    ingest_labels = set(ingest_row.get("gap_labels") or [])
    if "bridge_missing" not in ingest_labels:
        violations.append({
            "code": "ingestion_bridge_gap_missing",
            "detail": "ingest.fetch_plan_root_producer must remain distinct from retrieval execute",
        })

    findings = audit.get("findings")
    if not isinstance(findings, list) or len(findings) < 5:
        violations.append({
            "code": "missing_findings",
            "detail": "at least five findings required",
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
        print("PASS: GY catalog/fetch audit artifact is internally consistent.")
    return 0 if not violations else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
