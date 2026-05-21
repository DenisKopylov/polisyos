from __future__ import annotations

import pytest

from polisyos.scientist.methods.search.readiness import DecisionReadiness
from polisyos.scientist.validation.claim_support import (
    ClaimFamily,
    ClaimPublishability,
    CounterevidenceAction,
    LifecycleTransition,
    SupportPredicate,
    SupportStrength,
    claim_support_rules,
    evaluate_claim_support,
    grounding_matrix_checks_for_family,
    grounding_matrix_family_for_claim_family,
)

MINIMAL_SUPPORTED_CLAIMS = {
    ClaimFamily.FACTUAL: {
        "data_refs": ["data.msme_panel"],
        "source_attribution": ["State Statistics Service panel"],
    },
    ClaimFamily.LEGAL: {
        "norm_refs": ["norm.ua.credit_eligibility"],
        "jurisdiction": "UA",
        "effective_date": "2026-01-01",
    },
    ClaimFamily.CAUSAL: {
        "data_refs": ["data.msme_panel"],
        "method_refs": ["method.did"],
        "identification_strategy": "difference_in_differences",
    },
    ClaimFamily.NUMERICAL: {
        "method_refs": ["method.did"],
        "method_output_refs": ["result.did.effect"],
        "metric": "effect_estimate",
        "value": 0.04,
    },
    ClaimFamily.FORECAST: {
        "method_refs": ["method.forecast"],
        "uncertainty_refs": ["uncertainty.forecast.interval"],
        "forecast_horizon": "12 months",
    },
    ClaimFamily.DISTRIBUTIONAL: {
        "method_refs": ["method.distributional"],
        "subgroup_refs": ["subgroup.women_owned_msme"],
    },
    ClaimFamily.WELFARE: {
        "method_refs": ["method.welfare"],
        "welfare_metric": "net_social_benefit",
    },
    ClaimFamily.IMPLEMENTATION: {
        "implementation_plan_refs": ["implementation.rollout.plan"],
        "feasibility_refs": ["implementation.feasibility.review"],
    },
}


def _claim(family: ClaimFamily, **overrides: object) -> dict[str, object]:
    return {
        "claim_id": f"claim_{family.value}",
        "claim_family": family.value,
        "text": f"{family.value} claim",
        **MINIMAL_SUPPORTED_CLAIMS[family],
        **overrides,
    }


def test_claim_support_rules_cover_required_claim_families() -> None:
    rules = claim_support_rules()

    assert set(rules) == set(ClaimFamily)
    assert SupportPredicate.DATA_REF in rules[ClaimFamily.FACTUAL].required_predicates
    assert SupportPredicate.NORM_REF in rules[ClaimFamily.LEGAL].required_predicates
    assert SupportPredicate.IDENTIFICATION_STRATEGY in rules[ClaimFamily.CAUSAL].required_predicates
    assert SupportPredicate.METHOD_OUTPUT_REF in rules[ClaimFamily.NUMERICAL].required_predicates
    assert SupportPredicate.UNCERTAINTY_REF in rules[ClaimFamily.FORECAST].required_predicates
    assert SupportPredicate.SUBGROUP_REF in rules[ClaimFamily.DISTRIBUTIONAL].required_predicates
    assert SupportPredicate.WELFARE_METRIC in rules[ClaimFamily.WELFARE].required_predicates
    assert SupportPredicate.IMPLEMENTATION_PLAN_REF in (
        rules[ClaimFamily.IMPLEMENTATION].required_predicates
    )


@pytest.mark.parametrize("family", list(ClaimFamily))
def test_each_claim_family_can_be_evaluated_as_supported(family: ClaimFamily) -> None:
    assessment = evaluate_claim_support(
        _claim(family),
        base_readiness=DecisionReadiness.EXTERNAL_BRIEFING,
    )

    assert assessment.support_strength is SupportStrength.SUPPORTED
    assert assessment.missing_predicates == []
    assert assessment.publishability is ClaimPublishability.PUBLISHABLE


def test_support_strength_is_resolved_separately_from_publishability() -> None:
    assessment = evaluate_claim_support(
        _claim(ClaimFamily.IMPLEMENTATION),
        base_readiness=DecisionReadiness.RESEARCH_ARTIFACT,
    )

    assert assessment.support_strength is SupportStrength.SUPPORTED
    assert assessment.readiness_level is DecisionReadiness.RESEARCH_ARTIFACT
    assert assessment.publishability is ClaimPublishability.INTERNAL_ONLY


