#!/usr/bin/env python3
"""Validate the GY Task 0 P1 substrate authority audit artifact.

This check protects the P1 finding that core substrate contracts are not enough
for authority: CAS bytes can be valid while DAG authority events, bitemporal
admission, raw-route redaction, and exact S12 producer refs remain incomplete.
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
    / "layer3_gy_p1_substrate_authority_audit.json"
)

REQUIRED_PATTERNS = {"P01", "P02", "P03", "P05", "P07", "P08", "P10", "P13", "P15", "P25"}
REQUIRED_RISK_AREAS = {
    "CAS integrity/dedup/GC/tamper",
    "time semantics/bitemporality",
    "secrets/PII",
    "cost/VOI/budget",
}
EXPECTED_SUMMARY = {
    "cas_temp_dedup_same_ref": True,
    "cas_temp_artifact_count_after_duplicate_put": 1,
    "cas_temp_blob_tamper_detected_on_verify": True,
    "cas_temp_blob_tamper_detected_on_read": True,
    "cas_temp_reput_after_blob_tamper_heals_blob": False,
    "cas_temp_manifest_tamper_detected_on_verify": True,
    "cas_temp_manifest_tamper_detected_on_read": True,
    "cas_temp_manifest_tamper_detected_on_get_manifest": False,
    "filesystem_cas_gc_api_present": False,
    "p0_dag_cas_manifest_count": 178,
    "p0_dag_cas_authority_manifest_count": 0,
    "production_worker_dag_manifest_count": 99,
    "depth2_valid_snapshot_dag_manifest_count": 71,
    "runtime_authority_writer_present": True,
    "scientist_dag_uses_ordinary_put_json_for_workflow_report": True,
    "artifact_preview_redaction_present": True,
    "artifact_raw_content_route_unredacted": True,
    "artifact_download_route_unredacted": True,
    "pii_detection_stage_exists": True,
    "pii_detection_default_enabled": False,
    "retrieval_fetch_executor_applies_pii_stage": False,
    "ingestion_path_applies_pii_stage_when_enabled": True,
    "connector_probe_payload_files_scanned": 1,
    "connector_probe_secret_pii_hits": 0,
    "selected_secret_match_line_count": 5,
    "selected_secret_match_file_count": 4,
    "selected_pii_match_line_count": 0,
    "runtime_workflow_temporal_surface_supported": False,
    "artifact_content_temporal_surface_supported": False,
    "runtime_temporal_supported_surface_count": 6,
    "runtime_temporal_unsupported_surface_count": 5,
    "pdc_json_files_time_scanned": 277,
    "pdc_catalog_watermark_occurrences": 0,
    "pdc_source_updated_at_occurrences": 0,
    "pdc_legal_as_of_occurrences": 87,
    "pdc_legal_as_of_null_or_empty_occurrences": 44,
    "dag_time_fields_include_source_freshness": False,
    "s12_real_resource_economics_producers_exist": True,
    "g5_s12_pass_refs_exact_producer_artifacts_found": False,
    "g5_s12_pass_uses_authorial_refs": True,
    "run_cost_gate_is_separate_runtime_cost_capability": True,
    "overall_status": "blocked_for_authority_bridging_not_core_contract_absence",
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

    if audit.get("schema_version") != "policyos.policy_design_case.layer3_gy_p1_substrate_authority_audit.v1":
        violations.append(_violation("bad_schema_version", audit.get("schema_version")))
    if audit.get("status") != "pass":
        violations.append(_violation("audit_status_not_pass", audit.get("status")))
    if audit.get("system_readiness") != "blocked_for_high_risk_substrate_authority":
        violations.append(_violation("system_readiness_greenwash", audit.get("system_readiness")))

    methodology = _dict(audit.get("methodology"))
    for key in (
        "code_static_read",
        "temporary_cas_probe_run",
        "p0_dag_cas_manifests_scanned",
        "selected_secret_pii_scan_run",
        "time_field_inventory_run",
        "s12_ref_dereference_run",
    ):
        if methodology.get(key) is not True:
            violations.append(_violation("methodology_missing_probe", key))
    for key in ("agents_used", "network_fetches_run", "runtime_server_started", "fixes_made"):
        if methodology.get(key) is not False:
            violations.append(_violation("methodology_scope_drift", f"{key}={methodology.get(key)!r}"))

    classification = _dict(audit.get("classification"))
    if classification.get("primary") != "high_risk_substrate_authority_partial":
        violations.append(_violation("classification_drift", classification.get("primary")))
    if classification.get("repair_before_downstream_governance") is not True:
        violations.append(_violation("missing_repair_before_governance", classification))
    missing_patterns = sorted(REQUIRED_PATTERNS - _strings(classification.get("patterns")))
    if missing_patterns:
        violations.append(_violation("missing_pattern_register_ids", missing_patterns))

    summary = _dict(audit.get("summary"))
    for key, expected in EXPECTED_SUMMARY.items():
        if summary.get(key) != expected:
            violations.append(
                _violation(
                    "summary_semantics_drift",
                    f"{key}={summary.get(key)!r}; expected {expected!r}",
                )
            )

    cas = _dict(audit.get("cas_integrity_dedup_gc_tamper_evidence"))
    temp_probe = _dict(cas.get("temporary_probe"))
    expected_temp = {
        "dedup_same_ref": True,
        "artifact_count_after_duplicate_put": 1,
        "blob_tamper_verify_ok": False,
        "blob_tamper_get_bytes_exception": "ArtifactIntegrityError",
        "reput_after_blob_tamper_same_ref": True,
        "reput_after_blob_tamper_verify_ok": False,
        "manifest_tamper_verify_ok": False,
        "manifest_tamper_get_manifest_exception": None,
        "manifest_tamper_get_bytes_exception": "ArtifactIntegrityError",
        "filesystem_cas_gc_like_methods": [],
    }
    for key, expected in expected_temp.items():
        if temp_probe.get(key) != expected:
            violations.append(_violation("cas_probe_drift", f"{key}={temp_probe.get(key)!r}"))
    manifest_scan = _dict(cas.get("p0_dag_manifest_scan"))
    if manifest_scan.get("total_manifest_count") != 178:
        violations.append(_violation("p0_cas_manifest_count_drift", manifest_scan.get("total_manifest_count")))
    if manifest_scan.get("authority_manifest_count") != 0:
        violations.append(_violation("dag_authority_manifest_greenwash", manifest_scan.get("authority_manifest_count")))
    bridge_rows = _list(cas.get("authority_bridge_map"))
    if not any(_dict(row).get("status") == "cas_integrity_only_no_runtime_authority_manifest" for row in bridge_rows):
        violations.append(_violation("missing_dag_authority_gap_row", bridge_rows))

    time = _dict(audit.get("time_semantics_bitemporality"))
    capabilities = _dict(time.get("runtime_temporal_capabilities"))
    unsupported = set(str(item) for item in _list(capabilities.get("unsupported_surfaces")))
    for surface in ("run_workflow", "run_nodes", "artifact_content"):
        if surface not in unsupported:
            violations.append(_violation("temporal_unsupported_surface_greenwash", surface))
    pdc_time = _dict(time.get("pdc_time_field_inventory"))
    occurrences = _dict(pdc_time.get("field_occurrences"))
    if occurrences.get("catalog_watermark") != 0 or occurrences.get("source_updated_at") != 0:
        violations.append(_violation("source_time_field_count_greenwash", occurrences))
    nulls = _dict(pdc_time.get("null_or_empty_occurrences"))
    if nulls.get("legal_as_of") != 44:
        violations.append(_violation("legal_time_null_count_drift", nulls.get("legal_as_of")))

    secret = _dict(audit.get("secrets_pii_scan"))
    if secret.get("selected_secret_match_line_count") != 5:
        violations.append(_violation("secret_scan_count_drift", secret.get("selected_secret_match_line_count")))
    if secret.get("selected_pii_match_line_count") != 0:
        violations.append(_violation("pii_scan_count_drift", secret.get("selected_pii_match_line_count")))
    connector_payload_scan = _dict(secret.get("connector_probe_payload_scan"))
    if connector_payload_scan.get("files_scanned") != 1 or connector_payload_scan.get("secret_hits") != 0:
        violations.append(_violation("connector_payload_scan_drift", connector_payload_scan))
    secret_hits = _list(secret.get("secret_hits"))
    if not any(_dict(hit).get("classification") == "raw_dag_bundle_secret_like_fixture_leak" for hit in secret_hits):
        violations.append(_violation("missing_raw_dag_secret_hit", secret_hits))
    route_behavior = _dict(secret.get("route_behavior"))
    if route_behavior.get("artifact_raw_content_route_unredacted") is not True:
        violations.append(_violation("raw_content_route_greenwash", route_behavior))
    if route_behavior.get("artifact_download_route_unredacted") is not True:
        violations.append(_violation("download_route_greenwash", route_behavior))
    pii = _dict(secret.get("pii_stage_wiring"))
    if pii.get("default_enabled") is not False:
        violations.append(_violation("pii_default_greenwash", pii))
    if pii.get("retrieval_fetch_executor_applies_stage") is not False:
        violations.append(_violation("retrieval_pii_wiring_greenwash", pii))

    cost = _dict(audit.get("cost_voi_budget_honesty"))
    producers = _dict(cost.get("s12_real_producers"))
    if producers.get("exists") is not True:
        violations.append(_violation("s12_producer_absence_misstated", producers))
    g5_refs = _dict(cost.get("g5_s12_pass_exact_refs"))
    if g5_refs.get("exact_producer_artifacts_found") is not False:
        violations.append(_violation("g5_s12_exact_ref_greenwash", g5_refs))
    if g5_refs.get("classification") != "authorial_refs_in_g5_handoff_not_measured_exact_s12_objects":
        violations.append(_violation("g5_s12_classification_drift", g5_refs.get("classification")))
    run_cost = _dict(cost.get("runtime_run_cost_gate"))
    if run_cost.get("separate_capability") is not True or run_cost.get("not_equivalent_to_s12_voi_budget_honesty") is not True:
        violations.append(_violation("run_cost_gate_equivalence_greenwash", run_cost))

    risk_rows = _list(audit.get("substrate_authority_risk_matrix"))
    risk_areas = {str(_dict(row).get("area")) for row in risk_rows}
    missing_areas = sorted(REQUIRED_RISK_AREAS - risk_areas)
    if missing_areas:
        violations.append(_violation("missing_risk_matrix_rows", missing_areas))
    for row_obj in risk_rows:
        row = _dict(row_obj)
        if not str(row.get("must_not_count_as", "")).strip():
            violations.append(_violation("risk_row_missing_negative_boundary", row.get("area")))

    acceptance = " ".join(str(item) for item in _list(audit.get("acceptance_signal_for_future_repairs")))
    for phrase in (
        "runtime authority writer",
        "not_publishable",
        "single temporal admission envelope",
        "G5 S12 refs dereference",
    ):
        if phrase not in acceptance:
            violations.append(_violation("missing_acceptance_signal", phrase))

    return violations


def main() -> int:
    """Run the P1 substrate authority audit validator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    violations = validate(audit)
    if args.json:
        print(json.dumps({"status": "fail" if violations else "pass", "violations": violations}, indent=2))
    elif violations:
        print("FAIL layer3_gy_p1_substrate_authority_audit")
        for violation in violations:
            print(f"- {violation['code']}: {violation['detail']}")
    else:
        print("PASS layer3_gy_p1_substrate_authority_audit")
    return 1 if violations else 0


if __name__ == "__main__":
    import sys

    from tools.lib.timing import run_timed_entrypoint

    raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
