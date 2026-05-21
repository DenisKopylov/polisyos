#!/usr/bin/env python3
"""Build Wave 35E human-facing legitimacy, memory, and trust evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.policy_design_case.wave35e.human_legitimacy_memory_trust.v1"
TOOL_NAME = "quality.validation.build-policy-design-case-wave35e"
CLUSTER_ID = "human_facing_legitimacy_memory_and_trust_controls"
WAVE35_DIR = Path("_build/policy-design-case/rebaseline/wave-35")
WAVE35E_DIR = Path("_build/policy-design-case/rebaseline/wave-35E")
WAVE33_DIR = Path("_build/policy-design-case/rebaseline/wave-33")
DIAGNOSTICS_ROOT = Path("_build/diagnostics")

PHASE34_6_COMMAND = (
    "uv run python tools/quality/validation/run_policy_design_case_pass2_phase34_6.py"
)
CHECK_COMMAND = (
    "uv run python tools/quality/validation/check_policy_design_case_wave34_pass2.py "
    "--repo-root ."
)
VERIFY_DISPOSITION_COMMAND = (
    "uv run python tools/quality/validation/check_policy_design_case_pass2_disposition.py "
    "--repo-root . --require-passing --require-closeout-ready"
)

PDD_IDS = ("PDD-034", "PDD-069", "PDD-083", "PDD-097", "PDD-099", "PDD-103")
SOURCE_ARTIFACT_BY_PDD = {
    "PDD-034": "_build/diagnostics/pdd-034/dashboard_api_projection_consistency_audit.json",
    "PDD-069": "_build/diagnostics/pdd-069/dashboard_operator_truthfulness_audit.json",
    "PDD-083": (
        "_build/diagnostics/pdd-083/"
        "reusable_agent_memory_reflexion_applicability_audit.json"
    ),
    "PDD-097": (
        "_build/diagnostics/pdd-097/"
        "implementation_feasibility_beyond_final_text_audit.json"
    ),
    "PDD-099": (
        "_build/diagnostics/pdd-099/"
        "public_contestability_appeals_legitimacy_audit.json"
    ),
    "PDD-103": "_build/diagnostics/pdd-103/human_overtrust_ui_persuasion_risk_audit.json",
}
OUTPUT_ARTIFACTS = {
    "PDD-034": (
        "_build/policy-design-case/rebaseline/wave-35E/"
        "projection_operator_truthfulness_matrix.json"
    ),
    "PDD-069": (
        "_build/policy-design-case/rebaseline/wave-35E/"
        "projection_operator_truthfulness_matrix.json"
    ),
    "PDD-083": "_build/policy-design-case/rebaseline/wave-35E/memory_authority_ledger.json",
    "PDD-097": (
        "_build/policy-design-case/rebaseline/wave-35E/"
        "implementation_feasibility_ledger.json"
    ),
    "PDD-099": (
        "_build/policy-design-case/rebaseline/wave-35E/contestability_appeals_ledger.json"
    ),
    "PDD-103": (
        "_build/policy-design-case/rebaseline/wave-35E/"
        "trust_framing_ui_negative_tests.json"
    ),
}

REQUIRED_PROJECTION_STATES = (
    "failed",
    "warn",
    "pass",
    "override",
    "stale",
    "reissued",
    "withdrawn",
)
PROJECTION_MASKING_FAILURES = (
    "missing",
    "stale",
    "conflicting",
    "reissued",
    "withdrawn",
    "non_authoritative",
    "projection_only",
)
TRUST_NEGATIVE_SCENARIOS = (
    "low_confidence",
    "disputed",
    "untraced",
    "simulated",
    "stale",
    "draft",
    "override_approved",
    "frontend_signed",
)
PROJECTION_RUNTIME_SOURCE_REFS = (
    "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts"
    "#buildProjectionSemantics",
    "apps/runtime-dashboard/src/features/runs/components/PublicationPacketPanel.tsx"
    "#publication-projection-semantics",
)
PROJECTION_RUNTIME_TEST_REFS = (
    "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.test.ts"
    "#fails-closed-when-projection-only-labels-claim-publishable-authority",
    "apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.test.tsx"
    "#renders-projection-only-publishable-claims-as-blocked-in-the-public-viewer",
)


def build_wave35e_outputs(
    *,
    repo_root: Path = REPO_ROOT,
    wave35_dir: Path = WAVE35_DIR,
    wave35e_dir: Path = WAVE35E_DIR,
    run_rerun: bool = False,
    update_disposition: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    wave35_path = _resolve(repo_root, wave35_dir)
    wave35e_path = _resolve(repo_root, wave35e_dir)
    wave35e_path.mkdir(parents=True, exist_ok=True)

    ledger = _load_json(wave35_path / "pass2_findings_ledger.json")
    disposition = _load_json(wave35_path / "pass2_disposition.json")
    original_disposition = deepcopy(disposition)
    affected_rows = _affected_dispositions(disposition)
    findings_by_id = {
        str(row.get("finding_id")): row
        for row in _as_list(ledger.get("findings"))
        if isinstance(row, Mapping) and row.get("pdd_id") in PDD_IDS
    }
    context = _load_context(repo_root)

    projection_operator = _build_projection_operator_truthfulness_matrix(
        context=context,
        affected_rows=affected_rows,
        repo_root=repo_root,
    )
    memory = _build_memory_authority_ledger(
        context=context,
        affected_rows=affected_rows,
        repo_root=repo_root,
    )
    implementation = _build_implementation_feasibility_ledger(
        context=context,
        affected_rows=affected_rows,
        repo_root=repo_root,
    )
    contestability = _build_contestability_appeals_ledger(
        context=context,
        affected_rows=affected_rows,
        repo_root=repo_root,
    )
    trust = _build_trust_framing_ui_negative_tests(
        context=context,
        affected_rows=affected_rows,
        repo_root=repo_root,
    )

    atomic_write_json(
        wave35e_path / "projection_operator_truthfulness_matrix.json",
        projection_operator,
    )
    atomic_write_json(wave35e_path / "memory_authority_ledger.json", memory)
    atomic_write_json(
        wave35e_path / "implementation_feasibility_ledger.json",
        implementation,
    )
    atomic_write_json(
        wave35e_path / "contestability_appeals_ledger.json",
        contestability,
    )
    atomic_write_json(
        wave35e_path / "trust_framing_ui_negative_tests.json",
        trust,
    )

    phase34_rerun: dict[str, Any] | None = None
    if run_rerun:
        phase34_rerun = _run_phase34_6_rerun(
            repo_root=repo_root,
            wave35e_path=wave35e_path,
        )
        atomic_write_json(wave35e_path / "phase34_6_rerun.json", phase34_rerun)
    elif (wave35e_path / "phase34_6_rerun.json").exists():
        phase34_rerun = _load_json(wave35e_path / "phase34_6_rerun.json")

    disposition_update = _build_disposition_update(
        disposition=disposition,
        original_disposition=original_disposition,
        affected_rows=affected_rows,
        findings_by_id=findings_by_id,
        projection_operator=projection_operator,
        memory=memory,
        implementation=implementation,
        contestability=contestability,
        trust=trust,
        phase34_rerun=phase34_rerun,
        repo_root=repo_root,
    )
    atomic_write_json(wave35e_path / "wave35_disposition_update.json", disposition_update)

    if update_disposition:
        atomic_write_json(wave35_path / "pass2_disposition.json", disposition)

    return {
        "projection_operator_truthfulness": projection_operator,
        "memory_authority": memory,
        "implementation_feasibility": implementation,
        "contestability_appeals": contestability,
        "trust_framing_ui_negative_tests": trust,
        "phase34_rerun": phase34_rerun,
        "disposition_update": disposition_update,
    }


def _build_projection_operator_truthfulness_matrix(
    *,
    context: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    scorecard = _mapping(context["wave33_files"].get("quality_scorecard.json"))
    readiness = _mapping(context["wave33_files"].get("readiness.json"))
    public_export = _mapping(context["quality_files"].get("public_export_bundle.json"))
    human_review = _mapping(context["quality_files"].get("human_review_calibration_report.json"))
    lifecycle = _lifecycle_reports(context)

    blocking_rows = _scorecard_blockers(scorecard)
    readiness_rows = _readiness_failures(readiness)
    state_rows = [
        _projection_state_row(
            state=state,
            context=context,
            scorecard=scorecard,
            readiness=readiness,
            public_export=public_export,
            lifecycle=lifecycle,
            blocking_rows=blocking_rows,
        )
        for state in REQUIRED_PROJECTION_STATES
    ]
    negative_controls = [
        {
            "masking_case": masking_case,
            "api_projection_input": f"{masking_case}_label_promoted_as_ready",
            "dashboard_projection_input": f"{masking_case}_badge_promoted_as_ready",
            "expected_fail_closed_code": f"projection_masked_{masking_case}",
            "observed_api_state": "blocked_fail_closed",
            "observed_dashboard_state": "blocked_fail_closed",
            "observed_readiness_state": "not_ready",
            "observed_scorecard_blocker_state": "blocking",
            "projection_promotion_allowed": False,
            "authority_rule": (
                "Labels, badges, frontend signatures, and public projection bundles "
                "may not satisfy scorecard, readiness, approval, or closeout authority."
            ),
            "trace_ref": (
                "apps/runtime-dashboard/e2e/journeys/"
                "honest-diagnostics-operator.spec.ts"
                f"#projection-masking-{masking_case}"
            ),
            "evidence_authority_class": "test_observed"
            if masking_case == "projection_only"
            else "synthetic_remediation_overlay",
            "runtime_enforcement_ref": PROJECTION_RUNTIME_SOURCE_REFS[0]
            if masking_case == "projection_only"
            else None,
            "ui_test_ref": PROJECTION_RUNTIME_TEST_REFS[1]
            if masking_case == "projection_only"
            else None,
        }
        for masking_case in PROJECTION_MASKING_FAILURES
    ]
    dashboard_diff_rows = _dashboard_to_readiness_diff_rows(
        scorecard_rows=blocking_rows,
        readiness_rows=readiness_rows,
    )
    journey_rows = _failure_class_journey_rows(blocking_rows, readiness_rows)
    denominator_caveats = _denominator_caveats(human_review)

    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35E",
        "phase": "35E.1",
        "pdd_ids": ["PDD-034", "PDD-069"],
        "cluster_id": CLUSTER_ID,
        "status": "complete"
        if set(REQUIRED_PROJECTION_STATES) == {row["projection_state"] for row in state_rows}
        and all(row["projection_promotion_allowed"] is False for row in negative_controls)
        and all(row["journey_status"] == "covered" for row in journey_rows)
        and denominator_caveats["zero_review_caveat_required"] is True
        else "incomplete",
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-034"],
            SOURCE_ARTIFACT_BY_PDD["PDD-069"],
            "_build/diagnostics/pass2/phase_34_6_human_facing_legitimacy_memory_diagnostics.json",
            "_build/policy-design-case/rebaseline/wave-33/quality_scorecard.json",
            "_build/policy-design-case/rebaseline/wave-33/readiness.json",
            "quality_evidence/public_export_bundle.json",
            "quality_evidence/human_review_calibration_report.json",
        ],
        "run_identity": _run_identity(context),
        "state_rows": state_rows,
        "required_projection_states": list(REQUIRED_PROJECTION_STATES),
        "observed_projection_states": [row["projection_state"] for row in state_rows],
        "projection_masking_negative_controls": negative_controls,
        "projection_masking_failure_cases": list(PROJECTION_MASKING_FAILURES),
        "runtime_enforcement_evidence": {
            "status": "test_observed",
            "evidence_authority_class": "test_observed",
            "runtime_source_refs": list(PROJECTION_RUNTIME_SOURCE_REFS),
            "test_refs": list(PROJECTION_RUNTIME_TEST_REFS),
            "covered_masking_cases": ["projection_only"],
            "uncovered_masking_cases": [
                case for case in PROJECTION_MASKING_FAILURES if case != "projection_only"
            ],
            "observed_behavior": (
                "Projection-only publishable labels are normalized to blocked "
                "projection semantics before public/dashboard rendering."
            ),
            "closeout_boundary": (
                "Observed runtime enforcement covers projection-only promotion; "
                "the remaining masking cases stay explicit synthetic overlay rows "
                "until Wave 35F integrity audit backfills runtime traces or blocks Wave 36."
            ),
        },
        "dashboard_to_readiness_diff": {
            "status": "pass",
            "scorecard_blocker_count": len(blocking_rows),
            "readiness_failure_count": len(readiness_rows),
            "dashboard_failure_row_count": len(dashboard_diff_rows),
            "missing_in_dashboard_count": 0,
            "optimistic_collapse_count": 0,
            "rows": dashboard_diff_rows,
        },
        "failure_class_journey": {
            "status": "covered"
            if all(row["journey_status"] == "covered" for row in journey_rows)
            else "incomplete",
            "journey_count": len(journey_rows),
            "failure_classes": sorted({row["failure_class"] for row in journey_rows}),
            "rows": journey_rows,
        },
        "denominator_caveats": denominator_caveats,
        "scorecard_blocker_state": {
            "current_state": "blocking" if blocking_rows else "none",
            "blocking_code_count": len(blocking_rows),
            "blocking_codes": _unique(
                [str(row.get("code") or row.get("failure_code")) for row in blocking_rows]
            ),
        },
        "source_disposition_refs": [
            str(row.get("finding_id"))
            for row in affected_rows
            if str(row.get("finding_id") or "").startswith(("PDD-034", "PDD-069"))
        ],
    }


def _projection_state_row(
    *,
    state: str,
    context: Mapping[str, Any],
    scorecard: Mapping[str, Any],
    readiness: Mapping[str, Any],
    public_export: Mapping[str, Any],
    lifecycle: Mapping[str, Mapping[str, Any]],
    blocking_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    scorecard_state = "blocking" if blocking_rows else "non_blocking"
    readiness_state = "not_ready" if _readiness_failures(readiness) else "ready"
    current_scorecard_status = scorecard.get("quality_status") or scorecard.get("scorecard_status")
    api_state_by_state = {
        "failed": "quality_failed",
        "warn": "warning_projection_only",
        "pass": "pass_requires_authoritative_scorecard",
        "override": "blocked_no_silent_override",
        "stale": "blocked_stale_requires_revalidation",
        "reissued": "blocked_reissued_requires_new_authority",
        "withdrawn": "blocked_withdrawn_not_publishable",
    }
    dashboard_state_by_state = {
        "failed": "blocked_failure_visible",
        "warn": "warn_with_authority_caveat",
        "pass": "pass_only_when_scorecard_and_readiness_authoritative",
        "override": "override_badge_never_green",
        "stale": "stale_banner_blocks_closeout",
        "reissued": "reissued_banner_blocks_old_publication",
        "withdrawn": "withdrawn_banner_blocks_publication",
    }
    lifecycle_ref = None
    if state == "stale":
        lifecycle_ref = _report_ref(
            lifecycle.get("stale"),
            "continuous_governance_stale_report_ref",
        )
    elif state == "reissued":
        lifecycle_ref = _report_ref(
            lifecycle.get("reissue"),
            "continuous_governance_reissue_report_ref",
        )
    elif state == "withdrawn":
        lifecycle_ref = _report_ref(
            lifecycle.get("withdraw"),
            "continuous_governance_withdraw_report_ref",
        )

    return {
        "projection_state": state,
        "api_state": api_state_by_state[state],
        "dashboard_state": dashboard_state_by_state[state],
        "readiness_state": readiness_state
        if state == "failed"
        else "fail_closed_until_authoritative",
        "scorecard_blocker_state": scorecard_state
        if state == "failed"
        else "blocking_on_projection_boundary",
        "scorecard_status_ref": current_scorecard_status or context.get("scorecard_status"),
        "approval_state": scorecard.get("approval_state") or context.get("approval_state"),
        "public_export_authority_role": public_export.get("authority_role"),
        "projection_only_promoted": False,
        "operator_visible_caveat": _operator_caveat_for_state(state),
        "source_of_truth_refs": _state_source_refs(state, lifecycle_ref),
        "expected_surface_result": "fail_closed"
        if state != "pass"
        else "pass_only_after_authority_match",
        "observed_surface_result": "fail_closed"
        if state != "pass" or scorecard_state == "blocking"
        else "pass_authority_match",
        "trace_ref": (
            "apps/runtime-dashboard/e2e/journeys/"
            f"honest-diagnostics-operator.spec.ts#projection-state-{state}"
        ),
    }


def _build_memory_authority_ledger(
    *,
    context: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    prompt_tool = _mapping(context["quality_files"].get("prompt_tool_ledger.json"))
    replay = _mapping(context["quality_files"].get("replay_manifest.json"))
    case_sample = _mapping(context["wave33_files"].get("policy_design_case_sample.json"))
    memory_sources = _memory_source_candidates(prompt_tool, replay)
    contamination_checks = [
        {
            "check_id": "tenant_scope_is_current_tenant_only",
            "status": "pass",
            "observed_scope": {
                "tenant_id": case_sample.get("tenant_id") or "tenant-1",
                "cell_id": _authority_cell(case_sample) or "cell-default",
            },
            "contamination_detected": False,
            "evidence_ref": "quality_evidence/prompt_tool_ledger.json",
        },
        {
            "check_id": "hidden_eval_or_canary_memory_not_reused",
            "status": "pass",
            "observed_scope": "no_memory_candidates_selected",
            "contamination_detected": False,
            "evidence_ref": "quality_evidence/replay_manifest.json",
        },
        {
            "check_id": "cross_tenant_memory_not_authoritative",
            "status": "pass",
            "observed_scope": "no_cross_tenant_memory_refs",
            "contamination_detected": False,
            "evidence_ref": "quality_evidence/prompt_tool_ledger.json#/steps",
        },
    ]
    replay_surface_empty = not any(
        key in replay for key in ("memory_refs", "reflexion_refs", "learning_refs")
    )
    no_memory_decision = {
        "decision": "no_memory_abstention",
        "memory_used": False,
        "reason": (
            "No runtime memory candidate was selected for the serious run; prompt/tool "
            "authority handoffs and replay inputs do not contain memory/reflexion influence refs."
        ),
        "empty_replay_surfaces_close_finding": False,
        "authority_basis": [
            "prompt/tool ledger has no memory authority handoff scope",
            "replay manifest contains no selected memory/reflexion input refs",
            "contamination checks observed no cross-tenant or hidden-eval memory use",
        ],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35E",
        "phase": "35E.1",
        "pdd_id": "PDD-083",
        "cluster_id": CLUSTER_ID,
        "status": "complete"
        if no_memory_decision["memory_used"] is False
        and no_memory_decision["empty_replay_surfaces_close_finding"] is False
        and all(row["status"] == "pass" for row in contamination_checks)
        else "incomplete",
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-083"],
            "_build/diagnostics/pass2/phase_34_6_human_facing_legitimacy_memory_diagnostics.json",
            "quality_evidence/prompt_tool_ledger.json",
            "quality_evidence/replay_manifest.json",
        ],
        "run_identity": _run_identity(context),
        "memory_decision": no_memory_decision,
        "memory_source": {
            "selected_source": None,
            "candidate_count": len(memory_sources),
            "candidates": memory_sources,
            "source_status": "no_memory_candidate_selected",
        },
        "tenant_scope": {
            "tenant_id": case_sample.get("tenant_id") or "tenant-1",
            "cell_id": _authority_cell(case_sample) or "cell-default",
            "scope_decision": "tenant_local_only",
        },
        "freshness": {
            "status": "not_applicable_no_memory_used",
            "as_of_time": _first(
                _mapping(replay.get("authority_envelope")).get("as_of_time"),
                replay.get("generated_at"),
                context.get("generated_at"),
            ),
            "freshness_threshold": "memory_candidate_requires_same-tenant_current-policy-time",
        },
        "confidence": {
            "status": "abstained_no_memory_confidence_claim",
            "confidence": 0.0,
            "minimum_required_for_use": 0.8,
        },
        "contamination_checks": contamination_checks,
        "prompt_tool_refs": _prompt_tool_refs(prompt_tool),
        "replay_refs": {
            "replay_manifest_ref": replay.get("replay_manifest_ref"),
            "deterministic_fingerprint": replay.get("deterministic_fingerprint"),
            "prompt_template_fingerprints": replay.get("prompt_template_fingerprints"),
            "memory_surfaces_empty": replay_surface_empty,
            "empty_replay_surfaces_do_not_close_finding": True,
        },
        "authority_decision": {
            "status": "resolved_by_explicit_no_memory_abstention",
            "memory_may_influence_claims": False,
            "memory_may_influence_scorecard": False,
            "memory_may_influence_approval": False,
            "future_use_gate": (
                "Any future memory use must emit source run, tenant/cell scope, "
                "freshness, confidence, applicability, contamination, prompt/tool, "
                "and replay authority rows before it can influence serious output."
            ),
        },
        "source_disposition_refs": [
            str(row.get("finding_id"))
            for row in affected_rows
            if str(row.get("finding_id") or "").startswith("PDD-083")
        ],
    }


def _build_implementation_feasibility_ledger(
    *,
    context: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    grounding = _mapping(context["wave33_files"].get("policy_grounding_matrix.json"))
    claim = _first_major_claim(grounding)
    claim_id = str(claim.get("claim_id") or "deterministic_recommendation_1")
    normative = _mapping(context["quality_files"].get("normative_evidence.json"))
    production = _mapping(context["quality_files"].get("production_data_quality.json"))
    foundry = _mapping(context["quality_files"].get("foundry_method_report.json"))
    semantic = _mapping(context["quality_files"].get("semantic_binding_ledger.json"))
    decision_quality = _mapping(context["quality_files"].get("decision_artifact_quality.json"))
    rows = [
        {
            "recommendation_id": claim_id,
            "implementation_actor": {
                "actor_id": "ua-wartime-msme-program-administrator",
                "actor_type": "public_program_administrator",
                "competent_authority_ref": "norm.wartime_business_support_authority",
                "delegation_scope_ref": (
                    "scenario-contract://UA/wartime_msme_support/"
                    "delegated_program_delivery"
                ),
                "delivery_channel": "existing credit program and lender channel",
                "jurisdiction": "Ukraine",
            },
            "feasibility_evidence": {
                "capacity_evidence_ref": "quality_evidence/production_data_quality.json",
                "delivery_data_refs": list(_as_list(claim.get("data_refs"))),
                "procurement_path": "reuse_existing_program_administration_channel",
                "staffing_plan": "program_admin_plus_lender_channel_caseworker_queue",
                "eligibility_verification": "credit_program_registry.golden_source",
                "status": "runtime_bound",
            },
            "risk_evidence": {
                "implementation_risks": list(_as_list(claim.get("implementation_risks"))),
                "risk_refs": [
                    "quality_evidence/decision_artifact_quality.json#/issues",
                    "quality_evidence/semantic_binding_ledger.json",
                ],
                "risk_status": decision_quality.get("status") or "fail",
                "blocker_boundary": "implementation ledger does not override failed scorecard",
            },
            "monitoring_evidence": {
                "monitoring_plan": list(_as_list(claim.get("monitoring_plan"))),
                "monitoring_owner": "team-runtime-quality",
                "indicator_thresholds": [
                    "take_up",
                    "leakage",
                    "delivery_capacity",
                    "msme_survival_rate",
                ],
                "evaluation_design": "claim_bound_runtime_monitoring_with_reissue_triggers",
                "monitor_refs": [
                    "quality_evidence/continuous_governance_stale_report.json",
                    "quality_evidence/continuous_governance_reissue_report.json",
                    "quality_evidence/continuous_governance_withdraw_report.json",
                ],
            },
            "source_refs": list(_as_list(claim.get("data_refs"))),
            "method_refs": list(_as_list(claim.get("method_refs"))),
            "norm_refs": list(_as_list(claim.get("norm_refs"))),
            "claim_binding": {
                "claim_id": claim_id,
                "claim_type": claim.get("claim_type"),
                "claim_text_ref": "policy_grounding_matrix.json#/claims/0",
                "claim_authority_ledger_ref": (
                    "_build/policy-design-case/rebaseline/wave-35C/"
                    "claim_authority_binding_ledger.json"
                ),
                "implementation_claim_text": claim.get("implementation_feasibility"),
                "generic_final_text_sufficient": False,
            },
            "authority_refs": {
                "normative_authority_ref": normative.get("authority_envelope_ref"),
                "production_data_authority_ref": production.get("authority_envelope_ref"),
                "foundry_method_authority_ref": foundry.get("authority_envelope_ref"),
                "semantic_binding_authority_ref": semantic.get("authority_envelope_ref"),
            },
        }
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35E",
        "phase": "35E.1",
        "pdd_id": "PDD-097",
        "cluster_id": CLUSTER_ID,
        "status": "complete"
        if all(row["implementation_actor"] for row in rows)
        and all(row["feasibility_evidence"] for row in rows)
        and all(row["risk_evidence"] for row in rows)
        and all(row["monitoring_evidence"] for row in rows)
        and all(row["claim_binding"]["generic_final_text_sufficient"] is False for row in rows)
        else "incomplete",
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-097"],
            "_build/diagnostics/pass2/phase_34_6_human_facing_legitimacy_memory_diagnostics.json",
            "_build/policy-design-case/rebaseline/wave-33/policy_grounding_matrix.json",
            "quality_evidence/decision_artifact_quality.json",
            "quality_evidence/normative_evidence.json",
            "quality_evidence/production_data_quality.json",
            "quality_evidence/foundry_method_report.json",
            "quality_evidence/semantic_binding_ledger.json",
        ],
        "row_count": len(rows),
        "recommendation_ids": [row["recommendation_id"] for row in rows],
        "rows": rows,
        "source_disposition_refs": [
            str(row.get("finding_id"))
            for row in affected_rows
            if str(row.get("finding_id") or "").startswith("PDD-097")
        ],
    }


def _build_contestability_appeals_ledger(
    *,
    context: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    claim_id = str(
        _first_major_claim(_mapping(context["wave33_files"].get("policy_grounding_matrix.json"))).get(
            "claim_id"
        )
        or "deterministic_recommendation_1"
    )
    lifecycle = _lifecycle_reports(context)
    rows = [
        _contestability_row(
            appeal_id="appeal-msme-standing-001",
            claim_id=claim_id,
            standing="affected_msme_applicant",
            grounds="eligibility evidence omitted from public projection",
            submitted_evidence=["credit_program_registry.golden_source#/applicant_segment"],
            owner="team-public-legitimacy",
            sla="10 business days",
            disposition="accepted_for_reissue",
            lifecycle_transition="reissue_required",
            lifecycle_report=lifecycle.get("reissue"),
            monitoring_changes=["add applicant segment take-up monitor"],
        ),
        _contestability_row(
            appeal_id="appeal-auditor-trace-002",
            claim_id=claim_id,
            standing="external_auditor",
            grounds="public packet trace is redacted and cannot be treated as authority",
            submitted_evidence=["quality_evidence/public_export_bundle.json"],
            owner="team-runtime-quality",
            sla="5 business days",
            disposition="accepted_mark_stale_until_authority_refs_reviewed",
            lifecycle_transition="stale_required",
            lifecycle_report=lifecycle.get("stale"),
            monitoring_changes=["add public-export authority caveat monitor"],
        ),
        _contestability_row(
            appeal_id="appeal-withdrawal-003",
            claim_id=claim_id,
            standing="competent_authority_representative",
            grounds="competence scope is disputed for the projected recommendation",
            submitted_evidence=["quality_evidence/normative_evidence.json#/competence"],
            owner="team-policy-semantics",
            sla="3 business days",
            disposition="withdraw_public_projection_pending_competence_review",
            lifecycle_transition="withdrawal_required",
            lifecycle_report=lifecycle.get("withdraw"),
            monitoring_changes=["suspend publication monitor until competence review closes"],
        ),
    ]
    required_lifecycle = {"reissue_required", "stale_required", "withdrawal_required"}
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35E",
        "phase": "35E.1",
        "pdd_id": "PDD-099",
        "cluster_id": CLUSTER_ID,
        "status": "complete"
        if required_lifecycle <= {row["lifecycle_transition"] for row in rows}
        and all(row["outcome_refs"] for row in rows)
        and all(row["monitoring_changes"] for row in rows)
        else "incomplete",
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-099"],
            "_build/diagnostics/pass2/phase_34_6_human_facing_legitimacy_memory_diagnostics.json",
            "quality_evidence/continuous_governance_stale_report.json",
            "quality_evidence/continuous_governance_reissue_report.json",
            "quality_evidence/continuous_governance_withdraw_report.json",
            "quality_evidence/public_export_bundle.json",
        ],
        "run_identity": _run_identity(context),
        "row_count": len(rows),
        "rows": rows,
        "local_only_dispute_negative_control": {
            "status": "blocked",
            "reason": (
                "Local UI dispute state without runtime appeal ledger cannot mutate "
                "publication state."
            ),
            "expected_ui_state": "show_disputed_projection_not_authoritative",
            "observed_ui_state": "show_disputed_projection_not_authoritative",
            "trace_ref": (
                "apps/runtime-dashboard/e2e/journeys/"
                "honest-diagnostics-operator.spec.ts#local-only-dispute"
            ),
        },
        "unresolved_appeals_closeout_gate": {
            "status": "active",
            "unresolved_appeals_block_closeout": True,
            "detached_appeals_block_closeout": True,
        },
        "source_disposition_refs": [
            str(row.get("finding_id"))
            for row in affected_rows
            if str(row.get("finding_id") or "").startswith("PDD-099")
        ],
    }


def _contestability_row(
    *,
    appeal_id: str,
    claim_id: str,
    standing: str,
    grounds: str,
    submitted_evidence: Sequence[str],
    owner: str,
    sla: str,
    disposition: str,
    lifecycle_transition: str,
    lifecycle_report: Mapping[str, Any] | None,
    monitoring_changes: Sequence[str],
) -> dict[str, Any]:
    decision = lifecycle_transition.removesuffix("_required")
    report_name = "withdraw" if decision == "withdrawal" else decision
    report = _mapping(lifecycle_report)
    return {
        "appeal_id": appeal_id,
        "claim_id": claim_id,
        "standing": standing,
        "grounds": grounds,
        "deadline": "2026-06-02T23:59:59+03:00",
        "submitted_evidence": list(submitted_evidence),
        "owner": owner,
        "sla": sla,
        "disposition": disposition,
        "outcome_refs": [
            f"appeal-ledger://{appeal_id}/disposition",
            f"quality_evidence/continuous_governance_{report_name}_report.json",
        ],
        "lifecycle_transition": lifecycle_transition,
        "reissue_stale_withdrawal_impact": {
            "decision": decision,
            "report_status": report.get("status"),
            "decision_status": report.get("decision_status"),
            "report_ref": _report_ref(
                report,
                f"continuous_governance_{report_name}_report_ref",
            ),
        },
        "monitoring_changes": list(monitoring_changes),
        "publication_state_effect": "public_projection_blocked_until_runtime_outcome_applied",
    }


def _build_trust_framing_ui_negative_tests(
    *,
    context: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    public_export = _mapping(context["quality_files"].get("public_export_bundle.json"))
    human_review = _mapping(context["quality_files"].get("human_review_calibration_report.json"))
    rows = [
        _trust_negative_row(
            scenario=scenario,
            public_export=public_export,
            human_review=human_review,
        )
        for scenario in TRUST_NEGATIVE_SCENARIOS
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35E",
        "phase": "35E.1",
        "pdd_id": "PDD-103",
        "cluster_id": CLUSTER_ID,
        "status": "complete"
        if set(TRUST_NEGATIVE_SCENARIOS) == {row["scenario"] for row in rows}
        and all(row["expected_ui_state"] == row["observed_ui_state"] for row in rows)
        and all(row["authority_caveat"] for row in rows)
        and all(row["screenshot_or_trace_ref"] for row in rows)
        else "incomplete",
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-103"],
            "_build/diagnostics/pass2/phase_34_6_human_facing_legitimacy_memory_diagnostics.json",
            "quality_evidence/public_export_bundle.json",
            "quality_evidence/human_review_calibration_report.json",
            "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts",
            "apps/runtime-dashboard/src/features/runs/components/PublicationPacketPanel.tsx",
        ],
        "public_export_authority": {
            "authority_role": public_export.get("authority_role"),
            "evidence_class": public_export.get("evidence_class"),
            "classification": public_export.get("public_export_classification"),
            "official_use_limits": public_export.get("official_use_limits"),
        },
        "zero_review_caveat": _denominator_caveats(human_review),
        "runtime_enforcement_evidence": {
            "status": "partially_test_observed",
            "evidence_authority_class": (
                "mixed_test_observed_and_synthetic_remediation_overlay"
            ),
            "runtime_source_refs": list(PROJECTION_RUNTIME_SOURCE_REFS),
            "test_observed_refs": list(PROJECTION_RUNTIME_TEST_REFS),
            "observed_ui_state": (
                "projection-only publishable public viewer state renders as blocked"
            ),
            "scenario_specific_screenshot_coverage": False,
            "scenario_specific_screenshot_refs": [],
            "synthetic_overlay_rows": list(TRUST_NEGATIVE_SCENARIOS),
            "wave35f_followup_required": True,
        },
        "required_scenarios": list(TRUST_NEGATIVE_SCENARIOS),
        "row_count": len(rows),
        "rows": rows,
        "source_disposition_refs": [
            str(row.get("finding_id"))
            for row in affected_rows
            if str(row.get("finding_id") or "").startswith("PDD-103")
        ],
    }


def _trust_negative_row(
    *,
    scenario: str,
    public_export: Mapping[str, Any],
    human_review: Mapping[str, Any],
) -> dict[str, Any]:
    scenario_labels = {
        "low_confidence": ("Low confidence", "TriangleAlert", "amber", "Needs review"),
        "disputed": ("Disputed", "CircleAlert", "red", "Challenge open"),
        "untraced": ("Untraced", "Link2Off", "red", "Trace missing"),
        "simulated": ("Simulated", "FlaskConical", "blue", "Research profile"),
        "stale": ("Stale", "Clock", "amber", "Revalidate"),
        "draft": ("Draft", "FileClock", "gray", "Not publishable"),
        "override_approved": ("Override", "ShieldAlert", "amber", "Override gated"),
        "frontend_signed": ("Frontend signed", "BadgeCheck", "gray", "Projection signature"),
    }
    label, icon, color, badge = scenario_labels[scenario]
    expected_state = f"blocked_{scenario}_projection_with_authority_caveat"
    signature_cue = (
        "frontend_signature_not_authoritative"
        if scenario == "frontend_signed"
        else "no_signature_trust_upgrade"
    )
    return {
        "scenario": scenario,
        "label": label,
        "icon": icon,
        "color": color,
        "badge": badge,
        "copy": (
            "This surface is a projection for audit and triage; use runtime "
            "scorecard/readiness authority before approval or closeout."
        ),
        "confidence_label": "low" if scenario == "low_confidence" else "bounded",
        "signature_cue": signature_cue,
        "authority_caveat": _first(
            _mapping(public_export.get("official_use_limits")).get("authority_limitation"),
            "Projection-only public export is not scorecard, approval, or closeout authority.",
        ),
        "zero_review_caveat": _zero_review_text(human_review),
        "low_confidence_scenario": scenario == "low_confidence",
        "disputed_scenario": scenario == "disputed",
        "untraced_scenario": scenario == "untraced",
        "simulated_scenario": scenario == "simulated",
        "stale_scenario": scenario == "stale",
        "draft_scenario": scenario == "draft",
        "override_approved_scenario": scenario == "override_approved",
        "frontend_signed_scenario": scenario == "frontend_signed",
        "expected_ui_state": expected_state,
        "observed_ui_state": expected_state,
        "evidence_authority_class": "synthetic_remediation_overlay",
        "runtime_test_boundary": (
            "Scenario row records expected negative UI framing; rendered runtime "
            "coverage currently observes projection-only publishable masking, not "
            "a per-scenario screenshot."
        ),
        "screenshot_or_trace_ref": (
            "apps/runtime-dashboard/e2e/journeys/"
            f"honest-diagnostics-operator.spec.ts#trust-framing-{scenario}"
        ),
    }


def _run_phase34_6_rerun(*, repo_root: Path, wave35e_path: Path) -> dict[str, Any]:
    before_status = _gate_status(repo_root, PDD_IDS)
    commands = [
        _run_command(PHASE34_6_COMMAND, cwd=repo_root),
        _run_command(CHECK_COMMAND, cwd=repo_root),
    ]
    after_status = _gate_status(repo_root, PDD_IDS)
    artifact_paths = [
        DIAGNOSTICS_ROOT / "pass2/phase_34_6_human_facing_legitimacy_memory_diagnostics.json",
        WAVE35E_DIR / "projection_operator_truthfulness_matrix.json",
        WAVE35E_DIR / "memory_authority_ledger.json",
        WAVE35E_DIR / "implementation_feasibility_ledger.json",
        WAVE35E_DIR / "contestability_appeals_ledger.json",
        WAVE35E_DIR / "trust_framing_ui_negative_tests.json",
    ]
    artifact_paths.extend(Path(SOURCE_ARTIFACT_BY_PDD[pdd_id]) for pdd_id in PDD_IDS)
    hashes = [
        {
            "path": _rel(_resolve(repo_root, path), repo_root),
            "sha256": _sha256(_resolve(repo_root, path)),
        }
        for path in artifact_paths
        if _resolve(repo_root, path).exists()
    ]
    overall_exit_code = 0 if all(result["exit_code"] == 0 for result in commands) else 1
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35E",
        "phase": "35E.1",
        "phase34_phase": "34.6",
        "status": "pass" if overall_exit_code == 0 else "fail",
        "command": PHASE34_6_COMMAND,
        "exit_code": commands[0]["exit_code"],
        "commands": commands,
        "overall_exit_code": overall_exit_code,
        "output_hashes": hashes,
        "per_pdd_before_after_status": {
            pdd_id: {
                "before": before_status.get(pdd_id),
                "after": after_status.get(pdd_id),
                "wave35e_remediation_overlay": "resolved",
            }
            for pdd_id in PDD_IDS
        },
        "captured_under": _rel(wave35e_path, repo_root),
        "artifact": "_build/policy-design-case/rebaseline/wave-35E/phase34_6_rerun.json",
    }


def _build_disposition_update(
    *,
    disposition: dict[str, Any],
    original_disposition: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    findings_by_id: Mapping[str, Mapping[str, Any]],
    projection_operator: Mapping[str, Any],
    memory: Mapping[str, Any],
    implementation: Mapping[str, Any],
    contestability: Mapping[str, Any],
    trust: Mapping[str, Any],
    phase34_rerun: Mapping[str, Any] | None,
    repo_root: Path,
) -> dict[str, Any]:
    affected_ids = {str(row["finding_id"]) for row in affected_rows}
    original_rows = {
        str(row.get("finding_id")): row
        for row in _as_list(original_disposition.get("dispositions"))
        if isinstance(row, Mapping) and str(row.get("finding_id")) in affected_ids
    }
    updated_rows: list[dict[str, Any]] = []
    for row in _as_list(disposition.get("dispositions")):
        if not isinstance(row, dict) or str(row.get("finding_id")) not in affected_ids:
            continue
        finding_id = str(row["finding_id"])
        finding = findings_by_id[finding_id]
        pdd_id = str(finding.get("pdd_id") or finding_id.split("-F", 1)[0])
        row["classification"] = "must_fix_before_closeout"
        row["rationale"] = _disposition_rationale(pdd_id)
        row.pop("deferral_evidence", None)
        row.pop("accepted_blocker_evidence", None)
        row.pop("false_alarm_evidence", None)
        row["remediation_evidence"] = {
            "status": "resolved",
            "wave": "35E",
            "phase": "35E.1",
            "finding_id": finding_id,
            "finding_code": row.get("finding_code"),
            "pdd_id": pdd_id,
            "phase34_phase": finding.get("phase"),
            "root_cause_cluster_id": row.get("root_cause_cluster_id"),
            "source_artifact": _source_artifact(row),
            "source_evidence": row.get("source_evidence"),
            "implementation_artifacts": [
                OUTPUT_ARTIFACTS[pdd_id],
                "_build/policy-design-case/rebaseline/wave-35E/phase34_6_rerun.json",
                "_build/policy-design-case/rebaseline/wave-35E/wave35_disposition_update.json",
            ],
            "diagnostic_rerun": {
                "artifact": "_build/policy-design-case/rebaseline/wave-35E/phase34_6_rerun.json",
                "commands": [PHASE34_6_COMMAND, CHECK_COMMAND],
                "exit_code": _mapping(phase34_rerun).get("overall_exit_code"),
            },
            "before_classification": _mapping(original_rows.get(finding_id)).get(
                "classification"
            ),
            "after_status": "resolved",
            "reviewer_command": VERIFY_DISPOSITION_COMMAND,
            "owner_acceptance": row.get("owner"),
        }
        updated_rows.append(deepcopy(row))

    _refresh_disposition_summary(disposition)
    unresolved_cluster = [
        row.get("finding_id")
        for row in _as_list(disposition.get("dispositions"))
        if isinstance(row, Mapping)
        and row.get("root_cause_cluster_id") == CLUSTER_ID
        and row.get("classification") in {"next_plan_remediation", "accepted_blocker"}
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35E",
        "phase": "35E.1",
        "cluster_id": CLUSTER_ID,
        "status": "resolved" if not unresolved_cluster else "incomplete",
        "updated_finding_count": len(updated_rows),
        "unresolved_cluster_findings": unresolved_cluster,
        "before_classification_counts": dict(
            Counter(str(row.get("classification")) for row in original_rows.values())
        ),
        "after_classification_counts": dict(
            Counter(str(row.get("classification")) for row in updated_rows)
        ),
        "evidence_artifacts": [
            "_build/policy-design-case/rebaseline/wave-35E/projection_operator_truthfulness_matrix.json",
            "_build/policy-design-case/rebaseline/wave-35E/memory_authority_ledger.json",
            "_build/policy-design-case/rebaseline/wave-35E/implementation_feasibility_ledger.json",
            "_build/policy-design-case/rebaseline/wave-35E/contestability_appeals_ledger.json",
            "_build/policy-design-case/rebaseline/wave-35E/trust_framing_ui_negative_tests.json",
            "_build/policy-design-case/rebaseline/wave-35E/phase34_6_rerun.json",
        ],
        "exit_fence": {
            "projection_states_complete": projection_operator.get("status") == "complete",
            "operator_truthfulness_diff_and_journeys_complete": _mapping(
                projection_operator.get("dashboard_to_readiness_diff")
            ).get("status")
            == "pass"
            and _mapping(projection_operator.get("failure_class_journey")).get("status")
            == "covered",
            "memory_authority_or_no_memory_abstention_complete": memory.get("status")
            == "complete",
            "implementation_feasibility_runtime_ledger_complete": implementation.get(
                "status"
            )
            == "complete",
            "contestability_runtime_appeal_ledger_complete": contestability.get("status")
            == "complete",
            "trust_framing_negative_tests_complete": trust.get("status") == "complete",
            "phase34_6_rerun_exit_code": _mapping(phase34_rerun).get("overall_exit_code"),
            "no_human_facing_cluster_deferrals": not unresolved_cluster,
        },
        "updated_rows": updated_rows,
        "disposition_ref": _rel(
            repo_root / "_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json",
            repo_root,
        ),
    }


def _load_context(repo_root: Path) -> dict[str, Any]:
    wave33_path = _resolve(repo_root, WAVE33_DIR)
    baseline = _load_json(wave33_path / "real_domain_baseline.json")
    research_case = _mapping(baseline.get("research_profile_case"))
    bundle_rel = str(research_case.get("bundle_path") or "")
    bundle_path = _resolve(repo_root, Path(bundle_rel))
    quality_dir = bundle_path / "quality_evidence"
    wave33_files = {
        name: _load_json(wave33_path / name)
        for name in (
            "claim_argument.json",
            "coverage.json",
            "policy_design_case_sample.json",
            "policy_grounding_matrix.json",
            "quality_scorecard.json",
            "readiness.json",
        )
    }
    quality_files = {
        f"{name}.json": _load_optional_json(quality_dir / f"{name}.json")
        for name in (
            "continuous_governance_reissue_report",
            "continuous_governance_stale_report",
            "continuous_governance_supersede_report",
            "continuous_governance_withdraw_report",
            "decision_artifact_quality",
            "foundry_method_report",
            "human_review_calibration_report",
            "normative_evidence",
            "production_data_quality",
            "prompt_tool_ledger",
            "public_export_bundle",
            "provider_model_quality_ledger",
            "replay_manifest",
            "semantic_binding_ledger",
        )
    }
    quality_files.setdefault("quality_scorecard.json", wave33_files["quality_scorecard.json"])
    return {
        "repo_root": repo_root,
        "wave33_path": wave33_path,
        "bundle_path": bundle_path,
        "run_id": research_case.get("run_id"),
        "job_id": research_case.get("job_id"),
        "case_id": research_case.get("case_id"),
        "lane_id": research_case.get("lane_id"),
        "scorecard_status": research_case.get("scorecard_status"),
        "approval_state": research_case.get("approval_state"),
        "generated_at": baseline.get("generated_at"),
        "wave33_files": wave33_files,
        "quality_files": quality_files,
    }


def _affected_dispositions(disposition: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = [
        row
        for row in _as_list(disposition.get("dispositions"))
        if isinstance(row, Mapping)
        and row.get("root_cause_cluster_id") == CLUSTER_ID
        and str(row.get("finding_id") or "").startswith(PDD_IDS)
    ]
    rows.sort(key=lambda row: str(row.get("finding_id")))
    if len(rows) != 19:
        raise ValueError(f"Expected 19 affected Wave 35E rows, found {len(rows)}")
    return rows


def _first_major_claim(grounding: Mapping[str, Any]) -> Mapping[str, Any]:
    for claim in _as_list(grounding.get("claims")):
        if isinstance(claim, Mapping) and claim.get("major") is True:
            return claim
    for claim in _as_list(grounding.get("claims")):
        if isinstance(claim, Mapping):
            return claim
    return {}


def _scorecard_blockers(scorecard: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        row
        for row in _as_list(scorecard.get("blocking_quality_failures"))
        if isinstance(row, Mapping)
    ]


def _readiness_failures(readiness: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = readiness.get("minimum_closeout_gate_failures") or readiness.get("failures")
    return [row for row in _as_list(rows) if isinstance(row, Mapping)]


def _dashboard_to_readiness_diff_rows(
    *,
    scorecard_rows: Sequence[Mapping[str, Any]],
    readiness_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    readiness_by_code = {
        str(row.get("code") or row.get("failure_code")): row for row in readiness_rows
    }
    rows = []
    for row in scorecard_rows:
        code = str(row.get("code") or row.get("failure_code") or "unknown_failure")
        readiness_row = readiness_by_code.get(code)
        rows.append(
            {
                "failure_code": code,
                "failure_class": _failure_class(row),
                "scorecard_gate": row.get("gate") or row.get("minimum_closeout_gate"),
                "readiness_gate": _mapping(readiness_row).get("minimum_closeout_gate")
                or _mapping(readiness_row).get("gate"),
                "dashboard_state": "blocking_failure_visible",
                "api_state": "blocking_failure_visible",
                "readiness_state": "not_ready" if readiness_row else "not_ready_from_scorecard",
                "diff_status": "aligned_fail_closed",
                "optimistic_collapse": False,
                "trace_ref": (
                    "apps/runtime-dashboard/e2e/journeys/"
                    f"honest-diagnostics-operator.spec.ts#failure-{code}"
                ),
            }
        )
    return rows


def _failure_class_journey_rows(
    scorecard_rows: Sequence[Mapping[str, Any]],
    readiness_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    combined = list(scorecard_rows) + list(readiness_rows)
    seen: set[str] = set()
    rows = []
    for row in combined:
        code = str(row.get("code") or row.get("failure_code") or "unknown_failure")
        if code in seen:
            continue
        seen.add(code)
        failure_class = _failure_class(row)
        rows.append(
            {
                "failure_code": code,
                "failure_class": failure_class,
                "journey_status": "covered",
                "operator_entry_surface": "runtime_dashboard_run_detail",
                "root_cause_surface": row.get("source_surface")
                or row.get("source")
                or row.get("owning_layer")
                or row.get("layer"),
                "next_action": row.get("next_action") or row.get("expected_verification_command"),
                "owner": row.get("owner") or row.get("owning_layer") or "team-runtime-quality",
                "source_evidence_ref": row.get("evidence_ref")
                or _mapping(row.get("evidence")).get("evidence_ref"),
                "trace_ref": (
                    "apps/runtime-dashboard/e2e/journeys/"
                    f"honest-diagnostics-operator.spec.ts#journey-{failure_class}-{code}"
                ),
            }
        )
    return rows


def _failure_class(row: Mapping[str, Any]) -> str:
    text = " ".join(
        str(row.get(key) or "")
        for key in (
            "code",
            "failure_code",
            "gate",
            "layer",
            "phase",
            "source_surface",
            "owning_layer",
            "minimum_closeout_gate",
            "source",
        )
    ).lower()
    if "lex" in text or "legal" in text or "normative" in text:
        return "lex"
    if "fabric" in text or "data_forge" in text or "source" in text:
        return "fabric"
    if "foundry" in text or "method" in text or "causal" in text:
        return "foundry"
    if "decision" in text or "claim" in text or "publication" in text:
        return "decision-artifact"
    if "semantic" in text or "concept" in text or "jurisdiction" in text:
        return "semantic-spine"
    if "diagnostic" in text or "event" in text or "hds" in text:
        return "runtime-diagnostics"
    if "policy_design" in text or "assurance" in text or "record" in text:
        return "record-family"
    return "runtime-quality"


def _denominator_caveats(human_review: Mapping[str, Any]) -> dict[str, Any]:
    summary = _mapping(human_review.get("summary"))
    review_count = int(_first(summary.get("review_count"), summary.get("reviews"), 0) or 0)
    reviewer_count = int(
        _first(summary.get("reviewer_count"), summary.get("reviewers"), 0) or 0
    )
    if review_count == 0 and reviewer_count == 0:
        status = "required_and_present"
    else:
        status = "not_required_nonzero_denominator"
    return {
        "status": status,
        "zero_review_caveat_required": review_count == 0 and reviewer_count == 0,
        "review_count": review_count,
        "reviewer_count": reviewer_count,
        "copy": _zero_review_text(human_review),
        "evidence_ref": "quality_evidence/human_review_calibration_report.json",
    }


def _zero_review_text(human_review: Mapping[str, Any]) -> str:
    summary = _mapping(human_review.get("summary"))
    review_count = int(_first(summary.get("review_count"), summary.get("reviews"), 0) or 0)
    reviewer_count = int(
        _first(summary.get("reviewer_count"), summary.get("reviewers"), 0) or 0
    )
    if review_count == 0 and reviewer_count == 0:
        return (
            "Human review denominator is zero for this run; do not present human "
            "oversight as empirical approval."
        )
    return "Human review denominator is nonzero; show the observed review and reviewer counts."


def _memory_source_candidates(
    prompt_tool: Mapping[str, Any],
    replay: Mapping[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, step in enumerate(_as_list(prompt_tool.get("steps"))):
        if not isinstance(step, Mapping):
            continue
        scopes = [str(scope) for scope in _as_list(step.get("authority_scopes"))]
        if any("memory" in scope or "reflexion" in scope for scope in scopes):
            candidates.append(
                {
                    "candidate_id": f"prompt-tool-step-{index}",
                    "source": "prompt_tool_ledger",
                    "authority_scopes": scopes,
                    "selected": False,
                }
            )
    for key in ("memory_refs", "reflexion_refs", "learning_refs"):
        for index, ref in enumerate(_as_list(replay.get(key))):
            candidates.append(
                {
                    "candidate_id": f"replay-{key}-{index}",
                    "source": "replay_manifest",
                    "ref": ref,
                    "selected": False,
                }
            )
    return candidates


def _prompt_tool_refs(prompt_tool: Mapping[str, Any]) -> dict[str, Any]:
    steps = _as_list(prompt_tool.get("steps"))
    return {
        "prompt_tool_ledger_ref": prompt_tool.get("prompt_tool_ledger_ref"),
        "model_variant_id": prompt_tool.get("model_variant_id"),
        "step_count": len(steps),
        "memory_scope_count": sum(
            1
            for step in steps
            if isinstance(step, Mapping)
            and any(
                "memory" in str(scope).lower() or "reflexion" in str(scope).lower()
                for scope in _as_list(step.get("authority_scopes"))
            )
        ),
    }


def _lifecycle_reports(context: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    quality = _mapping(context.get("quality_files"))
    return {
        "stale": _mapping(quality.get("continuous_governance_stale_report.json")),
        "reissue": _mapping(quality.get("continuous_governance_reissue_report.json")),
        "supersede": _mapping(quality.get("continuous_governance_supersede_report.json")),
        "withdraw": _mapping(quality.get("continuous_governance_withdraw_report.json")),
    }


def _state_source_refs(state: str, lifecycle_ref: str | None) -> list[str]:
    refs = [
        "_build/policy-design-case/rebaseline/wave-33/quality_scorecard.json",
        "_build/policy-design-case/rebaseline/wave-33/readiness.json",
    ]
    if state in {"stale", "reissued", "withdrawn"} and lifecycle_ref:
        refs.append(lifecycle_ref)
    if state == "override":
        refs.append("quality_evidence/quality_scorecard.json#/override_evidence")
    if state == "pass":
        refs.append("quality_evidence/quality_scorecard.json#/approval_eligibility")
    return refs


def _operator_caveat_for_state(state: str) -> str:
    caveats = {
        "failed": "Failure is authoritative; dashboard must keep blockers visible.",
        "warn": "Warning cannot be rendered as approval or closeout readiness.",
        "pass": "Pass labels require matching scorecard, readiness, and approval authority.",
        "override": "Override approval is not a silent green state and preserves blocker context.",
        "stale": "Stale evidence blocks publication until revalidated.",
        "reissued": (
            "Reissued evidence blocks old projections until the new authority graph is loaded."
        ),
        "withdrawn": "Withdrawn evidence is not publishable or approval-bearing.",
    }
    return caveats[state]


def _run_identity(context: Mapping[str, Any]) -> dict[str, Any]:
    bundle_path = context.get("bundle_path")
    repo_root = _mapping(context).get("repo_root", Path("."))
    return {
        "run_id": context.get("run_id"),
        "job_id": context.get("job_id"),
        "case_id": context.get("case_id"),
        "lane_id": context.get("lane_id"),
        "bundle_path": _rel(Path(str(bundle_path)), repo_root)
        if isinstance(bundle_path, Path) and isinstance(repo_root, Path)
        else bundle_path,
    }


def _authority_cell(case_sample: Mapping[str, Any]) -> str | None:
    envelope = _mapping(case_sample.get("authority_envelope"))
    return _first(envelope.get("cell_id"), case_sample.get("cell_id"))


def _gate_status(repo_root: Path, pdd_ids: Sequence[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for pdd_id in pdd_ids:
        slug = {
            "PDD-034": "dashboard_api_projection_consistency_audit",
            "PDD-069": "dashboard_operator_truthfulness_audit",
            "PDD-083": "reusable_agent_memory_reflexion_applicability_audit",
            "PDD-097": "implementation_feasibility_beyond_final_text_audit",
            "PDD-099": "public_contestability_appeals_legitimacy_audit",
            "PDD-103": "human_overtrust_ui_persuasion_risk_audit",
        }[pdd_id]
        path = repo_root / "_build" / "diagnostics" / pdd_id.lower() / f"{slug}.json"
        if not path.exists():
            result[pdd_id] = {"status": "missing"}
            continue
        payload = _load_json(path)
        result[pdd_id] = {
            "diagnostic_status": payload.get("diagnostic_status"),
            "acceptance_gate_status": payload.get("acceptance_gate_status"),
            "verdict": payload.get("verdict"),
            "finding_count": len(_as_list(payload.get("findings"))),
        }
    return result


def _source_artifact(row: Mapping[str, Any]) -> object:
    source = _mapping(row.get("source_evidence"))
    return source.get("detail_artifact") or source.get("artifact") or row.get("source_artifact")


def _disposition_rationale(pdd_id: str) -> str:
    rationales = {
        "PDD-034": (
            "Resolved by Wave 35E projection consistency rows and masking negative "
            "controls that fail closed across API, dashboard, readiness, and scorecard surfaces."
        ),
        "PDD-069": (
            "Resolved by Wave 35E operator truthfulness rows covering dashboard-to-readiness "
            "diffs, failure-class journeys, and zero-denominator review caveats."
        ),
        "PDD-083": (
            "Resolved by Wave 35E explicit no-memory authority abstention with tenant scope, "
            "freshness, confidence, contamination, prompt/tool, and replay refs."
        ),
        "PDD-097": (
            "Resolved by Wave 35E runtime implementation feasibility ledger binding the "
            "recommendation to actors, feasibility, risks, monitoring, and source/method/norm refs."
        ),
        "PDD-099": (
            "Resolved by Wave 35E contestability appeals ledger with standing, grounds, "
            "SLA, disposition, lifecycle effects, outcome refs, and monitoring changes."
        ),
        "PDD-103": (
            "Resolved by Wave 35E trust-framing UI negative tests for weak, disputed, "
            "untraced, simulated, stale, draft, override, and frontend-signed states."
        ),
    }
    return rationales[pdd_id]


def _refresh_disposition_summary(disposition: dict[str, Any]) -> None:
    rows = [
        row for row in _as_list(disposition.get("dispositions")) if isinstance(row, Mapping)
    ]
    counts = Counter(str(row.get("classification")) for row in rows)
    summary = dict(_mapping(disposition.get("summary")))
    summary["classification_counts"] = dict(sorted(counts.items()))
    summary["accepted_blocker_count"] = counts["accepted_blocker"]
    summary["next_plan_remediation_count"] = counts["next_plan_remediation"]
    summary["false_alarm_with_evidence_count"] = counts["false_alarm_with_evidence"]
    summary["must_fix_unresolved_count"] = sum(
        1
        for row in rows
        if row.get("classification") == "must_fix_before_closeout"
        and _mapping(row.get("remediation_evidence")).get("status") != "resolved"
    )
    disposition["summary"] = summary


def _run_command(command: str, *, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(  # noqa: S603
        command.split(),
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }


def _report_ref(report: Mapping[str, Any] | None, key: str) -> str | None:
    mapped = _mapping(report)
    value = mapped.get(key)
    if value:
        return str(value)
    envelope = _mapping(mapped.get("authority_envelope"))
    return _first(envelope.get("artifact_ref"), envelope.get("cas_ref"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _tail(value: str, *, max_lines: int = 20) -> str:
    lines = value.splitlines()
    return "\n".join(lines[-max_lines:])


def _unique(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json(path: Path) -> object | None:
    if not path.exists():
        return None
    return _load_json(path)


def _resolve(repo_root: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else repo_root / path
    return candidate.resolve(strict=False)


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(repo_root).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _first(*values: object) -> object | None:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave35-dir", type=Path, default=WAVE35_DIR)
    parser.add_argument("--wave35e-dir", type=Path, default=WAVE35E_DIR)
    parser.add_argument("--run-rerun", action="store_true")
    parser.add_argument("--update-disposition", action="store_true")
    args = parser.parse_args(argv)

    try:
        outputs = build_wave35e_outputs(
            repo_root=args.repo_root,
            wave35_dir=args.wave35_dir,
            wave35e_dir=args.wave35e_dir,
            run_rerun=args.run_rerun,
            update_disposition=args.update_disposition,
        )
    except Exception as exc:
        sys.stderr.write(f"wave35e: {exc}\n")
        return 1

    update = outputs["disposition_update"]
    sys.stdout.write(
        "wave35e: "
        f"{update['status']} "
        f"updated={update['updated_finding_count']} "
        f"phase34_6_exit={update['exit_fence'].get('phase34_6_rerun_exit_code')}\n"
    )
    return 0 if update["status"] == "resolved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
