#!/usr/bin/env python3
"""Run Policy Design Case Pass 2 Phase 34.6 diagnostics."""

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
    canonical_diagnostic,
    load_wave33_context,
    write_phase_outputs,
)

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

PHASE_ID = "34.6"
PHASE_TITLE = "Phase 34.6 Human-Facing, Legitimacy, And Memory Diagnostics"
PHASE_FILE_STEM = "phase_34_6_human_facing_legitimacy_memory_diagnostics"
SCHEMA_VERSION = "policyos.policy_design_case.pass2.phase34_6_diagnostic.v1"
INDEX_SCHEMA_VERSION = "policyos.policy_design_case.pass2.phase34_6_index.v1"
TOOL_NAME = "quality.validation.run-policy-design-case-pass2-phase34-6"

PDD_SPECS: dict[str, dict[str, str]] = {
    "PDD-034": {
        "pdd_id": "PDD-034",
        "slug": "dashboard_api_projection_consistency_audit",
        "title": "Audit Dashboard/API Semantic Projection Consistency",
        "question": (
            "Do dashboard and API projections faithfully reflect scorecard, approval "
            "packet, decision validity, lifecycle, and bundle authorities?"
        ),
    },
    "PDD-069": {
        "pdd_id": "PDD-069",
        "slug": "dashboard_operator_truthfulness_audit",
        "title": "Audit Dashboard Operator Truthfulness",
        "question": (
            "Can an operator diagnose every major production-quality failure from the "
            "dashboard without stale, optimistic, generic, or incomplete UI?"
        ),
    },
    "PDD-083": {
        "pdd_id": "PDD-083",
        "slug": "reusable_agent_memory_reflexion_applicability_audit",
        "title": "Audit Reusable Agent Memory And Reflexion Applicability",
        "question": (
            "Do reusable memory and reflexion lessons influence serious runs only when "
            "applicability, tenant scope, freshness, confidence, and contamination checks pass?"
        ),
    },
    "PDD-097": {
        "pdd_id": "PDD-097",
        "slug": "implementation_feasibility_beyond_final_text_audit",
        "title": "Audit Implementation Feasibility Beyond Final Text",
        "question": (
            "Does every major recommendation prove implementation by real institutions "
            "under real constraints?"
        ),
    },
    "PDD-099": {
        "pdd_id": "PDD-099",
        "slug": "public_contestability_appeals_legitimacy_audit",
        "title": "Audit Public Contestability, Appeals, And Legitimacy",
        "question": (
            "Can affected stakeholders challenge public decisions through a runtime-owned, "
            "auditable, outcome-bearing process?"
        ),
    },
    "PDD-103": {
        "pdd_id": "PDD-103",
        "slug": "human_overtrust_ui_persuasion_risk_audit",
        "title": "Audit Human Overtrust And UI Persuasion Risk",
        "question": "Do UI trust signals make users rely on results beyond their runtime authority?",
    },
}


def build_phase34_6_diagnostics(
    *,
    repo_root: Path = REPO_ROOT,
    wave33_dir: Path = DEFAULT_WAVE33_DIR,
) -> tuple[dict[str, Any], Mapping[str, Any]]:
    context = load_wave33_context(repo_root=repo_root, wave33_dir=wave33_dir)
    diagnostics = {
        "PDD-034": _diagnose_pdd_034(context),
        "PDD-069": _diagnose_pdd_069(context),
        "PDD-083": _diagnose_pdd_083(context),
        "PDD-097": _diagnose_pdd_097(context),
        "PDD-099": _diagnose_pdd_099(context),
        "PDD-103": _diagnose_pdd_103(context),
    }
    return diagnostics, context


