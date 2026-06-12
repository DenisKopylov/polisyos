#!/usr/bin/env python3
"""Validate and optionally persist the Layer 3 G2 causal forecast bundle."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from polisyos.runtime.quality import layer3_causal_forecast as g2
from tools.lib.fs import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")
DOCS_REFERENCE_DIR = Path("docs/reference")

ADAPTER_ADMISSION_REGISTRY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_adapter_admission_registry.json"
)
L2_SKG_SEARCH_LEDGERS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_l2_skg_search_ledgers.json"
)
L2_SKG_QUERY_TRACES_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_l2_skg_query_traces.json"
)
L2_SKG_INDEX_COVERAGE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_l2_skg_index_coverage.json"
)
SEARCH_RECALL_FRESHNESS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_search_recall_freshness.json"
)
FOUNDRY_METHOD_REGISTRY_COVERAGE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_foundry_method_registry_coverage.json"
)
FOUNDRY_METHOD_REGISTRY_SEARCH_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_foundry_method_registry_search.json"
)
METHOD_REQUIREMENT_BINDINGS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_method_requirement_bindings.json"
)
METHOD_VALIDITY_TRANSPORT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_method_validity_transport.json"
)
SEMANTIC_SPINE_BINDINGS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_semantic_spine_bindings.json"
)
CONCEPT_ALIGNMENT_RECORDS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_concept_alignment_records.json"
)
S10_PREREQUISITE_BINDINGS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_s10_prerequisite_bindings.json"
)
FORECAST_SUPPORT_BINDINGS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_forecast_support_bindings.json"
)
GROUNDED_FORECAST_HANDOFFS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_grounded_forecast_handoffs.json"
)
OBSERVABLE_CALIBRATION_REPORT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_observable_calibration_report.json"
)
TRANSPORT_LIMIT_DECLARATIONS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_transport_limit_declarations.json"
)
AUTHORITY_ENVELOPES_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g2_authority_envelopes.json"
CONFORMANCE_REPORT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g2_conformance_report.json"
W12D_CONSUMER_GATE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g2_w12d_consumer_gate.json"
CAUSAL_FORECAST_AUDIT_SURFACE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_causal_forecast_audit_surface.json"
)
HEALTH_METRIC_DELTA_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g2_health_metric_delta.toml"
ADAPTER_CONTRACT_REGISTRY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_adapter_contract_registry.toml"
)
READINESS_MANIFEST_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g2_readiness_manifest.json"

GENERATED_ARTIFACTS_TOML_PATH = Path("architecture/generated_artifacts.toml")
GENERATED_ARTIFACTS_DOC_PATH = DOCS_REFERENCE_DIR / "generated-artifacts.md"
INVENTORY_PATH = POLICY_DESIGN_CASE_DIR / "inventory.json"
DOCS_SURFACE_PATH = DOCS_REFERENCE_DIR / "policy-design-case-layer3-causal-forecast.md"
DOCUMENTATION_INVENTORY_PATH = DOCS_REFERENCE_DIR / "documentation-inventory.md"
REFERENCE_INDEX_PATH = DOCS_REFERENCE_DIR / "index.md"
PUBLIC_SURFACE_PATH = DOCS_REFERENCE_DIR / "policy-design-case-layer3-causal-forecast.md"

G1_DEPENDENCY_PATHS: tuple[Path, ...] = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_readiness_manifest.json",
    POLICY_DESIGN_CASE_DIR / "layer3_g1_adapter_contract_registry.toml",
    POLICY_DESIGN_CASE_DIR / "layer3_g1_coverage_lineage_abstention_surface.json",
)
JSON_ARTIFACT_PATHS: tuple[Path, ...] = (
    ADAPTER_ADMISSION_REGISTRY_PATH,
    L2_SKG_SEARCH_LEDGERS_PATH,
    L2_SKG_QUERY_TRACES_PATH,
    L2_SKG_INDEX_COVERAGE_PATH,
    SEARCH_RECALL_FRESHNESS_PATH,
    FOUNDRY_METHOD_REGISTRY_COVERAGE_PATH,
    FOUNDRY_METHOD_REGISTRY_SEARCH_PATH,
    METHOD_REQUIREMENT_BINDINGS_PATH,
    METHOD_VALIDITY_TRANSPORT_PATH,
    SEMANTIC_SPINE_BINDINGS_PATH,
    CONCEPT_ALIGNMENT_RECORDS_PATH,
    S10_PREREQUISITE_BINDINGS_PATH,
    FORECAST_SUPPORT_BINDINGS_PATH,
    GROUNDED_FORECAST_HANDOFFS_PATH,
    OBSERVABLE_CALIBRATION_REPORT_PATH,
    TRANSPORT_LIMIT_DECLARATIONS_PATH,
    AUTHORITY_ENVELOPES_PATH,
    CONFORMANCE_REPORT_PATH,
    W12D_CONSUMER_GATE_PATH,
    CAUSAL_FORECAST_AUDIT_SURFACE_PATH,
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
    "g1_dependency_status",
    "g2_l2_skg_coverage_status",
    "g2_search_ledger_count",
    "g2_skg_query_trace_count",
    "g2_foundry_method_registry_coverage_status",
    "g2_method_requirement_binding_count",
    "g2_method_validity_report_status",
    "g2_semantic_spine_binding_count",
    "g2_s10_prerequisite_binding_status",
    "g2_forecast_support_binding_count",
    "g2_w12d_consumer_gate_status",
    "g2_search_engineering_quality_status",
    "g2_conformance_status",
    "g2_health_metric_ids",
)
ALL_ISSUE_CODES: tuple[str, ...] = tuple(dict.fromkeys(g2.ALL_ISSUE_CODES))


def validate_layer3_g2_readiness(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    """Build a Layer 3 G2 readiness report from runtime and registered surfaces."""

    root = Path(repo_root).resolve()
    runtime_bundle = g2.build_layer3_g2_bundle(root)
    if write:
        written_artifact_paths = _write_artifacts(root, runtime_bundle)
    else:
        written_artifact_paths = []

    runtime_report = g2.validate_layer3_g2_bundle(root, runtime_bundle).model_dump(
        mode="json"
    )
    drift_keys = _manifest_runtime_drift_keys(root, runtime_bundle)
    issues: list[dict[str, str]] = []
    issues.extend(_normalize_issues(runtime_report.get("issues", [])))
    issues.extend(_validate_persisted_artifacts(root))
    issues.extend(_validate_written_artifact_set(written_artifact_paths) if write else [])
    issues.extend(_validate_g1_dependency(root))
    issues.extend(_manifest_runtime_drift_issues(drift_keys))
    issues.extend(_validate_registration_and_docs(root))
    issues.extend(_validate_authority_posture(runtime_bundle))
    issues.extend(_validate_search_health(runtime_bundle))
    issues.extend(_validate_method_health(runtime_bundle))
    issues.extend(_validate_s10_and_w12d_bridge(runtime_bundle))
    issues.extend(_validate_conformance_health(runtime_bundle))

    normalized_issues = _deduplicate_issues(issues)
    return {
        "schema_version": g2.LAYER3_G2_SCHEMA_VERSION,
        "status": "fail" if normalized_issues else "pass",
        "issues": normalized_issues,
        "summary": _summary(root, runtime_bundle, runtime_report, drift_keys),
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
    """Run the Layer 3 G2 readiness check CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    report = validate_layer3_g2_readiness(args.repo_root, write=args.write)
    rendered = (
        _json_dumps(report) if args.output_format == "json" else _render_text_report(report)
    )
    if args.output is not None:
        output_path = _resolve_repo_path(Path(args.repo_root).resolve(), args.output)
        atomic_write_text(output_path, rendered)
    sys.stdout.write(rendered)
    return 0 if report["status"] == "pass" else 1


