from __future__ import annotations

# ruff: noqa: S101
from polisyos.data_requirement import (
    DataQualityMinimums,
    DataRequirementScope,
    DataRequirementSpec,
)
from polisyos.legal_requirement import LegalAuthorityRequirementSpec
from polisyos.method_requirement import MethodValidityRequirementSpec
from polisyos.participation_requirement import (
    ParticipationAuthorityLevel,
    ParticipationClaimPurpose,
    ParticipationClaimUse,
    ParticipationPopulationScope,
    ParticipationProvenanceClass,
    ParticipationProvenanceRecord,
    ParticipationProvenanceRequirementSpec,
    ParticipationRepresentativenessClass,
    ParticipationSourceKind,
)
from polisyos.runtime.quality.producer_pipeline import (
    run_requirement_spec_producer_pipeline,
)
from polisyos.scholar_requirement import ScholarSupportRequirementSpec


def test_requirement_spec_pipeline_runs_real_w7_adapters_and_acquisition_bridge() -> None:
    report = run_requirement_spec_producer_pipeline(
        run_id="run-wave7-real-adapters",
        job_id="job-wave7-real-adapters",
        tenant_id="tenant-wave7",
        request_ref="request:wave7:msme",
        authority_profile="production",
        spine_context={
            "concept_spine_ref": "concept-spine:wave7",
            "jurisdiction_spine_ref": "jurisdiction-spine:ua",
            "canonical_concept_refs": ["concept:msme-survival"],
        },
        claims=[
            {
                "claim_id": "claim-msme-effect",
                "facet_refs": ["facet-msme"],
                "baseline_refs": ["baseline:status-quo"],
                "alternative_refs": ["alternative:credit-guarantee"],
                "portfolio_refs": ["portfolio:wave7"],
                "effective_independence_refs": ["independence:wave7"],
                "argument_refs": ["argument:wave7"],
            }
        ],
        universal_grammar_compilation={"status": "pass", "ref": "grammar:wave7"},
        obligation_graph={"status": "pass", "graph_ref": "obligation-graph:wave7"},
        claim_decomposition={"status": "pass", "ref": "claim-ledger:wave7"},
        data_requirement_specs=[_data_spec()],
        source_contract_candidates=[_source_contract_candidate()],
        legal_authority_requirement_specs=[_legal_spec()],
        candidate_norms=[_legal_norm()],
        method_validity_requirement_specs=[_method_spec()],
        candidate_methods=[_method_candidate()],
        scholar_support_requirement_specs=[_scholar_spec()],
        scholar_evidence_bundle=_scholar_bundle(),
        participation_provenance_requirement_specs=[_participation_spec()],
        participation_records=[_participation_record()],
    )

    assert report["status"] == "pass"
    assert report["capability_reality_label"] == "implemented"
    assert report["producer_state_summary"]["final_states"] == {
        "fabric": "emitted_binding",
        "foundry": "emitted_binding",
        "lex": "emitted_binding",
        "participation": "emitted_binding",
        "scholar": "emitted_binding",
    }
    assert report["compiled_requirement_interfaces"]["fabric"]["summary"]["selected"] == 1
    assert report["compiled_requirement_interfaces"]["lex"]["summary"]["selected"] >= 1
    foundry_summary = report["compiled_requirement_interfaces"]["foundry"]["summary"]
    assert foundry_summary["selected_method_count"] == 1
    assert report["compiled_requirement_interfaces"]["scholar"]["status"] == "pass"
    assert report["compiled_requirement_interfaces"]["participation"]["summary"]["satisfied"] == 1
    assert report["acquisition_planner"]["summary"]["record_count"] == 5
    assert {
        record["requirement_family"]
        for record in report["acquisition_planner"]["acquisition_records"]
    } == {
        "data_requirement",
        "legal_authority_requirement",
        "method_validity_requirement",
        "scholar_support_requirement",
        "participation_provenance_requirement",
    }