def write_phase34_6_outputs(
    *,
    repo_root: Path = REPO_ROOT,
    wave33_dir: Path = DEFAULT_WAVE33_DIR,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> tuple[dict[str, Any], list[Path]]:
    diagnostics, context = build_phase34_6_diagnostics(
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


def _diagnose_pdd_034(context: Mapping[str, Any]) -> dict[str, Any]:
    return canonical_diagnostic(
        context=context,
        spec=PDD_SPECS["PDD-034"],
        tool_name=TOOL_NAME,
        schema_version=SCHEMA_VERSION,
        phase=PHASE_ID,
        verdict="confirmed_projection_consistency_matrix_incomplete_for_wave33",
        acceptance_gate_status="failed_for_missing_cross_surface_negative_matrix",
        findings=[
            {
                "code": "projection_state_matrix_missing",
                "severity": "blocker",
                "summary": (
                    "Wave 33 provides one failed research-profile lane but no API/dashboard "
                    "matrix for failed, warn, pass, override, stale, reissued, and withdrawn states."
                ),
                "evidence": [
                    "_build/policy-design-case/rebaseline/wave-33/real_domain_baseline.json",
                    "_build/policy-design-case/rebaseline/wave-33/research_real_domain_matrix.json",
                ],
            },
            {
                "code": "dashboard_projection_schema_loose",
                "severity": "high",
                "summary": (
                    "Dashboard validation accepts policy_design_case_projection as a "
                    "generic record, so projection-only semantics are not enforced."
                ),
                "evidence": "apps/runtime-dashboard/src/api/validators.ts",
            },
            {
                "code": "projection_masking_negative_controls_missing",
                "severity": "blocker",
                "summary": (
                    "Wave 33 fails closed upstream, but does not prove projections fail "
                    "closed when labels mask missing, stale, conflicting, reissued, withdrawn, "
                    "or non-authoritative evidence."
                ),
                "evidence": "quality_evidence/quality_scorecard.json",
            },
        ],
        evidence={
            "positive_controls": [
                "public_export_bundle declares projection_only authority",
                "control response shaping exposes authoritative_scorecard_ref and projection_source fields",
            ],
            "gate_matrix": [
                {"requirement": "API projection diff against immutable authorities", "verdict": "fail"},
                {"requirement": "Dashboard traces for required states", "verdict": "fail"},
                {"requirement": "Projection-only boundaries", "verdict": "partial"},
                {"requirement": "Projection masking negative controls", "verdict": "not_proven"},
            ],
        },
        recommended_gate=(
            "Require a same-run projection consistency matrix comparing API and dashboard "
            "labels to immutable scorecard, approval, decision-validity, lifecycle, and public-bundle authorities."
        ),
        backlog_summary=(
            "Wave 33 proves projection-only boundaries exist in some surfaces, but it does "
            "not prove dashboard/API projection consistency across required state classes."
        ),
        recommended_remediation_id="PDD-034-A1",
    )


def _diagnose_pdd_069(context: Mapping[str, Any]) -> dict[str, Any]:
    return canonical_diagnostic(
        context=context,
        spec=PDD_SPECS["PDD-069"],
        tool_name=TOOL_NAME,
        schema_version=SCHEMA_VERSION,
        phase=PHASE_ID,
        verdict="confirmed_operator_truthfulness_coverage_is_single_fixture_not_failure_matrix",
        acceptance_gate_status="failed_for_operator_journey_coverage_gap",
        findings=[
            {
                "code": "failure_class_journey_matrix_missing",
                "severity": "blocker",
                "summary": "Wave 33 emits many blocking failure classes, but only one dashboard fixture is covered.",
                "evidence": [
                    "quality_evidence/quality_scorecard.json",
                    "apps/runtime-dashboard/e2e/journeys/honest-diagnostics-operator.spec.ts",
                ],
            },
            {
                "code": "dashboard_to_readiness_diff_missing",
                "severity": "blocker",
                "summary": (
                    "No persisted dashboard-to-readiness diff proves the dashboard mirrors "
                    "Wave 33 readiness and scorecard blockers without optimistic collapse."
                ),
                "evidence": [
                    "_build/policy-design-case/rebaseline/wave-33/readiness.json",
                    "_build/policy-design-case/rebaseline/wave-33/coverage.json",
                ],
            },
            {
                "code": "zero_review_pass_requires_operator_denominator_caveat",
                "severity": "high",
                "summary": (
                    "Human review calibration passes with zero reviews and reviewers while "
                    "effective oversight is true, requiring explicit denominator caveats."
                ),
                "evidence": "quality_evidence/human_review_calibration_report.json",
            },
        ],
        evidence={
            "positive_controls": [
                "operator_diagnostic schema fields exist in control response shaping",
                "one failed serious-run dashboard smoke journey exists",
            ],
            "gate_matrix": [
                {"requirement": "Operator journeys for every serious failure class", "verdict": "fail"},
                {"requirement": "Freshness and source-of-truth indicators", "verdict": "partial"},
                {"requirement": "Dashboard-to-readiness diff", "verdict": "fail"},
                {"requirement": "Artifact/ref navigation to root cause", "verdict": "partial"},
            ],
        },
        recommended_gate=(
            "Require dashboard journeys and persisted dashboard-to-readiness diffs for every "
            "blocking Wave 33 scorecard code."
        ),
        backlog_summary=(
            "Wave 33 and the dashboard have the beginning of operator diagnostics, but not "
            "a failure-class journey matrix or freshness/readiness diff proof. PDD-069 remains failed."
        ),
        recommended_remediation_id="PDD-069-A1",
    )


def _diagnose_pdd_083(context: Mapping[str, Any]) -> dict[str, Any]:
    return canonical_diagnostic(
        context=context,
        spec=PDD_SPECS["PDD-083"],
        tool_name=TOOL_NAME,
        schema_version=SCHEMA_VERSION,
        phase=PHASE_ID,
        verdict="confirmed_no_wave33_runtime_memory_use_ledger",
        acceptance_gate_status="failed_for_missing_memory_use_authority_ledger",
        findings=[
            {
                "code": "memory_use_ledger_missing",
                "severity": "blocker",
                "summary": "Wave 33 contains no memory-use ledger, no no-memory attestation, and no memory/reflexion event artifact.",
                "evidence": "Wave 33 runtime bundle",
            },
            {
                "code": "prompt_tool_ledger_not_memory_authority",
                "severity": "blocker",
                "summary": (
                    "Prompt/tool ledger passes, but has no memory applicability, tenant-scope, "
                    "freshness, confidence, or contamination decisions."
                ),
                "evidence": "quality_evidence/prompt_tool_ledger.json",
            },
            {
                "code": "replay_manifest_memory_surfaces_empty",
                "severity": "high",
                "summary": (
                    "Replay manifest surfaces are empty for memory/reflexion authority purposes."
                ),
                "evidence": "quality_evidence/replay_manifest.json",
            },
        ],
        evidence={
            "positive_controls": [
                "memory contamination checks and retrieval primitives exist in source",
                "case lifecycle has learning contamination validation primitives",
            ],
            "gate_matrix": [
                {"requirement": "Memory-use ledger", "verdict": "fail"},
                {"requirement": "Source-run and tenant/cell scope refs", "verdict": "fail"},
                {"requirement": "Applicability, freshness, and confidence verdicts", "verdict": "fail"},
                {"requirement": "Hidden-eval/canary contamination verdicts", "verdict": "fail"},
                {"requirement": "No-memory attestation", "verdict": "fail"},
            ],
        },
        recommended_gate=(
            "Require runtime memory candidate, rejection, use, no-memory, scope, freshness, "
            "confidence, applicability, contamination, and influence-surface authority rows."
        ),
        backlog_summary=(
            "Wave 33 has no memory/reflexion authority evidence, so reusable learning cannot "
            "be treated as governed input or governed absence. PDD-083 remains failed."
        ),
        recommended_remediation_id="PDD-083-A1",
    )


def _diagnose_pdd_097(context: Mapping[str, Any]) -> dict[str, Any]:
    return canonical_diagnostic(
        context=context,
        spec=PDD_SPECS["PDD-097"],
        tool_name=TOOL_NAME,
        schema_version=SCHEMA_VERSION,
        phase=PHASE_ID,
        verdict="confirmed_implementation_feasibility_claim_is_textual_not_institutional_ledger",
        acceptance_gate_status="failed_for_missing_implementation_feasibility_ledger",
        findings=[
            {
                "code": "implementation_ledger_missing",
                "severity": "blocker",
                "summary": "The major recommendation has implementation and monitoring text but no implementation feasibility ledger.",
                "evidence": "_build/policy-design-case/rebaseline/wave-33/policy_grounding_matrix.json",
            },
            {
                "code": "implementation_evidence_refs_generic",
                "severity": "blocker",
                "summary": (
                    "Implementation feasibility, risk, and monitoring statements cite generic "
                    "data, method, and scenario norm refs used elsewhere."
                ),
                "evidence": "quality_evidence/decision_artifact_quality.json",
            },
            {
                "code": "implementation_monitoring_coverage_zero",
                "severity": "blocker",
                "summary": (
                    "Coverage reports implementation_monitoring_evaluation_pct=0.0 and "
                    "baseline_implementation_monitoring_evaluation_not_emitted."
                ),
                "evidence": "_build/policy-design-case/rebaseline/wave-33/coverage.json",
            },
        ],
        evidence={
            "missing_evidence_classes": [
                "implementing_authority",
                "service_delivery_channel",
                "capacity_evidence",
                "procurement_path",
                "staffing_plan",
                "enforcement_route",
                "eligibility_verification",
                "appeal_handling",
                "rollout_owner",
                "monitoring_owner",
                "indicator_thresholds",
                "evaluation_design",
            ],
            "gate_matrix": [
                {"requirement": "Implementing authority and delivery refs", "verdict": "fail"},
                {"requirement": "Capacity, procurement, staffing, enforcement, appeal, rollout refs", "verdict": "fail"},
                {"requirement": "Monitoring ownership and evaluation plan", "verdict": "fail"},
                {"requirement": "Claim-to-implementation-risk binding", "verdict": "fail"},
                {"requirement": "Fail closed when implementation evidence is missing", "verdict": "partial_fail"},
            ],
        },
        recommended_gate=(
            "Require claim-bound institutional authority, delivery, capacity, procurement, "
            "staffing, enforcement, eligibility, appeal, rollout, monitoring, thresholds, "
            "and typed blockers for every major recommendation."
        ),
        backlog_summary=(
            "Wave 33 has implementation text, risks, and monitoring copy, but no institutional "
            "feasibility ledger. PDD-097 remains failed."
        ),
        recommended_remediation_id="PDD-097-A1",
    )


def _diagnose_pdd_099(context: Mapping[str, Any]) -> dict[str, Any]:
    return canonical_diagnostic(
        context=context,
        spec=PDD_SPECS["PDD-099"],
        tool_name=TOOL_NAME,
        schema_version=SCHEMA_VERSION,
        phase=PHASE_ID,
        verdict="confirmed_public_contestability_is_hooked_in_pass1b_contract_but_absent_from_wave33_case",
        acceptance_gate_status="failed_for_missing_runtime_contestability_appeals_ledger",
        findings=[
            {
                "code": "contestability_appeal_ledger_missing",
                "severity": "blocker",
                "summary": (
                    "No Wave 33 ledger records standing, grounds, deadline, submitted evidence, "
                    "owner, SLA, disposition, or outcome refs."
                ),
                "evidence": "Wave 33 runtime bundle",
            },
            {
                "code": "lifecycle_noop_not_challenge_outcome",
                "severity": "blocker",
                "summary": (
                    "Lifecycle reports are no-op passes and do not prove accepted disputes can "
                    "force reissue, stale marking, withdrawal, or monitoring changes."
                ),
                "evidence": [
                    "quality_evidence/continuous_governance_stale_report.json",
                    "quality_evidence/continuous_governance_reissue_report.json",
                    "quality_evidence/continuous_governance_supersede_report.json",
                    "quality_evidence/continuous_governance_withdraw_report.json",
                ],
            },
            {
                "code": "legitimacy_denominators_absent",
                "severity": "high",
                "summary": (
                    "Human oversight, structured judgement, consultation, and publication "
                    "external-audit families are effectively unproven in Wave 33 evidence."
                ),
                "evidence": [
                    "_build/policy-design-case/rebaseline/wave-33/coverage.json",
                    "quality_evidence/human_review_calibration_report.json",
                ],
            },
        ],
        evidence={
            "positive_controls": [
                "public_export_bundle is projection-only",
                "stale, reissue, supersede, and withdraw lifecycle reports exist",
            ],
            "gate_matrix": [
                {"requirement": "Standing, grounds, deadline, submitted evidence, owner, SLA, disposition refs", "verdict": "fail"},
                {"requirement": "Accepted challenge affects publication state", "verdict": "fail"},
                {"requirement": "Local-only dispute negative scenarios", "verdict": "fail"},
                {"requirement": "Block closeout when appeals are unresolved or detached", "verdict": "not_proven"},
            ],
        },
        recommended_gate=(
            "Require runtime-owned contestability and appeal disposition evidence linked "
            "to publication state, SLA, disposition, lifecycle mutation, or blocker effects."
        ),
        backlog_summary=(
            "Wave 33 contains lifecycle and public-export projection controls, but no "
            "contestability/appeals ledger with outcome-bearing process. PDD-099 remains failed."
        ),
        recommended_remediation_id="PDD-099-A1",
    )


def _diagnose_pdd_103(context: Mapping[str, Any]) -> dict[str, Any]:
    return canonical_diagnostic(
        context=context,
        spec=PDD_SPECS["PDD-103"],
        tool_name=TOOL_NAME,
        schema_version=SCHEMA_VERSION,
        phase=PHASE_ID,
        verdict="confirmed_public_and_operator_trust_cues_exceed_runtime_authority_caveats",
        acceptance_gate_status="failed_for_trust_framing_ledger_gap",
        findings=[
            {
                "code": "trust_framing_ledger_missing",
                "severity": "blocker",
                "summary": (
                    "No Wave 33 ledger maps labels, icons, colors, badges, copy, confidence "
                    "labels, or signature cues to authority and caveats."
                ),
                "evidence": "Wave 33 runtime bundle",
            },
            {
                "code": "frontend_signature_cue_overtrust_risk",
                "severity": "blocker",
                "summary": (
                    "Public UI displays signature verified/OK cues while public export authority "
                    "remains projection_only."
                ),
                "evidence": [
                    "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts",
                    "apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.tsx",
                    "apps/runtime-dashboard/src/features/runs/components/PublicationPacketPanel.tsx",
                ],
            },
            {
                "code": "zero_review_human_trust_caveat_missing",
                "severity": "high",
                "summary": (
                    "Human review calibration passes with review_count=0 and reviewer_count=0; "
                    "human-facing UI needs denominator caveats."
                ),
                "evidence": "quality_evidence/human_review_calibration_report.json",
            },
            {
                "code": "ui_negative_tests_missing",
                "severity": "blocker",
                "summary": (
                    "No Wave 33 UI negative tests cover low-confidence, disputed, untraced, "
                    "simulated, stale, draft, override-approved, or frontend-signed states."
                ),
                "evidence": "apps/runtime-dashboard",
            },
        ],
        evidence={
            "positive_controls": [
                "public export and projection semantics classify the bundle as projection-only",
            ],
            "observed_trust_cues": [
                "signature verified badge",
                "OK badge for raw signature value",
                "ShieldCheck icon with HIGH confidence badge",
                "signed public viewer copy",
            ],
            "gate_matrix": [
                {"requirement": "Label/icon/color/copy-to-authority mapping", "verdict": "fail"},
                {"requirement": "Equal caveats beside strong trust cues", "verdict": "fail"},
                {"requirement": "Negative tests for weak/disputed/simulated/stale/draft/override states", "verdict": "fail"},
                {"requirement": "Public/operator comprehension checks", "verdict": "fail"},
            ],
        },
        recommended_gate=(
            "Require a trust-framing ledger and UI negative tests mapping every label, "
            "icon, color, badge, copy string, confidence label, and signature cue to exact "
            "authority source and caveat requirements."
        ),
        backlog_summary=(
            "Wave 33 proves projection-only semantics exist, but UI trust cues are not "
            "ledger-bound to those authority limits. PDD-103 remains failed."
        ),
        recommended_remediation_id="PDD-103-A1",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave33-dir", type=Path, default=DEFAULT_WAVE33_DIR)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload, written = write_phase34_6_outputs(
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
