from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.runtime import UniversalPolicyDesignCase
from polisyos.ir.governance.policy_composition import PolicyLayerLevel
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import NormativeOutcomeChannel, ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.observation.contracts import IdentificationMode
from polisyos.policy_grammar import (
    PolicyGrammarCompiler,
    PolicyGrammarConceptSpineRefs,
    PolicyGrammarConsumerError,
    PolicyGrammarIntent,
    UniversalAuthorityProfile,
    assert_authority_slot_eligible,
    load_universal_policy_design_case,
    require_compiled_universal_policy_design_case,
)
from polisyos.policy_grammar import UNIVERSAL_POLICY_DESIGN_CASE_ARTIFACT_KIND


def test_compiler_emits_typed_facets_for_three_diverse_policy_intents() -> None:
    compiler = PolicyGrammarCompiler()
    cases = [
        (
            "msme_credit",
            (
                "Create a concessional credit guarantee programme for displaced MSMEs in "
                "northern regions in 2026, funded by budget appropriation and delivered "
                "through partner banks to preserve employment."
            ),
            ProblemDomain.FISCAL,
            {
                "instrument_type": "credit",
                "targeting_type": "categorical",
                "delivery_channel": "credit_registry",
                "funding_channel": "concessional_credit",
                "risk_facet": "budget_feasibility",
                "method_need": IdentificationMode.POINT_IDENTIFIED,
            },
        ),
        (
            "health_rollout",
            (
                "Phase a mobile clinic vaccination service for rural children during 2026 "
                "with public-service delivery, budget funding, and monitoring for coverage."
            ),
            ProblemDomain.HEALTHCARE,
            {
                "instrument_type": "service",
                "targeting_type": "categorical",
                "delivery_channel": "public_service",
                "funding_channel": "budget_appropriation",
                "risk_facet": "equity_harm",
                "method_need": IdentificationMode.SEQUENTIAL,
            },
        ),
        (
            "housing_voucher",
            (
                "Provide a means-tested housing voucher subsidy for low-income renters in "
                "Kyiv oblast through municipal service centres, with annual appropriations."
            ),
            ProblemDomain.SOCIAL,
            {
                "instrument_type": "subsidy",
                "targeting_type": "means_tested",
                "delivery_channel": "voucher",
                "funding_channel": "budget_appropriation",
                "risk_facet": "fairness_threshold_reversal",
                "method_need": IdentificationMode.POINT_IDENTIFIED,
            },
        ),
    ]

    for intent_id, text, domain, expected in cases:
        compiled = compiler.compile(
            intent=PolicyGrammarIntent(intent_id=intent_id, text=text, domain=domain),
            authority_profile=_authority_profile(PolicyLayerLevel.LOCAL),
            concept_spine_refs=_concept_spine_refs(intent_id),
        )

        assert isinstance(compiled, UniversalPolicyDesignCase)
        assert compiled.status == "compiled"
        assert compiled.capability_reality_label == "implemented"
        assert compiled.facets is not None
        assert compiled.facets.instrument_type.value == expected["instrument_type"]
        assert compiled.facets.targeting_type.value == expected["targeting_type"]
        assert compiled.facets.delivery_channel.value == expected["delivery_channel"]
        assert compiled.facets.funding_channel.value == expected["funding_channel"]
        assert compiled.facets.authority_type.value is PolicyLayerLevel.LOCAL
        assert compiled.facets.outcome_channel.value is NormativeOutcomeChannel.SIMULATION_METRIC
        assert compiled.facets.risk_facet.value == expected["risk_facet"]
        assert compiled.facets.method_need.value is expected["method_need"]
        assert compiled.facets.population_predicate.value != "free_text"
        assert compiled.facets.geography_predicate.value != "free_text"
        assert compiled.facets.time_predicate.value != "free_text"
        for facet in compiled.facets.iter_facets():
            assert facet.concept_spine_refs
            assert facet.source_vocabulary_refs


