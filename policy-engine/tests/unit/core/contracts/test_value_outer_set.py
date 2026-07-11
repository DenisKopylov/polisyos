from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.contracts import DataTrust, ValueOuterSet


def _trust() -> DataTrust:
    return DataTrust(
        tier="derived_proxy",
        trust_cap=0.6,
        trust_multiplier=0.6,
        min_coverage=0.35,
        max_coverage=0.85,
        promotion_floor=0.5,
        authority_ref="repo://l5/measurement_registry.json#/trust_tiers/derived_proxy",
    )


def test_value_outer_set_interval_box_derives_width_and_l5_identification_status() -> None:
    value_set = ValueOuterSet.interval_box(
        coordinates=("disposable_income", "poverty_rate"),
        lower=(10.0, 0.1),
        upper=(25.0, 0.4),
        identification_mode="proxy_identified",
        assumptions=("d3_bias_corrected_bounds",),
        assumption_status="externally_supported",
        calibration_scope={
            "population": "ukraine_household_cells",
            "regime": "ukraine_schema_v2",
            "measurement": "household_distribution",
        },
        data_trust=_trust(),
        world_model_record_ref="world_model_record_test",
        epoch="ukraine_schema_v2",
        representation_status="certified",
    )

    assert value_set.representation == "interval_box"
    assert value_set.identification_status == "proxy"
    assert value_set.width == (15.0, 0.3)
    decision = value_set.promotion_decision()
    assert decision.promotable is True
    assert decision.capped_decision_grade == "low"
    assert decision.trust_score == 0.6
    assert value_set.promotion_decision().promotable is True


def test_value_outer_set_persisted_payload_round_trips_derived_width_checksum() -> None:
    value_set = ValueOuterSet.interval_box(
        coordinates=("disposable_income", "poverty_rate"),
        lower=(10.0, 0.1),
        upper=(25.0, 0.4),
        identification_mode="proxy_identified",
        assumptions=("d3_bias_corrected_bounds",),
        assumption_status="externally_supported",
        calibration_scope={"measurement": "household_distribution"},
        data_trust=_trust(),
        world_model_record_ref="world_model_record_test",
        epoch="ukraine_schema_v2",
        representation_status="certified",
    )

    restored = ValueOuterSet.from_persisted_payload(value_set.model_dump_json())

    assert restored == value_set
    assert restored.width == (15.0, 0.3)
    children, aux_data = value_set.tree_flatten()
    assert ValueOuterSet.tree_unflatten(aux_data, children) == value_set


def test_value_outer_set_persisted_payload_rejects_tampered_width() -> None:
    value_set = ValueOuterSet.interval_box(
        coordinates=("disposable_income",),
        lower=(10.0,),
        upper=(25.0,),
        identification_mode="proxy_identified",
        assumptions=("d3_bias_corrected_bounds",),
        assumption_status="externally_supported",
        calibration_scope={"measurement": "household_distribution"},
        data_trust=_trust(),
        world_model_record_ref="world_model_record_test",
        epoch="ukraine_schema_v2",
        representation_status="certified",
    )
    payload = value_set.model_dump(mode="json")
    payload["width"] = [14.0]
    payload["representation_status"] = "bogus"

    with pytest.raises(ValueError, match="value_outer_set_width_tampered"):
        ValueOuterSet.from_persisted_payload(payload)

    payload["representation_status"] = "certified"
    payload["width"] = 15.0
    with pytest.raises(ValueError, match="value_outer_set_width_tampered"):
        ValueOuterSet.from_persisted_payload(payload)

    payload.pop("width")
    with pytest.raises(ValueError, match="value_outer_set_persisted_width_missing"):
        ValueOuterSet.from_persisted_payload(payload)


