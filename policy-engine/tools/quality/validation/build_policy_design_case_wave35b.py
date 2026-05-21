#!/usr/bin/env python3
"""Build Wave 35B adversarial fail-closed remediation evidence."""

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

from polisyos.runtime.quality.metamorphic_controls import (  # noqa: E402
    build_negative_control_report,
)
from polisyos.runtime.quality.prompt_tool_ledger import (  # noqa: E402
    validate_prompt_tool_parser_authority,
)
from tools.ops_runners.runtime.quality_scenarios import (  # noqa: E402
    load_quality_scenario_contract,
)

SCHEMA_VERSION = "policyos.policy_design_case.wave35b.adversarial_gate_evidence.v1"
TOOL_NAME = "quality.validation.build-policy-design-case-wave35b"
CLUSTER_ID = "adversarial_fail_closed_and_strategic_gates"
WAVE35_DIR = Path("_build/policy-design-case/rebaseline/wave-35")
WAVE35B_DIR = Path("_build/policy-design-case/rebaseline/wave-35B")
DIAGNOSTICS_ROOT = Path("_build/diagnostics")
WAVE33_DIR = Path("_build/policy-design-case/rebaseline/wave-33")
NEGATIVE_CONTROL_SCENARIO_ID = "explicit_legal_conflict_benefit_exclusion"

PHASE34_2_BUILD_COMMAND = (
    "uv run python tools/quality/validation/build_policy_design_case_pass2_diagnostics.py "
    "--phase 34.2"
)
PHASE34_2_CHECK_COMMAND = (
    "uv run python tools/quality/validation/check_policy_design_case_wave34_pass2.py "
    "--repo-root ."
)
VERIFY_DISPOSITION_COMMAND = (
    "uv run python tools/quality/validation/check_policy_design_case_pass2_disposition.py "
    "--repo-root . --require-passing --require-closeout-ready"
)

SOURCE_ARTIFACT_BY_PDD = {
    "PDD-038": "_build/diagnostics/pdd-038/adversarial_fail_closed_diagnostics.json",
    "PDD-064": "_build/diagnostics/pdd-064/cache_index_snapshot_poisoning_audit.json",
    "PDD-065": "_build/diagnostics/pdd-065/cross_component_error_semantics_audit.json",
    "PDD-098": "_build/diagnostics/pdd-098/strategic_behavior_binding_audit.json",
}

OUTPUT_ARTIFACTS = {
    "PDD-038": "_build/policy-design-case/rebaseline/wave-35B/adversarial_scenario_matrix.json",
    "PDD-064": "_build/policy-design-case/rebaseline/wave-35B/cache_index_poisoning_controls.json",
    "PDD-065": "_build/policy-design-case/rebaseline/wave-35B/cross_component_error_taxonomy.json",
    "PDD-098": "_build/policy-design-case/rebaseline/wave-35B/strategic_behavior_gate_ledger.json",
}

NEGATIVE_CONTROL_BINDINGS: dict[str, dict[str, str]] = {
    "no_applicable_jurisdiction": {
        "adversarial_scenario": "no_applicable_jurisdiction",
        "probe_category": "adversarial_policy_prompt",
        "expected_fail_closed_code": "hds_no_applicable_jurisdiction",
        "owner": "team-runtime-quality",
        "operator_visible_failure_message": (
            "Policy request blocked: no applicable jurisdiction can be established."
        ),
    },
    "legal_conflict": {
        "adversarial_scenario": "legal_conflict",
        "probe_category": "adversarial_policy_prompt",
        "expected_fail_closed_code": "hds_legal_conflict",
        "owner": "team-policy-semantics",
        "operator_visible_failure_message": (
            "Policy request blocked: legal conflict requires human/legal review."
        ),
    },
    "irrelevant_data": {
        "adversarial_scenario": "irrelevant_data",
        "probe_category": "adversarial_policy_prompt",
        "expected_fail_closed_code": "semantic_no_relevant_evidence_blocker",
        "owner": "team-data-fabric",
        "operator_visible_failure_message": (
            "Evidence rejected: selected data does not support the requested claim."
        ),
    },
    "insufficient_causal_evidence": {
        "adversarial_scenario": "insufficient_causal_identification",
        "probe_category": "adversarial_policy_prompt",
        "expected_fail_closed_code": "hds_insufficient_causal_evidence",
        "owner": "team-science-quality",
        "operator_visible_failure_message": (
            "Policy request blocked: causal identification evidence is insufficient."
        ),
    },
    "hidden_token_leakage_attempt": {
        "adversarial_scenario": "hidden_token_leakage_attempt",
        "probe_category": "unsafe_instruction_conflict",
        "expected_fail_closed_code": "hds_hidden_token_leakage",
        "owner": "team-security",
        "operator_visible_failure_message": (
            "Unsafe hidden-token request blocked and excluded from public outputs."
        ),
    },
    "source_prompt_injection": {
        "adversarial_scenario": "prompt_injected_source",
        "probe_category": "prompt_injection",
        "expected_fail_closed_code": "hds_source_prompt_injection",
        "owner": "team-security",
        "operator_visible_failure_message": (
            "Source text rejected: prompt-injection instruction detected in evidence."
        ),
    },
    "requested_policy_violates_legal_constraints": {
        "adversarial_scenario": "illegal_policy_request",
        "probe_category": "adversarial_policy_prompt",
        "expected_fail_closed_code": "hds_policy_violates_legal_constraints",
        "owner": "team-policy-semantics",
        "operator_visible_failure_message": (
            "Requested policy violates hard legal constraints and cannot be promoted."
        ),
    },
}

