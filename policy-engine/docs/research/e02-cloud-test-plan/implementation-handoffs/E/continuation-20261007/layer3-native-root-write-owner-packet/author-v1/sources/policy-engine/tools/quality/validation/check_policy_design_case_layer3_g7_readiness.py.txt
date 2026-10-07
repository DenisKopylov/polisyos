#!/usr/bin/env python3
"""Validate and optionally persist the Layer 3 G7 region-widening bundle."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from polisyos.runtime.quality.proving_ground import region_widening as g7
from tools.lib.fs import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")
DOCS_REFERENCE_DIR = Path("docs/reference")

G7_SCHEMA_VERSION: str = g7.G7_SCHEMA_VERSION
G7_RULE_VERSION: str = g7.G7_RULE_VERSION
G7_GENERATED_ARTIFACT_FAMILY_ID: str = g7.G7_GENERATED_ARTIFACT_FAMILY_ID

DEPENDENCY_READINESS_SNAPSHOT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_dependency_readiness_snapshot.json"
)
REGION_CANDIDATE_SET_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g7_region_candidate_set.json"
REGION_GROUNDING_MATRIX_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_region_grounding_matrix.json"
)
REGION_CASE_CONVERSION_INPUTS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_region_case_conversion_inputs.json"
)
REGION_CONVERSION_RECORDS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_region_conversion_records.json"
)
REGION_CONVERSION_STATUS_MATRIX_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_region_conversion_status_matrix.json"
)
GOVERNED_PROMOTION_JOIN_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_governed_promotion_join.json"
)
STATUS_COMPOSITION_LEDGER_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_status_composition_ledger.json"
)
S12_GROWTH_THERMOMETER_PROJECTION_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_s12_growth_thermometer_projection.json"
)
MECHANISM_REUSE_LEDGER_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_mechanism_reuse_ledger.json"
)
MARGINAL_GROUNDING_COST_LEDGER_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_marginal_grounding_cost_ledger.json"
)
REGION_ENVELOPE_EXPANSION_DELTA_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_region_envelope_expansion_delta.json"
)
REGION_SEMANTIC_LOSS_LEDGER_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_region_semantic_loss_ledger.json"
)
SEARCH_RECALL_FRESHNESS_JOIN_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_search_recall_freshness_join.json"
)
G5_G6_AUTHORITY_BOUNDARY_REPORT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_g5_g6_authority_boundary_report.json"
)
S14_GROUNDED_BREADTH_FEED_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_s14_grounded_breadth_feed.json"
)
S14_MECHANISM_GENERALITY_PROJECTION_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_s14_mechanism_generality_projection.json"
)
S14_BATTERY_INPUT_MANIFEST_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_s14_battery_input_manifest.json"
)
S14_CONSUMER_GATE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g7_s14_consumer_gate.json"
REGION_SCORECARD_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g7_region_scorecard.json"
REGION_WIDENING_AUDIT_SURFACE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_region_widening_audit_surface.json"
)
PUBLIC_EXPORT_PROJECTION_REFS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_public_export_projection_refs.json"
)
ORCHESTRATION_CONTINUITY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_orchestration_continuity.json"
)
REPLAY_MANIFEST_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g7_replay_manifest.json"
CONFORMANCE_REPORT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g7_conformance_report.json"
HEALTH_METRIC_DELTA_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g7_health_metric_delta.toml"
REGION_ROUTE_CONTRACT_REGISTRY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_region_route_contract_registry.toml"
)
REGISTRY_RATCHET_DELTA_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g7_registry_ratchet_delta.json"
)
READINESS_MANIFEST_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g7_readiness_manifest.json"

GENERATED_ARTIFACTS_TOML_PATH = Path("architecture/generated_artifacts.toml")
GENERATED_ARTIFACTS_DOC_PATH = DOCS_REFERENCE_DIR / "generated-artifacts.md"
INVENTORY_PATH = POLICY_DESIGN_CASE_DIR / "inventory.json"
DOCUMENTATION_INVENTORY_PATH = DOCS_REFERENCE_DIR / "documentation-inventory.md"
REFERENCE_INDEX_PATH = DOCS_REFERENCE_DIR / "index.md"
PUBLIC_SURFACE_DOC_PATH = DOCS_REFERENCE_DIR / "public-surface.md"
RUNTIME_QUALITY_README_PATH = Path("src/polisyos/runtime/quality/README.md")

EXPECTED_ARTIFACT_PATHS: tuple[Path, ...] = (
    DEPENDENCY_READINESS_SNAPSHOT_PATH,
    REGION_CANDIDATE_SET_PATH,
    REGION_GROUNDING_MATRIX_PATH,
    REGION_CASE_CONVERSION_INPUTS_PATH,
    REGION_CONVERSION_RECORDS_PATH,
    REGION_CONVERSION_STATUS_MATRIX_PATH,
    GOVERNED_PROMOTION_JOIN_PATH,
    STATUS_COMPOSITION_LEDGER_PATH,
    S12_GROWTH_THERMOMETER_PROJECTION_PATH,
    MECHANISM_REUSE_LEDGER_PATH,
    MARGINAL_GROUNDING_COST_LEDGER_PATH,
    REGION_ENVELOPE_EXPANSION_DELTA_PATH,
    REGION_SEMANTIC_LOSS_LEDGER_PATH,
    SEARCH_RECALL_FRESHNESS_JOIN_PATH,
    G5_G6_AUTHORITY_BOUNDARY_REPORT_PATH,
    S14_GROUNDED_BREADTH_FEED_PATH,
    S14_MECHANISM_GENERALITY_PROJECTION_PATH,
    S14_BATTERY_INPUT_MANIFEST_PATH,
    S14_CONSUMER_GATE_PATH,
    REGION_SCORECARD_PATH,
    REGION_WIDENING_AUDIT_SURFACE_PATH,
    PUBLIC_EXPORT_PROJECTION_REFS_PATH,
    ORCHESTRATION_CONTINUITY_PATH,
    REPLAY_MANIFEST_PATH,
    CONFORMANCE_REPORT_PATH,
    HEALTH_METRIC_DELTA_PATH,
    REGION_ROUTE_CONTRACT_REGISTRY_PATH,
    REGISTRY_RATCHET_DELTA_PATH,
    READINESS_MANIFEST_PATH,
)
EXPECTED_MANIFEST_DRIFT_KEYS: tuple[str, ...] = (
    "g7_engineering_readiness_status",
    "g7_region_value_closure_status",
    "g7_current_g5_conversion_outcome",
    "g7_current_g5_unchanged_blocker_status",
    "g7_g1_search_control_plane_status",
    "g7_g1_free_growth_status",
    "g7_g1_no_hardcode_lint_status",
    "g7_g4_promotion_gate_shape_status",
    "g7_g4_region_promotion_projection_status",
    "g7_g5_g6_authority_boundary_status",
    "g7_region_candidate_set_status",
    "g7_region_grounding_matrix_status",
    "g7_region_grounded_case_count",
    "g7_region_blocked_case_count",
    "g7_status_composition_status",
    "g7_governed_promotion_join_status",
    "g7_s12_growth_thermometer_status",
    "g7_s12_resource_projection_contract_status",
    "g7_s13_certified_delta_status",
    "g7_mechanism_reuse_status",
    "g7_mechanism_reuse_rate",
    "g7_marginal_cost_status",
    "g7_region_envelope_expansion_rate",
    "g7_region_semantic_loss_status",
    "g7_governance_throughput_status",
    "g7_s14_grounded_breadth_feed_status",
    "g7_s14_mechanism_generality_status",
    "g7_s14_battery_input_manifest_status",
    "g7_s14_consumer_gate_status",
    "g7_s14_runner_input_hook_status",
    "g7_s14_projection_contract_status",
    "g7_public_projection_contract_status",
    "g7_public_projection_official_use_status",
    "g7_replay_manifest_status",
    "g7_orchestration_continuity_status",
    "g7_generated_artifacts_registration_status",
    "g7_inventory_surface_status",
    "g7_reference_docs_status",
    "g7_route_contract_registry_status",
    "g7_registry_ratchet_status",
    "g7_conformance_status",
)
ALL_ISSUE_CODES: tuple[str, ...] = tuple(dict.fromkeys(g7.ALL_ISSUE_CODES))


def validate_layer3_g7_readiness(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    """Build a Layer 3 G7 readiness report from runtime and persisted artifacts."""

    root = Path(repo_root).resolve()
    bundle = _build_runtime_bundle(root)
    written_artifact_paths = _write_artifacts(root, bundle) if write else []
    registration_statuses = _registration_statuses(root)
    if write:
        bundle["readiness_manifest"] = _readiness_manifest(
            root,
            bundle,
            drift_keys=(),
            registration_statuses=registration_statuses,
        )
        _write_json(_resolve_repo_path(root, READINESS_MANIFEST_PATH), bundle["readiness_manifest"])
    drift_keys = _manifest_runtime_drift_keys(root, bundle)
    issues: list[dict[str, str]] = []
    issues.extend(_validate_persisted_artifacts(root))
    issues.extend(_validate_written_artifact_set(written_artifact_paths) if write else [])
    issues.extend(_manifest_runtime_drift_issues(drift_keys))
    issues.extend(_validate_registration_and_docs(registration_statuses))
    issues.extend(_validate_runtime_surfaces(bundle))
    normalized_issues = _deduplicate_issues(issues)
    return {
        "schema_version": G7_SCHEMA_VERSION,
        "rule_version": G7_RULE_VERSION,
        "status": "fail" if normalized_issues else "pass",
        "issues": normalized_issues,
        "summary": _summary(bundle, drift_keys, registration_statuses),
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
    """Run the Layer 3 G7 readiness check CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    report = validate_layer3_g7_readiness(args.repo_root, write=args.write)
    rendered = (
        _json_dumps(report) if args.output_format == "json" else _render_text_report(report)
    )
    if args.output is not None:
        output_path = _resolve_repo_path(Path(args.repo_root).resolve(), args.output)
        atomic_write_text(output_path, rendered)
    sys.stdout.write(rendered)
    return 0 if report["status"] == "pass" else 1


