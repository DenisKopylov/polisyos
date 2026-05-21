#!/usr/bin/env python3
"""Run Policy Design Case Pass 2 Phase 34.4 diagnostics."""

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

PHASE_ID = "34.4"
PHASE_TITLE = "Phase 34.4 Extraction And Measurement Diagnostics"
PHASE_FILE_STEM = "phase_34_4_extraction_measurement_diagnostics"
SCHEMA_VERSION = "policyos.policy_design_case.pass2.phase34_4_diagnostic.v1"
INDEX_SCHEMA_VERSION = "policyos.policy_design_case.pass2.phase34_4_index.v1"
TOOL_NAME = "quality.validation.run-policy-design-case-pass2-phase34-4"

PDD_SPECS: dict[str, dict[str, str]] = {
    "PDD-100": {
        "pdd_id": "PDD-100",
        "slug": "document_extraction_authority_audit",
        "title": "Audit Document, OCR, Footnote, Annex, And Table Extraction Authority",
        "question": (
            "Can final claims rely on document, OCR, footnote, annex, or table extraction "
            "only when claim-bound extraction-quality evidence proves fidelity?"
        ),
    },
    "PDD-101": {
        "pdd_id": "PDD-101",
        "slug": "survey_measurement_construct_validity_audit",
        "title": "Audit Survey Design, Measurement Error, And Construct-Validity Semantics",
        "question": (
            "Can survey-derived claims pass only when survey design, weighting, nonresponse, "
            "imputation, measurement error, and construct validity are bound to the claim?"
        ),
    },
}


def build_phase34_4_diagnostics(
    *,
    repo_root: Path = REPO_ROOT,
    wave33_dir: Path = DEFAULT_WAVE33_DIR,
) -> tuple[dict[str, Any], Mapping[str, Any]]:
    context = load_wave33_context(repo_root=repo_root, wave33_dir=wave33_dir)
    diagnostics = {
        "PDD-100": _diagnose_pdd_100(context),
        "PDD-101": _diagnose_pdd_101(context),
    }
    return diagnostics, context


