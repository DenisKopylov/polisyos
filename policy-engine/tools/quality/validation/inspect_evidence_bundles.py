#!/usr/bin/env python3
"""Inspect selected serious evidence bundles for Phase 6.4 closeout."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.authority import (  # noqa: E402
    authority_envelope_ownership_issues,
)
from polisyos.runtime.quality.concept_spine import (  # noqa: E402
    build_policy_design_concept_spine_boundary_record,
)
from polisyos.runtime.quality.data_forge_binding import (  # noqa: E402
    DATA_FORGE_SNAPSHOT_BINDING_FILE,
    normalize_data_forge_snapshot_binding_report,
)
from polisyos.runtime.quality.nl_replay_orchestration import (  # noqa: E402
    NL_REPLAY_ORCHESTRATION_FILE_REF,
    NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION,
)
from polisyos.runtime.quality.policy_design_jurisdiction_spine import (  # noqa: E402
    build_policy_design_jurisdiction_spine_boundary_record,
)
from polisyos.runtime.quality.scholar_academic_evidence import (  # noqa: E402
    SCHOLAR_ACADEMIC_EVIDENCE_FILENAME,
    build_scholar_academic_evidence_boundary_record,
)
from polisyos.runtime.quality.scorecard import (  # noqa: E402
    QUALITY_REPORT_FILES,
    QUALITY_REPORT_RUNTIME_REFS,
)

SCHEMA_VERSION = "policyos.evidence_bundle_inspection.v1"
TOOL_NAME = "quality.validation.inspect-evidence-bundles"
SERIOUS_PROFILES = {"research", "governed", "production"}
SETUP_EVIDENCE_PROFILES = {"governed", "production"}
PASSING_BUNDLE_STATUSES = {"pass", "passed", "completed"}
NON_READY_RESULT_STATUSES = {"blocked", "failed", "skipped", "not_run"}

ComponentPredicate = Callable[[Path, Mapping[str, Any]], bool]
ComponentSpec = tuple[str, tuple[str, ...], ComponentPredicate]

REQUIRED_COMPONENTS: tuple[ComponentSpec, ...] = (
    (
        "evidence_provenance_manifest",
        ("quality_evidence/evidence_provenance_manifest.json",),
        lambda root, payloads: _json_file_has_schema(
            root,
            "quality_evidence/evidence_provenance_manifest.json",
            "policyos.evidence_provenance_manifest.v1",
        ),
    ),
    (
        "authority_envelopes",
        ("quality_evidence/*.json",),
        lambda _root, payloads: bool(_nested_find_all(payloads, "authority_envelope")),
    ),
    (
        "diagnostic_events",
        ("job.json#/progress/details/diagnostic_events", "run.json#/diagnostic_events"),
        lambda _root, payloads: _has_diagnostic_events(payloads),
    ),
    (
        "diagnostic_event_type_registry_version",
        ("quality_evidence/replay_manifest.json#/registry_refs/event_type_registry",),
        lambda _root, payloads: _has_event_registry_version(payloads),
    ),
    (
        "provider_model_quality_ledger",
        ("quality_evidence/provider_model_quality_ledger.json",),
        lambda root, _payloads: (
            root / "quality_evidence/provider_model_quality_ledger.json"
        ).is_file(),
    ),
    (
        "performance_budget_evidence",
        ("canary_performance_budget.json", "performance.json"),
        lambda root, _payloads: (root / "canary_performance_budget.json").is_file()
        or (root / "performance.json").is_file(),
    ),
    (
        "cas_producer_governance_metadata",
        ("cas_manifests/quality_artifact_ownership.manifest.json",),
        lambda root, _payloads: _cas_manifest_has_producer_governance(root),
    ),
    (
        "effective_mode_ledger",
        ("effective_mode_ledger", "effective_mode_ref", "effective_mode_ledger_ref"),
        lambda _root, payloads: _has_any_nested_key(
            payloads,
            ("effective_mode_ledger", "effective_mode_ref", "effective_mode_ledger_ref"),
        ),
    ),
    (
        "fallback_degradation_ledger",
        ("degradation_ledger", "degradation_ledger_ref", "fallback_degradation_ref"),
        lambda _root, payloads: _has_any_nested_key(
            payloads,
            ("degradation_ledger", "degradation_ledger_ref", "fallback_degradation_ref"),
        ),
    ),
    (
        "semantic_binding_ledger",
        ("quality_evidence/semantic_binding_ledger.json",),
        lambda root, _payloads: (root / "quality_evidence/semantic_binding_ledger.json").is_file(),
    ),
    (
        "prompt_tool_parser_ledger",
        ("quality_evidence/prompt_tool_ledger.json",),
        lambda root, _payloads: (root / "quality_evidence/prompt_tool_ledger.json").is_file(),
    ),
    (
        "source_truth_conflict_records",
        ("quality_evidence/source_truth_conflicts.json",),
        lambda root, payloads: (root / "quality_evidence/source_truth_conflicts.json").is_file()
        or _has_any_nested_key(payloads, ("source_truth_conflicts",)),
    ),
    (
        "adapter_preservation_records",
        ("quality_evidence/source_truth_conflicts.json#/adapter_preservation_records",),
        lambda _root, payloads: bool(
            _nested_find_all(payloads, "adapter_preservation_records")
        )
        or _has_any_nested_key(
            payloads,
            ("source_truth_adapter_surfaces", "source_truth_adapter_paths"),
        ),
    ),
    (
        "schema_compatibility_decisions",
        ("quality_evidence/replay_manifest.json#/schema_compatibility_decisions",),
        lambda _root, payloads: _has_schema_compatibility_decisions(payloads),
    ),
    (
        "invariant_proof_harness_report",
        ("quality_evidence/invariant_proof_harness_report.json",),
        lambda root, _payloads: (
            root / "quality_evidence/invariant_proof_harness_report.json"
        ).is_file(),
    ),
    (
        "replay_evidence",
        ("quality_evidence/replay_manifest.json", "quality_evidence/drift_explanation.json"),
        lambda root, _payloads: (root / "quality_evidence/replay_manifest.json").is_file()
        and (root / "quality_evidence/drift_explanation.json").is_file(),
    ),
    (
        "resilience_evidence",
        ("quality_evidence/resilience_matrix.json",),
        lambda root, _payloads: (root / "quality_evidence/resilience_matrix.json").is_file(),
    ),
    (
        "privacy_security_evidence",
        (
            "quality_evidence/privacy_compliance_report.json",
            "quality_evidence/security_assurance_report.json",
        ),
        lambda root, _payloads: (
            root / "quality_evidence/privacy_compliance_report.json"
        ).is_file()
        and (root / "quality_evidence/security_assurance_report.json").is_file(),
    ),
    (
        "human_review_evidence",
        ("quality_evidence/human_review_calibration_report.json",),
        lambda root, _payloads: (
            root / "quality_evidence/human_review_calibration_report.json"
        ).is_file(),
    ),
    (
        "decision_quality_evidence",
        ("quality_evidence/decision_artifact_quality.json",),
        lambda root, _payloads: (
            root / "quality_evidence/decision_artifact_quality.json"
        ).is_file(),
    ),
    (
        "data_forge_snapshot_binding",
        (f"quality_evidence/{DATA_FORGE_SNAPSHOT_BINDING_FILE}",),
        lambda _root, payloads: _data_forge_snapshot_boundary_status(payloads) == "pass",
    ),
    (
        "scholar_academic_evidence",
        (f"quality_evidence/{SCHOLAR_ACADEMIC_EVIDENCE_FILENAME}",),
        lambda _root, payloads: _scholar_academic_boundary_status(payloads) == "pass",
    ),
    (
        "policy_design_concept_spine_boundary",
        ("quality_evidence/policy_design_case.json#/concept_spine",),
        lambda _root, payloads: _concept_spine_boundary_status(payloads) == "pass",
    ),
    (
        "policy_design_jurisdiction_spine_boundary",
        ("quality_evidence/policy_design_case.json#/jurisdiction_spine",),
        lambda _root, payloads: _jurisdiction_spine_boundary_status(payloads) == "pass",
    ),
    (
        "runtime_orchestration_continuity",
        (NL_REPLAY_ORCHESTRATION_FILE_REF,),
        lambda root, _payloads: _json_file_has_schema(
            root,
            NL_REPLAY_ORCHESTRATION_FILE_REF,
            NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION,
        )
        and _status_from_payload(
            _load_json_or_none(root / NL_REPLAY_ORCHESTRATION_FILE_REF),
            "status",
        )
        == "pass",
    ),
    (
        "assurance_case",
        ("quality_evidence/assurance_case.json",),
        lambda root, _payloads: (root / "quality_evidence/assurance_case.json").is_file(),
    ),
    (
        "diagnostic_slo_evidence",
        ("quality_evidence/diagnostic_slo_report.json",),
        lambda root, _payloads: (
            root / "quality_evidence/diagnostic_slo_report.json"
        ).is_file(),
    ),
    (
        "attestation_records",
        ("quality_evidence/attestation_records.json",),
        lambda root, _payloads: (root / "quality_evidence/attestation_records.json").is_file(),
    ),
    (
        "continuous_governance_lifecycle_evidence",
        (
            "quality_evidence/continuous_governance_stale_report.json",
            "quality_evidence/continuous_governance_reissue_report.json",
            "quality_evidence/continuous_governance_supersede_report.json",
            "quality_evidence/continuous_governance_withdraw_report.json",
        ),
        lambda root, payloads: (
            (not _published_decision_lifecycle_in_scope(payloads))
            or all(
                (root / rel_path).is_file()
                for rel_path in (
                    "quality_evidence/continuous_governance_stale_report.json",
                    "quality_evidence/continuous_governance_reissue_report.json",
                    "quality_evidence/continuous_governance_supersede_report.json",
                    "quality_evidence/continuous_governance_withdraw_report.json",
                )
            )
        ),
    ),
)

FORBIDDEN_PUBLIC_TOKENS = (
    "access_token",
    "api_key",
    "bearer ",
    "hidden_answer",
    "hidden answer",
    "password",
    "private_prompt",
    "provider_credential",
    "provider_config",
    "raw_sensitive",
    "restricted_source",
    "secret-key",
    "sk-",
    "system_prompt",
)
UNSAFE_PUBLIC_PATH_MARKERS = (
    "/users/",
    "\\users\\",
    "../",
    "..\\",
    "/private/",
    "/var/folders/",
)


class EvidenceBundleInspectionInputError(ValueError):
    """Raised when Phase 6.4 inspection input cannot be read."""


def build_evidence_bundle_inspection_report(
    *,
    repo_root: Path = REPO_ROOT,
    bundle_dirs: Sequence[Path] = (),
    matrix_run_payload: Mapping[str, Any] | None = None,
    matrix_run_path: Path | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    matrix_payload = _load_matrix_payload(repo_root, matrix_run_payload, matrix_run_path)
    selected = _selected_inspection_targets(
        repo_root=repo_root,
        bundle_dirs=bundle_dirs,
        matrix_run_payload=matrix_payload,
    )
    bundle_inspections = [_inspect_target(target) for target in selected]
    findings = [
        {**finding, "lane_id": inspection.get("lane_id")}
        for inspection in bundle_inspections
        for finding in inspection.get("findings", [])
        if isinstance(finding, Mapping)
    ]
    fail_count = sum(1 for finding in findings if finding.get("status") == "fail")
    warn_count = sum(1 for finding in findings if finding.get("status") == "warn")
    closeout_ready_count = sum(
        1 for inspection in bundle_inspections if inspection.get("closeout_ready") is True
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "repo_root": str(repo_root),
        "status": "fail" if fail_count else ("warn" if warn_count else "pass"),
        "summary": {
            "selected_serious_count": len(bundle_inspections),
            "closeout_ready_count": closeout_ready_count,
            "finding_count": len(findings),
            "fail_count": fail_count,
            "warn_count": warn_count,
        },
        "bundle_inspections": bundle_inspections,
        "findings": findings,
    }


def dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _inspect_target(target: Mapping[str, Any]) -> dict[str, Any]:
    profile = str(target.get("profile") or "unknown")
    lane_id = str(target.get("lane_id") or "")
    status = str(target.get("status") or "unknown")
    bundle_path = target.get("bundle_path")

    if status != "passed":
        return _inspect_non_ready_target(target)

    if not isinstance(bundle_path, Path) or not bundle_path.exists():
        return {
            "lane_id": lane_id or None,
            "profile": profile,
            "status": status,
            "bundle_path": str(bundle_path) if isinstance(bundle_path, Path) else None,
            "closeout_ready": False,
            "setup_evidence": None,
            "components": [],
            "findings": [
                _finding(
                    "phase64_selected_serious_bundle_missing",
                    "Selected serious lane passed but no readable evidence bundle was attached.",
                )
            ],
        }

    payloads = _load_bundle_payloads(bundle_path)
    component_rows = _component_rows(bundle_path, payloads)
    findings = [
        _finding(
            "phase64_component_missing",
            f"Evidence bundle is missing Phase 6.4 component: {row['component_id']}.",
            evidence_refs=row["evidence_refs"],
        )
        for row in component_rows
        if row["status"] == "fail"
    ]
    findings.extend(_public_leak_findings(bundle_path))
    findings.extend(_public_export_truth_findings(bundle_path, payloads))
    findings.extend(_authority_envelope_ownership_findings(payloads))
    findings.extend(_residual_spine_boundary_findings(payloads))

    bundle = payloads.get("bundle")
    scorecard = payloads.get("scorecard")
    scorecard_status = _status_from_payload(scorecard, "quality_status")
    bundle_quality_status = _status_from_payload(bundle, "quality_status")
    operator_triage_ledger = _operator_triage_ledger_from_scorecard(scorecard)
    if scorecard_status and scorecard_status not in PASSING_BUNDLE_STATUSES:
        findings.append(
            _finding(
                "phase64_scorecard_not_pass",
                "Selected serious evidence bundle scorecard is not pass.",
                evidence_refs=["quality_evidence/quality_scorecard.json"],
            )
        )
        findings.extend(_operator_triage_ledger_findings(operator_triage_ledger))
    if bundle_quality_status and bundle_quality_status not in PASSING_BUNDLE_STATUSES:
        findings.append(
            _finding(
                "phase64_bundle_quality_status_not_pass",
                "Selected serious evidence bundle quality_status is not pass.",
                evidence_refs=["bundle.json"],
            )
        )
    return {
        "lane_id": lane_id or _lane_id_from_bundle(bundle),
        "profile": profile if profile != "unknown" else _profile_from_bundle(bundle),
        "status": status,
        "bundle_path": str(bundle_path),
        "closeout_ready": not any(finding["status"] == "fail" for finding in findings),
        "setup_evidence": None,
        "operator_triage_ledger": operator_triage_ledger,
        "components": component_rows,
        "findings": findings,
    }


def _inspect_non_ready_target(target: Mapping[str, Any]) -> dict[str, Any]:
    profile = str(target.get("profile") or "unknown")
    lane_id = str(target.get("lane_id") or "")
    status = str(target.get("status") or "unknown")
    setup_evidence = target.get("setup_evidence")
    findings: list[dict[str, Any]] = []

    if profile in SETUP_EVIDENCE_PROFILES:
        if not _typed_setup_evidence_present(setup_evidence):
            findings.append(
                _finding(
                    "phase64_typed_setup_evidence_missing",
                    (
                        "Non-ready governed/production lanes must carry typed setup "
                        "evidence and cannot be counted as closeout-ready."
                    ),
                )
            )
    else:
        findings.append(_matrix_lane_not_passed_finding(target))

    return {
        "lane_id": lane_id or None,
        "profile": profile,
        "status": status,
        "bundle_path": None,
        "closeout_ready": False,
        "setup_evidence": setup_evidence if isinstance(setup_evidence, Mapping) else None,
        "matrix_failure_envelope": (
            dict(setup_evidence) if isinstance(setup_evidence, Mapping) else None
        ),
        "components": [],
        "findings": findings,
    }


def _matrix_lane_not_passed_finding(target: Mapping[str, Any]) -> dict[str, Any]:
    failure = target.get("setup_evidence")
    if not isinstance(failure, Mapping):
        return _finding(
            "phase64_selected_serious_bundle_not_ready",
            "Selected serious lane is non-ready and has no inspectable bundle.",
        )
    code = str(failure.get("code") or "unknown").strip() or "unknown"
    owner = str(failure.get("owner") or "runtime-quality").strip() or "runtime-quality"
    root_cause_class = (
        str(failure.get("root_cause_class") or failure.get("type") or "runtime_lane_failure")
        .strip()
        or "runtime_lane_failure"
    )
    next_action = (
        str(failure.get("next_action") or "Inspect the emitted matrix failure envelope.")
        .strip()
        or "Inspect the emitted matrix failure envelope."
    )
    finding = _finding(
        "phase64_matrix_lane_not_passed",
        (
            "Selected serious lane did not pass; preserving matrix failure "
            f"envelope code {code} for operator triage."
        ),
    )
    finding.update(
        {
            "failure_envelope_code": code,
            "owner": owner,
            "root_cause_class": root_cause_class,
            "next_action": next_action,
        }
    )
    return finding


def _component_rows(root: Path, payloads: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for component_id, evidence_refs, predicate in REQUIRED_COMPONENTS:
        passed = predicate(root, payloads)
        rows.append(
            {
                "component_id": component_id,
                "status": "pass" if passed else "fail",
                "evidence_refs": list(evidence_refs),
            }
        )
    return rows


def _operator_triage_ledger_from_scorecard(scorecard: Any) -> dict[str, Any] | None:
    if not isinstance(scorecard, Mapping):
        return None
    ledger = scorecard.get("operator_triage_ledger")
    if isinstance(ledger, Mapping):
        return dict(ledger)
    return None


def _operator_triage_ledger_findings(
    ledger: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if ledger is None:
        return [
            _finding(
                "phase64_operator_triage_ledger_missing",
                (
                    "Failed serious scorecards must include an operator triage ledger "
                    "with the first failing producer artifact."
                ),
                evidence_refs=["quality_evidence/quality_scorecard.json"],
            )
        ]
    root_causes = ledger.get("root_causes")
    if ledger.get("schema_version") != "policyos.operator_triage_ledger.v1" or not isinstance(
        root_causes,
        list,
    ):
        return [
            _finding(
                "phase64_operator_triage_ledger_missing",
                "Operator triage ledger is not scorecard-reader compatible.",
                evidence_refs=["quality_evidence/quality_scorecard.json"],
            )
        ]
    missing = []
    for index, row in enumerate(root_causes):
        if not isinstance(row, Mapping):
            missing.append(f"root_causes[{index}]")
            continue
        for key in ("owner", "root_cause_class", "first_failing_artifact_ref", "next_action"):
            if not _non_empty(row.get(key)):
                missing.append(f"root_causes[{index}].{key}")
    if missing:
        return [
            _finding(
                "phase64_operator_triage_ledger_missing",
                (
                    "Operator triage ledger is missing required first-failing-producer "
                    f"fields: {', '.join(missing[:5])}."
                ),
                evidence_refs=["quality_evidence/quality_scorecard.json"],
            )
        ]
    return []


def _authority_envelope_ownership_findings(
    payloads: Mapping[str, Any],
) -> list[dict[str, Any]]:
    quality_reports = payloads.get("quality_reports")
    if not isinstance(quality_reports, Mapping):
        return []
    report_key_by_filename = {
        filename: report_key for report_key, filename in QUALITY_REPORT_FILES.items()
    }
    findings: list[dict[str, Any]] = []
    for filename, report in quality_reports.items():
        if not isinstance(filename, str) or not isinstance(report, Mapping):
            continue
        envelope = report.get("authority_envelope")
        if not isinstance(envelope, Mapping):
            continue
        report_key = report_key_by_filename.get(filename)
        if not report_key:
            continue
        ref_key = QUALITY_REPORT_RUNTIME_REFS.get(report_key)
        runtime_ref = str(report.get(ref_key) or "").strip() if ref_key else ""
        issues = authority_envelope_ownership_issues(
            envelope=envelope,
            report_key=report_key,
            report=report,
            ref_key=ref_key,
            runtime_ref=runtime_ref or None,
        )
        if not issues:
            continue
        findings.append(
            _finding(
                "hds_borrowed_authority_envelope",
                (
                    "Evidence bundle report carries an authority envelope owned by "
                    "a different report kind."
                ),
                evidence_refs=[f"quality_evidence/{filename}"],
            )
        )
    return findings


def _residual_spine_boundary_findings(
    payloads: Mapping[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for boundary, evidence_ref in (
        (
            _data_forge_snapshot_boundary_record(payloads),
            f"quality_evidence/{DATA_FORGE_SNAPSHOT_BINDING_FILE}",
        ),
        (
            _scholar_academic_boundary_record(payloads),
            f"quality_evidence/{SCHOLAR_ACADEMIC_EVIDENCE_FILENAME}",
        ),
        (
            _concept_spine_boundary_record(payloads),
            "quality_evidence/policy_design_case.json#/concept_spine",
        ),
        (
            _jurisdiction_spine_boundary_record(payloads),
            "quality_evidence/policy_design_case.json#/jurisdiction_spine",
        ),
    ):
        status = str(boundary.get("status") or "").strip().casefold()
        if status == "pass":
            continue
        issues = _boundary_issues(boundary)
        blockers = _boundary_blockers(boundary)
        if not issues and blockers:
            issues = [
                {
                    "code": str(blocker.get("code") or f"{boundary.get('record_id')}_blocked"),
                    "message": str(
                        blocker.get("message")
                        or f"Residual evidence boundary is blocked: {boundary.get('record_id')}."
                    ),
                }
                for blocker in blockers
            ]
        if not issues:
            issues = [
                {
                    "code": f"{boundary.get('record_id') or 'residual_boundary'}_invalid",
                    "message": (
                        "Residual evidence boundary did not pass and emitted no typed "
                        "issue."
                    ),
                }
            ]
        for issue in issues:
            findings.append(
                _finding(
                    str(issue.get("code") or "residual_spine_boundary_failed"),
                    str(
                        issue.get("message")
                        or "Residual evidence boundary is missing, failed, or blocked."
                    ),
                    evidence_refs=[evidence_ref],
                )
            )
    return findings


def _data_forge_snapshot_boundary_status(payloads: Mapping[str, Any]) -> str:
    return str(_data_forge_snapshot_boundary_record(payloads).get("status") or "")


def _scholar_academic_boundary_status(payloads: Mapping[str, Any]) -> str:
    return str(_scholar_academic_boundary_record(payloads).get("status") or "")


def _concept_spine_boundary_status(payloads: Mapping[str, Any]) -> str:
    return str(_concept_spine_boundary_record(payloads).get("status") or "")


def _jurisdiction_spine_boundary_status(payloads: Mapping[str, Any]) -> str:
    return str(_jurisdiction_spine_boundary_record(payloads).get("status") or "")


def _data_forge_snapshot_boundary_record(payloads: Mapping[str, Any]) -> dict[str, Any]:
    report = _quality_report_payload(payloads, DATA_FORGE_SNAPSHOT_BINDING_FILE)
    normalized = normalize_data_forge_snapshot_binding_report(
        report if isinstance(report, Mapping) else None
    )
    status = str(normalized.get("status") or "").strip().casefold()
    return {
        "record_id": "data_forge_snapshot_binding",
        "status": status,
        "issues": _boundary_issues(normalized),
        "blockers": _boundary_blockers(normalized),
    }


def _scholar_academic_boundary_record(payloads: Mapping[str, Any]) -> dict[str, Any]:
    report = _quality_report_payload(payloads, SCHOLAR_ACADEMIC_EVIDENCE_FILENAME)
    return build_scholar_academic_evidence_boundary_record(
        report if isinstance(report, Mapping) else None
    )


def _concept_spine_boundary_record(payloads: Mapping[str, Any]) -> dict[str, Any]:
    case_payload = _policy_design_case_payload(payloads)
    return build_policy_design_concept_spine_boundary_record(
        _concept_spine_payload(case_payload) if isinstance(case_payload, Mapping) else None
    )


def _jurisdiction_spine_boundary_record(payloads: Mapping[str, Any]) -> dict[str, Any]:
    case_payload = _policy_design_case_payload(payloads)
    jurisdiction = (
        case_payload.get("jurisdiction_spine")
        if isinstance(case_payload, Mapping)
        else None
    )
    return build_policy_design_jurisdiction_spine_boundary_record(
        jurisdiction if isinstance(jurisdiction, Mapping) else None
    )


def _policy_design_case_payload(payloads: Mapping[str, Any]) -> Mapping[str, Any] | None:
    payload = _quality_report_payload(payloads, "policy_design_case.json")
    return payload if isinstance(payload, Mapping) else None


def _concept_spine_payload(case_payload: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(case_payload, Mapping):
        return None
    direct = case_payload.get("concept_spine")
    if isinstance(direct, Mapping):
        return direct
    nodes = case_payload.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if isinstance(node, Mapping) and str(node.get("node_type") or "") == "concept_spine":
                return node
    return None


def _quality_report_payload(payloads: Mapping[str, Any], filename: str) -> Any:
    quality_reports = payloads.get("quality_reports")
    if not isinstance(quality_reports, Mapping):
        return None
    return quality_reports.get(filename)


def _boundary_issues(boundary: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues = boundary.get("issues")
    if not isinstance(issues, list):
        return []
    return [dict(issue) for issue in issues if isinstance(issue, Mapping)]


def _boundary_blockers(boundary: Mapping[str, Any]) -> list[dict[str, Any]]:
    blockers = boundary.get("blockers")
    if not isinstance(blockers, list):
        return []
    return [dict(blocker) for blocker in blockers if isinstance(blocker, Mapping)]


def _public_leak_findings(root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    public_paths = [
        root / "quality_evidence/public_export_bundle.json",
        root / "request.sanitized.json",
        root / "env.sanitized.json",
    ]
    for path in public_paths:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        payload = _load_json_text_or_none(text)
        values = (
            _iter_public_string_values(payload)
            if payload is not None
            else (("$", text),)
        )
        for value_path, value in values:
            lowered = value.casefold()
            for token in FORBIDDEN_PUBLIC_TOKENS:
                if token in lowered:
                    findings.append(
                        _finding(
                            "phase64_public_bundle_leak",
                            (
                                "Public bundle file contains forbidden token "
                                f"{token} at {value_path}."
                            ),
                            evidence_refs=[_relative_to(root, path)],
                        )
                    )
            for marker in UNSAFE_PUBLIC_PATH_MARKERS:
                if marker in lowered:
                    findings.append(
                        _finding(
                            "phase64_public_bundle_leak",
                            (
                                "Public bundle file contains unsafe path marker "
                                f"{marker} at {value_path}."
                            ),
                            evidence_refs=[_relative_to(root, path)],
                        )
                    )
    return findings


def _public_export_truth_findings(
    root: Path,
    payloads: Mapping[str, Any],
) -> list[dict[str, Any]]:
    path = root / "quality_evidence" / "public_export_bundle.json"
    if not path.is_file():
        return []
    public_export = _load_json_or_none(path)
    if not isinstance(public_export, Mapping):
        return []

    findings: list[dict[str, Any]] = []
    authority_role = str(public_export.get("authority_role") or "").casefold()
    evidence_class = str(public_export.get("evidence_class") or "").casefold()
    provenance_kind = str(public_export.get("provenance_kind") or "").casefold()
    if (
        authority_role not in {"projection_only", "not_authoritative"}
        or evidence_class != "redacted_derived"
        or provenance_kind in {"runtime_emitted", "runtime_attested", "producer_emitted"}
    ):
        findings.append(
            _finding(
                "phase64_public_export_authority_boundary",
                "Public export is shaped like authority-bearing evidence.",
                evidence_refs=["quality_evidence/public_export_bundle.json"],
            )
        )

    limits = public_export.get("official_use_limits")
    disallowed = (
        {
            str(item)
            for item in limits.get("may_not_be_used_for", [])
            if str(item).strip()
        }
        if isinstance(limits, Mapping)
        else set()
    )
    required_limits = {
        "approval_authority",
        "runtime_closeout_authority",
        "scorecard_authority",
    }
    if not isinstance(limits, Mapping) or limits.get("official_use") != "public_audit_only":
        findings.append(
            _finding(
                "phase64_public_export_authority_boundary",
                "Public export is missing public-audit-only official-use limits.",
                evidence_refs=["quality_evidence/public_export_bundle.json"],
            )
        )
    elif not required_limits <= disallowed:
        findings.append(
            _finding(
                "phase64_public_export_authority_boundary",
                "Public export official-use limits do not forbid authority reuse.",
                evidence_refs=["quality_evidence/public_export_bundle.json"],
            )
        )

    source_status = _status_from_payload(payloads.get("scorecard"), "quality_status")
    if not source_status:
        source_status = _status_from_payload(payloads.get("bundle"), "quality_status")
    projected_status = _public_export_projected_scorecard_status(public_export)
    if source_status and projected_status and source_status != projected_status:
        findings.append(
            _finding(
                "phase64_public_export_truth_mismatch",
                (
                    "Public export quality scorecard summary does not preserve "
                    f"runtime scorecard status {source_status}."
                ),
                evidence_refs=[
                    "quality_evidence/public_export_bundle.json",
                    "quality_evidence/quality_scorecard.json",
                ],
            )
        )
    return findings


def _public_export_projected_scorecard_status(public_export: Mapping[str, Any]) -> str:
    artifacts = public_export.get("artifacts")
    if not isinstance(artifacts, Mapping):
        return ""
    summary = artifacts.get("quality_scorecard_summary")
    if not isinstance(summary, Mapping):
        return ""
    return str(summary.get("quality_status") or "").strip().casefold()


def _selected_inspection_targets(
    *,
    repo_root: Path,
    bundle_dirs: Sequence[Path],
    matrix_run_payload: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []

    for raw_dir in bundle_dirs:
        bundle_dir = raw_dir if raw_dir.is_absolute() else repo_root / raw_dir
        bundle = _load_json_or_none(bundle_dir / "bundle.json")
        profile = _profile_from_bundle(bundle)
        if profile not in SERIOUS_PROFILES:
            continue
        targets.append(
            {
                "lane_id": _lane_id_from_bundle(bundle),
                "profile": profile,
                "status": "passed",
                "bundle_path": bundle_dir,
                "setup_evidence": None,
            }
        )

    if matrix_run_payload is None:
        return targets

    for lane in _matrix_lanes(matrix_run_payload):
        lane_id = str(lane.get("lane_id") or "")
        profile = str(lane.get("profile") or _profile_from_lane_id(lane_id))
        if profile not in SERIOUS_PROFILES:
            continue
        result_status = str(lane.get("status") or "")
        bundle_path_raw = lane.get("bundle_path")
        bundle_path = (
            Path(str(bundle_path_raw)).expanduser()
            if isinstance(bundle_path_raw, str) and bundle_path_raw.strip()
            else None
        )
        if bundle_path is not None and not bundle_path.is_absolute():
            bundle_path = repo_root / bundle_path
        targets.append(
            {
                "lane_id": lane_id,
                "profile": profile,
                "status": result_status,
                "bundle_path": bundle_path,
                "setup_evidence": lane.get("failure_envelope"),
            }
        )
    return targets


def _matrix_lanes(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    lanes = payload.get("lanes")
    if not isinstance(lanes, list):
        return []
    return [lane for lane in lanes if isinstance(lane, Mapping)]


def _load_matrix_payload(
    repo_root: Path,
    payload: Mapping[str, Any] | None,
    path: Path | None,
) -> Mapping[str, Any] | None:
    if payload is not None:
        return payload
    if path is None:
        return None
    matrix_path = path if path.is_absolute() else repo_root / path
    loaded = _load_json_or_none(matrix_path)
    if not isinstance(loaded, Mapping):
        raise EvidenceBundleInspectionInputError(
            f"matrix run JSON is missing or invalid: {matrix_path}"
        )
    return loaded


def _load_bundle_payloads(root: Path) -> dict[str, Any]:
    quality_reports: dict[str, Any] = {}
    quality_dir = root / "quality_evidence"
    if quality_dir.exists():
        for path in sorted(quality_dir.glob("*.json")):
            quality_reports[path.name] = _load_json_or_none(path)
    return {
        "bundle": _load_json_or_none(root / "bundle.json"),
        "job": _load_json_or_none(root / "job.json"),
        "run": _load_json_or_none(root / "run.json"),
        "artifacts": _load_json_or_none(root / "artifacts.json"),
        "scorecard": _load_json_or_none(quality_dir / "quality_scorecard.json"),
        "quality_reports": quality_reports,
        "cas_manifest": _load_json_or_none(
            root / "cas_manifests" / "quality_artifact_ownership.manifest.json"
        ),
    }


def _json_file_has_schema(root: Path, rel_path: str, schema_version: str) -> bool:
    payload = _load_json_or_none(root / rel_path)
    return isinstance(payload, Mapping) and payload.get("schema_version") == schema_version


def _cas_manifest_has_producer_governance(root: Path) -> bool:
    payload = _load_json_or_none(
        root / "cas_manifests" / "quality_artifact_ownership.manifest.json"
    )
    return (
        isinstance(payload, Mapping)
        and isinstance(payload.get("producer"), Mapping)
        and isinstance(payload.get("governance"), Mapping)
    )


def _has_diagnostic_events(payloads: Mapping[str, Any]) -> bool:
    for value in _nested_find_all(payloads, "diagnostic_events"):
        if isinstance(value, list) and any(isinstance(item, Mapping) for item in value):
            return True
        if isinstance(value, Mapping):
            return True
    for value in _nested_find_all(payloads, "diagnostic_event"):
        if isinstance(value, Mapping):
            return True
    return False


def _has_event_registry_version(payloads: Mapping[str, Any]) -> bool:
    for key in ("event_type_registry", "diagnostic_event_type_registry"):
        for value in _nested_find_all(payloads, key):
            if isinstance(value, Mapping) and (
                _non_empty(value.get("version"))
                or _non_empty(value.get("registry_version"))
            ):
                return True
    return False


def _has_schema_compatibility_decisions(payloads: Mapping[str, Any]) -> bool:
    for value in _nested_find_all(payloads, "schema_compatibility_decisions"):
        if isinstance(value, Mapping) and value:
            return True
    for value in _nested_find_all(payloads, "schema_compatibility"):
        if isinstance(value, Mapping) and (
            _non_empty(value.get("decision")) or _non_empty(value.get("status"))
        ):
            return True
    return False


def _published_decision_lifecycle_in_scope(payloads: Mapping[str, Any]) -> bool:
    for value in _nested_find_all(payloads, "published_decision_lifecycle_in_scope"):
        if value is True:
            return True
    for value in _nested_find_all(payloads, "published_decision_lifecycle"):
        if isinstance(value, Mapping) and value:
            return True
    return False


def _has_any_nested_key(payload: Any, keys: Sequence[str]) -> bool:
    return any(_nested_find_all(payload, key) for key in keys)


def _nested_find_all(payload: Any, key: str) -> list[Any]:
    matches: list[Any] = []
    if isinstance(payload, Mapping):
        for current_key, value in payload.items():
            if current_key == key:
                matches.append(value)
            matches.extend(_nested_find_all(value, key))
    elif isinstance(payload, list):
        for value in payload:
            matches.extend(_nested_find_all(value, key))
    return matches


def _typed_setup_evidence_present(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    return (
        _non_empty(value.get("type"))
        and _non_empty(value.get("code"))
        and str(value.get("readiness_state") or "").strip() == "not_ready"
    )


def _status_from_payload(payload: Any, key: str) -> str:
    if not isinstance(payload, Mapping):
        return ""
    return str(payload.get(key) or payload.get("status") or "").strip().casefold()


def _profile_from_bundle(bundle: Any) -> str:
    if not isinstance(bundle, Mapping):
        return "unknown"
    canary_kind = str(bundle.get("canary_kind") or "").strip().casefold()
    if canary_kind:
        return canary_kind
    return _profile_from_lane_id(_lane_id_from_bundle(bundle) or "")


def _lane_id_from_bundle(bundle: Any) -> str | None:
    if not isinstance(bundle, Mapping):
        return None
    command = bundle.get("command")
    if not isinstance(command, Mapping):
        return None
    value = command.get("matrix_lane_id") or command.get("lane_id")
    return str(value) if value else None


def _profile_from_lane_id(lane_id: str) -> str:
    for part in lane_id.split("__"):
        if part.startswith("profile-"):
            return part.removeprefix("profile-")
    return "unknown"


def _finding(
    code: str,
    message: str,
    *,
    evidence_refs: Sequence[str] = (),
) -> dict[str, Any]:
    row: dict[str, Any] = {"status": "fail", "code": code, "message": message}
    if evidence_refs:
        row["evidence_refs"] = list(evidence_refs)
    return row


def _non_empty(value: Any) -> bool:
    return value not in (None, "", [], {})


def _relative_to(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _load_json_or_none(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _load_json_text_or_none(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _iter_public_string_values(payload: Any, *, path: str = "$") -> tuple[tuple[str, str], ...]:
    if _public_redaction_policy_path(path):
        return ()
    if isinstance(payload, str):
        return ((path, payload),)
    if isinstance(payload, Mapping):
        values: list[tuple[str, str]] = []
        for key, value in payload.items():
            values.extend(
                _iter_public_string_values(value, path=f"{path}.{key}")
            )
        return tuple(values)
    if isinstance(payload, list):
        values = []
        for index, value in enumerate(payload):
            values.extend(_iter_public_string_values(value, path=f"{path}[{index}]"))
        return tuple(values)
    return ()


def _public_redaction_policy_path(path: str) -> bool:
    return any(
        marker in path
        for marker in (
            ".official_use_limits",
            ".redaction_summary",
            ".redaction_policy",
            ".redaction_policy_ref",
            ".env_var",
        )
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--bundle-dir",
        action="append",
        type=Path,
        default=[],
        help="Selected serious evidence bundle directory to inspect.",
    )
    parser.add_argument(
        "--matrix-run-json",
        type=Path,
        help="Canary matrix run JSON whose selected serious lanes should be inspected.",
    )
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--require-passing", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    try:
        payload = build_evidence_bundle_inspection_report(
            repo_root=repo_root,
            bundle_dirs=args.bundle_dir,
            matrix_run_path=args.matrix_run_json,
        )
    except EvidenceBundleInspectionInputError as exc:
        sys.stderr.write(f"evidence bundle inspection failed: {exc}\n")
        return 2

    rendered = dump_json(payload)
    if args.json_output is not None:
        output = (
            args.json_output
            if args.json_output.is_absolute()
            else repo_root / args.json_output
        )
        atomic_write_text(output, rendered)
    else:
        sys.stdout.write(rendered)
    if args.require_passing and payload["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