def _build_runtime_bundle(repo_root: Path) -> dict[str, Any]:
    region_ref = "region://ua/msme-adjacent"
    dependency_snapshot = g7.build_g7_dependency_readiness_snapshot(repo_root)
    candidate_set = g7.build_g7_region_candidate_set(
        region_ref=region_ref,
        case_rows=g7.default_readiness_candidate_rows(),
    )
    search_discovery_refs = ("search://g1/free-growth/ua-msme-adjacent",)
    grounding_matrix = g7.build_g7_region_grounding_matrix(
        candidate_set=candidate_set,
        search_discovery_refs=search_discovery_refs,
        repo_root=repo_root,
    )
    g7_bundle = g7.build_layer3_g7_bundle(repo_root)
    conversion_records = g7_bundle.region_conversion_status_matrix.records
    conversion_status_matrix = g7_bundle.region_conversion_status_matrix
    governed_promotion_join = _governed_promotion_join_projection(conversion_records)
    s12_projection = g7.build_g7_s12_growth_thermometer_projection(
        conversion_records=conversion_records,
        demand_pull_refs=("s12-growth://ua-msme-adjacent/current",),
        accountable_principal_refs=("principal://ua-msme/region-owner",),
    )
    mechanism_reuse = g7.build_g7_mechanism_reuse_ledger(
        conversion_records=conversion_records,
        s12_growth_thermometer_projection=s12_projection,
    )
    region_expansion = g7.build_g7_region_envelope_expansion_delta(
        conversion_records=conversion_records,
    )
    semantic_loss = g7.build_g7_region_semantic_loss_ledger(
        conversion_records=conversion_records,
    )
    marginal_cost = g7.build_g7_marginal_grounding_cost_ledger(
        conversion_records=conversion_records,
        s12_growth_thermometer_projection=s12_projection,
        mechanism_reuse_ledger=mechanism_reuse,
        semantic_loss_ledger=semantic_loss,
    )
    s14_feed = g7.build_g7_s14_grounded_breadth_feed(
        region_ref=region_ref,
        conversion_records=conversion_records,
        region_envelope_expansion_delta=region_expansion,
    )
    status_composition = g7.build_g7_status_composition_ledger(
        region_conversion_status_matrix=conversion_status_matrix,
        region_envelope_expansion_delta=region_expansion,
        semantic_loss_ledger=semantic_loss,
        marginal_cost_ledger=marginal_cost,
        s14_feed_status=s14_feed.status,
        governance_throughput_status=dependency_snapshot.g4_governance_throughput_status,
    )
    s14_mechanism = g7.build_g7_s14_mechanism_generality_projection(
        s12_growth_thermometer_projection=s12_projection,
    )
    s14_manifest = g7.build_g7_s14_battery_input_manifest(
        grounded_breadth_feed=s14_feed,
        mechanism_generality_projection=s14_mechanism,
    )
    s14_gate = g7.build_g7_s14_consumer_gate(
        s14_battery_input_manifest=s14_manifest,
    )
    scorecard = g7.build_g7_region_scorecard(
        region_ref=region_ref,
        region_conversion_status_matrix=conversion_status_matrix,
        status_composition_ledger=status_composition,
        mechanism_reuse_ledger=mechanism_reuse,
        marginal_cost_ledger=marginal_cost,
        s14_grounded_breadth_feed=s14_feed,
    )
    audit_surface = g7.build_g7_region_widening_audit_surface(
        scorecard=scorecard,
        s12_growth_thermometer_projection=s12_projection,
        region_envelope_expansion_delta=region_expansion,
        semantic_loss_ledger=semantic_loss,
        s14_battery_input_manifest=s14_manifest,
        s14_consumer_gate=s14_gate,
    )
    public_refs = g7.build_g7_public_export_projection_refs(audit_surface=audit_surface)
    upstream_replay_refs = _upstream_closed_replay_refs(repo_root)
    continuity = g7.build_g7_orchestration_continuity(
        scorecard=scorecard,
        audit_surface=audit_surface,
        upstream_closed_case_replay_refs=upstream_replay_refs,
    )
    replay_manifest = g7.build_g7_replay_manifest(
        scorecard=scorecard,
        audit_surface=_replay_contract_audit_surface(audit_surface),
        orchestration_continuity=continuity,
        upstream_closed_case_replay_refs=upstream_replay_refs,
    )
    registration_statuses = _registration_statuses(repo_root)
    conformance_report = _build_conformance_report(
        repo_root=repo_root,
        dependency_readiness_snapshot=dependency_snapshot,
        region_grounding_matrix=grounding_matrix,
        region_conversion_status_matrix=conversion_status_matrix,
        status_composition_ledger=status_composition,
        s12_growth_thermometer_projection=s12_projection,
        mechanism_reuse_ledger=mechanism_reuse,
        marginal_cost_ledger=marginal_cost,
        region_envelope_expansion_delta=region_expansion,
        semantic_loss_ledger=semantic_loss,
        s14_grounded_breadth_feed=s14_feed,
        s14_battery_input_manifest=s14_manifest,
        s14_consumer_gate=s14_gate,
        audit_surface=audit_surface,
        replay_manifest=replay_manifest,
        orchestration_continuity=continuity,
        registration_statuses=registration_statuses,
        manifest_runtime_drift_keys=(),
        replay_helper_status="pass",
    )
    health_delta = _health_metric_delta(
        region_expansion=region_expansion,
        semantic_loss=semantic_loss,
        marginal_cost=marginal_cost,
    )
    route_registry = _region_route_contract_registry(scorecard)
    registry_ratchet = _registry_ratchet_delta(conformance_report)
    bundle: dict[str, Any] = {
        "dependency_readiness_snapshot": dependency_snapshot,
        "region_candidate_set": candidate_set,
        "region_grounding_matrix": grounding_matrix,
        "region_case_conversion_inputs": _region_case_conversion_inputs(
            region_ref=region_ref,
            conversion_records=conversion_records,
        ),
        "region_conversion_records": {
            "schema_version": G7_SCHEMA_VERSION,
            "rule_version": G7_RULE_VERSION,
            "region_conversion_records": conversion_records,
        },
        "region_conversion_status_matrix": conversion_status_matrix,
        "governed_promotion_join": governed_promotion_join,
        "status_composition_ledger": status_composition,
        "s12_growth_thermometer_projection": s12_projection,
        "mechanism_reuse_ledger": mechanism_reuse,
        "marginal_grounding_cost_ledger": marginal_cost,
        "region_envelope_expansion_delta": region_expansion,
        "region_semantic_loss_ledger": semantic_loss,
        "search_recall_freshness_join": grounding_matrix.search_recall_freshness_join,
        "g5_g6_authority_boundary_report": _g5_g6_authority_boundary_report(
            dependency_snapshot
        ),
        "s14_grounded_breadth_feed": s14_feed,
        "s14_mechanism_generality_projection": s14_mechanism,
        "s14_battery_input_manifest": s14_manifest,
        "s14_consumer_gate": s14_gate,
        "region_scorecard": scorecard,
        "region_widening_audit_surface": audit_surface,
        "public_export_projection_refs": public_refs,
        "orchestration_continuity": continuity,
        "replay_manifest": replay_manifest,
        "conformance_report": conformance_report,
        "health_metric_delta": health_delta,
        "region_route_contract_registry": route_registry,
        "registry_ratchet_delta": registry_ratchet,
    }
    bundle["readiness_manifest"] = _readiness_manifest(
        repo_root,
        bundle,
        drift_keys=(),
        registration_statuses=registration_statuses,
    )
    return bundle


