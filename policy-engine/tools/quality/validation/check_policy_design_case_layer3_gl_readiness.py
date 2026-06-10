#!/usr/bin/env python3
"""Validate and optionally persist the Layer 3 GL legal/mandate-search bundle."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from polisyos.runtime.quality import layer3_legal_mandate_search as gl
from tools.lib.fs import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")
DOCS_REFERENCE_DIR = Path("docs/reference")
GL_SCHEMA_VERSION = gl.LAYER3_GL_SCHEMA_VERSION
GL_RULE_VERSION = gl.LAYER3_GL_RULE_VERSION

ADAPTER_ADMISSION_REGISTRY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_adapter_admission_registry.json"
)
L3_LEGAL_KG_INDEX_COVERAGE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_l3_legal_kg_index_coverage.json"
)
L3_LEGAL_KG_SEARCH_LEDGERS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_l3_legal_kg_search_ledgers.json"
)
L3_LEGAL_KG_QUERY_TRACES_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_l3_legal_kg_query_traces.json"
SEARCH_RECALL_FRESHNESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_search_recall_freshness.json"
L5_CALIBRATION_BINDINGS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_l5_calibration_bindings.json"
LEGAL_REQUIREMENT_BINDINGS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_legal_requirement_bindings.json"
)
AUTHORITY_FACET_BINDINGS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_authority_facet_bindings.json"
NORM_CANDIDATE_BINDINGS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_norm_candidate_bindings.json"
THRESHOLD_AUTHORITY_RECORDS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_threshold_authority_records.json"
)
MANDATE_AUTHORITY_RECORDS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_mandate_authority_records.json"
TEMPORAL_COMPETENCE_RECORDS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_temporal_competence_records.json"
)
AMENDMENT_LINEAGE_RECORDS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_amendment_lineage_records.json"
REFERENCE_RESOLUTION_RECORDS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_reference_resolution_records.json"
)
LEGAL_AUTHORITY_REPORT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_legal_authority_report.json"
LEX_INTERVENTION_MAP_BINDINGS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_lex_intervention_map_bindings.json"
)
CLAIM_REGISTRY_CONSUMER_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_claim_registry_consumer_gate.json"
)
SEMANTIC_BINDING_CONSUMER_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_semantic_binding_consumer_gate.json"
)
ARGUMENT_GRAPH_READINESS_CONSUMER_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_argument_graph_readiness_consumer_gate.json"
)
S6_MANDATE_CONSUMER_GATE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_s6_mandate_consumer_gate.json"
S7_DELEGATION_CONSUMER_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_s7_delegation_consumer_gate.json"
)
S8_VALUE_CHOICE_CONSUMER_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_s8_value_choice_consumer_gate.json"
)
PDC_COMPILER_CONSUMER_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_pdc_compiler_consumer_gate.json"
)
DESIGN_CONSTRAINT_CONSUMER_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_design_constraint_consumer_gate.json"
)
G4_PROMOTION_GATE_CONSUMER_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_g4_promotion_gate_consumer_gate.json"
)
PROMOTION_GATE_HANDOFF_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_promotion_gate_handoff.json"
LEGAL_MANDATE_AUDIT_SURFACE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_legal_mandate_audit_surface.json"
)
PUBLIC_EXPORT_PROJECTION_REFS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_public_export_projection_refs.json"
)
CONFORMANCE_REPORT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_conformance_report.json"
HEALTH_METRIC_DELTA_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_health_metric_delta.toml"
ADAPTER_CONTRACT_REGISTRY_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_adapter_contract_registry.toml"
READINESS_MANIFEST_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_readiness_manifest.json"

GENERATED_ARTIFACTS_TOML_PATH = Path("architecture/generated_artifacts.toml")
GENERATED_ARTIFACTS_DOC_PATH = DOCS_REFERENCE_DIR / "generated-artifacts.md"
INVENTORY_PATH = POLICY_DESIGN_CASE_DIR / "inventory.json"
DOCS_SURFACE_PATH = DOCS_REFERENCE_DIR / "policy-design-case-layer3-legal-mandate-search.md"
DOCUMENTATION_INVENTORY_PATH = DOCS_REFERENCE_DIR / "documentation-inventory.md"
REFERENCE_INDEX_PATH = DOCS_REFERENCE_DIR / "index.md"

JSON_ARTIFACT_PATHS: tuple[Path, ...] = (
    ADAPTER_ADMISSION_REGISTRY_PATH,
    L3_LEGAL_KG_INDEX_COVERAGE_PATH,
    L3_LEGAL_KG_SEARCH_LEDGERS_PATH,
    L3_LEGAL_KG_QUERY_TRACES_PATH,
    SEARCH_RECALL_FRESHNESS_PATH,
    L5_CALIBRATION_BINDINGS_PATH,
    LEGAL_REQUIREMENT_BINDINGS_PATH,
    AUTHORITY_FACET_BINDINGS_PATH,
    NORM_CANDIDATE_BINDINGS_PATH,
    THRESHOLD_AUTHORITY_RECORDS_PATH,
    MANDATE_AUTHORITY_RECORDS_PATH,
    TEMPORAL_COMPETENCE_RECORDS_PATH,
    AMENDMENT_LINEAGE_RECORDS_PATH,
    REFERENCE_RESOLUTION_RECORDS_PATH,
    LEGAL_AUTHORITY_REPORT_PATH,
    LEX_INTERVENTION_MAP_BINDINGS_PATH,
    CLAIM_REGISTRY_CONSUMER_GATE_PATH,
    SEMANTIC_BINDING_CONSUMER_GATE_PATH,
    ARGUMENT_GRAPH_READINESS_CONSUMER_GATE_PATH,
    S6_MANDATE_CONSUMER_GATE_PATH,
    S7_DELEGATION_CONSUMER_GATE_PATH,
    S8_VALUE_CHOICE_CONSUMER_GATE_PATH,
    PDC_COMPILER_CONSUMER_GATE_PATH,
    DESIGN_CONSTRAINT_CONSUMER_GATE_PATH,
    G4_PROMOTION_GATE_CONSUMER_GATE_PATH,
    PROMOTION_GATE_HANDOFF_PATH,
    LEGAL_MANDATE_AUDIT_SURFACE_PATH,
    PUBLIC_EXPORT_PROJECTION_REFS_PATH,
    CONFORMANCE_REPORT_PATH,
    READINESS_MANIFEST_PATH,
)
TOML_ARTIFACT_PATHS: tuple[Path, ...] = (
    HEALTH_METRIC_DELTA_PATH,
    ADAPTER_CONTRACT_REGISTRY_PATH,
)
EXPECTED_ARTIFACT_PATHS: tuple[Path, ...] = (
    *JSON_ARTIFACT_PATHS,
    *TOML_ARTIFACT_PATHS,
)
EXPECTED_MANIFEST_DRIFT_KEYS: tuple[str, ...] = (
    "schema_version",
    "rule_version",
    "g0_dependency_status",
    "g1_context_status",
    "g2_context_status",
    "g3_context_status",
    "gl_l3_legal_kg_route_status",
    "gl_l3_legal_kg_table_count",
    "gl_l3_legal_kg_index_coverage_status",
    "gl_search_ledger_count",
    "gl_query_trace_count",
    "gl_search_recall_freshness_status",
    "gl_l5_calibration_binding_status",
    "gl_l5_calibration_binding_count",
    "gl_legal_requirement_binding_count",
    "gl_authority_facet_binding_status",
    "gl_authority_facet_binding_count",
    "gl_norm_candidate_binding_count",
    "gl_legal_authority_report_status",
    "gl_selected_norm_ref_count",
    "gl_legal_authority_record_count",
    "gl_threshold_authority_record_count",
    "gl_mandate_authority_record_count",
    "gl_temporal_competence_status",
    "gl_amendment_lineage_status",
    "gl_reference_resolution_status",
    "gl_lex_intervention_map_binding_status",
    "gl_claim_registry_consumer_gate_status",
    "gl_semantic_binding_consumer_gate_status",
    "gl_argument_graph_readiness_consumer_gate_status",
    "gl_s6_mandate_consumer_gate_status",
    "gl_s7_delegation_consumer_gate_status",
    "gl_s8_value_choice_consumer_gate_status",
    "gl_design_constraint_consumer_gate_status",
    "gl_g4_promotion_gate_consumer_gate_status",
    "gl_public_export_projection_status",
    "gl_public_export_projection_hook_status",
    "gl_public_export_projection_mode",
    "gl_public_export_projection_ref_surface_status",
    "gl_inventory_surface_status",
    "gl_reference_docs_status",
    "gl_invariant_readiness_check_registration_status",
    "gl_adapter_semantic_loss_status",
    "gl_governance_throughput_status",
    "gl_conformance_status",
    "gl_adapter_contract_registry_status",
    "gl_adapter_contract_path_count",
    "gl_health_metric_ids",
)
ALL_ISSUE_CODES: tuple[str, ...] = tuple(dict.fromkeys(gl.ALL_ISSUE_CODES))
GL_ADAPTER_PATH_IDS: frozenset[str] = frozenset(gl.GL_ADAPTER_PATH_IDS)
GL_REFERENCE_ONLY_PUBLIC_ROUTE = gl.GL_REFERENCE_ONLY_PUBLIC_PROJECTION_ROUTE
GL_PUBLIC_EXPORT_BUNDLE_ROUTE = gl.GL_PUBLIC_EXPORT_BUNDLE_ROUTE


def validate_layer3_gl_readiness(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    """Build a Layer 3 GL readiness report from runtime and registered surfaces."""

    root = Path(repo_root).resolve()
    runtime_bundle = gl.build_layer3_gl_bundle(root)
    written_artifact_paths = _write_artifacts(root, runtime_bundle) if write else []
    runtime_report = gl.validate_layer3_gl_bundle(root, runtime_bundle).model_dump(mode="json")
    drift_keys = _manifest_runtime_drift_keys(root, runtime_bundle)
    issues: list[dict[str, str]] = []
    issues.extend(_normalize_issues(runtime_report.get("issues", [])))
    issues.extend(_validate_persisted_artifacts(root))
    issues.extend(_validate_written_artifact_set(written_artifact_paths) if write else [])
    issues.extend(_manifest_runtime_drift_issues(drift_keys))
    issues.extend(_validate_registration_and_docs(root))
    issues.extend(_validate_runtime_surfaces(runtime_bundle))
    normalized_issues = _deduplicate_issues(issues)
    return {
        "schema_version": gl.LAYER3_GL_SCHEMA_VERSION,
        "status": "fail" if normalized_issues else "pass",
        "issues": normalized_issues,
        "summary": _summary(root, runtime_bundle, runtime_report, drift_keys),
        "artifacts": {
            "expected_artifact_paths": [path.as_posix() for path in EXPECTED_ARTIFACT_PATHS],
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
    """Run the Layer 3 GL readiness check CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    report = validate_layer3_gl_readiness(args.repo_root, write=args.write)
    rendered = _json_dumps(report) if args.output_format == "json" else _render_text_report(report)
    if args.output is not None:
        output_path = _resolve_repo_path(Path(args.repo_root).resolve(), args.output)
        atomic_write_text(output_path, rendered)
    sys.stdout.write(rendered)
    return 0 if report["status"] == "pass" else 1