@pytest.mark.parametrize(
    ("lower", "upper"),
    [
        ((float("nan"),), (1.0,)),
        ((0.0,), (float("inf"),)),
        ((float("-inf"),), (1.0,)),
    ],
)
def test_value_outer_set_rejects_non_finite_bounds_before_persistence(
    lower: tuple[float, ...],
    upper: tuple[float, ...],
) -> None:
    with pytest.raises(ValueError, match="value_outer_set_bounds_non_finite"):
        ValueOuterSet.interval_box(
            coordinates=("disposable_income",),
            lower=lower,
            upper=upper,
            identification_mode="proxy_identified",
            assumptions=("d3_bias_corrected_bounds",),
            assumption_status="externally_supported",
            calibration_scope={"measurement": "household_distribution"},
            data_trust=_trust(),
            world_model_record_ref="world_model_record_test",
            epoch="ukraine_schema_v2",
            representation_status="certified",
        )


def test_value_outer_set_live_boundary_rejects_even_empty_supplied_width() -> None:
    value_set = ValueOuterSet.interval_box(
        coordinates=("disposable_income",),
        lower=(10.0,),
        upper=(25.0,),
        identification_mode="proxy_identified",
        assumptions=("d3_bias_corrected_bounds",),
        assumption_status="externally_supported",
        calibration_scope={"measurement": "household_distribution"},
        data_trust=_trust(),
        world_model_record_ref="world_model_record_test",
        epoch="ukraine_schema_v2",
        representation_status="certified",
    )
    payload = value_set.model_dump(mode="json")
    payload["width"] = []

    with pytest.raises(ValueError, match="value_outer_set_width_supplied_not_derived"):
        ValueOuterSet.model_validate(payload)


def test_value_outer_set_point_mode_requires_tight_interval_generically() -> None:
    value_set = ValueOuterSet.interval_box(
        coordinates=("disposable_income",),
        lower=(42.0,),
        upper=(42.0,),
        identification_mode="point_identified",
        assumptions=("l5_point_identified",),
        assumption_status="externally_supported",
        calibration_scope={"measurement": "budget_flows"},
        data_trust=DataTrust(
            tier="authoritative_high_coverage",
            trust_cap=1.0,
            trust_multiplier=1.0,
            min_coverage=0.9,
            max_coverage=1.0,
            promotion_floor=0.5,
            authority_ref="repo://l5/measurement_registry.json#/trust_tiers/authoritative_high_coverage",
        ),
        world_model_record_ref="world_model_record_test",
        epoch="ukraine_schema_v2",
        representation_status="certified",
    )

    assert value_set.identification_status == "point"
    assert value_set.width == (0.0,)
    assert value_set.promotion_decision().capped_decision_grade == "high"

    with pytest.raises(ValueError, match="point_identified_requires_tight_interval"):
        ValueOuterSet.interval_box(
            coordinates=("disposable_income",),
            lower=(41.0,),
            upper=(42.0,),
            identification_mode="point_identified",
            assumptions=("bad_point_width",),
            assumption_status="declared",
            calibration_scope={"measurement": "budget_flows"},
            data_trust=value_set.data_trust,
            world_model_record_ref="world_model_record_test",
            epoch="ukraine_schema_v2",
            representation_status="certified",
        )


def test_value_outer_set_non_certified_cannot_mint_promotion_value() -> None:
    search_only = ValueOuterSet.interval_box(
        coordinates=("disposable_income",),
        lower=(1.0,),
        upper=(3.0,),
        identification_mode="proxy_identified",
        assumptions=("search_probe",),
        assumption_status="declared",
        calibration_scope={"measurement": "household_distribution"},
        data_trust=_trust(),
        world_model_record_ref="world_model_record_test",
        epoch="ukraine_schema_v2",
        representation_status="search_only",
    )

    assert search_only.promotion_decision().promotable is False
    decision = search_only.promotion_decision()
    assert decision.promotable is False
    assert "representation_not_certified" in decision.reasons

    with pytest.raises(ValidationError):
        ValueOuterSet.model_validate(
            {
                **search_only.model_dump(mode="json", exclude={"width"}),
                "representation_status": "maybe",
            }
        )