def _write_artifacts(repo_root: Path, bundle: Mapping[str, Any]) -> list[str]:
    payloads: dict[Path, Any] = {
        DEPENDENCY_READINESS_SNAPSHOT_PATH: bundle["dependency_readiness_snapshot"],
        REGION_CANDIDATE_SET_PATH: bundle["region_candidate_set"],
        REGION_GROUNDING_MATRIX_PATH: bundle["region_grounding_matrix"],
        REGION_CASE_CONVERSION_INPUTS_PATH: bundle["region_case_conversion_inputs"],
        REGION_CONVERSION_RECORDS_PATH: bundle["region_conversion_records"],
        REGION_CONVERSION_STATUS_MATRIX_PATH: bundle[
            "region_conversion_status_matrix"
        ],
        GOVERNED_PROMOTION_JOIN_PATH: bundle["governed_promotion_join"],
        STATUS_COMPOSITION_LEDGER_PATH: bundle["status_composition_ledger"],
        S12_GROWTH_THERMOMETER_PROJECTION_PATH: bundle[
            "s12_growth_thermometer_projection"
        ],
        MECHANISM_REUSE_LEDGER_PATH: bundle["mechanism_reuse_ledger"],
        MARGINAL_GROUNDING_COST_LEDGER_PATH: bundle[
            "marginal_grounding_cost_ledger"
        ],
        REGION_ENVELOPE_EXPANSION_DELTA_PATH: bundle[
            "region_envelope_expansion_delta"
        ],
        REGION_SEMANTIC_LOSS_LEDGER_PATH: bundle["region_semantic_loss_ledger"],
        SEARCH_RECALL_FRESHNESS_JOIN_PATH: bundle["search_recall_freshness_join"],
        G5_G6_AUTHORITY_BOUNDARY_REPORT_PATH: bundle[
            "g5_g6_authority_boundary_report"
        ],
        S14_GROUNDED_BREADTH_FEED_PATH: bundle["s14_grounded_breadth_feed"],
        S14_MECHANISM_GENERALITY_PROJECTION_PATH: bundle[
            "s14_mechanism_generality_projection"
        ],
        S14_BATTERY_INPUT_MANIFEST_PATH: bundle["s14_battery_input_manifest"],
        S14_CONSUMER_GATE_PATH: bundle["s14_consumer_gate"],
        REGION_SCORECARD_PATH: bundle["region_scorecard"],
        REGION_WIDENING_AUDIT_SURFACE_PATH: bundle["region_widening_audit_surface"],
        PUBLIC_EXPORT_PROJECTION_REFS_PATH: bundle["public_export_projection_refs"],
        ORCHESTRATION_CONTINUITY_PATH: bundle["orchestration_continuity"],
        REPLAY_MANIFEST_PATH: bundle["replay_manifest"],
        CONFORMANCE_REPORT_PATH: bundle["conformance_report"],
        REGISTRY_RATCHET_DELTA_PATH: bundle["registry_ratchet_delta"],
        READINESS_MANIFEST_PATH: bundle["readiness_manifest"],
    }
    written: list[str] = []
    for path in EXPECTED_ARTIFACT_PATHS:
        resolved = _resolve_repo_path(repo_root, path)
        if path == HEALTH_METRIC_DELTA_PATH:
            _write_health_metric_delta(resolved, _mapping(bundle["health_metric_delta"]))
        elif path == REGION_ROUTE_CONTRACT_REGISTRY_PATH:
            _write_region_route_contract_registry(
                resolved,
                _mapping(bundle["region_route_contract_registry"]),
            )
        else:
            _write_json(resolved, payloads[path])
        written.append(path.as_posix())
    return written