def write_phase34_4_outputs(
    *,
    repo_root: Path = REPO_ROOT,
    wave33_dir: Path = DEFAULT_WAVE33_DIR,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> tuple[dict[str, Any], list[Path]]:
    diagnostics, context = build_phase34_4_diagnostics(
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


def _diagnose_pdd_100(context: Mapping[str, Any]) -> dict[str, Any]:
    wave_files = expect_mapping(context.get("wave_files"), "wave_files")
    quality_files = expect_mapping(context.get("quality_files"), "quality_files")
    case_sample = expect_mapping(
        wave_files.get("policy_design_case_sample.json"),
        "policy_design_case_sample",
        required=False,
    )
    scorecard = expect_mapping(
        wave_files.get("quality_scorecard.json"),
        "quality_scorecard",
        required=False,
    )
    normative = expect_mapping(
        quality_files.get("normative_evidence.json"),
        "normative_evidence",
        required=False,
    )
    scholar = expect_mapping(
        quality_files.get("scholar_academic_evidence.json"),
        "scholar_academic_evidence",
        required=False,
    )
    gate_names = [
        str(gate.get("name") or gate.get("code") or "")
        for gate in as_list(scorecard.get("quality_gates"))
        if isinstance(gate, Mapping)
    ]
    findings = [
        {
            "code": "claim_bound_extraction_quality_ledger_missing",
            "severity": "critical",
            "summary": "No runtime claim-bound extraction-quality ledger exists.",
            "evidence": [
                "policy_design_case_sample.json has no extraction_quality_ledgers key.",
                "quality_scorecard.json has no extraction-fidelity gate.",
            ],
        },
        {
            "code": "norm_refs_lack_retrieval_locator_metadata",
            "severity": "critical",
            "summary": (
                "Legal-shaped norm refs are not backed by retrieval, locator, query, "
                "jurisdiction, or time-filter metadata."
            ),
            "evidence": "quality_evidence/normative_evidence.json",
        },
        {
            "code": "batch_extraction_qc_not_claim_authority",
            "severity": "high",
            "summary": (
                "Batch extraction QC exists adjacent to the run, but is not promoted "
                "into claim-selected authority for Wave 33."
            ),
            "evidence": [
                "production_data/lex/lex-amendment-only-optimized-20260501-v3/finalize/qc_report.json",
                "quality_evidence/policy_grounding_matrix.json",
            ],
        },
        {
            "code": "difficult_document_classes_unproven_at_runtime",
            "severity": "high",
            "summary": (
                "Table, appendix, annex, footnote, signature, skipped-page, and OCR "
                "confidence classes remain unproven in runtime evidence."
            ),
            "evidence": "quality_evidence/normative_evidence.json",
        },
        {
            "code": "scholar_fulltext_quality_not_claim_selected",
            "severity": "medium",
            "summary": (
                "Scholar full-text/span quality is adjacent evidence, not a claim-level "
                "extraction authority ref for Wave 33."
            ),
            "evidence": "quality_evidence/scholar_academic_evidence.json",
        },
    ]
    evidence = {
        "policy_design_case_extraction_keys": {
            "has_extraction_quality_ledgers": "extraction_quality_ledgers"
            in case_sample,
            "concept_spine_node_count": len(as_list(case_sample.get("nodes"))),
        },
        "scorecard_extraction_gates": [
            name
            for name in gate_names
            if any(token in name.lower() for token in ("extract", "ocr", "table"))
        ],
        "normative_evidence": {
            "status": normative.get("status"),
            "issue_codes": _issue_codes(normative),
        },
        "scholar_evidence": {
            "status": scholar.get("status"),
            "summary": scholar.get("summary"),
        },
    }
    return canonical_diagnostic(
        context=context,
        spec=PDD_SPECS["PDD-100"],
        tool_name=TOOL_NAME,
        schema_version=SCHEMA_VERSION,
        phase=PHASE_ID,
        verdict="confirmed_no_claim_bound_extraction_quality_ledger",
        acceptance_gate_status="failed",
        findings=findings,
        evidence=evidence,
        recommended_gate=(
            "Fail final claim support when document extraction evidence lacks "
            "claim-bound locator, OCR/table/annex fidelity, skipped-content, and "
            "extraction-QC refs."
        ),
        backlog_summary=(
            "Wave 33 proves the legal and source evidence can fail closed, but it "
            "does not emit a claim-bound extraction-quality ledger. Adjacent Lex and "
            "Scholar QC cannot substitute for runtime extraction authority."
        ),
        recommended_remediation_id="PDD-100-A1",
    )


def _diagnose_pdd_101(context: Mapping[str, Any]) -> dict[str, Any]:
    wave_files = expect_mapping(context.get("wave_files"), "wave_files")
    quality_files = expect_mapping(context.get("quality_files"), "quality_files")
    case_sample = expect_mapping(
        wave_files.get("policy_design_case_sample.json"),
        "policy_design_case_sample",
        required=False,
    )
    production_quality = expect_mapping(
        quality_files.get("production_data_quality.json"),
        "production_data_quality",
        required=False,
    )
    foundry = expect_mapping(
        quality_files.get("foundry_method_report.json"),
        "foundry_method_report",
        required=False,
    )
    grounding = expect_mapping(
        wave_files.get("policy_grounding_matrix.json"),
        "policy_grounding_matrix",
        required=False,
    )
    findings = [
        {
            "code": "survey_to_claim_measurement_ledger_missing",
            "severity": "critical",
            "summary": "No survey-to-claim or measurement-error ledger exists.",
            "evidence": [
                "policy_design_case_sample.json has no survey_to_claim_ledgers key.",
                "quality_scorecard.json has no survey/measurement gate.",
            ],
        },
        {
            "code": "survey_catalog_records_lack_design_semantics",
            "severity": "critical",
            "summary": (
                "Survey candidate sources can be cataloged without design semantics "
                "such as weights, nonresponse, imputation, strata, clusters, or "
                "construct definitions."
            ),
            "evidence": "production_data/datasets_full_phase3full_20260327_183054/all_records.jsonl",
        },
        {
            "code": "generic_construct_validity_can_pass_without_survey_semantics",
            "severity": "high",
            "summary": (
                "Generic construct-validity evidence can pass without survey design "
                "or measurement-error support."
            ),
            "evidence": "quality_evidence/production_data_quality.json",
        },
        {
            "code": "non_survey_current_claim_has_no_typed_abstention",
            "severity": "high",
            "summary": (
                "The current claim is not survey-selected, but Wave 33 does not emit "
                "a typed non-survey abstention or future-survey guard."
            ),
            "evidence": "_build/policy-design-case/rebaseline/wave-33/policy_grounding_matrix.json",
        },
        {
            "code": "method_blockers_not_survey_measurement_specific",
            "severity": "medium",
            "summary": (
                "Method blockers are generic rather than survey-measurement-specific."
            ),
            "evidence": "quality_evidence/foundry_method_report.json",
        },
    ]
    evidence = {
        "policy_design_case_survey_keys": {
            "has_survey_to_claim_ledgers": "survey_to_claim_ledgers" in case_sample,
            "has_measurement_error_ledgers": "measurement_error_ledgers"
            in case_sample,
        },
        "production_data_construct_validity": production_quality.get(
            "construct_validity"
        ),
        "claim_data_refs": _claim_data_refs(grounding),
        "foundry_issue_codes": _issue_codes(foundry),
    }
    return canonical_diagnostic(
        context=context,
        spec=PDD_SPECS["PDD-101"],
        tool_name=TOOL_NAME,
        schema_version=SCHEMA_VERSION,
        phase=PHASE_ID,
        verdict="confirmed_no_survey_to_claim_measurement_ledger",
        acceptance_gate_status=(
            "failed_for_survey_capability_current_claim_not_survey_selected"
        ),
        findings=findings,
        evidence=evidence,
        recommended_gate=(
            "Fail or explicitly abstain when a survey-capable source path lacks "
            "claim-bound design, weighting, nonresponse, imputation, measurement-error, "
            "construct, and subgroup-support evidence."
        ),
        backlog_summary=(
            "Wave 33's current claim relies on production-panel style sources, but "
            "the runtime still lacks a survey-to-claim abstention and measurement "
            "contract. Survey-shaped catalog records can exist without design "
            "semantics, so future survey evidence could enter as generic production data."
        ),
        recommended_remediation_id="PDD-101-A1",
    )


def _issue_codes(payload: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []
    for key in ("issues", "blocking_issues", "failures"):
        for item in as_list(payload.get(key)):
            if isinstance(item, Mapping) and item.get("code"):
                codes.append(str(item["code"]))
            elif isinstance(item, str):
                codes.append(item)
    return codes


def _claim_data_refs(grounding: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for claim in as_list(grounding.get("claims")):
        if isinstance(claim, Mapping):
            refs.extend(str(ref) for ref in as_list(claim.get("data_refs")))
    return refs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave33-dir", type=Path, default=DEFAULT_WAVE33_DIR)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload, written = write_phase34_4_outputs(
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