def _write_artifacts(repo_root: Path, bundle: g2.Layer3G2Bundle) -> list[str]:
    base = {
        "schema_version": g2.LAYER3_G2_SCHEMA_VERSION,
        "rule_version": g2.LAYER3_G2_RULE_VERSION,
    }
    payloads: dict[Path, Any] = {
        ADAPTER_ADMISSION_REGISTRY_PATH: {
            **base,
            "adapter_admission_registry": _dump(bundle.adapter_admission_registry),
        },
        L2_SKG_SEARCH_LEDGERS_PATH: {
            **base,
            "l2_skg_search_ledgers": _dump(bundle.l2_skg_search_ledgers),
        },
        L2_SKG_QUERY_TRACES_PATH: {
            **base,
            "l2_skg_query_traces": _dump(bundle.l2_skg_query_traces),
        },
        L2_SKG_INDEX_COVERAGE_PATH: {
            **base,
            "l2_skg_index_coverage": _dump(bundle.l2_skg_index_coverage),
        },
        SEARCH_RECALL_FRESHNESS_PATH: {
            **base,
            "search_recall_freshness": _dump(bundle.search_recall_freshness),
        },
        FOUNDRY_METHOD_REGISTRY_COVERAGE_PATH: {
            **base,
            "foundry_method_registry_coverage": _dump(
                bundle.foundry_method_registry_coverage
            ),
        },
        FOUNDRY_METHOD_REGISTRY_SEARCH_PATH: {
            **base,
            "foundry_method_registry_search": _dump(bundle.foundry_method_registry_search),
        },
        METHOD_REQUIREMENT_BINDINGS_PATH: {
            **base,
            "method_requirement_bindings": _dump(bundle.method_requirement_bindings),
        },
        METHOD_VALIDITY_TRANSPORT_PATH: {
            **base,
            "method_validity_transport": _dump(bundle.method_validity_transport),
        },
        SEMANTIC_SPINE_BINDINGS_PATH: {
            **base,
            "semantic_spine_bindings": _dump(bundle.semantic_spine_bindings),
        },
        CONCEPT_ALIGNMENT_RECORDS_PATH: {
            **base,
            "concept_alignment_records": _dump(bundle.concept_alignment_records),
        },
        S10_PREREQUISITE_BINDINGS_PATH: {
            **base,
            "s10_prerequisite_bindings": _dump(bundle.s10_prerequisite_bindings),
        },
        FORECAST_SUPPORT_BINDINGS_PATH: {
            **base,
            "forecast_support_bindings": _dump(bundle.forecast_support_bindings),
        },
        GROUNDED_FORECAST_HANDOFFS_PATH: {
            **base,
            "grounded_forecast_handoffs": _dump(bundle.grounded_forecast_handoffs),
        },
        OBSERVABLE_CALIBRATION_REPORT_PATH: {
            **base,
            "observable_calibration_report": _dump(bundle.observable_calibration_report),
        },
        TRANSPORT_LIMIT_DECLARATIONS_PATH: {
            **base,
            "transport_limit_declarations": _dump(bundle.transport_limit_declarations),
        },
        AUTHORITY_ENVELOPES_PATH: {
            **base,
            "authority_envelopes": _dump(bundle.authority_envelopes),
        },
        CONFORMANCE_REPORT_PATH: {
            **base,
            "conformance_report": _dump(bundle.conformance_report),
        },
        W12D_CONSUMER_GATE_PATH: {
            **base,
            "w12d_consumer_gate": _dump(bundle.w12d_consumer_gate),
        },
        CAUSAL_FORECAST_AUDIT_SURFACE_PATH: {
            **base,
            "causal_forecast_audit_surface": _dump(bundle.causal_forecast_audit_surface),
        },
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
            "layer3_g2_persisted_artifact_missing",
            path.as_posix(),
            "Layer 3 G2 readiness requires persisted runtime artifacts.",
        )
        for path in EXPECTED_ARTIFACT_PATHS
        if not _resolve_repo_path(repo_root, path).exists()
    ]