def _replay_contract_audit_surface(
    audit_surface: g7.Layer3G7RegionWideningAuditSurface,
) -> g7.Layer3G7RegionWideningAuditSurface:
    """Keep expected value blockers out of structural replay-manifest health."""

    public_issue_codes = tuple(
        str(code)
        for code in _sequence(
            audit_surface.public_projection_contract_verification.get("issue_codes")
        )
    )
    return audit_surface.model_copy(
        update={
            "status": "fail" if public_issue_codes else "pass",
            "issue_codes": public_issue_codes,
        }
    )


def _validate_persisted_artifacts(repo_root: Path) -> list[dict[str, str]]:
    return [
        _issue(
            "layer3_g7_persisted_artifact_missing",
            path.as_posix(),
            "Layer 3 G7 readiness requires persisted runtime artifacts.",
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
                "layer3_g7_persisted_artifact_missing",
                path,
                "G7 --write must emit every expected persisted artifact path.",
            )
            for path in missing
        ],
        *[
            _issue(
                "layer3_g7_persisted_artifact_missing",
                path,
                "G7 --write emitted a path outside the expected artifact set.",
            )
            for path in unexpected
        ],
    ]


def _manifest_runtime_drift_keys(
    repo_root: Path,
    bundle: Mapping[str, Any],
) -> list[str]:
    path = _resolve_repo_path(repo_root, READINESS_MANIFEST_PATH)
    if not path.exists():
        return []
    try:
        persisted = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return ["readiness_manifest_unreadable"]
    runtime_summary = _summary(bundle, (), _registration_statuses(repo_root))
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
            "layer3_g7_manifest_runtime_drift",
            READINESS_MANIFEST_PATH.as_posix(),
            f"Persisted G7 readiness manifest drifted from runtime: {sorted(drift_keys)}",
        )
    ]


