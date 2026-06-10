#!/usr/bin/env python3
"""Validate and optionally persist the Layer 3 G5 conversion bundle."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from polisyos.runtime.quality import layer3_proving_ground_conversion as g5
from tools.lib.fs import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")
DOCS_REFERENCE_DIR = Path("docs/reference")
G5_SCHEMA_VERSION = g5.G5_SCHEMA_VERSION
G5_RULE_VERSION = g5.G5_RULE_VERSION

DEPENDENCY_READINESS_SNAPSHOT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_dependency_readiness_snapshot.json"
)
PINNED_CASE_INPUT_BUNDLE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_pinned_case_input_bundle.json"
)
W12D_CASE_BLOCK_INDEX_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_w12d_case_block_index.json"
)
COMPOSED_LOOP_COMPLETENESS_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_composed_loop_completeness_gate.json"
)
G4_HANDOFF_RESOLUTION_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_g4_handoff_resolution.json"
)
G4_PROMOTION_RECORD_RESOLUTION_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_g4_promotion_record_resolution.json"
)
UPSTREAM_SCOPE_JOIN_MATRIX_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_upstream_scope_join_matrix.json"
)
GROUNDED_RESULT_EVIDENCE_SET_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_grounded_result_evidence_set.json"
)
EFFECTIVE_EVIDENCE_INDEPENDENCE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_effective_evidence_independence.json"
)
USEFUL_DESIGN_METRIC_ELIGIBILITY_JOIN_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_useful_design_metric_eligibility_join.json"
)
CONVERSION_ELIGIBILITY_LEDGER_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_conversion_eligibility_ledger.json"
)
STATUS_COMPOSITION_LEDGER_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_status_composition_ledger.json"
)
GROUNDED_ABSTENTION_QUALITY_RECORD_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_grounded_abstention_quality_record.json"
)
DEMAND_PULL_ATTEMPT_RECORD_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_demand_pull_attempt_record.json"
)
DEPENDENCY_HEALTH_METRIC_SNAPSHOT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_dependency_health_metric_snapshot.json"
)
ENVELOPE_EXPANSION_DELTA_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_envelope_expansion_delta.json"
)
CONVERSION_RECORDS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g5_conversion_records.json"
W12D_CONSUMER_GATE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g5_w12d_consumer_gate.json"
CONVERSION_AUDIT_SURFACE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_conversion_audit_surface.json"
)
PUBLIC_EXPORT_PROJECTION_REFS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_public_export_projection_refs.json"
)
CONFORMANCE_REPORT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g5_conformance_report.json"
HEALTH_METRIC_DELTA_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g5_health_metric_delta.toml"
CONVERSION_ROUTE_CONTRACT_REGISTRY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_conversion_route_contract_registry.toml"
)
REGISTRY_RATCHET_DELTA_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_registry_ratchet_delta.json"
)
READINESS_MANIFEST_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g5_readiness_manifest.json"

GENERATED_ARTIFACTS_TOML_PATH = Path("architecture/generated_artifacts.toml")
GENERATED_ARTIFACTS_DOC_PATH = DOCS_REFERENCE_DIR / "generated-artifacts.md"
INVENTORY_PATH = POLICY_DESIGN_CASE_DIR / "inventory.json"
DOCS_SURFACE_PATH = (
    DOCS_REFERENCE_DIR / "policy-design-case-layer3-proving-ground-conversion.md"
)
DOCUMENTATION_INVENTORY_PATH = DOCS_REFERENCE_DIR / "documentation-inventory.md"
REFERENCE_INDEX_PATH = DOCS_REFERENCE_DIR / "index.md"
PUBLIC_SURFACE_DOC_PATH = DOCS_REFERENCE_DIR / "public-surface.md"

EXPECTED_ARTIFACT_PATHS: tuple[Path, ...] = (
    DEPENDENCY_READINESS_SNAPSHOT_PATH,
    PINNED_CASE_INPUT_BUNDLE_PATH,
    W12D_CASE_BLOCK_INDEX_PATH,
    COMPOSED_LOOP_COMPLETENESS_GATE_PATH,
    G4_HANDOFF_RESOLUTION_PATH,
    G4_PROMOTION_RECORD_RESOLUTION_PATH,
    UPSTREAM_SCOPE_JOIN_MATRIX_PATH,
    GROUNDED_RESULT_EVIDENCE_SET_PATH,
    EFFECTIVE_EVIDENCE_INDEPENDENCE_PATH,
    USEFUL_DESIGN_METRIC_ELIGIBILITY_JOIN_PATH,
    CONVERSION_ELIGIBILITY_LEDGER_PATH,
    STATUS_COMPOSITION_LEDGER_PATH,
    GROUNDED_ABSTENTION_QUALITY_RECORD_PATH,
    DEMAND_PULL_ATTEMPT_RECORD_PATH,
    DEPENDENCY_HEALTH_METRIC_SNAPSHOT_PATH,
    ENVELOPE_EXPANSION_DELTA_PATH,
    CONVERSION_RECORDS_PATH,
    W12D_CONSUMER_GATE_PATH,
    CONVERSION_AUDIT_SURFACE_PATH,
    PUBLIC_EXPORT_PROJECTION_REFS_PATH,
    CONFORMANCE_REPORT_PATH,
    HEALTH_METRIC_DELTA_PATH,
    CONVERSION_ROUTE_CONTRACT_REGISTRY_PATH,
    REGISTRY_RATCHET_DELTA_PATH,
    READINESS_MANIFEST_PATH,
)
EXPECTED_MANIFEST_DRIFT_KEYS: tuple[str, ...] = (
    "status",
    "schema_version",
    "rule_version",
    "g5_dependency_readiness_status",
    "g5_g0_dependency_status",
    "g5_g1_dependency_status",
    "g5_g2_dependency_status",
    "g5_g3_dependency_status",
    "g5_gl_dependency_status",
    "g5_g4_dependency_status",
    "g5_pinned_case_input_status",
    "g5_composed_loop_completeness_status",
    "g5_g4_handoff_resolution_status",
    "g5_upstream_scope_join_status",
    "g5_effective_evidence_independence_status",
    "g5_conversion_record_count",
    "g5_conversion_outcome",
    "g5_grounded_conversion_count",
    "g5_w12d_consumer_gate_status",
    "g5_envelope_expansion_status",
    "g5_public_surface_status",
    "g5_projection_boundary_status",
    "g5_s12_projection_contract_status",
    "g5_s14_projection_contract_status",
    "g5_conformance_status",
    "g5_generated_artifacts_registration_status",
    "g5_inventory_surface_status",
    "g5_reference_docs_status",
    "issue_codes",
)
ALL_ISSUE_CODES: tuple[str, ...] = tuple(dict.fromkeys(g5.ALL_ISSUE_CODES))
SURFACE_AUDIENCES: frozenset[str] = frozenset(("PUBLIC", "REVIEWER", "EXPERT", "MACHINE"))


def validate_layer3_g5_readiness(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    """Build a Layer 3 G5 readiness report from runtime and registered surfaces."""

    root = Path(repo_root).resolve()
    runtime_bundle = g5.build_layer3_g5_bundle(root)
    written_artifact_paths = _write_artifacts(root, runtime_bundle) if write else []
    runtime_report = g5.validate_layer3_g5_bundle(root, runtime_bundle).model_dump(
        mode="json"
    )
    drift_keys = _manifest_runtime_drift_keys(root, runtime_bundle)
    registration_statuses = _registration_statuses(root)
    issues: list[dict[str, str]] = []
    issues.extend(_normalize_issues(runtime_report.get("issues", [])))
    issues.extend(_validate_persisted_artifacts(root))
    issues.extend(_validate_written_artifact_set(written_artifact_paths) if write else [])
    issues.extend(_manifest_runtime_drift_issues(drift_keys))
    issues.extend(_validate_registration_and_docs(registration_statuses))
    issues.extend(_validate_runtime_surfaces(runtime_bundle))
    normalized_issues = _deduplicate_issues(issues)
    return {
        "schema_version": G5_SCHEMA_VERSION,
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
    """Run the Layer 3 G5 readiness check CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    report = validate_layer3_g5_readiness(args.repo_root, write=args.write)
    rendered = (
        _json_dumps(report) if args.output_format == "json" else _render_text_report(report)
    )
    if args.output is not None:
        output_path = _resolve_repo_path(Path(args.repo_root).resolve(), args.output)
        atomic_write_text(output_path, rendered)
    sys.stdout.write(rendered)
    return 0 if report["status"] == "pass" else 1


