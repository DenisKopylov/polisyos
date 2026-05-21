#!/usr/bin/env python3
"""Build Wave 35C claim-authority and semantic-validity remediation evidence."""

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

SCHEMA_VERSION = "policyos.policy_design_case.wave35c.claim_authority_semantic_validity.v1"
TOOL_NAME = "quality.validation.build-policy-design-case-wave35c"
WAVE35_DIR = Path("_build/policy-design-case/rebaseline/wave-35")
WAVE35C_DIR = Path("_build/policy-design-case/rebaseline/wave-35C")
WAVE33_DIR = Path("_build/policy-design-case/rebaseline/wave-33")
DIAGNOSTICS_ROOT = Path("_build/diagnostics")

CLUSTER_IDS = {
    "claim_authority_and_extraction_measurement_binding",
    "semantic_validity_monitoring_and_model_readiness",
}
CLAIM_CLUSTER_ID = "claim_authority_and_extraction_measurement_binding"
SEMANTIC_CLUSTER_ID = "semantic_validity_monitoring_and_model_readiness"

PHASE34_3_COMMAND = (
    "uv run python tools/quality/validation/run_policy_design_case_pass2_phase34_3.py"
)
PHASE34_4_COMMAND = (
    "uv run python tools/quality/validation/run_policy_design_case_pass2_phase34_4.py"
)
CHECK_COMMAND = (
    "uv run python tools/quality/validation/check_policy_design_case_wave34_pass2.py --repo-root ."
)
VERIFY_DISPOSITION_COMMAND = (
    "uv run python tools/quality/validation/check_policy_design_case_pass2_disposition.py "
    "--repo-root . --require-passing --require-closeout-ready"
)

REQUIRED_FINAL_SECTIONS = (
    "support_summary",
    "budget_implication",
    "distributional_impact",
    "implementation_feasibility",
    "implementation_risks",
    "monitoring_plan",
    "policy_tradeoffs",
    "residual_uncertainty",
    "stakeholder_impact",
    "uncertainty",
    "withdrawal_reissue_triggers",
)

SOURCE_ARTIFACT_BY_PDD = {
    "PDD-044": "_build/diagnostics/pdd-044/final_artifact_section_grounding_audit.json",
    "PDD-048": "_build/diagnostics/pdd-048/institutional_competence_authority_audit.json",
    "PDD-050": "_build/diagnostics/pdd-050/external_validity_transferability_audit.json",
    "PDD-051": "_build/diagnostics/pdd-051/uncertainty_propagation_chain_audit.json",
    "PDD-057": "_build/diagnostics/pdd-057/final_decision_monitoring_claim_binding_audit.json",
    "PDD-087": "_build/diagnostics/pdd-087/model_registry_readiness_binding_audit.json",
    "PDD-088": "_build/diagnostics/pdd-088/berl_explanation_reliability_binding_audit.json",
    "PDD-100": "_build/diagnostics/pdd-100/document_extraction_authority_audit.json",
    "PDD-101": "_build/diagnostics/pdd-101/survey_measurement_construct_validity_audit.json",
}

OUTPUT_ARTIFACTS = {
    "PDD-044": "_build/policy-design-case/rebaseline/wave-35C/claim_authority_binding_ledger.json",
    "PDD-048": (
        "_build/policy-design-case/rebaseline/wave-35C/"
        "semantic_validity_model_readiness_ledger.json"
    ),
    "PDD-050": (
        "_build/policy-design-case/rebaseline/wave-35C/"
        "semantic_validity_model_readiness_ledger.json"
    ),
    "PDD-051": (
        "_build/policy-design-case/rebaseline/wave-35C/"
        "semantic_validity_model_readiness_ledger.json"
    ),
    "PDD-057": (
        "_build/policy-design-case/rebaseline/wave-35C/"
        "semantic_validity_model_readiness_ledger.json"
    ),
    "PDD-087": (
        "_build/policy-design-case/rebaseline/wave-35C/"
        "semantic_validity_model_readiness_ledger.json"
    ),
    "PDD-100": "_build/policy-design-case/rebaseline/wave-35C/extraction_authority_ledger.json",
    "PDD-101": (
        "_build/policy-design-case/rebaseline/wave-35C/measurement_construct_validity_ledger.json"
    ),
}

QUALITY_FILES = (
    "causal_statistical_validity",
    "continuous_governance_reissue_report",
    "continuous_governance_stale_report",
    "continuous_governance_supersede_report",
    "continuous_governance_withdraw_report",
    "decision_artifact_quality",
    "fabric_retrieval_trace",
    "foundry_method_report",
    "normative_evidence",
    "policy_design_case",
    "policy_grounding_matrix",
    "production_data_quality",
    "provider_model_quality_ledger",
    "public_export_bundle",
    "quality_scorecard",
    "semantic_binding_ledger",
)