def _write_artifacts(repo_root: Path, bundle: gl.Layer3GLBundle) -> list[str]:
    base = {
        "schema_version": gl.LAYER3_GL_SCHEMA_VERSION,
        "rule_version": gl.LAYER3_GL_RULE_VERSION,
    }
    payloads: dict[Path, Any] = {
        ADAPTER_ADMISSION_REGISTRY_PATH: {
            **base,
            "adapter_admission_registry": _dump(bundle.adapter_admission_registry),
        },
        L3_LEGAL_KG_INDEX_COVERAGE_PATH: _dump(bundle.l3_legal_kg_index_coverage),
        L3_LEGAL_KG_SEARCH_LEDGERS_PATH: {
            **base,
            "ledgers": _dump(bundle.l3_legal_kg_search_ledgers),
        },
        L3_LEGAL_KG_QUERY_TRACES_PATH: {
            **base,
            "query_traces": _dump(bundle.l3_legal_kg_query_traces),
        },
        SEARCH_RECALL_FRESHNESS_PATH: _dump(bundle.search_recall_freshness),
        L5_CALIBRATION_BINDINGS_PATH: {**base, "bindings": _dump(bundle.l5_calibration_bindings)},
        LEGAL_REQUIREMENT_BINDINGS_PATH: {
            **base,
            "bindings": _dump(bundle.legal_requirement_bindings),
        },
        AUTHORITY_FACET_BINDINGS_PATH: {
            **base,
            "bindings": _dump(bundle.authority_facet_bindings),
        },
        NORM_CANDIDATE_BINDINGS_PATH: {**base, "bindings": _dump(bundle.norm_candidate_bindings)},
        THRESHOLD_AUTHORITY_RECORDS_PATH: {
            **base,
            "records": _dump(bundle.threshold_authority_records),
        },
        MANDATE_AUTHORITY_RECORDS_PATH: {
            **base,
            "records": _dump(bundle.mandate_authority_records),
        },
        TEMPORAL_COMPETENCE_RECORDS_PATH: {
            **base,
            "records": _dump(bundle.temporal_competence_records),
        },
        AMENDMENT_LINEAGE_RECORDS_PATH: {
            **base,
            "records": _dump(bundle.amendment_lineage_records),
        },
        REFERENCE_RESOLUTION_RECORDS_PATH: {
            **base,
            "records": _dump(bundle.reference_resolution_records),
        },
        LEGAL_AUTHORITY_REPORT_PATH: _dump(bundle.legal_authority_report),
        LEX_INTERVENTION_MAP_BINDINGS_PATH: {
            **base,
            "bindings": _dump(bundle.lex_intervention_map_bindings),
        },
        CLAIM_REGISTRY_CONSUMER_GATE_PATH: _dump(bundle.claim_registry_consumer_gate),
        SEMANTIC_BINDING_CONSUMER_GATE_PATH: _dump(bundle.semantic_binding_consumer_gate),
        ARGUMENT_GRAPH_READINESS_CONSUMER_GATE_PATH: _dump(
            bundle.argument_graph_readiness_consumer_gate
        ),
        S6_MANDATE_CONSUMER_GATE_PATH: _dump(bundle.s6_mandate_consumer_gate),
        S7_DELEGATION_CONSUMER_GATE_PATH: _dump(bundle.s7_delegation_consumer_gate),
        S8_VALUE_CHOICE_CONSUMER_GATE_PATH: _dump(bundle.s8_value_choice_consumer_gate),
        PDC_COMPILER_CONSUMER_GATE_PATH: _dump(bundle.pdc_compiler_consumer_gate),
        DESIGN_CONSTRAINT_CONSUMER_GATE_PATH: _dump(bundle.design_constraint_consumer_gate),
        G4_PROMOTION_GATE_CONSUMER_GATE_PATH: _dump(bundle.g4_promotion_gate_consumer_gate),
        PROMOTION_GATE_HANDOFF_PATH: _dump(bundle.promotion_gate_handoff),
        LEGAL_MANDATE_AUDIT_SURFACE_PATH: _dump(bundle.legal_mandate_audit_surface),
        PUBLIC_EXPORT_PROJECTION_REFS_PATH: _dump(bundle.public_export_projection_refs),
        CONFORMANCE_REPORT_PATH: _dump(bundle.conformance_report),
        READINESS_MANIFEST_PATH: _dump(bundle.readiness_manifest),
    }
    written: list[str] = []
    for path, payload in payloads.items():
        _write_json(_resolve_repo_path(repo_root, path), payload)
        written.append(path.as_posix())
    _write_health_metric_delta(
        _resolve_repo_path(repo_root, HEALTH_METRIC_DELTA_PATH),
        bundle.health_metric_delta,
    )
    written.append(HEALTH_METRIC_DELTA_PATH.as_posix())
    _write_adapter_contract_registry(
        _resolve_repo_path(repo_root, ADAPTER_CONTRACT_REGISTRY_PATH),
        bundle.adapter_contract_registry,
    )
    written.append(ADAPTER_CONTRACT_REGISTRY_PATH.as_posix())
    return written