def test_value_outer_set_data_trust_gates_promotion_value_generically() -> None:
    def _value_with_trust(data_trust: DataTrust) -> ValueOuterSet:
        return ValueOuterSet.interval_box(
            coordinates=("disposable_income",),
            lower=(1.0,),
            upper=(3.0,),
            identification_mode="proxy_identified",
            assumptions=("d3_bias_corrected_bounds",),
            assumption_status="externally_supported",
            calibration_scope={"measurement": "synthetic_l5_family"},
            data_trust=data_trust,
            world_model_record_ref="world_model_record_test",
            epoch="synthetic_epoch",
            representation_status="certified",
        )

    zero = _value_with_trust(
        DataTrust(
            tier="synthetic_zero",
            trust_cap=0.0,
            trust_multiplier=1.0,
            min_coverage=0.0,
            max_coverage=1.0,
            promotion_floor=0.5,
            authority_ref="repo://l5/measurement_registry.json#/trust_tiers/synthetic_zero",
        )
    ).promotion_decision()
    weak = _value_with_trust(
        DataTrust(
            tier="synthetic_weak",
            trust_cap=0.25,
            trust_multiplier=0.6,
            min_coverage=0.0,
            max_coverage=1.0,
            promotion_floor=0.5,
            authority_ref="repo://l5/measurement_registry.json#/trust_tiers/synthetic_weak",
        )
    ).promotion_decision()
    below_min = _value_with_trust(
        DataTrust(
            tier="synthetic_below_min_coverage",
            trust_cap=0.6,
            trust_multiplier=0.9,
            min_coverage=0.7,
            max_coverage=1.0,
            promotion_floor=0.5,
            authority_ref=(
                "repo://l5/measurement_registry.json#/trust_tiers/"
                "synthetic_below_min_coverage"
            ),
        )
    ).promotion_decision()
    medium = _value_with_trust(
        DataTrust(
            tier="synthetic_medium",
            trust_cap=0.85,
            trust_multiplier=0.95,
            min_coverage=0.5,
            max_coverage=1.0,
            promotion_floor=0.5,
            authority_ref="repo://l5/measurement_registry.json#/trust_tiers/synthetic_medium",
        )
    ).promotion_decision()
    high = _value_with_trust(
        DataTrust(
            tier="synthetic_high",
            trust_cap=1.0,
            trust_multiplier=1.0,
            min_coverage=0.9,
            max_coverage=1.0,
            promotion_floor=0.5,
            authority_ref="repo://l5/measurement_registry.json#/trust_tiers/synthetic_high",
        )
    ).promotion_decision()

    assert zero.promotable is False
    assert "data_trust_zero" in zero.reasons
    assert weak.promotable is False
    assert "data_trust_below_promotion_floor" in weak.reasons
    assert below_min.promotable is False
    assert "data_trust_below_l5_min_coverage" in below_min.reasons
    assert medium.promotable is True
    assert medium.capped_decision_grade == "medium"
    assert high.promotable is True
    assert high.capped_decision_grade == "high"


def test_value_outer_set_compare_is_conservative_and_unknown_on_timeout() -> None:
    baseline = ValueOuterSet.interval_box(
        coordinates=("metric",),
        lower=(10.0,),
        upper=(20.0,),
        identification_mode="proxy_identified",
        assumptions=("d3_bias_corrected_bounds",),
        assumption_status="externally_supported",
        calibration_scope={"measurement": "household_distribution"},
        data_trust=_trust(),
        world_model_record_ref="world_model_record_test",
        epoch="ukraine_schema_v2",
        representation_status="certified",
    )
    dominated = baseline.model_copy(update={"lower": (0.0,), "upper": (9.0,)})
    overlapping = baseline.model_copy(update={"lower": (15.0,), "upper": (25.0,)})

    assert baseline.compare(dominated) == "dominates"
    assert baseline.compare(overlapping) == "incomparable"
    assert baseline.compare(dominated, force_timeout=True) == "unknown"