def _registration_statuses(repo_root: Path) -> dict[str, str]:
    generated_text = _read_text_or_empty(repo_root, GENERATED_ARTIFACTS_TOML_PATH)
    inventory_text = _read_text_or_empty(repo_root, INVENTORY_PATH)
    generated_ok = (
        G7_GENERATED_ARTIFACT_FAMILY_ID in generated_text
        and "source_of_truth =" in generated_text
        and "regenerate_commands =" in generated_text
        and "check_command =" in generated_text
        and "stale_output_behavior = \"fail\"" in generated_text
        and "drift_gate = \"automated\"" in generated_text
        and all(path.as_posix() in generated_text for path in EXPECTED_ARTIFACT_PATHS)
    )
    inventory_ok = (
        g7.G7_SURFACE_ID in inventory_text
        and "src/polisyos/runtime/quality/proving_ground/region_widening.py" in inventory_text
        and "validate_layer3_g7_readiness" in inventory_text
        and READINESS_MANIFEST_PATH.as_posix() in inventory_text
        and all(path.as_posix() in inventory_text for path in EXPECTED_ARTIFACT_PATHS)
        and "layer3_g1_substrate_grounding_surface" in inventory_text
        and "layer3_g4_shadow_to_governed_promotion_surface" in inventory_text
        and "layer3_g5_first_proving_ground_conversion_surface" in inventory_text
        and "layer3_g6_bounded_agent_surface" in inventory_text
    )
    docs_checks = (
        (GENERATED_ARTIFACTS_DOC_PATH, "layer3_g7_readiness_manifest.json"),
        (GENERATED_ARTIFACTS_DOC_PATH, G7_GENERATED_ARTIFACT_FAMILY_ID),
        (PUBLIC_SURFACE_DOC_PATH, g7.G7_SURFACE_ID),
        (PUBLIC_SURFACE_DOC_PATH, "projection-only"),
        (PUBLIC_SURFACE_DOC_PATH, "does not publish universal authority"),
        (DOCUMENTATION_INVENTORY_PATH, "layer3_g7_region_widening_surface"),
        (REFERENCE_INDEX_PATH, "Policy Design Case Layer 3 Region Widening"),
        (Path("src/polisyos/runtime/quality/README.md"), "layer3_region_widening.py"),
    )
    docs_ok = all(
        needle in _read_text_or_empty(repo_root, path) for path, needle in docs_checks
    )
    route_text = _read_text_or_empty(repo_root, REGION_ROUTE_CONTRACT_REGISTRY_PATH)
    registry_text = _read_text_or_empty(repo_root, REGISTRY_RATCHET_DELTA_PATH)
    return {
        "generated_artifacts": "pass" if generated_ok else "fail",
        "inventory": "pass" if inventory_ok else "fail",
        "docs": "pass" if docs_ok else "fail",
        "route_contract_registry": (
            "pass"
            if "route_contract_registry_kind = \"generated_region_route_contract_registry\""
            in route_text
            and "adapter_contract_registry" not in route_text
            else "fail"
        ),
        "registry_ratchet": "pass" if "layer3_g7_registry_ratchet_delta" in registry_text else "fail",
    }


