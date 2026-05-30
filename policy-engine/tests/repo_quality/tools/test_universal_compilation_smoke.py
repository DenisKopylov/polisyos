from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime
from typing import Any

from polisyos.core.contracts.runtime import UniversalAuthorityProfile, UniversalPolicyDesignCase
from polisyos.ir.governance.policy_composition import PolicyLayerLevel
from polisyos.ir.governance.problem_frame import ProblemDomain
from polisyos.obligation_graph import (
    ComplexityBudget,
    ObligationGraph,
    compile_obligation_graph,
)
from polisyos.obligation_rules import build_seed_obligation_rule_catalog
from polisyos.policy_grammar import (
    PolicyGrammarCompiler,
    PolicyGrammarConceptSpineRefs,
    PolicyGrammarIntent,
    facet_snapshots_for_obligation_graph,
)
from polisyos.runtime.quality.candidate_firewall import candidate_firewall_issues_for_payload
from polisyos.runtime.quality.hypothesis_ledger import HypothesisLedger
from polisyos.scientist.policy_design.claim_decomposition import compile_claim_decomposition
from polisyos.scientist.policy_design.critic_ensemble import MultiCriticEnsemble
from polisyos.scientist.policy_design.formulator import LLMFormulator, LLMFormulatorInput

NOW = datetime(2026, 5, 23, 12, 0, tzinfo=UTC)


INTENTS: tuple[tuple[str, str, ProblemDomain], ...] = (
    (
        "msme_credit",
        (
            "Create a concessional credit guarantee programme for displaced MSMEs in "
            "northern regions in 2026, funded by budget appropriation and delivered "
            "through partner banks to preserve employment."
        ),
        ProblemDomain.FISCAL,
    ),
    (
        "health_intervention",
        (
            "Phase a mobile clinic vaccination service for rural children during 2026 "
            "with public-service delivery, budget funding, and monitoring for coverage."
        ),
        ProblemDomain.HEALTHCARE,
    ),
    (
        "housing_subsidy",
        (
            "Provide a means-tested housing voucher subsidy for low-income renters in "
            "Kyiv oblast through municipal service centres, with annual appropriations."
        ),
        ProblemDomain.SOCIAL,
    ),
)


def test_i7_universal_compilation_smoke_for_three_policy_intents() -> None:
    catalog = build_seed_obligation_rule_catalog()

    for intent_id, text, domain in INTENTS:
        case = PolicyGrammarCompiler().compile(
            intent=PolicyGrammarIntent(intent_id=intent_id, text=text, domain=domain),
            authority_profile=UniversalAuthorityProfile(
                profile_id=f"authority_profile.{intent_id}",
                authority_type=PolicyLayerLevel.LOCAL,
            ),
            concept_spine_refs=_concept_refs(intent_id),
        )
        assert case.facets is not None, case.blockers

        graph = compile_obligation_graph(
            run_id=f"run-{intent_id}",
            facets=facet_snapshots_for_obligation_graph(case),
            governed_rules=catalog.rules,
            complexity_budget=ComplexityBudget(max_frontier_items=12),
            generated_at=NOW,
        )
        assert graph.candidate_ledger
        assert graph.bundle_ledger
        assert graph.blocking_frontier

        claim_ledger = compile_claim_decomposition(
            {
                "run_id": f"run-{intent_id}",
                "intent": text,
                "facets": _claim_facets(case),
                "obligations": _claim_obligations(graph),
                "named_alternatives": [
                    {
                        "alternative_id": f"alternative-{intent_id}-cash-transfer",
                        "label": "Cash transfer alternative",
                        "description": "Direct transfer instead of the proposed instrument.",
                    }
                ],
                "concept_spine_refs": [case.concept_spine_ref],
                "authority_profile_refs": [case.authority_profile.profile_id],
            }
        )
        assert claim_ledger.family_assignments
        assert claim_ledger.baseline_records
        assert claim_ledger.alternative_records

        formulator_input = LLMFormulatorInput(
            run_id=f"run-{intent_id}",
            intent=text,
            facets={facet["facet_type"]: facet["value"] for facet in _claim_facets(case)},
            obligations=list(_claim_obligations(graph)),
            claim_decomposition=[
                claim.model_dump(mode="json", exclude_none=True)
                for claim in claim_ledger.claims
            ],
            authority_profile_ref=case.authority_profile.profile_id,
            concept_spine_refs=(case.concept_spine_ref,),
            source_refs=(case.case_id, graph.graph_id),
        )
        formulator_output = LLMFormulator().formulate(formulator_input)
        critic_report = MultiCriticEnsemble.default().evaluate(
            formulator_input,
            candidates=formulator_output.candidates,
        )
        critic_entries = [
            verdict.proposed_candidate.to_ledger_entry()
            for verdict in critic_report.verdicts
            if verdict.proposed_candidate is not None
        ]
        runtime_ledger = HypothesisLedger.model_validate(
            {
                "run_id": f"run-{intent_id}",
                "job_id": f"job-{intent_id}",
                "entries": [
                    *[
                        entry.model_dump(mode="json", exclude_none=True)
                        for entry in formulator_output.ledger_entries
                    ],
                    *[
                        entry.model_dump(mode="json", exclude_none=True)
                        for entry in critic_entries
                    ],
                ],
            }
        )

        assert runtime_ledger.summary["candidate_unverified_count"] >= 1
        assert critic_report.diversity.basis_count == 8
        issues = candidate_firewall_issues_for_payload(
            {"selected_norm_refs": [runtime_ledger.entries[0].candidate_ref]},
            hypothesis_ledger=runtime_ledger,
            authority_slots=("legal_authority",),
            surface="claim_registry",
        )
        assert {issue["code"] for issue in issues} == {
            "candidate_firewall_candidate_unverified"
        }


def _concept_refs(intent_id: str) -> PolicyGrammarConceptSpineRefs:
    return PolicyGrammarConceptSpineRefs(
        concept_spine_ref=f"cas://concept-spine/{intent_id}",
        jurisdiction_spine_ref=f"cas://jurisdiction-spine/{intent_id}",
        canonical_concept_refs=(f"concept:{intent_id}:policy",),
    )


def _claim_facets(case: UniversalPolicyDesignCase) -> list[dict[str, Any]]:
    return [
        {
            "facet_id": snapshot["facet_id"],
            "facet_type": snapshot["facet_type"],
            "value": snapshot["value"],
            "concept_spine_refs": [snapshot["concept_ref"]],
            "authority_profile_refs": [snapshot["authority_profile"]],
        }
        for snapshot in facet_snapshots_for_obligation_graph(case)
    ]


def _claim_obligations(graph: ObligationGraph) -> list[dict[str, Any]]:
    facet_refs = [facet.facet_id for facet in graph.facets]
    concept_refs = [facet.concept_ref for facet in graph.facets]
    authority_refs = [facet.authority_profile for facet in graph.facets]
    return [
        {
            "obligation_id": item.frontier_id,
            "family": item.bundle_key.family,
            "description": item.obligation_text,
            "facet_refs": facet_refs,
            "concept_spine_refs": concept_refs,
            "authority_profile_refs": authority_refs,
        }
        for item in graph.blocking_frontier
    ]
