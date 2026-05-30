from __future__ import annotations

from polisyos.scholar import build_scholar_spine_evidence_binding


def test_scholar_spine_binding_consumes_neutral_producer_spine_context() -> None:
    binding = build_scholar_spine_evidence_binding(
        literature_refs=["paper:credit-survival"],
        spine_context={
            "schema_version": "policyos.producer_spine_context.v1",
            "context_id": "ctx-ua-msme",
            "concept_spine_ref": "concept-spine:release",
            "jurisdiction_spine_ref": "jurisdiction-spine:release",
            "canonical_concept_refs": ["concept:firm_survival"],
            "jurisdiction_refs": ["jurisdiction:UA"],
            "consumer_components": [
                "lex",
                "fabric",
                "scholar",
                "foundry",
                "scientist",
                "final_compiler",
            ],
        },
        requirement_specs=[
            {
                "requirement_id": "scholar:req:firm-survival",
                "claim_id": "claim:ua-msme-survival",
                "claim_text": "Credit access improves firm survival.",
                "claim_type": "causal",
                "claim_use": "scholarly_support",
                "authority_level": "governed_pilot",
                "required_publication_tier": "peer_reviewed",
                "recency_days": 1095,
                "required_replication_count": 2,
                "required_independence_breadth": 2,
                "required_citation_network_depth": 1,
                "dependent_corpus_collapse_rules": [
                    {"rule_id": "collapse-shared-dataset", "collapse_on": "dataset_id"}
                ],
                "concept_spine_refs": ["construct:firm_survival"],
            }
        ],
    )

    assert binding["schema_version"] == "policyos.scholar.spine_evidence_binding.v1"
    assert binding["requirement_refs"] == ["scholar:req:firm-survival"]
    assert binding["consumed_concept_spine_ref"] == "concept-spine:release"
    assert binding["canonical_concept_refs"] == ("concept:firm_survival",)
    assert len(binding["candidate_spine_binding_refs"]) == 1
    assert binding["candidate_spine_binding_refs"][0].startswith(
        "spine-binding:scholar:concept:firm_survival:jurisdiction:UA:"
    )
