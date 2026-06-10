#!/usr/bin/env python3
"""Validate and optionally persist the Layer 3 G3 analytics-search bundle."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from polisyos.runtime.quality import layer3_analytics_search as g3
from tools.lib.fs import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")
DOCS_REFERENCE_DIR = Path("docs/reference")

ADAPTER_ADMISSION_REGISTRY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_adapter_admission_registry.json"
)
L2_SKG_PROOF_CANDIDATE_BINDINGS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_l2_skg_proof_candidate_bindings.json"
)
IR_ANALYTICS_SEARCH_LEDGERS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_ir_analytics_search_ledgers.json"
)
IR_ANALYTICS_QUERY_TRACES_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_ir_analytics_query_traces.json"
)
IR_CATALOG_COVERAGE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g3_ir_catalog_coverage.json"
IR_ARTIFACT_STORE_INDEX_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_ir_artifact_store_index.json"
)
CERTIFICATE_RESOLUTION_REPORT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_certificate_resolution_report.json"
)
SEARCH_RECALL_FRESHNESS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_search_recall_freshness.json"
)
METHOD_REQUIREMENT_BINDINGS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_method_requirement_bindings.json"
)
SEMANTIC_SPINE_BINDINGS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_semantic_spine_bindings.json"
)
PROOF_CARRYING_ANALYTICS_RECORDS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_proof_carrying_analytics_records.json"
)
IR_ANALYTICS_CLAIM_BRIDGE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_ir_analytics_claim_bridge.json"
)
S11_PREREQUISITE_BINDINGS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_s11_prerequisite_bindings.json"
)
S11_CALIBRATION_BINDINGS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_s11_calibration_bindings.json"
)
S11_PREDICTIVE_POSTURE_BINDINGS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_s11_predictive_posture_bindings.json"
)
CLAIM_REGISTRY_CONSUMER_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_claim_registry_consumer_gate.json"
)
BASELINE_COMPARISON_CONSUMER_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_baseline_comparison_consumer_gate.json"
)
W12D_CONSUMER_GATE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g3_w12d_consumer_gate.json"
PUBLIC_EXPORT_PROJECTION_REFS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_public_export_projection_refs.json"
)
PROOF_CARRYING_AUDIT_SURFACE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_proof_carrying_audit_surface.json"
)
CONFORMANCE_REPORT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g3_conformance_report.json"
HEALTH_METRIC_DELTA_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g3_health_metric_delta.toml"
ADAPTER_CONTRACT_REGISTRY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_adapter_contract_registry.toml"
)
READINESS_MANIFEST_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g3_readiness_manifest.json"

GENERATED_ARTIFACTS_TOML_PATH = Path("architecture/generated_artifacts.toml")
GENERATED_ARTIFACTS_DOC_PATH = DOCS_REFERENCE_DIR / "generated-artifacts.md"
INVENTORY_PATH = POLICY_DESIGN_CASE_DIR / "inventory.json"
DOCS_SURFACE_PATH = DOCS_REFERENCE_DIR / "policy-design-case-layer3-analytics-search.md"
DOCUMENTATION_INVENTORY_PATH = DOCS_REFERENCE_DIR / "documentation-inventory.md"
REFERENCE_INDEX_PATH = DOCS_REFERENCE_DIR / "index.md"

JSON_ARTIFACT_PATHS: tuple[Path, ...] = (
    ADAPTER_ADMISSION_REGISTRY_PATH,
    L2_SKG_PROOF_CANDIDATE_BINDINGS_PATH,
    IR_ANALYTICS_SEARCH_LEDGERS_PATH,
    IR_ANALYTICS_QUERY_TRACES_PATH,
    IR_CATALOG_COVERAGE_PATH,
    IR_ARTIFACT_STORE_INDEX_PATH,
    CERTIFICATE_RESOLUTION_REPORT_PATH,
    SEARCH_RECALL_FRESHNESS_PATH,
    METHOD_REQUIREMENT_BINDINGS_PATH,
    SEMANTIC_SPINE_BINDINGS_PATH,
    PROOF_CARRYING_ANALYTICS_RECORDS_PATH,
    IR_ANALYTICS_CLAIM_BRIDGE_PATH,
    S11_PREREQUISITE_BINDINGS_PATH,
    S11_CALIBRATION_BINDINGS_PATH,
    S11_PREDICTIVE_POSTURE_BINDINGS_PATH,
    CLAIM_REGISTRY_CONSUMER_GATE_PATH,
    BASELINE_COMPARISON_CONSUMER_GATE_PATH,
    W12D_CONSUMER_GATE_PATH,
    PUBLIC_EXPORT_PROJECTION_REFS_PATH,
    PROOF_CARRYING_AUDIT_SURFACE_PATH,
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
    "g1_dependency_status",
    "g2_dependency_status",
    "g3_l2_skg_dependency_status",
    "g3_l2_skg_proof_candidate_binding_count",
    "g3_ir_catalog_coverage_status",
    "g3_ir_artifact_store_index_status",
    "g3_search_ledger_count",
    "g3_query_trace_count",
    "g3_certificate_resolution_status",
    "g3_resolved_certificate_count",
    "g3_search_recall_freshness_status",
    "g3_search_recall_seed_count",
    "g3_search_recall_recalled_seed_count",
    "g3_method_requirement_binding_count",
    "g3_proof_carrying_record_count",
    "g3_ir_analytics_bridge_status",
    "g3_s11_prerequisite_binding_status",
    "g3_s11_predictive_posture_binding_count",
    "g3_claim_registry_consumer_gate_status",
    "g3_baseline_comparison_consumer_gate_status",
    "g3_w12d_consumer_gate_status",
    "g3_public_export_projection_status",
    "g3_search_engineering_quality_status",
    "g3_conformance_status",
    "g3_adapter_contract_registry_status",
    "g3_adapter_contract_path_count",
    "g3_health_metric_ids",
)
ALL_ISSUE_CODES: tuple[str, ...] = tuple(dict.fromkeys(g3.ALL_ISSUE_CODES))


def validate_layer3_g3_readiness(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    """Build a Layer 3 G3 readiness report from runtime and registered surfaces."""

    root = Path(repo_root).resolve()
    runtime_bundle = g3.build_layer3_g3_bundle(root)
    if write:
        written_artifact_paths = _write_artifacts(root, runtime_bundle)
    else:
        written_artifact_paths = []

    runtime_report = g3.validate_layer3_g3_bundle(root, runtime_bundle).model_dump(
        mode="json"
    )
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
        "schema_version": g3.LAYER3_G3_SCHEMA_VERSION,
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
    """Run the Layer 3 G3 readiness check CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    report = validate_layer3_g3_readiness(args.repo_root, write=args.write)
    rendered = (
        _json_dumps(report) if args.output_format == "json" else _render_text_report(report)
    )
    if args.output is not None:
        output_path = _resolve_repo_path(Path(args.repo_root).resolve(), args.output)
        atomic_write_text(output_path, rendered)
    sys.stdout.write(rendered)
    return 0 if report["status"] == "pass" else 1