def _write_artifacts(repo_root: Path, bundle: g5.Layer3G5Bundle) -> list[str]:
    base = {"schema_version": G5_SCHEMA_VERSION, "rule_version": G5_RULE_VERSION}
    payloads: dict[Path, Any] = {
        DEPENDENCY_READINESS_SNAPSHOT_PATH: _dump(bundle.dependency_readiness_snapshot),
        PINNED_CASE_INPUT_BUNDLE_PATH: _dump(bundle.pinned_case_input_bundle),
        W12D_CASE_BLOCK_INDEX_PATH: _dump(
            bundle.pinned_case_input_bundle.w12d_case_block_index
        ),
        COMPOSED_LOOP_COMPLETENESS_GATE_PATH: _dump(
            bundle.pinned_case_input_bundle.composed_loop_completeness_gate
        ),
        G4_HANDOFF_RESOLUTION_PATH: _dump(bundle.g4_handoff_resolution),
        G4_PROMOTION_RECORD_RESOLUTION_PATH: {
            **base,
            "promotion_record_resolutions": _dump(
                bundle.g4_handoff_resolution.promotion_record_resolutions
            ),
        },
        UPSTREAM_SCOPE_JOIN_MATRIX_PATH: _dump(bundle.upstream_scope_join_matrix),
        GROUNDED_RESULT_EVIDENCE_SET_PATH: _dump(bundle.grounded_result_evidence_set),
        EFFECTIVE_EVIDENCE_INDEPENDENCE_PATH: _dump(
            bundle.grounded_result_evidence_set.effective_independence_record
        ),
        USEFUL_DESIGN_METRIC_ELIGIBILITY_JOIN_PATH: _dump(
            bundle.useful_design_metric_eligibility_join
        ),
        CONVERSION_ELIGIBILITY_LEDGER_PATH: _dump(
            bundle.conversion_eligibility_ledger
        ),
        STATUS_COMPOSITION_LEDGER_PATH: _dump(bundle.status_composition_ledger),
        GROUNDED_ABSTENTION_QUALITY_RECORD_PATH: _dump(
            bundle.grounded_abstention_quality_record
        ),
        DEMAND_PULL_ATTEMPT_RECORD_PATH: _dump(bundle.demand_pull_attempt_record),
        DEPENDENCY_HEALTH_METRIC_SNAPSHOT_PATH: _dump(
            bundle.dependency_health_metric_snapshot
        ),
        ENVELOPE_EXPANSION_DELTA_PATH: _dump(bundle.envelope_expansion_delta),
        CONVERSION_RECORDS_PATH: {
            **base,
            "conversion_records": _dump(bundle.conversion_records),
        },
        W12D_CONSUMER_GATE_PATH: _dump(bundle.w12d_consumer_gate),
        CONVERSION_AUDIT_SURFACE_PATH: _dump(bundle.conversion_audit_surface),
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
        elif path == CONVERSION_ROUTE_CONTRACT_REGISTRY_PATH:
            _write_conversion_route_contract_registry(
                resolved,
                bundle.conversion_route_contract_registry,
            )
        else:
            _write_json(resolved, payloads[path])
        written.append(path.as_posix())
    return written


def _validate_persisted_artifacts(repo_root: Path) -> list[dict[str, str]]:
    return [
        _issue(
            "layer3_g5_persisted_artifact_missing",
            path.as_posix(),
            "Layer 3 G5 readiness requires persisted runtime artifacts.",
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
                "layer3_g5_persisted_artifact_missing",
                path,
                "G5 --write must emit every expected persisted artifact path.",
            )
            for path in missing
        ],
        *[
            _issue(
                "layer3_g5_persisted_artifact_missing",
                path,
                "G5 --write emitted a path outside the expected artifact set.",
            )
            for path in unexpected
        ],
    ]