def _validate_persisted_artifacts(repo_root: Path) -> list[dict[str, str]]:
    return [
        _issue(
            "layer3_gl_persisted_artifact_missing",
            path.as_posix(),
            "Layer 3 GL readiness requires persisted runtime artifacts.",
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
                "layer3_gl_persisted_artifact_missing",
                path,
                "GL --write must emit every expected persisted artifact path.",
            )
            for path in missing
        ],
        *[
            _issue(
                "layer3_gl_persisted_artifact_missing",
                path,
                "GL --write emitted a path outside the expected artifact set.",
            )
            for path in unexpected
        ],
    ]


def _manifest_runtime_drift_keys(repo_root: Path, runtime_bundle: gl.Layer3GLBundle) -> list[str]:
    path = _resolve_repo_path(repo_root, READINESS_MANIFEST_PATH)
    if not path.exists():
        return []
    try:
        persisted = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return ["readiness_manifest_unreadable"]
    runtime_manifest = runtime_bundle.readiness_manifest.model_dump(mode="json")
    return [
        key
        for key in EXPECTED_MANIFEST_DRIFT_KEYS
        if persisted.get(key) != runtime_manifest.get(key)
    ]


def _manifest_runtime_drift_issues(drift_keys: Sequence[str]) -> list[dict[str, str]]:
    if not drift_keys:
        return []
    return [
        _issue(
            "layer3_gl_manifest_runtime_drift",
            READINESS_MANIFEST_PATH.as_posix(),
            f"Persisted GL readiness manifest drifted from runtime: {sorted(drift_keys)}",
        )
    ]