def _data_spec() -> DataRequirementSpec:
    return DataRequirementSpec(
        requirement_id="data-requirement:claim-msme-effect",
        claim_id="claim-msme-effect",
        required_data_families=("production_msme_panel",),
        scope=DataRequirementScope(
            population="msmes",
            geography="state_or_region",
            time="annual",
            time_role="observation_time",
        ),
        recency_horizon="P90D",
        lineage_strictness="strict",
        quality_minima=DataQualityMinimums(min_quality_score=0.8, min_completeness=0.95),
        missingness_tolerance=0.02,
        transformation_tolerance="none",
        admissibility_predicates=("source_family_matches_compiled_requirement",),
        mandatory_facets=("source_contract_ref", "lineage_refs"),
        facet_refs=("facet-msme",),
        concept_spine_refs=("concept:msme-survival",),
        authority_profile_refs=("authority_profile.production",),
    )


def _source_contract_candidate() -> dict[str, object]:
    return {
        "candidate_ref": "source-contract:production-msme-panel",
        "source_family": "production_msme_panel",
        "present_facets": ["source_contract_ref", "lineage_refs"],
        "source_contract_validation": {"status": "pass"},
    }


def _legal_spec() -> LegalAuthorityRequirementSpec:
    return LegalAuthorityRequirementSpec.model_validate(
        {
            "requirement_id": "legal-requirement:claim-msme-effect",
            "claim_ref": "claim:claim-msme-effect",
            "claim_id": "claim-msme-effect",
            "mandatory": True,
            "required_hierarchy_depth": 2,
            "temporal_competence_window": {
                "start": "2026-01-01",
                "end": "2026-12-31",
                "time_role": "implementation_period",
            },
            "authority_types": ["implementing"],
            "required_instrument_classes": ["credit_guarantee"],
            "required_actor_refs": ["kyiv_city_council"],
            "implementation_authority_required": True,
            "jurisdiction": "UA-30-KYIV",
            "authority_profile_ref": "production",
        }
    )


def _legal_norm() -> dict[str, object]:
    return {
        "norm_id": "norm.ua.local_credit",
        "norm_version_ref": "norm.ua.local_credit@2026-01-01",
        "source_provenance_ref": "lex-corpus:ua-local-credit",
        "jurisdiction": "UA-30-KYIV",
        "policy_domain": "wartime_msme_support",
        "effective_from": "2025-01-01",
        "source_authority": "Kyiv City Council",
        "authority_level": "local",
        "hierarchy_depth": 2,
        "authority_basis": "statutory_delegation",
        "authority_types": ["implementing"],
        "competent_actor_ref": "kyiv_city_council",
        "instrument_types": ["credit_guarantee"],
        "implementation_authority_ref": "kyiv_city_program_office",
        "hierarchy_position": "local",
        "legal_as_of": "2026-05-23",
        "legal_effective_window": {"start": "2025-01-01", "end": None},
        "rule_version_ref": "lex-legal-authority:v2",
        "provenance_kind": "deterministic_producer",
    }


def _method_spec() -> MethodValidityRequirementSpec:
    return MethodValidityRequirementSpec(
        requirement_id="method-requirement:claim-msme-effect",
        run_id="run-wave7-real-adapters",
        claim_id="claim-msme-effect",
        identification_class="point",
        method_expectations=["causal_effect_estimation"],
        required_method_families=["causal_effect_estimation"],
        transportability_requirement="target_population_limits",
        uncertainty_class="interval",
        assumption_validation_needs=[
            {"assumption_id": "parallel_trends"},
            {"assumption_id": "overlap_or_support"},
        ],
    )


def _method_candidate() -> dict[str, object]:
    return {
        "method_id": "causal.did.runtime",
        "method_family": "causal_effect_estimation",
        "method_expectations": ["causal_effect_estimation"],
        "truthfulness_status": "runtime_consistent",
        "runtime_assumption_gates": [
            {
                "gate_ref": "gate://parallel-trends",
                "assumption": "parallel_trends",
                "status": "pass",
            },
            {"gate_ref": "gate://overlap", "assumption": "overlap_or_support", "status": "pass"},
        ],
        "uncertainty_refs": {"uncertainty_envelope_ref": "sha256:" + "6" * 64},
        "limitation_refs": {"method_limitation_ref": "sha256:" + "5" * 64},
        "method_result_refs": {"method_result_ref": "sha256:" + "4" * 64},
    }