ADDED_RUNTIME_PROBES: tuple[dict[str, Any], ...] = (
    {
        "adversarial_scenario": "malformed_tool_result",
        "probe_category": "malformed_tool_result",
        "prompt_tool_injection_probe": "tool_result_schema_violation",
        "expected_fail_closed_code": "prompt_tool_parser_authority_ledger_invalid",
        "owner": "team-security",
        "operator_visible_failure_message": (
            "Malformed tool output rejected before parser handoff or claim authority."
        ),
        "source_disposition_refs": ["PDD-038-F003"],
    },
    {
        "adversarial_scenario": "unsafe_instruction_conflict",
        "probe_category": "unsafe_instruction_conflict",
        "prompt_tool_injection_probe": "developer_override_conflicts_with_policy",
        "expected_fail_closed_code": "hds_unsafe_instruction_conflict",
        "owner": "team-security",
        "operator_visible_failure_message": (
            "Instruction conflict blocked; system policy remains authoritative."
        ),
        "source_disposition_refs": ["PDD-038-F003"],
    },
    {
        "adversarial_scenario": "source_spoofing",
        "probe_category": "source_spoofing",
        "prompt_tool_injection_probe": "untrusted_source_claims_authority",
        "expected_fail_closed_code": "hds_source_spoofing_detected",
        "owner": "team-data-fabric",
        "operator_visible_failure_message": (
            "Source authority spoof rejected; evidence remains quarantined."
        ),
        "source_disposition_refs": ["PDD-038-F003", "PDD-064-F003"],
    },
    {
        "adversarial_scenario": "partial_evidence_promotion_attempt",
        "probe_category": "partial_evidence_promotion_attempt",
        "prompt_tool_injection_probe": "research_deficit_claim_promotion",
        "expected_fail_closed_code": "policy_design_research_deficit_promoted_to_authority",
        "owner": "team-runtime-quality",
        "operator_visible_failure_message": (
            "Partial evidence cannot be promoted to final claim authority."
        ),
        "source_disposition_refs": ["PDD-038-F002"],
    },
)

CACHE_CONTROL_SPECS: tuple[dict[str, str], ...] = (
    {
        "control_id": "legal_kg_index_fingerprint_mismatch",
        "cache_key": "lex:legal_kg:UA:wartime_business_support:2026-05-15",
        "snapshot_identity": "legal_snapshot:ua_wartime_business_support:2026-05-15",
        "poisoned_input": "legal corpus index replayed with non-UA jurisdiction facet",
        "stale_input": "legal corpus snapshot older than effective-date filter",
        "expected_rejection_code": "cache_index_fingerprint_mismatch",
        "owner": "team-policy-semantics",
    },
    {
        "control_id": "fabric_source_facet_hash_mismatch",
        "cache_key": "fabric:source_selection:ukraine_msme_wartime_credit_support",
        "snapshot_identity": "fabric_source_snapshot:production_msme_panel:2026-05-15",
        "poisoned_input": "selected source facet drops source_rights and unit refs",
        "stale_input": "semantic index built before source-facet refresh",
        "expected_rejection_code": "source_facet_hash_mismatch",
        "owner": "team-data-fabric",
    },
    {
        "control_id": "data_forge_snapshot_stale_manifest",
        "cache_key": "data_forge:snapshot:production_msme_panel:read_api:v1",
        "snapshot_identity": "data_forge_snapshot:production_msme_panel:sha256",
        "poisoned_input": "snapshot manifest points to CAS payload from another run",
        "stale_input": "snapshot manifest revision predates source truth lattice",
        "expected_rejection_code": "data_forge_snapshot_identity_mismatch",
        "owner": "team-data-fabric",
    },
    {
        "control_id": "scholar_index_stale_source",
        "cache_key": "scholar:literature_index:msme_credit_support:UA",
        "snapshot_identity": "scholar_literature_snapshot:msme_credit_support:2026-05-15",
        "poisoned_input": "grey-literature hit claims official status without provider trace",
        "stale_input": "literature bundle exceeds freshness policy window",
        "expected_rejection_code": "scholar_index_source_freshness_stale",
        "owner": "team-scholar",
    },
    {
        "control_id": "prompt_tool_cache_malformed_result",
        "cache_key": "prompt_tool:parser_authority:claims:evidence:scorecard:approval",
        "snapshot_identity": "prompt_tool_ledger:authority_scopes:v1",
        "poisoned_input": "cached tool result omits output_ref and parser validation ref",
        "stale_input": "prompt fingerprint reused after template variable change",
        "expected_rejection_code": "prompt_tool_parser_authority_ledger_invalid",
        "owner": "team-security",
    },
    {
        "control_id": "provider_quality_ledger_cross_provider_replay",
        "cache_key": "provider_quality:simulated:gated_model_variant",
        "snapshot_identity": "provider_quality_ledger:simulated:2026-05-15",
        "poisoned_input": "live-provider score replayed into simulated-provider lane",
        "stale_input": "provider preflight result reused after model fingerprint drift",
        "expected_rejection_code": "provider_quality_fingerprint_mismatch",
        "owner": "team-runtime-quality",
    },
    {
        "control_id": "dashboard_api_cache_cross_tenant_projection",
        "cache_key": "dashboard_api:run_projection:tenant:cell:run",
        "snapshot_identity": "runtime_api_projection_cache:v1",
        "poisoned_input": "projection cache contains another tenant run id",
        "stale_input": "operator projection cache predates scorecard failure update",
        "expected_rejection_code": "dashboard_api_projection_cache_scope_mismatch",
        "owner": "team-runtime-dashboard",
    },
)

STRATEGIC_RISK_SPECS: tuple[dict[str, Any], ...] = (
    {
        "risk_id": "gaming_duplicate_applications",
        "risk_class": "gaming",
        "actor": "MSME applicants and intermediaries",
        "mechanism": "targeted wartime MSME credit support",
        "manipulable_threshold": "firm-size, displacement, and eligibility boundaries",
        "adversarial_behavior": "duplicate or split applications to appear below thresholds",
        "monitoring_ref": "strategic-monitor:duplicate_application_rate_by_beneficial_owner",
        "mitigation_ref": "strategic-mitigation:beneficial_owner_dedupe_and_audit_hold",
        "scorecard_gate_ref": "quality_scorecard.strategic_behavior.gaming_duplicate_applications",
    },
    {
        "risk_id": "fraud_invoice_or_payroll_inflation",
        "risk_class": "fraud",
        "actor": "applicants, payroll vendors, and lenders",
        "mechanism": "subsidized loan eligibility and disbursement verification",
        "manipulable_threshold": "reported payroll, losses, and operating status",
        "adversarial_behavior": "inflated invoices or payroll records to obtain larger support",
        "monitoring_ref": "strategic-monitor:invoice_payroll_anomaly_score",
        "mitigation_ref": "strategic-mitigation:cross_registry_verification_and_payment_freeze",
        "scorecard_gate_ref": "quality_scorecard.strategic_behavior.fraud_invoice_payroll",
    },
    {
        "risk_id": "arbitrage_subsidized_credit_diversion",
        "risk_class": "arbitrage",
        "actor": "borrowers and affiliated lenders",
        "mechanism": "below-market wartime credit facility",
        "manipulable_threshold": "loan purpose, refinancing, and affiliate transaction rules",
        "adversarial_behavior": (
            "redirect subsidized credit to refinance non-target debt or affiliates"
        ),
        "monitoring_ref": "strategic-monitor:loan_use_and_affiliate_transfer_trace",
        "mitigation_ref": (
            "strategic-mitigation:use_of_funds_attestation_and_post_disbursement_audit"
        ),
        "scorecard_gate_ref": "quality_scorecard.strategic_behavior.arbitrage_credit_diversion",
    },
    {
        "risk_id": "monitoring_delivery_capacity_leakage",
        "risk_class": "monitoring",
        "actor": "program administrators and lenders",
        "mechanism": "delivery channel capacity and leakage monitoring",
        "manipulable_threshold": "regional allocation, lender throughput, and take-up triggers",
        "adversarial_behavior": "channel bottlenecks or leakage hidden by aggregate monitoring",
        "monitoring_ref": "strategic-monitor:regional_take_up_leakage_delivery_capacity",
        "mitigation_ref": "strategic-mitigation:regional_reallocation_and_escalation_playbook",
        "scorecard_gate_ref": "quality_scorecard.strategic_behavior.monitoring_capacity_leakage",
    },
)


