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
from tools.quality.validation import pass2_diagnostics_support as _pass2_support  # noqa: E402
from tools.quality.validation import pass2_phase34_1_diagnostics as _pass2_phase34_1  # noqa: E402
from tools.quality.validation import pass2_phase34_2_diagnostics as _pass2_phase34_2  # noqa: E402
from tools.quality.validation.pass2_diagnostics_support import Pass2DiagnosticBindings  # noqa: E402

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
        "runtime_acceptance_status": ("not_evaluated" if blocked else _aggregate_acceptance(pdds)),
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
        "runtime_acceptance_status": ("not_evaluated" if blocked else _aggregate_acceptance(pdds)),
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
                pdd_id: report["acceptance_gate_status"] for pdd_id, report in pdds.items()
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
    return _pass2_support._load_wave33_artifacts(
        bindings=_pass2_diagnostic_bindings(),
        repo_root=repo_root,
        wave33_dir=wave33_dir,
        phase=phase,
    )


def _load_wave33_bundle_artifacts(
    *,
    repo_root: Path,
    observed: Mapping[str, Any],
    phase: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    return _pass2_support._load_wave33_bundle_artifacts(
        bindings=_pass2_diagnostic_bindings(), repo_root=repo_root, observed=observed, phase=phase
    )


def _observed_wave33_case(loaded: Mapping[str, Any]) -> dict[str, Any]:
    return _pass2_support._observed_wave33_case(
        bindings=_pass2_diagnostic_bindings(), loaded=loaded
    )


def _build_pdd037_report(
    *,
    contracts: Mapping[str, Mapping[str, Any]],
    observed: Mapping[str, Any],
    input_issues: Sequence[Mapping[str, Any]],
    wave33_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    return _pass2_phase34_1._build_pdd037_report(
        bindings=_pass2_diagnostic_bindings(),
        contracts=contracts,
        observed=observed,
        input_issues=input_issues,
        wave33_dir=wave33_dir,
        repo_root=repo_root,
    )


def _build_pdd055_report(
    *,
    contracts: Mapping[str, Mapping[str, Any]],
    observed: Mapping[str, Any],
    input_issues: Sequence[Mapping[str, Any]],
    wave33_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    return _pass2_phase34_1._build_pdd055_report(
        bindings=_pass2_diagnostic_bindings(),
        contracts=contracts,
        observed=observed,
        input_issues=input_issues,
        wave33_dir=wave33_dir,
        repo_root=repo_root,
    )


def _build_pdd056_report(
    *,
    contracts: Mapping[str, Mapping[str, Any]],
    observed: Mapping[str, Any],
    input_issues: Sequence[Mapping[str, Any]],
    wave33_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    return _pass2_phase34_1._build_pdd056_report(
        bindings=_pass2_diagnostic_bindings(),
        contracts=contracts,
        observed=observed,
        input_issues=input_issues,
        wave33_dir=wave33_dir,
        repo_root=repo_root,
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
    return _pass2_phase34_2._build_pdd038_report(
        bindings=_pass2_diagnostic_bindings(),
        loaded=loaded,
        observed=observed,
        bundle_artifacts=bundle_artifacts,
        input_issues=input_issues,
        wave33_dir=wave33_dir,
        repo_root=repo_root,
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
    return _pass2_phase34_2._build_pdd064_report(
        bindings=_pass2_diagnostic_bindings(),
        loaded=loaded,
        observed=observed,
        bundle_artifacts=bundle_artifacts,
        input_issues=input_issues,
        wave33_dir=wave33_dir,
        repo_root=repo_root,
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
    return _pass2_phase34_2._build_pdd065_report(
        bindings=_pass2_diagnostic_bindings(),
        loaded=loaded,
        observed=observed,
        bundle_artifacts=bundle_artifacts,
        input_issues=input_issues,
        wave33_dir=wave33_dir,
        repo_root=repo_root,
    )


def _build_pdd098_report(
    *,
    loaded: Mapping[str, Any],
    observed: Mapping[str, Any],
    input_issues: Sequence[Mapping[str, Any]],
    wave33_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    return _pass2_phase34_2._build_pdd098_report(
        bindings=_pass2_diagnostic_bindings(),
        loaded=loaded,
        observed=observed,
        input_issues=input_issues,
        wave33_dir=wave33_dir,
        repo_root=repo_root,
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
    return _pass2_support._pdd_report(
        bindings=_pass2_diagnostic_bindings(),
        pdd_id=pdd_id,
        acceptance_gate_status=acceptance_gate_status,
        findings=findings,
        summary=summary,
        details=details,
        observed=observed,
        phase=phase,
        verdict=verdict,
    )


def _verdict_for_pdd(pdd_id: str, acceptance_gate_status: str) -> str:
    return _pass2_support._verdict_for_pdd(
        bindings=_pass2_diagnostic_bindings(),
        pdd_id=pdd_id,
        acceptance_gate_status=acceptance_gate_status,
    )


def _wave33_from_observed(observed: Mapping[str, Any]) -> dict[str, Any]:
    return _pass2_support._wave33_from_observed(
        bindings=_pass2_diagnostic_bindings(), observed=observed
    )


def _source_artifacts_from_observed(observed: Mapping[str, Any]) -> dict[str, str]:
    return _pass2_support._source_artifacts_from_observed(
        bindings=_pass2_diagnostic_bindings(), observed=observed
    )


def _backlog_summary_for_pdd(
    *,
    pdd_id: str,
    acceptance_gate_status: str,
    verdict: str,
    finding_count: int,
) -> str:
    return _pass2_support._backlog_summary_for_pdd(
        bindings=_pass2_diagnostic_bindings(),
        pdd_id=pdd_id,
        acceptance_gate_status=acceptance_gate_status,
        verdict=verdict,
        finding_count=finding_count,
    )


def _load_contracts(
    *,
    scenario_ids: Sequence[str],
) -> dict[str, dict[str, Any]]:
    return _pass2_support._load_contracts(
        bindings=_pass2_diagnostic_bindings(), scenario_ids=scenario_ids
    )


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
    return _pass2_support._finding(
        bindings=_pass2_diagnostic_bindings(),
        pdd_id=pdd_id,
        code=code,
        severity=severity,
        title=title,
        message=message,
        owner=owner,
        missing_input=missing_input,
        upstream_cause=upstream_cause,
        downstream_impact=downstream_impact,
        refs=refs,
        scenario_id=scenario_id,
        next_command=next_command,
        phase=phase,
    )


def _extract_quality_scenario_ids(matrix: Mapping[str, Any]) -> list[str]:
    return _pass2_support._extract_quality_scenario_ids(
        bindings=_pass2_diagnostic_bindings(), matrix=matrix
    )


def _scenario_ids_from_command(command: Sequence[Any]) -> list[str]:
    return _pass2_support._scenario_ids_from_command(
        bindings=_pass2_diagnostic_bindings(), command=command
    )


def _scorecard_blocking_failures(scorecard: Mapping[str, Any]) -> list[dict[str, Any]]:
    return _pass2_support._scorecard_blocking_failures(
        bindings=_pass2_diagnostic_bindings(), scorecard=scorecard
    )


def _intent_summary(intent: Mapping[str, Any]) -> dict[str, Any]:
    return _pass2_support._intent_summary(bindings=_pass2_diagnostic_bindings(), intent=intent)


def _control_by_id(report: Mapping[str, Any], control_id: str) -> dict[str, Any]:
    return _pass2_support._control_by_id(
        bindings=_pass2_diagnostic_bindings(), report=report, control_id=control_id
    )


def _aggregate_acceptance(pdds: Mapping[str, Mapping[str, Any]]) -> str:
    return _pass2_support._aggregate_acceptance(bindings=_pass2_diagnostic_bindings(), pdds=pdds)


def _contract_control_status(pdds: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return _pass2_support._contract_control_status(bindings=_pass2_diagnostic_bindings(), pdds=pdds)


def _wave33_fail_closed_summary(
    loaded: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> dict[str, Any]:
    return _pass2_support._wave33_fail_closed_summary(
        bindings=_pass2_diagnostic_bindings(), loaded=loaded, observed=observed
    )


def _scorecard_failures(scorecard: Mapping[str, Any]) -> list[dict[str, Any]]:
    return _pass2_support._scorecard_failures(
        bindings=_pass2_diagnostic_bindings(), scorecard=scorecard
    )


def _scorecard_code_set(scorecard: Mapping[str, Any]) -> set[str]:
    return _pass2_support._scorecard_code_set(
        bindings=_pass2_diagnostic_bindings(), scorecard=scorecard
    )


def _codes_from_items(items: object) -> set[str]:
    return _pass2_support._codes_from_items(bindings=_pass2_diagnostic_bindings(), items=items)


def _first_code(items: Sequence[Mapping[str, Any]]) -> str | None:
    return _pass2_support._first_code(bindings=_pass2_diagnostic_bindings(), items=items)


def _issue_code_counts(issues: object) -> dict[str, int]:
    return _pass2_support._issue_code_counts(bindings=_pass2_diagnostic_bindings(), issues=issues)


def _timeline_cache_events(timeline: Mapping[str, Any]) -> list[dict[str, Any]]:
    return _pass2_support._timeline_cache_events(
        bindings=_pass2_diagnostic_bindings(), timeline=timeline
    )


def _readiness_summary_semantics(readiness: Mapping[str, Any]) -> dict[str, Any]:
    return _pass2_support._readiness_summary_semantics(
        bindings=_pass2_diagnostic_bindings(), readiness=readiness
    )


def _first_claim(grounding: Mapping[str, Any]) -> dict[str, Any]:
    return _pass2_support._first_claim(bindings=_pass2_diagnostic_bindings(), grounding=grounding)


def _strategic_surface_terms(value: object) -> list[str]:
    return _pass2_support._strategic_surface_terms(
        bindings=_pass2_diagnostic_bindings(), value=value
    )


def _contains_key_fragment(value: object, fragments: Sequence[str]) -> bool:
    return _pass2_support._contains_key_fragment(
        bindings=_pass2_diagnostic_bindings(), value=value, fragments=fragments
    )


def _bundle_refs(bundle_path: str, relative_paths: Sequence[str]) -> list[str]:
    return _pass2_support._bundle_refs(
        bindings=_pass2_diagnostic_bindings(),
        bundle_path=bundle_path,
        relative_paths=relative_paths,
    )


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
            {str(finding.get("code")) for finding in findings if isinstance(finding, dict)}
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
    return _pass2_support._recommendation_for_pdd(
        bindings=_pass2_diagnostic_bindings(), pdd_id=pdd_id
    )


def _resolve_path(repo_root: Path, path: Path) -> Path:
    return _pass2_support._resolve_path(
        bindings=_pass2_diagnostic_bindings(), repo_root=repo_root, path=path
    )


def _rel(path: Path | str, repo_root: Path) -> str:
    return _pass2_support._rel(
        bindings=_pass2_diagnostic_bindings(), path=path, repo_root=repo_root
    )


def _mapping(value: object) -> dict[str, Any]:
    return _pass2_support._mapping(bindings=_pass2_diagnostic_bindings(), value=value)


def _strings(value: object) -> list[str]:
    return _pass2_support._strings(bindings=_pass2_diagnostic_bindings(), value=value)


def _dump_json(payload: Mapping[str, Any]) -> str:
    return _pass2_support._dump_json(bindings=_pass2_diagnostic_bindings(), payload=payload)


def _now() -> str:
    return _pass2_support._now(bindings=_pass2_diagnostic_bindings())


def _pass2_diagnostic_bindings() -> Pass2DiagnosticBindings:
    return Pass2DiagnosticBindings(
        pdd038_adversarial_scenarios=PDD038_ADVERSARIAL_SCENARIOS,
        pdd_questions=PDD_QUESTIONS,
        pdd_titles=PDD_TITLES,
        phase34_2=PHASE34_2,
        phase34_2_bundle_artifacts=PHASE34_2_BUNDLE_ARTIFACTS,
        path_type=Path,
        required_wave33_artifacts=REQUIRED_WAVE33_ARTIFACTS,
        tool_name=TOOL_NAME,
        utc_timezone=UTC,
        wave=WAVE,
        backlog_summary_for_pdd=_backlog_summary_for_pdd,
        bundle_refs=_bundle_refs,
        codes_from_items=_codes_from_items,
        contains_key_fragment=_contains_key_fragment,
        control_by_id=_control_by_id,
        extract_quality_scenario_ids=_extract_quality_scenario_ids,
        finding=_finding,
        first_claim=_first_claim,
        first_code=_first_code,
        intent_summary=_intent_summary,
        issue_code_counts=_issue_code_counts,
        mapping=_mapping,
        now=_now,
        pdd_report=_pdd_report,
        readiness_summary_semantics=_readiness_summary_semantics,
        recommendation_for_pdd=_recommendation_for_pdd,
        rel=_rel,
        resolve_path=_resolve_path,
        scenario_ids_from_command=_scenario_ids_from_command,
        scorecard_blocking_failures=_scorecard_blocking_failures,
        scorecard_code_set=_scorecard_code_set,
        scorecard_failures=_scorecard_failures,
        source_artifacts_from_observed=_source_artifacts_from_observed,
        strategic_surface_terms=_strategic_surface_terms,
        strings=_strings,
        timeline_cache_events=_timeline_cache_events,
        verdict_for_pdd=_verdict_for_pdd,
        wave33_fail_closed_summary=_wave33_fail_closed_summary,
        wave33_from_observed=_wave33_from_observed,
        build_cross_domain_control_report=build_cross_domain_control_report,
        build_metamorphic_prompt_report=build_metamorphic_prompt_report,
        build_negative_control_report=build_negative_control_report,
        build_scenario_semantic_binding_report=build_scenario_semantic_binding_report,
        datetime_module=datetime,
        json_module=json,
        load_quality_scenario_contract=load_quality_scenario_contract,
    )


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
        written.update({f"phase34_2:{key}": path for key, path in phase34_2_written.items()})
        payload_paths.append(phase34_2_written["phase34_2_payload"])

    payloads = [
        json.loads(payload_path.read_text(encoding="utf-8")) for payload_path in payload_paths
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
                        "runtime_acceptance_status": payload["runtime_acceptance_status"],
                    }
                    for payload in payloads
                },
                "output": {key: _rel(path, args.repo_root) for key, path in written.items()},
            }
        )
    )
    return 1 if any(payload["status"] == "blocked" for payload in payloads) else 0


if __name__ == "__main__":
    sys.exit(main())
