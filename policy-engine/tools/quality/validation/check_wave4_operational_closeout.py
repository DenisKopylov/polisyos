#!/usr/bin/env python3
"""Validate a fresh Wave 4 Honest Diagnostics operational closeout bundle."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.attestation import REQUIRED_TRUST_BOUNDARY_IDS  # noqa: E402
from polisyos.runtime.quality.diagnostic_slos import DIAGNOSTIC_SLO_METRIC_IDS  # noqa: E402

SCHEMA_VERSION = "policyos.honest_diagnostics.wave4_closeout.v1"
TOOL_NAME = "quality.validation.check-wave4-operational-closeout"
DEFAULT_DECISION_LOG = Path(
    "docs/system-design-decisions/honest-diagnostics-substrate-decision-log.md"
)
DEFAULT_BUILD_REPORT = Path(
    "_build/honest-diagnostics/rebaseline/wave-4/wave4_operational_closeout.json"
)

REQUIRED_QUALITY_FILES = {
    "quality_scorecard": "quality_scorecard.json",
    "semantic_binding_ledger": "semantic_binding_ledger.json",
    "decision_artifact_quality": "decision_artifact_quality.json",
    "assurance_case": "assurance_case.json",
    "diagnostic_slo_report": "diagnostic_slo_report.json",
    "attestation_records": "attestation_records.json",
    "public_export_bundle": "public_export_bundle.json",
}
REQUIRED_AUTHORITY_REPORTS = {
    "normative_evidence": "normative_evidence.json",
    "fabric_retrieval_trace": "fabric_retrieval_trace.json",
    "foundry_method_report": "foundry_method_report.json",
    "policy_grounding_matrix": "policy_grounding_matrix.json",
    "semantic_binding_ledger": "semantic_binding_ledger.json",
    "conflict_check": "conflict_check.json",
    "decision_artifact_quality": "decision_artifact_quality.json",
}
AUTHORITY_EVIDENCE_CLASS = "authority_bearing"
AUTHORITY_ROLES = {"producer_authority", "runtime_blocker"}
AUTHORITY_PROVENANCE = {"runtime_emitted", "runtime_blocker"}
FORBIDDEN_PUBLIC_TOKENS = (
    "access_token",
    "api_key",
    "bearer ",
    "hidden_answer",
    "password",
    "private_prompt",
    "provider_config",
    "raw_sensitive",
    "restricted_source",
    "secret-key",
    "sk-",
    "system_prompt",
    "tenant-1",
)


class Wave4CloseoutInputError(ValueError):
    """Raised when the requested bundle cannot be read."""


def build_wave4_operational_closeout_report(
    *,
    repo_root: Path,
    bundle_dir: Path,
    ignore_weekly_baseline_window: bool = False,
    decision_log: Path = DEFAULT_DECISION_LOG,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    bundle_dir = bundle_dir.resolve()
    if not bundle_dir.exists():
        raise Wave4CloseoutInputError(f"bundle_dir does not exist: {bundle_dir}")

    quality_dir = bundle_dir / "quality_evidence"
    bundle = _load_json(bundle_dir / "bundle.json")
    quality = {
        key: _load_json(quality_dir / filename)
        for key, filename in REQUIRED_QUALITY_FILES.items()
        if (quality_dir / filename).is_file()
    }
    authority_reports = {
        key: _load_json(quality_dir / filename)
        for key, filename in REQUIRED_AUTHORITY_REPORTS.items()
        if (quality_dir / filename).is_file()
    }
    migration_sandbox = _load_json(
        bundle_dir / "migration_sandbox" / "legacy_migration_sandbox.json"
    )
    runtime_refs = _runtime_refs(bundle_dir)
    evidence_bundle_ref = _relative(bundle_dir, repo_root)
    decision_log_path = _resolve(repo_root, decision_log)

    item_rows: list[dict[str, Any]] = []
    item_rows.append(
        _item(
            "semantic_binding_claim_level",
            _semantic_binding_findings(quality, authority_reports),
            evidence_refs=["quality_evidence/semantic_binding_ledger.json"],
        )
    )
    item_rows.append(
        _item(
            "candidate_selected_rejected_blockers_preserved",
            _candidate_evidence_findings(quality),
            evidence_refs=["quality_evidence/semantic_binding_ledger.json"],
        )
    )
    item_rows.append(
        _item(
            "compiler_grade_final_artifacts",
            _decision_artifact_findings(quality),
            evidence_refs=["quality_evidence/decision_artifact_quality.json"],
        )
    )
    item_rows.append(
        _item(
            "legacy_quarantined_unless_compatible",
            _legacy_quarantine_findings(migration_sandbox),
            evidence_refs=["migration_sandbox/legacy_migration_sandbox.json"],
        )
    )
    item_rows.append(
        _item(
            "migration_sandbox_authority_side_only",
            _migration_sandbox_findings(migration_sandbox),
            evidence_refs=["migration_sandbox/legacy_migration_sandbox.json"],
        )
    )
    item_rows.append(
        _item(
            "serious_bundle_assurance_and_slos",
            _assurance_and_slo_findings(quality),
            evidence_refs=[
                "quality_evidence/assurance_case.json",
                "quality_evidence/diagnostic_slo_report.json",
            ],
        )
    )
    item_rows.append(
        _item(
            "trust_boundary_attestation_verified",
            _attestation_findings(quality),
            evidence_refs=["quality_evidence/attestation_records.json"],
        )
    )
    item_rows.append(
        _item(
            "public_exports_projection_only",
            _public_export_findings(quality),
            evidence_refs=["quality_evidence/public_export_bundle.json"],
        )
    )
    item_rows.append(
        _item(
            "coverage_dashboard_wave4_targets",
            _coverage_evidence_findings(bundle, quality),
            evidence_refs=["quality_evidence", "bundle.json"],
        )
    )
    weekly_item = {
        "item_id": "weekly_baseline_window",
        "status": (
            "not_applicable_by_instruction"
            if ignore_weekly_baseline_window
            else _weekly_baseline_status(migration_sandbox)
        ),
        "evidence_refs": ["migration_sandbox/legacy_migration_sandbox.json"],
        "findings": []
        if ignore_weekly_baseline_window
        else _weekly_baseline_findings(migration_sandbox),
        "note": (
            "Two consecutive weekly closeout baselines were explicitly excluded "
            "from this Wave 4 implementation request."
        ),
    }
    item_rows.append(weekly_item)
    item_rows.append(
        _item(
            "anti_drift_decision_log_recorded",
            _decision_log_findings(decision_log_path),
            evidence_refs=[_relative(decision_log_path, repo_root)],
        )
    )

    blocking_findings = [
        {**finding, "item_id": item["item_id"]}
        for item in item_rows
        if item["status"] == "fail"
        for finding in item.get("findings", [])
    ]
    public_export_ref = (
        "quality_evidence/public_export_bundle.json"
        if "public_export_bundle" in quality
        else None
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "status": "fail" if blocking_findings else "pass",
        "evidence_bundle_ref": evidence_bundle_ref,
        "runtime_refs": runtime_refs,
        "authority_envelope_refs": _authority_envelope_refs(authority_reports),
        "diagnostic_slo_refs": _diagnostic_slo_refs(quality.get("diagnostic_slo_report")),
        "attestation_refs": _attestation_refs(quality.get("attestation_records")),
        "migration_sandbox_ref": "migration_sandbox/legacy_migration_sandbox.json",
        "public_export_ref": public_export_ref,
        "decision_log_ref": _relative(decision_log_path, repo_root),
        "exit_fence_items": item_rows,
        "blocking_findings": blocking_findings,
    }


def dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _item(
    item_id: str,
    findings: list[dict[str, Any]],
    *,
    evidence_refs: list[str],
) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "status": "fail" if findings else "pass",
        "evidence_refs": evidence_refs,
        "findings": findings,
    }


def _finding(code: str, message: str, *, evidence_ref: str | None = None) -> dict[str, Any]:
    row = {"code": code, "message": message}
    if evidence_ref is not None:
        row["evidence_ref"] = evidence_ref
    return row


def _semantic_binding_findings(
    quality: Mapping[str, Any],
    authority_reports: Mapping[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    ledger = _without_authority(quality.get("semantic_binding_ledger"))
    if not isinstance(ledger, Mapping):
        return [_finding("semantic_binding_ledger_missing", "Semantic binding ledger is missing.")]
    if ledger.get("schema_version") != "policyos.semantic_binding_ledger.v1":
        findings.append(
            _finding("semantic_binding_schema_invalid", "Semantic binding schema is invalid.")
        )
    if ledger.get("status") != "pass":
        findings.append(
            _finding("semantic_binding_status_not_pass", "Semantic binding did not pass.")
        )
    semantic_ref = _text(ledger.get("semantic_binding_ref"))
    if semantic_ref is None:
        findings.append(
            _finding("semantic_binding_ref_missing", "Semantic binding ref is missing.")
        )
    for section in ("intent", "lex", "fabric", "foundry", "scientist", "final_compiler"):
        value = ledger.get(section)
        if not value:
            findings.append(
                _finding(
                    "semantic_binding_phase_missing",
                    f"Semantic binding section is missing: {section}.",
                )
            )
    for report_key in REQUIRED_AUTHORITY_REPORTS:
        report = authority_reports.get(report_key)
        envelope = report.get("authority_envelope") if isinstance(report, Mapping) else None
        if not isinstance(envelope, Mapping):
            findings.append(
                _finding(
                    "authority_envelope_missing",
                    f"{report_key} is missing an authority envelope.",
                    evidence_ref=f"quality_evidence/{REQUIRED_AUTHORITY_REPORTS[report_key]}",
                )
            )
            continue
        if _normalized(envelope.get("evidence_class")) != AUTHORITY_EVIDENCE_CLASS:
            findings.append(
                _finding(
                    "authority_evidence_class_invalid",
                    f"{report_key} is not authority-bearing evidence.",
                )
            )
        if _normalized(envelope.get("authority_role")) not in AUTHORITY_ROLES:
            findings.append(
                _finding(
                    "authority_role_invalid",
                    f"{report_key} authority role cannot satisfy closeout.",
                )
            )
        if _normalized(envelope.get("provenance_kind")) not in AUTHORITY_PROVENANCE:
            findings.append(
                _finding(
                    "authority_provenance_invalid",
                    f"{report_key} provenance is not runtime authority.",
                )
            )
        envelope_semantic_ref = _text(envelope.get("semantic_binding_ref"))
        if semantic_ref and envelope_semantic_ref != semantic_ref:
            findings.append(
                _finding(
                    "semantic_binding_ref_mismatch",
                    f"{report_key} semantic_binding_ref does not match the ledger.",
                )
            )
    return findings


def _candidate_evidence_findings(quality: Mapping[str, Any]) -> list[dict[str, Any]]:
    ledger = _without_authority(quality.get("semantic_binding_ledger"))
    if not isinstance(ledger, Mapping):
        return [_finding("semantic_binding_ledger_missing", "Semantic binding ledger is missing.")]
    findings: list[dict[str, Any]] = []
    requirements = {
        "lex": (
            "candidate_norm_refs",
            "selected_norm_refs",
            "rejected_norm_refs",
            "no_norm_blocker_refs",
            "retrieval_error_blocker_refs",
        ),
        "fabric": (
            "candidate_dataset_source_refs",
            "selected_dataset_source_refs",
            "rejected_dataset_source_refs",
            "data_gap_blocker_refs",
            "ambiguity_blocker_refs",
        ),
        "foundry": (
            "selected_method_refs",
            "rejected_method_refs",
            "method_incompatibility_blocker_refs",
        ),
    }
    for section, keys in requirements.items():
        records = ledger.get(section)
        if not isinstance(records, Sequence) or isinstance(records, str) or not records:
            findings.append(
                _finding("semantic_candidate_records_missing", f"{section} records are missing.")
            )
            continue
        for key in keys:
            if key not in records[0]:
                findings.append(
                    _finding(
                        "semantic_candidate_field_missing",
                        f"{section}.{key} is missing.",
                    )
                )
    return findings


def _decision_artifact_findings(quality: Mapping[str, Any]) -> list[dict[str, Any]]:
    report = quality.get("decision_artifact_quality")
    if not isinstance(report, Mapping):
        return [_finding("decision_artifact_quality_missing", "Decision artifact quality is missing.")]
    findings: list[dict[str, Any]] = []
    if report.get("status") != "pass":
        findings.append(
            _finding("decision_artifact_quality_not_pass", "Decision artifact quality did not pass.")
        )
    if int(report.get("blocking_issue_count") or 0) != 0:
        findings.append(
            _finding("decision_artifact_blocking_issues", "Decision artifact has blocking issues.")
        )
    issues = report.get("issues")
    if isinstance(issues, Sequence) and not isinstance(issues, str):
        for issue in issues:
            if isinstance(issue, Mapping) and _normalized(issue.get("severity")) in {
                "fail",
                "block",
                "blocking",
            }:
                findings.append(
                    _finding(
                        str(issue.get("code") or "decision_artifact_issue"),
                        "Decision artifact contains a failing issue.",
                    )
                )
    if "compiler_issues" in report:
        findings.append(
            _finding("decision_artifact_compiler_issues", "Compiler issues remain in final report.")
        )
    if not isinstance(report.get("authority_envelope"), Mapping):
        findings.append(
            _finding(
                "decision_artifact_authority_envelope_missing",
                "Decision artifact quality lacks authority envelope.",
            )
        )
    return findings


def _legacy_quarantine_findings(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if report.get("status") != "pass":
        findings.append(_finding("legacy_migration_sandbox_failed", "Migration sandbox failed."))
    policy = report.get("closeout_policy")
    if not isinstance(policy, Mapping) or policy.get("legacy_satisfies_serious_gates") is not False:
        findings.append(
            _finding(
                "legacy_can_satisfy_serious_gates",
                "Legacy side is not explicitly blocked from serious gates.",
            )
        )
    for comparison in _sequence_of_mappings(report.get("comparisons")):
        legacy = comparison.get("legacy")
        if not isinstance(legacy, Mapping):
            continue
        if _normalized(legacy.get("evidence_class")) != "legacy_quarantined":
            findings.append(
                _finding("legacy_not_quarantined", "Legacy comparison output is not quarantined.")
            )
        if _normalized(legacy.get("authority_role")) != "diagnostic_only":
            findings.append(
                _finding("legacy_role_not_diagnostic_only", "Legacy output can act as authority.")
            )
    return findings


def _migration_sandbox_findings(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if report.get("production_closeout_allowed") is not True:
        findings.append(
            _finding(
                "migration_sandbox_closeout_blocked",
                "Migration sandbox does not allow authority-side closeout.",
            )
        )
    for comparison in _sequence_of_mappings(report.get("comparisons")):
        if comparison.get("status") != "pass":
            findings.append(
                _finding(
                    "migration_comparison_failed",
                    f"Migration comparison failed: {comparison.get('report_key')}.",
                )
            )
        authority = comparison.get("authority_validation")
        if not isinstance(authority, Mapping) or authority.get("status") != "pass":
            findings.append(
                _finding(
                    "migration_authority_envelope_missing",
                    f"Authority side is not envelope-backed: {comparison.get('report_key')}.",
                )
            )
    return findings


def _assurance_and_slo_findings(quality: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    assurance = quality.get("assurance_case")
    if not isinstance(assurance, Mapping):
        findings.append(_finding("assurance_case_missing", "Assurance case is missing."))
    else:
        if "provisional" in json.dumps(assurance, sort_keys=True).casefold():
            findings.append(
                _finding("assurance_case_provisional", "Final assurance case is provisional.")
            )
        for key in ("claim", "argument", "evidence", "owner", "next_diagnostic_command"):
            if not assurance.get(key):
                findings.append(
                    _finding("assurance_case_field_missing", f"Assurance case missing {key}.")
                )
        if assurance.get("non_overridable_blockers"):
            findings.append(
                _finding(
                    "assurance_case_non_overridable_blockers",
                    "Assurance case still has non-overridable blockers.",
                )
            )
    slos = quality.get("diagnostic_slo_report")
    if not isinstance(slos, Mapping):
        findings.append(_finding("diagnostic_slo_report_missing", "Diagnostic SLO report is missing."))
        return findings
    if slos.get("status") != "pass" or slos.get("readiness_decision") != "pass":
        findings.append(_finding("diagnostic_slo_not_pass", "Diagnostic SLO report did not pass."))
    metrics = {
        str(metric.get("metric_id")): metric
        for metric in _sequence_of_mappings(slos.get("metrics"))
    }
    for metric_id in DIAGNOSTIC_SLO_METRIC_IDS:
        metric = metrics.get(metric_id)
        if metric is None:
            findings.append(
                _finding("diagnostic_slo_metric_missing", f"Missing SLO metric {metric_id}.")
            )
            continue
        if metric.get("status") != "pass":
            findings.append(
                _finding("diagnostic_slo_metric_not_pass", f"SLO metric failed: {metric_id}.")
            )
        if not metric.get("observed_at") or not metric.get("evidence_ref"):
            findings.append(
                _finding(
                    "diagnostic_slo_metric_not_observed",
                    f"SLO metric lacks observation evidence: {metric_id}.",
                )
            )
    if slos.get("blockers"):
        findings.append(_finding("diagnostic_slo_blockers", "Diagnostic SLO blockers remain."))
    return findings


def _attestation_findings(quality: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = quality.get("attestation_records")
    if not isinstance(records, Sequence) or isinstance(records, str):
        return [_finding("attestation_records_missing", "Attestation records are missing.")]
    by_boundary = {
        str(record.get("trust_boundary_id")): record
        for record in records
        if isinstance(record, Mapping)
    }
    findings: list[dict[str, Any]] = []
    for boundary_id in sorted(REQUIRED_TRUST_BOUNDARY_IDS):
        record = by_boundary.get(boundary_id)
        if record is None:
            findings.append(
                _finding("attestation_required_boundary_missing", f"Missing {boundary_id}.")
            )
            continue
        if record.get("signature_ref") in {None, ""}:
            findings.append(_finding("attestation_signature_missing", f"{boundary_id} unsigned."))
        if record.get("evidence_ref") in {None, ""}:
            findings.append(_finding("attestation_evidence_missing", f"{boundary_id} lacks evidence."))
        if record.get("consumer_verification") != "verified":
            findings.append(
                _finding("attestation_not_verified", f"{boundary_id} is not verified.")
            )
        if record.get("tamper_check_status") != "pass":
            findings.append(
                _finding("attestation_tamper_check_failed", f"{boundary_id} tamper check failed.")
            )
        if _contains_synthetic_attestation_ref(record):
            findings.append(
                _finding(
                    "attestation_synthetic_ref",
                    f"{boundary_id} contains synthetic attestation refs.",
                )
            )
    return findings


def _public_export_findings(quality: Mapping[str, Any]) -> list[dict[str, Any]]:
    bundle = quality.get("public_export_bundle")
    if not isinstance(bundle, Mapping):
        return [_finding("public_export_bundle_missing", "Public export bundle is missing.")]
    findings: list[dict[str, Any]] = []
    expected = {
        "evidence_class": "redacted_derived",
        "authority_role": "projection_only",
        "allowed_scorecard_authority_role": "not_authoritative",
    }
    for key, expected_value in expected.items():
        if bundle.get(key) != expected_value:
            findings.append(
                _finding("public_export_authority_boundary_invalid", f"{key} is not {expected_value}.")
            )
    limits = bundle.get("official_use_limits")
    if not isinstance(limits, Mapping):
        findings.append(
            _finding("public_export_official_use_limits_missing", "Official-use limits are missing.")
        )
    else:
        denied = {str(item) for item in _sequence(limits.get("may_not_be_used_for"))}
        for required in (
            "scorecard_authority",
            "approval_authority",
            "runtime_closeout_authority",
        ):
            if required not in denied:
                findings.append(
                    _finding("public_export_official_use_limits_missing", f"{required} not denied.")
                )
    public_text = json.dumps(bundle, sort_keys=True).casefold()
    for token in FORBIDDEN_PUBLIC_TOKENS:
        if token in public_text:
            findings.append(
                _finding("public_export_sensitive_token_leaked", f"Forbidden token leaked: {token}.")
            )
    semantic = bundle.get("semantic_audit")
    if not isinstance(semantic, Mapping) or not semantic.get("authority_projections"):
        findings.append(
            _finding("public_export_semantic_audit_missing", "Semantic audit projection is missing.")
        )
    return findings


def _coverage_evidence_findings(
    bundle: Mapping[str, Any],
    quality: Mapping[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    files = bundle.get("files")
    quality_files = files.get("quality_evidence") if isinstance(files, Mapping) else None
    if not isinstance(quality_files, Mapping):
        findings.append(_finding("bundle_quality_file_index_missing", "Bundle file index is missing."))
    else:
        for required in ("assurance_case", "diagnostic_slo_report", "public_export_bundle"):
            if not quality_files.get(required):
                findings.append(
                    _finding("bundle_quality_file_index_incomplete", f"Missing index for {required}.")
                )
    for key in REQUIRED_QUALITY_FILES:
        if key not in quality:
            findings.append(
                _finding("wave4_required_evidence_missing", f"Missing quality evidence {key}.")
            )
    return findings


def _decision_log_findings(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return [_finding("decision_log_missing", "Decision log is missing.")]
    text = path.read_text(encoding="utf-8").casefold()
    required_terms = ("wave 4", "weekly", "baseline", "check_substrate_drift")
    return [
        _finding("decision_log_wave4_closeout_missing", f"Decision log lacks {term}.")
        for term in required_terms
        if term not in text
    ]


def _weekly_baseline_status(report: Mapping[str, Any]) -> str:
    return "fail" if _weekly_baseline_findings(report) else "pass"


def _weekly_baseline_findings(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    policy = report.get("dual_write_policy")
    observed = policy.get("observed_consecutive_weekly_closeout_baselines") if isinstance(policy, Mapping) else None
    try:
        observed_count = int(observed)
    except (TypeError, ValueError):
        observed_count = 0
    if observed_count >= 2:
        return []
    return [
        _finding(
            "weekly_baseline_window_incomplete",
            "Two consecutive weekly closeout baselines have not been observed.",
        )
    ]


def _authority_envelope_refs(authority_reports: Mapping[str, Any]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for key, report in authority_reports.items():
        envelope = report.get("authority_envelope") if isinstance(report, Mapping) else None
        if not isinstance(envelope, Mapping):
            continue
        ref = _text(envelope.get("cas_ref") or envelope.get("artifact_ref"))
        if ref is not None:
            refs[key] = ref
    return refs


def _diagnostic_slo_refs(report: Any) -> dict[str, str]:
    if not isinstance(report, Mapping):
        return {}
    refs: dict[str, str] = {}
    for metric in _sequence_of_mappings(report.get("metrics")):
        metric_id = _text(metric.get("metric_id"))
        ref = _text(metric.get("evidence_ref"))
        if metric_id and ref:
            refs[metric_id] = ref
    return refs


def _attestation_refs(records: Any) -> dict[str, str]:
    refs: dict[str, str] = {}
    if not isinstance(records, Sequence) or isinstance(records, str):
        return refs
    for record in records:
        if not isinstance(record, Mapping):
            continue
        boundary_id = _text(record.get("trust_boundary_id"))
        ref = _text(record.get("evidence_ref"))
        if boundary_id and ref:
            refs[boundary_id] = ref
    return refs


def _runtime_refs(bundle_dir: Path) -> dict[str, str]:
    refs: dict[str, str] = {}
    for path in (bundle_dir / "job.json", bundle_dir / "run.json"):
        if not path.is_file():
            continue
        payload = _load_json(path)
        runtime_refs = _nested_get(payload, ("progress", "details", "runtime_quality_refs"))
        if isinstance(runtime_refs, Mapping):
            refs.update({str(key): str(value) for key, value in runtime_refs.items()})
        params_refs = _nested_get(payload, ("params", "runtime_quality_refs"))
        if isinstance(params_refs, Mapping):
            refs.update({str(key): str(value) for key, value in params_refs.items()})
    return refs


def _contains_synthetic_attestation_ref(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_synthetic_attestation_ref(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return any(_contains_synthetic_attestation_ref(item) for item in value)
    return isinstance(value, str) and value.startswith("attestation://")


def _without_authority(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return value
    stripped = dict(value)
    stripped.pop("authority_envelope", None)
    return stripped


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return list(value)
    return []


def _sequence_of_mappings(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in _sequence(value) if isinstance(item, Mapping)]


def _nested_get(payload: Any, path: Iterable[str]) -> Any:
    current = payload
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _normalized(value: Any) -> str:
    return str(value or "").strip().casefold()


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise Wave4CloseoutInputError(f"required JSON file is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise Wave4CloseoutInputError(f"invalid JSON file: {path}: {exc}") from exc


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--decision-log", type=Path, default=DEFAULT_DECISION_LOG)
    parser.add_argument("--ignore-weekly-baseline-window", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    try:
        report = build_wave4_operational_closeout_report(
            repo_root=repo_root,
            bundle_dir=_resolve(repo_root, args.bundle_dir),
            ignore_weekly_baseline_window=args.ignore_weekly_baseline_window,
            decision_log=args.decision_log,
        )
    except Wave4CloseoutInputError as exc:
        sys.stderr.write(f"wave4 operational closeout failed: {exc}\n")
        return 2

    bundle_report = _resolve(repo_root, args.bundle_dir) / "quality_evidence" / (
        "wave4_operational_closeout.json"
    )
    build_report = (
        _resolve(repo_root, args.json_output) if args.json_output else repo_root / DEFAULT_BUILD_REPORT
    )
    for path in (bundle_report, build_report):
        atomic_write_text(path, dump_json(report))
    if report["status"] != "pass":
        sys.stderr.write(
            "wave4 operational closeout: fail; blocking findings="
            f"{len(report['blocking_findings'])}\n"
        )
        return 1
    sys.stdout.write("wave4 operational closeout: pass\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