def test_compiler_reuses_problem_frame_and_policy_spec_without_new_ir_enum_strings() -> None:
    compiler = PolicyGrammarCompiler()
    problem_frame = ProblemFrame(
        problem_id="health_problem",
        domain=ProblemDomain.HEALTHCARE,
        narrative="Rural primary-care access is low.",
    )
    policy_spec = PolicySpec(
        policy_id="clinic_policy",
        interventions=[
            InterventionSpec(
                intervention_id="mobile_clinic",
                kind="service",
                target=SelectorPredicate(
                    kind="predicate",
                    field="region_type",
                    operator="==",
                    value="rural",
                ),
                schedule=ScheduleSpec(start_step=0, duration_steps=12),
                params={"monthly_budget": Decimal("100000")},
                target_population_type="children",
                target_region_ids=["rural_regions"],
                identification_mode=IdentificationMode.SEQUENTIAL,
            )
        ],
    )

    compiled = compiler.compile(
        intent=PolicyGrammarIntent.from_problem_policy(
            intent_id="from_trinity",
            problem_frame=problem_frame,
            policy_spec=policy_spec,
        ),
        authority_profile=_authority_profile(PolicyLayerLevel.STATE),
        concept_spine_refs=_concept_spine_refs("from_trinity"),
    )

    assert compiled.status == "compiled"
    assert compiled.facets is not None
    assert compiled.facets.authority_type.value is PolicyLayerLevel.STATE
    assert compiled.facets.outcome_channel.value is NormativeOutcomeChannel.SIMULATION_METRIC
    assert compiled.facets.method_need.value is IdentificationMode.SEQUENTIAL
    assert "polisyos.ir.governance.problem_frame.ProblemDomain" in compiled.reuse_evidence
    assert "polisyos.ir.governance.policy_spec.PolicySpec" in compiled.reuse_evidence
    assert "polisyos.scientist.policy_design.schema.PolicyCandidateSchema" in compiled.reuse_evidence
    assert "polisyos.scientist.policy_design.critic.ConstraintCritic" in compiled.reuse_evidence
    assert "polisyos.scientist.evals.challenge_factory.ChallengeClass" in compiled.reuse_evidence
    assert "polisyos.ir.governance.temporal_logic.TemporalPolicyConstraint" in compiled.reuse_evidence


def test_missing_concept_spine_refs_blocks_consumer_ready_facets() -> None:
    compiled = PolicyGrammarCompiler().compile(
        intent=PolicyGrammarIntent(
            intent_id="ambiguous_spine",
            text="Create a health service for children in 2026.",
            domain=ProblemDomain.HEALTHCARE,
        ),
        authority_profile=_authority_profile(PolicyLayerLevel.LOCAL),
        concept_spine_refs=PolicyGrammarConceptSpineRefs(
            concept_spine_ref="cas://concept-spine",
            jurisdiction_spine_ref="cas://jurisdiction-spine",
        ),
    )

    assert compiled.status == "blocked"
    assert compiled.facets is None
    assert _blocker_codes(compiled) == {"policy_grammar_concept_refs_missing"}
    with pytest.raises(PolicyGrammarConsumerError, match="blocked"):
        require_compiled_universal_policy_design_case(compiled)


def test_unclassified_intent_blocks_structural_false_pass() -> None:
    compiled = PolicyGrammarCompiler().compile(
        intent=PolicyGrammarIntent(
            intent_id="unclassified",
            text="Do something beneficial someday.",
            domain=ProblemDomain.CUSTOM,
        ),
        authority_profile=_authority_profile(PolicyLayerLevel.LOCAL),
        concept_spine_refs=_concept_spine_refs("unclassified"),
    )

    assert compiled.status == "blocked"
    assert compiled.facets is None
    assert "policy_grammar_facet_derivation_missing" in _blocker_codes(compiled)


