from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

# ruff: noqa: S101
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.welfare.frontier_emitter import (
    AlternativeOutcome,
    ObjectiveSpec,
    WelfareFrontierError,
    assert_welfare_publication_not_scalar_only,
    build_welfare_frontier_surface,
    emit_welfare_frontier,
    load_welfare_frontier_emission,
    persist_welfare_frontier_emission,
)
from polisyos.foundry.welfare.social_weight_provenance import (
    AffectedGroupWeight,
    SocialWeightMandate,
    SocialWeightProvenance,
    ValueChoiceActor,
)

if TYPE_CHECKING:
    from pathlib import Path


def _objectives() -> tuple[ObjectiveSpec, ...]:
    return (
        ObjectiveSpec(objective_id="employment", label="Employment gain", direction="maximize"),
        ObjectiveSpec(objective_id="fiscal_cost", label="Fiscal cost", direction="minimize"),
        ObjectiveSpec(
            objective_id="low_income_gain",
            label="Low-income welfare gain",
            direction="maximize",
        ),
    )


def _outcomes() -> tuple[AlternativeOutcome, ...]:
    return (
        AlternativeOutcome(
            alternative_id="targeted_credit",
            label="Targeted credit support",
            objective_values={
                "employment": 10.0,
                "fiscal_cost": 20.0,
                "low_income_gain": 8.0,
            },
            claim_refs=("claim:welfare:1",),
            welfare_bound_refs=("cas://welfare-bound/targeted-credit",),
            social_weight_ref="swr://policy.welfare/test@1.0.0#abc",
        ),
        AlternativeOutcome(
            alternative_id="broad_subsidy",
            label="Broad subsidy",
            objective_values={
                "employment": 12.0,
                "fiscal_cost": 25.0,
                "low_income_gain": 7.0,
            },
            claim_refs=("claim:welfare:1",),
            welfare_bound_refs=("cas://welfare-bound/broad-subsidy",),
            social_weight_ref="swr://policy.welfare/test@1.0.0#abc",
        ),
        AlternativeOutcome(
            alternative_id="cash_transfer",
            label="Cash transfer",
            objective_values={
                "employment": 8.0,
                "fiscal_cost": 15.0,
                "low_income_gain": 9.0,
            },
            claim_refs=("claim:welfare:1",),
            welfare_bound_refs=("cas://welfare-bound/cash-transfer",),
            social_weight_ref="swr://policy.welfare/test@1.0.0#abc",
        ),
        AlternativeOutcome(
            alternative_id="untargeted_credit",
            label="Untargeted credit",
            objective_values={
                "employment": 9.0,
                "fiscal_cost": 22.0,
                "low_income_gain": 6.0,
            },
            claim_refs=("claim:welfare:1",),
            welfare_bound_refs=("cas://welfare-bound/untargeted-credit",),
            social_weight_ref="swr://policy.welfare/test@1.0.0#abc",
        ),
    )


def _provenance() -> SocialWeightProvenance:
    return SocialWeightProvenance(
        provenance_id="swp-public-budget-2026",
        social_weight_ref="swr://policy.welfare/test@1.0.0#abc",
        source_class="governance_decision",
        chosen_by=(
            ValueChoiceActor(
                actor_id="agency:treasury",
                actor_role="public_authority",
                display_name="Treasury policy board",
            ),
        ),
        mandate=SocialWeightMandate(
            mandate_ref="mandate://budget-act/2026/section-4",
            mandate_type="statutory",
            authority_scope="distributional welfare weights for this budget cycle",
        ),
        chosen_at=datetime(2026, 5, 24, tzinfo=UTC),
        affected_groups=(
            AffectedGroupWeight(group_id="low_income", weight=2.0),
            AffectedGroupWeight(group_id="fixed_income", weight=1.4),
        ),
        dissent=(
            {
                "dissent_id": "dissent:small-business-panel",
                "summary": "SME panel preferred broad subsidy despite weaker low-income gains.",
                "affected_group_ids": ("small_business",),
            },
        ),
        review_status="approved",
        review_refs=("review://welfare-weights/2026-05-24",),
        sponsor_disclosure_status="none_disclosed",
        claim_refs=("claim:welfare:1",),
    )


