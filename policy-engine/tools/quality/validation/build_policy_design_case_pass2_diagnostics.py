#!/usr/bin/env python3
"""Build Policy Design Case Pass 2 diagnostics for Phase 34."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.metamorphic_controls import (  # noqa: E402
    PHASE56_CROSS_DOMAIN_SCENARIO_IDS,
    build_cross_domain_control_report,
    build_metamorphic_prompt_report,
    build_negative_control_report,
    build_scenario_semantic_binding_report,
)
from tools.ops_runners.runtime.quality_scenarios import (  # noqa: E402
    load_quality_scenario_contract,
)

SCHEMA_VERSION_PHASE34_1 = "policyos.policy_design_case.pass2.phase34_1_diagnostics.v1"
SCHEMA_VERSION_PHASE34_2 = "policyos.policy_design_case.pass2.phase34_2_diagnostics.v1"
SCHEMA_VERSION = SCHEMA_VERSION_PHASE34_1
TOOL_NAME = "quality.validation.build-policy-design-case-pass2-diagnostics"
PHASE34_1 = "34.1"
PHASE34_2 = "34.2"
PHASE = PHASE34_1
WAVE = "34"
DEFAULT_WAVE33_DIR = Path("_build/policy-design-case/rebaseline/wave-33")
DEFAULT_OUTPUT_DIR = Path("_build/diagnostics")
DEFAULT_FRAGMENT_DIR = Path("_build/diagnostics/pass2/backlog_fragments")

REQUIRED_WAVE33_ARTIFACTS: tuple[str, ...] = (
    "real_domain_baseline.json",
    "research_real_domain_matrix.json",
    "policy_design_case_sample.json",
    "quality_scorecard.json",
    "readiness.json",
    "production_data_evidence.json",
    "claim_argument.json",
    "policy_grounding_matrix.json",
)

PDD_TITLES = {
    "PDD-037": "Run Cross-Domain Generality Diagnostic Matrix",
    "PDD-055": "Build Metamorphic Policy Diagnostic Suite",
    "PDD-056": "Audit Multilingual And Transliteration End-To-End Equivalence",
    "PDD-038": "Negative/Adversarial Fail-Closed Diagnostics",
    "PDD-064": "Adversarial Cache/Index/Snapshot Poisoning Diagnostics",
    "PDD-065": "Cross-Component Error Semantics Contract",
    "PDD-098": "Strategic Behavior/Gaming/Fraud/Arbitrage Binding",
}

PDD_QUESTIONS = {
    "PDD-037": "Do Wave 33 real-case bindings generalize across materially different policy domains?",
    "PDD-055": "Do metamorphic variants preserve materially equivalent policy semantics and fail when critical evidence is removed?",
    "PDD-056": "Do multilingual and transliterated requests bind to the same concepts, norms, data, methods, and claims?",
    "PDD-038": "Do adversarial or negative scenarios fail closed without unsupported final policy claims?",
    "PDD-064": "Can cache, index, and snapshot poisoning be detected without trusting stale or unauthenticated source state?",
    "PDD-065": "Do cross-component errors preserve root-cause semantics from producer to operator surfaces?",
    "PDD-098": "Are gaming, fraud, arbitrage, and strategic behavior assumptions bound to evidence and monitoring?",
}

PDD_ARTIFACTS_PHASE34_1 = {
    "PDD-037": "cross_domain_generality_diagnostic_matrix",
    "PDD-055": "metamorphic_policy_diagnostic_suite",
    "PDD-056": "multilingual_transliteration_equivalence_audit",
}

PDD_ARTIFACTS_PHASE34_2 = {
    "PDD-038": "adversarial_fail_closed_diagnostics",
    "PDD-064": "cache_index_snapshot_poisoning_audit",
    "PDD-065": "cross_component_error_semantics_audit",
    "PDD-098": "strategic_behavior_binding_audit",
}

PDD_ARTIFACTS = PDD_ARTIFACTS_PHASE34_1
PDD_ARTIFACTS_BY_ID = {
    **PDD_ARTIFACTS_PHASE34_1,
    **PDD_ARTIFACTS_PHASE34_2,
}

PDD038_ADVERSARIAL_SCENARIOS: tuple[str, ...] = (
    "no_applicable_jurisdiction",
    "legal_conflict",
    "irrelevant_data",
    "insufficient_causal_identification",
    "hidden_token_leakage_attempt",
    "prompt_injected_source",
    "illegal_policy_request",
)

PHASE34_2_BUNDLE_ARTIFACTS = {
    "security_assurance_report": Path("quality_evidence/security_assurance_report.json"),
    "prompt_tool_ledger": Path("quality_evidence/prompt_tool_ledger.json"),
    "conflict_check": Path("quality_evidence/conflict_check.json"),
    "fabric_retrieval_trace": Path("quality_evidence/fabric_retrieval_trace.json"),
    "production_data_quality": Path("quality_evidence/production_data_quality.json"),
    "foundry_method_report": Path("quality_evidence/foundry_method_report.json"),
    "decision_artifact_quality": Path("quality_evidence/decision_artifact_quality.json"),
    "timeline": Path("timeline.json"),
}


def build_phase34_1_payload(
    *,
    repo_root: Path = REPO_ROOT,
    wave33_dir: Path = DEFAULT_WAVE33_DIR,
    scenario_ids: Sequence[str] = PHASE56_CROSS_DOMAIN_SCENARIO_IDS,
) -> dict[str, Any]:
    """Build Phase 34.1 diagnostic reports from Wave 33 evidence."""

    repo_root = repo_root.resolve()
    wave33_dir = _resolve_path(repo_root, wave33_dir)
    loaded, input_artifacts, input_issues = _load_wave33_artifacts(
        repo_root=repo_root,
        wave33_dir=wave33_dir,
    )
    observed = _observed_wave33_case(loaded)
    contracts = _load_contracts(scenario_ids=scenario_ids)

    pdd37 = _build_pdd037_report(
        contracts=contracts,
        observed=observed,
        input_issues=input_issues,
        wave33_dir=wave33_dir,
        repo_root=repo_root,
    )
    pdd55 = _build_pdd055_report(
        contracts=contracts,
        observed=observed,
        input_issues=input_issues,
        wave33_dir=wave33_dir,
        repo_root=repo_root,
    )
    pdd56 = _build_pdd056_report(
        contracts=contracts,
        observed=observed,
        input_issues=input_issues,
        wave33_dir=wave33_dir,
        repo_root=repo_root,
    )
    pdds = {report["pdd_id"]: report for report in (pdd37, pdd55, pdd56)}
    total_findings = sum(len(report["findings"]) for report in pdds.values())
    blocked = bool(input_issues)
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": WAVE,
        "phase": PHASE,
        "status": "blocked" if blocked else "diagnosed",
        "runtime_acceptance_status": (
            "not_evaluated" if blocked else _aggregate_acceptance(pdds)
        ),
        "input_evidence": {
            "wave33_dir": _rel(wave33_dir, repo_root),
            "artifacts": input_artifacts,
            "issues": input_issues,
        },
        "observed_wave33_case": observed,
        "summary": {
            "pdd_count": len(pdds),
            "finding_count": total_findings,
            "input_issue_count": len(input_issues),
            "required_cross_domain_scenario_count": len(tuple(scenario_ids)),
            "observed_runtime_scenario_ids": observed["observed_scenario_ids"],
            "contract_control_status": _contract_control_status(pdds),
        },
        "pdds": pdds,
    }


def write_phase34_1_reports(
    *,
    repo_root: Path = REPO_ROOT,
    wave33_dir: Path = DEFAULT_WAVE33_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    fragment_dir: Path = DEFAULT_FRAGMENT_DIR,
) -> dict[str, Path]:
    """Write detailed PDD reports and backlog fragments."""

    repo_root = repo_root.resolve()
    output_dir = _resolve_path(repo_root, output_dir)
    fragment_dir = _resolve_path(repo_root, fragment_dir)
    payload = build_phase34_1_payload(
        repo_root=repo_root,
        wave33_dir=wave33_dir,
    )
    written: dict[str, Path] = {}
    phase_dir = output_dir / "pass2"
    phase_payload_path = phase_dir / "phase34_1_cross_domain_metamorphic_diagnostics.json"
    phase_summary_path = phase_dir / "phase34_1_cross_domain_metamorphic_diagnostics.md"
    atomic_write_text(phase_payload_path, _dump_json(payload))
    atomic_write_text(phase_summary_path, _render_phase_summary(payload, repo_root))
    written["phase_payload"] = phase_payload_path
    written["phase_summary"] = phase_summary_path

    for pdd_id, report in payload["pdds"].items():
        slug = PDD_ARTIFACTS[pdd_id]
        pdd_dir = output_dir / pdd_id.lower()
        json_path = pdd_dir / f"{slug}.json"
        detail_path = pdd_dir / f"{slug}.md"
        summary_path = pdd_dir / "summary.md"
        fragment_path = fragment_dir / f"{pdd_id.lower()}.md"

        atomic_write_text(json_path, _dump_json(report))
        atomic_write_text(detail_path, _render_pdd_detail(report, repo_root))
        atomic_write_text(summary_path, _render_pdd_summary(report, repo_root))
        atomic_write_text(fragment_path, _render_backlog_fragment(report, repo_root))

        written[f"{pdd_id}:json"] = json_path
        written[f"{pdd_id}:detail"] = detail_path
        written[f"{pdd_id}:summary"] = summary_path
        written[f"{pdd_id}:fragment"] = fragment_path

    payload["output"] = {key: _rel(path, repo_root) for key, path in written.items()}
    atomic_write_text(phase_payload_path, _dump_json(payload))
    return written


def build_phase34_2_payload(
    *,
    repo_root: Path = REPO_ROOT,
    wave33_dir: Path = DEFAULT_WAVE33_DIR,
) -> dict[str, Any]:
    """Build Phase 34.2 adversarial and fail-closed diagnostics."""

    repo_root = repo_root.resolve()
    wave33_dir = _resolve_path(repo_root, wave33_dir)
    loaded, input_artifacts, input_issues = _load_wave33_artifacts(
        repo_root=repo_root,
        wave33_dir=wave33_dir,
        phase=PHASE34_2,
    )
    observed = _observed_wave33_case(loaded)
    bundle_artifacts, bundle_index, bundle_issues = _load_wave33_bundle_artifacts(
        repo_root=repo_root,
        observed=observed,
        phase=PHASE34_2,
    )
    all_input_issues = [*input_issues, *bundle_issues]
    pdd38 = _build_pdd038_report(
        loaded=loaded,
        observed=observed,
        bundle_artifacts=bundle_artifacts,
        input_issues=all_input_issues,
        wave33_dir=wave33_dir,
        repo_root=repo_root,
    )
    pdd64 = _build_pdd064_report(
        loaded=loaded,
        observed=observed,
        bundle_artifacts=bundle_artifacts,
        input_issues=all_input_issues,
        wave33_dir=wave33_dir,
        repo_root=repo_root,
    )
    pdd65 = _build_pdd065_report(
        loaded=loaded,
        observed=observed,
        bundle_artifacts=bundle_artifacts,
        input_issues=all_input_issues,
        wave33_dir=wave33_dir,
        repo_root=repo_root,
    )
    pdd98 = _build_pdd098_report(
        loaded=loaded,
        observed=observed,
        input_issues=all_input_issues,
        wave33_dir=wave33_dir,
        repo_root=repo_root,
    )
    pdds = {report["pdd_id"]: report for report in (pdd38, pdd64, pdd65, pdd98)}
    blocked = bool(input_issues)
    total_findings = sum(len(report["findings"]) for report in pdds.values())
    return {
        "schema_version": SCHEMA_VERSION_PHASE34_2,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": WAVE,
        "phase": PHASE34_2,
        "status": "blocked" if blocked else "diagnosed",
        "runtime_acceptance_status": (
            "not_evaluated" if blocked else _aggregate_acceptance(pdds)
        ),
        "input_evidence": {
            "wave33_dir": _rel(wave33_dir, repo_root),
            "artifacts": input_artifacts,
            "bundle_artifacts": bundle_index,
            "issues": all_input_issues,
        },
        "observed_wave33_case": observed,
        "summary": {
            "pdd_count": len(pdds),
            "finding_count": total_findings,
            "input_issue_count": len(all_input_issues),
            "required_adversarial_scenario_count": len(PDD038_ADVERSARIAL_SCENARIOS),
            "acceptance_status_by_pdd": {
                pdd_id: report["acceptance_gate_status"]
                for pdd_id, report in pdds.items()
            },
            "fail_closed_baseline": _wave33_fail_closed_summary(loaded, observed),
        },
        "pdds": pdds,
    }


def write_phase34_2_reports(
    *,
    repo_root: Path = REPO_ROOT,
    wave33_dir: Path = DEFAULT_WAVE33_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    fragment_dir: Path = DEFAULT_FRAGMENT_DIR,
) -> dict[str, Path]:
    """Write Phase 34.2 detailed PDD reports and backlog fragments."""

    repo_root = repo_root.resolve()
    output_dir = _resolve_path(repo_root, output_dir)
    fragment_dir = _resolve_path(repo_root, fragment_dir)
    payload = build_phase34_2_payload(
        repo_root=repo_root,
        wave33_dir=wave33_dir,
    )
    written: dict[str, Path] = {}
    phase_dir = output_dir / "pass2"
    phase_payload_path = phase_dir / "phase34_2_adversarial_fail_closed_diagnostics.json"
    phase_summary_path = phase_dir / "phase34_2_adversarial_fail_closed_diagnostics.md"
    atomic_write_text(phase_payload_path, _dump_json(payload))
    atomic_write_text(phase_summary_path, _render_phase_summary(payload, repo_root))
    written["phase34_2_payload"] = phase_payload_path
    written["phase34_2_summary"] = phase_summary_path

    for pdd_id, report in payload["pdds"].items():
        slug = PDD_ARTIFACTS_PHASE34_2[pdd_id]
        pdd_dir = output_dir / pdd_id.lower()
        json_path = pdd_dir / f"{slug}.json"
        detail_path = pdd_dir / f"{slug}.md"
        summary_path = pdd_dir / "summary.md"
        fragment_path = fragment_dir / f"{pdd_id.lower()}.md"

        atomic_write_text(json_path, _dump_json(report))
        atomic_write_text(detail_path, _render_pdd_detail(report, repo_root))
        atomic_write_text(summary_path, _render_pdd_summary(report, repo_root))
        atomic_write_text(fragment_path, _render_backlog_fragment(report, repo_root))

        written[f"{pdd_id}:json"] = json_path
        written[f"{pdd_id}:detail"] = detail_path
        written[f"{pdd_id}:summary"] = summary_path
        written[f"{pdd_id}:fragment"] = fragment_path

    payload["output"] = {key: _rel(path, repo_root) for key, path in written.items()}
    atomic_write_text(phase_payload_path, _dump_json(payload))
    return written


def _load_wave33_artifacts(
    *,
    repo_root: Path,
    wave33_dir: Path,
    phase: str = PHASE,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    loaded: dict[str, Any] = {}
    artifacts: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for filename in REQUIRED_WAVE33_ARTIFACTS:
        path = wave33_dir / filename
        exists = path.exists()
        artifacts.append(
            {
                "name": filename,
                "path": _rel(path, repo_root),
                "status": "present" if exists else "missing",
            }
        )
        if not exists:
            issues.append(
                _finding(
                    pdd_id=f"PHASE-{phase}",
                    code="pass2_wave33_required_artifact_missing",
                    severity="PDC-CRITICAL",
                    title="Wave 33 required evidence artifact is missing",
                    message=f"Phase {phase} cannot evaluate Wave 33 evidence without {filename}.",
                    owner="team-runtime-quality",
                    missing_input=_rel(path, repo_root),
                    upstream_cause=(
                        "Wave 33 rebaseline evidence is incomplete or was not "
                        "generated."
                    ),
                    downstream_impact=(
                        "Pass 2 behavioral diagnostics cannot distinguish real runtime "
                        "evidence from hypothetical scenario contracts."
                    ),
                    refs=[_rel(path, repo_root)],
                    phase=phase,
                )
            )
            loaded[filename] = {}
            continue
        try:
            loaded[filename] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(
                _finding(
                    pdd_id=f"PHASE-{phase}",
                    code="pass2_wave33_artifact_invalid_json",
                    severity="PDC-CRITICAL",
                    title="Wave 33 evidence artifact is invalid JSON",
                    message=f"{filename} could not be parsed: {exc.msg}.",
                    owner="team-runtime-quality",
                    missing_input=_rel(path, repo_root),
                    upstream_cause="Wave 33 evidence was written in an unreadable form.",
                    downstream_impact="Pass 2 diagnostics cannot consume this artifact.",
                    refs=[_rel(path, repo_root)],
                    phase=phase,
                )
            )
            loaded[filename] = {}
    return loaded, artifacts, issues


def _load_wave33_bundle_artifacts(
    *,
    repo_root: Path,
    observed: Mapping[str, Any],
    phase: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    bundle_rel = observed.get("bundle_path")
    artifacts: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    loaded: dict[str, Any] = {}
    if not bundle_rel:
        issues.append(
            _finding(
                pdd_id=f"PHASE-{phase}",
                code="pass2_wave33_runtime_bundle_path_missing",
                severity="PDC-CRITICAL",
                title="Wave 33 runtime bundle path is missing",
                message=(
                    "Phase 34.2 cannot inspect runtime adversarial evidence "
                    "without the Wave 33 bundle path."
                ),
                owner="team-runtime-quality",
                missing_input="real_domain_baseline.research_profile_case.bundle_path",
                upstream_cause="Wave 33 real-domain baseline did not record its evidence bundle.",
                downstream_impact=(
                    "Bundle-level fail-closed diagnostics cannot inspect security, "
                    "cache, prompt, or source traces."
                ),
                refs=[
                    "_build/policy-design-case/rebaseline/wave-33/real_domain_baseline.json"
                ],
                phase=phase,
            )
        )
        return loaded, artifacts, issues

    bundle_path = _resolve_path(repo_root, Path(str(bundle_rel)))
    for name, relative_path in PHASE34_2_BUNDLE_ARTIFACTS.items():
        path = bundle_path / relative_path
        exists = path.exists()
        artifacts.append(
            {
                "name": name,
                "path": _rel(path, repo_root),
                "status": "present" if exists else "missing",
            }
        )
        if not exists:
            loaded[name] = {}
            continue
        try:
            loaded[name] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(
                _finding(
                    pdd_id=f"PHASE-{phase}",
                    code="pass2_wave33_runtime_bundle_artifact_invalid_json",
                    severity="PDC-HIGH",
                    title="Wave 33 runtime bundle artifact is invalid JSON",
                    message=f"{relative_path.as_posix()} could not be parsed: {exc.msg}.",
                    owner="team-runtime-quality",
                    missing_input=_rel(path, repo_root),
                    upstream_cause="Runtime evidence was written in an unreadable form.",
                    downstream_impact="Phase 34.2 cannot inspect this runtime evidence surface.",
                    refs=[_rel(path, repo_root)],
                    phase=phase,
                )
            )
            loaded[name] = {}
    return loaded, artifacts, issues


def _observed_wave33_case(loaded: Mapping[str, Any]) -> dict[str, Any]:
    real = _mapping(loaded.get("real_domain_baseline.json"))
    matrix = _mapping(loaded.get("research_real_domain_matrix.json"))
    case = _mapping(loaded.get("policy_design_case_sample.json"))
    scorecard = _mapping(loaded.get("quality_scorecard.json"))
    readiness = _mapping(loaded.get("readiness.json"))
    claim_argument = _mapping(loaded.get("claim_argument.json"))
    production_data = _mapping(loaded.get("production_data_evidence.json"))

    research_case = _mapping(real.get("research_profile_case"))
    observed_scenario_ids = _extract_quality_scenario_ids(matrix)
    return {
        "wave": real.get("wave"),
        "status": real.get("status"),
        "exit_fence": real.get("exit_fence") or {},
        "case_id": case.get("case_id") or research_case.get("case_id"),
        "run_id": case.get("run_id") or research_case.get("run_id"),
        "job_id": case.get("job_id") or research_case.get("job_id"),
        "bundle_path": research_case.get("bundle_path"),
        "authority_profile": case.get("authority_profile")
        or research_case.get("authority_profile")
        or {},
        "observed_scenario_ids": observed_scenario_ids,
        "intent": _intent_summary(_mapping(case.get("intent_envelope"))),
        "scorecard": {
            "quality_status": scorecard.get("quality_status"),
            "approval_state": scorecard.get("approval_state"),
            "blocking_failures": _scorecard_blocking_failures(scorecard),
        },
        "readiness": {
            "status": readiness.get("status"),
            "passes_required": readiness.get("passes_required"),
            "minimum_closeout_gate_failures": readiness.get(
                "minimum_closeout_gate_failures"
            )
            or [],
        },
        "stage_evidence": research_case.get("stage_evidence") or {},
        "claim_argument": {
            "status": _mapping(claim_argument.get("claim")).get("status"),
            "subclaim_count": len(claim_argument.get("subclaims") or []),
        },
        "production_data": {
            "materialization_ref_count": len(
                _mapping(production_data.get("materialization_refs"))
            ),
            "bundle_roles": sorted(
                _mapping(_mapping(production_data.get("context")).get("bundles")).keys()
            ),
        },
    }


def _build_pdd037_report(
    *,
    contracts: Mapping[str, Mapping[str, Any]],
    observed: Mapping[str, Any],
    input_issues: Sequence[Mapping[str, Any]],
    wave33_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    observed_scenarios = set(_strings(observed.get("observed_scenario_ids")))
    scenarios: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = list(input_issues)
    for scenario_id, contract in contracts.items():
        expected = _mapping(contract.get("expected_evidence_contract"))
        runtime_present = scenario_id in observed_scenarios
        contract_controls = build_cross_domain_control_report(dict(contract))
        semantic_binding = build_scenario_semantic_binding_report(dict(contract))
        scenario_row = {
            "scenario_id": scenario_id,
            "title": contract.get("title"),
            "runtime_evidence_status": "present" if runtime_present else "missing",
            "domain_hint": contract.get("domain_hint"),
            "context": contract.get("context") or {},
            "expected_contract": {
                "normative_fact_classes": expected.get("normative_fact_classes") or [],
                "admissible_data_source_families": expected.get(
                    "admissible_data_source_families"
                )
                or [],
                "foundry_method_expectations": expected.get(
                    "foundry_method_expectations"
                )
                or [],
                "conflict_checks": expected.get("conflict_checks") or [],
            },
            "contract_control_report": contract_controls,
            "semantic_binding_report": semantic_binding,
        }
        if not runtime_present:
            findings.append(
                _finding(
                    pdd_id="PDD-037",
                    code="pass2_wave33_cross_domain_bundle_missing",
                    severity="PDC-CRITICAL",
                    title="Wave 33 lacks required cross-domain runtime bundle",
                    message=(
                        "No Wave 33 runtime bundle was observed for the required "
                        f"cross-domain scenario {scenario_id}."
                    ),
                    owner="team-runtime-quality",
                    missing_input=(
                        "runtime-owned research-profile bundle for "
                        f"{scenario_id}"
                    ),
                    upstream_cause=(
                        "Wave 33 emitted a single research-profile baseline, not "
                        "the five Pass 2 cross-domain scenarios."
                    ),
                    downstream_impact=(
                        "PolicyOS cannot yet prove Lex/Fabric/Foundry/Scientist "
                        "bindings adapt across materially different policy domains."
                    ),
                    scenario_id=scenario_id,
                    refs=[_rel(wave33_dir, repo_root)],
                    next_command=(
                        "Run the research-profile canary lane for this scenario, "
                        "then rebuild Phase 34.1 diagnostics."
                    ),
                )
            )
        scenarios.append(scenario_row)
    missing = [
        row for row in scenarios if row["runtime_evidence_status"] != "present"
    ]
    acceptance = "blocked" if input_issues else ("failed" if missing else "satisfied")
    return _pdd_report(
        pdd_id="PDD-037",
        acceptance_gate_status=acceptance,
        findings=findings,
        summary={
            "required_domain_count": len(scenarios),
            "runtime_domain_count": len(scenarios) - len(missing),
            "missing_runtime_domain_count": len(missing),
            "contract_control_pass_count": sum(
                1
                for row in scenarios
                if row["contract_control_report"].get("status") == "pass"
            ),
            "semantic_binding_pass_count": sum(
                1
                for row in scenarios
                if row["semantic_binding_report"].get("status") == "pass"
            ),
        },
        details={"scenarios": scenarios},
        observed=observed,
    )


def _build_pdd055_report(
    *,
    contracts: Mapping[str, Mapping[str, Any]],
    observed: Mapping[str, Any],
    input_issues: Sequence[Mapping[str, Any]],
    wave33_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    observed_scenarios = set(_strings(observed.get("observed_scenario_ids")))
    scenarios: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = list(input_issues)
    total_variants = 0
    present_variants = 0
    missing_data_removal = 0
    for scenario_id, contract in contracts.items():
        metamorphic = build_metamorphic_prompt_report(dict(contract))
        negative = build_negative_control_report(dict(contract))
        runtime_variants: list[dict[str, Any]] = []
        for variant in metamorphic.get("variants") or []:
            if not isinstance(variant, dict):
                continue
            variant_id = str(variant.get("variant_id") or "variant")
            present = scenario_id in observed_scenarios and variant_id == "en_direct"
            total_variants += 1
            present_variants += 1 if present else 0
            runtime_variants.append(
                {
                    "variant_id": variant_id,
                    "locale": variant.get("locale"),
                    "expected": variant.get("expected"),
                    "contract_status": variant.get("status"),
                    "runtime_evidence_status": (
                        "present_baseline" if present else "missing"
                    ),
                }
            )
        missing_count = sum(
            1
            for variant in runtime_variants
            if variant["runtime_evidence_status"] == "missing"
        )
        if missing_count:
            findings.append(
                _finding(
                    pdd_id="PDD-055",
                    code="pass2_wave33_metamorphic_variant_bundle_missing",
                    severity="PDC-CRITICAL",
                    title="Wave 33 lacks paired metamorphic runtime variants",
                    message=(
                        f"{scenario_id} has {missing_count} missing runtime "
                        "variant bundles for paraphrase, language, jurisdiction, "
                        "time, data-family, or method perturbations."
                    ),
                    owner="team-runtime-quality",
                    missing_input="paired runtime bundles for metamorphic variants",
                    upstream_cause=(
                        "Wave 33 generated only the baseline research-profile "
                        "case evidence."
                    ),
                    downstream_impact=(
                        "A serious closeout would still be based on a single "
                        "happy-path scenario."
                    ),
                    scenario_id=scenario_id,
                    refs=[_rel(wave33_dir, repo_root)],
                )
            )
        irrelevant = _control_by_id(negative, "irrelevant_data")
        data_removal_present = False
        if not data_removal_present:
            missing_data_removal += 1
            findings.append(
                _finding(
                    pdd_id="PDD-055",
                    code="pass2_wave33_metamorphic_data_removal_probe_missing",
                    severity="PDC-CRITICAL",
                    title="Wave 33 lacks irrelevant-data/data-removal runtime probe",
                    message=(
                        "The scenario contract declares an irrelevant-data control, "
                        "but Wave 33 has no paired runtime probe for it."
                    ),
                    owner="team-runtime-quality",
                    missing_input="runtime irrelevant-data or data-removal perturbation",
                    upstream_cause="Wave 33 did not execute perturbation lanes.",
                    downstream_impact=(
                        "The diagnostics cannot prove that removing relevant data "
                        "or adding irrelevant evidence changes readiness correctly."
                    ),
                    scenario_id=scenario_id,
                    refs=[_rel(wave33_dir, repo_root)],
                )
            )
        scenarios.append(
            {
                "scenario_id": scenario_id,
                "contract_metamorphic_report": metamorphic,
                "contract_negative_control_report": negative,
                "irrelevant_data_contract_control": irrelevant,
                "runtime_variants": runtime_variants,
                "missing_runtime_variant_count": missing_count,
                "data_removal_runtime_status": (
                    "present" if data_removal_present else "missing"
                ),
            }
        )
    missing_variants = total_variants - present_variants
    acceptance = (
        "blocked"
        if input_issues
        else "failed"
        if missing_variants or missing_data_removal
        else "satisfied"
    )
    return _pdd_report(
        pdd_id="PDD-055",
        acceptance_gate_status=acceptance,
        findings=findings,
        summary={
            "scenario_count": len(scenarios),
            "contract_metamorphic_pass_count": sum(
                1
                for row in scenarios
                if row["contract_metamorphic_report"].get("status") == "pass"
            ),
            "total_variant_count": total_variants,
            "runtime_variant_count": present_variants,
            "missing_runtime_variant_count": missing_variants,
            "missing_data_removal_probe_count": missing_data_removal,
        },
        details={"scenarios": scenarios},
        observed=observed,
    )


def _build_pdd056_report(
    *,
    contracts: Mapping[str, Mapping[str, Any]],
    observed: Mapping[str, Any],
    input_issues: Sequence[Mapping[str, Any]],
    wave33_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    observed_scenarios = set(_strings(observed.get("observed_scenario_ids")))
    scenarios: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = list(input_issues)
    runtime_pair_count = 0
    transliteration_variant_count = 0
    mixed_language_variant_count = 0

    for scenario_id, contract in contracts.items():
        metamorphic = build_metamorphic_prompt_report(dict(contract))
        variants = [
            variant
            for variant in metamorphic.get("variants") or []
            if isinstance(variant, dict)
        ]
        en_equivalent = [
            variant
            for variant in variants
            if variant.get("locale") == "en" and variant.get("expected") == "pass"
        ]
        uk_equivalent = [
            variant
            for variant in variants
            if variant.get("locale") == "uk" and variant.get("expected") == "pass"
        ]
        transliteration = [
            variant
            for variant in variants
            if "translit" in str(variant.get("variant_id") or "").casefold()
            or "latn" in str(variant.get("locale") or "").casefold()
        ]
        mixed_language = [
            variant
            for variant in variants
            if "mixed" in str(variant.get("variant_id") or "").casefold()
        ]
        transliteration_variant_count += len(transliteration)
        mixed_language_variant_count += len(mixed_language)
        runtime_pair_present = scenario_id in observed_scenarios and bool(
            en_equivalent and uk_equivalent
        )
        runtime_pair_count += 1 if runtime_pair_present else 0

        if not runtime_pair_present:
            findings.append(
                _finding(
                    pdd_id="PDD-056",
                    code="pass2_wave33_multilingual_runtime_pair_missing",
                    severity="PDC-HIGH",
                    title="Wave 33 lacks paired English/Ukrainian runtime bundles",
                    message=(
                        "No paired Wave 33 runtime evidence proves that English "
                        f"and Ukrainian requests bind equivalently for {scenario_id}."
                    ),
                    owner="team-policy-semantics",
                    missing_input="paired English and Ukrainian runtime bundles",
                    upstream_cause="Wave 33 executed only one baseline prompt lane.",
                    downstream_impact=(
                        "Multilingual production support remains unproved for "
                        "concept, norm, dataset, method, grounding, and claim bindings."
                    ),
                    scenario_id=scenario_id,
                    refs=[_rel(wave33_dir, repo_root)],
                )
            )
        if not transliteration:
            findings.append(
                _finding(
                    pdd_id="PDD-056",
                    code="pass2_transliteration_variant_contract_missing",
                    severity="PDC-HIGH",
                    title="No transliteration variant is declared for runtime probing",
                    message=(
                        f"{scenario_id} has English and Ukrainian variants, but no "
                        "transliterated Ukrainian variant."
                    ),
                    owner="team-policy-semantics",
                    missing_input="Ukrainian transliteration prompt variant",
                    upstream_cause=(
                        "The Pass 2 scenario contract does not yet encode a "
                        "transliteration pair."
                    ),
                    downstream_impact=(
                        "PDD-056 cannot prove equivalence for transliterated user requests."
                    ),
                    scenario_id=scenario_id,
                    refs=["tools/ops_runners/runtime/golden_quality_scenarios.json"],
                )
            )
        if not mixed_language:
            findings.append(
                _finding(
                    pdd_id="PDD-056",
                    code="pass2_mixed_language_variant_contract_missing",
                    severity="PDC-MEDIUM",
                    title="No mixed-language variant is declared for runtime probing",
                    message=(
                        f"{scenario_id} has no mixed Ukrainian/English prompt variant."
                    ),
                    owner="team-policy-semantics",
                    missing_input="mixed-language prompt variant",
                    upstream_cause=(
                        "The Pass 2 scenario contract covers en/uk but not mixed-language input."
                    ),
                    downstream_impact=(
                        "PDD-056 cannot detect mixed-language binding divergence."
                    ),
                    scenario_id=scenario_id,
                    refs=["tools/ops_runners/runtime/golden_quality_scenarios.json"],
                )
            )
        scenarios.append(
            {
                "scenario_id": scenario_id,
                "contract_metamorphic_report": metamorphic,
                "english_equivalent_variants": en_equivalent,
                "ukrainian_equivalent_variants": uk_equivalent,
                "transliteration_variants": transliteration,
                "mixed_language_variants": mixed_language,
                "runtime_pair_status": (
                    "present" if runtime_pair_present else "missing"
                ),
            }
        )

    findings.append(
        _finding(
            pdd_id="PDD-056",
            code="pass2_wave33_hardcoded_language_path_audit_missing",
            severity="PDC-HIGH",
            title="Wave 33 has no hardcoded-language-path runtime audit",
            message=(
                "Wave 33 evidence does not contain a runtime audit proving that "
                "language, country, or topic detection avoids hardcoded paths."
            ),
            owner="team-policy-semantics",
            missing_input="hardcoded-language-path detection report",
            upstream_cause="Phase 33 produced real-domain baseline evidence only.",
            downstream_impact=(
                "Equivalent multilingual requests may silently bind to different "
                "concepts, norms, datasets, methods, or claims."
            ),
            refs=[_rel(wave33_dir, repo_root)],
        )
    )
    acceptance = (
        "blocked"
        if input_issues
        else "failed"
        if len(scenarios) != runtime_pair_count
        or transliteration_variant_count == 0
        or mixed_language_variant_count == 0
        else "satisfied"
    )
    return _pdd_report(
        pdd_id="PDD-056",
        acceptance_gate_status=acceptance,
        findings=findings,
        summary={
            "scenario_count": len(scenarios),
            "runtime_multilingual_pair_count": runtime_pair_count,
            "missing_runtime_multilingual_pair_count": len(scenarios)
            - runtime_pair_count,
            "transliteration_variant_count": transliteration_variant_count,
            "mixed_language_variant_count": mixed_language_variant_count,
            "contract_ukrainian_variant_count": sum(
                len(row["ukrainian_equivalent_variants"]) for row in scenarios
            ),
        },
        details={"scenarios": scenarios},
        observed=observed,
    )


def _build_pdd038_report(
    *,
    loaded: Mapping[str, Any],
    observed: Mapping[str, Any],
    bundle_artifacts: Mapping[str, Any],
    input_issues: Sequence[Mapping[str, Any]],
    wave33_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    case = _mapping(loaded.get("policy_design_case_sample.json"))
    scorecard_codes = _scorecard_code_set(_mapping(loaded.get("quality_scorecard.json")))
    jurisdiction_spine = _mapping(case.get("jurisdiction_spine"))
    jurisdiction_blockers = [
        item
        for item in jurisdiction_spine.get("blockers") or []
        if isinstance(item, dict)
    ]
    conflict_check = _mapping(bundle_artifacts.get("conflict_check"))
    fabric_trace = _mapping(bundle_artifacts.get("fabric_retrieval_trace"))
    foundry_report = _mapping(bundle_artifacts.get("foundry_method_report"))
    security_report = _mapping(bundle_artifacts.get("security_assurance_report"))
    prompt_tool_ledger = _mapping(bundle_artifacts.get("prompt_tool_ledger"))
    fail_closed = _wave33_fail_closed_summary(loaded, observed)
    bundle_path = str(observed.get("bundle_path") or "")

    scenario_rows = [
        {
            "scenario": "no_applicable_jurisdiction",
            "wave_33_result": (
                "partial_related_blocker"
                if jurisdiction_blockers
                else "not_run_as_adversarial_scenario"
            ),
            "observed_blocker_code": _first_code(jurisdiction_blockers)
            or (
                "policy_design_jurisdiction_unresolved_competence_blocker"
                if "policy_design_jurisdiction_unresolved_competence_blocker"
                in scorecard_codes
                else None
            ),
            "gap": (
                "The real-domain UA lane blocked unresolved competence, but no "
                "explicit no-applicable-jurisdiction adversarial scenario id is recorded."
            ),
            "evidence_refs": [
                _rel(wave33_dir / "policy_design_case_sample.json", repo_root),
                _rel(wave33_dir / "quality_scorecard.json", repo_root),
            ],
        },
        {
            "scenario": "legal_conflict",
            "wave_33_result": "not_run_as_adversarial_scenario",
            "observed_blocker_code": None,
            "gap": (
                "Conflict-check evidence is present for the baseline, but no "
                "legal-conflict negative scenario produces a typed blocker."
            ),
            "evidence_refs": _bundle_refs(
                bundle_path,
                ["quality_evidence/conflict_check.json"],
            ),
            "baseline_conflict_status": conflict_check.get("status"),
        },
        {
            "scenario": "irrelevant_data",
            "wave_33_result": (
                "partial_related_blocker"
                if {
                    "selected_source_missing_source_rights",
                    "semantic_fabric_source_facet_incomplete",
                }
                & scorecard_codes
                else "not_run_as_adversarial_scenario"
            ),
            "observed_blocker_code": "; ".join(
                sorted(
                    {
                        code
                        for code in (
                            "selected_source_missing_source_rights",
                            "semantic_fabric_source_facet_incomplete",
                        )
                        if code in scorecard_codes
                    }
                )
            )
            or None,
            "gap": (
                "The baseline blocks incomplete source semantics, but no "
                "irrelevant-data adversarial fixture proves unrelated data is rejected."
            ),
            "evidence_refs": [
                *_bundle_refs(
                    bundle_path,
                    ["quality_evidence/fabric_retrieval_trace.json"],
                ),
                _rel(wave33_dir / "quality_scorecard.json", repo_root),
            ],
            "fabric_status": fabric_trace.get("status"),
        },
        {
            "scenario": "insufficient_causal_identification",
            "wave_33_result": (
                "blocked"
                if "method_identification_requirements_missing" in scorecard_codes
                else "not_run_as_adversarial_scenario"
            ),
            "observed_blocker_code": (
                "method_identification_requirements_missing"
                if "method_identification_requirements_missing" in scorecard_codes
                else None
            ),
            "gap": (
                "The causal-identification blocker is real, but it is not "
                "labeled as a PDD-038 adversarial scenario run."
            ),
            "evidence_refs": _bundle_refs(
                bundle_path,
                ["quality_evidence/foundry_method_report.json"],
            ),
            "foundry_status": foundry_report.get("status"),
        },
        {
            "scenario": "hidden_token_leakage_attempt",
            "wave_33_result": "not_run_as_adversarial_scenario",
            "observed_blocker_code": None,
            "gap": (
                "Security assurance passes without per-scenario hidden-token "
                "leakage attempt evidence."
            ),
            "evidence_refs": _bundle_refs(
                bundle_path,
                ["quality_evidence/security_assurance_report.json"],
            ),
            "security_status": security_report.get("status"),
        },
        {
            "scenario": "prompt_injected_source",
            "wave_33_result": "not_run_as_adversarial_scenario",
            "observed_blocker_code": None,
            "gap": (
                "Prompt/tool ledger records prompt fingerprints and parser "
                "validation, but no injected-source rejection scenario."
            ),
            "evidence_refs": _bundle_refs(
                bundle_path,
                ["quality_evidence/prompt_tool_ledger.json"],
            ),
            "prompt_tool_status": _mapping(prompt_tool_ledger.get("summary")).get(
                "status"
            ),
        },
        {
            "scenario": "illegal_policy_request",
            "wave_33_result": "not_run_as_adversarial_scenario",
            "observed_blocker_code": None,
            "gap": (
                "No illegal-policy request fixture or runtime blocker is present "
                "in Wave 33 evidence."
            ),
            "evidence_refs": [],
        },
    ]

    findings = [
        *input_issues,
        _finding(
            pdd_id="PDD-038",
            code="pass2_wave33_baseline_fails_closed",
            severity="PDC-INFO",
            title="Wave 33 baseline fails closed",
            message=(
                "The Wave 33 real-domain baseline remains non-ready while "
                "scorecard and readiness blockers are present."
            ),
            owner="team-runtime-quality",
            missing_input="none",
            upstream_cause="Wave 33 emitted typed quality and readiness blockers.",
            downstream_impact=(
                "The baseline did not publish a production-ready policy decision."
            ),
            refs=[_rel(wave33_dir, repo_root)],
            phase=PHASE34_2,
        ),
        _finding(
            pdd_id="PDD-038",
            code="pass2_pdd038_adversarial_scenario_evidence_missing",
            severity="PDC-CRITICAL",
            title="Required adversarial scenarios are not recorded",
            message=(
                "PDD-038 requires no-jurisdiction, legal-conflict, irrelevant-data, "
                "insufficient-identification, hidden-token, prompt-injection, and "
                "illegal-policy probes; Wave 33 records only baseline-adjacent blockers."
            ),
            owner="team-runtime-quality",
            missing_input="scenario-bearing PDD-038 adversarial runtime evidence",
            upstream_cause=(
                "Wave 33 ran the public golden real-domain lane, not the "
                "adversarial fail-closed matrix."
            ),
            downstream_impact=(
                "Fail-closed behavior may be incidental to ordinary evidence gaps "
                "rather than proven against adversarial inputs."
            ),
            refs=[_rel(wave33_dir, repo_root)],
            phase=PHASE34_2,
        ),
        _finding(
            pdd_id="PDD-038",
            code="pass2_pdd038_security_prompt_injection_probes_missing",
            severity="PDC-HIGH",
            title="Security and prompt-tool evidence lacks injection probes",
            message=(
                "The security and prompt/tool evidence surfaces pass or summarize "
                "normal execution without hidden-token or prompt-injected-source probes."
            ),
            owner="team-security",
            missing_input=(
                "hidden-token leakage and prompt-injected-source rejection fixtures"
            ),
            upstream_cause=(
                "Runtime assurance artifacts do not expose per-adversary "
                "scenario results."
            ),
            downstream_impact=(
                "A pass status cannot demonstrate source and hidden-token "
                "fail-closed semantics."
            ),
            refs=_bundle_refs(
                bundle_path,
                [
                    "quality_evidence/security_assurance_report.json",
                    "quality_evidence/prompt_tool_ledger.json",
                ],
            ),
            phase=PHASE34_2,
        ),
    ]
    acceptance = "blocked" if input_issues else "failed"
    return _pdd_report(
        pdd_id="PDD-038",
        acceptance_gate_status=acceptance,
        findings=findings,
        summary={
            "fail_closed_baseline_status": fail_closed["status"],
            "required_scenario_count": len(PDD038_ADVERSARIAL_SCENARIOS),
            "scenario_count": len(scenario_rows),
            "not_run_scenario_count": sum(
                1
                for row in scenario_rows
                if row["wave_33_result"] == "not_run_as_adversarial_scenario"
            ),
            "partial_related_blocker_count": sum(
                1 for row in scenario_rows if row["wave_33_result"] == "partial_related_blocker"
            ),
            "security_status": security_report.get("status"),
            "prompt_tool_status": _mapping(prompt_tool_ledger.get("summary")).get(
                "status"
            ),
        },
        details={
            "fail_closed_baseline": fail_closed,
            "scenario_matrix": scenario_rows,
        },
        observed=observed,
        phase=PHASE34_2,
        verdict="fail_closed_baseline_confirmed_but_adversarial_scenario_coverage_incomplete",
    )


def _build_pdd064_report(
    *,
    loaded: Mapping[str, Any],
    observed: Mapping[str, Any],
    bundle_artifacts: Mapping[str, Any],
    input_issues: Sequence[Mapping[str, Any]],
    wave33_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    scorecard_codes = _scorecard_code_set(
        _mapping(loaded.get("quality_scorecard.json"))
    )
    fabric_trace = _mapping(bundle_artifacts.get("fabric_retrieval_trace"))
    production_data_quality = _mapping(bundle_artifacts.get("production_data_quality"))
    timeline = _mapping(bundle_artifacts.get("timeline"))
    bundle_path = str(observed.get("bundle_path") or "")
    fingerprint_surfaces = [
        loaded,
        bundle_artifacts,
    ]
    has_fingerprint_ledger = any(
        _contains_key_fragment(
            surface,
            ("fingerprint_ledger", "index_fingerprint", "cache_fingerprint"),
        )
        for surface in fingerprint_surfaces
    )
    production_manifest_ref = _mapping(
        _mapping(production_data_quality.get("authority_envelope")).get(
            "same_input_closure"
        )
    ).get("production_data_manifest_ref")
    fabric_manifest_ref = fabric_trace.get("manifest_ref")
    cache_events = _timeline_cache_events(timeline)
    controls = [
        {
            "control": "index_cache_fingerprint_ledger",
            "status": "present" if has_fingerprint_ledger else "missing",
            "finding": (
                "No Wave 33 artifact exposes an index/cache fingerprint ledger "
                "for legal KG, dataset catalog, semantic index, academic index, "
                "benchmark, prompt cache, provider ledger, or dashboard cache."
            ),
            "evidence_refs": [],
        },
        {
            "control": "manifest_to_index_compatibility_proof",
            "status": (
                "partial_gap"
                if fabric_manifest_ref or production_manifest_ref
                else "missing"
            ),
            "finding": (
                "Manifest and same-input closure refs exist, but no index/cache "
                "compatibility proof binds cached/indexed material to those manifest refs."
            ),
            "evidence_refs": _bundle_refs(
                bundle_path,
                [
                    "quality_evidence/fabric_retrieval_trace.json",
                    "quality_evidence/production_data_quality.json",
                ],
            ),
            "manifest_refs": {
                "fabric_manifest_ref": fabric_manifest_ref,
                "production_data_manifest_ref": production_manifest_ref,
            },
        },
        {
            "control": "data_forge_snapshot_binding",
            "status": (
                "failed_closed"
                if "data_forge_snapshot_binding_missing" in scorecard_codes
                else "not_observed"
            ),
            "finding": (
                "Scorecard blocks closeout when Data Forge snapshot binding "
                "evidence is missing."
            ),
            "evidence_refs": [_rel(wave33_dir / "quality_scorecard.json", repo_root)],
        },
        {
            "control": "stale_poisoned_cache_negative_tests",
            "status": "missing",
            "finding": (
                "Cache events are visible, but no stale, poisoned, cross-context, "
                "or inconsistent-fingerprint negative test result is recorded."
            ),
            "evidence_refs": _bundle_refs(bundle_path, ["timeline.json"]),
            "cache_event_count": len(cache_events),
        },
        {
            "control": "source_facet_integrity",
            "status": (
                "failed_closed"
                if {
                    "selected_source_missing_source_rights",
                    "semantic_fabric_source_facet_incomplete",
                }
                & scorecard_codes
                else "not_observed"
            ),
            "finding": (
                "Fabric source-facet incompleteness is reflected in blocking "
                "scorecard codes."
            ),
            "evidence_refs": _bundle_refs(
                bundle_path,
                ["quality_evidence/fabric_retrieval_trace.json"],
            ),
        },
    ]
    issue_counts = _issue_code_counts(fabric_trace.get("issues") or [])
    findings = [
        *input_issues,
        _finding(
            pdd_id="PDD-064",
            code="pass2_pdd064_index_cache_fingerprint_ledger_missing",
            severity="PDC-CRITICAL",
            title="Index/cache fingerprint ledger is missing",
            message=(
                "Wave 33 does not expose the fingerprint ledger or manifest-to-index "
                "compatibility proof required by PDD-064."
            ),
            owner="team-runtime-quality",
            missing_input=(
                "cache/index fingerprint ledger and manifest-to-index "
                "compatibility proof"
            ),
            upstream_cause=(
                "Runtime evidence records manifests and cache events but not "
                "cross-surface fingerprint acceptance semantics."
            ),
            downstream_impact=(
                "Stale or cross-context indexes cannot be distinguished from "
                "valid runtime evidence."
            ),
            refs=[
                _rel(wave33_dir, repo_root),
                *_bundle_refs(bundle_path, ["timeline.json"]),
            ],
            phase=PHASE34_2,
        ),
        _finding(
            pdd_id="PDD-064",
            code="pass2_pdd064_snapshot_source_gaps_fail_closed",
            severity="PDC-CRITICAL",
            title="Snapshot and source-facet gaps fail closed",
            message=(
                "The scorecard blocks closeout on Data Forge snapshot binding and "
                "Fabric source-facet gaps."
            ),
            owner="team-data-fabric",
            missing_input="complete source facets and Data Forge snapshot binding evidence",
            upstream_cause=(
                "Selected Fabric sources lack source-rights and semantic facet "
                "bindings."
            ),
            downstream_impact=(
                "The baseline does not pass while source or snapshot binding "
                "evidence is incomplete."
            ),
            refs=[_rel(wave33_dir / "quality_scorecard.json", repo_root)],
            phase=PHASE34_2,
        ),
        _finding(
            pdd_id="PDD-064",
            code="pass2_pdd064_poisoning_negative_tests_missing",
            severity="PDC-HIGH",
            title="Stale/poisoned cache negative tests are missing",
            message=(
                "Timeline cache events are present, but there is no PDD-064 "
                "acceptance matrix proving stale or poisoned cache inputs fail closed."
            ),
            owner="team-runtime-quality",
            missing_input=(
                "stale, poisoned, cross-context, and inconsistent-fingerprint "
                "cache/index negative tests"
            ),
            upstream_cause=(
                "Wave 33 collected a baseline runtime trace instead of cache "
                "poisoning probes."
            ),
            downstream_impact=(
                "Cache hits/stores cannot be audited for cross-run, cross-tenant, "
                "or cross-jurisdiction poisoning."
            ),
            refs=_bundle_refs(bundle_path, ["timeline.json"]),
            phase=PHASE34_2,
        ),
    ]
    acceptance = "blocked" if input_issues else "failed"
    return _pdd_report(
        pdd_id="PDD-064",
        acceptance_gate_status=acceptance,
        findings=findings,
        summary={
            "control_count": len(controls),
            "missing_or_partial_control_count": sum(
                1 for control in controls if control["status"] in {"missing", "partial_gap"}
            ),
            "cache_event_count": len(cache_events),
            "fabric_issue_code_count": len(issue_counts),
            "scorecard_snapshot_source_blocker_count": len(
                {
                    code
                    for code in (
                        "data_forge_snapshot_binding_missing",
                        "selected_source_missing_source_rights",
                        "semantic_fabric_source_facet_incomplete",
                    )
                    if code in scorecard_codes
                }
            ),
        },
        details={
            "controls": controls,
            "fabric_issue_code_counts": issue_counts,
            "cache_events": cache_events[:20],
        },
        observed=observed,
        phase=PHASE34_2,
        verdict="snapshot_source_gaps_fail_closed_but_cache_poisoning_controls_not_proven",
    )


def _build_pdd065_report(
    *,
    loaded: Mapping[str, Any],
    observed: Mapping[str, Any],
    bundle_artifacts: Mapping[str, Any],
    input_issues: Sequence[Mapping[str, Any]],
    wave33_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    scorecard = _mapping(loaded.get("quality_scorecard.json"))
    readiness = _mapping(loaded.get("readiness.json"))
    claim_argument = _mapping(loaded.get("claim_argument.json"))
    bundle_path = str(observed.get("bundle_path") or "")
    scorecard_failures = _scorecard_failures(scorecard)
    claim_blockers = [
        item for item in claim_argument.get("blockers") or [] if isinstance(item, dict)
    ]
    readiness_failures = [
        item
        for item in readiness.get("minimum_closeout_gate_failures") or []
        if isinstance(item, dict)
    ]
    summary_semantics = _readiness_summary_semantics(readiness)
    taxonomy_artifact_present = _contains_key_fragment(
        [loaded, bundle_artifacts],
        ("error_taxonomy", "translation_map", "cross_component_error"),
    )
    surfaces = [
        {
            "surface": "quality_scorecard.blocking_quality_failures",
            "status": "preserves_root_cause" if scorecard_failures else "missing",
            "evidence": {
                "failure_count": len(scorecard_failures),
                "unique_codes": len(_codes_from_items(scorecard_failures)),
                "sample_codes": sorted(_codes_from_items(scorecard_failures))[:12],
            },
        },
        {
            "surface": "claim_argument.blockers",
            "status": "preserves_root_cause" if claim_blockers else "missing",
            "evidence": {
                "blocker_count": len(claim_blockers),
                "sample": claim_blockers[:5],
            },
        },
        {
            "surface": "readiness.minimum_closeout_gate_failures",
            "status": "preserves_root_cause" if readiness_failures else "missing",
            "evidence": {
                "failure_count": len(readiness_failures),
                "sample": readiness_failures[:5],
            },
        },
        {
            "surface": "readiness.summary/component_results",
            "status": summary_semantics["status"],
            "evidence": summary_semantics,
        },
        {
            "surface": "explicit_cross_component_error_taxonomy",
            "status": "present" if taxonomy_artifact_present else "missing",
            "evidence": {
                "searched_surfaces": [
                    _rel(wave33_dir / name, repo_root)
                    for name in REQUIRED_WAVE33_ARTIFACTS
                ]
                + _bundle_refs(
                    bundle_path,
                    [
                        "quality_evidence/fabric_retrieval_trace.json",
                        "quality_evidence/foundry_method_report.json",
                        "quality_evidence/security_assurance_report.json",
                        "quality_evidence/prompt_tool_ledger.json",
                        "quality_evidence/decision_artifact_quality.json",
                    ],
                ),
            },
        },
    ]
    findings = [
        *input_issues,
        _finding(
            pdd_id="PDD-065",
            code="pass2_pdd065_detailed_surfaces_preserve_root_cause",
            severity="PDC-HIGH",
            title="Detailed surfaces preserve distinct root-cause codes",
            message=(
                "Scorecard, claim argument, and readiness minimum-closeout failures "
                "retain distinct failure codes and next actions."
            ),
            owner="team-runtime-quality",
            missing_input="none",
            upstream_cause="Wave 33 detailed artifacts include typed blocker records.",
            downstream_impact="Operators can recover root causes from detailed artifacts.",
            refs=[
                _rel(wave33_dir / "quality_scorecard.json", repo_root),
                _rel(wave33_dir / "claim_argument.json", repo_root),
                _rel(wave33_dir / "readiness.json", repo_root),
            ],
            phase=PHASE34_2,
        ),
        _finding(
            pdd_id="PDD-065",
            code="pass2_pdd065_readiness_summary_collapses_failure_semantics",
            severity="PDC-HIGH",
            title="Readiness summary collapses failure semantics",
            message=(
                "The readiness payload status is fail, but summary/component views "
                "report all component checks as pass and zero summary failures."
            ),
            owner="team-runtime-quality",
            missing_input=(
                "readiness summary entries that carry root-cause failure codes "
                "and next actions"
            ),
            upstream_cause=(
                "The readiness aggregation summary is disconnected from minimum "
                "closeout gate failures."
            ),
            downstream_impact=(
                "Dashboard or operator views that read only summary fields can "
                "miss the actual failing causes."
            ),
            refs=[_rel(wave33_dir / "readiness.json", repo_root)],
            phase=PHASE34_2,
        ),
        _finding(
            pdd_id="PDD-065",
            code="pass2_pdd065_error_taxonomy_artifact_missing",
            severity="PDC-MEDIUM",
            title="Cross-component error taxonomy artifact is missing",
            message=(
                "No explicit translation contract maps no-evidence, failed-retrieval, "
                "conflict, staleness, irrelevance, schema mismatch, and lineage loss "
                "across Lex/Fabric/Foundry/Scientist/runtime/dashboard surfaces."
            ),
            owner="team-runtime-quality",
            missing_input="cross-component error taxonomy and translation map artifact",
            upstream_cause=(
                "Wave 33 emits typed errors but does not package a shared "
                "semantics contract."
            ),
            downstream_impact=(
                "Distinct failure causes are inferred from artifacts rather than "
                "governed by a shared contract."
            ),
            refs=[_rel(wave33_dir, repo_root)],
            phase=PHASE34_2,
        ),
    ]
    acceptance = "blocked" if input_issues else "failed"
    return _pdd_report(
        pdd_id="PDD-065",
        acceptance_gate_status=acceptance,
        findings=findings,
        summary={
            "surface_count": len(surfaces),
            "root_cause_preserving_surface_count": sum(
                1
                for surface in surfaces
                if surface["status"] == "preserves_root_cause"
            ),
            "collapsed_summary_surface_count": sum(
                1
                for surface in surfaces
                if surface["status"] == "collapses_or_hides_root_cause_in_summary"
            ),
            "taxonomy_artifact_present": taxonomy_artifact_present,
            "readiness_status": readiness.get("status"),
        },
        details={"surfaces": surfaces},
        observed=observed,
        phase=PHASE34_2,
        verdict=(
            "scorecard_and_claim_argument_preserve_codes_but_"
            "readiness_summary_collapses_failure_semantics"
        ),
    )


def _build_pdd098_report(
    *,
    loaded: Mapping[str, Any],
    observed: Mapping[str, Any],
    input_issues: Sequence[Mapping[str, Any]],
    wave33_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    grounding = _mapping(loaded.get("policy_grounding_matrix.json"))
    claim = _first_claim(grounding)
    fail_closed = _wave33_fail_closed_summary(loaded, observed)
    strategic_ledger_present = _contains_key_fragment(
        loaded,
        (
            "strategic_behavior_ledger",
            "gaming_risk",
            "fraud_risk",
            "arbitrage_risk",
        ),
    )
    strategic_terms = _strategic_surface_terms(claim)
    requirements = [
        {
            "required_surface": "strategic_behavior_ledger",
            "status": "present" if strategic_ledger_present else "missing",
            "finding": "No strategic behavior ledger is present in Wave 33 evidence.",
            "evidence_refs": [],
        },
        {
            "required_surface": (
                "actor_incentive_manipulable_threshold_enforcement_mitigation_refs"
            ),
            "status": "present" if strategic_terms else "missing_or_generic",
            "finding": (
                "The claim mentions implementation risks and monitoring, but does "
                "not bind actors, incentives, manipulable thresholds, enforcement, "
                "fraud controls, or mitigation refs."
            ),
            "evidence_refs": [
                _rel(wave33_dir / "policy_grounding_matrix.json", repo_root)
            ],
            "matched_terms": strategic_terms,
        },
        {
            "required_surface": "mechanism_to_strategic_evidence_binding",
            "status": "missing",
            "finding": (
                "Foundry and claim evidence are not connected to strategic behavior, "
                "gaming, fraud, arbitrage, or misreporting analyses."
            ),
            "evidence_refs": [],
        },
        {
            "required_surface": "adversarial_gaming_fraud_arbitrage_scenarios",
            "status": "missing",
            "finding": (
                "No adversarial strategic behavior scenario output is recorded "
                "for the wartime credit-support mechanism."
            ),
            "evidence_refs": [],
        },
    ]
    findings = [
        *input_issues,
        _finding(
            pdd_id="PDD-098",
            code="pass2_pdd098_strategic_behavior_ledger_missing",
            severity="PDC-CRITICAL",
            title="Strategic behavior ledger is missing",
            message=(
                "Wave 33 has no strategic behavior ledger or mechanism-bound "
                "gaming/fraud/arbitrage scenario evidence."
            ),
            owner="team-policy-semantics",
            missing_input=(
                "strategic behavior ledger with actor, incentive, threshold, "
                "enforcement, mitigation, and adversarial scenario refs"
            ),
            upstream_cause=(
                "The real-domain baseline grounds claims in generic monitoring "
                "text rather than strategic-risk evidence."
            ),
            downstream_impact=(
                "A wartime credit-support recommendation could miss predictable "
                "misreporting, threshold manipulation, displacement, or arbitrage risks."
            ),
            refs=[_rel(wave33_dir / "policy_grounding_matrix.json", repo_root)],
            phase=PHASE34_2,
        ),
        _finding(
            pdd_id="PDD-098",
            code="pass2_pdd098_monitoring_text_generic_not_mechanism_bound",
            severity="PDC-HIGH",
            title="Monitoring text is generic",
            message=(
                "Implementation-risk and monitoring text does not bind actors, "
                "incentives, enforcement surfaces, or mitigation references."
            ),
            owner="team-policy-semantics",
            missing_input="mechanism-bound strategic behavior refs in claim grounding",
            upstream_cause="The claim grounding matrix records generic monitoring language.",
            downstream_impact=(
                "Generic monitoring cannot prove PDD-098 strategic-risk coverage."
            ),
            refs=[_rel(wave33_dir / "policy_grounding_matrix.json", repo_root)],
            phase=PHASE34_2,
        ),
        _finding(
            pdd_id="PDD-098",
            code="pass2_pdd098_closeout_failure_indirect_not_strategic_gate",
            severity="PDC-MEDIUM",
            title="Closeout is blocked indirectly, not by a strategic-risk gate",
            message=(
                "The current lane is not production-ready because scorecard and "
                "readiness fail, but there is no dedicated strategic-risk gate."
            ),
            owner="team-runtime-quality",
            missing_input="PDD-098 strategic-risk quality gate",
            upstream_cause=(
                "Existing quality failures block publication before strategic "
                "behavior can be evaluated."
            ),
            downstream_impact=(
                "PDD-098 still needs a dedicated gate before closeout can rely on it."
            ),
            refs=[
                _rel(wave33_dir / "quality_scorecard.json", repo_root),
                _rel(wave33_dir / "readiness.json", repo_root),
            ],
            phase=PHASE34_2,
        ),
    ]
    acceptance = "blocked" if input_issues else "failed"
    return _pdd_report(
        pdd_id="PDD-098",
        acceptance_gate_status=acceptance,
        findings=findings,
        summary={
            "requirement_count": len(requirements),
            "missing_requirement_count": sum(
                1
                for requirement in requirements
                if str(requirement["status"]).startswith("missing")
            ),
            "strategic_ledger_present": strategic_ledger_present,
            "strategic_term_match_count": len(strategic_terms),
            "fail_closed_baseline_status": fail_closed["status"],
        },
        details={
            "requirements": requirements,
            "claim_risk_surface": {
                "claim_id": claim.get("claim_id"),
                "implementation_risks": claim.get("implementation_risks") or [],
                "monitoring_plan": claim.get("monitoring_plan") or [],
                "withdrawal_reissue_triggers": claim.get("withdrawal_reissue_triggers")
                or [],
            },
            "fail_closed_baseline": fail_closed,
        },
        observed=observed,
        phase=PHASE34_2,
        verdict="strategic_behavior_binding_missing; closeout_failure_is_indirect",
    )


def _pdd_report(
    *,
    pdd_id: str,
    acceptance_gate_status: str,
    findings: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    details: Mapping[str, Any],
    observed: Mapping[str, Any],
    phase: str = PHASE,
    verdict: str | None = None,
) -> dict[str, Any]:
    normalized_verdict = verdict or _verdict_for_pdd(pdd_id, acceptance_gate_status)
    report = {
        "schema_version": f"policyos.policy_design_case.pass2.{pdd_id.lower()}.v1",
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "pdd_id": pdd_id,
        "title": PDD_TITLES[pdd_id],
        "question": PDD_QUESTIONS[pdd_id],
        "wave": WAVE,
        "phase": phase,
        "diagnostic_status": "diagnosed",
        "acceptance_gate_status": acceptance_gate_status,
        "acceptance_gate_result": acceptance_gate_status,
        "runtime_acceptance_status": (
            "failed" if acceptance_gate_status in {"failed", "blocked"} else "passed"
        ),
        "verdict": normalized_verdict,
        "wave33": _wave33_from_observed(observed),
        "source_artifacts": _source_artifacts_from_observed(observed),
        "observed_wave33_case": observed,
        "summary": dict(summary),
        "findings": list(findings),
        "details": dict(details),
        "recommended_gate": _recommendation_for_pdd(pdd_id),
        "backlog_summary": _backlog_summary_for_pdd(
            pdd_id=pdd_id,
            acceptance_gate_status=acceptance_gate_status,
            verdict=normalized_verdict,
            finding_count=len(findings),
        ),
    }
    return report


def _verdict_for_pdd(pdd_id: str, acceptance_gate_status: str) -> str:
    if acceptance_gate_status == "blocked":
        return f"{pdd_id.lower()}_blocked_by_missing_wave33_input_evidence"
    if acceptance_gate_status == "satisfied":
        return f"{pdd_id.lower()}_acceptance_gate_satisfied"
    verdicts = {
        "PDD-037": "cross_domain_runtime_bundle_coverage_incomplete",
        "PDD-055": "metamorphic_runtime_variant_coverage_incomplete",
        "PDD-056": "multilingual_transliteration_equivalence_not_proven",
        "PDD-038": "adversarial_fail_closed_coverage_incomplete",
        "PDD-064": "cache_index_snapshot_poisoning_controls_not_proven",
        "PDD-065": "cross_component_error_semantics_incomplete",
        "PDD-098": "strategic_behavior_binding_missing",
    }
    return verdicts[pdd_id]


def _wave33_from_observed(observed: Mapping[str, Any]) -> dict[str, Any]:
    scorecard = _mapping(observed.get("scorecard"))
    return {
        "run_id": observed.get("run_id"),
        "job_id": observed.get("job_id"),
        "case_id": observed.get("case_id"),
        "lane_id": observed.get("lane_id"),
        "bundle_path": observed.get("bundle_path"),
        "matrix_status": observed.get("matrix_status"),
        "scorecard_status": scorecard.get("quality_status"),
        "approval_state": scorecard.get("approval_state"),
        "claim_argument_status": _mapping(observed.get("claim_argument")).get("status"),
    }


def _source_artifacts_from_observed(observed: Mapping[str, Any]) -> dict[str, str]:
    source_artifacts = {
        "real_domain_baseline": "_build/policy-design-case/rebaseline/wave-33/real_domain_baseline.json",
        "research_real_domain_matrix": "_build/policy-design-case/rebaseline/wave-33/research_real_domain_matrix.json",
        "policy_design_case_sample": "_build/policy-design-case/rebaseline/wave-33/policy_design_case_sample.json",
        "quality_scorecard": "_build/policy-design-case/rebaseline/wave-33/quality_scorecard.json",
        "readiness": "_build/policy-design-case/rebaseline/wave-33/readiness.json",
        "production_data_evidence": "_build/policy-design-case/rebaseline/wave-33/production_data_evidence.json",
        "claim_argument": "_build/policy-design-case/rebaseline/wave-33/claim_argument.json",
        "policy_grounding_matrix": "_build/policy-design-case/rebaseline/wave-33/policy_grounding_matrix.json",
    }
    if observed.get("bundle_path"):
        source_artifacts["bundle"] = str(observed["bundle_path"])
    return source_artifacts


def _backlog_summary_for_pdd(
    *,
    pdd_id: str,
    acceptance_gate_status: str,
    verdict: str,
    finding_count: int,
) -> str:
    return (
        f"Wave 34 Pass 2 ran {pdd_id} against Wave 33 real-case evidence. "
        f"The diagnostic status is diagnosed, the runtime acceptance gate is "
        f"`{acceptance_gate_status}`, and the verdict is `{verdict}` with "
        f"{finding_count} finding(s)."
    )


def _load_contracts(
    *,
    scenario_ids: Sequence[str],
) -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    for scenario_id in scenario_ids:
        contracts[scenario_id] = load_quality_scenario_contract(
            scenario_id,
            include_quarantined=True,
        )
    return contracts


def _finding(
    *,
    pdd_id: str,
    code: str,
    severity: str,
    title: str,
    message: str,
    owner: str,
    missing_input: str,
    upstream_cause: str,
    downstream_impact: str,
    refs: Sequence[str],
    scenario_id: str | None = None,
    next_command: str | None = None,
    phase: str = PHASE,
) -> dict[str, Any]:
    return {
        "pdd_id": pdd_id,
        "code": code,
        "severity": severity,
        "title": title,
        "message": message,
        "owner": owner,
        "phase": phase,
        "scenario_id": scenario_id,
        "missing_input": missing_input,
        "upstream_cause": upstream_cause,
        "downstream_impact": downstream_impact,
        "refs": list(refs),
        "next_command": next_command
        or "uv run python tools/quality/validation/build_policy_design_case_pass2_diagnostics.py",
    }


def _extract_quality_scenario_ids(matrix: Mapping[str, Any]) -> list[str]:
    scenario_ids: list[str] = []
    lanes = matrix.get("lanes")
    if isinstance(lanes, list):
        for lane in lanes:
            if not isinstance(lane, dict):
                continue
            scenario = lane.get("scenario")
            if isinstance(scenario, str) and scenario not in {"", "public_golden"}:
                scenario_ids.append(scenario)
            command = lane.get("command")
            if isinstance(command, list):
                scenario_ids.extend(_scenario_ids_from_command(command))
    selection = matrix.get("selection")
    if isinstance(selection, dict):
        scenario = selection.get("scenario")
        if isinstance(scenario, str) and scenario:
            scenario_ids.append(scenario)
    return sorted(dict.fromkeys(scenario_ids))


def _scenario_ids_from_command(command: Sequence[Any]) -> list[str]:
    rendered = [str(item) for item in command]
    found: list[str] = []
    for index, item in enumerate(rendered):
        if item.startswith("--quality-scenario="):
            found.append(item.split("=", 1)[1])
        elif item == "--quality-scenario" and index + 1 < len(rendered):
            found.append(rendered[index + 1])
    return [item for item in found if item]


def _scorecard_blocking_failures(scorecard: Mapping[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for gate in scorecard.get("quality_gates") or []:
        if not isinstance(gate, dict):
            continue
        if gate.get("status") == "fail" and gate.get("blocking") is True:
            failures.append(
                {
                    "name": gate.get("name"),
                    "code": gate.get("code"),
                    "stage": gate.get("stage"),
                    "evidence_ref": gate.get("evidence_ref"),
                    "next_action": gate.get("next_action"),
                }
            )
    return failures


def _intent_summary(intent: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "jurisdiction": intent.get("jurisdiction"),
        "policy_time": intent.get("policy_time"),
        "data_time": intent.get("data_time"),
        "policy_problem": intent.get("policy_problem"),
        "desired_outcome": intent.get("desired_outcome"),
        "proposed_intervention": intent.get("proposed_intervention"),
        "target_population": intent.get("target_population"),
    }


def _control_by_id(report: Mapping[str, Any], control_id: str) -> dict[str, Any]:
    for control in report.get("controls") or []:
        if isinstance(control, dict) and control.get("control_id") == control_id:
            return dict(control)
    return {}


def _aggregate_acceptance(pdds: Mapping[str, Mapping[str, Any]]) -> str:
    statuses = {str(report.get("acceptance_gate_status")) for report in pdds.values()}
    if "blocked" in statuses:
        return "not_evaluated"
    if "failed" in statuses:
        return "failed"
    return "passed"


def _contract_control_status(pdds: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    pdd37 = _mapping(pdds.get("PDD-037"))
    pdd55 = _mapping(pdds.get("PDD-055"))
    return {
        "pdd037_contract_control_pass_count": _mapping(pdd37.get("summary")).get(
            "contract_control_pass_count",
            0,
        ),
        "pdd037_semantic_binding_pass_count": _mapping(pdd37.get("summary")).get(
            "semantic_binding_pass_count",
            0,
        ),
        "pdd055_contract_metamorphic_pass_count": _mapping(pdd55.get("summary")).get(
            "contract_metamorphic_pass_count",
            0,
        ),
    }


def _wave33_fail_closed_summary(
    loaded: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> dict[str, Any]:
    real = _mapping(loaded.get("real_domain_baseline.json"))
    scorecard = _mapping(loaded.get("quality_scorecard.json"))
    readiness = _mapping(loaded.get("readiness.json"))
    research_case = _mapping(real.get("research_profile_case"))
    blocking_failures = scorecard.get("blocking_quality_failures")
    if not isinstance(blocking_failures, list):
        blocking_failures = _scorecard_blocking_failures(scorecard)
    minimum_failures = readiness.get("minimum_closeout_gate_failures")
    if not isinstance(minimum_failures, list):
        minimum_failures = []
    fail_closed = bool(
        research_case.get("matrix_status") == "failed"
        or scorecard.get("quality_status") == "fail"
        or readiness.get("status") == "fail"
        or observed.get("readiness", {}).get("status") == "fail"
    )
    return {
        "status": "confirmed" if fail_closed else "not_confirmed",
        "matrix_status": research_case.get("matrix_status"),
        "failure_code": research_case.get("failure_code"),
        "scorecard_status": research_case.get("scorecard_status"),
        "quality_status": scorecard.get("quality_status"),
        "approval_state": scorecard.get("approval_state"),
        "readiness_status": readiness.get("status"),
        "passes_all": readiness.get("passes_all"),
        "passes_required": readiness.get("passes_required"),
        "blocking_quality_failure_count": len(blocking_failures),
        "minimum_closeout_gate_failure_count": len(minimum_failures),
    }


def _scorecard_failures(scorecard: Mapping[str, Any]) -> list[dict[str, Any]]:
    failures = scorecard.get("blocking_quality_failures")
    if isinstance(failures, list):
        return [dict(item) for item in failures if isinstance(item, dict)]
    return _scorecard_blocking_failures(scorecard)


def _scorecard_code_set(scorecard: Mapping[str, Any]) -> set[str]:
    return _codes_from_items(_scorecard_failures(scorecard)) | _codes_from_items(
        scorecard.get("quality_gates") or []
    )


def _codes_from_items(items: object) -> set[str]:
    codes: set[str] = set()
    if not isinstance(items, list):
        return codes
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in ("code", "failure_code"):
            value = item.get(key)
            if isinstance(value, str) and value:
                codes.add(value)
    return codes


def _first_code(items: Sequence[Mapping[str, Any]]) -> str | None:
    for item in items:
        for key in ("code", "failure_code"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _issue_code_counts(issues: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not isinstance(issues, list):
        return counts
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        code = issue.get("code")
        if not isinstance(code, str) or not code:
            continue
        counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items()))


def _timeline_cache_events(timeline: Mapping[str, Any]) -> list[dict[str, Any]]:
    events = timeline.get("events")
    if not isinstance(events, list):
        return []
    cache_events: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_name = str(event.get("event") or "")
        metrics = _mapping(event.get("metrics"))
        refs = _mapping(event.get("refs"))
        if "CACHE" not in event_name and not any(
            "cache" in str(key).casefold() for key in metrics
        ):
            continue
        outputs = refs.get("outputs")
        outputs = outputs if isinstance(outputs, list) else []
        cache_events.append(
            {
                "phase": event.get("phase"),
                "event": event.get("event"),
                "status": event.get("status"),
                "artifact_kinds": sorted(
                    {
                        str(output.get("kind"))
                        for output in outputs
                        if isinstance(output, dict) and output.get("kind")
                    }
                ),
                "counter_keys": sorted(metrics.keys()),
            }
        )
    return cache_events


def _readiness_summary_semantics(readiness: Mapping[str, Any]) -> dict[str, Any]:
    summary = _mapping(readiness.get("summary"))
    status_counts = _mapping(summary.get("status_counts"))
    component_results = _mapping(readiness.get("component_results"))
    readiness_aggregator = _mapping(component_results.get("readiness_aggregator"))
    failure_class_counts = _mapping(summary.get("failure_class_counts"))
    collapsed = (
        readiness.get("status") == "fail"
        and status_counts.get("fail", 0) == 0
        and readiness_aggregator.get("status") == "pass"
    )
    return {
        "status": (
            "collapses_or_hides_root_cause_in_summary"
            if collapsed
            else "preserves_root_cause"
        ),
        "readiness_status": readiness.get("status"),
        "summary_status_counts": status_counts,
        "readiness_aggregator_component_status": readiness_aggregator.get("status"),
        "component_failures": readiness.get("component_failures") or [],
        "failure_class_counts": failure_class_counts,
    }


def _first_claim(grounding: Mapping[str, Any]) -> dict[str, Any]:
    claims = grounding.get("claims")
    if isinstance(claims, list):
        for claim in claims:
            if isinstance(claim, dict):
                return dict(claim)
    claim = grounding.get("claim")
    return dict(claim) if isinstance(claim, dict) else {}


def _strategic_surface_terms(value: object) -> list[str]:
    text = json.dumps(value, ensure_ascii=False).casefold()
    terms = (
        "actor",
        "incentive",
        "manipulable",
        "threshold",
        "enforcement",
        "fraud",
        "gaming",
        "arbitrage",
        "misreport",
        "mitigation",
    )
    return [term for term in terms if term in text]


def _contains_key_fragment(value: object, fragments: Sequence[str]) -> bool:
    wanted = tuple(fragment.casefold() for fragment in fragments)
    if isinstance(value, dict):
        for key, nested in value.items():
            if any(fragment in str(key).casefold() for fragment in wanted):
                return True
            if _contains_key_fragment(nested, wanted):
                return True
    elif isinstance(value, list):
        return any(_contains_key_fragment(item, wanted) for item in value)
    return False


def _bundle_refs(bundle_path: str, relative_paths: Sequence[str]) -> list[str]:
    if not bundle_path:
        return []
    return [
        (Path(bundle_path) / relative_path).as_posix()
        for relative_path in relative_paths
    ]


def _render_phase_summary(payload: Mapping[str, Any], repo_root: Path) -> str:
    lines = [
        f"# Phase {payload.get('phase')} Pass 2 Diagnostics",
        "",
        f"Status: `{payload.get('status')}`",
        f"Runtime acceptance status: `{payload.get('runtime_acceptance_status')}`",
        "",
        "Wave 33 observed runtime scenarios:",
    ]
    observed = _mapping(payload.get("observed_wave33_case"))
    scenario_ids = _strings(observed.get("observed_scenario_ids"))
    if scenario_ids:
        lines.extend(f"- `{scenario_id}`" for scenario_id in scenario_ids)
    else:
        lines.append("- none")
    lines.extend(["", "PDD results:", ""])
    for pdd_id, report in _mapping(payload.get("pdds")).items():
        report_map = _mapping(report)
        summary_path = DEFAULT_OUTPUT_DIR / pdd_id.lower() / "summary.md"
        lines.append(
            "- "
            f"`{pdd_id}`: `{report_map.get('acceptance_gate_status')}`, "
            f"{len(report_map.get('findings') or [])} finding(s), "
            f"summary `{_rel(summary_path, repo_root)}`"
        )
    lines.append("")
    return "\n".join(lines)


def _render_pdd_detail(report: Mapping[str, Any], repo_root: Path) -> str:
    pdd_id = str(report["pdd_id"])
    lines = [
        f"# {pdd_id} - {report['title']}",
        "",
        f"Diagnostic status: `{report.get('diagnostic_status')}`",
        f"Acceptance gate status: `{report.get('acceptance_gate_status')}`",
        f"Runtime acceptance status: `{report.get('runtime_acceptance_status')}`",
        "",
        "Summary:",
    ]
    for key, value in _mapping(report.get("summary")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "Findings:", ""])
    findings = report.get("findings") or []
    if findings:
        lines.append("| Code | Severity | Scenario | Missing Input |")
        lines.append("|---|---|---|---|")
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            lines.append(
                "| "
                f"`{finding.get('code')}` | "
                f"`{finding.get('severity')}` | "
                f"`{finding.get('scenario_id') or 'global'}` | "
                f"{finding.get('missing_input')} |"
            )
    else:
        lines.append("No findings.")
    lines.extend(["", "Detailed JSON is the sibling artifact in this directory.", ""])
    return "\n".join(lines)


def _render_pdd_summary(report: Mapping[str, Any], repo_root: Path) -> str:
    pdd_id = str(report["pdd_id"])
    slug = PDD_ARTIFACTS_BY_ID[pdd_id]
    json_path = DEFAULT_OUTPUT_DIR / pdd_id.lower() / f"{slug}.json"
    detail_path = DEFAULT_OUTPUT_DIR / pdd_id.lower() / f"{slug}.md"
    summary = _mapping(report.get("summary"))
    lines = [
        f"# {pdd_id} Summary",
        "",
        f"Verdict: `{report.get('diagnostic_status')}`",
        f"Acceptance result: `{report.get('acceptance_gate_status')}`",
        f"Runtime/product acceptance status: `{report.get('runtime_acceptance_status')}`",
        "",
        "Artifacts:",
        f"- `{_rel(json_path, repo_root)}`",
        f"- `{_rel(detail_path, repo_root)}`",
        "",
        "Core counts:",
    ]
    for key, value in summary.items():
        lines.append(f"- `{key}`: `{value}`")
    findings = report.get("findings") or []
    if findings:
        lines.extend(["", "Primary finding codes:"])
        for code in sorted(
            {
                str(finding.get("code"))
                for finding in findings
                if isinstance(finding, dict)
            }
        ):
            lines.append(f"- `{code}`")
    lines.extend(
        [
            "",
            "Recommended remediation:",
            _recommendation_for_pdd(pdd_id),
            "",
            "Verification:",
            "- `uv run pytest "
            "tests/repo_quality/tools/test_policy_design_case_pass2_diagnostics.py "
            "-q`",
            "- `uv run python "
            "tools/quality/validation/build_policy_design_case_pass2_diagnostics.py`",
            "",
        ]
    )
    return "\n".join(lines)


def _render_backlog_fragment(report: Mapping[str, Any], repo_root: Path) -> str:
    pdd_id = str(report["pdd_id"])
    slug = PDD_ARTIFACTS_BY_ID[pdd_id]
    lines = [
        f"### {pdd_id} - {report['title']}",
        "",
        "- Pass: Pass 2 behavioral diagnostics.",
        f"- Phase: {report.get('phase')}.",
        f"- Diagnostic status: `{report.get('diagnostic_status')}`.",
        f"- Acceptance result: `{report.get('acceptance_gate_status')}`.",
        f"- Runtime/product acceptance status: `{report.get('runtime_acceptance_status')}`.",
        f"- Detailed artifact: `_build/diagnostics/{pdd_id.lower()}/{slug}.json`.",
        f"- Summary artifact: `_build/diagnostics/{pdd_id.lower()}/summary.md`.",
        "- Key finding codes: "
        + ", ".join(
            f"`{code}`"
            for code in sorted(
                {
                    str(finding.get("code"))
                    for finding in report.get("findings") or []
                    if isinstance(finding, dict)
                }
            )
        )
        + ".",
        "- Next action: " + _recommendation_for_pdd(pdd_id),
        "",
    ]
    return "\n".join(lines)


def _recommendation_for_pdd(pdd_id: str) -> str:
    if pdd_id == "PDD-037":
        return (
            "Generate research-profile runtime bundles for the five required "
            "cross-domain scenarios and rerun Phase 34.1."
        )
    if pdd_id == "PDD-055":
        return (
            "Add paired metamorphic canary lanes for paraphrase, language, "
            "jurisdiction, time, irrelevant-evidence, and data-removal perturbations."
        )
    if pdd_id == "PDD-056":
        return (
            "Add paired English, Ukrainian, mixed-language, and transliterated runtime "
            "lanes plus a hardcoded-language-path audit."
        )
    if pdd_id == "PDD-038":
        return (
            "Add scenario-bearing no-jurisdiction, legal-conflict, irrelevant-data, "
            "insufficient-ID, hidden-token, prompt-injection, and illegal-policy probes."
        )
    if pdd_id == "PDD-064":
        return (
            "Emit cache/index fingerprint ledgers, manifest-to-index compatibility "
            "proofs, and stale/poisoned/cross-context negative tests."
        )
    if pdd_id == "PDD-065":
        return (
            "Publish a cross-component error taxonomy and make readiness summaries "
            "carry root-cause codes, next actions, and owning layers."
        )
    return (
        "Add strategic behavior ledgers and adversarial gaming, fraud, arbitrage, "
        "misreporting, threshold, enforcement, and mitigation bindings."
    )


def _resolve_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _rel(path: Path | str, repo_root: Path) -> str:
    candidate = Path(path)
    if not candidate.is_absolute():
        return candidate.as_posix()
    try:
        return candidate.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return candidate.as_posix()


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave33-dir", type=Path, default=DEFAULT_WAVE33_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--fragment-dir", type=Path, default=DEFAULT_FRAGMENT_DIR)
    parser.add_argument(
        "--phase",
        choices=("34.1", "34.2", "all"),
        default="all",
        help="Diagnostic phase to write. Defaults to all Phase 34 pass2 diagnostics.",
    )
    args = parser.parse_args(argv)

    written: dict[str, Path] = {}
    payload_paths: list[Path] = []
    if args.phase in {"34.1", "all"}:
        phase34_1_written = write_phase34_1_reports(
            repo_root=args.repo_root,
            wave33_dir=args.wave33_dir,
            output_dir=args.output_dir,
            fragment_dir=args.fragment_dir,
        )
        written.update({f"phase34_1:{key}": path for key, path in phase34_1_written.items()})
        payload_paths.append(phase34_1_written["phase_payload"])
    if args.phase in {"34.2", "all"}:
        phase34_2_written = write_phase34_2_reports(
            repo_root=args.repo_root,
            wave33_dir=args.wave33_dir,
            output_dir=args.output_dir,
            fragment_dir=args.fragment_dir,
        )
        written.update(
            {f"phase34_2:{key}": path for key, path in phase34_2_written.items()}
        )
        payload_paths.append(phase34_2_written["phase34_2_payload"])

    payloads = [
        json.loads(payload_path.read_text(encoding="utf-8"))
        for payload_path in payload_paths
    ]
    sys.stdout.write(
        _dump_json(
            {
                "status": (
                    "blocked"
                    if any(payload["status"] == "blocked" for payload in payloads)
                    else "diagnosed"
                ),
                "phases": {
                    str(payload["phase"]): {
                        "status": payload["status"],
                        "runtime_acceptance_status": payload[
                            "runtime_acceptance_status"
                        ],
                    }
                    for payload in payloads
                },
                "output": {
                    key: _rel(path, args.repo_root) for key, path in written.items()
                },
            }
        )
    )
    return 1 if any(payload["status"] == "blocked" for payload in payloads) else 0


if __name__ == "__main__":
    sys.exit(main())
