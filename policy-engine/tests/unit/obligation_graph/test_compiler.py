# ruff: noqa: S101
"""Semantic tests for the W6.C obligation graph compiler."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from polisyos.core.contracts.runtime import UniversalAuthorityProfile
from polisyos.ir.governance.problem_frame import ProblemDomain
from polisyos.obligation_graph import (
    ComplexityBudget,
    FacetSnapshot,
    GovernedObligationRule,
    ObligationCandidateInput,
    ObligationGraphCompileError,
    PriorityClass,
    SourceClass,
    compile_obligation_graph,
    obligation_graph_audit_surface,
    write_obligation_graph_artifact,
)
from polisyos.obligation_rules import build_seed_obligation_rule_catalog
from polisyos.policy_grammar import (
    PolicyGrammarCompiler,
    PolicyGrammarConceptSpineRefs,
    PolicyGrammarIntent,
    facet_snapshots_for_obligation_graph,
)

if TYPE_CHECKING:
    from pathlib import Path

NOW = datetime(2026, 5, 23, 12, 0, tzinfo=UTC)


def _facet() -> FacetSnapshot:
    return FacetSnapshot(
        facet_id="facet:housing-subsidy",
        facet_type="instrument_type",
        value="housing_subsidy",
        concept_ref="concept://policy/housing-subsidy",
        scope="kyiv:housing",
        authority_profile="municipal_serious_policy",
        temporal_window="2026-Q2",
    )


def _candidate(
    candidate_id: str,
    *,
    family: str = "data",
    source_class: SourceClass = SourceClass.PRODUCER_BLOCKER,
    remedy_path: str = "source_freshness",
    priority_hint: PriorityClass | None = None,
    marginal_assurance_value: float = 5.0,
    expected_cost: float = 1.0,
    reviewer_burden_minutes: float = 5.0,
    authority_allowance_passed: bool = True,
    admissibility_passed: bool = True,
    current_run_relevance_passed: bool = True,
    material_public_risk_passed: bool = True,
    source_ref: str | None = None,
    lineage_refs: tuple[str, ...] = (),
    competence_ref: str | None = None,
    time_scope_ref: str | None = None,
) -> ObligationCandidateInput:
    return ObligationCandidateInput(
        candidate_id=candidate_id,
        family=family,
        obligation_text=f"Resolve {family} obligation {candidate_id}",
        source_class=source_class,
        source_ref=source_ref or f"source://{candidate_id}",
        owner="team-runtime-quality",
        scope="kyiv:housing",
        authority_profile="municipal_serious_policy",
        temporal_window="2026-Q2",
        remedy_path=remedy_path,
        priority_hint=priority_hint,
        authority_allowance_passed=authority_allowance_passed,
        admissibility_passed=admissibility_passed,
        current_run_relevance_passed=current_run_relevance_passed,
        material_public_risk_passed=material_public_risk_passed,
        marginal_assurance_value=marginal_assurance_value,
        expected_cost=expected_cost,
        degradation_risk=0.0,
        reviewer_burden_minutes=reviewer_burden_minutes,
        complexity_cost=1.0,
        lineage_refs=lineage_refs,
        deadline_at=NOW + timedelta(days=2),
        escalation_owner="team-policyos-runtime",
        competence_ref=competence_ref,
        time_scope_ref=time_scope_ref,
    )


def test_llm_burst_stays_candidate_only_and_collapses_to_one_visible_bundle() -> None:
    llm_candidates = tuple(
        _candidate(
            f"llm-freshness-{index}",
            source_class=SourceClass.LLM_CANDIDATE,
            source_ref=f"prompt://llm-burst/{index}",
            lineage_refs=(f"prompt://shared/{index % 3}",),
            marginal_assurance_value=50.0,
        )
        for index in range(120)
    )

    graph = compile_obligation_graph(
        run_id="run-llm-burst",
        facets=(_facet(),),
        candidate_sources=llm_candidates,
        complexity_budget=ComplexityBudget(max_frontier_items=5),
        generated_at=NOW,
    )

    assert len(graph.candidate_ledger) == 120
    assert len(graph.bundle_ledger) == 1
    assert graph.bundle_ledger[0].child_count == 120
    assert graph.bundle_ledger[0].active is True
    assert SourceClass.LLM_CANDIDATE in graph.bundle_ledger[0].source_classes
    assert graph.blocking_frontier == ()
    assert graph.deferred_or_rejected[0].reason == "source_ceiling_candidate_not_blocking"
    assert graph.deferred_or_rejected[0].owner == "team-runtime-quality"
    assert graph.deferred_or_rejected[0].reopen_trigger
    assert graph.telemetry["silent_drop_rate"] == 0.0
    assert graph.telemetry["llm_authority_leakage_rate"] == 0.0


def test_frontier_promotes_lexicographic_winners_and_keeps_budget_deferrals_visible() -> None:
    rule = GovernedObligationRule(
        rule_id="rule:legal-competence",
        rule_family="legal",
        rule_version="2026.05",
        logic_hash="sha256:legal-competence",
        owner="team-lex",
        scope="kyiv:housing",
        authority_level="municipal_serious_policy",
        evidence_basis="ADR-0168 plus municipal competence register",
        status="governed",
        public_revalidation_effect="revalidate_affected_scope",
        obligation_text="Prove municipal legal competence before recommendation.",
        authority_profile="municipal_serious_policy",
        temporal_window="2026-Q2",
        remedy_path="legal_competence",
        required_facets={"instrument_type": "housing_subsidy"},
        priority_ceiling=PriorityClass.AUTHORITY_LEVEL_MANDATORY,
        marginal_assurance_value=10.0,
    )
    producer_blocker = _candidate(
        "producer:blocker:freshness",
        priority_hint=PriorityClass.MANDATORY,
        marginal_assurance_value=8.0,
        lineage_refs=("fabric://source-contract/a", "fabric://source-contract/a"),
    )
    duplicate_critic = _candidate(
        "critic:duplicate:freshness",
        source_class=SourceClass.DETERMINISTIC_CRITIC,
        priority_hint=PriorityClass.CONDITIONAL,
        marginal_assurance_value=25.0,
        lineage_refs=("critic://freshness",),
    )
    conditional = _candidate(
        "critic:implementation-risk",
        family="implementation",
        source_class=SourceClass.DETERMINISTIC_CRITIC,
        remedy_path="implementation_monitoring",
        priority_hint=PriorityClass.CONDITIONAL,
        marginal_assurance_value=100.0,
        expected_cost=0.1,
        reviewer_burden_minutes=1.0,
    )
    inadmissible = _candidate(
        "producer:privacy-blocker",
        family="privacy",
        remedy_path="privacy_remediation",
        priority_hint=PriorityClass.MANDATORY,
        admissibility_passed=False,
        marginal_assurance_value=1_000.0,
    )

    graph = compile_obligation_graph(
        run_id="run-budget",
        facets=(_facet(),),
        governed_rules=(rule,),
        candidate_sources=(producer_blocker, duplicate_critic, conditional, inadmissible),
        complexity_budget=ComplexityBudget(max_frontier_items=2),
        generated_at=NOW,
    )

    assert [item.priority_class for item in graph.blocking_frontier] == [
        PriorityClass.AUTHORITY_LEVEL_MANDATORY,
        PriorityClass.MANDATORY,
    ]
    assert len(graph.blocking_frontier) == 2
    freshness_bundle = next(
        bundle for bundle in graph.bundle_ledger if bundle.remedy_path == "source_freshness"
    )
    assert freshness_bundle.child_count == 2
    assert freshness_bundle.canonical_priority == PriorityClass.MANDATORY
    assert freshness_bundle.lineage_refs == (
        "critic://freshness",
        "fabric://source-contract/a",
    )
    assert any(
        record.reason == "complexity_budget_exceeded"
        and record.bundle_key.family == "implementation"
        and record.owner == "team-runtime-quality"
        for record in graph.deferred_or_rejected
    )
    assert any(
        record.reason == "legal_privacy_admissibility_failed"
        and record.bundle_key.family == "privacy"
        for record in graph.deferred_or_rejected
    )


def test_compile_requires_derived_facets_before_graph_construction() -> None:
    with pytest.raises(ObligationGraphCompileError, match="facet_derivation_missing"):
        compile_obligation_graph(
            run_id="run-no-facets",
            facets=(),
            candidate_sources=(_candidate("candidate"),),
            generated_at=NOW,
        )


def test_structured_facet_pattern_rules_promote_vertical_metadata_to_frontier() -> None:
    rule = {
        "rule_id": "obligation.data.vertical_msme_additionality",
        "rule_family": "data",
        "rule_version": "2026.05.0",
        "logic_hash": "sha256:" + "1" * 64,
        "owner": "team-data-forge",
        "scope": {
            "jurisdictions": ["UA"],
            "policy_domains": ["msme_credit_grant"],
            "authority_profiles": ["governed"],
            "temporal_window": "case_lifecycle",
        },
        "authority_level": "governed",
        "evidence_basis": [
            "tests/fixtures/universal-corpus/cases/ua-msme-affordable-loans-2022.json"
        ],
        "status": "governed",
        "public_revalidation_effect": "review_open_cases",
        "source_refs": ["tests/fixtures/universal-corpus/cases/ua-msme-affordable-loans-2022.json"],
        "logic": {
            "predicate": "ua_msme_credit_additionality_vertical_rule",
            "facet_match_all": [
                {"facet_type": "instrument_type", "value_eq": "credit"},
                {"facet_type": "population_predicate", "value_eq": "msmes"},
            ],
            "claim_text_contains_any": ["wartime MSME credit"],
            "evidence_family": "program_evaluation_or_counterfactual_credit_additionality",
            "data_family": "program_evaluation_or_counterfactual_credit_additionality",
            "vertical_rule": True,
        },
    }

    graph = compile_obligation_graph(
        run_id="run-vertical-rule",
        facets=(
            _facet().model_copy(update={"facet_type": "instrument_type", "value": "credit"}),
            _facet().model_copy(update={"facet_type": "population_predicate", "value": "msmes"}),
        ),
        governed_rules=(rule,),
        generated_at=NOW,
        intent_text="Ukraine wartime MSME credit support",
    )

    assert len(graph.blocking_frontier) == 1
    item = graph.blocking_frontier[0]
    assert item.bundle_key.remedy_path == (
        "program_evaluation_or_counterfactual_credit_additionality"
    )
    assert item.metadata["vertical_rule"] is True
    assert item.metadata["data_family"] == (
        "program_evaluation_or_counterfactual_credit_additionality"
    )


def test_structured_facet_pattern_rule_does_not_match_without_claim_text_fallback() -> None:
    rule = {
        "rule_id": "obligation.implementation.room_for_river_monitoring",
        "rule_family": "implementation",
        "rule_version": "2026.05.0",
        "logic_hash": "sha256:" + "2" * 64,
        "owner": "team-runtime-quality",
        "scope": {
            "jurisdictions": ["NL"],
            "policy_domains": ["climate_adaptation"],
            "authority_profiles": ["research"],
            "temporal_window": "case_lifecycle",
        },
        "authority_level": "research",
        "evidence_basis": [
            "tests/fixtures/universal-corpus/cases/w11a_netherlands_room_for_river_2007.json"
        ],
        "status": "governed",
        "public_revalidation_effect": "review_open_cases",
        "source_refs": [
            "tests/fixtures/universal-corpus/cases/w11a_netherlands_room_for_river_2007.json"
        ],
        "logic": {
            "predicate": "room_for_river_scenario_monitoring_vertical_rule",
            "facet_match_all": [
                {"facet_type": "instrument_type", "value_eq": "procurement"},
                {"facet_type": "geography_predicate", "value_eq": "state_or_region"},
            ],
            "claim_text_contains_any": ["room for river", "flood risk"],
            "evidence_family": "hydrological_modeling_and_lifecycle_monitoring",
            "vertical_rule": True,
        },
    }

    graph = compile_obligation_graph(
        run_id="run-nonmatching-vertical-rule",
        facets=(
            _facet().model_copy(update={"facet_type": "instrument_type", "value": "procurement"}),
            _facet().model_copy(
                update={"facet_type": "geography_predicate", "value": "state_or_region"}
            ),
        ),
        governed_rules=(rule,),
        generated_at=NOW,
        intent_text="UK levelling up competitive capital grant fund",
    )

    assert graph.blocking_frontier == ()


def test_llm_critic_consensus_enters_frontier_at_review_required_ceiling() -> None:
    graph = compile_obligation_graph(
        run_id="run-consensus",
        facets=(_facet(),),
        candidate_sources=(
            _candidate(
                "llm-consensus:obligation",
                source_class=SourceClass.LLM_CRITIC_CONSENSUS,
                priority_hint=PriorityClass.MANDATORY,
                source_ref="critic-consensus://candidate/1",
            ),
        ),
        generated_at=NOW,
    )

    assert graph.blocking_frontier[0].priority_class == PriorityClass.REVIEW_REQUIRED
    assert graph.candidate_ledger[0].ceiling_reason == (
        "llm_critic_consensus_review_required_ceiling"
    )


def test_compiler_consumes_policy_grammar_case_and_governed_rule_catalog() -> None:
    case = PolicyGrammarCompiler().compile(
        intent=PolicyGrammarIntent(
            intent_id="intent-msme-credit",
            text=(
                "Create a concessional credit guarantee programme for displaced MSMEs "
                "in northern regions in 2026, funded by budget appropriation and "
                "delivered through partner banks to preserve employment."
            ),
            domain=ProblemDomain.FISCAL,
        ),
        authority_profile=UniversalAuthorityProfile(
            profile_id="authority_profile.municipal_governed",
            authority_type="local",
        ),
        concept_spine_refs=PolicyGrammarConceptSpineRefs(
            concept_spine_ref="concept-spine://w6/msme-credit",
            jurisdiction_spine_ref="jurisdiction-spine://municipal",
            canonical_concept_refs=("concept://policy/msme-credit",),
        ),
    )
    catalog = build_seed_obligation_rule_catalog()

    graph = compile_obligation_graph(
        run_id="run-msme-credit",
        facets=facet_snapshots_for_obligation_graph(case),
        governed_rules=catalog.rules,
        generated_at=NOW,
        complexity_budget=ComplexityBudget(max_frontier_items=8),
    )

    assert graph.candidate_ledger
    assert graph.bundle_ledger
    assert graph.blocking_frontier
    assert {entry.source_class for entry in graph.candidate_ledger} == {
        SourceClass.GOVERNED_RULE
    }
    assert all(
        item.source_classes == (SourceClass.GOVERNED_RULE,)
        for item in graph.blocking_frontier
    )


def test_legal_requirement_needs_competence_time_scope_proof_for_authority_promotion() -> None:
    unproved = _candidate(
        "legal:unproved",
        family="legal",
        source_class=SourceClass.LEGAL_REQUIREMENT,
        remedy_path="legal_competence",
        priority_hint=PriorityClass.AUTHORITY_LEVEL_MANDATORY,
    )

    graph = compile_obligation_graph(
        run_id="run-legal-unproved",
        facets=(_facet(),),
        candidate_sources=(unproved,),
        generated_at=NOW,
    )

    assert graph.blocking_frontier == ()
    assert graph.deferred_or_rejected[0].reason == "legal_requirement_proof_missing"
    assert graph.bundle_ledger[0].canonical_priority == PriorityClass.REVIEW_REQUIRED

    proved = _candidate(
        "legal:proved",
        family="legal",
        source_class=SourceClass.LEGAL_REQUIREMENT,
        remedy_path="legal_competence",
        priority_hint=PriorityClass.AUTHORITY_LEVEL_MANDATORY,
        competence_ref="lex://competence/kyiv-housing",
        time_scope_ref="time://competence-window/2026-Q2",
    )

    proved_graph = compile_obligation_graph(
        run_id="run-legal-proved",
        facets=(_facet(),),
        candidate_sources=(proved,),
        generated_at=NOW,
    )

    assert [item.priority_class for item in proved_graph.blocking_frontier] == [
        PriorityClass.AUTHORITY_LEVEL_MANDATORY
    ]


def test_artifact_writer_and_audit_surface_preserve_visibility_paths(tmp_path: Path) -> None:
    graph = compile_obligation_graph(
        run_id="run-artifact",
        facets=(_facet(),),
        candidate_sources=(
            _candidate("producer:blocker", priority_hint=PriorityClass.MANDATORY),
            _candidate(
                "llm:candidate",
                source_class=SourceClass.LLM_CANDIDATE,
                remedy_path="candidate_noise",
            ),
        ),
        generated_at=NOW,
    )

    artifact_path = write_obligation_graph_artifact(graph, tmp_path)
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    audit_surface = obligation_graph_audit_surface(graph)

    assert payload["schema_version"] == "policyos.obligation_graph.v1"
    assert payload["run_id"] == "run-artifact"
    assert audit_surface["candidate_ledger"][1]["source_class"] == "llm_candidate"
    assert audit_surface["deferred_or_rejected"][0]["reason"] == (
        "source_ceiling_candidate_not_blocking"
    )
    assert "domain_evidence" in audit_surface["authority_boundary"]["may_not_use_for"]
