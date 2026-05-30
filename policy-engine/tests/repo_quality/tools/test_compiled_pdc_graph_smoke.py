from __future__ import annotations

# ruff: noqa: S101
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from polisyos.core.contracts.runtime import UniversalAuthorityProfile
from polisyos.ir.governance.policy_composition import PolicyLayerLevel
from polisyos.ir.governance.problem_frame import ProblemDomain
from polisyos.obligation_graph import ComplexityBudget, compile_obligation_graph
from polisyos.obligation_rules import build_seed_obligation_rule_catalog
from polisyos.policy_grammar import (
    PolicyGrammarCompiler,
    PolicyGrammarConceptSpineRefs,
    PolicyGrammarIntent,
    facet_snapshots_for_obligation_graph,
)
from polisyos.runtime.quality.producer_pipeline import (
    run_requirement_spec_producer_pipeline,
)
from polisyos.scientist.policy_design.claim_decomposition import compile_claim_decomposition

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


@dataclass(frozen=True)
class _SmokeCapabilityBinding:
    schema_version: str = "policyos.capability_binding_result.v1"
    rule_version_ref: str = "capability-smoke-v1"
    requirement_id: str | None = None
    status: str = "selected_derived"
    selected_capability_ref: str | None = None
    construct_ref: str | None = None
    capability_index_ref: str | None = "capability-index:compiled-pdc-smoke"
    authority_level: str = "governed_pilot"
    authority_envelope_result: str = "admissible_with_smoke_fixture"
    binding_reasons: tuple[str, ...] = ("construct_match", "smoke_fixture")
    blocked_reasons: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ("repo-quality smoke resolver",)
    acquisition_strategies: tuple[dict[str, Any], ...] = ()
    rejected_alternatives: tuple[dict[str, Any], ...] = ()
    conflict_markers: tuple[dict[str, Any], ...] = ()


class _SmokeCapabilityResolver:
    def resolve(self, query: Any) -> _SmokeCapabilityBinding:
        construct = getattr(query, "construct", None) or query.get("construct")
        requirement_id = getattr(query, "requirement_id", None) or query.get(
            "requirement_id"
        )
        return _SmokeCapabilityBinding(
            requirement_id=requirement_id,
            selected_capability_ref=f"capability:{construct}:compiled-pdc-smoke",
            construct_ref=f"construct:{construct}",
        )