def _validate_registration_and_docs(repo_root: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    generated_text = _read_text_or_empty(repo_root, GENERATED_ARTIFACTS_TOML_PATH)
    if gl.GL_GENERATED_ARTIFACT_FAMILY_ID not in generated_text or not all(
        path.as_posix() in generated_text for path in EXPECTED_ARTIFACT_PATHS
    ):
        issues.append(
            _issue(
                "layer3_gl_generated_artifacts_family_missing",
                GENERATED_ARTIFACTS_TOML_PATH.as_posix(),
                "architecture/generated_artifacts.toml must register the GL family.",
            )
        )
    inventory_text = _read_text_or_empty(repo_root, INVENTORY_PATH)
    if gl.GL_SURFACE_ID not in inventory_text:
        issues.append(
            _issue(
                "layer3_gl_inventory_surface_missing",
                INVENTORY_PATH.as_posix(),
                "Policy Design Case inventory must register the GL audit surface.",
            )
        )
    docs_checks = (
        (GENERATED_ARTIFACTS_DOC_PATH, "layer3_gl_readiness_manifest.json"),
        (DOCS_SURFACE_PATH, "search vs authority"),
        (DOCUMENTATION_INVENTORY_PATH, "policy-design-case-layer3-legal-mandate-search.md"),
        (REFERENCE_INDEX_PATH, "policy-design-case-layer3-legal-mandate-search.md"),
    )
    for path, needle in docs_checks:
        if needle not in _read_text_or_empty(repo_root, path):
            issues.append(
                _issue(
                    "layer3_gl_reference_index_missing",
                    path.as_posix(),
                    f"GL documentation/reference surface is missing marker: {needle}",
                )
            )
    return issues


def _validate_runtime_surfaces(bundle: gl.Layer3GLBundle) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    issues.extend(_validate_adapter_contract_registry(bundle))
    if bundle.public_export_projection_refs.raw_legal_payload_exported:
        issues.append(
            _issue(
                "layer3_gl_public_raw_legal_payload_leak",
                "$.public_export_projection_refs",
                "GL public projection refs must not export raw legal payloads.",
            )
        )
    if bundle.public_export_projection_refs.projection_mode != "reference_only":
        issues.append(
            _issue(
                "layer3_gl_public_export_projection_mode_mismatch",
                "$.public_export_projection_refs.projection_mode",
                "Task 1 GL projection mode is reference_only until a public-export hook exists.",
            )
        )
    if set(bundle.health_metric_delta.get("metric_ids", ())) < set(gl.EXPECTED_HEALTH_METRICS):
        issues.append(
            _issue(
                "layer3_gl_persisted_artifact_missing",
                "$.health_metric_delta.metric_ids",
                "GL health metric delta must include all expected metric ids.",
            )
        )
    return issues


def _validate_adapter_contract_registry(bundle: gl.Layer3GLBundle) -> list[dict[str, str]]:
    registry = _mapping(bundle.adapter_contract_registry)
    path_ids = {str(path_id) for path_id in _tuple(registry.get("adapter_path_ids"))}
    issues: list[dict[str, str]] = []
    if not registry or registry.get("status") != "pass":
        issues.append(
            _issue(
                "layer3_gl_adapter_contract_registry_missing",
                "$.adapter_contract_registry.status",
                "GL adapter contract registry must pass once Task 7 registers adapter paths.",
            )
        )
    missing = sorted(GL_ADAPTER_PATH_IDS - path_ids)
    if missing or int(registry.get("adapter_path_count") or 0) != len(path_ids):
        issues.append(
            _issue(
                "layer3_gl_adapter_registry_summary_only",
                "$.adapter_contract_registry.adapter_path_ids",
                f"GL adapter registry must preserve every adapter path id; missing={missing}.",
            )
        )
    unknown = sorted(path_ids - GL_ADAPTER_PATH_IDS)
    if unknown:
        issues.append(
            _issue(
                "layer3_gl_adapter_unknown_path",
                "$.adapter_contract_registry.adapter_path_ids",
                f"GL adapter registry includes unknown path ids: {unknown}.",
            )
        )
    public_routes = path_ids & {GL_REFERENCE_ONLY_PUBLIC_ROUTE, GL_PUBLIC_EXPORT_BUNDLE_ROUTE}
    if len(public_routes) != 1:
        issues.append(
            _issue(
                "layer3_gl_public_export_projection_mode_mismatch",
                "$.adapter_contract_registry.public_projection_route",
                "GL adapter registry must register exactly one public projection route.",
            )
        )
    projection_mode = str(registry.get("public_projection_mode") or "")
    if projection_mode != bundle.public_export_projection_refs.projection_mode:
        issues.append(
            _issue(
                "layer3_gl_public_export_projection_mode_mismatch",
                "$.adapter_contract_registry.public_projection_mode",
                "GL adapter registry projection mode must match runtime projection refs.",
            )
        )
    if projection_mode == "reference_only":
        if registry.get("public_projection_route") != GL_REFERENCE_ONLY_PUBLIC_ROUTE:
            issues.append(
                _issue(
                    "layer3_gl_public_export_projection_mode_mismatch",
                    "$.adapter_contract_registry.public_projection_route",
                    "Reference-only GL projection must route to reference-only surface.",
                )
            )
        if GL_PUBLIC_EXPORT_BUNDLE_ROUTE in path_ids or registry.get(
            "public_export_bundle_route_registered"
        ):
            issues.append(
                _issue(
                    "layer3_gl_public_export_hook_overclaimed",
                    "$.adapter_contract_registry.public_export_bundle_route_registered",
                    "Reference-only GL projection must not register public-export-bundle route.",
                )
            )
    return issues


def _summary(
    repo_root: Path,
    bundle: gl.Layer3GLBundle,
    runtime_report: Mapping[str, Any],
    drift_keys: Sequence[str],
) -> dict[str, Any]:
    summary = dict(bundle.readiness_manifest.model_dump(mode="json"))
    summary.update(_mapping(runtime_report.get("summary")))
    summary.update(
        {
            "schema_version": gl.LAYER3_GL_SCHEMA_VERSION,
            "rule_version": gl.LAYER3_GL_RULE_VERSION,
            "surface_id": bundle.legal_mandate_audit_surface.surface_id,
            "surface_audiences": list(bundle.legal_mandate_audit_surface.surface_audiences),
            "may_not_use_for": list(bundle.legal_mandate_audit_surface.may_not_use_for),
            "gl_conformance_status": bundle.conformance_report.status,
            "gl_conformance_issue_count": len(bundle.conformance_report.issue_codes),
            "gl_manifest_runtime_drift_key_count": len(drift_keys),
            "expected_artifact_count": len(EXPECTED_ARTIFACT_PATHS),
            "persisted_gl_artifact_count": sum(
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
        f"schema_version = {_toml_value(payload.get('schema_version', gl.LAYER3_GL_SCHEMA_VERSION))}",
        f"rule_version = {_toml_value(payload.get('rule_version', gl.LAYER3_GL_RULE_VERSION))}",
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
        f"schema_version = {_toml_value(gl.LAYER3_GL_SCHEMA_VERSION)}",
        f"rule_version = {_toml_value(gl.LAYER3_GL_RULE_VERSION)}",
        f"status = {_toml_value(payload.get('status', 'pass'))}",
        f"public_projection_mode = {_toml_value(payload.get('public_projection_mode', 'reference_only'))}",
        f"public_projection_route = {_toml_value(payload.get('public_projection_route', GL_REFERENCE_ONLY_PUBLIC_ROUTE))}",
        "public_export_bundle_route_registered = "
        f"{_toml_value(payload.get('public_export_bundle_route_registered', False))}",
        f"adapter_path_count = {_toml_value(payload.get('adapter_path_count', 0))}",
        "",
        "[adapter_contract_registry]",
        f"adapter_path_ids = {_toml_value(payload.get('adapter_path_ids', []))}",
    ]
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
    return value if value.replace("_", "").isalnum() else json.dumps(value)


def _dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _dump(inner) for key, inner in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_dump(item) for item in value]
    return value


def _normalize_issues(issues: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for issue in issues if isinstance(issues, Sequence) else []:
        if isinstance(issue, Mapping):
            normalized.append(
                _issue(
                    str(issue.get("code", "")),
                    str(issue.get("path", "$")),
                    str(issue.get("message", "")),
                )
            )
    return normalized


def _deduplicate_issues(issues: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []
    for issue in issues:
        key = (str(issue.get("code", "")), str(issue.get("path", "")))
        if key not in seen:
            seen.add(key)
            deduped.append(dict(issue))
    return deduped


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text_or_empty(repo_root: Path, path: Path) -> str:
    resolved = _resolve_repo_path(repo_root, path)
    if not resolved.exists():
        return ""
    return resolved.read_text(encoding="utf-8")


def _resolve_repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _tuple(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, bytes):
        return tuple(value)
    return (value,)


def _render_text_report(report: Mapping[str, Any]) -> str:
    lines = [f"layer3_gl_readiness_status={report.get('status', '')}"]
    summary = _mapping(report.get("summary"))
    for key in sorted(summary):
        lines.append(f"{key}={summary[key]}")
    issues = report.get("issues", [])
    if issues:
        lines.append("issues:")
        for issue in issues:
            if isinstance(issue, Mapping):
                lines.append(
                    f"- {issue.get('code', '')} {issue.get('path', '')}: {issue.get('message', '')}"
                )
    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
