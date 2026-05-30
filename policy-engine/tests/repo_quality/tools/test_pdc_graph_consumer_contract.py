from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime
from typing import Any

from polisyos.core.contracts.policy_design_case_projection import PolicyDesignCaseAudience
from polisyos.evidence.portfolio.effective_independence_graph import (
    build_effective_independence_graph,
)
from polisyos.foundry.welfare.frontier_emitter import (
    AlternativeOutcome,
    ObjectiveSpec,
    WelfareFrontierEmission,
    emit_welfare_frontier,
)
from polisyos.foundry.welfare.social_weight_provenance import (
    AffectedGroupWeight,
    SocialWeightMandate,
    SocialWeightProvenance,
    ValueChoiceActor,
)
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    CrossGraphEvidenceSummary,
    EvidenceNeed,
    EvidenceNeedAssessment,
    EvidenceNeedType,
    EvidenceStatus,
    LegalStatus,
    ObservabilityStatus,
)
from polisyos.runtime.quality.argument_graph import (
    build_argument_graph,
    export_argument_graph,
    inspect_argument_graph,
)
from polisyos.runtime.quality.producer_pipeline import run_requirement_spec_producer_pipeline
from polisyos.runtime.quality.projection_semantics import (
    build_policy_design_case_projection_from_runtime_graph,
    verify_policy_design_case_projection_consumer_contract,
)
from polisyos.scientist.cross_graph.conflict_materializer import (
    materialize_cross_graph_conflicts,
)
from polisyos.scientist.evidence.claims.models import ClaimLedger, ClaimUse
from polisyos.scientist.policy_design.baseline_compiler import BaselineComparisonCompiler
from tests.repo_quality.tools.test_compiled_pdc_graph_smoke import (
    INTENTS,
    _compile_w6_artifacts,
)

NOW = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)


def test_wave8_pdc_graph_consumer_contract_closes_runtime_bridges() -> None:
    for intent_id, text, domain in INTENTS:
        artifacts = _compile_w6_artifacts(intent_id=intent_id, text=text, domain=domain)
        report = run_requirement_spec_producer_pipeline(
            run_id=f"run-w8-contract-{intent_id}",
            job_id=f"job-w8-contract-{intent_id}",
            tenant_id="tenant-w8-contract",
            request_ref=f"request:{intent_id}",
            authority_profile="production",
            spine_context={
                "concept_spine_ref": f"concept-spine:{intent_id}",
                "jurisdiction_spine_ref": f"jurisdiction-spine:{intent_id}",
                "canonical_concept_refs": [f"concept:{intent_id}:policy"],
            },
            claims=artifacts["claims"],
            universal_grammar_compilation=artifacts["universal_grammar_compilation"],
            obligation_graph=artifacts["obligation_graph"],
            claim_decomposition=artifacts["claim_decomposition"],
            data_requirement_specs=artifacts["data_requirement_specs"],
            legal_authority_requirement_specs=artifacts["legal_authority_requirement_specs"],
            method_validity_requirement_specs=artifacts["method_validity_requirement_specs"],
            scholar_support_requirement_specs=artifacts["scholar_support_requirement_specs"],
            participation_provenance_requirement_specs=artifacts[
                "participation_provenance_requirement_specs"
            ],
        )
        graph = report["runtime_pdc_graph"]

        projection = build_policy_design_case_projection_from_runtime_graph(
            runtime_pdc_graph=graph,
            surface="machine_projection",
            audience=PolicyDesignCaseAudience.MACHINE,
            generated_at=NOW,
        )
        verification = verify_policy_design_case_projection_consumer_contract(
            projections={"machine": projection},
            expected_closeout_truth=projection["closeout_truth"],
            runtime_pdc_graph=graph,
        )
        assert verification["status"] == "pass"
        assert projection["projection_policy"] == "reads_runtime_policy_design_case_graph"

        argument_graph = build_argument_graph(graph, generated_at=NOW)
        assert argument_graph["summary"]["claim_count"] >= 1
        assert inspect_argument_graph(argument_graph)["summary"]["claim_path_count"] >= 1
        assert export_argument_graph(argument_graph)["standards"] == ["SACM", "CAE", "GSN"]

        comparison_ledger = _compile_one_superiority_comparison(
            artifacts["claim_ledger"],
            intent_id=intent_id,
        )
        assert comparison_ledger.comparison_records
        assert comparison_ledger.claims[0].comparison_refs

        welfare = _emit_fixture_welfare_frontier(
            claim_ref=f"claim:{comparison_ledger.claims[0].claim_id}",
            intent_id=intent_id,
        )
        assert welfare.frontier.frontier_alternative_ids
        assert welfare.value_choice.social_weight_provenance_id.startswith("swp-")

    conflict = materialize_cross_graph_conflicts(
        _conflicting_profile(),
        run_id="run-w8-contract-conflict",
        claim_id_by_need_id={"legal_applicability_need:contract": ["claim-conflict"]},
    )
    assert conflict.conflict_records
    assert conflict.claim_registry["claims"][0]["conflict_refs"] == [
        conflict.conflict_records[0]["conflict_id"]
    ]

    independence = build_effective_independence_graph(
        [
            _evidence_line("publication-a", study_id="study-duplicate"),
            _evidence_line("publication-b", study_id="study-duplicate"),
        ],
        portfolio_designs=[_portfolio_design()],
        graph_id="effective-independence-contract",
        producer_execution_started_at="2026-05-24T12:00:00+00:00",
    )
    assert independence["raw_evidence_line_count"] == 2
    assert independence["hard_effective_line_count"] == 1


