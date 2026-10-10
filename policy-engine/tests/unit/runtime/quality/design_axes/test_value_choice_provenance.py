from __future__ import annotations

from polisyos.pdc import AuthorityBoundary
from polisyos.runtime.quality.design_axes.value_choice_provenance import (
    LAYER2_S8_VALUE_CHOICE_RULE_VERSION,
    build_value_choice_provenance_record,
    project_value_tradeoff_disclosure,
)


def test_advisory_choice_projection_preserves_selection_source_and_audience() -> None:
    """A candidate selection remains traceable while disclosure stays non-authoritative."""

    record = build_value_choice_provenance_record(
        record_id="value-choice/bridge-pilot/candidate-a",
        record_ref="pdc://bridge-pilot/s8/value-choice/candidate-a",
        case_id="bridge-pilot",
        selected_alternative_ref="alternative://bridge-pilot/candidate-a",
        objective_provenance_ref="pdc://bridge-pilot/s8/objective-provenance",
        value_schedule_ref=None,
        pareto_archive_ref="pdc://bridge-pilot/s8/unranked-frontier",
        social_weight_provenance_refs=(),
        mandate_refs=("pdc://bridge-pilot/s6/mandate-limitation",),
        delegation_refs=(),
        value_authorization_decision_refs=(),
        conflict_rows=(),
        affected_group_rows=({"group_ref": "group://bridge-pilot/commuters"},),
        dissent_refs=("dissent://bridge-pilot/commuter-panel",),
        blocking_rights_refs=(),
        alternative_schedule_sensitivity_rows=(),
        disposition="advisory_only",
        integrity_status="limit",
        replay_refs=(
            "pdc://bridge-pilot/s8/objective-provenance",
            "pdc://bridge-pilot/s8/unranked-frontier",
        ),
        authority_boundary=AuthorityBoundary(
            authoritative_for=["value_choice_provenance"],
            may_not_use_for=[
                "production_recommendation",
                "production_claim_authority",
                "scalar_welfare_authority",
            ],
            source_authority="deterministic_producer",
            posture="advisory",
            rule_version_refs=[LAYER2_S8_VALUE_CHOICE_RULE_VERSION],
        ),
        rule_version_ref=LAYER2_S8_VALUE_CHOICE_RULE_VERSION,
    )

    expert = project_value_tradeoff_disclosure(
        value_choice_record=record,
        audience="EXPERT",
        rule_version_ref=LAYER2_S8_VALUE_CHOICE_RULE_VERSION,
    )
    public = project_value_tradeoff_disclosure(
        value_choice_record=record,
        audience="PUBLIC",
        rule_version_ref=LAYER2_S8_VALUE_CHOICE_RULE_VERSION,
    )

    assert expert.audience == "EXPERT"
    assert expert.value_choice_provenance_ref == record.record_ref
    assert expert.selected_alternative_ref == record.selected_alternative_ref
    assert record.objective_provenance_ref in expert.expert_refs
    assert public.audience == "PUBLIC"
    assert public.selected_alternative_ref == record.selected_alternative_ref
    assert public.normative_admission_ref is None
    assert "scalar_welfare_authority" in public.authority_boundary.may_not_use_for
