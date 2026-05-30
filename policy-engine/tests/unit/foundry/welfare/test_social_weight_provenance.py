from __future__ import annotations

from datetime import UTC, datetime

# ruff: noqa: S101
import pytest

from polisyos.foundry.welfare.social_weight_provenance import (
    AffectedGroupWeight,
    SocialWeightMandate,
    SocialWeightProvenance,
    SocialWeightProvenanceError,
    ValueChoiceActor,
    assert_social_weight_provenance_usable_for_value_choice,
)


def _actor() -> ValueChoiceActor:
    return ValueChoiceActor(
        actor_id="agency:treasury",
        actor_role="public_authority",
        display_name="Treasury policy board",
    )


def _mandate() -> SocialWeightMandate:
    return SocialWeightMandate(
        mandate_ref="mandate://budget-act/2026/section-4",
        mandate_type="statutory",
        authority_scope="distributional welfare weights for this budget cycle",
    )


def test_social_weight_provenance_requires_governance_lineage() -> None:
    with pytest.raises(ValueError, match="chosen_by"):
        SocialWeightProvenance(
            provenance_id="swp-empty-actor",
            social_weight_ref="swr://policy.welfare/test@1.0.0#abc",
            source_class="governance_decision",
            chosen_by=(),
            mandate=_mandate(),
            chosen_at=datetime(2026, 5, 24, tzinfo=UTC),
            affected_groups=(
                AffectedGroupWeight(group_id="low_income", weight=2.0),
            ),
            sponsor_disclosure_status="none_disclosed",
            review_status="approved",
            claim_refs=("claim:welfare:1",),
        )


def test_llm_social_weight_candidate_cannot_be_used_for_value_choice() -> None:
    provenance = SocialWeightProvenance(
        provenance_id="swp-llm-candidate",
        social_weight_ref="swr://policy.welfare/test@1.0.0#abc",
        source_class="llm_candidate",
        chosen_by=(_actor(),),
        mandate=_mandate(),
        chosen_at=datetime(2026, 5, 24, tzinfo=UTC),
        affected_groups=(
            AffectedGroupWeight(group_id="low_income", weight=2.0),
        ),
        sponsor_disclosure_status="none_disclosed",
        review_status="approved",
        claim_refs=("claim:welfare:1",),
    )

    with pytest.raises(
        SocialWeightProvenanceError,
        match="social_weight_llm_source_not_authoritative",
    ):
        assert_social_weight_provenance_usable_for_value_choice(provenance)


def test_review_pending_provenance_remains_visible_but_not_publication_ready() -> None:
    provenance = SocialWeightProvenance(
        provenance_id="swp-review-pending",
        social_weight_ref="swr://policy.welfare/test@1.0.0#abc",
        source_class="participatory_process",
        chosen_by=(_actor(),),
        mandate=_mandate(),
        chosen_at=datetime(2026, 5, 24, tzinfo=UTC),
        affected_groups=(
            AffectedGroupWeight(group_id="low_income", weight=2.0),
            AffectedGroupWeight(group_id="fixed_income", weight=1.4),
        ),
        sponsor_disclosure_status="disclosed",
        sponsor_disclosures=(
            {
                "sponsor_id": "sponsor:public-budget-office",
                "sponsor_name": "Public Budget Office",
                "interest": "administrative sponsor",
                "disclosure_ref": "disclosure://budget-office/2026",
            },
        ),
        review_status="pending_review",
        claim_refs=("claim:welfare:1",),
    )

    assert provenance.publication_readiness == "review_required"
    assert "value_choice_authority" in provenance.may_not_use_for