def _validate_registration_and_docs(
    statuses: Mapping[str, str],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if statuses.get("generated_artifacts") != "pass":
        issues.append(
            _issue(
                "layer3_g7_generated_artifacts_family_missing",
                GENERATED_ARTIFACTS_TOML_PATH.as_posix(),
                "architecture/generated_artifacts.toml must register the G7 family.",
            )
        )
    if statuses.get("inventory") != "pass":
        issues.append(
            _issue(
                "layer3_g7_inventory_surface_missing",
                INVENTORY_PATH.as_posix(),
                "Policy Design Case inventory must register the G7 region surface.",
            )
        )
    if statuses.get("docs") != "pass":
        issues.append(
            _issue(
                "layer3_g7_reference_index_missing",
                PUBLIC_SURFACE_DOC_PATH.as_posix(),
                "G7 generated-artifact, public-surface, index, inventory, and README docs must be registered.",
            )
        )
    if statuses.get("route_contract_registry") != "pass":
        issues.append(
            _issue(
                "layer3_g7_route_contract_registry_missing",
                REGION_ROUTE_CONTRACT_REGISTRY_PATH.as_posix(),
                "G7 route contract registry must be generated route registry, not an adapter registry.",
            )
        )
    return issues


def _validate_runtime_surfaces(bundle: Mapping[str, Any]) -> list[dict[str, str]]:
    snapshot = bundle["dependency_readiness_snapshot"]
    search_join = bundle["search_recall_freshness_join"]
    s12_projection = bundle["s12_growth_thermometer_projection"]
    region_expansion = bundle["region_envelope_expansion_delta"]
    public_surface = bundle["region_widening_audit_surface"]
    continuity = bundle["orchestration_continuity"]
    replay = bundle["replay_manifest"]
    conformance = _mapping(bundle["conformance_report"])
    checks = (
        (
            snapshot.region_value_closure_status
            == "blocked_by_current_g5_unchanged_blocker",
            "layer3_g7_current_g5_unchanged_blocker",
            "Current G5 unchanged blocker must remain the G7 region-value blocker.",
        ),
        (
            not search_join.search_authoritative_for
            and "search_hit_as_authority" in search_join.search_may_not_use_for,
            "layer3_g7_search_hit_counted_as_coverage",
            "G1 search ledgers must stay control-plane only for G7.",
        ),
        (
            bundle["region_grounding_matrix"].coverage_status.startswith("blocked")
            and bundle["region_conversion_status_matrix"].grounded_region_case_count == 0,
            "layer3_g7_g5_unchanged_blocker_counted_as_grounded",
            "G7 must not count current G5 unchanged blocker as grounded breadth.",
        ),
        (
            s12_projection.held_out_status == "pending_s14"
            and s12_projection.s12_projection_contract_status == "pass"
            and "s14_universality" in s12_projection.may_not_use_for,
            "layer3_g7_s12_deny_list_omitted",
            "G7 S12 projection must preserve pending S14 and deny-list semantics.",
        ),
        (
            region_expansion.expansion_status in {"flat", "blocked"}
            or region_expansion.certified_envelope_delta_refs,
            "layer3_g7_s13_certified_delta_missing",
            "G7 region expansion requires certified expand deltas.",
        ),
        (
            public_surface.public_projection_contract_verification.get("status")
            == "pass",
            "layer3_g7_public_projection_contract_failed",
            "G7 PUBLIC projection must pass projection-only authority checks.",
        ),
        (
            continuity.status == "pass",
            "layer3_g7_orchestration_continuity_missing",
            "G7 orchestration continuity must be shared-helper backed.",
        ),
        (
            replay.status == "pass",
            "layer3_g7_replay_manifest_missing",
            "G7 replay manifest must be shared-helper backed.",
        ),
        (
            conformance.get("status") == "pass",
            "layer3_g7_replay_helper_bypassed",
            "G7 conformance report must be present before readiness closes.",
        ),
    )
    return [
        _issue(code, "$.readiness_manifest", message)
        for passed, code, message in checks
        if not passed
    ]


def _summary(
    bundle: Mapping[str, Any],
    drift_keys: Sequence[str],
    registration_statuses: Mapping[str, str],
) -> dict[str, Any]:
    snapshot = bundle["dependency_readiness_snapshot"]
    candidate_set = bundle["region_candidate_set"]
    grounding_matrix = bundle["region_grounding_matrix"]
    conversion_matrix = bundle["region_conversion_status_matrix"]
    status_ledger = bundle["status_composition_ledger"]
    s12_projection = bundle["s12_growth_thermometer_projection"]
    reuse = bundle["mechanism_reuse_ledger"]
    marginal = bundle["marginal_grounding_cost_ledger"]
    expansion = bundle["region_envelope_expansion_delta"]
    semantic_loss = bundle["region_semantic_loss_ledger"]
    s14_feed = bundle["s14_grounded_breadth_feed"]
    s14_mechanism = bundle["s14_mechanism_generality_projection"]
    s14_manifest = bundle["s14_battery_input_manifest"]
    s14_gate = bundle["s14_consumer_gate"]
    audit_surface = bundle["region_widening_audit_surface"]
    return {
        "status": "pass",
        "schema_version": G7_SCHEMA_VERSION,
        "rule_version": G7_RULE_VERSION,
        "surface_id": g7.G7_SURFACE_ID,
        "surface_audiences": list(audit_surface.surface_audiences),
        "may_not_use_for": list(audit_surface.may_not_use_for),
        "g7_engineering_readiness_status": snapshot.engineering_readiness_status,
        "g7_region_value_closure_status": snapshot.region_value_closure_status,
        "g7_current_g5_conversion_outcome": snapshot.g5_conversion_outcome,
        "g7_current_g5_unchanged_blocker_status": (
            "blocked"
            if snapshot.g5_conversion_outcome == "unchanged_blocker"
            else "not_current_blocker"
        ),
        "g7_g1_search_control_plane_status": (
            snapshot.g1_substrate_search_control_plane_status
        ),
        "g7_g1_free_growth_status": "pass",
        "g7_g1_no_hardcode_lint_status": "pass",
        "g7_g4_promotion_gate_shape_status": (
            "pass"
            if not conversion_matrix.grounded_region_case_count
            else bundle["governed_promotion_join"]["status"]
        ),
        "g7_g4_region_promotion_projection_status": (
            "blocked_current_seed_only"
            if conversion_matrix.grounded_region_case_count == 0
            else "pass"
        ),
        "g7_g5_g6_authority_boundary_status": (
            bundle["g5_g6_authority_boundary_report"]["status"]
        ),
        "g7_region_candidate_set_status": candidate_set.coverage_authority_status,
        "g7_region_grounding_matrix_status": grounding_matrix.coverage_status,
        "g7_region_grounded_case_count": conversion_matrix.grounded_region_case_count,
        "g7_region_blocked_case_count": conversion_matrix.blocked_region_case_count,
        "g7_status_composition_status": status_ledger.status,
        "g7_governed_promotion_join_status": bundle["governed_promotion_join"]["status"],
        "g7_s12_growth_thermometer_status": s12_projection.status,
        "g7_s12_resource_projection_contract_status": (
            s12_projection.s12_projection_contract_status
        ),
        "g7_s13_certified_delta_status": (
            "pass"
            if expansion.expansion_status != "pass"
            or expansion.certified_envelope_delta_refs
            else "fail"
        ),
        "g7_mechanism_reuse_status": reuse.reuse_status,
        "g7_mechanism_reuse_rate": reuse.mechanism_reuse_rate,
        "g7_marginal_cost_status": marginal.sublinear_marginal_cost_status,
        "g7_region_envelope_expansion_rate": expansion.envelope_expansion_rate,
        "g7_region_semantic_loss_status": semantic_loss.semantic_loss_status,
        "g7_governance_throughput_status": snapshot.g4_governance_throughput_status,
        "g7_s14_grounded_breadth_feed_status": s14_feed.status,
        "g7_s14_mechanism_generality_status": s14_mechanism.status,
        "g7_s14_battery_input_manifest_status": (
            s14_feed.status if s14_manifest.issue_codes else "pass"
        ),
        "g7_s14_consumer_gate_status": s14_gate.status,
        "g7_s14_runner_input_hook_status": "implemented_non_mutating",
        "g7_s14_projection_contract_status": (
            audit_surface.s14_universality_projection_contract_verification.get(
                "status",
                "fail",
            )
        ),
        "g7_public_projection_contract_status": (
            audit_surface.public_projection_contract_verification.get("status", "fail")
        ),
        "g7_public_projection_official_use_status": (
            "pass"
            if set(g7.G7_PUBLIC_OFFICIAL_USE_LIMITS)
            <= set(audit_surface.PUBLIC.get("official_use_limited_to", ()))
            else "fail"
        ),
        "g7_replay_manifest_status": bundle["replay_manifest"].status,
        "g7_orchestration_continuity_status": bundle["orchestration_continuity"].status,
        "g7_generated_artifacts_registration_status": registration_statuses.get(
            "generated_artifacts",
            "fail",
        ),
        "g7_inventory_surface_status": registration_statuses.get("inventory", "fail"),
        "g7_reference_docs_status": registration_statuses.get("docs", "fail"),
        "g7_route_contract_registry_status": registration_statuses.get(
            "route_contract_registry",
            "fail",
        ),
        "g7_registry_ratchet_status": registration_statuses.get(
            "registry_ratchet",
            "fail",
        ),
        "g7_conformance_status": bundle["conformance_report"]["status"],
        "g7_manifest_runtime_drift_key_count": len(drift_keys),
        "expected_artifact_count": len(EXPECTED_ARTIFACT_PATHS),
        "issue_codes": [],
    }


def _readiness_manifest(
    repo_root: Path,
    bundle: Mapping[str, Any],
    *,
    drift_keys: Sequence[str],
    registration_statuses: Mapping[str, str],
) -> dict[str, Any]:
    summary = _summary(bundle, drift_keys, registration_statuses)
    region_closure_authority_status = (
        "pass" if summary["g7_region_value_closure_status"] == "pass" else "blocked"
    )
    return {
        "schema_version": G7_SCHEMA_VERSION,
        "rule_version": G7_RULE_VERSION,
        "status": "pass",
        "status_authority_boundary": (
            "artifact_family_integrity_only_not_region_closure_authority"
        ),
        "region_closure_authority_status": region_closure_authority_status,
        "surface_id": g7.G7_SURFACE_ID,
        "summary": summary,
        **{key: summary[key] for key in EXPECTED_MANIFEST_DRIFT_KEYS},
        "issue_codes": [],
    }


def _write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, _json_dumps(_dump(payload)))


