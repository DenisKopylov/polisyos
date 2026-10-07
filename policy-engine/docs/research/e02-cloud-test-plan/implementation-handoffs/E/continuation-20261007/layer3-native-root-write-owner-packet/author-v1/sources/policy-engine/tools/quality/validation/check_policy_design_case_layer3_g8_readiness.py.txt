#!/usr/bin/env python3
"""Validate and optionally persist the Layer 3 G8 metric-governance bundle."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from polisyos.runtime.quality.proving_ground import health_metric_governance as g8
from tools.lib.fs import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")
DOCS_REFERENCE_DIR = Path("docs/reference")

G8_SCHEMA_VERSION: str = g8.G8_SCHEMA_VERSION
G8_RULE_VERSION: str = g8.G8_RULE_VERSION
G8_GENERATED_ARTIFACT_FAMILY_ID: str = g8.G8_GENERATED_ARTIFACT_FAMILY_ID

EXPECTED_ARTIFACT_PATHS: tuple[Path, ...] = g8.EXPECTED_ARTIFACT_PATHS
EXPECTED_MANIFEST_DRIFT_KEYS: tuple[str, ...] = g8.EXPECTED_MANIFEST_DRIFT_KEYS
ALL_ISSUE_CODES: tuple[str, ...] = tuple(dict.fromkeys(g8.ALL_ISSUE_CODES))

HEALTH_METRIC_REGISTRY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_health_metric_registry.json"
)
METRIC_SOURCE_SNAPSHOT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_metric_source_snapshot.json"
)
NORMALIZED_METRIC_SIGNALS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_normalized_metric_signals.json"
)
METRIC_TREND_REPORT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_metric_trend_report.json"
)
CROSS_METRIC_DIAGNOSIS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_cross_metric_diagnosis.json"
)
DOMAIN_VS_SEARCH_CEILING_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_domain_vs_search_ceiling_gate.json"
)
METRIC_GAMING_FIREWALL_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_metric_gaming_firewall.json"
)
WARNING_LIFECYCLE_LEDGER_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_warning_lifecycle_ledger.json"
)
D44_CORPUS_REBASING_RULE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_d44_corpus_rebasing_rule.json"
)
D44_REANNOTATION_COVERAGE_MATRIX_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_d44_reannotation_coverage_matrix.json"
)
D44_REBASING_TRIGGER_LEDGER_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_d44_rebasing_trigger_ledger.json"
)
D44_REBASING_CANDIDATE_SET_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_d44_rebasing_candidate_set.json"
)
D44_REBASING_RECEIPT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_d44_rebasing_receipt.json"
)
SEALED_BATTERY_INTEGRITY_JOIN_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_sealed_battery_integrity_join.json"
)
OPEN_QUESTION_ANSWER_LEDGER_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_open_question_answer_ledger.json"
)
METRIC_GOVERNANCE_AUDIT_SURFACE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_metric_governance_audit_surface.json"
)
CLOSEOUT_SIGNAL_CONSUMER_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_closeout_signal_consumer_gate.json"
)
PUBLIC_EXPORT_PROJECTION_REFS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_public_export_projection_refs.json"
)
REPLAY_MANIFEST_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g8_replay_manifest.json"
CONFORMANCE_REPORT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_conformance_report.json"
)
HEALTH_METRIC_GOVERNANCE_DELTA_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_health_metric_governance_delta.toml"
)
ROUTE_CONTRACT_REGISTRY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_metric_governance_route_contract_registry.toml"
)
REGISTRY_RATCHET_DELTA_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_registry_ratchet_delta.json"
)
READINESS_MANIFEST_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_readiness_manifest.json"
)

GENERATED_ARTIFACTS_TOML_PATH = Path("architecture/generated_artifacts.toml")
INVENTORY_PATH = POLICY_DESIGN_CASE_DIR / "inventory.json"
GENERATED_ARTIFACTS_DOC_PATH = DOCS_REFERENCE_DIR / "generated-artifacts.md"
PUBLIC_SURFACE_DOC_PATH = DOCS_REFERENCE_DIR / "public-surface.md"
DOCUMENTATION_INVENTORY_PATH = DOCS_REFERENCE_DIR / "documentation-inventory.md"
REFERENCE_INDEX_PATH = DOCS_REFERENCE_DIR / "index.md"
RUNTIME_QUALITY_README_PATH = Path("src/polisyos/runtime/quality/README.md")


def validate_layer3_g8_readiness(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    """Build a Layer 3 G8 readiness report from runtime and persisted artifacts."""

    root = Path(repo_root).resolve()
    bundle = g8.build_layer3_g8_bundle(root)
    written_artifact_paths = _write_artifacts(root, bundle) if write else []
    registration_statuses = _registration_statuses(root)
    readiness_manifest = _readiness_manifest(
        bundle=bundle,
        drift_keys=(),
        registration_statuses=registration_statuses,
        issue_codes=(),
    )
    if write:
        _write_json(_resolve_repo_path(root, READINESS_MANIFEST_PATH), readiness_manifest)
        written_artifact_paths.append(READINESS_MANIFEST_PATH.as_posix())
    drift_keys = _manifest_runtime_drift_keys(root, readiness_manifest)
    issues: list[dict[str, str]] = []
    issues.extend(_validate_persisted_artifacts(root))
    issues.extend(_validate_written_artifact_set(written_artifact_paths) if write else [])
    issues.extend(_manifest_runtime_drift_issues(drift_keys))
    issues.extend(_registration_issues(registration_statuses))
    issues.extend(_validate_runtime_surfaces(bundle))
    normalized_issues = _dedupe_issues(issues)
    readiness_manifest = _readiness_manifest(
        bundle=bundle,
        drift_keys=drift_keys,
        registration_statuses=registration_statuses,
        issue_codes=tuple(issue["code"] for issue in normalized_issues),
    )
    if write:
        _write_json(_resolve_repo_path(root, READINESS_MANIFEST_PATH), readiness_manifest)
    return {
        "schema_version": G8_SCHEMA_VERSION,
        "rule_version": G8_RULE_VERSION,
        "status": "fail" if normalized_issues else "pass",
        "issues": normalized_issues,
        "summary": _summary(
            bundle=bundle,
            drift_keys=drift_keys,
            registration_statuses=registration_statuses,
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
    """Run the Layer 3 G8 readiness check CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    report = validate_layer3_g8_readiness(args.repo_root, write=args.write)
    rendered = (
        _json_dumps(report) if args.output_format == "json" else _render_text_report(report)
    )
    if args.output is not None:
        output_path = _resolve_repo_path(Path(args.repo_root).resolve(), args.output)
        atomic_write_text(output_path, rendered)
    sys.stdout.write(rendered)
    return 0 if report["status"] == "pass" else 1