def test_i8_compiled_pdc_graph_smoke_passes_or_emits_typed_blocker() -> None:
    for intent_id, text, domain in INTENTS:
        artifacts = _compile_w6_artifacts(intent_id=intent_id, text=text, domain=domain)
        report = run_requirement_spec_producer_pipeline(
            run_id=f"run-i8-smoke-{intent_id}",
            job_id=f"job-i8-smoke-{intent_id}",
            tenant_id="tenant-i8-smoke",
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

        smoke = report["compiled_pdc_graph_smoke"]

        assert report["compiled_requirement_exit_gate"]["status"] == "pass"
        assert smoke["status"] == "pass"
        assert smoke["runtime_pdc_graph_ref"].startswith("sha256:")
        assert smoke["capability_reality_label"] == "implemented"


def _compile_w6_artifacts(
    *,
    intent_id: str,
    text: str,
    domain: ProblemDomain,
) -> dict[str, Any]:
    from polisyos.data_requirement import DataRequirementCompiler
    from polisyos.legal_requirement import LegalAuthorityRequirementCompiler
    from polisyos.method_requirement import MethodValidityRequirementCompiler
    from polisyos.participation_requirement import ParticipationProvenanceCompiler
    from polisyos.scholar_requirement import ScholarSupportRequirementCompiler

    case = PolicyGrammarCompiler().compile(
        intent=PolicyGrammarIntent(intent_id=intent_id, text=text, domain=domain),
        authority_profile=UniversalAuthorityProfile(
            profile_id=f"authority_profile.{intent_id}",
            authority_type=PolicyLayerLevel.LOCAL,
        ),
        concept_spine_refs=PolicyGrammarConceptSpineRefs(
            concept_spine_ref=f"cas://concept-spine/{intent_id}",
            jurisdiction_spine_ref=f"cas://jurisdiction-spine/{intent_id}",
            canonical_concept_refs=(f"concept:{intent_id}:policy",),
        ),
    )
    graph = compile_obligation_graph(
        run_id=f"run-{intent_id}",
        facets=facet_snapshots_for_obligation_graph(case),
        governed_rules=build_seed_obligation_rule_catalog().rules,
        complexity_budget=ComplexityBudget(max_frontier_items=12),
        generated_at=NOW,
    )
    facets = [
        {
            "facet_id": snapshot["facet_id"],
            "facet_type": snapshot["facet_type"],
            "value": snapshot["value"],
            "concept_spine_refs": [snapshot["concept_ref"]],
            "authority_profile_refs": [snapshot["authority_profile"]],
        }
        for snapshot in facet_snapshots_for_obligation_graph(case)
    ]
    obligations = [
        {
            "obligation_id": item.frontier_id,
            "family": item.bundle_key.family,
            "description": item.obligation_text,
            "facet_refs": [facet["facet_id"] for facet in facets],
            "concept_spine_refs": [case.concept_spine_ref],
            "authority_profile_refs": [case.authority_profile.profile_id],
        }
        for item in graph.blocking_frontier
    ]
    claim_ledger = compile_claim_decomposition(
        {
            "run_id": f"run-{intent_id}",
            "intent": text,
            "facets": facets,
            "obligations": obligations,
            "named_alternatives": [
                {
                    "alternative_id": f"alternative-{intent_id}",
                    "label": "Alternative policy design",
                    "description": "A plausible alternative for PDC comparison.",
                }
            ],
            "concept_spine_refs": [case.concept_spine_ref],
            "authority_profile_refs": [case.authority_profile.profile_id],
        }
    )
    claims = [
        {
            **claim.model_dump(mode="json", exclude_none=True),
            "baseline_refs": [record.baseline_id for record in claim_ledger.baseline_records],
            "alternative_refs": [
                record.alternative_id for record in claim_ledger.alternative_records
            ],
            "legal_authority_required": True,
            "required_authority_types": ["implementing"],
            "policy_instrument": _instrument_for_intent(intent_id),
            "competent_actor_ref": "local_policy_authority",
            "implementation_authority_required": True,
            "implementation_authority_ref": "local_implementation_office",
            "authority_level": "production",
            "population_scope": "affected_population",
        }
        for claim in claim_ledger.claims[:3]
    ]
    data_report = DataRequirementCompiler(
        capability_resolver=_SmokeCapabilityResolver()
    ).compile_for_claim_ledger(
        run_id=f"run-{intent_id}",
        scenario_id=intent_id,
        claim_ledger=claim_ledger,
        facet_snapshots=facets,
        obligation_graph=graph,
        authority_profile_refs=(case.authority_profile.profile_id,),
    )
    legal_specs = LegalAuthorityRequirementCompiler().compile(
        run_id=f"run-{intent_id}",
        target_context={
            "jurisdiction": "UA-30-KYIV",
            "authority_profile": "production",
            "as_of": "2026-05-23",
        },
        claims=claims,
        facets=facets,
        obligations=obligations,
    )
    method_artifact = MethodValidityRequirementCompiler().compile(
        run_id=f"run-{intent_id}",
        claims=claims,
        requirement_graph_ref=graph.graph_id,
    )
    scholar_result = ScholarSupportRequirementCompiler().compile(
        {
            "run_id": f"run-{intent_id}",
            "authority_level": "production",
            "claims": [
                {
                    "claim_id": claim["claim_id"],
                    "claim_text": claim["text"],
                    "claim_type": claim.get("claim_type") or "factual",
                    "claim_family": claim.get("claim_family"),
                    "claim_use": claim.get("claim_use"),
                    "authority_level": "production",
                    "population_scope": "affected_population",
                    "facet_refs": claim.get("facet_refs", []),
                    "obligation_refs": claim.get("obligation_refs", []),
                    "concept_spine_refs": claim.get("concept_spine_refs", []),
                    "authority_profile_refs": claim.get("authority_profile_refs", []),
                }
                for claim in claims
            ],
        }
    )
    participation_bundle = ParticipationProvenanceCompiler().compile(
        {
            "run_id": f"run-{intent_id}",
            "claims": claims,
        }
    )
    return {
        "claim_ledger": claim_ledger,
        "claims": claims,
        "universal_grammar_compilation": {
            "status": "pass",
            "ref": case.case_id,
            "facet_count": len(facets),
        },
        "obligation_graph": {
            "status": "pass",
            "graph_ref": graph.graph_id,
            "frontier_count": len(graph.blocking_frontier),
        },
        "claim_decomposition": {
            "status": "pass",
            "ref": f"claim-ledger:{intent_id}",
            "claim_count": len(claim_ledger.claims),
        },
        "data_requirement_specs": data_report.specs,
        "legal_authority_requirement_specs": [
            spec for spec in legal_specs if not spec.out_of_scope
        ][:3],
        "method_validity_requirement_specs": method_artifact.requirements[:3],
        "scholar_support_requirement_specs": scholar_result.requirements[:3],
        "participation_provenance_requirement_specs": participation_bundle.requirements[:3],
    }


def _instrument_for_intent(intent_id: str) -> str:
    if intent_id == "health_intervention":
        return "public_service_delivery"
    if intent_id == "housing_subsidy":
        return "housing_voucher"
    return "credit_guarantee"
