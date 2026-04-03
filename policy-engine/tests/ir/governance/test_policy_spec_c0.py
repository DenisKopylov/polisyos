from __future__ import annotations

from decimal import Decimal

from polisyos.ir.governance.policy_spec import (
    InterventionSpec,
    PolicySpec,
    TemporalInterventionSequence,
)
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.observation.contracts import IdentificationMode, StrategicResponseChannel
from polisyos.ir.types import SelectorOperator


def _target_selector() -> SelectorPredicate:
    return SelectorPredicate(
        field="id",
        operator=SelectorOperator.EQUALS,
        value="all",
    )


def test_legacy_policy_spec_payload_still_validates_unchanged() -> None:
    policy = PolicySpec(
        policy_id="legacy_policy",
        interventions=[
            InterventionSpec(
                intervention_id="tax_cut",
                kind="income_tax",
                target=_target_selector(),
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params={"rate": Decimal("0.1")},
            )
        ],
    )

    intervention = policy.interventions[0]
    assert intervention.identification_mode is None
    assert intervention.strategic_response_expected is False
    assert intervention.transmission_channels == []


def test_new_intervention_metadata_round_trips_through_json() -> None:
    spec = InterventionSpec(
        intervention_id="proc_threshold_change",
        kind="procurement_threshold_change",
        target=_target_selector(),
        schedule=ScheduleSpec(start_step=1, duration_steps=3),
        params={"threshold": Decimal("500000")},
        lex_provision_ref="lex.procurement.thresholds.2023",
        target_population_type="public_buyers",
        target_sector_ids=["health"],
        target_region_ids=["UA-30"],
        measurement_expectations={"expected_metric": "procurement_share"},
        identification_mode=IdentificationMode.INTERFERENCE_AWARE,
        strategic_response_expected=True,
        transmission_channels=[
            StrategicResponseChannel.PROCUREMENT_CHANNEL,
            StrategicResponseChannel.COMPLIANCE_CHANNEL,
        ],
    )

    restored = InterventionSpec.model_validate_json(spec.model_dump_json())
    assert restored.model_dump(mode="json") == spec.model_dump(mode="json")


def test_schedule_remains_canonical_timing_surface() -> None:
    spec = InterventionSpec(
        intervention_id="subsidy_rule",
        kind="targeted_subsidy_rule",
        target=_target_selector(),
        schedule=ScheduleSpec(start_step=5, duration_steps=2),
        params={"amount": Decimal("2500")},
    )

    dumped = spec.model_dump(mode="json")
    assert "schedule" in dumped
    assert "activation_date" not in dumped
    assert "deactivation_date" not in dumped


def test_temporal_intervention_sequence_schema_supports_dtr_sequences() -> None:
    sequence = TemporalInterventionSequence(
        sequence_id="ua_proc_seq",
        dynamic_intervention_id="dynamic_procurement_response",
        strategic_response_expected=True,
        transmission_channels=[StrategicResponseChannel.PROCUREMENT_CHANNEL],
        steps=[
            {
                "step_id": "s1",
                "effective_date": "2022-03",
                "intervention_id": "procurement_emergency_rules",
            },
            {
                "step_id": "s2",
                "effective_date": "2023-06",
                "intervention_id": "procurement_threshold_change",
            },
        ],
    )

    assert sequence.identification_mode == IdentificationMode.SEQUENTIAL
    assert len(sequence.steps) == 2