def _write_artifacts(repo_root: Path, bundle: g8.Layer3G8Bundle) -> list[str]:
    payloads: dict[Path, Any] = {
        HEALTH_METRIC_REGISTRY_PATH: bundle.registry,
        METRIC_SOURCE_SNAPSHOT_PATH: bundle.source_snapshot,
        NORMALIZED_METRIC_SIGNALS_PATH: bundle.normalized_signals,
        METRIC_TREND_REPORT_PATH: bundle.metric_trend_report,
        CROSS_METRIC_DIAGNOSIS_PATH: bundle.cross_metric_diagnosis,
        DOMAIN_VS_SEARCH_CEILING_GATE_PATH: bundle.ceiling_gate,
        METRIC_GAMING_FIREWALL_PATH: bundle.metric_gaming_firewall,
        WARNING_LIFECYCLE_LEDGER_PATH: bundle.warning_lifecycle_ledger,
        D44_CORPUS_REBASING_RULE_PATH: bundle.d44_rebasing_rule,
        D44_REANNOTATION_COVERAGE_MATRIX_PATH: (
            bundle.d44_reannotation_coverage_matrix
        ),
        D44_REBASING_TRIGGER_LEDGER_PATH: bundle.d44_rebasing_trigger_ledger,
        D44_REBASING_CANDIDATE_SET_PATH: bundle.d44_rebasing_candidate_set,
        D44_REBASING_RECEIPT_PATH: bundle.d44_rebasing_receipt,
        SEALED_BATTERY_INTEGRITY_JOIN_PATH: bundle.sealed_battery_integrity_join,
        OPEN_QUESTION_ANSWER_LEDGER_PATH: bundle.open_question_answer_ledger,
        METRIC_GOVERNANCE_AUDIT_SURFACE_PATH: bundle.audit_surface,
        CLOSEOUT_SIGNAL_CONSUMER_GATE_PATH: bundle.closeout_signal_consumer_gate,
        PUBLIC_EXPORT_PROJECTION_REFS_PATH: bundle.public_export_projection_refs,
        REPLAY_MANIFEST_PATH: bundle.replay_manifest,
        CONFORMANCE_REPORT_PATH: bundle.conformance_report,
        REGISTRY_RATCHET_DELTA_PATH: bundle.registry_ratchet_delta,
    }
    written: list[str] = []
    for path in EXPECTED_ARTIFACT_PATHS:
        if path == READINESS_MANIFEST_PATH:
            continue
        resolved = _resolve_repo_path(repo_root, path)
        if path == HEALTH_METRIC_GOVERNANCE_DELTA_PATH:
            _write_health_metric_governance_delta(
                resolved,
                _mapping(bundle.health_metric_governance_delta),
            )
        elif path == ROUTE_CONTRACT_REGISTRY_PATH:
            _write_route_contract_registry(
                resolved,
                _mapping(bundle.route_contract_registry),
            )
        else:
            _write_json(resolved, payloads[path])
        written.append(path.as_posix())
    return written