def _validate_written_artifact_set(written_paths: Sequence[str]) -> list[dict[str, str]]:
    expected = {path.as_posix() for path in EXPECTED_ARTIFACT_PATHS}
    written = {str(path) for path in written_paths}
    return [
        _issue(
            "layer3_g2_persisted_artifact_missing",
            path,
            "G2 --write must emit every expected persisted artifact path.",
        )
        for path in sorted(expected - written)
    ]


def _validate_g1_dependency(repo_root: Path) -> list[dict[str, str]]:
    issues = [
        _issue(
            "layer3_g2_g1_dependency_not_ready",
            path.as_posix(),
            "Layer 3 G2 requires ready G1 substrate grounding artifacts.",
        )
        for path in G1_DEPENDENCY_PATHS
        if not _resolve_repo_path(repo_root, path).exists()
    ]
    manifest_path = _resolve_repo_path(
        repo_root, POLICY_DESIGN_CASE_DIR / "layer3_g1_readiness_manifest.json"
    )
    if not manifest_path.exists():
        return issues
    try:
        manifest = _read_json(manifest_path)
    except (OSError, json.JSONDecodeError) as error:
        return [
            *issues,
            _issue(
                "layer3_g2_g1_dependency_not_ready",
                str(manifest_path),
                f"G1 readiness manifest could not be loaded: {error}",
            ),
        ]
    counts = _mapping(manifest.get("counts"))
    degraded = (
        manifest.get("schema_version") != "policyos.policy_design_case.layer3_g1_substrate_grounding.v1"
        or counts.get("g0_v2_dependency_status") != "pass"
        or counts.get("g1_l1_l5_l6_index_coverage_status") != "pass"
        or counts.get("g1_search_recall_status") != "pass"
        or counts.get("g1_index_freshness_status") != "pass"
        or counts.get("g1_search_engineering_quality_status") != "pass"
    )
    if degraded:
        issues.append(
            _issue(
                "layer3_g2_g1_dependency_not_ready",
                "architecture/policy_design_case/layer3_g1_readiness_manifest.json",
                "G1 readiness manifest is not pass-ready for G2 causal forecast use.",
            )
        )
    return issues