def test_missing_required_predicates_lower_support_without_hiding_matrix_checks() -> None:
    assessment = evaluate_claim_support(
        {
            "claim_id": "causal_missing_design",
            "claim_family": "causal",
            "text": "The programme caused improved survival.",
            "data_refs": ["data.msme_panel"],
            "method_refs": ["method.did"],
        },
        base_readiness=DecisionReadiness.EXTERNAL_BRIEFING,
    )

    assert assessment.support_strength is SupportStrength.WEAK
    assert assessment.publishability is ClaimPublishability.REVIEW_REQUIRED
    assert assessment.missing_predicates == [SupportPredicate.IDENTIFICATION_STRATEGY]
    assert "claim_family_missing_required_grounding" in assessment.grounding_matrix_checks


def test_counterevidence_actions_control_lifecycle_and_publication_state() -> None:
    base_claim = _claim(ClaimFamily.CAUSAL)

    blocked = evaluate_claim_support(
        base_claim,
        base_readiness=DecisionReadiness.RECOMMENDATION_READY,
        counterevidence=[
            {
                "counterevidence_id": "ce.block",
                "action": CounterevidenceAction.BLOCK.value,
                "reason": "Negative control invalidates the causal design.",
            }
        ],
    )
    warned = evaluate_claim_support(
        base_claim,
        base_readiness=DecisionReadiness.RECOMMENDATION_READY,
        counterevidence=[
            {
                "counterevidence_id": "ce.warn",
                "action": CounterevidenceAction.WARN.value,
                "reason": "One source has a narrower population.",
            }
        ],
    )
    lowered = evaluate_claim_support(
        base_claim,
        base_readiness=DecisionReadiness.RECOMMENDATION_READY,
        counterevidence=[
            {
                "counterevidence_id": "ce.lower",
                "action": CounterevidenceAction.LOWER_READINESS.value,
                "readiness_floor": DecisionReadiness.ANALYST_ADVISORY.value,
                "reason": "External validity is not replication-grade.",
            }
        ],
    )
    review = evaluate_claim_support(
        base_claim,
        base_readiness=DecisionReadiness.RECOMMENDATION_READY,
        counterevidence=[
            {
                "counterevidence_id": "ce.review",
                "action": CounterevidenceAction.REQUIRE_REVIEW.value,
                "reason": "Reviewer must adjudicate a conflicting estimate.",
            }
        ],
    )

    assert blocked.publishability is ClaimPublishability.BLOCKED
    assert blocked.lifecycle_transition is LifecycleTransition.BLOCK_PUBLICATION
    assert "counterevidence_blocks_claim" in {issue["code"] for issue in blocked.issues}

    assert warned.publishability is ClaimPublishability.PUBLISHABLE
    assert warned.lifecycle_transition is LifecycleTransition.WARN
    assert "counterevidence_warns_claim" in {issue["code"] for issue in warned.issues}

    assert lowered.publishability is ClaimPublishability.PUBLISHABLE
    assert lowered.readiness_level is DecisionReadiness.ANALYST_ADVISORY
    assert lowered.lifecycle_transition is LifecycleTransition.LOWER_READINESS

    assert review.publishability is ClaimPublishability.REVIEW_REQUIRED
    assert review.lifecycle_transition is LifecycleTransition.REQUIRE_REVIEW


def test_support_rules_map_to_final_policy_grounding_matrix_checks() -> None:
    assert grounding_matrix_family_for_claim_family(ClaimFamily.FACTUAL) == "empirical"
    assert grounding_matrix_family_for_claim_family(ClaimFamily.LEGAL) == "normative"
    assert grounding_matrix_family_for_claim_family(ClaimFamily.WELFARE) == "causal"

    numerical_checks = grounding_matrix_checks_for_family(ClaimFamily.NUMERICAL)
    legal_checks = grounding_matrix_checks_for_family(ClaimFamily.LEGAL)
    implementation_checks = grounding_matrix_checks_for_family(ClaimFamily.IMPLEMENTATION)

    assert "numeric_claim_missing_method_output" in numerical_checks
    assert "numeric_claim_mismatch" in numerical_checks
    assert "normative_claim_missing_applicable_norm" in legal_checks
    assert "minor_claim_missing_grounding_rationale" in implementation_checks