def _summary(
    *,
    bundle: g8.Layer3G8Bundle,
    drift_keys: Sequence[str],
    registration_statuses: Mapping[str, str],
) -> dict[str, Any]:
    audiences = set(bundle.audit_surface.surface_audiences)
    summary: dict[str, Any] = {
        "schema_version": G8_SCHEMA_VERSION,
        "rule_version": G8_RULE_VERSION,
        "status": bundle.audit_surface.status,
        "surface_id": g8.G8_SURFACE_ID,
        "expected_artifact_count": len(EXPECTED_ARTIFACT_PATHS),
        "may_not_use_for": list(g8.G8_MAY_NOT_USE_FOR),
        "g8_metric_governance_status": bundle.audit_surface.status,
        "g8_canonical_metric_count": len(bundle.registry.entries),
        "g8_metric_alias_resolution_status": (
            "pass" if not bundle.registry.issue_codes else "blocked"
        ),
        "g8_metric_source_snapshot_status": bundle.source_snapshot.status,
        "g8_metric_source_count": bundle.source_snapshot.source_count,
        "g8_normalized_metric_signal_status": bundle.normalized_signals.status,
        "g8_metric_trend_report_status": bundle.metric_trend_report.status,
        "g8_effective_independence_status": (
            bundle.cross_metric_diagnosis.effective_independence_status
        ),
        "g8_effective_independent_evidence_count": (
            bundle.cross_metric_diagnosis.effective_independent_evidence_count
        ),
        "g8_domain_vs_search_ceiling_status": bundle.ceiling_gate.status,
        "g8_metric_gaming_firewall_status": bundle.metric_gaming_firewall.status,
        "g8_warning_lifecycle_status": bundle.warning_lifecycle_ledger.status,
        "g8_d44_rebasing_rule_status": bundle.d44_rebasing_rule.status,
        "g8_d44_reannotation_coverage_status": (
            bundle.d44_reannotation_coverage_matrix.status
        ),
        "g8_d44_rebasing_trigger_status": bundle.d44_rebasing_trigger_ledger.status,
        "g8_d44_rebasing_receipt_status": bundle.d44_rebasing_receipt.status,
        "g8_sealed_battery_integrity_status": (
            bundle.sealed_battery_integrity_join.status
        ),
        "g8_open_question_answer_status": bundle.open_question_answer_ledger.status,
        "g8_expert_machine_surface_status": (
            "pass" if audiences == {"EXPERT", "MACHINE"} else "blocked"
        ),
        "g8_closeout_signal_consumer_status": (
            bundle.closeout_signal_consumer_gate.status
        ),
        "g8_public_projection_contract_status": (
            bundle.public_export_projection_refs.public_projection_status
        ),
        "g8_replay_manifest_status": bundle.replay_manifest.get("status"),
        "g8_conformance_status": bundle.conformance_report.status,
        "g8_generated_artifacts_registration_status": registration_statuses[
            "generated_artifacts"
        ],
        "g8_inventory_surface_status": registration_statuses["inventory"],
        "g8_reference_docs_status": registration_statuses["docs"],
        "g8_route_contract_registry_status": registration_statuses[
            "route_contract_registry"
        ],
        "g8_registry_ratchet_status": registration_statuses["registry_ratchet"],
        "g8_manifest_runtime_drift_key_count": len(drift_keys),
    }
    return summary


