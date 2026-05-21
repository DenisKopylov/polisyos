#!/usr/bin/env python3
"""Run Policy Design Case Pass 2 Phase 34.5 diagnostics."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation.pass2_wave34_common import (
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_WAVE33_DIR,
    Pass2Wave34InputError,
    as_list,
    canonical_diagnostic,
    expect_mapping,
    load_wave33_context,
    write_phase_outputs,
)

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

PHASE_ID = "34.5"
PHASE_TITLE = "Phase 34.5 Operational And Recovery Diagnostics"
PHASE_FILE_STEM = "phase_34_5_operational_recovery_diagnostics"
SCHEMA_VERSION = "policyos.policy_design_case.pass2.phase34_5_diagnostic.v1"
INDEX_SCHEMA_VERSION = "policyos.policy_design_case.pass2.phase34_5_index.v1"
TOOL_NAME = "quality.validation.run-policy-design-case-pass2-phase34-5"

PDD_SPECS: dict[str, dict[str, str]] = {
    "PDD-046": {
        "pdd_id": "PDD-046",
        "slug": "operational_root_cause_completeness_audit",
        "title": "Audit Observability Root-Cause Completeness",
        "question": (
            "Can every failed closeout class be traced to owner, phase, missing input, "
            "upstream cause, downstream impact, and next diagnostic command?"
        ),
    },
    "PDD-077": {
        "pdd_id": "PDD-077",
        "slug": "backup_restore_drill_evidence_audit",
        "title": "Audit Backup, Restore, And Disaster-Recovery Drill Evidence",
        "question": (
            "Does the Wave 33 bundle prove retained copies, restore drills, chain of "
            "custody, and restored artifact-family verification?"
        ),
    },
    "PDD-078": {
        "pdd_id": "PDD-078",
        "slug": "resource_exhaustion_semantics_audit",
        "title": "Audit Resource Quota, Rate-Limit, And Cost-Exhaustion Semantics",
        "question": (
            "Are quota, rate-limit, timeout, memory, byte, token, cost, and queue "
            "exhaustion states bound to downstream evidence and claim impact?"
        ),
    },
    "PDD-090": {
        "pdd_id": "PDD-090",
        "slug": "realtime_cursor_replay_polling_parity_audit",
        "title": "Audit Realtime SSE/WebSocket Cursor, Replay, And Polling Parity",
        "question": (
            "Do live stream, cursor replay, reconnect, fallback, and polling surfaces "
            "prove parity with the authoritative read model?"
        ),
    },
    "PDD-104": {
        "pdd_id": "PDD-104",
        "slug": "archive_grade_reproducibility_audit",
        "title": "Audit Archive-Grade Reproducibility And Long-Term Verification",
        "question": (
            "Can the decision be reproduced and verified years later from archive-grade "
            "legal, data, model, provider, source, schema, lockfile, signature, and "
            "restore evidence?"
        ),
    },
}


def build_phase34_5_diagnostics(
    *,
    repo_root: Path = REPO_ROOT,
    wave33_dir: Path = DEFAULT_WAVE33_DIR,
) -> tuple[dict[str, Any], Mapping[str, Any]]:
    context = load_wave33_context(repo_root=repo_root, wave33_dir=wave33_dir)
    diagnostics = {
        "PDD-046": _diagnose_pdd_046(context),
        "PDD-077": _diagnose_pdd_077(context),
        "PDD-078": _diagnose_pdd_078(context),
        "PDD-090": _diagnose_pdd_090(context),
        "PDD-104": _diagnose_pdd_104(context),
    }
    return diagnostics, context


def write_phase34_5_outputs(
    *,
    repo_root: Path = REPO_ROOT,
    wave33_dir: Path = DEFAULT_WAVE33_DIR,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> tuple[dict[str, Any], list[Path]]:
    diagnostics, context = build_phase34_5_diagnostics(
        repo_root=repo_root,
        wave33_dir=wave33_dir,
    )
    return write_phase_outputs(
        diagnostics=diagnostics,
        specs=PDD_SPECS,
        repo_root=repo_root,
        output_root=output_root,
        phase=PHASE_ID,
        phase_title=PHASE_TITLE,
        phase_file_stem=PHASE_FILE_STEM,
        index_schema_version=INDEX_SCHEMA_VERSION,
        tool_name=TOOL_NAME,
        context=context,
    )


def _diagnose_pdd_046(context: Mapping[str, Any]) -> dict[str, Any]:
    wave_files = expect_mapping(context.get("wave_files"), "wave_files")
    scorecard = expect_mapping(
        wave_files.get("quality_scorecard.json"),
        "quality_scorecard",
        required=False,
    )
    readiness = expect_mapping(
        wave_files.get("readiness.json"),
        "readiness",
        required=False,
    )
    findings = [
        {
            "code": "operator_diagnostic_command_list_missing",
            "severity": "high",
            "summary": (
                "The top-level job record does not provide a single operator diagnostic "
                "object or next diagnostic command list for failed closeout."
            ),
            "evidence": "job.json",
        },
        {
            "code": "scorecard_failure_breadcrumb_fields_partial",
            "severity": "high",
            "summary": (
                "Many scorecard gates expose layer and next action but not a complete "
                "owner, missing input, upstream cause, downstream impact, and command chain."
            ),
            "evidence": "_build/policy-design-case/rebaseline/wave-33/quality_scorecard.json",
        },
        {
            "code": "failed_classes_not_normalized_to_first_missing_producer",
            "severity": "blocker",
            "summary": (
                "Lex, Fabric, Foundry, decision-artifact, Scholar, and record-family "
                "failures are not normalized into a full breadcrumb chain."
            ),
            "evidence": "_build/policy-design-case/rebaseline/wave-33/readiness.json",
        },
        {
            "code": "orphan_diagnostic_event_root_cause_chain_missing",
            "severity": "high",
            "summary": (
                "Runtime diagnostic event reconciliation failures identify orphan refs "
                "but not the owner-to-first-missing-producer path for each orphan."
            ),
            "evidence": "quality_evidence/quality_scorecard.json",
        },
        {
            "code": "timeline_not_joined_to_scorecard_first_cause",
            "severity": "medium",
            "summary": (
                "Runtime timeline events and artifact refs are not joined back to "
                "scorecard failure rows as first-cause breadcrumbs."
            ),
            "evidence": "timeline.json",
        },
    ]
    evidence = {
        "readiness_minimum_closeout_failure_count": len(
            as_list(readiness.get("minimum_closeout_gate_failures"))
        ),
        "scorecard_quality_gate_count": len(as_list(scorecard.get("quality_gates"))),
        "representative_failed_classes": _representative_codes(scorecard, readiness),
        "job_operator_diagnostic": None,
        "job_next_diagnostic_commands": [],
    }
    return canonical_diagnostic(
        context=context,
        spec=PDD_SPECS["PDD-046"],
        tool_name=TOOL_NAME,
        schema_version=SCHEMA_VERSION,
        phase=PHASE_ID,
        verdict="confirmed_partial_root_cause_breadcrumbs_missing_for_quality_failures",
        acceptance_gate_status="failed",
        findings=findings,
        evidence=evidence,
        recommended_gate=(
            "Fail serious closeout when any failed scorecard/readiness row cannot be "
            "normalized into owner, phase, missing input, upstream cause, downstream "
            "impact, authoritative producer, evidence refs, and next command."
        ),
        backlog_summary=(
            "Wave 33 has useful failure breadcrumbs, but they are partial and split "
            "across readiness, scorecard, job, and timeline surfaces. PDD-046 remains "
            "failed until every failure class has a complete root-cause index."
        ),
        recommended_remediation_id="PDD-046-A1",
    )


def _diagnose_pdd_077(context: Mapping[str, Any]) -> dict[str, Any]:
    quality_files = expect_mapping(context.get("quality_files"), "quality_files")
    replay = expect_mapping(
        quality_files.get("replay_manifest.json"),
        "replay_manifest",
        required=False,
    )
    provenance = expect_mapping(
        quality_files.get("evidence_provenance_manifest.json"),
        "evidence_provenance_manifest",
        required=False,
    )
    findings = [
        _gap("restore_drill_report_missing", "restore drill bundle"),
        _gap("retained_copy_archive_hash_verification_missing", "retained copy and archive hash verification"),
        _gap("corruption_injection_recovery_result_missing", "corruption injection and recovery result"),
        _gap("restored_dashboard_verification_missing", "restored dashboard verification"),
        _gap("restored_lineage_verification_missing", "restored lineage verification"),
        _gap("restored_scorecard_verification_missing", "restored scorecard verification"),
        _gap("restored_final_artifact_verification_missing", "restored final-artifact verification"),
    ]
    evidence = {
        "replay_manifest_status": replay.get("status"),
        "provenance_file_count": len(as_list(provenance.get("files"))),
        "restore_drill_report_present": False,
        "chain_of_custody_present": False,
    }
    return canonical_diagnostic(
        context=context,
        spec=PDD_SPECS["PDD-077"],
        tool_name=TOOL_NAME,
        schema_version=SCHEMA_VERSION,
        phase=PHASE_ID,
        verdict="confirmed_restore_drill_evidence_missing_from_wave33_bundle",
        acceptance_gate_status="failed",
        findings=findings,
        evidence=evidence,
        recommended_gate=(
            "Require a Wave-owned restore drill report with retained-copy refs, archive "
            "hashes, corruption injection, chain of custody, and restored dashboard, "
            "lineage, scorecard, and final-artifact verification."
        ),
        backlog_summary=(
            "Wave 33 packages hashes, provenance, and replay refs, but those are not "
            "restore-drill evidence. PDD-077 remains failed because no retained-copy, "
            "chain-of-custody, or artifact-family restore verification exists."
        ),
        recommended_remediation_id="PDD-077-A1",
    )


def _diagnose_pdd_078(context: Mapping[str, Any]) -> dict[str, Any]:
    quality_files = expect_mapping(context.get("quality_files"), "quality_files")
    budget = expect_mapping(
        quality_files.get("canary_performance_budget.json"),
        "canary_performance_budget",
        required=False,
    )
    replay = expect_mapping(
        quality_files.get("replay_manifest.json"),
        "replay_manifest",
        required=False,
    )
    findings = [
        _gap("resource_exhaustion_ledger_missing", "resource-exhaustion ledger"),
        _gap("typed_resource_limit_markers_missing", "rate limit, circuit, timeout, byte, token, cost, memory, and queue markers"),
        _gap("resource_exhaustion_claim_impact_mapping_missing", "downstream claim and scorecard impact mapping"),
        _gap("partial_evidence_negative_scenarios_missing", "partial-evidence negative scenarios"),
        _gap("resource_exhaustion_degradation_ledger_missing", "degradation ledger binding"),
    ]
    evidence = {
        "performance_budget_status": budget.get("status"),
        "performance_budget_phase_count": len(as_list(budget.get("phases"))),
        "replay_manifest_degradation_ledger": replay.get("degradation_ledger"),
        "resource_exhaustion_ledger_present": False,
    }
    return canonical_diagnostic(
        context=context,
        spec=PDD_SPECS["PDD-078"],
        tool_name=TOOL_NAME,
        schema_version=SCHEMA_VERSION,
        phase=PHASE_ID,
        verdict="confirmed_resource_exhaustion_negative_scenarios_not_bound_to_wave33_closeout",
        acceptance_gate_status="failed",
        findings=findings,
        evidence=evidence,
        recommended_gate=(
            "Require a resource-exhaustion ledger with typed rate-limit, circuit, "
            "timeout, byte, token, cost, memory, queue, partial-evidence, claim-impact, "
            "scorecard-impact, limitation, and blocker rows."
        ),
        backlog_summary=(
            "Wave 33 has performance and cost budget evidence, but no resource "
            "exhaustion negative scenario or claim-impact ledger. PDD-078 remains "
            "failed until partial evidence is downgraded or blocked by typed resource limits."
        ),
        recommended_remediation_id="PDD-078-A1",
    )


def _diagnose_pdd_090(context: Mapping[str, Any]) -> dict[str, Any]:
    findings = [
        _gap("live_polling_parity_ledger_missing", "live/polling parity ledger"),
        _gap("server_cursor_replay_not_proven", "cursor replay semantics"),
        _gap("snapshot_hash_trail_missing", "snapshot hash trail"),
        _gap("dropped_reordered_reconnect_evidence_missing", "dropped/reordered/reconnect scenarios"),
        _gap("governance_terminal_state_parity_missing", "governance wait and terminal-state parity"),
        _gap("transport_fallback_explanation_missing", "operator-visible degraded/fallback explanation"),
    ]
    evidence = {
        "source_observations": [
            {
                "surface": "src/polisyos/runtime/http/routes/runs.py",
                "observation": (
                    "SSE endpoints accept a cursor, but Wave 33 does not persist a "
                    "cursor replay proof or read-model snapshot hash."
                ),
            },
            {
                "surface": "apps/runtime-dashboard/src/app/providers/RunsLiveProvider.tsx",
                "observation": (
                    "Client reconnect and polling fallback behavior exists, but no "
                    "Wave 33 parity ledger binds it to authoritative state."
                ),
            },
        ],
        "live_polling_parity_ledger_present": False,
    }
    return canonical_diagnostic(
        context=context,
        spec=PDD_SPECS["PDD-090"],
        tool_name=TOOL_NAME,
        schema_version=SCHEMA_VERSION,
        phase=PHASE_ID,
        verdict="confirmed_realtime_cursor_replay_polling_parity_not_proven",
        acceptance_gate_status="failed",
        findings=findings,
        evidence=evidence,
        recommended_gate=(
            "Require a live/polling parity ledger with stream endpoint, polling "
            "endpoint, cursors, event ids, snapshot hashes, reconnect/drop/reorder "
            "scenarios, terminal-state parity, and fallback explanation."
        ),
        backlog_summary=(
            "Runtime and dashboard live-stream primitives exist, but Wave 33 does not "
            "prove parity between live views, cursor replay, reconnect behavior, and "
            "the authoritative read model. PDD-090 remains failed."
        ),
        recommended_remediation_id="PDD-090-A1",
    )


def _diagnose_pdd_104(context: Mapping[str, Any]) -> dict[str, Any]:
    quality_files = expect_mapping(context.get("quality_files"), "quality_files")
    replay = expect_mapping(
        quality_files.get("replay_manifest.json"),
        "replay_manifest",
        required=False,
    )
    drift = expect_mapping(
        quality_files.get("drift_explanation.json"),
        "drift_explanation",
        required=False,
    )
    public_export = expect_mapping(
        quality_files.get("public_export_bundle.json"),
        "public_export_bundle",
        required=False,
    )
    findings = [
        _gap("archive_grade_decision_bundle_missing", "archive-grade decision bundle"),
        _gap("long_term_snapshot_set_incomplete", "legal/data/model/provider/source/version/trust-store snapshots"),
        _gap("durable_verifier_timestamp_signature_lockfile_missing", "verifier, timestamp, signature, lockfile, schema, and redaction refs"),
        _gap("long_horizon_restore_replay_drill_missing", "long-horizon restore/replay drill evidence"),
        _gap("decision_bound_retention_jurisdiction_missing", "retention jurisdiction"),
        _gap("durable_replay_inputs_incomplete", "deterministic replay or typed bounded drift explanation"),
    ]
    evidence = {
        "replay_manifest_status": replay.get("status"),
        "git_sha": replay.get("git_sha"),
        "dependency_fingerprint_count": len(
            expect_mapping(
                replay.get("dependency_fingerprints"),
                "dependency_fingerprints",
                required=False,
            )
        ),
        "drift_status": drift.get("status"),
        "public_export_authority_role": public_export.get("authority_role"),
        "archive_grade_decision_bundle_present": False,
    }
    return canonical_diagnostic(
        context=context,
        spec=PDD_SPECS["PDD-104"],
        tool_name=TOOL_NAME,
        schema_version=SCHEMA_VERSION,
        phase=PHASE_ID,
        verdict="confirmed_archive_grade_reproducibility_not_proven_for_wave33",
        acceptance_gate_status="failed",
        findings=findings,
        evidence=evidence,
        recommended_gate=(
            "Require archive-grade decision bundles with legal/data/model/provider/source "
            "snapshots, schema bundle, lockfiles, trust-store snapshot, verifier, timestamp "
            "authority, signature verification, redaction refs, retention jurisdiction, "
            "restore procedure, replay drill, and bounded-drift evidence."
        ),
        backlog_summary=(
            "Wave 33 records replay, drift, provenance, public export, and attestation "
            "evidence, but not an archive-grade decision bundle. PDD-104 remains failed "
            "because long-term verification inputs and restore/replay drill evidence are incomplete."
        ),
        recommended_remediation_id="PDD-104-A1",
    )


def _gap(code: str, requirement: str) -> dict[str, str]:
    return {
        "code": code,
        "severity": "blocker",
        "summary": f"Wave 33 does not prove the required {requirement}.",
        "requirement": requirement,
        "evidence": "_build/policy-design-case/rebaseline/wave-33",
    }


def _representative_codes(
    scorecard: Mapping[str, Any],
    readiness: Mapping[str, Any],
) -> list[str]:
    codes: list[str] = []
    rows = [
        *as_list(scorecard.get("quality_gates")),
        *as_list(scorecard.get("blocking_quality_failures")),
        *as_list(readiness.get("minimum_closeout_gate_failures")),
    ]
    for row in rows:
        if isinstance(row, Mapping) and row.get("code"):
            value = str(row["code"])
            if value not in codes:
                codes.append(value)
    return codes[:12]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave33-dir", type=Path, default=DEFAULT_WAVE33_DIR)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload, written = write_phase34_5_outputs(
            repo_root=args.repo_root,
            wave33_dir=args.wave33_dir,
            output_root=args.output_root,
        )
    except Pass2Wave34InputError as exc:
        sys.stderr.write(f"{TOOL_NAME}: error: {exc}\n")
        return 2

    if args.json:
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    else:
        summary = payload["summary"]
        sys.stdout.write(
            f"{TOOL_NAME}: {payload['status']} "
            f"pdds={summary['pdd_count']} "
            f"failed_or_blocking={summary['failed_or_blocking_gate_count']} "
            f"written={len(written)}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