def test_emit_frontier_separates_pareto_facts_from_value_choice() -> None:
    emission = emit_welfare_frontier(
        claim_refs=("claim:welfare:1",),
        objectives=_objectives(),
        outcomes=_outcomes(),
        social_weight_provenance=_provenance(),
        selected_alternative_id="targeted_credit",
        generated_at=datetime(2026, 5, 24, tzinfo=UTC),
    )

    assert emission.frontier.frontier_alternative_ids == (
        "targeted_credit",
        "broad_subsidy",
        "cash_transfer",
    )
    assert emission.frontier.dominated_alternative_ids == ("untargeted_credit",)
    assert emission.frontier.dominance["untargeted_credit"].dominated_by == (
        "targeted_credit",
    )
    assert emission.frontier.authoritative_for == ("pareto_frontier_fact",)
    assert "value_choice_authority" in emission.frontier.may_not_use_for

    assert emission.value_choice.selected_alternative_id == "targeted_credit"
    assert emission.value_choice.frontier_id == emission.frontier.frontier_id
    assert emission.value_choice.social_weight_provenance_id == "swp-public-budget-2026"
    assert emission.value_choice.authoritative_for == ("value_choice_record",)
    assert "pareto_frontier_fact" in emission.value_choice.may_not_use_for
    assert emission.value_choice.rejected_nondominated_alternative_ids == (
        "broad_subsidy",
        "cash_transfer",
    )

    dumped = emission.model_dump(mode="json")
    assert "scalar_welfare_aggregate" not in dumped
    assert emission.audit_trail.claim_refs == ("claim:welfare:1",)
    assert set(emission.audit_trail.welfare_bound_refs) == {
        "cas://welfare-bound/targeted-credit",
        "cas://welfare-bound/broad-subsidy",
        "cas://welfare-bound/cash-transfer",
        "cas://welfare-bound/untargeted-credit",
    }


def test_public_surface_exposes_frontier_and_blocks_scalar_only_payload() -> None:
    emission = emit_welfare_frontier(
        claim_refs=("claim:welfare:1",),
        objectives=_objectives(),
        outcomes=_outcomes(),
        social_weight_provenance=_provenance(),
        selected_alternative_id="targeted_credit",
    )

    with pytest.raises(WelfareFrontierError, match="scalar_welfare_aggregate_without_frontier"):
        assert_welfare_publication_not_scalar_only({"welfare_score": 0.72})

    surface = build_welfare_frontier_surface(emission, audience="public")
    assert_welfare_publication_not_scalar_only(surface.model_dump(mode="json"))
    assert surface.audience == "public"
    assert surface.authority_role == "projection_only"
    assert surface.frontier.frontier_id == emission.frontier.frontier_id
    assert surface.value_choice.selected_alternative_id == "targeted_credit"
    assert surface.social_weight_provenance.review_status == "approved"
    assert surface.scalar_aggregate is None
    assert "scalar_welfare_authority" in surface.may_not_use_for


def test_emit_frontier_rejects_scalar_aggregation_without_provenance() -> None:
    with pytest.raises(WelfareFrontierError, match="social_weight_provenance_required"):
        emit_welfare_frontier(
            claim_refs=("claim:welfare:1",),
            objectives=_objectives(),
            outcomes=_outcomes(),
            social_weight_provenance=None,
            selected_alternative_id="targeted_credit",
        )


def test_persisted_emission_round_trips_claim_bound_audit_trail(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    emission = emit_welfare_frontier(
        claim_refs=("claim:welfare:1",),
        objectives=_objectives(),
        outcomes=_outcomes(),
        social_weight_provenance=_provenance(),
        selected_alternative_id="targeted_credit",
        generated_at=datetime(2026, 5, 24, tzinfo=UTC),
    )

    ref = persist_welfare_frontier_emission(store, emission)
    loaded = load_welfare_frontier_emission(store, ref)

    assert ref.kind == "foundry.welfare_frontier_emission"
    assert loaded.frontier.frontier_id == emission.frontier.frontier_id
    assert loaded.audit_trail.claim_refs == ("claim:welfare:1",)
    assert loaded.social_weight_provenance.provenance_id == "swp-public-budget-2026"