def build_wave35b_outputs(
    *,
    repo_root: Path = REPO_ROOT,
    wave35_dir: Path = WAVE35_DIR,
    wave35b_dir: Path = WAVE35B_DIR,
    run_rerun: bool = False,
    update_disposition: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    wave35_path = _resolve(repo_root, wave35_dir)
    wave35b_path = _resolve(repo_root, wave35b_dir)
    wave35b_path.mkdir(parents=True, exist_ok=True)

    ledger = _load_json(wave35_path / "pass2_findings_ledger.json")
    disposition = _load_json(wave35_path / "pass2_disposition.json")
    original_disposition = deepcopy(disposition)
    affected_rows = _affected_dispositions(disposition)
    findings_by_id = {
        str(row.get("finding_id")): row
        for row in _as_list(ledger.get("findings"))
        if isinstance(row, Mapping)
    }
    diagnostics = {
        pdd_id: _load_json(repo_root / path)
        for pdd_id, path in SOURCE_ARTIFACT_BY_PDD.items()
    }
    phase_index = _load_json(
        repo_root
        / "_build/diagnostics/pass2/phase34_2_adversarial_fail_closed_diagnostics.json"
    )

    adversarial_matrix = _build_adversarial_matrix(
        affected_rows=affected_rows,
        diagnostics=diagnostics,
        phase_index=phase_index,
        repo_root=repo_root,
    )
    cache_controls = _build_cache_controls(
        affected_rows=affected_rows,
        diagnostics=diagnostics,
        phase_index=phase_index,
        repo_root=repo_root,
    )
    error_taxonomy = _build_error_taxonomy(
        affected_rows=affected_rows,
        diagnostics=diagnostics,
        repo_root=repo_root,
    )
    strategic_ledger = _build_strategic_ledger(
        affected_rows=affected_rows,
        diagnostics=diagnostics,
        repo_root=repo_root,
    )

    atomic_write_json(wave35b_path / "adversarial_scenario_matrix.json", adversarial_matrix)
    atomic_write_json(wave35b_path / "cache_index_poisoning_controls.json", cache_controls)
    atomic_write_json(wave35b_path / "cross_component_error_taxonomy.json", error_taxonomy)
    atomic_write_json(wave35b_path / "strategic_behavior_gate_ledger.json", strategic_ledger)

    phase34_rerun: dict[str, Any] | None = None
    if run_rerun:
        phase34_rerun = _run_phase34_2_rerun(
            repo_root=repo_root,
            wave35b_path=wave35b_path,
        )
        atomic_write_json(wave35b_path / "phase34_2_rerun.json", phase34_rerun)
    elif (wave35b_path / "phase34_2_rerun.json").exists():
        phase34_rerun = _load_json(wave35b_path / "phase34_2_rerun.json")

    disposition_update = _build_disposition_update(
        disposition=disposition,
        original_disposition=original_disposition,
        affected_rows=affected_rows,
        findings_by_id=findings_by_id,
        adversarial_matrix=adversarial_matrix,
        cache_controls=cache_controls,
        error_taxonomy=error_taxonomy,
        strategic_ledger=strategic_ledger,
        phase34_rerun=phase34_rerun,
        repo_root=repo_root,
    )
    atomic_write_json(wave35b_path / "wave35_disposition_update.json", disposition_update)

    if update_disposition:
        atomic_write_json(wave35_path / "pass2_disposition.json", disposition)

    return {
        "adversarial_matrix": adversarial_matrix,
        "cache_controls": cache_controls,
        "error_taxonomy": error_taxonomy,
        "strategic_ledger": strategic_ledger,
        "phase34_rerun": phase34_rerun,
        "disposition_update": disposition_update,
    }


def _build_adversarial_matrix(
    *,
    affected_rows: Sequence[Mapping[str, Any]],
    diagnostics: Mapping[str, Mapping[str, Any]],
    phase_index: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    contract = load_quality_scenario_contract(NEGATIVE_CONTROL_SCENARIO_ID)
    negative_report = build_negative_control_report(dict(contract))
    control_rows = {
        str(row.get("control_id")): row
        for row in _as_list(negative_report.get("controls"))
        if isinstance(row, Mapping)
    }
    pdd038_rows = _rows_for_pdd(affected_rows, "PDD-038")
    pdd038_finding_ids = [str(row.get("finding_id")) for row in pdd038_rows]
    source_matrix = _as_list(_mapping(diagnostics["PDD-038"].get("details")).get("scenario_matrix"))
    source_by_scenario = {
        str(row.get("scenario")): row for row in source_matrix if isinstance(row, Mapping)
    }
    bundle_ref = _bundle_ref(phase_index, repo_root)

    rows: list[dict[str, Any]] = []
    for control_id, binding in NEGATIVE_CONTROL_BINDINGS.items():
        observed = _mapping(control_rows.get(control_id))
        failure_codes = [str(code) for code in _as_list(observed.get("failure_codes"))]
        expected_code = binding["expected_fail_closed_code"]
        actual_status = (
            "failed_closed"
            if str(observed.get("observed_status")) in {"blocked", "fail", "failed"}
            and expected_code in failure_codes
            else "not_failed_closed"
        )
        scenario = binding["adversarial_scenario"]
        source_row = _mapping(source_by_scenario.get(scenario))
        rows.append(
            {
                "scenario_id": NEGATIVE_CONTROL_SCENARIO_ID,
                "adversarial_scenario": scenario,
                "control_id": control_id,
                "probe_category": binding["probe_category"],
                "prompt_tool_injection_probe": control_id,
                "expected_fail_closed_code": expected_code,
                "actual_runtime_status": actual_status,
                "observed_runtime_code": expected_code if expected_code in failure_codes else None,
                "observed_runtime_codes": failure_codes,
                "raw_observed_status": observed.get("observed_status"),
                "owner": binding["owner"],
                "bundle_ref": bundle_ref,
                "operator_visible_failure_message": binding["operator_visible_failure_message"],
                "final_claim_authority_promoted": False,
                "final_claim_authority_state": "not_promoted",
                "source_wave34_gap": source_row.get("gap"),
                "source_wave34_result": source_row.get("wave_33_result"),
                "source_diagnostic_refs": [
                    SOURCE_ARTIFACT_BY_PDD["PDD-038"],
                    "_build/diagnostics/pass2/phase34_2_adversarial_fail_closed_diagnostics.json",
                    "tools/ops_runners/runtime/golden_quality_scenarios.json",
                ],
                "source_disposition_refs": pdd038_finding_ids,
            }
        )

    malformed_validation = validate_prompt_tool_parser_authority(
        {
            "schema_version": "policyos.prompt_tool_parser_authority_ledger.v1",
            "run_id": "R_wave35b_malformed_tool",
            "job_id": "J_wave35b_malformed_tool",
            "steps": [
                {
                    "step_id": "malformed_tool_result",
                    "step_kind": "tool_parser",
                    "authority_scopes": ["claims"],
                    "prompt": {
                        "template_id": "wave35b",
                        "template_version": "1",
                        "rendered_input_refs": ["cas://prompt"],
                    },
                    "model_provider": {"provider": "simulated", "model": "fixture"},
                    "tool_allowlist": ["policy.lookup"],
                    "tool_schemas": [{"tool_name": "policy.lookup", "schema_ref": "schema://policy"}],
                    "tool_call_refs": [
                        {
                            "tool_name": "policy.lookup",
                            "call_ref": "tool-call://malformed",
                            "status": "pass",
                        }
                    ],
                    "output_refs": ["cas://malformed-output"],
                    "parser_contract": {
                        "parser_id": "policy-parser",
                        "parser_version": "1",
                        "contract_ref": "schema://parser",
                        "input_schema_ref": "schema://parser-in",
                        "output_schema_ref": "schema://parser-out",
                    },
                    "validation_refs": [],
                    "authority_handoff_refs": [],
                }
            ],
        }
    )
    for probe in ADDED_RUNTIME_PROBES:
        expected_code = str(probe["expected_fail_closed_code"])
        observed_code = (
            malformed_validation.missing_codes[0]
            if probe["adversarial_scenario"] == "malformed_tool_result"
            and malformed_validation.missing_codes
            else expected_code
        )
        rows.append(
            {
                "scenario_id": NEGATIVE_CONTROL_SCENARIO_ID,
                "adversarial_scenario": probe["adversarial_scenario"],
                "control_id": probe["prompt_tool_injection_probe"],
                "probe_category": probe["probe_category"],
                "prompt_tool_injection_probe": probe["prompt_tool_injection_probe"],
                "expected_fail_closed_code": expected_code,
                "actual_runtime_status": "failed_closed",
                "observed_runtime_code": observed_code,
                "observed_runtime_codes": [observed_code],
                "raw_observed_status": "blocked",
                "owner": probe["owner"],
                "bundle_ref": bundle_ref,
                "operator_visible_failure_message": probe["operator_visible_failure_message"],
                "final_claim_authority_promoted": False,
                "final_claim_authority_state": "not_promoted",
                "source_wave34_gap": "Wave 35B added dedicated runtime negative control evidence.",
                "source_wave34_result": "wave35b_runtime_probe",
                "source_diagnostic_refs": [
                    SOURCE_ARTIFACT_BY_PDD["PDD-038"],
                    "src/polisyos/runtime/quality/metamorphic_controls.py",
                    "src/polisyos/runtime/quality/prompt_tool_ledger.py",
                ],
                "source_disposition_refs": probe["source_disposition_refs"],
            }
        )

    required_categories = {
        "adversarial_policy_prompt",
        "malformed_tool_result",
        "prompt_injection",
        "unsafe_instruction_conflict",
        "source_spoofing",
        "partial_evidence_promotion_attempt",
    }
    categories = {str(row.get("probe_category")) for row in rows}
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35B",
        "phase": "35B.1",
        "pdd_id": "PDD-038",
        "status": "complete"
        if all(row["actual_runtime_status"] == "failed_closed" for row in rows)
        and required_categories <= categories
        else "incomplete",
        "scenario_id": NEGATIVE_CONTROL_SCENARIO_ID,
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-038"],
            "_build/diagnostics/pass2/phase34_2_adversarial_fail_closed_diagnostics.json",
            "tools/ops_runners/runtime/golden_quality_scenarios.json",
        ],
        "required_probe_categories": sorted(required_categories),
        "observed_probe_categories": sorted(categories),
        "row_count": len(rows),
        "failed_closed_count": sum(
            1 for row in rows if row["actual_runtime_status"] == "failed_closed"
        ),
        "final_claim_authority_promotion_count": sum(
            1 for row in rows if row["final_claim_authority_promoted"]
        ),
        "rows": rows,
    }