def _compile_one_superiority_comparison(
    claim_ledger: ClaimLedger,
    *,
    intent_id: str,
) -> ClaimLedger:
    claim = claim_ledger.claims[0].model_copy(
        update={
            "claim_use": ClaimUse.SUPERIORITY,
            "baseline_refs": [record.baseline_id for record in claim_ledger.baseline_records],
            "alternative_refs": [
                record.alternative_id for record in claim_ledger.alternative_records
            ],
        }
    )
    ledger = claim_ledger.model_copy(update={"claims": [claim, *claim_ledger.claims[1:]]})
    superiority_claims = [
        row for row in ledger.claims if row.claim_use is ClaimUse.SUPERIORITY
    ]
    selected_option = claim.alternative_refs[0]
    return BaselineComparisonCompiler().compile(
        {
            "claim_ledger": ledger,
            "selected_option_ref": selected_option,
            "selected_option_label": f"Selected {intent_id} option",
            "selected_option_evidence_refs": {f"evidence:{intent_id}:selected"},
            "option_metric_values": {
                selected_option: {"coverage": 0.8, "cost": 0.4},
                claim.baseline_refs[0]: {"coverage": 0.5, "cost": 0.2},
            },
            "objective_directions": {"coverage": "maximize", "cost": "minimize"},
            "foundry_method_report": {
                "selected_methods": [
                    {
                        "claim_id": row.claim_id,
                        "method_id": f"method:{intent_id}:frontier",
                        "method_output_refs": [
                            f"method-output:{intent_id}:{row.claim_id}:frontier"
                        ],
                        "limitation_refs": [f"limitation:{intent_id}:frontier"],
                    }
                    for row in superiority_claims
                ],
            },
            "ir_analytics_bridge": {
                "claim_bindings": [
                    {
                        "claim_id": row.claim_id,
                        "ir_analytics_refs": [f"ir:{intent_id}:{row.claim_id}:comparison"],
                        "ir_certificate_refs": [
                            f"ir-cert:{intent_id}:{row.claim_id}:comparison"
                        ],
                    }
                    for row in superiority_claims
                ],
            },
        }
    )


def _emit_fixture_welfare_frontier(
    *,
    claim_ref: str,
    intent_id: str,
) -> WelfareFrontierEmission:
    provenance = SocialWeightProvenance(
        provenance_id=f"swp-{intent_id}",
        social_weight_ref=f"swr://policy.welfare/{intent_id}@1.0.0#abc",
        source_class="governance_decision",
        chosen_by=(
            ValueChoiceActor(
                actor_id="agency:policy-board",
                actor_role="public_authority",
                display_name="Policy board",
            ),
        ),
        mandate=SocialWeightMandate(
            mandate_ref=f"mandate://{intent_id}/2026",
            mandate_type="statutory",
            authority_scope="welfare tradeoff review",
        ),
        chosen_at=NOW,
        affected_groups=(AffectedGroupWeight(group_id="affected_population", weight=1.2),),
        sponsor_disclosure_status="none_disclosed",
        review_status="approved",
        review_refs=(f"review://{intent_id}/weights",),
        claim_refs=(claim_ref,),
    )
    return emit_welfare_frontier(
        claim_refs=(claim_ref,),
        objectives=(
            ObjectiveSpec(objective_id="coverage", label="Coverage", direction="maximize"),
            ObjectiveSpec(objective_id="cost", label="Cost", direction="minimize"),
        ),
        outcomes=(
            AlternativeOutcome(
                alternative_id=f"{intent_id}-selected",
                label="Selected option",
                objective_values={"coverage": 0.8, "cost": 0.4},
                claim_refs=(claim_ref,),
                welfare_bound_refs=(f"welfare-bound:{intent_id}:selected",),
                social_weight_ref=provenance.social_weight_ref,
            ),
            AlternativeOutcome(
                alternative_id=f"{intent_id}-alternative",
                label="Alternative option",
                objective_values={"coverage": 0.7, "cost": 0.2},
                claim_refs=(claim_ref,),
                welfare_bound_refs=(f"welfare-bound:{intent_id}:alternative",),
                social_weight_ref=provenance.social_weight_ref,
            ),
        ),
        social_weight_provenance=provenance,
        selected_alternative_id=f"{intent_id}-selected",
        generated_at=NOW,
    )