def _write_artifacts(repo_root: Path, bundle: g3.Layer3G3Bundle) -> list[str]:
    base = {
        "schema_version": g3.LAYER3_G3_SCHEMA_VERSION,
        "rule_version": g3.LAYER3_G3_RULE_VERSION,
    }
    payloads: dict[Path, Any] = {
        ADAPTER_ADMISSION_REGISTRY_PATH: {
            **base,
            "adapter_admission_registry": _dump(bundle.adapter_admission_registry),
        },
        L2_SKG_PROOF_CANDIDATE_BINDINGS_PATH: {
            **base,
            "l2_skg_proof_candidate_bindings": _dump(
                bundle.l2_skg_proof_candidate_bindings
            ),
        },
        IR_ANALYTICS_SEARCH_LEDGERS_PATH: {
            **base,
            "ir_analytics_search_ledgers": _dump(bundle.ir_analytics_search_ledgers),
        },
        IR_ANALYTICS_QUERY_TRACES_PATH: {
            **base,
            "ir_analytics_query_traces": _dump(bundle.ir_analytics_query_traces),
        },
        IR_CATALOG_COVERAGE_PATH: {
            **base,
            "ir_catalog_coverage": _dump(bundle.ir_catalog_coverage),
        },
        IR_ARTIFACT_STORE_INDEX_PATH: {
            **base,
            "ir_artifact_store_index": _dump(bundle.ir_artifact_store_index),
        },
        CERTIFICATE_RESOLUTION_REPORT_PATH: {
            **base,
            "certificate_resolution_report": _dump(bundle.certificate_resolution_report),
        },
        SEARCH_RECALL_FRESHNESS_PATH: {
            **base,
            "search_recall_freshness": _dump(bundle.search_recall_freshness),
        },
        METHOD_REQUIREMENT_BINDINGS_PATH: {
            **base,
            "method_requirement_bindings": _dump(bundle.method_requirement_bindings),
        },
        SEMANTIC_SPINE_BINDINGS_PATH: {
            **base,
            "semantic_spine_bindings": _dump(bundle.semantic_spine_bindings),
        },
        PROOF_CARRYING_ANALYTICS_RECORDS_PATH: {
            **base,
            "proof_carrying_analytics_records": _dump(
                bundle.proof_carrying_analytics_records
            ),
        },
        IR_ANALYTICS_CLAIM_BRIDGE_PATH: {
            **base,
            "ir_analytics_claim_bridge": _dump(bundle.ir_analytics_claim_bridge),
        },
        S11_PREREQUISITE_BINDINGS_PATH: {
            **base,
            "s11_prerequisite_bindings": _dump(bundle.s11_prerequisite_bindings),
        },
        S11_CALIBRATION_BINDINGS_PATH: {
            **base,
            "s11_calibration_bindings": _dump(bundle.s11_calibration_bindings),
        },
        S11_PREDICTIVE_POSTURE_BINDINGS_PATH: {
            **base,
            "s11_predictive_posture_bindings": _dump(
                bundle.s11_predictive_posture_bindings
            ),
        },
        CLAIM_REGISTRY_CONSUMER_GATE_PATH: {
            **base,
            "claim_registry_consumer_gate": _dump(bundle.claim_registry_consumer_gate),
        },
        BASELINE_COMPARISON_CONSUMER_GATE_PATH: {
            **base,
            "baseline_comparison_consumer_gate": _dump(
                bundle.baseline_comparison_consumer_gate
            ),
        },
        W12D_CONSUMER_GATE_PATH: {
            **base,
            "w12d_consumer_gate": _dump(bundle.w12d_consumer_gate),
        },
        PUBLIC_EXPORT_PROJECTION_REFS_PATH: {
            **base,
            "public_export_projection_refs": _dump(bundle.public_export_projection_refs),
        },
        PROOF_CARRYING_AUDIT_SURFACE_PATH: {
            **base,
            "proof_carrying_audit_surface": _dump(bundle.proof_carrying_audit_surface),
        },
        CONFORMANCE_REPORT_PATH: {
            **base,
            "conformance_report": _dump(bundle.conformance_report),
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
    _write_adapter_contract_registry(_resolve_repo_path(repo_root, ADAPTER_CONTRACT_REGISTRY_PATH))
    written.append(ADAPTER_CONTRACT_REGISTRY_PATH.as_posix())
    return written


def _validate_persisted_artifacts(repo_root: Path) -> list[dict[str, str]]:
    return [
        _issue(
            "layer3_g3_persisted_artifact_missing",
            path.as_posix(),
            "Layer 3 G3 readiness requires persisted runtime artifacts.",
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
                "layer3_g3_persisted_artifact_missing",
                path,
                "G3 --write must emit every expected persisted artifact path.",
            )
            for path in missing
        ],
        *[
            _issue(
                "layer3_g3_persisted_artifact_missing",
                path,
                "G3 --write emitted a path outside the expected artifact set.",
            )
            for path in unexpected
        ],
    ]


def _manifest_runtime_drift_keys(
    repo_root: Path,
    runtime_bundle: g3.Layer3G3Bundle,
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
            "layer3_g3_manifest_runtime_drift",
            READINESS_MANIFEST_PATH.as_posix(),
            f"Persisted G3 readiness manifest drifted from runtime: {sorted(drift_keys)}",
        )
    ]