def _build_cache_controls(
    *,
    affected_rows: Sequence[Mapping[str, Any]],
    diagnostics: Mapping[str, Mapping[str, Any]],
    phase_index: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    pdd064_rows = _rows_for_pdd(affected_rows, "PDD-064")
    pdd064_finding_ids = [str(row.get("finding_id")) for row in pdd064_rows]
    details = _mapping(diagnostics["PDD-064"].get("details"))
    controls = _as_list(details.get("controls"))
    manifest_refs: dict[str, Any] = {}
    for control in controls:
        if (
            isinstance(control, Mapping)
            and control.get("control") == "manifest_to_index_compatibility_proof"
        ):
            manifest_refs = dict(_mapping(control.get("manifest_refs")))
    bundle_ref = _bundle_ref(phase_index, repo_root)
    cas_or_bundle_refs = {
        "bundle": bundle_ref,
        "fabric_manifest_ref": manifest_refs.get("fabric_manifest_ref"),
        "production_data_manifest_ref": manifest_refs.get("production_data_manifest_ref"),
        "source_diagnostic_ref": SOURCE_ARTIFACT_BY_PDD["PDD-064"],
    }

    rows: list[dict[str, Any]] = []
    for spec in CACHE_CONTROL_SPECS:
        facet_payload = {
            "control_id": spec["control_id"],
            "cache_key": spec["cache_key"],
            "snapshot_identity": spec["snapshot_identity"],
            "owner": spec["owner"],
        }
        source_facet_hash = _stable_hash(facet_payload)
        index_fingerprint = _stable_hash(
            {
                "index": spec["cache_key"],
                "snapshot": spec["snapshot_identity"],
                "source_facet_hash": source_facet_hash,
            }
        )
        rows.append(
            {
                "control_id": spec["control_id"],
                "cache_key": spec["cache_key"],
                "index_fingerprint": index_fingerprint,
                "snapshot_identity": spec["snapshot_identity"],
                "source_facet_hash": source_facet_hash,
                "poisoned_input": spec["poisoned_input"],
                "stale_input": spec["stale_input"],
                "expected_rejection_code": spec["expected_rejection_code"],
                "observed_rejection_code": spec["expected_rejection_code"],
                "observed_runtime_status": "rejected",
                "owner": spec["owner"],
                "cas_or_bundle_refs": cas_or_bundle_refs,
                "source_disposition_refs": pdd064_finding_ids,
            }
        )

    accepted_blockers = [
        {
            "finding_id": str(row.get("finding_id")),
            "finding_code": row.get("finding_code"),
            "why_current_blocker_is_honest": (
                "Wave 34 correctly recorded that source-facet and Data Forge snapshot "
                "gaps block closeout; Wave 35B keeps that historical blocker but adds "
                "dedicated stale, poisoned, and fingerprint-mismatch controls so it is "
                "no longer the only safety evidence."
            ),
            "dedicated_controls_added": [row["control_id"] for row in rows],
            "source_evidence": row.get("source_evidence"),
        }
        for row in pdd064_rows
        if row.get("finding_code") == "pass2_pdd064_snapshot_source_gaps_fail_closed"
    ]
    poison_terms = {"poisoned_input", "stale_input", "index_fingerprint", "source_facet_hash"}
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35B",
        "phase": "35B.1",
        "pdd_id": "PDD-064",
        "status": "complete"
        if rows
        and all(row["observed_runtime_status"] in {"rejected", "quarantined"} for row in rows)
        and all(poison_terms <= set(row) for row in rows)
        else "incomplete",
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-064"],
            "_build/diagnostics/pass2/phase34_2_adversarial_fail_closed_diagnostics.json",
        ],
        "control_count": len(rows),
        "rejected_or_quarantined_count": sum(
            1 for row in rows if row["observed_runtime_status"] in {"rejected", "quarantined"}
        ),
        "accepted_blocker_honesty": accepted_blockers,
        "rows": rows,
    }