def test_compile_and_persist_writes_cas_artifact_and_consumer_reads_it(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    compiler = PolicyGrammarCompiler()

    artifact = compiler.compile_and_persist(
        store=store,
        intent=PolicyGrammarIntent(
            intent_id="persisted_msme",
            text="Create a concessional credit programme for MSMEs in 2026.",
            domain=ProblemDomain.FISCAL,
        ),
        authority_profile=_authority_profile(PolicyLayerLevel.FEDERAL),
        concept_spine_refs=_concept_spine_refs("persisted_msme"),
    )

    assert artifact.artifact_ref.kind == UNIVERSAL_POLICY_DESIGN_CASE_ARTIFACT_KIND
    loaded = load_universal_policy_design_case(store, artifact.artifact_ref)
    consumer_ready = require_compiled_universal_policy_design_case(loaded)
    assert consumer_ready.case_id == artifact.case.case_id
    assert consumer_ready.downstream_consumer_components == (
        "obligation_graph",
        "claim_decomposition",
        "requirement_compilers",
    )
    assert consumer_ready.audit_surface.authoritative_for == ("compilation_facets",)


def test_llm_candidate_authority_profile_cannot_satisfy_authority_slots() -> None:
    compiled = PolicyGrammarCompiler().compile(
        intent=PolicyGrammarIntent(
            intent_id="llm_credit",
            text="Create a concessional credit programme for MSMEs in 2026.",
            domain=ProblemDomain.FISCAL,
        ),
        authority_profile=UniversalAuthorityProfile(
            profile_id="llm_profile",
            authority_type=PolicyLayerLevel.FEDERAL,
            source_classification="llm_candidate",
            authoritative_for=("compilation_facets",),
        ),
        concept_spine_refs=_concept_spine_refs("llm_credit"),
    )

    assert compiled.status == "candidate_unverified"
    assert compiled.authority_envelope.source_classification == "llm_candidate"
    assert "legal_authority" in compiled.authority_envelope.may_not_use_for
    assert "closeout_authority" in compiled.authority_envelope.may_not_use_for
    with pytest.raises(PolicyGrammarConsumerError, match="candidate_unverified"):
        assert_authority_slot_eligible(compiled, "legal_authority")


def test_authority_profile_rejects_llm_candidate_authoritative_legal_claim() -> None:
    with pytest.raises(ValidationError, match="llm_candidate"):
        UniversalAuthorityProfile(
            profile_id="bad_llm_profile",
            authority_type=PolicyLayerLevel.FEDERAL,
            source_classification="llm_candidate",
            authoritative_for=("legal_authority",),
        )


def _authority_profile(authority_type: PolicyLayerLevel) -> UniversalAuthorityProfile:
    return UniversalAuthorityProfile(
        profile_id=f"{authority_type.value}_authority",
        authority_type=authority_type,
        source_classification="deterministic_producer",
        authoritative_for=("compilation_facets",),
        may_not_use_for=(
            "legal_authority",
            "data_authority",
            "method_authority",
            "closeout_authority",
            "publication_authority",
        ),
    )


def _concept_spine_refs(intent_id: str) -> PolicyGrammarConceptSpineRefs:
    return PolicyGrammarConceptSpineRefs(
        concept_spine_ref=f"cas://concept-spine/{intent_id}",
        jurisdiction_spine_ref=f"cas://jurisdiction-spine/{intent_id}",
        facet_concept_refs={
            "instrument_type": (f"concept:{intent_id}:instrument",),
            "targeting_type": (f"concept:{intent_id}:targeting",),
            "delivery_channel": (f"concept:{intent_id}:delivery",),
            "funding_channel": (f"concept:{intent_id}:funding",),
            "authority_type": (f"concept:{intent_id}:authority",),
            "outcome_channel": (f"concept:{intent_id}:outcome",),
            "risk_facet": (f"concept:{intent_id}:risk",),
            "method_need": (f"concept:{intent_id}:method",),
            "population_predicate": (f"concept:{intent_id}:population",),
            "geography_predicate": (f"concept:{intent_id}:geography",),
            "time_predicate": (f"concept:{intent_id}:time",),
        },
    )


def _blocker_codes(case: UniversalPolicyDesignCase) -> set[str]:
    return {blocker.code for blocker in case.blockers}