def _manifest_runtime_drift_keys(
    repo_root: Path,
    runtime_bundle: g5.Layer3G5Bundle,
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
        "status": runtime_manifest.get("status"),
        "issue_codes": runtime_manifest.get("issue_codes", []),
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
            "layer3_g5_manifest_runtime_drift",
            READINESS_MANIFEST_PATH.as_posix(),
            f"Persisted G5 readiness manifest drifted from runtime: {sorted(drift_keys)}",
        )
    ]


def _registration_statuses(repo_root: Path) -> dict[str, str]:
    generated_text = _read_text_or_empty(repo_root, GENERATED_ARTIFACTS_TOML_PATH)
    inventory_text = _read_text_or_empty(repo_root, INVENTORY_PATH)
    docs_checks = (
        (GENERATED_ARTIFACTS_DOC_PATH, "layer3_g5_readiness_manifest.json"),
        (DOCS_SURFACE_PATH, "layer3_g5_first_proving_ground_conversion_surface"),
        (DOCS_SURFACE_PATH, "PUBLIC/REVIEWER/EXPERT/MACHINE"),
        (DOCS_SURFACE_PATH, "out_of_scope_reference_only"),
        (
            DOCUMENTATION_INVENTORY_PATH,
            "policy-design-case-layer3-proving-ground-conversion.md",
        ),
        (
            REFERENCE_INDEX_PATH,
            "policy-design-case-layer3-proving-ground-conversion.md",
        ),
        (PUBLIC_SURFACE_DOC_PATH, g5.G5_SURFACE_ID),
    )
    return {
        "generated_artifacts": (
            "pass"
            if g5.G5_GENERATED_ARTIFACT_FAMILY_ID in generated_text
            and all(path.as_posix() in generated_text for path in EXPECTED_ARTIFACT_PATHS)
            and "stale_output_behavior = \"fail\"" in generated_text
            and "drift_gate = \"automated\"" in generated_text
            else "fail"
        ),
        "inventory": "pass" if g5.G5_SURFACE_ID in inventory_text else "fail",
        "docs": (
            "pass"
            if all(needle in _read_text_or_empty(repo_root, path) for path, needle in docs_checks)
            else "fail"
        ),
    }


