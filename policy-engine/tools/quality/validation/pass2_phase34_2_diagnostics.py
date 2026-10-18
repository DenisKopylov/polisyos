"""Complete Phase 34.2 PDD report calculations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tools.quality.validation.pass2_diagnostics_support import Pass2DiagnosticBindings


def _build_pdd038_report(
    *,
    loaded: Mapping[str, Any],
    observed: Mapping[str, Any],
    bundle_artifacts: Mapping[str, Any],
    input_issues: Sequence[Mapping[str, Any]],
    wave33_dir: Path,
    repo_root: Path,
    bindings: Pass2DiagnosticBindings,
) -> dict[str, Any]:
    pdd038_adversarial_scenarios = bindings.pdd038_adversarial_scenarios
    phase34_2 = bindings.phase34_2
    _bundle_refs = bindings.bundle_refs
    _finding = bindings.finding
    _first_code = bindings.first_code
    _mapping = bindings.mapping
    _pdd_report = bindings.pdd_report
    _rel = bindings.rel
    _scorecard_code_set = bindings.scorecard_code_set
    _wave33_fail_closed_summary = bindings.wave33_fail_closed_summary
    case = _mapping(loaded.get("policy_design_case_sample.json"))
    scorecard_codes = _scorecard_code_set(_mapping(loaded.get("quality_scorecard.json")))
    jurisdiction_spine = _mapping(case.get("jurisdiction_spine"))
    jurisdiction_blockers = [
        item for item in jurisdiction_spine.get("blockers") or [] if isinstance(item, dict)
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
                if "policy_design_jurisdiction_unresolved_competence_blocker" in scorecard_codes
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
            "prompt_tool_status": _mapping(prompt_tool_ledger.get("summary")).get("status"),
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
            downstream_impact=("The baseline did not publish a production-ready policy decision."),
            refs=[_rel(wave33_dir, repo_root)],
            phase=phase34_2,
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
            phase=phase34_2,
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
            missing_input=("hidden-token leakage and prompt-injected-source rejection fixtures"),
            upstream_cause=(
                "Runtime assurance artifacts do not expose per-adversary scenario results."
            ),
            downstream_impact=(
                "A pass status cannot demonstrate source and hidden-token fail-closed semantics."
            ),
            refs=_bundle_refs(
                bundle_path,
                [
                    "quality_evidence/security_assurance_report.json",
                    "quality_evidence/prompt_tool_ledger.json",
                ],
            ),
            phase=phase34_2,
        ),
    ]
    acceptance = "blocked" if input_issues else "failed"
    return _pdd_report(
        pdd_id="PDD-038",
        acceptance_gate_status=acceptance,
        findings=findings,
        summary={
            "fail_closed_baseline_status": fail_closed["status"],
            "required_scenario_count": len(pdd038_adversarial_scenarios),
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
            "prompt_tool_status": _mapping(prompt_tool_ledger.get("summary")).get("status"),
        },
        details={
            "fail_closed_baseline": fail_closed,
            "scenario_matrix": scenario_rows,
        },
        observed=observed,
        phase=phase34_2,
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
    bindings: Pass2DiagnosticBindings,
) -> dict[str, Any]:
    phase34_2 = bindings.phase34_2
    _bundle_refs = bindings.bundle_refs
    _finding = bindings.finding
    _issue_code_counts = bindings.issue_code_counts
    _contains_key_fragment = bindings.contains_key_fragment
    _mapping = bindings.mapping
    _pdd_report = bindings.pdd_report
    _rel = bindings.rel
    _scorecard_code_set = bindings.scorecard_code_set
    _timeline_cache_events = bindings.timeline_cache_events
    scorecard_codes = _scorecard_code_set(_mapping(loaded.get("quality_scorecard.json")))
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
        _mapping(production_data_quality.get("authority_envelope")).get("same_input_closure")
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
                "partial_gap" if fabric_manifest_ref or production_manifest_ref else "missing"
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
                "Scorecard blocks closeout when Data Forge snapshot binding evidence is missing."
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
                "Fabric source-facet incompleteness is reflected in blocking scorecard codes."
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
                "cache/index fingerprint ledger and manifest-to-index compatibility proof"
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
            phase=phase34_2,
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
                "Selected Fabric sources lack source-rights and semantic facet bindings."
            ),
            downstream_impact=(
                "The baseline does not pass while source or snapshot binding "
                "evidence is incomplete."
            ),
            refs=[_rel(wave33_dir / "quality_scorecard.json", repo_root)],
            phase=phase34_2,
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
                "Wave 33 collected a baseline runtime trace instead of cache poisoning probes."
            ),
            downstream_impact=(
                "Cache hits/stores cannot be audited for cross-run, cross-tenant, "
                "or cross-jurisdiction poisoning."
            ),
            refs=_bundle_refs(bundle_path, ["timeline.json"]),
            phase=phase34_2,
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
        phase=phase34_2,
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
    bindings: Pass2DiagnosticBindings,
) -> dict[str, Any]:
    phase34_2 = bindings.phase34_2
    required_wave33_artifacts = bindings.required_wave33_artifacts
    _bundle_refs = bindings.bundle_refs
    _codes_from_items = bindings.codes_from_items
    _contains_key_fragment = bindings.contains_key_fragment
    _finding = bindings.finding
    _mapping = bindings.mapping
    _pdd_report = bindings.pdd_report
    _readiness_summary_semantics = bindings.readiness_summary_semantics
    _rel = bindings.rel
    _scorecard_failures = bindings.scorecard_failures
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
                    _rel(wave33_dir / name, repo_root) for name in required_wave33_artifacts
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
            phase=phase34_2,
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
                "readiness summary entries that carry root-cause failure codes and next actions"
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
            phase=phase34_2,
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
                "Wave 33 emits typed errors but does not package a shared semantics contract."
            ),
            downstream_impact=(
                "Distinct failure causes are inferred from artifacts rather than "
                "governed by a shared contract."
            ),
            refs=[_rel(wave33_dir, repo_root)],
            phase=phase34_2,
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
                1 for surface in surfaces if surface["status"] == "preserves_root_cause"
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
        phase=phase34_2,
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
    bindings: Pass2DiagnosticBindings,
) -> dict[str, Any]:
    phase34_2 = bindings.phase34_2
    _contains_key_fragment = bindings.contains_key_fragment
    _finding = bindings.finding
    _first_claim = bindings.first_claim
    _mapping = bindings.mapping
    _pdd_report = bindings.pdd_report
    _rel = bindings.rel
    _strategic_surface_terms = bindings.strategic_surface_terms
    _wave33_fail_closed_summary = bindings.wave33_fail_closed_summary
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
            "evidence_refs": [_rel(wave33_dir / "policy_grounding_matrix.json", repo_root)],
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
            phase=phase34_2,
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
            downstream_impact=("Generic monitoring cannot prove PDD-098 strategic-risk coverage."),
            refs=[_rel(wave33_dir / "policy_grounding_matrix.json", repo_root)],
            phase=phase34_2,
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
            phase=phase34_2,
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
                "withdrawal_reissue_triggers": claim.get("withdrawal_reissue_triggers") or [],
            },
            "fail_closed_baseline": fail_closed,
        },
        observed=observed,
        phase=phase34_2,
        verdict="strategic_behavior_binding_missing; closeout_failure_is_indirect",
    )