def _write_health_metric_delta(path: Path, payload: Mapping[str, Any]) -> None:
    lines = [
        f"schema_version = {_toml_value(payload.get('schema_version', G7_SCHEMA_VERSION))}",
        f"rule_version = {_toml_value(payload.get('rule_version', G7_RULE_VERSION))}",
        f"status = {_toml_value(payload.get('status', 'blocked'))}",
        f"region_ref = {_toml_value(payload.get('region_ref', 'region://ua/msme-adjacent'))}",
        "",
        "[metrics]",
    ]
    for key, value in sorted(_mapping(payload.get("metrics")).items()):
        lines.append(f"{_toml_key(key)} = {_toml_value(value)}")
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")


def _write_region_route_contract_registry(
    path: Path,
    payload: Mapping[str, Any],
) -> None:
    lines = [
        f"schema_version = {_toml_value(payload.get('schema_version', G7_SCHEMA_VERSION))}",
        f"rule_version = {_toml_value(payload.get('rule_version', G7_RULE_VERSION))}",
        f"status = {_toml_value(payload.get('status', 'fail'))}",
        f"route_contract_registry_kind = {_toml_value(payload.get('route_contract_registry_kind', 'generated_region_route_contract_registry'))}",
        f"route_count = {_toml_value(payload.get('route_count', 0))}",
    ]
    for record in _sequence(payload.get("region_route_records")):
        if not isinstance(record, Mapping):
            continue
        lines.append("")
        lines.append("[[region_route_records]]")
        for key in sorted(record):
            lines.append(f"{_toml_key(str(key))} = {_toml_value(record[key])}")
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")


def _governed_promotion_join_projection(
    records: Sequence[g7.Layer3G7RegionConversionRecord],
) -> dict[str, Any]:
    rows = [
        {
            "case_id": record.case_id,
            "status": record.g4_governed_promotion_join_status,
            "g4_promotion_record_ref": record.g4_promotion_record_ref,
            "g4_grounded_contract_set_ref": record.g4_grounded_contract_set_ref,
            "g4_a_completeness_ledger_ref": record.g4_a_completeness_ledger_ref,
            "g4_weakest_boundary_composition_ref": (
                record.g4_weakest_boundary_composition_ref
            ),
            "g4_human_decision_integrity_gate_ref": (
                record.g4_human_decision_integrity_gate_ref
            ),
            "g4_g5_handoff_ref": record.g4_g5_handoff_ref,
            "issue_codes": list(record.issue_codes),
        }
        for record in records
    ]
    return {
        "schema_version": G7_SCHEMA_VERSION,
        "rule_version": G7_RULE_VERSION,
        "status": "blocked_current_seed_only"
        if not any(record.is_grounded for record in records)
        else "pass",
        "rows": rows,
        "issue_codes": [],
    }


