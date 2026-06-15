#!/usr/bin/env python3
"""Validate the GY connector-family truth audit artifact.

This check protects the Task 0 audit result that connector rows are not
interchangeable. It does not claim every connector fetches successfully over
the network; it asserts that the artifact preserves the current mechanical
truth about catalog binding shape versus concrete connector fetch contracts.

Usage:
    python3 tools/quality/validation/check_layer3_gy_connector_family_truth_audit.py [--json]
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
    / "layer3_gy_connector_family_truth_audit.json"
)

REQUIRED_CONNECTORS = {
    "worldbank.wdi",
    "ckan.resource",
    "sdmx.source",
    "eurostat.data",
    "unesco_uis.data",
    "socrata.soda",
    "opendatasoft.ods",
    "rest.json",
    "wvs.wave7",
    "who.indicators",
    "unpd.data",
    "ukons.datasets",
}

EXPECTED_STATUS_COUNTS = {
    "shape_pass": 8,
    "shape_warn": 1,
    "contract_mismatch": 2,
    "not_execution_ready": 1,
}

EXPECTED_ROW_STATUSES = {
    "rest.json": "contract_mismatch",
    "unpd.data": "contract_mismatch",
    "ukons.datasets": "not_execution_ready",
    "sdmx.source": "shape_warn",
}

EXPECTED_BLOCKERS = {"rest.json", "unpd.data", "ukons.datasets"}
EXPECTED_WARN_ONLY = {"sdmx.source"}
ALLOWED_GAP_LABELS = {
    "producer_missing",
    "bridge_missing",
    "semantic_test_missing",
}


def _row_map(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = audit.get("connector_rows")
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        connector_id = row.get("connector_id")
        if isinstance(connector_id, str) and connector_id:
            out[connector_id] = row
    return out


def _check_by_id(row: dict[str, Any], check_id: str) -> dict[str, Any] | None:
    checks = row.get("shape_checks")
    if not isinstance(checks, list):
        return None
    for check in checks:
        if isinstance(check, dict) and check.get("id") == check_id:
            return check
    return None


def _labels(row: dict[str, Any]) -> set[str]:
    labels = row.get("gap_labels")
    return set(labels) if isinstance(labels, list) else set()


def validate(audit: dict[str, Any]) -> list[dict[str, Any]]:
    """Return audit integrity violations."""
    violations: list[dict[str, Any]] = []
    if audit.get("schema_version") != "layer3_gy_connector_family_truth_audit.v1":
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
            "detail": "artifact must not claim all-family network replay coverage",
        })

    summary = audit.get("summary")
    if not isinstance(summary, dict):
        violations.append({"code": "missing_summary", "detail": "summary missing"})
        summary = {}

    expected_summary = {
        "route_verdict": "connector_family_truth_mixed_binding_shape_contracts",
        "connector_count": 12,
        "expected_connector_count": 12,
        "missing_connectors": [],
        "all_rows_uniform": False,
        "uniform_connector_exists_claim_rejected": True,
        "requires_family_specific_adapters": True,
        "catalog_binding_shape_validation_required_before_fetch": True,
        "blocking_gap_count": 3,
        "warn_gap_count": 1,
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            violations.append({
                "code": "summary_semantics_drift",
                "detail": f"{key}={summary.get(key)!r}; expected {expected!r}",
            })

    if int(summary.get("production_binding_count_for_12_families") or 0) <= 50_000:
        violations.append({
            "code": "production_binding_scope_too_small",
            "detail": summary.get("production_binding_count_for_12_families"),
        })

    if summary.get("shape_status_counts") != EXPECTED_STATUS_COUNTS:
        violations.append({
            "code": "shape_status_counts_drift",
            "detail": summary.get("shape_status_counts"),
        })

    blockers = set(summary.get("families_with_blocking_shape_gaps") or [])
    if blockers != EXPECTED_BLOCKERS:
        violations.append({
            "code": "blocking_family_set_drift",
            "detail": sorted(blockers),
        })

    warn_only = set(summary.get("families_warn_only") or [])
    if warn_only != EXPECTED_WARN_ONLY:
        violations.append({
            "code": "warn_family_set_drift",
            "detail": sorted(warn_only),
        })

    critical_labels = set(summary.get("critical_gap_labels") or [])
    missing_critical = sorted(ALLOWED_GAP_LABELS - critical_labels)
    if missing_critical:
        violations.append({
            "code": "missing_critical_gap_label",
            "detail": missing_critical,
        })

    rows_by_id = _row_map(audit)
    if not rows_by_id:
        violations.append({
            "code": "missing_connector_rows",
            "detail": "connector_rows missing or empty",
        })
        return violations

    missing_rows = sorted(REQUIRED_CONNECTORS - set(rows_by_id))
    extra_rows = sorted(set(rows_by_id) - REQUIRED_CONNECTORS)
    if missing_rows:
        violations.append({"code": "missing_connector_row", "detail": missing_rows})
    if extra_rows:
        violations.append({"code": "unexpected_connector_row", "detail": extra_rows})

    for connector_id, row in sorted(rows_by_id.items()):
        for field in (
            "connector_family",
            "binding_count",
            "execution_tier_counts",
            "representative_binding",
            "fetch_contract",
            "shape_status",
            "shape_checks",
            "gap_labels",
            "pattern_ids",
            "stage",
            "capability_state",
            "authority_risk",
            "evidence_refs",
            "next_probe",
        ):
            if row.get(field) in (None, "", [], {}):
                if field == "gap_labels" and row.get("shape_status") == "shape_pass":
                    continue
                violations.append({
                    "code": "missing_connector_row_field",
                    "detail": f"{connector_id}.{field}",
                })

        labels = row.get("gap_labels")
        if isinstance(labels, list):
            unknown = sorted(set(labels) - ALLOWED_GAP_LABELS)
            if unknown:
                violations.append({
                    "code": "unknown_gap_label",
                    "detail": f"{connector_id}: {unknown}",
                })
        else:
            violations.append({"code": "bad_gap_labels", "detail": connector_id})

        checks = row.get("shape_checks")
        if not isinstance(checks, list) or not checks:
            violations.append({"code": "missing_shape_checks", "detail": connector_id})
        else:
            for check in checks:
                if not isinstance(check, dict):
                    violations.append({
                        "code": "bad_shape_check",
                        "detail": connector_id,
                    })
                    continue
                if check.get("id") in (None, "") or check.get("status") not in {
                    "pass",
                    "warn",
                    "fail",
                }:
                    violations.append({
                        "code": "bad_shape_check",
                        "detail": f"{connector_id}: {check}",
                    })

        evidence_refs = row.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not any(
            str(ref).endswith("dataset_catalog.duckdb") for ref in evidence_refs
        ):
            violations.append({
                "code": "missing_catalog_evidence_ref",
                "detail": connector_id,
            })
        if not isinstance(evidence_refs, list) or not any(
            str(ref).startswith("src/polisyos/fabric/connectors/") for ref in evidence_refs
        ):
            violations.append({
                "code": "missing_connector_code_evidence_ref",
                "detail": connector_id,
            })

    for connector_id, expected_status in EXPECTED_ROW_STATUSES.items():
        row = rows_by_id.get(connector_id)
        if row is None:
            continue
        if row.get("shape_status") != expected_status:
            violations.append({
                "code": "required_connector_status_changed",
                "detail": f"{connector_id}={row.get('shape_status')!r}; expected {expected_status!r}",
            })

    rest_row = rows_by_id.get("rest.json", {})
    rest_check = _check_by_id(rest_row, "request_dataset_id_controls_endpoint")
    if not rest_check or rest_check.get("status") != "fail":
        violations.append({
            "code": "rest_endpoint_contract_gap_missing",
            "detail": "rest.json must preserve request_dataset_id versus profile endpoint mismatch",
        })
    for label in ("producer_missing", "bridge_missing", "semantic_test_missing"):
        if label not in _labels(rest_row):
            violations.append({
                "code": "rest_gap_label_missing",
                "detail": label,
            })

    unpd_row = rows_by_id.get("unpd.data", {})
    for check_id in ("location_filter_present", "time_filter_present"):
        check = _check_by_id(unpd_row, check_id)
        if not check or check.get("status") != "fail":
            violations.append({
                "code": "unpd_required_filter_gap_missing",
                "detail": check_id,
            })
    for label in ("bridge_missing", "semantic_test_missing"):
        if label not in _labels(unpd_row):
            violations.append({
                "code": "unpd_gap_label_missing",
                "detail": label,
            })

    ukons_row = rows_by_id.get("ukons.datasets", {})
    ukons_check = _check_by_id(ukons_row, "binding_execution_tier_fetchable")
    if not ukons_check or ukons_check.get("status") != "fail":
        violations.append({
            "code": "ukons_catalog_tier_gap_missing",
            "detail": "ukons.datasets must remain catalog-tier-only in this audit",
        })
    for label in ("producer_missing", "bridge_missing", "semantic_test_missing"):
        if label not in _labels(ukons_row):
            violations.append({
                "code": "ukons_gap_label_missing",
                "detail": label,
            })

    sdmx_row = rows_by_id.get("sdmx.source", {})
    sdmx_check = _check_by_id(sdmx_row, "dimension_key_bound")
    if not sdmx_check or sdmx_check.get("status") != "warn":
        violations.append({
            "code": "sdmx_dimension_warning_missing",
            "detail": "sdmx.source must preserve unbounded dimension-key warning",
        })

    fetch_contracts = {
        json.dumps(row.get("fetch_contract"), sort_keys=True)
        for row in rows_by_id.values()
        if isinstance(row.get("fetch_contract"), dict)
    }
    if len(fetch_contracts) < 10:
        violations.append({
            "code": "family_contracts_too_uniform",
            "detail": len(fetch_contracts),
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
        print("PASS: GY connector-family truth audit artifact is internally consistent.")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