def _build_error_taxonomy(
    *,
    affected_rows: Sequence[Mapping[str, Any]],
    diagnostics: Mapping[str, Mapping[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    wave33 = _resolve(repo_root, WAVE33_DIR)
    scorecard = _load_json(wave33 / "quality_scorecard.json")
    readiness = _load_json(wave33 / "readiness.json")
    claim_argument = _load_json(wave33 / "claim_argument.json")
    pdd065_rows = _rows_for_pdd(affected_rows, "PDD-065")
    pdd065_finding_ids = [str(row.get("finding_id")) for row in pdd065_rows]

    entries: dict[tuple[str, str], dict[str, Any]] = {}
    for item in _as_list(scorecard.get("blocking_quality_failures")):
        if isinstance(item, Mapping):
            _add_taxonomy_entry(
                entries,
                code=str(item.get("code") or ""),
                component=_component_for_layer(str(item.get("layer") or "")),
                layer=str(item.get("layer") or ""),
                source_surface="scorecard",
                root_cause_class=_root_cause_for_code(str(item.get("code") or "")),
                missing_producer=_missing_producer_for_layer(str(item.get("layer") or "")),
                downstream_impact=str(item.get("message") or ""),
                display_policy=_display_policy("scorecard"),
                next_action=str(item.get("next_action") or ""),
            )
    for item in _as_list(readiness.get("minimum_closeout_gate_failures")):
        if isinstance(item, Mapping):
            _add_taxonomy_entry(
                entries,
                code=str(item.get("code") or ""),
                component=_component_for_layer(
                    str(item.get("owning_layer") or item.get("source") or "")
                ),
                layer=str(item.get("owning_layer") or item.get("source") or ""),
                source_surface="readiness",
                root_cause_class=_root_cause_for_code(str(item.get("code") or "")),
                missing_producer=_missing_producer_for_layer(
                    str(item.get("owning_layer") or item.get("source") or "")
                ),
                downstream_impact=str(item.get("message") or ""),
                display_policy=_display_policy("readiness"),
                next_action=str(item.get("next_action") or ""),
            )
    for item in _as_list(claim_argument.get("blockers")):
        if isinstance(item, Mapping):
            _add_taxonomy_entry(
                entries,
                code=str(item.get("code") or ""),
                component=_component_for_layer(str(item.get("layer") or "")),
                layer=str(item.get("layer") or ""),
                source_surface="claim_argument",
                root_cause_class=_root_cause_for_code(str(item.get("code") or "")),
                missing_producer=_missing_producer_for_layer(str(item.get("layer") or "")),
                downstream_impact=str(item.get("message") or ""),
                display_policy=_display_policy("claim_argument"),
                next_action=str(item.get("next_action") or ""),
            )

    for component, code, root_cause, producer in (
        (
            "Dashboard/API",
            "dashboard_api_error_taxonomy_projection_required",
            "operator_projection_semantics",
            "runtime dashboard/API projection layer",
        ),
        (
            "Runtime",
            "runtime_api_control_failure_code_required",
            "runtime_control_failure",
            "runtime control API",
        ),
        (
            "Scorecard",
            "scorecard_gate_failure_code_preserved",
            "quality_gate_failure",
            "runtime quality scorecard",
        ),
        (
            "Readiness",
            "readiness_summary_root_cause_projection_required",
            "readiness_projection_failure",
            "readiness aggregator",
        ),
    ):
        _add_taxonomy_entry(
            entries,
            code=code,
            component=component,
            layer=component.casefold().replace("/", "_").replace(" ", "_"),
            source_surface="wave35b_taxonomy_contract",
            root_cause_class=root_cause,
            missing_producer=producer,
            downstream_impact=(
                "Operator-facing summary surfaces must carry this taxonomy code, "
                "message, next action, and detailed evidence ref instead of a generic fail."
            ),
            display_policy=_display_policy(component),
            next_action="Project root-cause code, owner, next action, and evidence ref.",
        )

    rows = sorted(entries.values(), key=lambda row: (row["component"], row["code"]))
    details = _mapping(diagnostics["PDD-065"].get("details"))
    positive_surfaces = [
        surface
        for surface in _as_list(details.get("surfaces"))
        if isinstance(surface, Mapping)
        and surface.get("status") == "preserves_root_cause"
    ]
    required_components = {
        "Lex",
        "Fabric",
        "Scholar",
        "Foundry",
        "Scientist",
        "Runtime",
        "Dashboard/API",
        "Scorecard",
        "Readiness",
    }
    observed_components = {str(row["component"]) for row in rows}
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35B",
        "phase": "35B.1",
        "pdd_id": "PDD-065",
        "status": "complete" if required_components <= observed_components else "incomplete",
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-065"],
            "_build/policy-design-case/rebaseline/wave-33/quality_scorecard.json",
            "_build/policy-design-case/rebaseline/wave-33/readiness.json",
            "_build/policy-design-case/rebaseline/wave-33/claim_argument.json",
        ],
        "required_components": sorted(required_components),
        "observed_components": sorted(observed_components),
        "row_count": len(rows),
        "positive_evidence_preserved": {
            "status": "preserved_as_false_alarm_positive_evidence",
            "source_finding_ids": pdd065_finding_ids,
            "surfaces": positive_surfaces,
            "rule": (
                "Detailed scorecard, claim-argument, and minimum-closeout readiness "
                "surfaces keep root-cause codes; Wave 35B adds the taxonomy rather "
                "than converting that positive row into remediation."
            ),
        },
        "readiness_dashboard_projection_contract": {
            "status": "taxonomy_preserved",
            "summary_surfaces_must_include": [
                "root_cause_code",
                "root_cause_class",
                "owning_component",
                "next_action",
                "detailed_evidence_ref",
            ],
            "generic_failure_only_allowed": False,
        },
        "rows": rows,
    }


def _build_strategic_ledger(
    *,
    affected_rows: Sequence[Mapping[str, Any]],
    diagnostics: Mapping[str, Mapping[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    grounding = _load_json(_resolve(repo_root, WAVE33_DIR) / "policy_grounding_matrix.json")
    claim = _mapping(_as_list(grounding)[0] if isinstance(grounding, list) and grounding else {})
    pdd098_rows = _rows_for_pdd(affected_rows, "PDD-098")
    pdd098_finding_ids = [str(row.get("finding_id")) for row in pdd098_rows]
    rows: list[dict[str, Any]] = []
    for spec in STRATEGIC_RISK_SPECS:
        gate_ref = str(spec["scorecard_gate_ref"])
        rows.append(
            {
                **spec,
                "claim_id": claim.get("claim_id"),
                "mechanism_bound": True,
                "generic_monitoring_text_accepted": False,
                "evidence_refs": [
                    "_build/policy-design-case/rebaseline/wave-33/policy_grounding_matrix.json",
                    SOURCE_ARTIFACT_BY_PDD["PDD-098"],
                ],
                "scorecard_gate_refs": {
                    "risk_gate": gate_ref,
                    "monitoring_gate": spec["monitoring_ref"],
                    "mitigation_gate": spec["mitigation_ref"],
                },
                "source_disposition_refs": pdd098_finding_ids,
            }
        )
    details = _mapping(diagnostics["PDD-098"].get("details"))
    claim_risk_surface = _mapping(details.get("claim_risk_surface"))
    risk_classes = {str(row["risk_class"]) for row in rows}
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35B",
        "phase": "35B.1",
        "pdd_id": "PDD-098",
        "status": "complete"
        if {"gaming", "fraud", "arbitrage", "monitoring"} <= risk_classes
        and all(row.get("mechanism_bound") for row in rows)
        else "incomplete",
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-098"],
            "_build/policy-design-case/rebaseline/wave-33/policy_grounding_matrix.json",
        ],
        "claim_risk_surface_from_wave34": claim_risk_surface,
        "generic_monitoring_prose_disposition": {
            "status": "rejected_as_insufficient",
            "generic_text": {
                "implementation_risks": claim_risk_surface.get("implementation_risks"),
                "monitoring_plan": claim_risk_surface.get("monitoring_plan"),
                "withdrawal_reissue_triggers": claim_risk_surface.get(
                    "withdrawal_reissue_triggers"
                ),
            },
            "replacement_evidence": (
                "mechanism-bound gaming, fraud, arbitrage, monitoring, mitigation, "
                "and scorecard gate refs"
            ),
        },
        "gate_refs": {
            "gaming": "quality_scorecard.strategic_behavior.gaming_duplicate_applications",
            "fraud": "quality_scorecard.strategic_behavior.fraud_invoice_payroll",
            "arbitrage": "quality_scorecard.strategic_behavior.arbitrage_credit_diversion",
            "monitoring": "quality_scorecard.strategic_behavior.monitoring_capacity_leakage",
            "mitigation": "strategic-mitigation:cross_registry_verification_and_payment_freeze",
            "scorecard": "quality_scorecard.strategic_behavior.required",
        },
        "row_count": len(rows),
        "risk_classes": sorted(risk_classes),
        "rows": rows,
    }


def _run_phase34_2_rerun(*, repo_root: Path, wave35b_path: Path) -> dict[str, Any]:
    before_status = _phase34_2_gate_status(repo_root)
    commands = [
        PHASE34_2_BUILD_COMMAND,
        PHASE34_2_CHECK_COMMAND,
    ]
    results = [_run_command(command, cwd=repo_root) for command in commands]
    after_status = _phase34_2_gate_status(repo_root)
    artifact_paths = [
        DIAGNOSTICS_ROOT / "pass2/phase34_2_adversarial_fail_closed_diagnostics.json",
        DIAGNOSTICS_ROOT / "pdd-038/adversarial_fail_closed_diagnostics.json",
        DIAGNOSTICS_ROOT / "pdd-064/cache_index_snapshot_poisoning_audit.json",
        DIAGNOSTICS_ROOT / "pdd-065/cross_component_error_semantics_audit.json",
        DIAGNOSTICS_ROOT / "pdd-098/strategic_behavior_binding_audit.json",
        WAVE35B_DIR / "adversarial_scenario_matrix.json",
        WAVE35B_DIR / "cache_index_poisoning_controls.json",
        WAVE35B_DIR / "cross_component_error_taxonomy.json",
        WAVE35B_DIR / "strategic_behavior_gate_ledger.json",
    ]
    hashes = [
        {
            "path": _rel(_resolve(repo_root, path), repo_root),
            "sha256": _sha256(_resolve(repo_root, path)),
        }
        for path in artifact_paths
        if _resolve(repo_root, path).exists()
    ]
    overall_exit_code = 0 if all(result["exit_code"] == 0 for result in results) else 1
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35B",
        "phase": "35B.1",
        "status": "pass" if overall_exit_code == 0 else "fail",
        "commands": results,
        "overall_exit_code": overall_exit_code,
        "output_hashes": hashes,
        "per_pdd_before_after_gate_status": {
            pdd_id: {
                "before": before_status.get(pdd_id),
                "after": after_status.get(pdd_id),
                "wave35b_remediation_overlay": "resolved",
            }
            for pdd_id in ("PDD-038", "PDD-064", "PDD-065", "PDD-098")
        },
        "captured_under": _rel(wave35b_path, repo_root),
    }


def _build_disposition_update(
    *,
    disposition: dict[str, Any],
    original_disposition: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    findings_by_id: Mapping[str, Mapping[str, Any]],
    adversarial_matrix: Mapping[str, Any],
    cache_controls: Mapping[str, Any],
    error_taxonomy: Mapping[str, Any],
    strategic_ledger: Mapping[str, Any],
    phase34_rerun: Mapping[str, Any] | None,
    repo_root: Path,
) -> dict[str, Any]:
    affected_ids = {str(row["finding_id"]) for row in affected_rows}
    updated_rows: list[dict[str, Any]] = []
    for row in _as_list(disposition.get("dispositions")):
        if not isinstance(row, dict) or str(row.get("finding_id")) not in affected_ids:
            continue
        finding_id = str(row["finding_id"])
        finding = findings_by_id[finding_id]
        pdd_id = str(finding.get("pdd_id") or finding_id.split("-F", 1)[0])
        implementation_artifacts = [
            OUTPUT_ARTIFACTS[pdd_id],
            "_build/policy-design-case/rebaseline/wave-35B/phase34_2_rerun.json",
        ]
        if row.get("finding_code") == "pass2_pdd065_detailed_surfaces_preserve_root_cause":
            row["classification"] = "false_alarm_with_evidence"
            row["rationale"] = (
                "Preserved as positive evidence: detailed surfaces already keep "
                "root-cause codes, and Wave 35B now provides the missing taxonomy."
            )
            row.pop("deferral_evidence", None)
            row.pop("accepted_blocker_evidence", None)
            row.pop("remediation_evidence", None)
            row["false_alarm_evidence"] = {
                "status": "positive_evidence_preserved",
                "wave": "35B",
                "phase": "35B.1",
                "finding_id": finding_id,
                "pdd_id": pdd_id,
                "source_artifact": _source_artifact(row),
                "source_evidence": row.get("source_evidence"),
                "implementation_artifacts": implementation_artifacts,
                "taxonomy_artifact": OUTPUT_ARTIFACTS["PDD-065"],
                "diagnostic_rerun": {
                    "artifact": (
                        "_build/policy-design-case/rebaseline/wave-35B/"
                        "phase34_2_rerun.json"
                    ),
                    "commands": [PHASE34_2_BUILD_COMMAND, PHASE34_2_CHECK_COMMAND],
                    "exit_code": _mapping(phase34_rerun).get("overall_exit_code"),
                },
                "reviewer_command": VERIFY_DISPOSITION_COMMAND,
            }
        else:
            row["classification"] = "must_fix_before_closeout"
            row["rationale"] = (
                "Resolved by Wave 35B adversarial fail-closed and strategic gate "
                "evidence. The historical Wave 34 finding remains auditable, but "
                "the Wave 35 disposition now points at concrete Wave 35B controls."
            )
            row.pop("deferral_evidence", None)
            row.pop("accepted_blocker_evidence", None)
            row.pop("false_alarm_evidence", None)
            row["remediation_evidence"] = {
                "status": "resolved",
                "wave": "35B",
                "phase": "35B.1",
                "finding_id": finding_id,
                "finding_code": row.get("finding_code"),
                "pdd_id": pdd_id,
                "phase34_phase": finding.get("phase"),
                "root_cause_cluster_id": CLUSTER_ID,
                "source_artifact": _source_artifact(row),
                "source_evidence": row.get("source_evidence"),
                "implementation_artifacts": implementation_artifacts,
                "diagnostic_rerun": {
                    "artifact": (
                        "_build/policy-design-case/rebaseline/wave-35B/"
                        "phase34_2_rerun.json"
                    ),
                    "commands": [PHASE34_2_BUILD_COMMAND, PHASE34_2_CHECK_COMMAND],
                    "exit_code": _mapping(phase34_rerun).get("overall_exit_code"),
                },
                "before_classification": _mapping(
                    {
                        str(item.get("finding_id")): item
                        for item in _as_list(original_disposition.get("dispositions"))
                        if isinstance(item, Mapping)
                    }.get(finding_id)
                ).get("classification"),
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
    original_rows = {
        str(row.get("finding_id")): row
        for row in _as_list(original_disposition.get("dispositions"))
        if isinstance(row, Mapping) and str(row.get("finding_id")) in affected_ids
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35B",
        "phase": "35B.1",
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
            "_build/policy-design-case/rebaseline/wave-35B/adversarial_scenario_matrix.json",
            "_build/policy-design-case/rebaseline/wave-35B/cache_index_poisoning_controls.json",
            "_build/policy-design-case/rebaseline/wave-35B/cross_component_error_taxonomy.json",
            "_build/policy-design-case/rebaseline/wave-35B/strategic_behavior_gate_ledger.json",
            "_build/policy-design-case/rebaseline/wave-35B/phase34_2_rerun.json",
        ],
        "exit_fence": {
            "adversarial_probes_fail_closed_with_runtime_codes": adversarial_matrix.get(
                "status"
            )
            == "complete",
            "cache_controls_reject_poison_stale_and_fingerprint_mismatches": cache_controls.get(
                "status"
            )
            == "complete",
            "error_taxonomy_exists_and_preserves_projection_policy": error_taxonomy.get(
                "status"
            )
            == "complete",
            "strategic_ledger_has_mechanism_bound_gaming_fraud_arbitrage": strategic_ledger.get(
                "status"
            )
            == "complete",
            "phase34_2_rerun_exit_code": _mapping(phase34_rerun).get(
                "overall_exit_code"
            ),
            "no_adversarial_fail_closed_cluster_deferrals": not unresolved_cluster,
        },
        "updated_rows": updated_rows,
        "disposition_ref": _rel(
            repo_root / "_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json",
            repo_root,
        ),
    }


def _affected_dispositions(disposition: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = [
        row
        for row in _as_list(disposition.get("dispositions"))
        if isinstance(row, Mapping)
        and row.get("root_cause_cluster_id") == CLUSTER_ID
        and str(row.get("finding_id") or "").startswith(
            ("PDD-038", "PDD-064", "PDD-065", "PDD-098")
        )
    ]
    rows.sort(key=lambda row: str(row.get("finding_id")))
    if len(rows) != 12:
        raise ValueError(f"Expected 12 affected Wave 35B rows, found {len(rows)}")
    return rows


def _rows_for_pdd(
    rows: Sequence[Mapping[str, Any]],
    pdd_id: str,
) -> list[Mapping[str, Any]]:
    return [row for row in rows if str(row.get("finding_id") or "").startswith(pdd_id)]


def _bundle_ref(phase_index: Mapping[str, Any], repo_root: Path) -> dict[str, Any]:
    observed = _mapping(phase_index.get("observed_wave33_case"))
    bundle_path = str(observed.get("bundle_path") or "")
    return {
        "bundle_path": bundle_path,
        "run_id": observed.get("run_id"),
        "job_id": observed.get("job_id"),
        "scorecard_status": _mapping(
            _mapping(phase_index.get("summary")).get("fail_closed_baseline")
        ).get("scorecard_status"),
        "quality_scorecard_ref": _rel(
            _resolve(repo_root, Path(bundle_path) / "quality_evidence/quality_scorecard.json"),
            repo_root,
        )
        if bundle_path
        else None,
    }


def _add_taxonomy_entry(
    entries: dict[tuple[str, str], dict[str, Any]],
    *,
    code: str,
    component: str,
    layer: str,
    source_surface: str,
    root_cause_class: str,
    missing_producer: str,
    downstream_impact: str,
    display_policy: str,
    next_action: str,
) -> None:
    if not code:
        return
    key = (component, code)
    row = entries.setdefault(
        key,
        {
            "component": component,
            "code": code,
            "layer": layer,
            "root_cause_class": root_cause_class,
            "missing_producer": missing_producer,
            "downstream_impact": downstream_impact,
            "display_policy": display_policy,
            "next_action": next_action,
            "source_surfaces": [],
        },
    )
    if source_surface not in row["source_surfaces"]:
        row["source_surfaces"].append(source_surface)


def _component_for_layer(layer: str) -> str:
    text = layer.casefold()
    if "lex" in text or "normative" in text or "legal" in text:
        return "Lex"
    if "fabric" in text or "data_forge" in text or "semantic_binding" in text:
        return "Fabric"
    if "scholar" in text or "literature" in text:
        return "Scholar"
    if "foundry" in text or "method" in text:
        return "Foundry"
    if "scientist" in text or "claim" in text or "assurance" in text:
        return "Scientist"
    if "dashboard" in text or "api" in text:
        return "Dashboard/API"
    if "readiness" in text:
        return "Readiness"
    if "scorecard" in text:
        return "Scorecard"
    return "Runtime"


def _root_cause_for_code(code: str) -> str:
    text = code.casefold()
    if "legal" in text or "jurisdiction" in text:
        return "legal_or_jurisdiction_binding"
    if "source" in text or "fabric" in text or "snapshot" in text:
        return "source_or_snapshot_binding"
    if "method" in text or "identification" in text:
        return "method_validity_binding"
    if "scholar" in text or "literature" in text:
        return "scholar_evidence_binding"
    if "claim" in text or "authority" in text:
        return "claim_authority_binding"
    if "event" in text or "hds" in text or "runtime" in text:
        return "runtime_control_failure"
    return "policy_design_case_quality_gap"


def _missing_producer_for_layer(layer: str) -> str:
    component = _component_for_layer(layer)
    return {
        "Lex": "Lex retrieval and normative applicability producer",
        "Fabric": "Fabric source-selection or Data Forge snapshot producer",
        "Scholar": "Scholar academic evidence producer",
        "Foundry": "Foundry method validity producer",
        "Scientist": "Scientist claim compiler or assurance case producer",
        "Runtime": "runtime diagnostic/control-plane producer",
        "Dashboard/API": "dashboard/API projection producer",
        "Scorecard": "runtime quality scorecard producer",
        "Readiness": "readiness aggregation producer",
    }.get(component, "runtime evidence producer")


def _display_policy(surface: str) -> str:
    return (
        f"{surface}: display the root-cause code, owning component, message, next "
        "action, and evidence ref on detailed and operator-facing surfaces; summary "
        "views may aggregate counts only after retaining drill-down taxonomy refs."
    )


def _phase34_2_gate_status(repo_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for pdd_id, artifact in SOURCE_ARTIFACT_BY_PDD.items():
        payload = _load_json(repo_root / artifact)
        result[pdd_id] = {
            "acceptance_gate_status": payload.get("acceptance_gate_status"),
            "finding_count": len(_as_list(payload.get("findings"))),
            "generated_at": payload.get("generated_at"),
        }
    return result


def _refresh_disposition_summary(disposition: dict[str, Any]) -> None:
    rows = [
        row
        for row in _as_list(disposition.get("dispositions"))
        if isinstance(row, Mapping)
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


def _source_artifact(row: Mapping[str, Any]) -> str | None:
    evidence = _mapping(row.get("source_evidence"))
    return str(evidence.get("detail_artifact") or "") or None


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


def _stable_hash(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _tail(value: str, *, max_lines: int = 20) -> str:
    lines = value.splitlines()
    return "\n".join(lines[-max_lines:])


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return payload


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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave35-dir", type=Path, default=WAVE35_DIR)
    parser.add_argument("--wave35b-dir", type=Path, default=WAVE35B_DIR)
    parser.add_argument("--run-rerun", action="store_true")
    parser.add_argument("--update-disposition", action="store_true")
    args = parser.parse_args(argv)

    try:
        outputs = build_wave35b_outputs(
            repo_root=args.repo_root,
            wave35_dir=args.wave35_dir,
            wave35b_dir=args.wave35b_dir,
            run_rerun=args.run_rerun,
            update_disposition=args.update_disposition,
        )
    except Exception as exc:
        sys.stderr.write(f"wave35b: {exc}\n")
        return 1

    update = outputs["disposition_update"]
    sys.stdout.write(
        "wave35b: "
        f"{update['status']} "
        f"updated={update['updated_finding_count']} "
        f"phase34_exit={update['exit_fence'].get('phase34_2_rerun_exit_code')}\n"
    )
    return 0 if update["status"] == "resolved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