def _validate_registration_and_docs(repo_root: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    generated_text = _read_text_or_empty(repo_root, GENERATED_ARTIFACTS_TOML_PATH)
    if (
        g3.LAYER3_G3_GENERATED_ARTIFACT_FAMILY_ID not in generated_text
        or not all(path.as_posix() in generated_text for path in EXPECTED_ARTIFACT_PATHS)
    ):
        issues.append(
            _issue(
                "layer3_g3_persisted_artifact_missing",
                GENERATED_ARTIFACTS_TOML_PATH.as_posix(),
                "architecture/generated_artifacts.toml must register the G3 family.",
            )
        )
    inventory_text = _read_text_or_empty(repo_root, INVENTORY_PATH)
    if g3.LAYER3_G3_SURFACE_ID not in inventory_text:
        issues.append(
            _issue(
                "layer3_g3_public_raw_proof_leak",
                INVENTORY_PATH.as_posix(),
                "Policy Design Case inventory must register the G3 audit surface.",
            )
        )
    docs_checks = (
        (GENERATED_ARTIFACTS_DOC_PATH, "layer3_g3_readiness_manifest.json"),
        (DOCS_SURFACE_PATH, "layer3_g3_proof_carrying_audit_surface"),
        (DOCS_SURFACE_PATH, "PUBLIC/REVIEWER"),
        (DOCUMENTATION_INVENTORY_PATH, "policy-design-case-layer3-analytics-search.md"),
        (REFERENCE_INDEX_PATH, "policy-design-case-layer3-analytics-search.md"),
    )
    for path, needle in docs_checks:
        if needle not in _read_text_or_empty(repo_root, path):
            issues.append(
                _issue(
                    "layer3_g3_persisted_artifact_missing",
                    path.as_posix(),
                    f"G3 documentation/reference surface is missing marker: {needle}",
                )
            )
    return issues


def _validate_runtime_surfaces(bundle: g3.Layer3G3Bundle) -> list[dict[str, str]]:
    checks = (
        (
            bundle.search_recall_freshness.status == "pass"
            and bundle.search_recall_freshness.freshness_status == "pass"
            and bundle.search_recall_freshness.recalled_seed_count
            == bundle.search_recall_freshness.known_seed_count
            and bundle.search_recall_freshness.known_seed_count >= 3,
            "layer3_g3_search_recall_seed_miss_blocks_domain_ceiling",
            "G3 search recall/freshness must replay known seeds before ceiling claims.",
        ),
        (
            bundle.public_export_projection_refs.status == "pass"
            and not bundle.public_export_projection_refs.raw_proof_payload_exported
            and not bundle.public_export_projection_refs.raw_cas_manifest_exported
            and not bundle.public_export_projection_refs.raw_query_ledger_exported,
            "layer3_g3_public_raw_proof_leak",
            "G3 public export surface must expose projection refs without raw payloads.",
        ),
        (
            bundle.proof_carrying_audit_surface.status == "pass",
            "layer3_g3_public_raw_proof_leak",
            "G3 proof-carrying audit surface must pass.",
        ),
        (
            bundle.adapter_contract_registry.status == "pass",
            "layer3_g3_adapter_contract_registry_missing",
            "G3 adapter contract registry must load with existing adapter loader.",
        ),
        (
            set(bundle.health_metric_delta.get("metric_ids", ()))
            >= set(g3.EXPECTED_HEALTH_METRICS),
            "layer3_g3_persisted_artifact_missing",
            "G3 health metric delta must include all expected metric ids.",
        ),
    )
    return [_issue(code, "$.readiness_manifest", message) for passed, code, message in checks if not passed]


def _summary(
    repo_root: Path,
    bundle: g3.Layer3G3Bundle,
    runtime_report: Mapping[str, Any],
    drift_keys: Sequence[str],
) -> dict[str, Any]:
    summary = dict(bundle.readiness_manifest.model_dump(mode="json"))
    summary.update(_mapping(runtime_report.get("summary")))
    summary.update(
        {
            "schema_version": g3.LAYER3_G3_SCHEMA_VERSION,
            "rule_version": g3.LAYER3_G3_RULE_VERSION,
            "surface_id": bundle.proof_carrying_audit_surface.surface_id,
            "surface_audiences": list(bundle.proof_carrying_audit_surface.surface_audiences),
            "may_not_use_for": list(bundle.proof_carrying_audit_surface.may_not_use_for),
            "g3_conformance_status": bundle.conformance_report.status,
            "g3_conformance_issue_count": len(bundle.conformance_report.issue_codes),
            "g3_manifest_runtime_drift_key_count": len(drift_keys),
            "expected_artifact_count": len(EXPECTED_ARTIFACT_PATHS),
            "persisted_g3_artifact_count": sum(
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
        f"schema_version = {_toml_value(payload.get('schema_version', g3.LAYER3_G3_SCHEMA_VERSION))}",
        f"rule_version = {_toml_value(payload.get('rule_version', g3.LAYER3_G3_RULE_VERSION))}",
        "",
        "[health_metric_delta]",
        f"metric_ids = {_toml_value(payload.get('metric_ids', []))}",
    ]
    readings = _mapping(payload.get("readings"))
    for key in sorted(readings):
        lines.append(f"readings.{_toml_key(key)} = {_toml_value(readings[key])}")
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")


def _write_adapter_contract_registry(path: Path) -> None:
    source = _resolve_repo_path(REPO_ROOT, ADAPTER_CONTRACT_REGISTRY_PATH)
    if source.exists():
        atomic_write_text(path, source.read_text(encoding="utf-8"))
        return
    raise FileNotFoundError(source)


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
    lines = [f"layer3_g3_readiness_status={report.get('status', '')}"]
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