def _conflicting_profile() -> CrossGraphEvidenceProfile:
    need = EvidenceNeed(
        need_id="legal_applicability_need:contract",
        need_type=EvidenceNeedType.LEGAL_APPLICABILITY_NEED,
        source_path="policy_spec.interventions[0]",
    )
    assessment = EvidenceNeedAssessment(
        need=need,
        legal_status=LegalStatus.PROHIBITED,
        observability_status=ObservabilityStatus.DIRECT,
        evidence_status=EvidenceStatus.SUPPORTED,
        confidence=0.45,
        requires_expert_review=True,
        provenance_refs=["lex:blocker:contract", "scholar:study:contract"],
    )
    return CrossGraphEvidenceProfile(
        summary=CrossGraphEvidenceSummary(total_needs=1),
        needs=[assessment],
    )


def _portfolio_design() -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.evidence_portfolio_design.v1",
        "portfolio_id": "portfolio-contract",
        "claim_ids": ["claim-contract"],
        "predeclared": True,
        "declared_at": "2026-05-24T11:00:00+00:00",
        "declared_before_producer_execution": True,
        "authority_level": "production",
        "strands": [
            {
                "strand_id": "literature-strand",
                "claim_id": "claim-contract",
                "authority_level": "production",
                "candidate_data_source_families": ["academic_evidence"],
                "candidate_method_families": ["quasi_experimental_panel"],
                "defensible_specification_space": {"primary_estimand": "ATT"},
                "inclusion_rules": ["Include independent scholar publications."],
                "exclusion_rules": ["Exclude repeated reports of the same study."],
                "disconfirming_lines": [{"line_id": "counter-required", "required": True}],
                "synthesis_rules": {"strategy": "effective_independence"},
                "stopping_rules": {"minimum_effective_independent_evidence_count": 2},
                "cost_proportionality": {"budget_tier": "standard"},
            }
        ],
        "candidate_data_source_families": ["academic_evidence"],
        "candidate_method_families": ["quasi_experimental_panel"],
        "inclusion_rules": ["Prefer production-ready evidence lines."],
        "exclusion_rules": ["Reject raw-count inflation."],
        "disconfirming_lines": ["counter-required"],
        "synthesis_rules": {"strategy": "effective_independence"},
        "stopping_rules": {"minimum_effective_independent_evidence_count": 2},
        "cost_proportionality": {"budget_tier": "standard"},
    }


def _evidence_line(line_id: str, *, study_id: str) -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.evidence_line.v1",
        "line_id": line_id,
        "portfolio_id": "portfolio-contract",
        "portfolio_strand_id": "literature-strand",
        "claim_id": "claim-contract",
        "evidence_strand": "literature",
        "polarity": "support",
        "quality_score": 1.0,
        "source_refs": [f"source:{line_id}"],
        "primary_source": f"journal:{line_id}",
        "retrieval_path": f"scholar-search:{line_id}",
        "underlying_study_id": study_id,
        "legal_authority": ["research-use-permit-2026"],
        "author_ids": ["author:policy-eval-cell"],
        "institution_ids": ["policy-lab"],
        "sponsor_ids": ["public-interest-fund"],
        "dataset_id": "dataset-contract",
        "corpus_ancestry": ["dataset-contract"],
        "snapshot_id": "snapshot-contract",
        "subject_pool": "affected-population",
        "preprocessing_pipeline_id": "prep-contract",
        "transformation_lineage": ["transform:contract"],
        "method_id": f"foundry.did.{line_id}",
        "method_family": "difference_in_differences",
        "method_assumptions": ["parallel-trends"],
        "identification_strategy_id": "did-identification",
        "proof_reuse_status": "fresh_proof",
        "llm_generation_path": {
            "model": "none",
            "prompt_ref": "deterministic-producer",
            "retrieval_ref": f"scholar-search:{line_id}",
        },
        "simulation_dgp": {
            "dgp_ref": "not_simulated",
            "calibration_ref": "not_applicable",
            "assumption_family": "not_applicable",
        },
        "participation_sample_frame": "not_participation_evidence",
        "concept_spine_refs": ["concept-spine:contract"],
        "jurisdiction": "UA",
        "time_roles": {
            "publication_time": "2025-01-01",
            "retrieval_time": "2026-05-24T12:00:00+00:00",
            "legal_valid_time": "2026-01-01/2026-12-31",
        },
        "producer_identity": {
            "component": "polisyos.scholar.evidence",
            "version": "2026.05.24+w8f",
            "owner": "team-science-quality",
        },
        "execution_context": {
            "run_id": "run-w8-contract",
            "job_id": f"job:{line_id}",
            "tenant_id": "tenant-prod",
        },
        "evidence_ref": f"evidence:{line_id}",
        "runtime_event_ref": f"event:{line_id}",
    }
