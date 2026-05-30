# ruff: noqa: S101

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from polisyos.scholar_requirement import (
    ScholarClaimRequirementSeed,
    ScholarSupportRequirementCompiler,
    ScholarSupportRequirementSpec,
    build_scholar_capability_requirement_bindings,
    scholar_support_requirement_audit_surface,
    write_scholar_support_requirement_result,
)


def test_compiler_emits_serious_claim_support_requirement_spec() -> None:
    compiler = ScholarSupportRequirementCompiler()

    result = compiler.compile(
        {
            "run_id": "run.scholar.w7d",
            "authority_level": "production",
            "claims": [
                {
                    "claim_id": "claim.causal.1",
                    "claim_text": "Credit guarantees improve MSME survival.",
                    "claim_type": "causal",
                    "claim_family": "causal",
                    "claim_use": "decision_support",
                    "obligation_refs": ["obligation.academic_support"],
                    "concept_spine_refs": ["concept.msme_survival"],
                }
            ],
        }
    )

    spec = result.requirements[0]

    assert result.capability_reality_label == "implemented"
    assert spec.requirement_id == "scholar-support:run.scholar.w7d:claim.causal.1"
    assert spec.required_publication_tier == "peer_reviewed"
    assert spec.recency_days == 730
    assert spec.required_replication_count == 2
    assert spec.required_independence_breadth == 2
    assert spec.required_citation_network_depth == 2
    assert spec.participation_like_claim is False
    assert spec.participation_claim_use_allowed == "academic_support"
    assert {rule.collapse_on for rule in spec.dependent_corpus_collapse_rules} >= {
        "underlying_study_id",
        "dataset_id",
        "author_pool",
        "institution_pool",
        "citation_network",
        "replication_lineage",
    }


def test_compiler_downgrades_participation_like_publication_authority() -> None:
    compiler = ScholarSupportRequirementCompiler()

    result = compiler.compile(
        {
            "run_id": "run.scholar.participation",
            "authority_level": "production",
            "claims": [
                {
                    "claim_id": "claim.preference.1",
                    "claim_text": "Affected MSMEs prefer credit guarantees.",
                    "claim_type": "factual",
                    "claim_family": "preference",
                    "claim_use": "prevalence",
                    "population_scope": "affected_population",
                }
            ],
        }
    )

    spec = result.requirements[0]

    assert spec.participation_like_claim is True
    assert spec.required_publication_tier == "grey_literature"
    assert spec.participation_claim_use_requested == "prevalence"
    assert spec.participation_claim_use_allowed == "context-only"
    assert spec.authority_boundary == "academic_publication_not_participation_provenance"
    assert "FT-ADR-02" in spec.decision_refs
    assert "P14" in spec.pattern_guards


def test_spec_is_strict_and_requires_nontrivial_collapse_rules() -> None:
    with pytest.raises(ValidationError):
        ScholarClaimRequirementSeed(
            claim_id="claim.extra",
            claim_text="A claim.",
            unexpected="not allowed",
        )

    with pytest.raises(ValidationError):
        ScholarSupportRequirementSpec(
            requirement_id="scholar-support:bad",
            claim_id="claim.bad",
            claim_text="Bad spec.",
            required_publication_tier="peer_reviewed",
            recency_days=365,
            required_replication_count=2,
            required_independence_breadth=2,
            required_citation_network_depth=1,
            dependent_corpus_collapse_rules=[],
        )


def test_scholar_requirement_result_is_persisted_for_adapter_replay(tmp_path) -> None:
    result = ScholarSupportRequirementCompiler().compile(
        {
            "run_id": "run.scholar.w7d",
            "authority_level": "production",
            "claims": [
                {
                    "claim_id": "claim.causal.1",
                    "claim_text": "Credit guarantees improve MSME survival.",
                    "claim_type": "causal",
                    "claim_family": "causal",
                    "claim_use": "decision_support",
                }
            ],
        }
    )

    path = write_scholar_support_requirement_result(result, tmp_path)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    surface = scholar_support_requirement_audit_surface(result)

    assert path.name == "run.scholar.w7d-scholar-support-requirements.json"
    assert persisted["schema_version"] == "policyos.scholar.support_requirement_result.v1"
    assert persisted["runtime_event_ref"] == "event://scholar-requirement/run.scholar.w7d"
    assert surface["surface"] == "scholar_requirement.audit_surface"
    assert surface["summary"]["requirement_count"] == 1
    assert surface["authority_boundary"]["authoritative_for"] == [
        "scholar_support_requirements",
        "scholar_independence_preconditions",
        "scholar_participation_firewall",
    ]


def test_scholar_consumes_construct_linked_skg_capabilities_and_degrades_low_transport() -> None:
    spec = ScholarSupportRequirementCompiler().compile(
        {
            "run_id": "run.scholar.phase5",
            "authority_level": "production",
            "claims": [
                {
                    "claim_id": "claim.firm_survival",
                    "claim_text": "Credit access improves firm survival.",
                    "claim_type": "causal",
                    "claim_family": "causal",
                    "claim_use": "decision_support",
                    "concept_spine_refs": ["concept:firm_survival"],
                }
            ],
        }
    ).requirements[0]

    report = build_scholar_capability_requirement_bindings(
        scholar_support_requirement_specs=[spec],
        capability_bindings=[
            {
                "requirement_id": spec.requirement_id,
                "status": "selected_context_only",
                "selected_capability_ref": "capability:scholar_firm_survival_edges",
                "construct_ref": "construct:firm_survival",
                "capability_index_ref": "capability-index:phase5",
                "construct_registry_ref": "construct-registry:v1",
                "authority_composition_rule_ref": "capability-authority-v1.0",
                "modality": ["scholar_claim"],
                "evidence_mode": "scholarly_causal_support",
                "metadata": {
                    "ac_skg_edge_refs": ["ac_skg_edges:credit_access__firm_survival"],
                    "ac_skg_transport_score_refs": [
                        "ac_skg_transport_scores:ua_wartime_msme"
                    ],
                    "transport_score": 0.42,
                    "ac_skg_contested_edge_refs": [
                        "ac_skg_contested_edges:credit_access__firm_survival"
                    ],
                    "ac_parameter_estimate_refs": [
                        "ac_parameter_estimates:credit_survival_hazard_ratio"
                    ],
                    "ac_boundary_condition_refs": [
                        "ac_boundary_conditions:registered_firms_only"
                    ],
                },
            }
        ],
    )

    link = report["support_links"][0]
    blocker = report["literature_deficit_blockers"][0]

    assert report["status"] == "blocked"
    assert link["capability_ref"] == "capability:scholar_firm_survival_edges"
    assert link["construct_ref"] == "construct:firm_survival"
    assert link["ac_skg_edge_refs"] == ["ac_skg_edges:credit_access__firm_survival"]
    assert link["ac_skg_transport_score_refs"] == [
        "ac_skg_transport_scores:ua_wartime_msme"
    ]
    assert link["transport_score"] == 0.42
    assert link["authority_degradation_reason"] == "transport_score_below_0_5"
    assert blocker["code"] == "scholar_capability_transport_below_floor"
    assert blocker["capability_ref"] == "capability:scholar_firm_survival_edges"