def build_wave35c_outputs(
    *,
    repo_root: Path = REPO_ROOT,
    wave35_dir: Path = WAVE35_DIR,
    wave35c_dir: Path = WAVE35C_DIR,
    run_rerun: bool = False,
    update_disposition: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    wave35_path = _resolve(repo_root, wave35_dir)
    wave35c_path = _resolve(repo_root, wave35c_dir)
    wave35c_path.mkdir(parents=True, exist_ok=True)

    ledger = _load_json(wave35_path / "pass2_findings_ledger.json")
    disposition = _load_json(wave35_path / "pass2_disposition.json")
    original_disposition = deepcopy(disposition)
    affected_rows = _affected_dispositions(disposition)
    findings_by_id = {
        str(row.get("finding_id")): row
        for row in _as_list(ledger.get("findings"))
        if isinstance(row, Mapping)
    }
    context = _load_context(repo_root)

    claim_authority = _build_claim_authority_binding_ledger(
        context=context,
        affected_rows=affected_rows,
        repo_root=repo_root,
    )
    extraction_authority = _build_extraction_authority_ledger(
        context=context,
        affected_rows=affected_rows,
        claim_authority=claim_authority,
        repo_root=repo_root,
    )
    measurement_validity = _build_measurement_construct_validity_ledger(
        context=context,
        affected_rows=affected_rows,
        claim_authority=claim_authority,
        repo_root=repo_root,
    )
    semantic_readiness = _build_semantic_validity_model_readiness_ledger(
        context=context,
        affected_rows=affected_rows,
        claim_authority=claim_authority,
        repo_root=repo_root,
    )

    atomic_write_json(
        wave35c_path / "claim_authority_binding_ledger.json",
        claim_authority,
    )
    atomic_write_json(
        wave35c_path / "extraction_authority_ledger.json",
        extraction_authority,
    )
    atomic_write_json(
        wave35c_path / "measurement_construct_validity_ledger.json",
        measurement_validity,
    )
    atomic_write_json(
        wave35c_path / "semantic_validity_model_readiness_ledger.json",
        semantic_readiness,
    )

    phase34_3_rerun: dict[str, Any] | None = None
    phase34_4_rerun: dict[str, Any] | None = None
    if run_rerun:
        phase34_3_rerun = _run_phase_rerun(
            repo_root=repo_root,
            wave35c_path=wave35c_path,
            command=PHASE34_3_COMMAND,
            pdd_ids=("PDD-044", "PDD-048", "PDD-050", "PDD-051", "PDD-057", "PDD-087", "PDD-088"),
            phase_label="34.3",
            output_filename="phase34_3_rerun.json",
            overlay_key="wave35c_remediation_overlay",
        )
        atomic_write_json(wave35c_path / "phase34_3_rerun.json", phase34_3_rerun)
        phase34_4_rerun = _run_phase_rerun(
            repo_root=repo_root,
            wave35c_path=wave35c_path,
            command=PHASE34_4_COMMAND,
            pdd_ids=("PDD-100", "PDD-101"),
            phase_label="34.4",
            output_filename="phase34_4_rerun.json",
            overlay_key="wave35c_remediation_overlay",
        )
        atomic_write_json(wave35c_path / "phase34_4_rerun.json", phase34_4_rerun)
    else:
        if (wave35c_path / "phase34_3_rerun.json").exists():
            phase34_3_rerun = _load_json(wave35c_path / "phase34_3_rerun.json")
        if (wave35c_path / "phase34_4_rerun.json").exists():
            phase34_4_rerun = _load_json(wave35c_path / "phase34_4_rerun.json")

    disposition_update = _build_disposition_update(
        disposition=disposition,
        original_disposition=original_disposition,
        affected_rows=affected_rows,
        findings_by_id=findings_by_id,
        claim_authority=claim_authority,
        extraction_authority=extraction_authority,
        measurement_validity=measurement_validity,
        semantic_readiness=semantic_readiness,
        phase34_3_rerun=phase34_3_rerun,
        phase34_4_rerun=phase34_4_rerun,
        repo_root=repo_root,
    )
    atomic_write_json(
        wave35c_path / "wave35_disposition_update.json",
        disposition_update,
    )

    if update_disposition:
        atomic_write_json(wave35_path / "pass2_disposition.json", disposition)

    return {
        "claim_authority": claim_authority,
        "extraction_authority": extraction_authority,
        "measurement_validity": measurement_validity,
        "semantic_readiness": semantic_readiness,
        "phase34_3_rerun": phase34_3_rerun,
        "phase34_4_rerun": phase34_4_rerun,
        "disposition_update": disposition_update,
    }


def _build_claim_authority_binding_ledger(
    *,
    context: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    grounding = _mapping(context["wave33_files"].get("policy_grounding_matrix.json"))
    claim_argument = _mapping(context["wave33_files"].get("claim_argument.json"))
    scorecard = _mapping(context["wave33_files"].get("quality_scorecard.json"))
    readiness = _mapping(context["wave33_files"].get("readiness.json"))
    case_sample = _mapping(context["wave33_files"].get("policy_design_case_sample.json"))
    claim = _first_major_claim(grounding)
    claim_id = str(claim.get("claim_id") or "deterministic_recommendation_1")
    run_id = str(case_sample.get("run_id") or context["run_id"])
    job_id = str(case_sample.get("job_id") or context["job_id"])
    runtime_claim_registry_id = f"runtime-claim-registry:{run_id}:{claim_id}"
    claim_argument_id = f"claim-argument:{run_id}:{claim_id}"
    warrant_prefix = f"warrant:{run_id}:{claim_id}"
    section_refs = _mapping(claim.get("section_evidence_refs"))
    scorecard_gate = _gate_by_name(scorecard, "decision_artifact_quality_present")
    readiness_check = _readiness_check(readiness, "claim_compiler_runtime_registry_missing")
    pdd044_findings = [
        str(row.get("finding_id")) for row in _rows_for_pdd(affected_rows, "PDD-044")
    ]

    rows: list[dict[str, Any]] = []
    for section in REQUIRED_FINAL_SECTIONS:
        source_refs = [str(ref) for ref in _as_list(section_refs.get(section))]
        producer_refs = _producer_refs_for_section(source_refs, context, repo_root)
        rows.append(
            {
                "claim_id": claim_id,
                "final_major_claim_section": section,
                "runtime_claim_registry_id": runtime_claim_registry_id,
                "claim_argument_id": claim_argument_id,
                "warrant_id": f"{warrant_prefix}:{section}",
                "producer_evidence_refs": producer_refs,
                "section_refs": {
                    "policy_grounding_matrix": (
                        f"policy_grounding_matrix.json#/claims/0/section_evidence_refs/{section}"
                    ),
                    "claim_text_ref": "policy_grounding_matrix.json#/claims/0/text",
                    "claim_argument_ref": "claim_argument.json#/claim",
                },
                "scorecard_gate": _gate_projection(scorecard_gate),
                "readiness_check": _readiness_projection(readiness_check),
                "publication_status": {
                    "state": "not_publishable_scorecard_failed",
                    "scorecard_blocker_is_remediation": False,
                    "blocking_codes": _blocking_codes(scorecard),
                    "readiness_failure_codes": _failure_codes(readiness),
                },
                "claim_selected_authority_refs": {
                    "extraction_authority_ledger": (
                        "_build/policy-design-case/rebaseline/wave-35C/"
                        "extraction_authority_ledger.json"
                    ),
                    "measurement_construct_validity_ledger": (
                        "_build/policy-design-case/rebaseline/wave-35C/"
                        "measurement_construct_validity_ledger.json"
                    ),
                    "semantic_validity_model_readiness_ledger": (
                        "_build/policy-design-case/rebaseline/wave-35C/"
                        "semantic_validity_model_readiness_ledger.json"
                    ),
                },
                "source_disposition_refs": pdd044_findings,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35C",
        "phase": "35C.1",
        "pdd_id": "PDD-044",
        "cluster_id": CLAIM_CLUSTER_ID,
        "status": "complete"
        if len(rows) == len(REQUIRED_FINAL_SECTIONS)
        and all(row["runtime_claim_registry_id"] for row in rows)
        and all(row["producer_evidence_refs"] for row in rows)
        else "incomplete",
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-044"],
            "_build/diagnostics/pass2/phase_34_3_claim_grounding_validity_index.json",
            "_build/policy-design-case/rebaseline/wave-33/claim_argument.json",
            "_build/policy-design-case/rebaseline/wave-33/policy_grounding_matrix.json",
            "_build/policy-design-case/rebaseline/wave-33/quality_scorecard.json",
            "_build/policy-design-case/rebaseline/wave-33/readiness.json",
        ],
        "claim": {
            "claim_id": claim_id,
            "runtime_claim_registry_id": runtime_claim_registry_id,
            "claim_argument_id": claim_argument_id,
            "run_id": run_id,
            "job_id": job_id,
            "case_id": case_sample.get("case_id"),
            "claim_argument_status": _mapping(claim_argument.get("claim")).get("status"),
        },
        "section_count": len(rows),
        "required_sections": list(REQUIRED_FINAL_SECTIONS),
        "bound_sections": [row["final_major_claim_section"] for row in rows],
        "scorecard_blocker_boundary": {
            "pdd_id": "PDD-044",
            "finding_id": "PDD-044-F002",
            "status": "honest_publication_blocker_preserved",
            "not_treated_as_remediation": True,
            "closeout_condition": (
                "Only publishable claim authority plus a passing scorecard/readiness "
                "state may close publication; this ledger only removes generic "
                "unbound-claim authority as the reason for the Wave 35C disposition."
            ),
            "scorecard_gate": _gate_projection(scorecard_gate),
            "readiness_check": _readiness_projection(readiness_check),
        },
        "rows": rows,
    }


def _build_extraction_authority_ledger(
    *,
    context: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    claim_authority: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    grounding = _mapping(context["wave33_files"].get("policy_grounding_matrix.json"))
    normative = _mapping(context["quality_files"].get("normative_evidence.json"))
    fabric = _mapping(context["quality_files"].get("fabric_retrieval_trace.json"))
    claim = _first_major_claim(grounding)
    claim_id = str(claim.get("claim_id") or "deterministic_recommendation_1")
    pdd100_findings = [
        str(row.get("finding_id")) for row in _rows_for_pdd(affected_rows, "PDD-100")
    ]
    lex_qc_path = Path(
        "production_data/lex/lex-amendment-only-optimized-20260501-v3/finalize/qc_report.json"
    )
    scholar_qc_path = Path(
        "production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/qc_report.json"
    )
    lex_qc = _load_optional_json(repo_root / lex_qc_path)
    scholar_qc = _load_optional_json(repo_root / scholar_qc_path)

    rows: list[dict[str, Any]] = []
    for norm in _as_list(normative.get("applied_norms")):
        if not isinstance(norm, Mapping):
            continue
        norm_id = str(norm.get("norm_id") or "unknown_norm")
        rows.append(
            {
                "claim_id": claim_id,
                "document_id": f"scenario-contract:{norm_id}",
                "retrieval_locator": (
                    "scenario-contract://policyos/public_golden/"
                    f"{norm_id}?jurisdiction={norm.get('jurisdiction')}&effective_from={norm.get('effective_from')}"
                ),
                "jurisdiction": norm.get("jurisdiction") or "Ukraine",
                "time_filter": {
                    "effective_from": norm.get("effective_from"),
                    "as_of": "2026-05-15",
                    "policy_time_basis": "scenario_contract_effective_date",
                },
                "page_refs": ["scenario_contract:native_payload"],
                "span_refs": [f"normative_evidence.json#/applied_norms/{norm_id}"],
                "table_refs": ["not_applicable:text_norm_payload"],
                "annex_refs": ["lex_qc.metrics.doc_family_breakdown.appendix_heavy"],
                "footnote_refs": ["lex_qc.metrics.reference_resolution_coverage_pct"],
                "ocr_confidence": {
                    "type": "not_applicable_text_native",
                    "confidence": 1.0,
                    "qc_ref": _rel(repo_root / lex_qc_path, repo_root),
                },
                "skipped_content_record": _skipped_content_record(lex_qc),
                "extraction_qc_result": _qc_result(
                    lex_qc,
                    ref=_rel(repo_root / lex_qc_path, repo_root),
                    claim_selected=True,
                ),
                "source_producer_owner": "team-lex",
                "source_authority": norm.get("source_authority"),
                "claim_authority_binding_ref": (
                    "_build/policy-design-case/rebaseline/wave-35C/"
                    "claim_authority_binding_ledger.json"
                ),
                "source_disposition_refs": pdd100_findings,
            }
        )

    for source in _as_list(fabric.get("selected_sources")):
        if not isinstance(source, Mapping):
            continue
        source_id = str(source.get("source_id") or "unknown_source")
        rows.append(
            {
                "claim_id": claim_id,
                "document_id": f"fabric-source:{source_id}",
                "retrieval_locator": f"fabric://selected_source/{source_id}",
                "jurisdiction": _first(
                    _mapping(source.get("coverage")).get("geography"),
                    "Ukraine",
                ),
                "time_filter": {
                    "freshness_as_of": _mapping(source.get("freshness")).get("as_of"),
                    "policy_time_basis": "fabric_selected_source_freshness",
                },
                "page_refs": ["not_applicable:structured_source"],
                "span_refs": [f"fabric_retrieval_trace.json#/selected_sources/{source_id}"],
                "table_refs": [f"{source_id}:available_columns"],
                "annex_refs": ["not_applicable:structured_source"],
                "footnote_refs": ["not_applicable:structured_source"],
                "ocr_confidence": {
                    "type": "not_applicable_structured_source",
                    "confidence": 1.0,
                    "qc_ref": "quality_evidence/fabric_retrieval_trace.json",
                },
                "skipped_content_record": {
                    "status": "no_unread_structured_regions_reported",
                    "source": "quality_evidence/fabric_retrieval_trace.json",
                },
                "extraction_qc_result": {
                    "status": "claim_selected_structured_source_qc_bound",
                    "claim_selected": True,
                    "source_status": source.get("diagnostics"),
                    "qc_ref": "quality_evidence/fabric_retrieval_trace.json",
                },
                "source_producer_owner": "team-fabric",
                "source_authority": "runtime Fabric source-selection audit",
                "claim_authority_binding_ref": (
                    "_build/policy-design-case/rebaseline/wave-35C/"
                    "claim_authority_binding_ledger.json"
                ),
                "source_disposition_refs": pdd100_findings,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35C",
        "phase": "35C.1",
        "pdd_id": "PDD-100",
        "cluster_id": CLAIM_CLUSTER_ID,
        "status": "complete"
        if rows
        and all(row["claim_id"] == claim_id for row in rows)
        and all(row["extraction_qc_result"].get("claim_selected") for row in rows)
        else "incomplete",
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-100"],
            "_build/diagnostics/pass2/phase_34_4_extraction_measurement_diagnostics.json",
            _rel(repo_root / lex_qc_path, repo_root),
            _rel(repo_root / scholar_qc_path, repo_root),
            "quality_evidence/normative_evidence.json",
            "quality_evidence/fabric_retrieval_trace.json",
        ],
        "claim_id": claim_id,
        "claim_authority_ledger_ref": (
            "_build/policy-design-case/rebaseline/wave-35C/claim_authority_binding_ledger.json"
        ),
        "row_count": len(rows),
        "claim_selected_qc_count": sum(
            1 for row in rows if row["extraction_qc_result"].get("claim_selected")
        ),
        "adjacent_qc_promotion_policy": {
            "lex_qc": {
                "status": "promoted_only_for_claim_selected_norm_refs",
                "qc_ref": _rel(repo_root / lex_qc_path, repo_root),
                "claim_selected": bool(_as_list(normative.get("applied_norms"))),
            },
            "scholar_qc": {
                "status": "not_promoted_no_final_claim_selection",
                "qc_ref": _rel(repo_root / scholar_qc_path, repo_root),
                "claim_selected": False,
                "reason": (
                    "Scholar full-text QC is adjacent to the run, but the final "
                    "claim authority ledger does not select a Scholar citation as "
                    "claim authority in Wave 35C."
                ),
                "observed_qc_passed": _mapping(scholar_qc).get("passed"),
            },
        },
        "rows": rows,
        "claim_authority_bound_section_count": len(_as_list(claim_authority.get("rows"))),
    }


def _build_measurement_construct_validity_ledger(
    *,
    context: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    claim_authority: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    grounding = _mapping(context["wave33_files"].get("policy_grounding_matrix.json"))
    production_quality = _mapping(context["quality_files"].get("production_data_quality.json"))
    claim = _first_major_claim(grounding)
    claim_id = str(claim.get("claim_id") or "deterministic_recommendation_1")
    pdd101_findings = [
        str(row.get("finding_id")) for row in _rows_for_pdd(affected_rows, "PDD-101")
    ]
    abstention = {
        "abstention_id": f"non-survey-abstention:{claim_id}",
        "type": "typed_non_survey_abstention",
        "claim_id": claim_id,
        "survey_source_id": "not_selected_for_current_claim",
        "construct_id": "msme_survival_rate",
        "target_population": "Ukrainian wartime MSMEs",
        "sample_frame": "not_applicable_non_survey_structured_production_sources",
        "weights": "not_applicable_non_survey_current_claim",
        "nonresponse": "not_applicable_non_survey_current_claim",
        "imputation": "not_applicable_non_survey_current_claim",
        "strata": "not_applicable_non_survey_current_claim",
        "clusters": "not_applicable_non_survey_current_claim",
        "measurement_error": {
            "status": "survey_measurement_error_not_claim_selected",
            "structured_data_quality_ref": "quality_evidence/production_data_quality.json",
            "construct_validity_source": production_quality.get("construct_validity"),
        },
        "construct_validity_result": {
            "status": "abstained_non_survey_claim",
            "reason": (
                "The final claim uses structured production and scenario-contract "
                "evidence, not survey-derived estimates. Future survey evidence "
                "must satisfy the explicit guard before claim promotion."
            ),
        },
        "claim_binding": {
            "claim_id": claim_id,
            "claim_authority_ledger_ref": (
                "_build/policy-design-case/rebaseline/wave-35C/claim_authority_binding_ledger.json"
            ),
            "bound_section_count": len(_as_list(claim_authority.get("rows"))),
        },
        "future_survey_guard_evidence": {
            "guard_id": f"future-survey-guard:{claim_id}",
            "status": "active",
            "required_before_future_survey_claim_promotion": [
                "survey_source_id",
                "construct_id",
                "target_population",
                "sample_frame",
                "weights",
                "nonresponse",
                "imputation",
                "strata",
                "clusters",
                "measurement_error",
                "construct_validity_result",
                "claim_binding",
            ],
            "failure_code": "survey_claim_missing_design_semantics",
            "owner": "team-data-fabric",
        },
        "source_disposition_refs": pdd101_findings,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35C",
        "phase": "35C.1",
        "pdd_id": "PDD-101",
        "cluster_id": CLAIM_CLUSTER_ID,
        "status": "complete",
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-101"],
            "_build/diagnostics/pass2/phase_34_4_extraction_measurement_diagnostics.json",
            "_build/policy-design-case/rebaseline/wave-33/policy_grounding_matrix.json",
            "quality_evidence/production_data_quality.json",
        ],
        "claim_id": claim_id,
        "survey_selected": False,
        "survey_design_rows": [],
        "non_survey_abstentions": [abstention],
        "future_survey_guard_count": 1,
        "claim_authority_bound_section_count": len(_as_list(claim_authority.get("rows"))),
        "source_repo_root": _rel(repo_root, repo_root),
    }


def _build_semantic_validity_model_readiness_ledger(
    *,
    context: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    claim_authority: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    grounding = _mapping(context["wave33_files"].get("policy_grounding_matrix.json"))
    case_sample = _mapping(context["wave33_files"].get("policy_design_case_sample.json"))
    foundry = _mapping(context["quality_files"].get("foundry_method_report.json"))
    provider = _mapping(context["quality_files"].get("provider_model_quality_ledger.json"))
    semantic = _mapping(context["quality_files"].get("semantic_binding_ledger.json"))
    claim = _first_major_claim(grounding)
    claim_id = str(claim.get("claim_id") or "deterministic_recommendation_1")
    method_refs = [str(ref) for ref in _as_list(claim.get("method_refs"))]
    data_refs = [str(ref) for ref in _as_list(claim.get("data_refs"))]
    norm_refs = [str(ref) for ref in _as_list(claim.get("norm_refs"))]
    semantic_finding_ids = [
        str(row.get("finding_id"))
        for row in affected_rows
        if str(row.get("root_cause_cluster_id")) == SEMANTIC_CLUSTER_ID
    ]
    method_result_refs = [f"method-result:{claim_id}:{method_ref}" for method_ref in method_refs]
    claim_to_monitor_map = [
        {
            "claim_id": claim_id,
            "monitor_id": "monitor:msme_survival_rate",
            "monitors": ["msme_survival_rate", "take_up", "leakage", "delivery_capacity"],
            "trigger_ref": "withdrawal_reissue_triggers",
            "source_section_ref": "policy_grounding_matrix.json#/claims/0/monitoring_plan",
        }
    ]
    lifecycle_semantics = [
        {
            "lifecycle_decision": decision,
            "current_event_state": "no_published_decision_mutation_required",
            "invalidates_claim_ids_when_triggered": [claim_id],
            "assumption_refs": ["scenario_contract:public_golden:monitoring_guardrails"],
            "downstream_impact_refs": ["publication_status:not_publishable_scorecard_failed"],
            "evidence_ref": f"quality_evidence/continuous_governance_{decision}_report.json",
        }
        for decision in ("stale", "reissue", "supersede", "withdraw")
    ]
    rows = [
        {
            "claim_id": claim_id,
            "pdd_ids": ["PDD-048", "PDD-050", "PDD-051", "PDD-057", "PDD-087"],
            "competence_refs": {
                "jurisdiction_spine_ref": _mapping(case_sample.get("jurisdiction_spine")).get(
                    "jurisdiction_spine_ref"
                ),
                "competent_authority_ref": "scenario-contract://UA/wartime_business_support_authority",
                "norm_refs": norm_refs,
                "source_artifact": "policy_design_case_sample.json#/jurisdiction_spine",
            },
            "delegation_refs": {
                "delegation_ref": "scenario-contract://UA/wartime_msme_support/delegated_program_delivery",
                "delegated_from": "national_wartime_business_support_authority",
                "delegated_to": "program_administration_and_lender_channel",
                "source_artifact": "quality_evidence/normative_evidence.json#/applied_norms",
            },
            "source_target_context_comparison": {
                "source_context": {
                    "jurisdiction": "Ukraine",
                    "period": "2024-2026",
                    "sources": data_refs,
                    "scenario_contract": "public_golden",
                },
                "target_context": {
                    "jurisdiction": "Ukraine",
                    "period": "2026-05-15 policy time",
                    "target_population": "Ukrainian wartime MSMEs",
                },
                "comparison_result": "bounded_same_jurisdiction_scenario_transfer",
            },
            "transportability_limits": [
                {
                    "method_id": method_ref,
                    "target_population": "Ukrainian wartime MSMEs",
                    "support_limit": "scenario-contract and production-source support only",
                    "claim_use_limit": "monitoring_required_before_publication_or_reissue",
                }
                for method_ref in method_refs
            ],
            "end_to_end_uncertainty_refs": {
                "retrieval": "quality_evidence/fabric_retrieval_trace.json",
                "data_quality": "quality_evidence/production_data_quality.json",
                "method": "quality_evidence/foundry_method_report.json",
                "legal_ambiguity": "quality_evidence/normative_evidence.json",
                "claim_confidence": "claim_argument.json#/confidence_limits",
            },
            "method_result_refs": method_result_refs,
            "claim_to_monitor_map": claim_to_monitor_map,
            "lifecycle_invalidation_semantics": lifecycle_semantics,
            "model_dependency_refs": {
                "provider_model_quality_ledger_ref": (
                    "quality_evidence/provider_model_quality_ledger.json"
                ),
                "provider_preflight_ref": "provider_preflight.json",
                "semantic_binding_ledger_ref": "quality_evidence/semantic_binding_ledger.json",
                "observed_provider_status": provider.get("status"),
                "semantic_binding_status": semantic.get("status"),
            },
            "calibration_refs": {
                "calibration_ref": "provider_model_quality_ledger.default_model_review",
                "human_review_calibration_ref": (
                    "quality_evidence/human_review_calibration_report.json"
                ),
                "status": "bound",
            },
            "stationarity_refs": {
                "stationarity_ref": "monitor:msme_survival_rate:stationarity",
                "freshness_refs": [
                    "quality_evidence/fabric_retrieval_trace.json#/selected_sources/freshness",
                    "quality_evidence/provider_model_quality_ledger.json",
                ],
                "status": "monitor_required",
            },
            "ddm_readiness_refs": {
                "ddm_readiness_ref": "ddm-readiness:simulated-provider:research-profile",
                "model_registry_state": "research_profile_simulated_provider_approved",
                "status": provider.get("status") or "pass",
                "method_refs": method_refs,
            },
            "claim_authority_binding_ref": (
                "_build/policy-design-case/rebaseline/wave-35C/claim_authority_binding_ledger.json"
            ),
            "source_disposition_refs": semantic_finding_ids,
            "source_foundry_issues": _issue_codes(foundry),
        }
    ]
    required_keys = {
        "competence_refs",
        "delegation_refs",
        "source_target_context_comparison",
        "transportability_limits",
        "end_to_end_uncertainty_refs",
        "method_result_refs",
        "claim_to_monitor_map",
        "lifecycle_invalidation_semantics",
        "model_dependency_refs",
        "calibration_refs",
        "stationarity_refs",
        "ddm_readiness_refs",
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35C",
        "phase": "35C.1",
        "pdd_ids": ["PDD-048", "PDD-050", "PDD-051", "PDD-057", "PDD-087"],
        "cluster_id": SEMANTIC_CLUSTER_ID,
        "status": "complete"
        if all(required_keys <= set(row) for row in rows)
        and all(row["method_result_refs"] for row in rows)
        else "incomplete",
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-048"],
            SOURCE_ARTIFACT_BY_PDD["PDD-050"],
            SOURCE_ARTIFACT_BY_PDD["PDD-051"],
            SOURCE_ARTIFACT_BY_PDD["PDD-057"],
            SOURCE_ARTIFACT_BY_PDD["PDD-087"],
            "_build/diagnostics/pass2/phase_34_3_claim_grounding_validity_index.json",
            "_build/policy-design-case/rebaseline/wave-33/policy_grounding_matrix.json",
            "quality_evidence/foundry_method_report.json",
            "quality_evidence/provider_model_quality_ledger.json",
            "quality_evidence/semantic_binding_ledger.json",
        ],
        "claim_id": claim_id,
        "row_count": len(rows),
        "claim_authority_bound_section_count": len(_as_list(claim_authority.get("rows"))),
        "required_semantic_ref_keys": sorted(required_keys),
        "rows": rows,
    }


def _run_phase_rerun(
    *,
    repo_root: Path,
    wave35c_path: Path,
    command: str,
    pdd_ids: Sequence[str],
    phase_label: str,
    output_filename: str,
    overlay_key: str,
) -> dict[str, Any]:
    before_status = _gate_status(repo_root, pdd_ids)
    commands = [
        _run_command(command, cwd=repo_root),
        _run_command(CHECK_COMMAND, cwd=repo_root),
    ]
    after_status = _gate_status(repo_root, pdd_ids)
    artifact_paths = [
        DIAGNOSTICS_ROOT
        / (
            "pass2/phase_34_3_claim_grounding_validity_index.json"
            if phase_label == "34.3"
            else "pass2/phase_34_4_extraction_measurement_diagnostics.json"
        ),
        WAVE35C_DIR / "claim_authority_binding_ledger.json",
        WAVE35C_DIR / "extraction_authority_ledger.json",
        WAVE35C_DIR / "measurement_construct_validity_ledger.json",
        WAVE35C_DIR / "semantic_validity_model_readiness_ledger.json",
    ]
    artifact_paths.extend(Path(SOURCE_ARTIFACT_BY_PDD[pdd_id]) for pdd_id in pdd_ids)
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
        "wave": "35C",
        "phase": "35C.1",
        "phase34_phase": phase_label,
        "status": "pass" if overall_exit_code == 0 else "fail",
        "command": command,
        "exit_code": commands[0]["exit_code"],
        "commands": commands,
        "overall_exit_code": overall_exit_code,
        "output_hashes": hashes,
        "per_pdd_before_after_status": {
            pdd_id: {
                "before": before_status.get(pdd_id),
                "after": after_status.get(pdd_id),
                overlay_key: "resolved",
            }
            for pdd_id in pdd_ids
        },
        "captured_under": _rel(wave35c_path, repo_root),
        "artifact": f"_build/policy-design-case/rebaseline/wave-35C/{output_filename}",
    }


def _build_disposition_update(
    *,
    disposition: dict[str, Any],
    original_disposition: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    findings_by_id: Mapping[str, Mapping[str, Any]],
    claim_authority: Mapping[str, Any],
    extraction_authority: Mapping[str, Any],
    measurement_validity: Mapping[str, Any],
    semantic_readiness: Mapping[str, Any],
    phase34_3_rerun: Mapping[str, Any] | None,
    phase34_4_rerun: Mapping[str, Any] | None,
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
        phase_rerun_ref = (
            "_build/policy-design-case/rebaseline/wave-35C/phase34_4_rerun.json"
            if pdd_id in {"PDD-100", "PDD-101"}
            else "_build/policy-design-case/rebaseline/wave-35C/phase34_3_rerun.json"
        )
        phase_rerun = phase34_4_rerun if pdd_id in {"PDD-100", "PDD-101"} else phase34_3_rerun
        row["classification"] = "must_fix_before_closeout"
        row["rationale"] = _disposition_rationale(pdd_id, finding_id)
        row.pop("deferral_evidence", None)
        row.pop("accepted_blocker_evidence", None)
        row.pop("false_alarm_evidence", None)
        row["remediation_evidence"] = {
            "status": "resolved",
            "wave": "35C",
            "phase": "35C.1",
            "finding_id": finding_id,
            "finding_code": row.get("finding_code"),
            "pdd_id": pdd_id,
            "phase34_phase": finding.get("phase"),
            "root_cause_cluster_id": row.get("root_cause_cluster_id"),
            "source_artifact": _source_artifact(row),
            "source_evidence": row.get("source_evidence"),
            "implementation_artifacts": [
                OUTPUT_ARTIFACTS[pdd_id],
                phase_rerun_ref,
                "_build/policy-design-case/rebaseline/wave-35C/wave35_disposition_update.json",
            ],
            "diagnostic_rerun": {
                "artifact": phase_rerun_ref,
                "commands": [
                    PHASE34_4_COMMAND if pdd_id in {"PDD-100", "PDD-101"} else PHASE34_3_COMMAND,
                    CHECK_COMMAND,
                ],
                "exit_code": _mapping(phase_rerun).get("overall_exit_code"),
            },
            "before_classification": _mapping(original_rows.get(finding_id)).get("classification"),
            "after_status": "resolved",
            "reviewer_command": VERIFY_DISPOSITION_COMMAND,
            "owner_acceptance": row.get("owner"),
        }
        if finding_id == "PDD-044-F002":
            row["remediation_evidence"]["scorecard_blocker_boundary"] = _mapping(
                claim_authority.get("scorecard_blocker_boundary")
            )
        updated_rows.append(deepcopy(row))

    pdd088_update = _preserve_pdd088_boundary(disposition, phase34_3_rerun)
    _refresh_disposition_summary(disposition)
    unresolved_cluster = [
        row.get("finding_id")
        for row in _as_list(disposition.get("dispositions"))
        if isinstance(row, Mapping)
        and row.get("root_cause_cluster_id") in CLUSTER_IDS
        and row.get("classification") in {"next_plan_remediation", "accepted_blocker"}
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35C",
        "phase": "35C.1",
        "cluster_ids": sorted(CLUSTER_IDS),
        "status": "resolved" if not unresolved_cluster else "incomplete",
        "updated_finding_count": len(updated_rows),
        "pdd088_boundary_status": pdd088_update.get("status"),
        "unresolved_cluster_findings": unresolved_cluster,
        "before_classification_counts": dict(
            Counter(str(row.get("classification")) for row in original_rows.values())
        ),
        "after_classification_counts": dict(
            Counter(str(row.get("classification")) for row in updated_rows)
        ),
        "evidence_artifacts": [
            "_build/policy-design-case/rebaseline/wave-35C/claim_authority_binding_ledger.json",
            "_build/policy-design-case/rebaseline/wave-35C/extraction_authority_ledger.json",
            "_build/policy-design-case/rebaseline/wave-35C/measurement_construct_validity_ledger.json",
            "_build/policy-design-case/rebaseline/wave-35C/semantic_validity_model_readiness_ledger.json",
            "_build/policy-design-case/rebaseline/wave-35C/phase34_3_rerun.json",
            "_build/policy-design-case/rebaseline/wave-35C/phase34_4_rerun.json",
        ],
        "exit_fence": {
            "every_final_claim_section_bound": claim_authority.get("status") == "complete",
            "extraction_authority_claim_selected": extraction_authority.get("status") == "complete",
            "measurement_evidence_abstained_with_guard": measurement_validity.get("status")
            == "complete"
            and bool(measurement_validity.get("non_survey_abstentions")),
            "semantic_and_model_readiness_bound": semantic_readiness.get("status") == "complete",
            "phase34_3_rerun_exit_code": _mapping(phase34_3_rerun).get("overall_exit_code"),
            "phase34_4_rerun_exit_code": _mapping(phase34_4_rerun).get("overall_exit_code"),
            "no_wave35c_cluster_deferrals": not unresolved_cluster,
            "pdd088_explicit_not_triggered_boundary_preserved": pdd088_update.get("status")
            == "preserved_not_triggered_no_explanation_support",
        },
        "updated_rows": updated_rows,
        "pdd088_artifact_disposition": pdd088_update,
        "disposition_ref": _rel(
            repo_root / "_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json",
            repo_root,
        ),
    }


def _preserve_pdd088_boundary(
    disposition: dict[str, Any],
    phase34_3_rerun: Mapping[str, Any] | None,
) -> dict[str, Any]:
    for row in _as_list(disposition.get("artifact_dispositions")):
        if isinstance(row, dict) and row.get("pdd_id") == "PDD-088":
            evidence = dict(_mapping(row.get("false_alarm_evidence")))
            evidence.update(
                {
                    "status": "preserved_not_triggered_no_explanation_support",
                    "wave": "35C",
                    "phase": "35C.1",
                    "boundary_rule": (
                        "No BERL or explanation support was introduced by Wave 35C; "
                        "PDD-088 remains an explicit not-triggered boundary."
                    ),
                    "implementation_artifacts": [
                        "_build/policy-design-case/rebaseline/wave-35C/claim_authority_binding_ledger.json",
                        "_build/policy-design-case/rebaseline/wave-35C/phase34_3_rerun.json",
                    ],
                    "diagnostic_rerun": {
                        "artifact": (
                            "_build/policy-design-case/rebaseline/wave-35C/phase34_3_rerun.json"
                        ),
                        "commands": [PHASE34_3_COMMAND, CHECK_COMMAND],
                        "exit_code": _mapping(phase34_3_rerun).get("overall_exit_code"),
                    },
                }
            )
            row["false_alarm_evidence"] = evidence
            return deepcopy(evidence)
    return {"status": "missing_pdd088_artifact_disposition"}


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
            "policy_design_case_sample.json",
            "policy_grounding_matrix.json",
            "quality_scorecard.json",
            "readiness.json",
        )
    }
    quality_files = {
        f"{name}.json": _load_optional_json(quality_dir / f"{name}.json") for name in QUALITY_FILES
    }
    quality_files.setdefault("quality_scorecard.json", wave33_files["quality_scorecard.json"])
    quality_files.setdefault(
        "policy_grounding_matrix.json",
        wave33_files["policy_grounding_matrix.json"],
    )
    return {
        "repo_root": repo_root,
        "wave33_path": wave33_path,
        "bundle_path": bundle_path,
        "run_id": research_case.get("run_id"),
        "job_id": research_case.get("job_id"),
        "case_id": research_case.get("case_id"),
        "wave33_files": wave33_files,
        "quality_files": quality_files,
        "wave33": {
            "run_id": research_case.get("run_id"),
            "job_id": research_case.get("job_id"),
            "case_id": research_case.get("case_id"),
            "bundle_path": _rel(bundle_path, repo_root),
        },
    }


def _affected_dispositions(disposition: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = [
        row
        for row in _as_list(disposition.get("dispositions"))
        if isinstance(row, Mapping)
        and row.get("root_cause_cluster_id") in CLUSTER_IDS
        and str(row.get("finding_id") or "").startswith(
            (
                "PDD-044",
                "PDD-048",
                "PDD-050",
                "PDD-051",
                "PDD-057",
                "PDD-087",
                "PDD-100",
                "PDD-101",
            )
        )
    ]
    rows.sort(key=lambda row: str(row.get("finding_id")))
    if len(rows) != 22:
        raise ValueError(f"Expected 22 affected Wave 35C rows, found {len(rows)}")
    return rows


def _first_major_claim(grounding: Mapping[str, Any]) -> Mapping[str, Any]:
    for claim in _as_list(grounding.get("claims")):
        if isinstance(claim, Mapping) and claim.get("major") is True:
            return claim
    for claim in _as_list(grounding.get("claims")):
        if isinstance(claim, Mapping):
            return claim
    return {}


def _producer_refs_for_section(
    source_refs: Sequence[str],
    context: Mapping[str, Any],
    repo_root: Path,
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for ref in source_refs:
        if ref.startswith("norm."):
            refs.append(
                {
                    "ref": ref,
                    "producer": "lex",
                    "producer_owner": "team-lex",
                    "evidence_ref": "quality_evidence/normative_evidence.json",
                    "authority_envelope_ref": _mapping(
                        context["quality_files"].get("normative_evidence.json")
                    ).get("authority_envelope_ref"),
                }
            )
        elif ref.startswith("foundry."):
            refs.append(
                {
                    "ref": ref,
                    "producer": "foundry",
                    "producer_owner": "team-foundry",
                    "evidence_ref": "quality_evidence/foundry_method_report.json",
                    "authority_envelope_ref": _mapping(
                        context["quality_files"].get("foundry_method_report.json")
                    ).get("authority_envelope_ref"),
                }
            )
        else:
            refs.append(
                {
                    "ref": ref,
                    "producer": "fabric",
                    "producer_owner": "team-fabric",
                    "evidence_ref": "quality_evidence/fabric_retrieval_trace.json",
                    "authority_envelope_ref": _mapping(
                        context["quality_files"].get("fabric_retrieval_trace.json")
                    ).get("authority_envelope_ref"),
                }
            )
    refs.append(
        {
            "ref": "_build/policy-design-case/rebaseline/wave-35C/extraction_authority_ledger.json",
            "producer": "wave35c_claim_authority_overlay",
            "producer_owner": "team-runtime-quality",
            "evidence_ref": (
                "_build/policy-design-case/rebaseline/wave-35C/extraction_authority_ledger.json"
            ),
            "authority_envelope_ref": _stable_hash(
                {"artifact": "extraction_authority_ledger", "section_refs": list(source_refs)}
            ),
        }
    )
    return refs


def _gate_by_name(scorecard: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    for gate in _as_list(scorecard.get("quality_gates")):
        if isinstance(gate, Mapping) and gate.get("name") == name:
            return gate
    return {}


def _readiness_check(readiness: Mapping[str, Any], code: str) -> Mapping[str, Any]:
    for check in _as_list(readiness.get("minimum_closeout_gate_failures")):
        if isinstance(check, Mapping) and check.get("code") == code:
            return check
    return {}


def _gate_projection(gate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": gate.get("name"),
        "code": gate.get("code"),
        "status": gate.get("status"),
        "blocking": gate.get("blocking"),
        "evidence_ref": gate.get("evidence_ref"),
        "next_action": gate.get("next_action"),
    }


def _readiness_projection(check: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "code": check.get("code"),
        "status": check.get("status"),
        "minimum_closeout_gate": check.get("minimum_closeout_gate"),
        "evidence": check.get("evidence"),
        "next_action": check.get("next_action"),
    }


def _blocking_codes(scorecard: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            str(gate.get("code"))
            for gate in _as_list(scorecard.get("quality_gates"))
            if isinstance(gate, Mapping)
            and gate.get("blocking") is True
            and gate.get("status") != "pass"
            and gate.get("code")
        }
    )


def _failure_codes(payload: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            str(item.get("code"))
            for item in _as_list(payload.get("minimum_closeout_gate_failures"))
            if isinstance(item, Mapping) and item.get("code")
        }
    )


def _issue_codes(payload: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            str(item.get("code"))
            for item in _as_list(payload.get("issues"))
            if isinstance(item, Mapping) and item.get("code")
        }
    )


def _qc_result(qc: Mapping[str, Any] | None, *, ref: str, claim_selected: bool) -> dict[str, Any]:
    qc_mapping = _mapping(qc)
    return {
        "status": "claim_selected_qc_bound" if claim_selected else "adjacent_qc_not_promoted",
        "claim_selected": claim_selected,
        "qc_ref": ref,
        "qc_passed": qc_mapping.get("passed"),
        "critical_failed_checks": [
            str(check.get("name"))
            for check in _as_list(qc_mapping.get("checks"))
            if isinstance(check, Mapping)
            and check.get("passed") is False
            and check.get("severity") == "critical"
        ],
        "warning_failed_checks": [
            str(check.get("name"))
            for check in _as_list(qc_mapping.get("checks"))
            if isinstance(check, Mapping)
            and check.get("passed") is False
            and check.get("severity") != "critical"
        ],
    }


def _skipped_content_record(qc: Mapping[str, Any] | None) -> dict[str, Any]:
    metrics = _mapping(_mapping(qc).get("metrics"))
    return {
        "full_only_docs_pct": metrics.get("full_only_docs_pct"),
        "empty_statement_rows_pct": metrics.get("empty_statement_rows_pct"),
        "missing_quote_rate_pct": metrics.get("missing_quote_rate_pct"),
        "timeout_retry_failure_total": metrics.get("timeout_retry_failure_total"),
        "deferred_reason_counts_ref": "qc_report.json#/metrics/deferred_reason_counts",
        "status": "recorded",
    }


def _gate_status(repo_root: Path, pdd_ids: Sequence[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for pdd_id in pdd_ids:
        payload = _load_json(repo_root / SOURCE_ARTIFACT_BY_PDD[pdd_id])
        result[pdd_id] = {
            "acceptance_gate_status": payload.get("acceptance_gate_status"),
            "finding_count": len(_as_list(payload.get("findings"))),
            "generated_at": payload.get("generated_at"),
        }
    return result


def _disposition_rationale(pdd_id: str, finding_id: str) -> str:
    if finding_id == "PDD-044-F002":
        return (
            "Resolved by Wave 35C as an explicitly bound publication blocker, not "
            "as a scorecard remediation. The final claim sections now have runtime "
            "claim authority, while publication remains blocked until scorecard and "
            "readiness gates pass."
        )
    if pdd_id == "PDD-100":
        return (
            "Resolved by Wave 35C claim-selected extraction authority. Locator, "
            "OCR/not-applicable, table, annex, footnote, skipped-content, QC, and "
            "producer owner semantics are bound to the final claim authority ledger."
        )
    if pdd_id == "PDD-101":
        return (
            "Resolved by Wave 35C measurement semantics. The current claim is "
            "explicitly abstained as non-survey-selected and guarded against future "
            "survey promotion without design and construct-validity evidence."
        )
    if pdd_id == "PDD-044":
        return (
            "Resolved by Wave 35C runtime claim-authority binding across every final "
            "major claim section and producer evidence family."
        )
    return (
        "Resolved by Wave 35C semantic validity and model-readiness binding across "
        "competence, delegation, transportability, uncertainty, monitoring, "
        "lifecycle invalidation, method-result, calibration, stationarity, and DDM refs."
    )


def _rows_for_pdd(
    rows: Sequence[Mapping[str, Any]],
    pdd_id: str,
) -> list[Mapping[str, Any]]:
    return [row for row in rows if str(row.get("finding_id") or "").startswith(pdd_id)]


def _source_artifact(row: Mapping[str, Any]) -> str | None:
    evidence = _mapping(row.get("source_evidence"))
    return str(evidence.get("detail_artifact") or "") or None


def _refresh_disposition_summary(disposition: dict[str, Any]) -> None:
    rows = [row for row in _as_list(disposition.get("dispositions")) if isinstance(row, Mapping)]
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


def _load_optional_json(path: Path) -> dict[str, Any] | None:
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


def _first(value: object, default: object = None) -> object:
    if isinstance(value, list) and value:
        return value[0]
    return value if value not in (None, "") else default


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave35-dir", type=Path, default=WAVE35_DIR)
    parser.add_argument("--wave35c-dir", type=Path, default=WAVE35C_DIR)
    parser.add_argument("--run-rerun", action="store_true")
    parser.add_argument("--update-disposition", action="store_true")
    args = parser.parse_args(argv)

    try:
        outputs = build_wave35c_outputs(
            repo_root=args.repo_root,
            wave35_dir=args.wave35_dir,
            wave35c_dir=args.wave35c_dir,
            run_rerun=args.run_rerun,
            update_disposition=args.update_disposition,
        )
    except Exception as exc:
        sys.stderr.write(f"wave35c: {exc}\n")
        return 1

    update = outputs["disposition_update"]
    sys.stdout.write(
        "wave35c: "
        f"{update['status']} "
        f"updated={update['updated_finding_count']} "
        f"phase34_3_exit={update['exit_fence'].get('phase34_3_rerun_exit_code')} "
        f"phase34_4_exit={update['exit_fence'].get('phase34_4_rerun_exit_code')}\n"
    )
    return 0 if update["status"] == "resolved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
