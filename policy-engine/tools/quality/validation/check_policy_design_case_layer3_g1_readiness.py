#!/usr/bin/env python3
"""Validate and optionally persist the Layer 3 G1 substrate grounding bundle."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from polisyos.runtime.quality import layer3_substrate_grounding as g1
from tools.lib.fs import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")
DOCS_REFERENCE_DIR = Path("docs/reference")

ADAPTER_ADMISSION_REGISTRY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_adapter_admission_registry.json"
)
SUBSTRATE_SEARCH_LEDGERS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_substrate_search_ledgers.json"
)
L1_L5_L6_INDEX_COVERAGE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_l1_l5_l6_index_coverage.json"
)
SEARCH_RECALL_FRESHNESS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_search_recall_freshness.json"
)
HARDCODE_STRANGLE_DELTA_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_hardcode_strangle_delta.json"
)
FREE_GROWTH_REPORT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g1_free_growth_report.json"
SEARCH_ENGINEERING_QUALITY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_search_engineering_quality_report.json"
)
GROUNDED_SOURCE_CONTRACTS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_grounded_source_contracts.json"
)
LINEAGE_CONTAMINATION_LEDGER_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_lineage_contamination_ledger.json"
)
CONFORMANCE_REPORT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g1_conformance_report.json"
COVERAGE_LINEAGE_ABSTENTION_SURFACE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_coverage_lineage_abstention_surface.json"
)
HEALTH_METRIC_DELTA_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g1_health_metric_delta.toml"
ADAPTER_CONTRACT_REGISTRY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_adapter_contract_registry.toml"
)
READINESS_MANIFEST_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g1_readiness_manifest.json"
DOCS_SURFACE_PATH = DOCS_REFERENCE_DIR / "policy-design-case-layer3-substrate-grounding.md"
INVENTORY_PATH = POLICY_DESIGN_CASE_DIR / "inventory.json"
GENERATED_ARTIFACTS_DOC_PATH = DOCS_REFERENCE_DIR / "generated-artifacts.md"
DOCUMENTATION_INVENTORY_PATH = DOCS_REFERENCE_DIR / "documentation-inventory.md"

G0_DEPENDENCY_PATHS: tuple[Path, ...] = (
    POLICY_DESIGN_CASE_DIR / "layer3_g0_readiness_manifest.json",
    POLICY_DESIGN_CASE_DIR / "layer3_discovery_search_discipline.json",
    POLICY_DESIGN_CASE_DIR / "layer3_hardcode_enumeration_backlog.json",
    POLICY_DESIGN_CASE_DIR / "layer3_engineering_quality_check.json",
    POLICY_DESIGN_CASE_DIR / "layer3_health_metric_ledgers.toml",
)
JSON_ARTIFACT_PATHS: tuple[Path, ...] = (
    ADAPTER_ADMISSION_REGISTRY_PATH,
    SUBSTRATE_SEARCH_LEDGERS_PATH,
    L1_L5_L6_INDEX_COVERAGE_PATH,
    SEARCH_RECALL_FRESHNESS_PATH,
    HARDCODE_STRANGLE_DELTA_PATH,
    FREE_GROWTH_REPORT_PATH,
    SEARCH_ENGINEERING_QUALITY_PATH,
    GROUNDED_SOURCE_CONTRACTS_PATH,
    LINEAGE_CONTAMINATION_LEDGER_PATH,
    CONFORMANCE_REPORT_PATH,
    COVERAGE_LINEAGE_ABSTENTION_SURFACE_PATH,
    READINESS_MANIFEST_PATH,
)
TOML_ARTIFACT_PATHS: tuple[Path, ...] = (HEALTH_METRIC_DELTA_PATH,)
EXPECTED_ARTIFACT_PATHS: tuple[Path, ...] = (
    *JSON_ARTIFACT_PATHS,
    *TOML_ARTIFACT_PATHS,
    ADAPTER_CONTRACT_REGISTRY_PATH,
)
HEALTH_METRIC_IDS = set(g1.EXPECTED_HEALTH_METRICS)
EXPECTED_MAY_NOT_USE_FOR = set(g1.G1_MAY_NOT_USE_FOR)

ALL_ISSUE_CODES: tuple[str, ...] = (
    "layer3_g1_g0_dependency_not_ready",
    "layer3_g1_persisted_artifact_missing",
    "layer3_g1_manifest_runtime_drift",
    "layer3_g1_surface_unsynced",
    "layer3_g1_claim_authority_leak",
    "layer3_g1_useful_design_credit_leak",
    "layer3_g1_search_ledger_missing",
    "layer3_g1_search_ledger_authority_boundary_leak",
    "layer3_g1_search_recall_not_measured",
    "layer3_g1_search_engineering_quality_not_measured",
    "layer3_g1_l1_dcat_no_metric_binding",
    "layer3_g1_source_contract_materialization_missing",
    "layer3_g1_hardcode_strangle_incomplete",
    "layer3_g1_search_recall_seed_miss_blocks_domain_ceiling",
    "layer3_g1_stale_index_blocks_domain_ceiling",
    "layer3_g1_hardcode_fallback_used_for_closure",
    "layer3_g1_hardcode_fallback_not_deleted",
    "layer3_g1_mechanism_generality_single_request",
    "layer3_g1_l1_l5_l6_index_coverage_missing",
    "layer3_g1_l1_l5_l6_bounded_surrogate_overclaimed",
    "layer3_g1_l1_dcat_not_queried",
    "layer3_g1_capability_index_used_as_l1_search",
    "layer3_g1_unjustified_l1_surrogate",
    "layer3_g1_search_engineering_quality_failed",
    "layer3_g1_raw_output_without_adapter",
    "layer3_g1_missing_rights",
    "layer3_g1_contaminated_lineage",
    "layer3_g1_local_path_lineage_ref",
    "layer3_g1_source_contract_validation_echo",
    "layer3_g1_coverage_overclaim",
    "layer3_g1_missing_source_contract",
    "layer3_g1_acquisition_gap_overclaimed",
    "layer3_g1_semantic_loss",
    "layer3_g1_construct_bundle_mismatch",
    "layer3_g1_no_hit_without_replayable_frontier",
    "layer3_g1_search_ceiling_not_domain_ceiling",
)


def validate_layer3_g1_readiness(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    """Build a Layer 3 G1 readiness report from runtime and registered surfaces."""

    root = Path(repo_root).resolve()
    runtime_bundle = g1.build_layer3_g1_bundle(root)
    if write:
        written_artifact_paths = _write_artifacts(root, runtime_bundle)
    else:
        written_artifact_paths = []

    issues: list[dict[str, str]] = []
    runtime_report = g1.validate_layer3_g1_bundle(root, runtime_bundle).model_dump(
        mode="json"
    )
    issues.extend(_normalize_issues(runtime_report.get("issues", [])))
    issues.extend(_validate_persisted_artifacts(root))
    issues.extend(_validate_g0_dependencies(root))
    issues.extend(_validate_manifest_runtime_drift(root, runtime_bundle))
    issues.extend(_validate_registration_and_docs(root))
    issues.extend(_validate_authority_posture(runtime_bundle))
    issues.extend(_validate_search_health(runtime_bundle))

    normalized_issues = _deduplicate_issues(issues)
    summary = _summary(root, runtime_bundle, runtime_report)
    return {
        "status": "fail" if normalized_issues else "pass",
        "issues": normalized_issues,
        "summary": summary,
        "artifacts": {
            "expected_artifact_paths": [path.as_posix() for path in EXPECTED_ARTIFACT_PATHS],
            "written_artifact_paths": written_artifact_paths,
            "missing_persisted_artifact_paths": [
                path.as_posix()
                for path in EXPECTED_ARTIFACT_PATHS
                if not (root / path).exists()
            ],
        },
        "write": write,
        "issue_code_dictionary": list(ALL_ISSUE_CODES),
    }


def _validate_persisted_artifacts(repo_root: Path) -> list[dict[str, str]]:
    return [
        _issue(
            "layer3_g1_persisted_artifact_missing",
            path.as_posix(),
            "Layer 3 G1 readiness requires persisted runtime artifacts.",
        )
        for path in EXPECTED_ARTIFACT_PATHS
        if not (repo_root / path).exists()
    ]


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Layer 3 G1 readiness check CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    report = validate_layer3_g1_readiness(args.repo_root, write=args.write)
    rendered = (
        _json_dumps(report) if args.output_format == "json" else _render_text_report(report)
    )
    if args.output is not None:
        output_path = _resolve_path(Path(args.repo_root), args.output)
        atomic_write_text(output_path, rendered)
    sys.stdout.write(rendered)
    return 0 if report["status"] == "pass" else 1


def _write_artifacts(repo_root: Path, bundle: g1.Layer3G1Bundle) -> list[str]:
    base = {
        "schema_version": g1.LAYER3_G1_SCHEMA_VERSION,
        "rule_version": g1.LAYER3_G1_RULE_VERSION,
    }
    payloads: dict[Path, Any] = {
        ADAPTER_ADMISSION_REGISTRY_PATH: {
            **base,
            "adapter_admission_registry": {"records": _dump(bundle.adapter_admission_registry)},
        },
        SUBSTRATE_SEARCH_LEDGERS_PATH: {
            **base,
            "search_ledgers": _dump(bundle.search_ledgers),
        },
        L1_L5_L6_INDEX_COVERAGE_PATH: {
            **base,
            "l1_l5_l6_index_coverage": _dump(bundle.l1_l5_l6_index_coverage),
        },
        SEARCH_RECALL_FRESHNESS_PATH: {
            **base,
            "search_recall_freshness": _dump(bundle.search_recall_freshness),
        },
        HARDCODE_STRANGLE_DELTA_PATH: {
            **base,
            "hardcode_strangle_delta": _dump(bundle.hardcode_strangle_delta),
        },
        FREE_GROWTH_REPORT_PATH: {
            **base,
            "free_growth_report": _dump(bundle.free_growth_report),
        },
        SEARCH_ENGINEERING_QUALITY_PATH: {
            **base,
            "search_engineering_quality": _dump(bundle.search_engineering_quality),
        },
        GROUNDED_SOURCE_CONTRACTS_PATH: {
            **base,
            "grounded_source_contracts": _dump(bundle.grounded_source_contracts),
        },
        LINEAGE_CONTAMINATION_LEDGER_PATH: {
            **base,
            "lineage_contamination_ledger": _dump(bundle.lineage_contamination_ledger),
        },
        CONFORMANCE_REPORT_PATH: {
            **base,
            "conformance_report": _dump(bundle.conformance_report),
        },
        COVERAGE_LINEAGE_ABSTENTION_SURFACE_PATH: {
            **base,
            "coverage_lineage_abstention_surface": _dump(
                bundle.coverage_lineage_abstention_surface
            ),
        },
        READINESS_MANIFEST_PATH: _dump(bundle.readiness_manifest),
    }
    written: list[str] = []
    for path, payload in payloads.items():
        _write_json(repo_root / path, payload)
        written.append(path.as_posix())
    _write_health_metric_delta(repo_root / HEALTH_METRIC_DELTA_PATH, bundle.health_metric_delta)
    written.append(HEALTH_METRIC_DELTA_PATH.as_posix())
    return written


def _validate_g0_dependencies(repo_root: Path) -> list[dict[str, str]]:
    missing = [path for path in G0_DEPENDENCY_PATHS if not (repo_root / path).exists()]
    issues = [
        _issue(
            "layer3_g1_g0_dependency_not_ready",
            path.as_posix(),
            "Layer 3 G1 requires ready G0 v2 dependency artifacts.",
        )
        for path in missing
    ]
    manifest_path = repo_root / POLICY_DESIGN_CASE_DIR / "layer3_g0_readiness_manifest.json"
    if not manifest_path.exists():
        return issues
    try:
        manifest = _read_json(manifest_path)
    except (OSError, json.JSONDecodeError) as error:
        issues.append(
            _issue(
                "layer3_g1_g0_dependency_not_ready",
                str(manifest_path.relative_to(repo_root)),
                f"G0 readiness manifest could not be loaded: {error}",
            )
        )
        return issues
    counts = _mapping(manifest.get("counts"))
    degraded = (
        manifest.get("schema_version") != g1.G0_SCHEMA_VERSION
        or manifest.get("rule_version") != g1.G0_RULE_VERSION
        or counts.get("g1_dependency_requirements_status") != "pass"
        or counts.get("search_recall_seed_status") != "pass"
        or counts.get("index_freshness_status") != "pass"
        or counts.get("no_hardcode_enumeration_lint_status") != "pass"
        or counts.get("engineering_quality_check_status") != "pass"
    )
    if degraded:
        issues.append(
            _issue(
                "layer3_g1_g0_dependency_not_ready",
                str(manifest_path.relative_to(repo_root)),
                "G0 readiness manifest is not v2/pass for G1 dependency use.",
            )
        )
    return issues


def _validate_manifest_runtime_drift(
    repo_root: Path,
    runtime_bundle: g1.Layer3G1Bundle,
) -> list[dict[str, str]]:
    path = repo_root / READINESS_MANIFEST_PATH
    if not path.exists():
        return []
    try:
        persisted = _read_json(path)
    except (OSError, json.JSONDecodeError) as error:
        return [
            _issue(
                "layer3_g1_manifest_runtime_drift",
                READINESS_MANIFEST_PATH.as_posix(),
                f"Persisted G1 readiness manifest could not be loaded: {error}",
            )
        ]
    runtime_counts = runtime_bundle.readiness_manifest.counts
    persisted_counts = _mapping(persisted.get("counts"))
    keys = (
        "g0_v2_dependency_status",
        "g1_l1_l5_l6_index_coverage_status",
        "g1_substrate_search_ledger_count",
        "g1_adapter_contract_path_count",
        "grounded_or_uncertain_construct_count",
        "source_contract_snapshot_count",
        "g1_search_engineering_quality_status",
    )
    drifted = [
        key for key in keys if persisted_counts.get(key) != runtime_counts.get(key)
    ]
    if (
        persisted.get("schema_version") != g1.LAYER3_G1_SCHEMA_VERSION
        or persisted.get("rule_version") != g1.LAYER3_G1_RULE_VERSION
    ):
        drifted.append("schema_or_rule_version")
    if not drifted:
        return []
    return [
        _issue(
            "layer3_g1_manifest_runtime_drift",
            READINESS_MANIFEST_PATH.as_posix(),
            f"Persisted G1 readiness manifest drifted from runtime: {sorted(drifted)}",
        )
    ]


def _validate_registration_and_docs(repo_root: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    inventory_path = repo_root / INVENTORY_PATH
    try:
        inventory = _read_json(inventory_path)
    except (OSError, json.JSONDecodeError) as error:
        return [
            _issue(
                "layer3_g1_surface_unsynced",
                INVENTORY_PATH.as_posix(),
                f"Policy Design Case inventory could not be loaded: {error}",
            )
        ]
    artifacts = inventory.get("artifacts", [])
    surface = next(
        (
            item
            for item in artifacts
            if isinstance(item, Mapping)
            and item.get("id") == "layer3_g1_substrate_grounding_audit_surface"
        ),
        None,
    )
    if not isinstance(surface, Mapping):
        issues.append(
            _issue(
                "layer3_g1_surface_unsynced",
                INVENTORY_PATH.as_posix(),
                "Inventory must register layer3_g1_substrate_grounding_audit_surface.",
            )
        )
    else:
        audiences = set(_sequence(surface.get("surface_audiences")))
        if audiences != {"EXPERT", "MACHINE"}:
            issues.append(
                _issue(
                    "layer3_g1_surface_unsynced",
                    "$.artifacts[layer3_g1_substrate_grounding_audit_surface]",
                    "G1 audit surface must be registered for EXPERT and MACHINE only.",
                )
            )
    for path, needle in (
        (DOCS_SURFACE_PATH, "layer3_g1_substrate_grounding_audit_surface"),
        (GENERATED_ARTIFACTS_DOC_PATH, "layer3_g1_substrate_search_ledgers.json"),
        (DOCUMENTATION_INVENTORY_PATH, "policy-design-case-layer3-substrate-grounding.md"),
    ):
        doc_path = repo_root / path
        if not doc_path.exists() or needle not in doc_path.read_text(encoding="utf-8"):
            issues.append(
                _issue(
                    "layer3_g1_surface_unsynced",
                    path.as_posix(),
                    f"G1 documentation/reference surface is missing required marker: {needle}",
                )
            )
    return issues


def _validate_authority_posture(bundle: g1.Layer3G1Bundle) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    counts = bundle.readiness_manifest.counts
    if int(counts.get("production_claim_authority_count") or 0) != 0:
        issues.append(
            _issue(
                "layer3_g1_claim_authority_leak",
                "$.readiness_manifest.counts.production_claim_authority_count",
                "G1 cannot produce claim authority.",
            )
        )
    if int(counts.get("useful_design_credit_count") or 0) != 0:
        issues.append(
            _issue(
                "layer3_g1_useful_design_credit_leak",
                "$.readiness_manifest.counts.useful_design_credit_count",
                "G1 cannot produce useful-design credit.",
            )
        )
    for index, ledger in enumerate(bundle.search_ledgers):
        if ledger.authoritative_for:
            issues.append(
                _issue(
                    "layer3_g1_search_ledger_authority_boundary_leak",
                    f"$.search_ledgers[{index}].authoritative_for",
                    "Search ledgers are replay frontiers only, never authority.",
                )
            )
        if not set(ledger.may_not_use_for) >= EXPECTED_MAY_NOT_USE_FOR:
            issues.append(
                _issue(
                    "layer3_g1_search_ledger_authority_boundary_leak",
                    f"$.search_ledgers[{index}].may_not_use_for",
                    "Search ledgers must carry the full G1 may-not-use boundary.",
                )
            )
    for index, binding in enumerate(_sequence(bundle.grounded_source_contracts.get("bindings"))):
        if not isinstance(binding, Mapping):
            continue
        if "claim_authority" in set(_sequence(binding.get("authoritative_for"))):
            issues.append(
                _issue(
                    "layer3_g1_claim_authority_leak",
                    f"$.grounded_source_contracts.bindings[{index}].authoritative_for",
                    "G1 bindings are audit evidence only, not claim authority.",
                )
            )
    return issues


def _validate_search_health(bundle: g1.Layer3G1Bundle) -> list[dict[str, str]]:
    counts = bundle.readiness_manifest.counts
    checks = (
        (
            counts.get("g1_l1_l5_l6_index_coverage_status") == "pass",
            "layer3_g1_l1_l5_l6_index_coverage_missing",
            "L1/L5/L6 index coverage must pass.",
        ),
        (
            int(counts.get("g1_substrate_search_ledger_count") or 0) >= 1,
            "layer3_g1_search_ledger_missing",
            "Every G1 selected/no-hit/abstention route needs a replayable ledger.",
        ),
        (
            counts.get("g1_search_recall_status") == "pass",
            "layer3_g1_search_recall_seed_miss_blocks_domain_ceiling",
            "Known-seed recall must pass before any domain ceiling.",
        ),
        (
            counts.get("g1_index_freshness_status") == "pass",
            "layer3_g1_stale_index_blocks_domain_ceiling",
            "Index freshness must pass before any domain ceiling.",
        ),
        (
            bool(bundle.free_growth_report.discovered_metric_ids)
            and int(counts.get("g1_free_growth_fixture_count") or 0) == 0,
            "layer3_g1_surface_unsynced",
            "G1 must prove free growth through the L1 route without fixture substitution.",
        ),
        (
            int(counts.get("g1_mechanism_generality_request_shape_count") or 0) >= 2,
            "layer3_g1_mechanism_generality_single_request",
            "G1 must prove two request shapes through the same mechanism.",
        ),
        (
            counts.get("g1_no_hardcode_enumeration_lint_status") == "pass",
            "layer3_g1_hardcode_fallback_used_for_closure",
            "No-hardcode lint must pass.",
        ),
        (
            counts.get("g1_hardcode_fallback_deletion_status")
            in {
                "deleted_or_disabled_no_fallback",
                "search_path_replaced_deletion_pending",
            },
            "layer3_g1_hardcode_strangle_incomplete",
            "Hardcoded fallback cleanup must be explicitly pending or complete.",
        ),
        (
            int(counts.get("g1_hardcode_fallback_closure_count") or 0) == 0,
            "layer3_g1_hardcode_fallback_used_for_closure",
            "Hardcoded fallback cannot close G1.",
        ),
        (
            counts.get("g1_search_engineering_quality_status") == "pass"
            and counts.get("g1_search_scaling_fixture_status") == "pass",
            "layer3_g1_search_engineering_quality_failed",
            "Search implementation must be indexed, bounded, deterministic, and scalable.",
        ),
        (
            set(counts.get("g1_health_metric_delta_ids") or []) >= HEALTH_METRIC_IDS,
            "layer3_g1_surface_unsynced",
            "All five G0 health metric deltas must be represented in G1.",
        ),
    )
    return [
        _issue(code, "$.readiness_manifest.counts", message)
        for passed, code, message in checks
        if not passed
    ]


def _summary(
    repo_root: Path,
    bundle: g1.Layer3G1Bundle,
    runtime_report: Mapping[str, Any],
) -> dict[str, Any]:
    counts = dict(bundle.readiness_manifest.counts)
    summary = {**counts, **_mapping(runtime_report.get("summary"))}
    summary.update(
        {
            "schema_version": g1.LAYER3_G1_SCHEMA_VERSION,
            "rule_version": g1.LAYER3_G1_RULE_VERSION,
            "surface_id": bundle.coverage_lineage_abstention_surface.surface_id,
            "surface_audiences": list(
                bundle.coverage_lineage_abstention_surface.surface_audiences
            ),
            "surface_out_of_scope_audiences": [
                str(item.get("audience"))
                for item in bundle.coverage_lineage_abstention_surface.surface_out_of_scope
            ],
            "expected_artifact_count": len(EXPECTED_ARTIFACT_PATHS),
            "persisted_g1_artifact_count": sum(
                1 for path in EXPECTED_ARTIFACT_PATHS if (repo_root / path).exists()
            ),
        }
    )
    return summary


def _write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, _json_dumps(payload))


def _write_health_metric_delta(path: Path, payload: Mapping[str, Any]) -> None:
    lines = [
        f"schema_version = {_toml_value(payload.get('schema_version', g1.LAYER3_G1_SCHEMA_VERSION))}",
        f"rule_version = {_toml_value(g1.LAYER3_G1_RULE_VERSION)}",
        "",
        "[health_metric_delta]",
        f"metric_ids = {_toml_value(payload.get('metric_ids', []))}",
    ]
    readings = _mapping(payload.get("readings"))
    for key in sorted(readings):
        lines.append(f"readings.{_toml_key(key)} = {_toml_value(readings[key])}")
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


def _mapping(value: object) -> Mapping[str, Any]:
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
    lines = [f"layer3_g1_readiness_status={report.get('status', '')}"]
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


def _resolve_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        sys.stderr.write(str(exc))
        raise