def _validate_registration_and_docs(
    statuses: Mapping[str, str],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if statuses.get("generated_artifacts") != "pass":
        issues.append(
            _issue(
                "layer3_g5_generated_artifacts_family_missing",
                GENERATED_ARTIFACTS_TOML_PATH.as_posix(),
                "architecture/generated_artifacts.toml must register the G5 family.",
            )
        )
    if statuses.get("inventory") != "pass":
        issues.append(
            _issue(
                "layer3_g5_inventory_surface_missing",
                INVENTORY_PATH.as_posix(),
                "Policy Design Case inventory must register the G5 conversion surface.",
            )
        )
    if statuses.get("docs") != "pass":
        issues.append(
            _issue(
                "layer3_g5_reference_index_missing",
                DOCS_SURFACE_PATH.as_posix(),
                "G5 reference docs/index/public-surface markers must be registered.",
            )
        )
    return issues


def _validate_runtime_surfaces(bundle: g5.Layer3G5Bundle) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    projection = bundle.public_export_projection_refs
    public_projection = projection.PUBLIC
    route_registry = bundle.conversion_route_contract_registry
    route_records = tuple(
        record
        for record in _sequence(route_registry.get("conversion_route_records"))
        if isinstance(record, Mapping)
    )
    negative_results = {
        result.negative_id: result
        for result in bundle.conformance_report.negative_results
    }
    missing_negative_ids = sorted(
        set(g5.G5_CONFORMANCE_NEGATIVE_IDS) - set(negative_results)
    )
    failed_negative_ids = [
        negative_id
        for negative_id, result in negative_results.items()
        if result.status != "pass"
    ]
    performance = bundle.conformance_report.performance_contract
    public_may_not = {
        str(value)
        for value in _sequence(public_projection.get("may_not_be_used_for"))
    }
    checks = (
        (
            "raw_upstream_payload" not in public_projection,
            "layer3_g5_public_raw_payload_leak",
            "PUBLIC G5 projection cannot include raw upstream payloads.",
        ),
        (
            not public_projection.get("authoritative_for"),
            "layer3_g5_projection_mints_authority",
            "G5 public projection cannot fill authority slots.",
        ),
        (
            {"claim_authority", "runtime_closeout_authority"} <= public_may_not,
            "layer3_g5_projection_omits_required_deny_list",
            "G5 public projection must preserve the required deny-list.",
        ),
        (
            projection.public_export_hook_status == "out_of_scope_reference_only"
            and not projection.public_export_bundle_route_registered,
            "layer3_g5_public_export_hook_overclaimed",
            "G5 projection refs cannot claim a public-export bundle hook.",
        ),
        (
            set(bundle.conversion_audit_surface.surface_audiences) >= SURFACE_AUDIENCES,
            "layer3_g5_public_raw_payload_leak",
            "G5 audit surface must expose all audiences with safe refs only.",
        ),
        (
            projection.projection_contract_verification.get("status") == "pass",
            "layer3_g5_projection_mints_authority",
            "G5 projection must pass runtime PDC projection authority checks.",
        ),
        (
            projection.s12_projection_contract_verification.get("status") == "pass",
            "layer3_g5_projection_omits_required_deny_list",
            "G5 S12 projection fields must pass S12 consumer-contract checks.",
        ),
        (
            projection.s14_projection_contract_verification.get("status") == "pass",
            "layer3_g5_projection_omits_required_deny_list",
            "G5 S14 projection fields must pass S14 consumer-contract checks.",
        ),
        (
            route_registry.get("status") == "pass"
            and route_records
            and "adapter_path_ids" not in route_registry,
            "layer3_g5_conversion_route_contract_registry_missing",
            "G5 must use a conversion-route registry, not an adapter registry.",
        ),
        (
            bundle.registry_ratchet_delta.status == "pass",
            "layer3_g5_registry_ratchet_delta_missing",
            "G5 registry ratchet delta must reference conformance evidence.",
        ),
        (
            bundle.conformance_report.status == "pass",
            "layer3_g5_registry_ratchet_delta_missing",
            "G5 conformance surface checks must pass before readiness closes.",
        ),
        (
            not missing_negative_ids and not failed_negative_ids,
            "layer3_g5_registry_ratchet_delta_missing",
            "G5 conformance report must execute every Task 7 negative.",
        ),
        (
            performance.get("status") == "pass"
            and performance.get("bounded_artifact_read_policy")
            == "explicit_expected_paths_only"
            and performance.get("request_path_repo_glob_allowed") is False
            and performance.get("upstream_builder_rerun_in_request_path") is False
            and performance.get("w12d_import_mode") == "lazy",
            "layer3_g5_unbounded_artifact_scan",
            "G5 performance/scaling contract must pass before readiness closes.",
        ),
        (
            bundle.conformance_report.closed_case_replay_integrity.get("status")
            == "pass",
            "layer3_g5_pre_g5_closed_case_replay_mutated",
            "G5 readiness must prove pre-G5 replay payloads are not mutated.",
        ),
        (
            bundle.conformance_report.closeout_boundary_check.status == "pass",
            "layer3_g5_closeout_surface_substitution_attempt",
            "G5 surfaces may be observed by closeout readers but cannot close cases.",
        ),
        (
            bundle.conformance_report.candidate_firewall_check.get("status") == "pass",
            "layer3_g5_candidate_unverified_used_as_authority",
            "G5 candidate/speculation refs must remain outside authority slots.",
        ),
        (
            bundle.conformance_report.warning_lifecycle_check.get("status") == "pass",
            "layer3_g5_unowned_warning_lifecycle",
            "G5 warning-like caveats must be owned warnings, limitations, or blockers.",
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
    bundle: g5.Layer3G5Bundle,
    runtime_report: Mapping[str, Any],
    drift_keys: Sequence[str],
    registration_statuses: Mapping[str, str],
) -> dict[str, Any]:
    summary = dict(_mapping(runtime_report.get("summary")))
    summary.update(bundle.readiness_manifest.summary)
    summary.update(
        {
            "status": bundle.readiness_manifest.status,
            "schema_version": G5_SCHEMA_VERSION,
            "rule_version": G5_RULE_VERSION,
            "surface_id": bundle.conversion_audit_surface.surface_id,
            "surface_audiences": list(bundle.conversion_audit_surface.surface_audiences),
            "may_not_use_for": list(bundle.conversion_audit_surface.may_not_use_for),
            "g5_generated_artifacts_registration_status": registration_statuses.get(
                "generated_artifacts",
                "fail",
            ),
            "g5_inventory_surface_status": registration_statuses.get("inventory", "fail"),
            "g5_reference_docs_status": registration_statuses.get("docs", "fail"),
            "g5_manifest_runtime_drift_key_count": len(drift_keys),
            "expected_artifact_count": len(EXPECTED_ARTIFACT_PATHS),
            "persisted_g5_artifact_count": sum(
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
        f"schema_version = {_toml_value(payload.get('schema_version', G5_SCHEMA_VERSION))}",
        f"rule_version = {_toml_value(payload.get('rule_version', G5_RULE_VERSION))}",
        "",
        "[health_metric_delta]",
        f"metric_ids = {_toml_value(payload.get('metric_ids', []))}",
    ]
    metric_statuses = _mapping(payload.get("metric_statuses"))
    for key in sorted(metric_statuses):
        lines.append(f"metric_statuses.{_toml_key(key)} = {_toml_value(metric_statuses[key])}")
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")


def _write_conversion_route_contract_registry(
    path: Path,
    payload: Mapping[str, Any],
) -> None:
    lines = [
        f"schema_version = {_toml_value(payload.get('schema_version', G5_SCHEMA_VERSION))}",
        f"rule_version = {_toml_value(payload.get('rule_version', G5_RULE_VERSION))}",
        f"status = {_toml_value(payload.get('status', 'fail'))}",
        f"route_count = {_toml_value(payload.get('route_count', 0))}",
    ]
    for record in _sequence(payload.get("conversion_route_records")):
        if not isinstance(record, Mapping):
            continue
        lines.append("")
        lines.append("[[conversion_route_records]]")
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
    lines = [f"layer3_g5_readiness_status={report.get('status', '')}"]
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