def _scholar_spec() -> ScholarSupportRequirementSpec:
    return ScholarSupportRequirementSpec(
        requirement_id="scholar-support:claim-msme-effect",
        claim_id="claim-msme-effect",
        claim_text="Credit guarantees improve MSME survival.",
        claim_type="causal",
        authority_level="production",
        required_publication_tier="peer_reviewed",
        recency_days=730,
        required_replication_count=1,
        required_independence_breadth=1,
        required_citation_network_depth=0,
        dependent_corpus_collapse_rules=[
            {"rule_id": "collapse-study", "collapse_on": "underlying_study_id"}
        ],
    )


def _scholar_bundle() -> dict[str, object]:
    return {
        "bundle_id": "bundle-wave7-scholar",
        "brief": {"question": "Do credit guarantees improve MSME survival?"},
        "query_graph": {
            "nodes": [
                {
                    "node_id": "q1",
                    "query": "credit guarantees MSME survival peer reviewed",
                    "perspective": "academic evidence",
                    "status": "searched",
                    "hit_count": 1,
                }
            ],
            "root_node_ids": ["q1"],
        },
        "query_traces": [{"query_node_id": "q1", "query": "credit guarantees", "hit_count": 1}],
        "sources": [
            {
                "source_id": "literature:journal-version",
                "url": "https://example.org/journal-version",
                "title": "Credit guarantees and MSME survival",
                "domain": "example.org",
                "source_type": "academic",
                "publication_tier": "peer_reviewed",
                "underlying_study_id": "credit-panel-2025",
                "provider": "fixture",
                "published_at": "2025-10-01T00:00:00+00:00",
                "page_age_days": 228,
                "content_sha256": "credit-panel-study",
                "quality_score": 0.9,
            }
        ],
        "snippets": [
            {
                "snippet_id": "snippet:journal-version:1",
                "source_id": "literature:journal-version",
                "url": "https://example.org/journal-version",
                "query_node_id": "q1",
                "perspective": "academic evidence",
                "text": "The journal article reports higher MSME survival.",
                "start_char": 0,
                "end_char": 50,
                "relevance_score": 0.9,
            }
        ],
        "claim_supports": [
            {
                "claim_id": "claim-msme-effect",
                "claim_text": "Credit guarantees improve MSME survival.",
                "snippet_ids": ["snippet:journal-version:1"],
                "source_ids": ["literature:journal-version"],
                "support_score": 0.8,
                "conflict_score": 0.0,
                "metadata": {"support_status": "supported"},
            }
        ],
    }


def _participation_spec() -> ParticipationProvenanceRequirementSpec:
    return ParticipationProvenanceRequirementSpec(
        requirement_id="participation-requirement:claim-msme-effect",
        run_id="run-wave7-real-adapters",
        claim_id="claim-msme-effect",
        claim_family="preference",
        claim_purpose=ParticipationClaimPurpose.PREFERENCE,
        claim_use_requested=ParticipationClaimUse.PREVALENCE,
        authority_level=ParticipationAuthorityLevel.PRODUCTION,
        population_scope=ParticipationPopulationScope.AFFECTED_POPULATION,
        required_modes=(ParticipationSourceKind.SURVEY,),
        required_sampling_frame="scope_matched_sampling_frame",
        minimum_provenance_class=ParticipationProvenanceClass.A_REPRESENTATIVE_POPULATION,
        minimum_representativeness_class=ParticipationRepresentativenessClass.REPRESENTATIVE,
        consent_redaction="redacted_microdata",
        dissent_handling="dissent_recorded",
        sponsor_disclosure="sponsor_disclosed",
    )


def _participation_record() -> ParticipationProvenanceRecord:
    return ParticipationProvenanceRecord(
        participation_ref="participation:survey:msme-owners",
        claim_refs=("claim-msme-effect",),
        source_kind=ParticipationSourceKind.SURVEY,
        provenance_class=ParticipationProvenanceClass.A_REPRESENTATIVE_POPULATION,
        representativeness_class=ParticipationRepresentativenessClass.REPRESENTATIVE,
        sampling_or_recruitment_frame="scope_matched_sampling_frame",
        affected_group_map={"groups": ["affected_msmes"]},
        consent_redaction_state="redacted_microdata",
        dissent_state="recorded",
        sponsor_disclosure="sponsor_disclosed",
        evidence_ref="sha256:" + "1" * 64,
    )