def _manifest_runtime_drift_keys(
    repo_root: Path,
    runtime_bundle: g2.Layer3G2Bundle,
) -> list[str]:
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
            "layer3_g2_manifest_runtime_drift",
            READINESS_MANIFEST_PATH.as_posix(),
            f"Persisted G2 readiness manifest drifted from runtime: {sorted(drift_keys)}",
        )
    ]


def _validate_registration_and_docs(repo_root: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    generated_text = _read_text_or_empty(repo_root, GENERATED_ARTIFACTS_TOML_PATH)
    if (
        g2.LAYER3_G2_GENERATED_ARTIFACT_FAMILY_ID not in generated_text
        or not all(path.as_posix() in generated_text for path in EXPECTED_ARTIFACT_PATHS)
    ):
        issues.append(
            _issue(
                "layer3_g2_generated_artifacts_family_missing",
                _path_label(GENERATED_ARTIFACTS_TOML_PATH),
                "architecture/generated_artifacts.toml must register the G2 artifact family.",
            )
        )
    if not _resolve_repo_path(repo_root, ADAPTER_CONTRACT_REGISTRY_PATH).exists():
        issues.append(
            _issue(
                "layer3_g2_adapter_contract_registry_missing",
                _path_label(ADAPTER_CONTRACT_REGISTRY_PATH),
                "G2 adapter contract registry TOML must be persisted.",
            )
        )

    inventory_path = _resolve_repo_path(repo_root, INVENTORY_PATH)
    try:
        inventory = _read_json(inventory_path)
    except (OSError, json.JSONDecodeError) as error:
        issues.append(
            _issue(
                "layer3_g2_inventory_surface_missing",
                _path_label(INVENTORY_PATH),
                f"Policy Design Case inventory could not be loaded: {error}",
            )
        )
    else:
        surface = next(
            (
                item
                for item in _sequence(inventory.get("artifacts", ()))
                if isinstance(item, Mapping)
                and item.get("id") == g2.LAYER3_G2_SURFACE_ID
            ),
            None,
        )
        if not isinstance(surface, Mapping):
            issues.append(
                _issue(
                    "layer3_g2_inventory_surface_missing",
                    _path_label(INVENTORY_PATH),
                    f"Inventory must register {g2.LAYER3_G2_SURFACE_ID}.",
                )
            )
        else:
            audiences = set(_sequence(surface.get("surface_audiences")))
            if not {"PUBLIC", "REVIEWER", "EXPERT", "MACHINE"} <= audiences:
                issues.append(
                    _issue(
                        "layer3_g2_public_surface_visibility_missing",
                        "$.artifacts[layer3_g2_causal_forecast_audit_surface]",
                        "G2 surface must expose tier/uncertainty/limitations to PUBLIC and REVIEWER.",
                    )
                )

    docs_checks = (
        (
            GENERATED_ARTIFACTS_DOC_PATH,
            "layer3_g2_w12d_consumer_gate.json",
            "layer3_g2_generated_artifacts_family_missing",
        ),
        (
            DOCS_SURFACE_PATH,
            "may_not_use_for",
            "layer3_g2_surface_unsynced",
        ),
        (
            DOCS_SURFACE_PATH,
            "uncertainty_interval_refs",
            "layer3_g2_public_surface_visibility_missing",
        ),
        (
            DOCUMENTATION_INVENTORY_PATH,
            "policy-design-case-layer3-causal-forecast.md",
            "layer3_g2_surface_unsynced",
        ),
        (
            REFERENCE_INDEX_PATH,
            "policy-design-case-layer3-causal-forecast.md",
            "layer3_g2_reference_index_missing",
        ),
        (
            PUBLIC_SURFACE_PATH,
            g2.LAYER3_G2_SURFACE_ID,
            "layer3_g2_public_surface_visibility_missing",
        ),
        (
            PUBLIC_SURFACE_PATH,
            "PUBLIC/REVIEWER",
            "layer3_g2_public_surface_visibility_missing",
        ),
    )
    for path, needle, code in docs_checks:
        text = _read_text_or_empty(repo_root, path)
        if needle not in text:
            issues.append(
                _issue(
                    code,
                    _path_label(path),
                    f"G2 documentation/reference surface is missing required marker: {needle}",
                )
            )
    return issues


def _validate_authority_posture(bundle: g2.Layer3G2Bundle) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    surface = bundle.causal_forecast_audit_surface
    if surface.status != "pass":
        for code in surface.issue_codes or ("layer3_g2_surface_unsynced",):
            issues.append(_issue(code, "$.causal_forecast_audit_surface", code))
    if not set(g2.G2_REQUIRED_AUTHORITY_DENIALS) <= set(surface.may_not_use_for):
        issues.append(
            _issue(
                "layer3_g2_public_surface_visibility_missing",
                "$.causal_forecast_audit_surface.may_not_use_for",
                "G2 audit surface must publish denied uses.",
            )
        )
    gate = bundle.w12d_consumer_gate
    if gate.closeout_claimed or gate.recommendation_authority_claimed or gate.claim_authority_claimed:
        issues.append(
            _issue(
                "layer3_g2_closeout_authority_leak",
                "$.w12d_consumer_gate",
                "G2 cannot claim closeout, recommendation, or claim authority.",
            )
        )
    return issues


def _validate_search_health(bundle: g2.Layer3G2Bundle) -> list[dict[str, str]]:
    checks = (
        (
            bundle.l2_skg_index_coverage.status == "pass",
            "layer3_g2_l2_skg_index_coverage_missing",
            "L2 SKG index coverage must pass.",
        ),
        (
            len(bundle.l2_skg_search_ledgers) >= 1,
            "layer3_g2_search_ledger_missing",
            "G2 requires a replayable L2 SKG search ledger.",
        ),
        (
            len(bundle.l2_skg_query_traces) >= 1,
            "layer3_g2_skg_query_trace_missing",
            "G2 requires replayable SKG query traces.",
        ),
        (
            bundle.search_recall_freshness.status == "pass",
            "layer3_g2_search_recall_seed_miss_blocks_domain_ceiling",
            "G2 search recall/freshness must pass.",
        ),
        (
            bundle.search_engineering_quality.status == "pass",
            "layer3_g2_search_engineering_quality_failed",
            "G2 search implementation must be indexed, bounded, deterministic, and scalable.",
        ),
        (
            bundle.free_growth_report is not None
            and bundle.free_growth_report.status == "pass",
            "layer3_g2_free_growth_fixture_failed",
            "G2 free-growth SKG/method fixture must pass.",
        ),
    )
    return [_issue(code, "$.readiness_manifest", message) for passed, code, message in checks if not passed]


def _validate_method_health(bundle: g2.Layer3G2Bundle) -> list[dict[str, str]]:
    checks = (
        (
            bundle.foundry_method_registry_coverage.status == "pass",
            "layer3_g2_foundry_discovery_coverage_missing",
            "Foundry method registry coverage must pass.",
        ),
        (
            len(bundle.method_requirement_bindings) >= 1
            and all(binding.status == "pass" for binding in bundle.method_requirement_bindings),
            "layer3_g2_method_requirement_missing",
            "G2 requires passing method-requirement bindings.",
        ),
        (
            len(bundle.method_validity_transport) >= 1
            and all(record.status == "pass" for record in bundle.method_validity_transport),
            "layer3_g2_method_validity_missing",
            "G2 requires passing Foundry method validity transport records.",
        ),
    )
    return [_issue(code, "$.readiness_manifest", message) for passed, code, message in checks if not passed]


def _validate_s10_and_w12d_bridge(bundle: g2.Layer3G2Bundle) -> list[dict[str, str]]:
    checks = (
        (
            len(bundle.semantic_spine_bindings) >= 1
            and all(binding.status == "pass" for binding in bundle.semantic_spine_bindings),
            "layer3_g2_semantic_binding_spine_missing",
            "G2 requires passing semantic-spine bindings.",
        ),
        (
            len(bundle.s10_prerequisite_bindings) >= 1
            and all(binding.status == "pass" for binding in bundle.s10_prerequisite_bindings),
            "layer3_g2_s10_prerequisite_binding_missing",
            "G2 requires passing S10 prerequisite bindings.",
        ),
        (
            len(bundle.forecast_support_bindings) >= 1
            and all(binding.status == "pass" for binding in bundle.forecast_support_bindings),
            "layer3_g2_forecast_support_missing",
            "G2 requires S10 ForecastSupport bindings.",
        ),
        (
            bundle.w12d_consumer_gate.status == "pass"
            and bundle.w12d_consumer_gate.posture_consumed,
            "layer3_g2_s10_consumer_bridge_missing",
            "W12D must consume the G2 public S10 forecast posture.",
        ),
        (
            len(bundle.grounded_forecast_handoffs) >= 1
            and all(handoff.status == "pass" for handoff in bundle.grounded_forecast_handoffs),
            "layer3_g2_grounded_forecast_handoff_missing",
            "G2 requires G4/G5-readable grounded forecast handoffs.",
        ),
    )
    return [_issue(code, "$.readiness_manifest", message) for passed, code, message in checks if not passed]


def _validate_conformance_health(bundle: g2.Layer3G2Bundle) -> list[dict[str, str]]:
    report = bundle.conformance_report
    if report.status == "pass" and report.conformance_status == "pass":
        return []
    issue_codes = report.issue_codes or ("layer3_g2_forecast_support_missing",)
    return [
        _issue(
            code,
            "$.conformance_report",
            "G2 final conformance battery must pass before readiness closeout.",
        )
        for code in issue_codes
    ]


def _summary(
    repo_root: Path,
    bundle: g2.Layer3G2Bundle,
    runtime_report: Mapping[str, Any],
    drift_keys: Sequence[str],
) -> dict[str, Any]:
    summary = dict(bundle.readiness_manifest.model_dump(mode="json"))
    summary.update(_mapping(runtime_report.get("summary")))
    summary.update(
        {
            "schema_version": g2.LAYER3_G2_SCHEMA_VERSION,
            "rule_version": g2.LAYER3_G2_RULE_VERSION,
            "surface_id": bundle.causal_forecast_audit_surface.surface_id,
            "surface_audiences": list(bundle.causal_forecast_audit_surface.surface_audiences),
            "forecast_tiers": list(bundle.causal_forecast_audit_surface.forecast_tiers),
            "uncertainty_interval_refs": list(
                bundle.causal_forecast_audit_surface.uncertainty_interval_refs
            ),
            "may_not_use_for": list(bundle.causal_forecast_audit_surface.may_not_use_for),
            "g2_conformance_status": bundle.conformance_report.status,
            "g2_conformance_issue_count": len(bundle.conformance_report.issue_codes),
            "g2_manifest_runtime_drift_key_count": len(drift_keys),
            "expected_artifact_count": len(EXPECTED_ARTIFACT_PATHS),
            "persisted_g2_artifact_count": sum(
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
        f"schema_version = {_toml_value(payload.get('schema_version', g2.LAYER3_G2_SCHEMA_VERSION))}",
        f"rule_version = {_toml_value(payload.get('rule_version', g2.LAYER3_G2_RULE_VERSION))}",
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
        f"schema_version = {_toml_value(payload.get('schema_version', g2.LAYER3_G2_SCHEMA_VERSION))}",
        f"rule_version = {_toml_value(payload.get('rule_version', g2.LAYER3_G2_RULE_VERSION))}",
        f"status = {_toml_value(payload.get('status', 'pass'))}",
        f"registry_id = {_toml_value(payload.get('registry_id', 'layer3-g2-adapter-contract-registry'))}",
        "",
        "[adapter_contract_registry]",
        f"adapter_contract_refs = {_toml_value(payload.get('adapter_contract_refs', []))}",
        f"capability_reality_label = {_toml_value(payload.get('capability_reality_label', 'implemented'))}",
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


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
    lines = [f"layer3_g2_readiness_status={report.get('status', '')}"]
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


def _path_label(path: Path) -> str:
    return path.as_posix() if not path.is_absolute() else str(path)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        sys.stderr.write(str(exc))
        raise