def _readiness_manifest(
    *,
    bundle: g8.Layer3G8Bundle,
    drift_keys: Sequence[str],
    registration_statuses: Mapping[str, str],
    issue_codes: Sequence[str],
) -> dict[str, Any]:
    summary = _summary(
        bundle=bundle,
        drift_keys=drift_keys,
        registration_statuses=registration_statuses,
    )
    return {
        "schema_version": G8_SCHEMA_VERSION,
        "rule_version": G8_RULE_VERSION,
        "manifest_id": "layer3-g8-health-metric-governance-readiness",
        "status": "pass" if not drift_keys and not issue_codes else "fail",
        "surface_id": g8.G8_SURFACE_ID,
        "generated_artifact_family": G8_GENERATED_ARTIFACT_FAMILY_ID,
        "expected_artifact_paths": [path.as_posix() for path in EXPECTED_ARTIFACT_PATHS],
        "manifest_runtime_drift_keys": list(drift_keys),
        "summary": summary,
        **{key: summary.get(key) for key in EXPECTED_MANIFEST_DRIFT_KEYS},
        "issue_codes": list(_dedupe_strings(issue_codes)),
        "authoritative_for": list(g8.G8_AUTHORITATIVE_FOR),
        "may_not_use_for": list(g8.G8_MAY_NOT_USE_FOR),
    }


def _validate_persisted_artifacts(repo_root: Path) -> list[dict[str, str]]:
    return [
        _issue(
            "layer3_g8_persisted_artifact_missing",
            path.as_posix(),
            "Layer 3 G8 readiness requires persisted runtime artifacts.",
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
                "layer3_g8_persisted_artifact_missing",
                path,
                "G8 --write must emit every expected persisted artifact path.",
            )
            for path in missing
        ],
        *[
            _issue(
                "layer3_g8_persisted_artifact_missing",
                path,
                "G8 --write emitted a path outside the expected artifact set.",
            )
            for path in unexpected
        ],
    ]


def _manifest_runtime_drift_keys(
    repo_root: Path,
    readiness_manifest: Mapping[str, Any],
) -> list[str]:
    path = _resolve_repo_path(repo_root, READINESS_MANIFEST_PATH)
    if not path.exists():
        return []
    try:
        persisted = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return ["readiness_manifest_unreadable"]
    runtime_summary = _mapping(readiness_manifest.get("summary"))
    persisted_summary = {
        **_mapping(persisted.get("summary")),
        **{
            key: persisted.get(key)
            for key in EXPECTED_MANIFEST_DRIFT_KEYS
            if key in persisted
        },
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
            "layer3_g8_manifest_runtime_drift",
            READINESS_MANIFEST_PATH.as_posix(),
            f"Persisted G8 readiness manifest drifted from runtime: {sorted(drift_keys)}",
        )
    ]