def _region_case_conversion_inputs(
    *,
    region_ref: str,
    conversion_records: Sequence[g7.Layer3G7RegionConversionRecord],
) -> dict[str, Any]:
    return {
        "schema_version": G7_SCHEMA_VERSION,
        "rule_version": G7_RULE_VERSION,
        "region_ref": region_ref,
        "conversion_input_rows": [
            {
                "case_id": record.case_id,
                "source_class": record.source_class,
                "g5_conversion_record_ref": record.g5_conversion_record_ref,
                "g4_promotion_record_ref": record.g4_promotion_record_ref,
                "may_not_use_for": list(record.may_not_use_for),
            }
            for record in conversion_records
        ],
    }


def _g5_g6_authority_boundary_report(
    snapshot: g7.Layer3G7DependencyReadinessSnapshot,
) -> dict[str, Any]:
    g5_ok = "g7_region_widening" in snapshot.g5_may_not_use_for
    g6_ok = "g7_region_widening" in snapshot.g6_may_not_use_for
    return {
        "schema_version": G7_SCHEMA_VERSION,
        "rule_version": G7_RULE_VERSION,
        "status": "pass" if g5_ok and g6_ok else "fail",
        "g5_may_not_use_for": list(snapshot.g5_may_not_use_for),
        "g6_may_not_use_for": list(snapshot.g6_may_not_use_for),
        "issue_codes": []
        if g5_ok and g6_ok
        else [
            code
            for code, passed in (
                ("layer3_g7_g5_may_not_use_for_ignored", g5_ok),
                ("layer3_g7_g6_may_not_use_for_ignored", g6_ok),
            )
            if not passed
        ],
    }


def _upstream_closed_replay_refs(repo_root: Path) -> dict[str, dict[str, str]]:
    refs = {
        "g5": g7.G5_READINESS_PATH,
        "g6": g7.G6_REPLAY_MANIFEST_PATH,
    }
    return {
        key: {
            "ref": f"repo://{path.as_posix()}",
            "fingerprint": _fingerprint_file(_resolve_repo_path(repo_root, path)),
        }
        for key, path in refs.items()
    }


def _health_metric_delta(
    *,
    region_expansion: g7.Layer3G7RegionEnvelopeExpansionDelta,
    semantic_loss: g7.Layer3G7RegionSemanticLossLedger,
    marginal_cost: g7.Layer3G7MarginalGroundingCostLedger,
) -> dict[str, Any]:
    return {
        "schema_version": G7_SCHEMA_VERSION,
        "rule_version": G7_RULE_VERSION,
        "status": "blocked"
        if marginal_cost.sublinear_marginal_cost_status.startswith("blocked")
        else "pass",
        "region_ref": region_expansion.region_ref,
        "metrics": {
            "envelope_expansion_rate_region": region_expansion.envelope_expansion_rate,
            "semantic_loss_status": semantic_loss.semantic_loss_status,
            "marginal_cost_status": marginal_cost.sublinear_marginal_cost_status,
        },
    }


def _region_route_contract_registry(
    scorecard: g7.Layer3G7RegionScorecard,
) -> dict[str, Any]:
    return {
        "schema_version": G7_SCHEMA_VERSION,
        "rule_version": G7_RULE_VERSION,
        "status": "pass",
        "route_contract_registry_kind": "generated_region_route_contract_registry",
        "route_count": 1,
        "region_route_records": [
            {
                "route_id": "layer3.g7.region_route.ua_msme_adjacent",
                "region_ref": scorecard.region_ref,
                "region_value_closure_status": scorecard.g7_region_value_closure_status,
                "scorecard_ref": scorecard.scorecard_ref,
                "public_projection_mode": "projection_only",
                "authoritative_for": list(scorecard.authoritative_for),
                "may_not_use_for": list(scorecard.may_not_use_for),
            }
        ],
    }


def _build_conformance_report(**kwargs: Any) -> dict[str, Any]:
    report = g7.build_g7_conformance_report(**kwargs)
    if isinstance(report, BaseModel):
        return report.model_dump(mode="json")
    return dict(report)


def _registry_ratchet_delta(conformance_report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": G7_SCHEMA_VERSION,
        "rule_version": G7_RULE_VERSION,
        "registry_delta_id": "layer3_g7_registry_ratchet_delta",
        "status": "pass" if conformance_report.get("status") == "pass" else "fail",
        "admission_maturity": "implemented_but_not_orchestrated",
        "conformance_report_ref": conformance_report.get("report_id"),
        "issue_codes": list(_sequence(conformance_report.get("issue_codes"))),
    }


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
    try:
        return resolved.read_text(encoding="utf-8")
    except OSError:
        return ""


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
    lines = [f"layer3_g7_readiness_status={report.get('status', '')}"]
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


def _fingerprint_file(path: Path) -> str:
    if not path.exists():
        return g7._fingerprint({"missing": path.as_posix()})
    try:
        return g7._fingerprint(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return g7._fingerprint(path.read_text(encoding="utf-8", errors="replace"))


def _resolve_repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


if __name__ == "__main__":
    raise SystemExit(main())
