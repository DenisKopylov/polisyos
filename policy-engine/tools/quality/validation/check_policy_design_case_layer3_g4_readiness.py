#!/usr/bin/env python3
"""Validate and optionally persist the Layer 3 G4 promotion-gate bundle."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from polisyos.runtime.quality import layer3_promotion_gate as g4
from tools.lib.fs import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")
DOCS_REFERENCE_DIR = Path("docs/reference")
G4_SCHEMA_VERSION = g4.LAYER3_G4_SCHEMA_VERSION
G4_RULE_VERSION = g4.LAYER3_G4_RULE_VERSION

DEPENDENCY_READINESS_SNAPSHOT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g4_dependency_readiness_snapshot.json"
)
PROMOTION_INPUT_SET_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g4_promotion_input_set.json"
GROUNDED_CONTRACT_SET_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g4_grounded_contract_set.json"
)
A_COMPLETENESS_LEDGER_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g4_a_completeness_ledger.json"
)
HUMAN_DECISION_INTEGRITY_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g4_human_decision_integrity_gate.json"
)
WEAKEST_BOUNDARY_COMPOSITION_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g4_weakest_boundary_composition.json"
)
PROMOTION_RECORDS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g4_promotion_records.json"
CLOSEOUT_CONSUMER_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g4_closeout_consumer_gate.json"
)
PDC_COMPILER_CONSUMER_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g4_pdc_compiler_consumer_gate.json"
)
G5_PROMOTION_HANDOFF_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g4_g5_promotion_handoff.json"
GOVERNANCE_THROUGHPUT_DELTA_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g4_governance_throughput_delta.json"
)
PROMOTION_AUDIT_SURFACE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g4_promotion_audit_surface.json"
)
PUBLIC_EXPORT_PROJECTION_REFS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g4_public_export_projection_refs.json"
)
CONFORMANCE_REPORT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g4_conformance_report.json"
HEALTH_METRIC_DELTA_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g4_health_metric_delta.toml"
ADAPTER_CONTRACT_REGISTRY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g4_adapter_contract_registry.toml"
)
REGISTRY_RATCHET_DELTA_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g4_registry_ratchet_delta.json"
)
READINESS_MANIFEST_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g4_readiness_manifest.json"

GENERATED_ARTIFACTS_TOML_PATH = Path("architecture/generated_artifacts.toml")
GENERATED_ARTIFACTS_DOC_PATH = DOCS_REFERENCE_DIR / "generated-artifacts.md"
INVENTORY_PATH = POLICY_DESIGN_CASE_DIR / "inventory.json"
DOCS_SURFACE_PATH = DOCS_REFERENCE_DIR / "policy-design-case-layer3-promotion-gate.md"
DOCUMENTATION_INVENTORY_PATH = DOCS_REFERENCE_DIR / "documentation-inventory.md"
REFERENCE_INDEX_PATH = DOCS_REFERENCE_DIR / "index.md"
PUBLIC_SURFACE_DOC_PATH = DOCS_REFERENCE_DIR / "public-surface.md"

EXPECTED_ARTIFACT_PATHS: tuple[Path, ...] = (
    DEPENDENCY_READINESS_SNAPSHOT_PATH,
    PROMOTION_INPUT_SET_PATH,
    GROUNDED_CONTRACT_SET_PATH,
    A_COMPLETENESS_LEDGER_PATH,
    HUMAN_DECISION_INTEGRITY_GATE_PATH,
    WEAKEST_BOUNDARY_COMPOSITION_PATH,
    PROMOTION_RECORDS_PATH,
    CLOSEOUT_CONSUMER_GATE_PATH,
    PDC_COMPILER_CONSUMER_GATE_PATH,
    G5_PROMOTION_HANDOFF_PATH,
    GOVERNANCE_THROUGHPUT_DELTA_PATH,
    PROMOTION_AUDIT_SURFACE_PATH,
    PUBLIC_EXPORT_PROJECTION_REFS_PATH,
    CONFORMANCE_REPORT_PATH,
    HEALTH_METRIC_DELTA_PATH,
    ADAPTER_CONTRACT_REGISTRY_PATH,
    REGISTRY_RATCHET_DELTA_PATH,
    READINESS_MANIFEST_PATH,
)
EXPECTED_MANIFEST_DRIFT_KEYS: tuple[str, ...] = (
    "schema_version",
    "rule_version",
    "g0_dependency_status",
    "g1_dependency_status",
    "g2_context_status",
    "g3_context_status",
    "gl_context_status",
    "g4_dependency_readiness_status",
    "g4_source_design_record_resolution_status",
    "g4_source_design_record_payload_status",
    "g4_source_design_record_digest_status",
    "g4_w12d_payload_source_status",
    "g4_dependency_artifact_shape_status",
    "g4_runtime_promotion_lane_collision_status",
    "g4_generated_artifact_promotion_target_collision_status",
    "g4_promotion_input_count",
    "g4_grounded_contract_set_status",
    "g4_grounded_contract_ref_count",
    "g4_a_completeness_status",
    "g4_a_completeness_requirement_count",
    "g4_a_completeness_missing_requirement_count",
    "g4_human_decision_integrity_status",
    "g4_s7_human_decision_payload_status",
    "g4_high_stakes_human_decision_bypass_status",
    "g4_s7_manifest_only_blocker_count",
    "g4_weakest_boundary_status",
    "g4_promotion_record_count",
    "g4_governed_promoted_count",
    "g4_promotion_blocked_count",
    "g4_may_not_use_for_completeness_status",
    "g4_closeout_consumer_gate_status",
    "g4_pdc_compiler_consumer_gate_status",
    "g4_g5_promotion_handoff_status",
    "g4_public_export_projection_status",
    "g4_public_projection_mode",
    "g4_public_export_hook_status",
    "g4_promotion_surface_status",
    "g4_governance_throughput_status",
    "g4_conformance_status",
    "g4_adapter_contract_registry_status",
    "g4_registry_ratchet_delta_status",
    "g4_promotion_gate_admission_maturity",
    "g4_promotion_gate_admission_conformance_ref_count",
    "g4_generated_artifacts_registration_status",
    "g4_inventory_surface_status",
    "g4_reference_docs_status",
    "g4_health_metric_ids",
)
ALL_ISSUE_CODES: tuple[str, ...] = tuple(dict.fromkeys(g4.ALL_ISSUE_CODES))
SURFACE_AUDIENCES: frozenset[str] = frozenset(("PUBLIC", "REVIEWER", "EXPERT", "MACHINE"))


def validate_layer3_g4_readiness(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    """Build a Layer 3 G4 readiness report from runtime and registered surfaces."""

    root = Path(repo_root).resolve()
    runtime_bundle = g4.build_layer3_g4_bundle(root)
    written_artifact_paths = _write_artifacts(root, runtime_bundle) if write else []
    runtime_report = g4.validate_layer3_g4_bundle(root, runtime_bundle).model_dump(
        mode="json"
    )
    drift_keys = _manifest_runtime_drift_keys(root, runtime_bundle)
    registration_statuses = _registration_statuses(root)
    issues: list[dict[str, str]] = []
    issues.extend(_normalize_issues(runtime_report.get("issues", [])))
    issues.extend(_validate_persisted_artifacts(root))
    issues.extend(_validate_written_artifact_set(written_artifact_paths) if write else [])
    issues.extend(_manifest_runtime_drift_issues(drift_keys))
    issues.extend(_validate_registration_and_docs(root, registration_statuses))
    issues.extend(_validate_runtime_surfaces(runtime_bundle))
    normalized_issues = _deduplicate_issues(issues)
    return {
        "schema_version": G4_SCHEMA_VERSION,
        "status": "fail" if normalized_issues else "pass",
        "issues": normalized_issues,
        "summary": _summary(
            root,
            runtime_bundle,
            runtime_report,
            drift_keys,
            registration_statuses,
        ),
        "artifacts": {
            "expected_artifact_paths": [
                path.as_posix() for path in EXPECTED_ARTIFACT_PATHS
            ],
            "written_artifact_paths": written_artifact_paths,
            "missing_persisted_artifact_paths": [
                path.as_posix()
                for path in EXPECTED_ARTIFACT_PATHS
                if not _resolve_repo_path(root, path).exists()
            ],
        },
        "write": write,
        "issue_code_dictionary": list(ALL_ISSUE_CODES),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Layer 3 G4 readiness check CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    report = validate_layer3_g4_readiness(args.repo_root, write=args.write)
    rendered = (
        _json_dumps(report) if args.output_format == "json" else _render_text_report(report)
    )
    if args.output is not None:
        output_path = _resolve_repo_path(Path(args.repo_root).resolve(), args.output)
        atomic_write_text(output_path, rendered)
    sys.stdout.write(rendered)
    return 0 if report["status"] == "pass" else 1


def _write_artifacts(repo_root: Path, bundle: g4.Layer3G4Bundle) -> list[str]:
    base = {"schema_version": G4_SCHEMA_VERSION, "rule_version": G4_RULE_VERSION}
    payloads: dict[Path, Any] = {
        DEPENDENCY_READINESS_SNAPSHOT_PATH: _dump(bundle.dependency_readiness_snapshot),
        PROMOTION_INPUT_SET_PATH: _dump(bundle.promotion_input_set),
        GROUNDED_CONTRACT_SET_PATH: _dump(bundle.grounded_contract_set),
        A_COMPLETENESS_LEDGER_PATH: _dump(bundle.a_completeness_ledger),
        HUMAN_DECISION_INTEGRITY_GATE_PATH: _dump(bundle.human_decision_integrity_gate),
        WEAKEST_BOUNDARY_COMPOSITION_PATH: _dump(bundle.weakest_boundary_composition),
        PROMOTION_RECORDS_PATH: {
            **base,
            "promotion_records": _dump(bundle.promotion_records),
        },
        CLOSEOUT_CONSUMER_GATE_PATH: _dump(bundle.closeout_consumer_gate),
        PDC_COMPILER_CONSUMER_GATE_PATH: _dump(bundle.pdc_compiler_consumer_gate),
        G5_PROMOTION_HANDOFF_PATH: _dump(bundle.g5_promotion_handoff),
        GOVERNANCE_THROUGHPUT_DELTA_PATH: _dump(bundle.governance_throughput_delta),
        PROMOTION_AUDIT_SURFACE_PATH: _dump(bundle.promotion_audit_surface),
        PUBLIC_EXPORT_PROJECTION_REFS_PATH: _dump(bundle.public_export_projection_refs),
        CONFORMANCE_REPORT_PATH: _dump(bundle.conformance_report),
        REGISTRY_RATCHET_DELTA_PATH: _dump(bundle.registry_ratchet_delta),
        READINESS_MANIFEST_PATH: {
            **bundle.readiness_manifest.summary,
            **_dump(bundle.readiness_manifest),
        },
    }
    written: list[str] = []
    for path in EXPECTED_ARTIFACT_PATHS:
        resolved = _resolve_repo_path(repo_root, path)
        if path == HEALTH_METRIC_DELTA_PATH:
            _write_health_metric_delta(resolved, bundle.health_metric_delta)
        elif path == ADAPTER_CONTRACT_REGISTRY_PATH:
            _write_adapter_contract_registry(resolved, bundle.adapter_contract_registry)
        else:
            _write_json(resolved, payloads[path])
        written.append(path.as_posix())
    return written


def _validate_persisted_artifacts(repo_root: Path) -> list[dict[str, str]]:
    return [
        _issue(
            "layer3_g4_persisted_artifact_missing",
            path.as_posix(),
            "Layer 3 G4 readiness requires persisted runtime artifacts.",
        )
        for path in EXPECTED_ARTIFACT_PATHS
        if not _resolve_repo_path(repo_root, path).exists()
    ]


def _validate_written_artifact_set(written_paths: Sequence[str]) -> list[dict[str, str]]:
    expected = {path.as_posix() for path in EXPECTED_ARTIFACT_PATHS}
    written = {str(path) for path in written_paths}
    missing = sorted(expected - written)
    unexpected = sorted(written - expected)
    return [
        *[
            _issue(
                "layer3_g4_persisted_artifact_missing",
                path,
                "G4 --write must emit every expected persisted artifact path.",
            )
            for path in missing
        ],
        *[
            _issue(
                "layer3_g4_persisted_artifact_missing",
                path,
                "G4 --write emitted a path outside the expected artifact set.",
            )
            for path in unexpected
        ],
    ]


def _manifest_runtime_drift_keys(
    repo_root: Path,
    runtime_bundle: g4.Layer3G4Bundle,
) -> list[str]:
    path = _resolve_repo_path(repo_root, READINESS_MANIFEST_PATH)
    if not path.exists():
        return []
    try:
        persisted = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return ["readiness_manifest_unreadable"]
    runtime_manifest = _dump(runtime_bundle.readiness_manifest)
    runtime_summary = {
        **_mapping(runtime_manifest.get("summary")),
        "schema_version": runtime_manifest.get("schema_version"),
        "rule_version": runtime_manifest.get("rule_version"),
    }
    persisted_summary = {
        **_mapping(persisted.get("summary")),
        **{key: persisted.get(key) for key in EXPECTED_MANIFEST_DRIFT_KEYS if key in persisted},
    }
    return [
        key
        for key in EXPECTED_MANIFEST_DRIFT_KEYS
        if persisted_summary.get(key) != runtime_summary.get(key)
    ]


def _manifest_runtime_drift_issues(drift_keys: Sequence[str]) -> list[dict[str, str]]:
    if not drift_keys:
        return []
    return [
        _issue(
            "layer3_g4_manifest_runtime_drift",
            READINESS_MANIFEST_PATH.as_posix(),
            f"Persisted G4 readiness manifest drifted from runtime: {sorted(drift_keys)}",
        )
    ]


def _registration_statuses(repo_root: Path) -> dict[str, str]:
    generated_text = _read_text_or_empty(repo_root, GENERATED_ARTIFACTS_TOML_PATH)
    inventory_text = _read_text_or_empty(repo_root, INVENTORY_PATH)
    docs_checks = (
        (GENERATED_ARTIFACTS_DOC_PATH, "layer3_g4_readiness_manifest.json"),
        (DOCS_SURFACE_PATH, "layer3_g4_promotion_audit_surface"),
        (DOCS_SURFACE_PATH, "PUBLIC/REVIEWER/EXPERT/MACHINE"),
        (DOCS_SURFACE_PATH, "out_of_scope_reference_only"),
        (DOCUMENTATION_INVENTORY_PATH, "policy-design-case-layer3-promotion-gate.md"),
        (REFERENCE_INDEX_PATH, "policy-design-case-layer3-promotion-gate.md"),
        (PUBLIC_SURFACE_DOC_PATH, g4.G4_SURFACE_ID),
    )
    return {
        "generated_artifacts": (
            "pass"
            if g4.G4_GENERATED_ARTIFACT_FAMILY_ID in generated_text
            and all(path.as_posix() in generated_text for path in EXPECTED_ARTIFACT_PATHS)
            else "fail"
        ),
        "inventory": "pass" if g4.G4_SURFACE_ID in inventory_text else "fail",
        "docs": (
            "pass"
            if all(needle in _read_text_or_empty(repo_root, path) for path, needle in docs_checks)
            else "fail"
        ),
    }


def _validate_registration_and_docs(
    repo_root: Path,
    statuses: Mapping[str, str],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if statuses.get("generated_artifacts") != "pass":
        issues.append(
            _issue(
                "layer3_g4_generated_artifacts_family_missing",
                GENERATED_ARTIFACTS_TOML_PATH.as_posix(),
                "architecture/generated_artifacts.toml must register the G4 family.",
            )
        )
    if statuses.get("inventory") != "pass":
        issues.append(
            _issue(
                "layer3_g4_inventory_surface_missing",
                INVENTORY_PATH.as_posix(),
                "Policy Design Case inventory must register the G4 promotion surface.",
            )
        )
    if statuses.get("docs") != "pass":
        issues.append(
            _issue(
                "layer3_g4_reference_index_missing",
                DOCS_SURFACE_PATH.as_posix(),
                "G4 reference docs/index/public-surface markers must be registered.",
            )
        )
    return issues


def _validate_runtime_surfaces(bundle: g4.Layer3G4Bundle) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    projection = bundle.public_export_projection_refs
    public_projection = projection.PUBLIC
    public_authorities = {str(value) for value in public_projection.get("authoritative_for", ())}
    negative_result_ids = {
        result.negative_id for result in bundle.conformance_report.negative_results
    }
    missing_negative_ids = sorted(set(g4.G4_CONFORMANCE_NEGATIVE_IDS) - negative_result_ids)
    failed_negative_ids = [
        result.negative_id
        for result in bundle.conformance_report.negative_results
        if result.status != "pass"
    ]
    bridge_records = tuple(
        record
        for record in _sequence(bundle.adapter_contract_registry.get("bridge_records"))
        if isinstance(record, Mapping)
    )
    bridge_records_by_id = {
        str(record.get("bridge_id")): record for record in bridge_records
    }
    bridge_records_are_semantic = (
        len(bridge_records) >= len(g4.G4_ADAPTER_PATH_IDS)
        and set(bridge_records_by_id) >= set(g4.G4_ADAPTER_PATH_IDS)
        and all(
            record.get("producer_artifact_family")
            and str(record.get("producer_artifact_ref", "")).startswith("repo://")
            and record.get("consumer")
            and record.get("authority_purpose")
            == "layer3_g4_governed_promotion_state"
            and set(_sequence(record.get("authoritative_for")))
            >= set(g4.G4_AUTHORITATIVE_FOR)
            and set(_sequence(record.get("may_not_use_for"))) >= set(g4.G4_MAY_NOT_USE_FOR)
            and record.get("semantic_loss_status")
            == "no_loss_for_promotion_state_refs"
            and _sequence(record.get("verification_refs"))
            and _sequence(record.get("conformance_negative_refs"))
            for record in bridge_records_by_id.values()
        )
    )
    if "raw_upstream_payload" in public_projection:
        issues.append(
            _issue(
                "layer3_g4_public_raw_payload_leak",
                "$.public_export_projection_refs.PUBLIC",
                "PUBLIC G4 projection cannot include raw upstream payloads.",
            )
        )
    if public_authorities & {"claim_authority", "policy_recommendation"}:
        issues.append(
            _issue(
                "layer3_g4_policy_projection_authority_leak",
                "$.public_export_projection_refs.PUBLIC.authoritative_for",
                "G4 projections are projection-only and cannot claim policy authority.",
            )
        )
    if (
        projection.public_export_hook_status == "implemented"
        and not projection.public_export_bundle_route_registered
    ):
        issues.append(
            _issue(
                "layer3_g4_public_export_hook_overclaimed",
                "$.public_export_projection_refs.public_export_hook_status",
                "Projection refs alone cannot claim the public export hook is implemented.",
            )
        )
    checks = (
        (
            set(bundle.promotion_audit_surface.surface_audiences) >= SURFACE_AUDIENCES,
            "layer3_g4_public_surface_visibility_missing",
            "G4 audit surface must expose PUBLIC/REVIEWER/EXPERT/MACHINE audiences.",
        ),
        (
            set(projection.audiences) >= SURFACE_AUDIENCES,
            "layer3_g4_public_surface_visibility_missing",
            "G4 public projection refs must expose all surface audiences.",
        ),
        (
            set(g4.G4_MAY_NOT_USE_FOR) <= set(projection.may_not_use_for),
            "layer3_g4_may_not_use_for_incomplete",
            "G4 public projection refs must preserve the full deny-list.",
        ),
        (
            projection.public_export_hook_status == "out_of_scope_reference_only",
            "layer3_g4_public_export_hook_overclaimed",
            "G4 public-export hook status must be reference-only unless integrated.",
        ),
        (
            bool(bundle.promotion_records)
            and any(record.promotion_state == "governed_promoted" for record in bundle.promotion_records)
            and any(record.promotion_state == "promotion_blocked" for record in bundle.promotion_records),
            "layer3_g4_promotion_record_missing",
            "G4 runtime bundle must include promoted and blocked promotion records.",
        ),
        (
            bundle.closeout_consumer_gate.status == "pass"
            and bundle.pdc_compiler_consumer_gate.status == "pass"
            and bundle.g5_promotion_handoff.status == "pass",
            "layer3_g4_g5_promotion_handoff_missing",
            "G4 consumer gates and G5 handoff must be readable.",
        ),
        (
            bundle.conformance_report.status == "pass",
            "layer3_g4_registry_ratchet_delta_missing",
            "G4 conformance negatives must pass before readiness closes.",
        ),
        (
            not missing_negative_ids and not failed_negative_ids,
            "layer3_g4_promotion_gate_admission_without_conformance",
            "G4 conformance report must execute every Task 7 negative.",
        ),
        (
            bundle.performance_contract_report.status == "pass"
            and bundle.conformance_report.performance_contract.status == "pass",
            "layer3_g4_unbounded_artifact_scan",
            "G4 performance/scaling contract must pass before readiness closes.",
        ),
        (
            bundle.registry_ratchet_delta.status == "pass"
            and bundle.registry_ratchet_delta.conformance_refs,
            "layer3_g4_promotion_gate_admission_without_conformance",
            "G4 registry ratchet delta must point at conformance refs.",
        ),
        (
            set(bundle.health_metric_delta.get("metric_ids", ()))
            >= set(g4.G4_EXPECTED_HEALTH_METRICS),
            "layer3_g4_persisted_artifact_missing",
            "G4 health metric delta must include all expected metric ids.",
        ),
        (
            bundle.adapter_contract_registry.get("status") == "pass"
            and set(bundle.adapter_contract_registry.get("adapter_path_ids", ()))
            >= set(g4.G4_ADAPTER_PATH_IDS),
            "layer3_g4_adapter_contract_registry_missing",
            "G4 adapter contract registry must enumerate semantic bridge paths.",
        ),
        (
            bridge_records_are_semantic,
            "layer3_g4_adapter_registry_summary_only",
            "G4 adapter contract registry must persist per-bridge producer/consumer/verification refs.",
        ),
    )
    issues.extend(
        _issue(code, "$.readiness_manifest", message)
        for passed, code, message in checks
        if not passed
    )
    return issues


def _summary(
    repo_root: Path,
    bundle: g4.Layer3G4Bundle,
    runtime_report: Mapping[str, Any],
    drift_keys: Sequence[str],
    registration_statuses: Mapping[str, str],
) -> dict[str, Any]:
    summary = dict(_mapping(runtime_report.get("summary")))
    summary.update(bundle.readiness_manifest.summary)
    summary.update(
        {
            "schema_version": G4_SCHEMA_VERSION,
            "rule_version": G4_RULE_VERSION,
            "surface_id": bundle.promotion_audit_surface.surface_id,
            "surface_audiences": list(bundle.promotion_audit_surface.surface_audiences),
            "may_not_use_for": list(bundle.promotion_audit_surface.may_not_use_for),
            "g4_generated_artifacts_registration_status": registration_statuses.get(
                "generated_artifacts",
                "fail",
            ),
            "g4_inventory_surface_status": registration_statuses.get("inventory", "fail"),
            "g4_reference_docs_status": registration_statuses.get("docs", "fail"),
            "g4_conformance_issue_count": len(bundle.conformance_report.issue_codes),
            "g4_manifest_runtime_drift_key_count": len(drift_keys),
            "expected_artifact_count": len(EXPECTED_ARTIFACT_PATHS),
            "persisted_g4_artifact_count": sum(
                1
                for path in EXPECTED_ARTIFACT_PATHS
                if _resolve_repo_path(repo_root, path).exists()
            ),
        }
    )
    return summary


def _write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, _json_dumps(payload))


def _write_health_metric_delta(path: Path, payload: Mapping[str, Any]) -> None:
    lines = [
        f"schema_version = {_toml_value(payload.get('schema_version', G4_SCHEMA_VERSION))}",
        f"rule_version = {_toml_value(payload.get('rule_version', G4_RULE_VERSION))}",
        "",
        "[health_metric_delta]",
        f"metric_ids = {_toml_value(payload.get('metric_ids', []))}",
    ]
    readings = _mapping(payload.get("readings"))
    for key in sorted(readings):
        lines.append(f"readings.{_toml_key(key)} = {_toml_value(readings[key])}")
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")


def _write_adapter_contract_registry(path: Path, payload: Mapping[str, Any]) -> None:
    lines = [
        f"schema_version = {_toml_value(payload.get('schema_version', G4_SCHEMA_VERSION))}",
        f"rule_version = {_toml_value(payload.get('rule_version', G4_RULE_VERSION))}",
        f"status = {_toml_value(payload.get('status', 'fail'))}",
        f"adapter_path_ids = {_toml_value(payload.get('adapter_path_ids', []))}",
        f"adapter_path_count = {_toml_value(payload.get('adapter_path_count', 0))}",
        f"bridge_record_count = {_toml_value(payload.get('bridge_record_count', 0))}",
        f"semantic_loss_status = {_toml_value(payload.get('semantic_loss_status', ''))}",
        f"authoritative_for = {_toml_value(payload.get('authoritative_for', []))}",
        f"may_not_use_for = {_toml_value(payload.get('may_not_use_for', []))}",
    ]
    for record in _sequence(payload.get("bridge_records")):
        if not isinstance(record, Mapping):
            continue
        lines.append("")
        lines.append("[[bridge_records]]")
        for key in sorted(record):
            lines.append(f"{_toml_key(str(key))} = {_toml_value(record[key])}")
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n"


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, Mapping):
        pairs = [f"{_toml_key(str(key))} = {_toml_value(value[key])}" for key in sorted(value)]
        return "{ " + ", ".join(pairs) + " }"
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if value is None:
        return '""'
    return json.dumps(str(value), ensure_ascii=False)


def _toml_key(value: str) -> str:
    return value if value.replace("_", "").replace("-", "").isalnum() else json.dumps(value)


def _dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _dump(inner) for key, inner in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_dump(item) for item in value]
    return value


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"_root": payload}


def _read_text_or_empty(repo_root: Path, path: Path) -> str:
    resolved = _resolve_repo_path(repo_root, path)
    return resolved.read_text(encoding="utf-8") if resolved.exists() else ""


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        return (value,)
    return tuple(value)


def _normalize_issues(issues: object) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for issue in _sequence(issues):
        payload = issue.model_dump(mode="json") if isinstance(issue, BaseModel) else issue
        if not isinstance(payload, Mapping):
            continue
        normalized.append(
            _issue(
                str(payload.get("code", "")),
                str(payload.get("path", "")),
                str(payload.get("message", "")),
            )
        )
    return normalized


def _deduplicate_issues(issues: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    normalized: list[dict[str, str]] = []
    for issue in issues:
        code = str(issue.get("code", ""))
        path = str(issue.get("path", ""))
        message = str(issue.get("message", ""))
        key = (code, path, message)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"code": code, "path": path, "message": message})
    return normalized


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _render_text_report(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [f"layer3_g4_readiness_status={report.get('status', '')}"]
    if isinstance(summary, Mapping):
        for key in sorted(summary):
            lines.append(f"{key}={_display_value(summary[key])}")
    issues = report.get("issues", [])
    if isinstance(issues, Sequence) and issues:
        lines.append("issues:")
        for issue in issues:
            if isinstance(issue, Mapping):
                lines.append(
                    f"- {issue.get('code', '')} {issue.get('path', '')}: "
                    f"{issue.get('message', '')}"
                )
    return "\n".join(lines).rstrip() + "\n"


def _display_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def _resolve_repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        sys.stderr.write(str(exc))
        raise
