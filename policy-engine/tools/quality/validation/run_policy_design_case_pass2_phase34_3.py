#!/usr/bin/env python3
"""Run Policy Design Case Pass 2 Phase 34.3 diagnostics."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json, atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.policy_design_case.pass2.phase34_3_diagnostic.v1"
INDEX_SCHEMA_VERSION = "policyos.policy_design_case.pass2.phase34_3_index.v1"
TOOL_NAME = "quality.validation.run-policy-design-case-pass2-phase34-3"
DEFAULT_WAVE33_DIR = Path("_build/policy-design-case/rebaseline/wave-33")
DEFAULT_OUTPUT_ROOT = Path("_build/diagnostics")
BACKLOG_FRAGMENT_DIR = Path("pass2/backlog_fragments")
PHASE_ID = "34.3"
WAVE_ID = "34"

PDD_SPECS: dict[str, dict[str, str]] = {
    "PDD-044": {
        "slug": "final_artifact_section_grounding_audit",
        "title": "Audit Final Artifact Section Grounding",
        "question": (
            "Does every major final decision section have source, method, norm, "
            "or typed-blocker refs?"
        ),
    },
    "PDD-048": {
        "slug": "institutional_competence_authority_audit",
        "title": "Audit Institutional Competence And Implementing Authority",
        "question": (
            "Does each recommendation identify a legally competent implementing "
            "authority?"
        ),
    },
    "PDD-050": {
        "slug": "external_validity_transferability_audit",
        "title": "Audit External Validity And Transferability Gate",
        "question": (
            "Does source-context evidence pass an explicit transferability check "
            "before supporting target policy claims?"
        ),
    },
    "PDD-051": {
        "slug": "uncertainty_propagation_chain_audit",
        "title": "Audit Uncertainty Propagation Chain",
        "question": (
            "Is uncertainty carried from retrieval, data quality, methods, models, "
            "legal ambiguity, and feasibility into final claims and approval?"
        ),
    },
    "PDD-057": {
        "slug": "final_decision_monitoring_claim_binding_audit",
        "title": "Audit Final Decision Monitoring Claim Binding",
        "question": (
            "Is every monitor, stale trigger, reissue trigger, and withdrawal path "
            "linked to original claims, assumptions, risks, norms, or milestones?"
        ),
    },
    "PDD-087": {
        "slug": "model_registry_readiness_binding_audit",
        "title": "Audit DDM/Model-Registry Readiness Binding To Policy Evidence",
        "question": (
            "Are model readiness, drift, calibration, incident, and registry states "
            "bound to the policy claims that use those models?"
        ),
    },
    "PDD-088": {
        "slug": "berl_explanation_reliability_binding_audit",
        "title": "Audit BERL Explanation Reliability Binding To Final Policy Claims",
        "question": (
            "Are explanation bundles used only within their declared reliability, "
            "support, method, and display-policy limits?"
        ),
    },
}

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
    "provider_model_quality_ledger",
    "public_export_bundle",
    "quality_scorecard",
    "semantic_binding_ledger",
)


class Phase34InputError(ValueError):
    """Raised when required Wave 33 evidence is absent or malformed."""


def build_phase34_3_payload(
    *,
    repo_root: Path = REPO_ROOT,
    wave33_dir: Path = DEFAULT_WAVE33_DIR,
) -> dict[str, Any]:
    """Build the complete Phase 34.3 diagnostic payload without writing files."""

    evidence = load_wave33_evidence(repo_root=repo_root, wave33_dir=wave33_dir)
    diagnostics = {
        "PDD-044": _diagnose_pdd_044(evidence),
        "PDD-048": _diagnose_pdd_048(evidence),
        "PDD-050": _diagnose_pdd_050(evidence),
        "PDD-051": _diagnose_pdd_051(evidence),
        "PDD-057": _diagnose_pdd_057(evidence),
        "PDD-087": _diagnose_pdd_087(evidence),
        "PDD-088": _diagnose_pdd_088(evidence),
    }
    runtime_acceptance_status = _aggregate_acceptance_status(diagnostics.values())
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": evidence["generated_at"],
        "wave": WAVE_ID,
        "phase": PHASE_ID,
        "status": "diagnosed",
        "runtime_acceptance_status": runtime_acceptance_status,
        "repo_root": str(evidence["repo_root"]),
        "wave33": evidence["wave33_summary"],
        "summary": {
            "pdd_count": len(diagnostics),
            "diagnosed_count": len(diagnostics),
            "blocking_or_failed_count": sum(
                1
                for item in diagnostics.values()
                if item["acceptance_gate_status"] in {"failed", "blocked"}
            ),
            "not_triggered_count": sum(
                1
                for item in diagnostics.values()
                if item["acceptance_gate_status"].startswith("not_triggered")
            ),
        },
        "diagnostics": diagnostics,
    }


def load_wave33_evidence(
    *,
    repo_root: Path = REPO_ROOT,
    wave33_dir: Path = DEFAULT_WAVE33_DIR,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    wave33_path = _resolve(repo_root, wave33_dir)
    baseline = _load_json(wave33_path / "real_domain_baseline.json")
    research_case = _expect_mapping(
        baseline.get("research_profile_case"),
        "real_domain_baseline.research_profile_case",
    )
    bundle_rel = str(research_case.get("bundle_path") or "")
    if not bundle_rel:
        raise Phase34InputError("Wave 33 baseline is missing research bundle path.")
    bundle_path = _resolve(repo_root, Path(bundle_rel))
    quality_dir = bundle_path / "quality_evidence"

    wave_files = {
        "claim_argument": _load_json(wave33_path / "claim_argument.json"),
        "policy_design_case_sample": _load_json(
            wave33_path / "policy_design_case_sample.json"
        ),
        "policy_grounding_matrix": _load_json(
            wave33_path / "policy_grounding_matrix.json"
        ),
        "production_data_evidence": _load_json(
            wave33_path / "production_data_evidence.json"
        ),
        "quality_scorecard": _load_json(wave33_path / "quality_scorecard.json"),
        "readiness": _load_json(wave33_path / "readiness.json"),
    }
    quality_files = {
        name: _load_optional_json(quality_dir / f"{name}.json")
        for name in QUALITY_FILES
    }
    if quality_files["quality_scorecard"] is None:
        quality_files["quality_scorecard"] = wave_files["quality_scorecard"]
    if quality_files["policy_grounding_matrix"] is None:
        quality_files["policy_grounding_matrix"] = wave_files["policy_grounding_matrix"]

    generated_at = str(baseline.get("generated_at") or "2026-05-18T18:57:46+00:00")
    scorecard = _expect_mapping(quality_files["quality_scorecard"], "quality_scorecard")
    claim_argument = _expect_mapping(wave_files["claim_argument"], "claim_argument")
    grounding = _expect_mapping(
        quality_files["policy_grounding_matrix"],
        "policy_grounding_matrix",
    )
    return {
        "repo_root": repo_root,
        "wave33_dir": wave33_path,
        "bundle_path": bundle_path,
        "generated_at": generated_at,
        "baseline": baseline,
        "research_case": research_case,
        "wave_files": wave_files,
        "quality_files": quality_files,
        "wave33_summary": {
            "run_id": research_case.get("run_id"),
            "job_id": research_case.get("job_id"),
            "case_id": research_case.get("case_id"),
            "lane_id": research_case.get("lane_id"),
            "bundle_path": _rel(repo_root, bundle_path),
            "matrix_status": research_case.get("matrix_status"),
            "scorecard_status": research_case.get("scorecard_status"),
            "claim_argument_status": claim_argument.get("claim", {}).get("status")
            if isinstance(claim_argument.get("claim"), Mapping)
            else None,
            "policy_grounding_status": grounding.get("status"),
            "scorecard_blocking_code_count": len(_blocking_codes(scorecard)),
        },
        "source_artifacts": {
            "real_domain_baseline": _rel(wave33_path, wave33_path / "real_domain_baseline.json"),
            "claim_argument": _rel(wave33_path, wave33_path / "claim_argument.json"),
            "policy_design_case_sample": _rel(
                wave33_path,
                wave33_path / "policy_design_case_sample.json",
            ),
            "policy_grounding_matrix": _rel(
                wave33_path,
                wave33_path / "policy_grounding_matrix.json",
            ),
            "quality_scorecard": _rel(wave33_path, wave33_path / "quality_scorecard.json"),
            "bundle": _rel(repo_root, bundle_path),
        },
    }


def write_phase34_3_outputs(
    payload: Mapping[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> list[Path]:
    """Write JSON, Markdown, summaries, and backlog fragments."""

    repo_root = repo_root.resolve()
    output_dir = _resolve(repo_root, output_root, must_exist=False)
    written: list[Path] = []
    diagnostics = _expect_mapping(payload.get("diagnostics"), "diagnostics")
    for pdd_id in PDD_SPECS:
        diagnostic = _expect_mapping(diagnostics.get(pdd_id), pdd_id)
        slug = PDD_SPECS[pdd_id]["slug"]
        pdd_dir = output_dir / pdd_id.lower()
        json_path = pdd_dir / f"{slug}.json"
        md_path = pdd_dir / f"{slug}.md"
        summary_path = pdd_dir / "summary.md"
        fragment_path = output_dir / BACKLOG_FRAGMENT_DIR / f"{pdd_id.lower()}.md"

        atomic_write_json(json_path, diagnostic)
        atomic_write_text(md_path, render_diagnostic_markdown(diagnostic))
        atomic_write_text(summary_path, render_summary_markdown(diagnostic))
        atomic_write_text(fragment_path, render_backlog_fragment(diagnostic))
        written.extend([json_path, md_path, summary_path, fragment_path])

    index_path = output_dir / "pass2" / "phase_34_3_claim_grounding_validity_index.json"
    index_md_path = output_dir / "pass2" / "phase_34_3_claim_grounding_validity_index.md"
    atomic_write_json(index_path, payload)
    atomic_write_text(index_md_path, render_index_markdown(payload))
    written.extend([index_path, index_md_path])
    return written


def dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def render_diagnostic_markdown(diagnostic: Mapping[str, Any]) -> str:
    lines = [
        f"# {diagnostic['pdd_id']} Diagnostic: {diagnostic['title']}",
        "",
        f"Generated: {diagnostic['generated_at']}",
        "",
        f"Phase: {diagnostic['phase']}",
        "",
        f"Verdict: `{diagnostic['verdict']}`",
        "",
        f"Acceptance gate status: `{diagnostic['acceptance_gate_status']}`.",
        "",
        "## Question",
        "",
        str(diagnostic["question"]),
        "",
        "## Wave 33 Evidence",
        "",
        _table(
            ("Field", "Observed value"),
            [
                ("run_id", _string(diagnostic["wave33"]["run_id"])),
                ("job_id", _string(diagnostic["wave33"]["job_id"])),
                ("lane_id", _string(diagnostic["wave33"]["lane_id"])),
                ("bundle_path", _code(diagnostic["wave33"]["bundle_path"])),
                ("scorecard_status", _string(diagnostic["wave33"]["scorecard_status"])),
                (
                    "policy_grounding_status",
                    _string(diagnostic["wave33"]["policy_grounding_status"]),
                ),
            ],
        ),
        "",
        "## Findings",
        "",
    ]
    findings = _as_list(diagnostic.get("findings"))
    if findings:
        for finding in findings:
            if not isinstance(finding, Mapping):
                continue
            lines.append(
                "- `{code}` ({severity}): {summary}".format(
                    code=finding.get("code"),
                    severity=finding.get("severity"),
                    summary=finding.get("summary"),
                )
            )
            evidence = finding.get("evidence")
            if evidence:
                lines.append(f"  Evidence: {_string(evidence)}")
    else:
        lines.append("- No active Wave 33 violation detected for this PDD.")
    lines.extend(
        [
            "",
            "## Evidence Details",
            "",
        ]
    )
    for key, value in _expect_mapping(diagnostic.get("evidence"), "evidence").items():
        lines.append(f"### {key}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(value, indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")

    lines.extend(
        [
            "## Recommended Gate",
            "",
            _string(diagnostic.get("recommended_gate")),
            "",
            "## Backlog Fragment",
            "",
            _string(diagnostic.get("backlog_summary")),
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_summary_markdown(diagnostic: Mapping[str, Any]) -> str:
    pdd_id = str(diagnostic["pdd_id"])
    pdd_dir = pdd_id.lower()
    slug = PDD_SPECS[pdd_id]["slug"]
    lines = [
        f"# {diagnostic['pdd_id']} Summary",
        "",
        f"Status: `{diagnostic['diagnostic_status']}`",
        "",
        f"Verdict: `{diagnostic['verdict']}`",
        "",
        str(diagnostic["backlog_summary"]),
        "",
        "## Strongest Findings",
        "",
    ]
    findings = _as_list(diagnostic.get("findings"))
    if findings:
        for index, finding in enumerate(findings, start=1):
            if isinstance(finding, Mapping):
                lines.append(f"{index}. `{finding.get('code')}` - {finding.get('summary')}")
    else:
        lines.append("1. No active violation detected in Wave 33 evidence.")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- `_build/diagnostics/{pdd_dir}/{slug}.md`",
            f"- `_build/diagnostics/{pdd_dir}/{slug}.json`",
            f"- `_build/diagnostics/pass2/backlog_fragments/{pdd_dir}.md`",
            "",
        ]
    )
    return "\n".join(lines)


def render_backlog_fragment(diagnostic: Mapping[str, Any]) -> str:
    findings = _as_list(diagnostic.get("findings"))
    pdd_id = str(diagnostic["pdd_id"])
    pdd_dir = pdd_id.lower()
    slug = PDD_SPECS[pdd_id]["slug"]
    lines = [
        f"### {diagnostic['pdd_id']} - {diagnostic['title']}",
        "",
        f"- Phase: {diagnostic['phase']}",
        f"- Diagnostic status: `{diagnostic['diagnostic_status']}`",
        f"- Verdict: `{diagnostic['verdict']}`",
        f"- Acceptance gate status: `{diagnostic['acceptance_gate_status']}`",
        f"- Finding count: {len(findings)}",
        f"- Detailed artifact: `_build/diagnostics/{pdd_dir}/{slug}.md`",
        f"- Machine artifact: `_build/diagnostics/{pdd_dir}/{slug}.json`",
        "",
        str(diagnostic["backlog_summary"]),
        "",
    ]
    if findings:
        lines.append("Finding seeds:")
        lines.append("")
        for finding in findings:
            if isinstance(finding, Mapping):
                lines.append(f"- `{finding.get('code')}`: {finding.get('summary')}")
        lines.append("")
    return "\n".join(lines)


def render_index_markdown(payload: Mapping[str, Any]) -> str:
    diagnostics = _expect_mapping(payload.get("diagnostics"), "diagnostics")
    rows = []
    for pdd_id in PDD_SPECS:
        diagnostic = _expect_mapping(diagnostics.get(pdd_id), pdd_id)
        rows.append(
            (
                pdd_id,
                _code(diagnostic["verdict"]),
                _code(diagnostic["acceptance_gate_status"]),
                str(len(_as_list(diagnostic.get("findings")))),
            )
        )
    return "\n".join(
        [
            "# Phase 34.3 Claim Grounding And Validity Diagnostics",
            "",
            f"Generated: {payload['generated_at']}",
            "",
            _table(("PDD", "Verdict", "Gate", "Findings"), rows),
            "",
        ]
    )


def _base_diagnostic(evidence: Mapping[str, Any], pdd_id: str) -> dict[str, Any]:
    spec = PDD_SPECS[pdd_id]
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": evidence["generated_at"],
        "wave": WAVE_ID,
        "phase": PHASE_ID,
        "pdd_id": pdd_id,
        "title": spec["title"],
        "question": spec["question"],
        "backlog_item": {
            "path": "docs/backlog/production-data-e2e-diagnostic-backlog.md",
            "id": pdd_id,
        },
        "source_artifacts": evidence["source_artifacts"],
        "wave33": evidence["wave33_summary"],
    }


def _diagnose_pdd_044(evidence: Mapping[str, Any]) -> dict[str, Any]:
    grounding = _quality(evidence, "policy_grounding_matrix")
    decision = _quality(evidence, "decision_artifact_quality")
    claims = _as_list(grounding.get("claims"))
    section_rows = []
    missing_section_refs: list[dict[str, str]] = []
    for claim in claims:
        if not isinstance(claim, Mapping):
            continue
        section_refs = _expect_mapping(
            claim.get("section_evidence_refs"),
            f"{claim.get('claim_id')}.section_evidence_refs",
            required=False,
        )
        missing = [
            section
            for section in REQUIRED_FINAL_SECTIONS
            if not _as_list(section_refs.get(section))
        ]
        for section in missing:
            missing_section_refs.append(
                {"claim_id": str(claim.get("claim_id")), "section": section}
            )
        section_rows.append(
            {
                "claim_id": claim.get("claim_id"),
                "grounding_status": claim.get("grounding_status"),
                "data_ref_count": len(_as_list(claim.get("data_refs"))),
                "method_ref_count": len(_as_list(claim.get("method_refs"))),
                "norm_ref_count": len(_as_list(claim.get("norm_refs"))),
                "section_count": len(section_refs),
                "missing_required_sections": missing,
            }
        )
    decision_issue_codes = _issue_codes(decision)
    findings: list[dict[str, Any]] = []
    if missing_section_refs:
        findings.append(
            _finding(
                "final_section_grounding_refs_missing",
                "blocker",
                "One or more required final sections lacks evidence refs or blockers.",
                missing_section_refs,
            )
        )
    if "claim_compiler_runtime_registry_missing" in decision_issue_codes:
        findings.append(
            _finding(
                "claim_compiler_runtime_registry_missing",
                "blocker",
                (
                    "Major claim sections have refs, but publishable compiler output "
                    "is not bound through the runtime claim registry."
                ),
                "quality_evidence/decision_artifact_quality.json",
            )
        )
    if "publishable_artifact_scorecard_not_passing" in decision_issue_codes:
        findings.append(
            _finding(
                "publishable_artifact_scorecard_not_passing",
                "blocker",
                (
                    "The final artifact cannot be promoted while upstream Wave 33 "
                    "scorecard blockers remain."
                ),
                "quality_evidence/decision_artifact_quality.json",
            )
        )
    payload = _base_diagnostic(evidence, "PDD-044")
    payload.update(
        {
            "diagnostic_status": "diagnosed",
            "verdict": "section_refs_present_but_publishable_compiler_gate_blocked",
            "acceptance_gate_status": "blocked",
            "findings": findings,
            "evidence": {
                "policy_grounding_summary": grounding.get("summary"),
                "claim_section_grounding": section_rows,
                "grounding_issues": grounding.get("issues", []),
                "decision_artifact_quality_summary": decision.get("summary"),
                "decision_artifact_issue_codes": decision_issue_codes,
            },
            "recommended_gate": (
                "Keep section-level refs, but require runtime claim-registry "
                "selection plus passing scorecard/approval before any final artifact "
                "is publishable."
            ),
            "backlog_summary": (
                "Wave 33 proves the final recommendation carries data, method, norm, "
                "and section evidence refs, so the narrow section-grounding surface is "
                "present. The artifact still fails compiler-grade closeout because the "
                "runtime claim registry is missing and the quality scorecard is not passing."
            ),
        }
    )
    return payload


def _diagnose_pdd_048(evidence: Mapping[str, Any]) -> dict[str, Any]:
    normative = _quality(evidence, "normative_evidence")
    sample = _wave(evidence, "policy_design_case_sample")
    semantic = _quality(evidence, "semantic_binding_ledger")
    jurisdiction_spine = _expect_mapping(
        sample.get("jurisdiction_spine"),
        "policy_design_case_sample.jurisdiction_spine",
        required=False,
    )
    applied_norms = _as_list(normative.get("applied_norms"))
    missing_competence_norms = [
        {
            "norm_id": norm.get("norm_id"),
            "authority_level": norm.get("authority_level"),
            "source_authority": norm.get("source_authority"),
        }
        for norm in applied_norms
        if isinstance(norm, Mapping)
        and not (norm.get("competence") and norm.get("competent_authority"))
    ]
    lex_bindings = _as_list(semantic.get("lex"))
    competence_refs = [
        ref
        for binding in lex_bindings
        if isinstance(binding, Mapping)
        for ref in _as_list(binding.get("competence_refs"))
    ]
    blockers = _as_list(jurisdiction_spine.get("blockers"))
    findings = [
        _finding(
            "implementing_authority_competence_refs_missing",
            "blocker",
            (
                "Selected norms are applied as scenario-contract refs without "
                "competent authority and delegated competence refs."
            ),
            missing_competence_norms,
        ),
        _finding(
            "jurisdiction_spine_unresolved_competence_blocker",
            "blocker",
            (
                "The runtime jurisdiction spine already blocks because UA competence "
                "evidence is unresolved."
            ),
            blockers,
        ),
    ]
    payload = _base_diagnostic(evidence, "PDD-048")
    payload.update(
        {
            "diagnostic_status": "diagnosed",
            "verdict": "confirmed_missing_implementing_competence_binding",
            "acceptance_gate_status": "failed",
            "findings": findings,
            "evidence": {
                "normative_status": normative.get("status"),
                "normative_summary": normative.get("summary"),
                "applied_norms_missing_competence": missing_competence_norms,
                "semantic_lex_competence_refs": competence_refs,
                "jurisdiction_spine_status": jurisdiction_spine.get("status"),
                "jurisdiction_spine_blockers": blockers,
                "scorecard_codes": _blocking_codes(_quality(evidence, "quality_scorecard")),
            },
            "recommended_gate": (
                "Require each final recommendation to cite an implementing actor, "
                "competent authority, legal basis, delegation scope, jurisdiction, "
                "and effective-date validity, or emit a typed competence blocker."
            ),
            "backlog_summary": (
                "Wave 33 confirms PDD-048 as an active blocker. Norms are selected "
                "from the deterministic scenario contract, but there are no competence "
                "refs, no implementing authority chain, and the jurisdiction spine "
                "blocks on `policy_design_jurisdiction_unresolved_competence_blocker`."
            ),
        }
    )
    return payload


def _diagnose_pdd_050(evidence: Mapping[str, Any]) -> dict[str, Any]:
    foundry = _quality(evidence, "foundry_method_report")
    semantic = _quality(evidence, "semantic_binding_ledger")
    grounding = _quality(evidence, "policy_grounding_matrix")
    transport_issues = [
        issue
        for issue in _as_list(foundry.get("issues"))
        if isinstance(issue, Mapping)
        and issue.get("code") == "method_transportability_limits_missing"
    ]
    foundry_bindings = _as_list(semantic.get("foundry"))
    sensitivity_refs = [
        ref
        for binding in foundry_bindings
        if isinstance(binding, Mapping)
        for ref in _as_list(binding.get("sensitivity_refs"))
    ]
    findings = [
        _finding(
            "method_transportability_limits_missing",
            "blocker",
            (
                "Selected Foundry methods do not carry target-population or "
                "support-limit transportability refs."
            ),
            transport_issues,
        ),
        _finding(
            "source_target_context_comparison_missing",
            "blocker",
            (
                "The claim cites a sensitivity/transportability method ref, but the "
                "evidence does not include a source-context versus target-context "
                "comparison."
            ),
            "quality_evidence/foundry_method_report.json",
        ),
    ]
    payload = _base_diagnostic(evidence, "PDD-050")
    payload.update(
        {
            "diagnostic_status": "diagnosed",
            "verdict": "confirmed_external_validity_gate_not_bound_to_claim_support",
            "acceptance_gate_status": "failed",
            "findings": findings,
            "evidence": {
                "foundry_status": foundry.get("status"),
                "foundry_summary": foundry.get("summary"),
                "transportability_issue_count": len(transport_issues),
                "semantic_sensitivity_refs": sensitivity_refs,
                "claim_method_refs": [
                    claim.get("method_refs")
                    for claim in _as_list(grounding.get("claims"))
                    if isinstance(claim, Mapping)
                ],
            },
            "recommended_gate": (
                "Require empirical claims to bind source context, target context, "
                "transfer assumptions, violations, sensitivity bounds, and a downgrade "
                "or blocker before recommendation promotion."
            ),
            "backlog_summary": (
                "Wave 33 has a method ref named "
                "`foundry.sensitivity_or_transportability_diagnostic`, but the "
                "selected methods all lack transportability limits and no source-target "
                "comparison is bound to the final claim. PDD-050 remains failed."
            ),
        }
    )
    return payload


def _diagnose_pdd_051(evidence: Mapping[str, Any]) -> dict[str, Any]:
    foundry = _quality(evidence, "foundry_method_report")
    semantic = _quality(evidence, "semantic_binding_ledger")
    claim_argument = _wave(evidence, "claim_argument")
    method_issue_codes = _issue_codes(foundry)
    selected_methods = _as_list(foundry.get("selected_methods"))
    local_intervals = [
        {
            "method_id": method.get("method_id"),
            "uncertainty": method.get("uncertainty"),
            "sensitivity": method.get("sensitivity"),
        }
        for method in selected_methods
        if isinstance(method, Mapping)
    ]
    required_uncertainty_refs = []
    for surface in ("foundry", "scientist", "final_compiler"):
        for binding in _as_list(semantic.get(surface)):
            if isinstance(binding, Mapping):
                required_uncertainty_refs.extend(
                    _as_list(binding.get("required_uncertainty_refs"))
                    + _as_list(binding.get("uncertainty_refs"))
                    + _as_list(binding.get("residual_uncertainty_ids"))
                )
    findings = [
        _finding(
            "uncertainty_refs_not_bound_end_to_end",
            "blocker",
            (
                "Wave 33 has local uncertainty text and intervals but no end-to-end "
                "uncertainty refs in semantic claim bindings."
            ),
            {"required_uncertainty_refs": required_uncertainty_refs},
        ),
        _finding(
            "method_result_refs_missing",
            "blocker",
            (
                "Foundry uncertainty is not backed by persisted method-result refs "
                "for the final claim."
            ),
            method_issue_codes,
        ),
    ]
    payload = _base_diagnostic(evidence, "PDD-051")
    payload.update(
        {
            "diagnostic_status": "diagnosed",
            "verdict": "confirmed_uncertainty_local_not_end_to_end",
            "acceptance_gate_status": "failed",
            "findings": findings,
            "evidence": {
                "foundry_status": foundry.get("status"),
                "local_method_uncertainty": local_intervals,
                "semantic_required_uncertainty_refs": required_uncertainty_refs,
                "claim_argument_confidence_limits": claim_argument.get("confidence_limits"),
                "claim_argument_unresolved_uncertainty": claim_argument.get(
                    "unresolved_uncertainty"
                ),
                "foundry_issue_codes": method_issue_codes,
            },
            "recommended_gate": (
                "Require a per-claim uncertainty ledger that combines data, method, "
                "legal, model, and implementation uncertainty and blocks approval "
                "when residual uncertainty exceeds the risk threshold."
            ),
            "backlog_summary": (
                "Wave 33 exposes uncertainty language and local method intervals, "
                "but the semantic bindings have no required uncertainty refs and the "
                "claim argument remains blocked with a 0.0 to 0.49 confidence envelope. "
                "PDD-051 remains failed."
            ),
        }
    )
    return payload


def _diagnose_pdd_057(evidence: Mapping[str, Any]) -> dict[str, Any]:
    grounding = _quality(evidence, "policy_grounding_matrix")
    semantic = _quality(evidence, "semantic_binding_ledger")
    governance_reports = {
        name: _quality(evidence, name)
        for name in (
            "continuous_governance_stale_report",
            "continuous_governance_reissue_report",
            "continuous_governance_supersede_report",
            "continuous_governance_withdraw_report",
        )
    }
    claim_monitoring = [
        {
            "claim_id": claim.get("claim_id"),
            "monitoring_plan": claim.get("monitoring_plan"),
            "withdrawal_reissue_triggers": claim.get("withdrawal_reissue_triggers"),
        }
        for claim in _as_list(grounding.get("claims"))
        if isinstance(claim, Mapping)
    ]
    monitoring_ids = []
    for surface in ("scientist", "final_compiler"):
        for binding in _as_list(semantic.get(surface)):
            if isinstance(binding, Mapping):
                monitoring_ids.extend(_as_list(binding.get("monitoring_ids")))
    lifecycle_rows = {
        name: {
            "status": report.get("status"),
            "decision_status": report.get("decision_status"),
            "lifecycle_decision": report.get("lifecycle_decision"),
            "reason": report.get("reason"),
        }
        for name, report in governance_reports.items()
    }
    findings = [
        _finding(
            "claim_to_monitor_map_missing",
            "blocker",
            (
                "The final claim has generic monitoring text, but semantic bindings "
                "expose no monitoring ids or claim-to-monitor map."
            ),
            {"monitoring_ids": monitoring_ids},
        ),
        _finding(
            "lifecycle_events_do_not_name_invalidated_claims",
            "blocker",
            (
                "Continuous governance records are no-op lifecycle passes and do not "
                "identify invalidated claims, assumptions, or downstream impacts."
            ),
            lifecycle_rows,
        ),
    ]
    payload = _base_diagnostic(evidence, "PDD-057")
    payload.update(
        {
            "diagnostic_status": "diagnosed",
            "verdict": "confirmed_monitoring_plan_not_claim_bound",
            "acceptance_gate_status": "failed",
            "findings": findings,
            "evidence": {
                "claim_monitoring_fields": claim_monitoring,
                "semantic_monitoring_ids": monitoring_ids,
                "governance_lifecycle_reports": lifecycle_rows,
            },
            "recommended_gate": (
                "Require claim id, assumption, risk, legal norm, threshold, owner, "
                "cadence, data refresh, and reissue trigger for every production monitor."
            ),
            "backlog_summary": (
                "Wave 33 includes generic monitoring and withdrawal/reissue text on the "
                "claim, but there is no claim-to-monitor map. Lifecycle reports are no-op "
                "passes and do not name invalidated claims or assumptions. PDD-057 failed."
            ),
        }
    )
    return payload


def _diagnose_pdd_087(evidence: Mapping[str, Any]) -> dict[str, Any]:
    provider = _quality(evidence, "provider_model_quality_ledger")
    foundry = _quality(evidence, "foundry_method_report")
    semantic = _quality(evidence, "semantic_binding_ledger")
    grounding = _quality(evidence, "policy_grounding_matrix")
    model_dependency_refs = []
    for surface in ("scientist", "final_compiler", "foundry"):
        for binding in _as_list(semantic.get(surface)):
            if isinstance(binding, Mapping):
                for key in (
                    "model_refs",
                    "model_output_refs",
                    "ddm_readiness_refs",
                    "calibration_refs",
                    "stationarity_refs",
                ):
                    model_dependency_refs.extend(_as_list(binding.get(key)))
    findings = [
        _finding(
            "claim_to_model_dependency_map_missing",
            "blocker",
            (
                "Claims and selected methods do not carry model-output dependency refs, "
                "DDM readiness refs, calibration refs, or stationarity refs."
            ),
            {"model_dependency_refs": model_dependency_refs},
        ),
        _finding(
            "method_result_refs_missing",
            "blocker",
            (
                "Policy claims cite method families, but selected Foundry methods have "
                "no persisted method-result refs to bind model readiness against."
            ),
            _issue_codes(foundry),
        ),
    ]
    payload = _base_diagnostic(evidence, "PDD-087")
    payload.update(
        {
            "diagnostic_status": "diagnosed",
            "verdict": "confirmed_model_readiness_not_bound_to_policy_claims",
            "acceptance_gate_status": "failed",
            "findings": findings,
            "evidence": {
                "provider_model_quality_status": provider.get("status"),
                "provider_model_quality_summary": provider.get("summary"),
                "provider_model_entries": [
                    {
                        "provider": entry.get("provider"),
                        "model_id": entry.get("model_id"),
                        "evidence_lane_kinds": entry.get("evidence_lane_kinds"),
                        "drift_action": entry.get("drift_action"),
                    }
                    for entry in _as_list(provider.get("entries"))
                    if isinstance(entry, Mapping)
                ],
                "claim_method_refs": [
                    claim.get("method_refs")
                    for claim in _as_list(grounding.get("claims"))
                    if isinstance(claim, Mapping)
                ],
                "semantic_model_dependency_refs": model_dependency_refs,
                "foundry_method_result_refs": foundry.get("summary", {}).get(
                    "method_result_refs"
                )
                if isinstance(foundry.get("summary"), Mapping)
                else None,
            },
            "recommended_gate": (
                "Require model-readiness, drift, incident, calibration, registry promotion, "
                "and stationarity refs for every claim that consumes model outputs."
            ),
            "backlog_summary": (
                "Wave 33 has a passing provider-model quality ledger for one simulated LLM "
                "observation, but final claims do not bind to model-output dependency, DDM "
                "readiness, calibration, incident, or stationarity refs. PDD-087 failed."
            ),
        }
    )
    return payload


def _diagnose_pdd_088(evidence: Mapping[str, Any]) -> dict[str, Any]:
    coverage = _wave(evidence, "readiness")
    claim_argument = _wave(evidence, "claim_argument")
    policy_case = _quality(evidence, "policy_design_case")
    grounding = _quality(evidence, "policy_grounding_matrix")
    berl_refs = _collect_refs_containing(
        {
            "claim_argument": claim_argument,
            "policy_design_case": policy_case,
            "policy_grounding_matrix": grounding,
        },
        ("berl", "explanation_bundle", "infidelity"),
    )
    findings: list[dict[str, Any]] = []
    acceptance = "not_triggered_no_explanation_support_detected"
    verdict = "no_berl_explanation_support_usage_detected"
    if berl_refs:
        findings.append(
            _finding(
                "berl_explanation_refs_need_claim_family_boundary_review",
                "warning",
                (
                    "BERL/explanation-like refs were present and should be checked "
                    "for claim-family authorization."
                ),
                berl_refs,
            )
        )
        acceptance = "blocked"
        verdict = "explanation_refs_present_require_reliability_review"
    payload = _base_diagnostic(evidence, "PDD-088")
    payload.update(
        {
            "diagnostic_status": "diagnosed",
            "verdict": verdict,
            "acceptance_gate_status": acceptance,
            "findings": findings,
            "evidence": {
                "berl_or_explanation_refs_detected": berl_refs,
                "claim_argument_keys": sorted(str(key) for key in claim_argument),
                "policy_design_case_claim_argument_surfaces": {
                    "claim_argument_evidence_case_present": bool(
                        policy_case.get("claim_argument_evidence_case")
                    ),
                    "claim_argument_mapping_present": bool(
                        policy_case.get("claim_argument_mapping")
                    ),
                    "claim_argument_validation_present": bool(
                        policy_case.get("claim_argument_validation")
                    ),
                },
                "coverage_berl_metric": _find_metric(
                    coverage,
                    "berl_required_reliability_pct",
                ),
            },
            "recommended_gate": (
                "When explanation artifacts are introduced into claim support, require "
                "an explanation-to-claim ledger with BERL validation, infidelity bounds, "
                "claim-family authorization, and display-policy limits. If no explanation "
                "is used, emit an explicit no-explanation-support boundary."
            ),
            "backlog_summary": (
                "Wave 33 does not show BERL or explanation bundles being used as causal, "
                "legal, budget, distributional, or implementation support for final claims. "
                "No active PDD-088 violation was detected, though future runs should emit an "
                "explicit no-explanation-support boundary."
            ),
        }
    )
    return payload


def _quality(evidence: Mapping[str, Any], name: str) -> dict[str, Any]:
    quality = _expect_mapping(evidence.get("quality_files"), "quality_files")
    payload = quality.get(name)
    if payload is None:
        return {}
    return _expect_mapping(payload, f"quality_files.{name}")


def _wave(evidence: Mapping[str, Any], name: str) -> dict[str, Any]:
    wave_files = _expect_mapping(evidence.get("wave_files"), "wave_files")
    return _expect_mapping(wave_files.get(name), f"wave_files.{name}")


def _finding(
    code: str,
    severity: str,
    summary: str,
    evidence: object,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "summary": summary,
        "evidence": evidence,
    }


def _blocking_codes(scorecard: Mapping[str, Any]) -> list[str]:
    codes = []
    for failure in _as_list(scorecard.get("blocking_quality_failures")):
        if isinstance(failure, Mapping) and failure.get("code"):
            codes.append(str(failure["code"]))
    return sorted(set(codes))


def _aggregate_acceptance_status(diagnostics: Sequence[Mapping[str, Any]]) -> str:
    statuses = [str(item.get("acceptance_gate_status") or "") for item in diagnostics]
    if any(status in {"failed", "blocked"} for status in statuses):
        return "failed"
    if statuses and all(status.startswith("not_triggered") for status in statuses):
        return "not_triggered"
    return "passed"


def _issue_codes(payload: Mapping[str, Any]) -> list[str]:
    codes = []
    for issue in _as_list(payload.get("issues")):
        if isinstance(issue, Mapping) and issue.get("code"):
            codes.append(str(issue["code"]))
    return sorted(set(codes))


def _find_metric(payload: Mapping[str, Any], metric_id: str) -> dict[str, Any] | None:
    metrics = payload.get("metrics")
    if isinstance(metrics, Mapping):
        metric = metrics.get(metric_id)
        if isinstance(metric, Mapping):
            return dict(metric)
    return _find_metric_recursive(payload, metric_id)


def _find_metric_recursive(value: object, metric_id: str) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        if value.get("metric_id") == metric_id:
            return dict(value)
        for child in value.values():
            found = _find_metric_recursive(child, metric_id)
            if found is not None:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_metric_recursive(child, metric_id)
            if found is not None:
                return found
    return None


def _collect_refs_containing(payloads: Mapping[str, Any], needles: Sequence[str]) -> list[str]:
    refs: list[str] = []

    def visit(value: object, path: str) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                visit(child, f"{path}.{key}" if path else str(key))
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
            return
        if isinstance(value, str) and any(needle in value.casefold() for needle in needles):
            refs.append(f"{path}={value}")

    visit(payloads, "")
    return sorted(set(refs))


def _as_list(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _expect_mapping(
    value: object,
    name: str,
    *,
    required: bool = True,
) -> dict[str, Any]:
    if value is None and not required:
        return {}
    if not isinstance(value, Mapping):
        raise Phase34InputError(f"{name} must be a JSON object.")
    return dict(value)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise Phase34InputError(f"Required evidence file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise Phase34InputError(f"Evidence file is invalid JSON: {path}: {exc}") from exc
    return _expect_mapping(payload, str(path))


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _load_json(path)


def _resolve(repo_root: Path, path: Path, *, must_exist: bool = True) -> Path:
    candidate = path if path.is_absolute() else repo_root / path
    candidate = candidate.resolve()
    if must_exist and not candidate.exists():
        raise Phase34InputError(f"Path not found: {candidate}")
    return candidate


def _rel(base: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path.resolve())


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_string(cell) for cell in row) + " |")
    return "\n".join(lines)


def _code(value: object) -> str:
    return f"`{_string(value)}`"


def _string(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).replace("\n", " ")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave33-dir", type=Path, default=DEFAULT_WAVE33_DIR)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the Phase 34.3 index payload to stdout.",
    )
    args = parser.parse_args(argv)

    try:
        payload = build_phase34_3_payload(
            repo_root=args.repo_root,
            wave33_dir=args.wave33_dir,
        )
        written = write_phase34_3_outputs(
            payload,
            repo_root=args.repo_root,
            output_root=args.output_root,
        )
    except Phase34InputError as exc:
        sys.stderr.write(f"{TOOL_NAME}: error: {exc}\n")
        return 2

    if args.json:
        sys.stdout.write(dump_json(payload))
    else:
        summary = payload["summary"]
        sys.stdout.write(
            f"{TOOL_NAME}: {payload['status']} "
            f"pdds={summary['pdd_count']} "
            f"blocking_or_failed={summary['blocking_or_failed_count']} "
            f"not_triggered={summary['not_triggered_count']} "
            f"written={len(written)}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