def _registration_statuses(repo_root: Path) -> dict[str, str]:
    generated_text = _read_text_or_empty(repo_root, GENERATED_ARTIFACTS_TOML_PATH)
    inventory_text = _read_text_or_empty(repo_root, INVENTORY_PATH)
    generated_ok = (
        G8_GENERATED_ARTIFACT_FAMILY_ID in generated_text
        and "source_of_truth =" in generated_text
        and "check_command =" in generated_text
        and 'stale_output_behavior = "fail"' in generated_text
        and all(path.as_posix() in generated_text for path in EXPECTED_ARTIFACT_PATHS)
    )
    inventory_ok = (
        g8.G8_SURFACE_ID in inventory_text
        and "src/polisyos/runtime/quality/proving_ground/health_metric_governance.py"
        in inventory_text
        and "check_policy_design_case_layer3_g8_readiness.py" in inventory_text
        and "validate_layer3_g8_readiness" in inventory_text
        and G8_GENERATED_ARTIFACT_FAMILY_ID in inventory_text
        and READINESS_MANIFEST_PATH.as_posix() in inventory_text
        and all(path.as_posix() in inventory_text for path in EXPECTED_ARTIFACT_PATHS)
        and "EXPERT" in inventory_text
        and "MACHINE" in inventory_text
        and "PUBLIC" in inventory_text
        and "REVIEWER" in inventory_text
    )
    docs_checks = (
        (
            GENERATED_ARTIFACTS_DOC_PATH,
            "Policy Design Case Layer 3 G8 health-metric governance artifacts",
        ),
        (GENERATED_ARTIFACTS_DOC_PATH, "layer3_g8_readiness_manifest.json"),
        (PUBLIC_SURFACE_DOC_PATH, g8.G8_SURFACE_ID),
        (PUBLIC_SURFACE_DOC_PATH, "EXPERT/MACHINE"),
        (PUBLIC_SURFACE_DOC_PATH, "out_of_scope_reference_only"),
        (PUBLIC_SURFACE_DOC_PATH, "layer3_g8_closeout_signal_consumer_gate.json"),
        (DOCUMENTATION_INVENTORY_PATH, g8.G8_SURFACE_ID),
        (REFERENCE_INDEX_PATH, "Policy Design Case Layer 3 Health-Metric Governance"),
        (RUNTIME_QUALITY_README_PATH, "layer3_health_metric_governance.py"),
    )
    docs_ok = all(
        needle in _read_text_or_empty(repo_root, path) for path, needle in docs_checks
    )
    route_text = _read_text_or_empty(repo_root, ROUTE_CONTRACT_REGISTRY_PATH)
    registry_text = _read_text_or_empty(repo_root, REGISTRY_RATCHET_DELTA_PATH)
    return {
        "generated_artifacts": "pass" if generated_ok else "fail",
        "inventory": "pass" if inventory_ok else "fail",
        "docs": "pass" if docs_ok else "fail",
        "route_contract_registry": (
            "pass"
            if (
                "route_contract_registry_kind = "
                '"generated_metric_governance_route_contract_registry"'
            )
            in route_text
            and "closeout_consumer_gate" in route_text
            else "fail"
        ),
        "registry_ratchet": (
            "pass" if "layer3_g8_registry_ratchet_delta" in registry_text else "fail"
        ),
    }


def _registration_issues(
    registration_statuses: Mapping[str, str],
) -> list[dict[str, str]]:
    issue_by_key = {
        "generated_artifacts": _issue(
            "layer3_g8_generated_artifacts_family_missing",
            GENERATED_ARTIFACTS_TOML_PATH.as_posix(),
            "Generated artifacts registry must declare the G8 artifact family.",
        ),
        "inventory": _issue(
            "layer3_g8_inventory_surface_missing",
            INVENTORY_PATH.as_posix(),
            "Policy Design Case inventory must expose the G8 audit surface.",
        ),
        "docs": _issue(
            "layer3_g8_reference_docs_missing",
            "docs/reference",
            "Reference docs must mention the G8 readiness surface and artifacts.",
        ),
        "route_contract_registry": _issue(
            "layer3_g8_route_contract_registry_missing",
            ROUTE_CONTRACT_REGISTRY_PATH.as_posix(),
            "G8 route contract registry must be generated and persisted.",
        ),
        "registry_ratchet": _issue(
            "layer3_g8_registry_ratchet_missing",
            REGISTRY_RATCHET_DELTA_PATH.as_posix(),
            "G8 registry ratchet delta must be generated and persisted.",
        ),
    }
    return [
        issue_by_key[key]
        for key, status in registration_statuses.items()
        if status != "pass"
    ]


def _validate_runtime_surfaces(bundle: g8.Layer3G8Bundle) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if bundle.audit_surface.status != "pass":
        for code in bundle.audit_surface.issue_codes or (
            "layer3_g8_metric_governance_audit_surface_blocked",
        ):
            issues.append(
                _issue(
                    str(code),
                    METRIC_GOVERNANCE_AUDIT_SURFACE_PATH.as_posix(),
                    "G8 audit surface must fail readiness when blocker-specific audit is blocked.",
                )
            )
    if bundle.open_question_answer_ledger.status != "pass":
        for code in bundle.open_question_answer_ledger.issue_codes or (
            "layer3_g8_open_question_answer_missing",
        ):
            issues.append(
                _issue(
                    str(code),
                    OPEN_QUESTION_ANSWER_LEDGER_PATH.as_posix(),
                    "G8 open-question answers must not pass with hidden optimism.",
                )
            )
    if bundle.conformance_report.status != "pass":
        for code in bundle.conformance_report.issue_codes or (
            "layer3_g8_conformance_negative_missing",
        ):
            issues.append(
                _issue(
                    str(code),
                    CONFORMANCE_REPORT_PATH.as_posix(),
                    "G8 conformance report must pass all required negative probes.",
                )
            )
    if bundle.closeout_signal_consumer_gate.status != "pass":
        issues.append(
            _issue(
                "layer3_g8_closeout_signal_consumer_missing",
                CLOSEOUT_SIGNAL_CONSUMER_GATE_PATH.as_posix(),
                "G8 closeout consumer gate must expose readiness without authority.",
            )
        )
    if bundle.public_export_projection_refs.public_projection_status != (
        "out_of_scope_reference_only"
    ):
        issues.append(
            _issue(
                "layer3_g8_public_projection_authority_leak",
                PUBLIC_EXPORT_PROJECTION_REFS_PATH.as_posix(),
                "G8 public projection refs must remain reference-only.",
            )
        )
    if bundle.replay_manifest.get("status") != "pass":
        issues.append(
            _issue(
                "layer3_g8_replay_manifest_missing",
                REPLAY_MANIFEST_PATH.as_posix(),
                "G8 replay manifest must be generated and pass structural checks.",
            )
        )
    return issues


def _write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, _json_dumps(_dump(payload)))


def _write_health_metric_governance_delta(
    path: Path,
    payload: Mapping[str, Any],
) -> None:
    lines = [
        f"schema_version = {_toml_value(payload.get('schema_version', G8_SCHEMA_VERSION))}",
        f"rule_version = {_toml_value(payload.get('rule_version', G8_RULE_VERSION))}",
        "",
        "[health_metric_governance_delta]",
    ]
    for key, value in sorted(
        _mapping(payload.get("health_metric_governance_delta")).items()
    ):
        lines.append(f"{_toml_key(str(key))} = {_toml_value(value)}")
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")


def _write_route_contract_registry(
    path: Path,
    payload: Mapping[str, Any],
) -> None:
    lines: list[str] = []
    for key in (
        "schema_version",
        "rule_version",
        "route_contract_registry_kind",
        "surface_id",
        "producer",
        "validator",
        "metric_trend_report",
        "closeout_consumer_gate",
        "may_not_use_for",
    ):
        value = payload.get(key)
        if value is None:
            continue
        lines.append(f"{_toml_key(key)} = {_toml_value(value)}")
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")


def _resolve_repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"_root": payload}


def _read_text_or_empty(repo_root: Path, path: Path) -> str:
    resolved = _resolve_repo_path(repo_root, path)
    try:
        return resolved.read_text(encoding="utf-8")
    except OSError:
        return ""


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, Mapping):
        pairs = [
            f"{_toml_key(str(key))} = {_toml_value(value[key])}" for key in sorted(value)
        ]
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


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value if isinstance(value, Mapping) else {}


def _dedupe_issues(issues: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
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


def _dedupe_strings(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _render_text_report(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [f"layer3_g8_readiness_status={report.get('status', '')}"]
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


if __name__ == "__main__":
    raise SystemExit(main())
