from __future__ import annotations

import hashlib
import json
import math

import pytest
from pydantic import ValidationError

from polisyos.core.contracts import DataTrust, ValueOuterSet

# Captured from the pre-EMP-01 ValueOuterSet writer, before changing its rules.
# The historical point used a tolerance; the partial width rounded to zero.
_LEGACY_TINY_PARTIAL = (
    '{"representation":"interval_box","lower":[0.0],"upper":[1e-13],'
    '"statistical_lower":null,"statistical_upper":null,"coordinates":["x"],'
    '"identification_status":"partial","assumptions":["legacy"],'
    '"assumption_status":"externally_supported","calibration_scope":{},'
    '"data_trust":{"tier":"legacy_test","trust_cap":0.6,"trust_multiplier":0.6,'
    '"min_coverage":null,"max_coverage":null,"promotion_floor":null,'
    '"authority_ref":"legacy:test"},"world_model_record_ref":"legacy-world",'
    '"epoch":"legacy-epoch","representation_status":"certified",'
    '"solver_time_budget_ms":null,"width":[0.0]}'
)
_LEGACY_NEAR_POINT = (
    '{"representation":"interval_box","lower":[0.0],"upper":[1e-10],'
    '"statistical_lower":null,"statistical_upper":null,"coordinates":["x"],'
    '"identification_status":"point","assumptions":["legacy"],'
    '"assumption_status":"externally_supported","calibration_scope":{},'
    '"data_trust":{"tier":"legacy_test","trust_cap":0.6,"trust_multiplier":0.6,'
    '"min_coverage":null,"max_coverage":null,"promotion_floor":null,'
    '"authority_ref":"legacy:test"},"world_model_record_ref":"legacy-world",'
    '"epoch":"legacy-epoch","representation_status":"certified",'
    '"solver_time_budget_ms":null,"width":[1e-10]}'
)
_LEGACY_PROXY = (
    '{"representation":"interval_box","lower":[0.1],"upper":[0.4],'
    '"statistical_lower":null,"statistical_upper":null,"coordinates":["x"],'
    '"identification_status":"proxy","assumptions":["legacy"],'
    '"assumption_status":"externally_supported","calibration_scope":{},'
    '"data_trust":{"tier":"legacy_test","trust_cap":0.6,"trust_multiplier":0.6,'
    '"min_coverage":null,"max_coverage":null,"promotion_floor":null,'
    '"authority_ref":"legacy:test"},"world_model_record_ref":"legacy-world",'
    '"epoch":"legacy-epoch","representation_status":"certified",'
    '"solver_time_budget_ms":null,"width":[0.3]}'
)


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


def _numeric_case(lower: float, upper: float, mode: str = "proxy") -> ValueOuterSet:
    return ValueOuterSet.interval_box(
        coordinates=("x",),
        lower=(lower,),
        upper=(upper,),
        identification_mode=mode,
        assumptions=("declared",),
        assumption_status="externally_supported",
        calibration_scope={"measurement_unit": "test-unit"},
        data_trust=_trust(),
        world_model_record_ref="world_model_record_test",
        epoch="epoch",
        representation_status="certified",
    )


def test_exact_numeric_profile_survives_scaling_and_preserves_distinct_floats() -> None:
    base = _numeric_case(0.0, 1e-6)
    scaled = _numeric_case(0.0, 1e-10)
    tiny = _numeric_case(0.0, 1e-13, "partial")
    negative = _numeric_case(-1e-10, 0.0)

    assert base.width == (1e-6,)
    assert scaled.width == (1e-10,)
    assert math.isclose(scaled.width[0], base.width[0] * 1e-4, rel_tol=1e-15)
    assert tiny.width == (1e-13,)
    assert negative.width == (1e-10,)
    assert base.numerical_profile == "policyos.value_outer_set.numeric.v2"
    assert ValueOuterSet.from_persisted_payload(scaled.model_dump_json()) == scaled
    children, metadata = tiny.tree_flatten()
    assert ValueOuterSet.tree_unflatten(metadata, children) == tiny
    with pytest.raises(ValueError, match="bounded_identification_requires_nonzero_interval"):
        _numeric_case(2.0, 2.0)

    next_float = math.nextafter(1.0, math.inf)
    following_float = math.nextafter(next_float, math.inf)
    first = _numeric_case(1.0, next_float)
    second = _numeric_case(next_float, following_float)
    assert first.width == second.width
    assert first.canonical_payload() != second.canonical_payload()


def test_exact_numeric_profile_rejects_width_overflow_before_persistence() -> None:
    control = _numeric_case(-1e100, 1e100)
    assert control.width == (2e100,)
    assert ValueOuterSet.from_persisted_payload(control.model_dump_json()) == control
    with pytest.raises(ValueError, match="value_outer_set_width_non_finite"):
        _numeric_case(-1e308, 1e308)


def test_exact_numeric_profile_checks_the_original_width_number() -> None:
    value_set = _numeric_case(0.0, float(2**53))
    payload = value_set.model_dump(mode="json")
    assert ValueOuterSet.from_persisted_payload(payload) == value_set
    # A JSON integer may have greater precision than a binary64 float.
    payload["width"] = [2**53]
    assert ValueOuterSet.from_persisted_payload(payload) == value_set
    for invalid in (2**53 + 1, 10**400, True, "9007199254740992"):
        payload["width"] = [invalid]
        with pytest.raises(ValueError, match="value_outer_set_width_tampered"):
            ValueOuterSet.from_persisted_payload(payload)


def test_historical_width_coercion_remains_readable_and_rejects_overflow() -> None:
    payload = json.loads(_LEGACY_PROXY)
    payload["width"] = ["0.3"]
    assert ValueOuterSet.from_persisted_payload(payload).width == (0.3,)
    payload["width"] = [10**400]
    with pytest.raises(ValueError, match="value_outer_set_width_tampered"):
        ValueOuterSet.from_persisted_payload(payload)


@pytest.mark.parametrize(
    ("payload", "canonical_sha256"),
    [
        (_LEGACY_TINY_PARTIAL, "58bf40598508218d41ab7e5f587a77980e1711492beed13c49230cd3df3ff862"),
        (_LEGACY_NEAR_POINT, "2952c75fee793840144263ebed9c047208a8752ed73de1d3e2af6257ec272019"),
        (_LEGACY_PROXY, "ba4d2d8964905519cd4ae94bc5b26f68c290a07f48e70b0754e16bcaa46ae490"),
    ],
    ids=["tiny-partial", "near-point", "proxy"],
)
def test_historical_numeric_profile_replays_exact_bytes_without_current_promotion(
    payload: str,
    canonical_sha256: str,
) -> None:
    restored = ValueOuterSet.from_persisted_payload(payload)
    assert restored.numerical_profile is None
    assert restored.model_dump_json() == payload
    canonical = json.dumps(restored.canonical_payload(), sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == canonical_sha256
    assert restored.promotion_decision().promotable is False
    assert "historical_numerical_profile" in restored.promotion_decision().reasons
    children, metadata = restored.tree_flatten()
    assert ValueOuterSet.tree_unflatten(metadata, children) == restored

    tampered = json.loads(payload)
    tampered["width"][0] += 1.0
    with pytest.raises(ValueError, match="value_outer_set_width_tampered"):
        ValueOuterSet.from_persisted_payload(tampered)
    tampered = json.loads(payload)
    tampered["upper"][0] += 1.0
    with pytest.raises(ValueError, match="value_outer_set_width_tampered"):
        ValueOuterSet.from_persisted_payload(tampered)


def test_numeric_profiles_do_not_fall_back_or_upgrade_historical_point() -> None:
    legacy = json.loads(_LEGACY_NEAR_POINT)
    legacy_without_width = {key: value for key, value in legacy.items() if key != "width"}
    historical = ValueOuterSet.from_historical_fields(legacy_without_width)
    assert historical.numerical_profile is None
    assert historical.width == (1e-10,)
    assert not historical.promotion_decision().promotable
    with pytest.raises(ValueError, match="point_identified_requires_tight_interval"):
        ValueOuterSet.model_validate(legacy_without_width)

    new = _numeric_case(0.1, 0.4)
    tampered = new.model_dump(mode="json")
    tampered["width"] = [0.3]  # old rounding; v2 must not retry the old rule
    with pytest.raises(ValueError, match="value_outer_set_width_tampered"):
        ValueOuterSet.from_persisted_payload(tampered)
    tampered["numerical_profile"] = "unknown"
    with pytest.raises(ValueError, match="value_outer_set_numerical_profile_invalid"):
        ValueOuterSet.from_persisted_payload(tampered)


def test_selected_profile_rejects_downgrade_even_when_checksums_match() -> None:
    new = _numeric_case(0.0, 1e-6)
    payload = new.model_dump(mode="json")
    assert (
        ValueOuterSet.from_persisted_payload(
            payload,
            expected_numerical_profile="policyos.value_outer_set.numeric.v2",
        )
        == new
    )
    downgraded = dict(payload)
    downgraded.pop("numerical_profile")
    # Both width algorithms happen to return 1e-6. The selected profile, not
    # a matching checksum, prevents this wire from masquerading as the v2 one.
    assert not ValueOuterSet.from_persisted_payload(downgraded).promotion_decision().promotable
    with pytest.raises(ValueError, match="value_outer_set_numerical_profile_mismatch"):
        ValueOuterSet.from_persisted_payload(
            downgraded,
            expected_numerical_profile="policyos.value_outer_set.numeric.v2",
        )
    with pytest.raises(ValueError, match="value_outer_set_numerical_profile_mismatch"):
        ValueOuterSet.from_persisted_payload(payload, expected_numerical_profile="historical")


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
    assert value_set.width == (15.0, 0.4 - 0.1)
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
    assert restored.width == (15.0, 0.4 - 0.1)
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


def test_value_outer_set_preserves_native_statistical_bounds_separately() -> None:
    identified = ValueOuterSet.interval_box(
        coordinates=("source_reported_value",),
        lower=(4.0,),
        upper=(4.0,),
        statistical_lower=(1.0,),
        statistical_upper=(10.0,),
        identification_mode="point_identified",
        assumptions=("source_reported_estimator",),
        assumption_status="externally_supported",
        calibration_scope={"measurement": "source_reported"},
        data_trust=_trust(),
        world_model_record_ref="world_model_record_test",
        epoch="source_reported_epoch",
        representation_status="certified",
    )
    same_identification_without_statistics = ValueOuterSet.interval_box(
        coordinates=("source_reported_value",),
        lower=(4.0,),
        upper=(4.0,),
        identification_mode="point_identified",
        assumptions=("source_reported_estimator",),
        assumption_status="externally_supported",
        calibration_scope={"measurement": "source_reported"},
        data_trust=_trust(),
        world_model_record_ref="world_model_record_test",
        epoch="source_reported_epoch",
        representation_status="certified",
    )

    assert identified.lower == (4.0,)
    assert identified.upper == (4.0,)
    assert identified.statistical_lower == (1.0,)
    assert identified.statistical_upper == (10.0,)
    assert (
        identified.promotion_decision()
        == same_identification_without_statistics.promotion_decision()
    )
    assert identified.canonical_payload()["statistical_lower"] == ["1"]
    assert identified.canonical_payload()["statistical_upper"] == ["10"]
    assert ValueOuterSet.from_persisted_payload(identified.model_dump_json()) == identified


def test_value_outer_set_rejects_incomplete_or_misaligned_statistical_bounds() -> None:
    common = {
        "coordinates": ("first", "second"),
        "lower": (4.0, 5.0),
        "upper": (4.0, 5.0),
        "identification_mode": "point_identified",
        "assumptions": ("source_reported_estimator",),
        "assumption_status": "externally_supported",
        "calibration_scope": {"measurement": "source_reported"},
        "data_trust": _trust(),
        "world_model_record_ref": "world_model_record_test",
        "epoch": "source_reported_epoch",
        "representation_status": "certified",
    }

    with pytest.raises(ValueError, match="statistical_bounds_must_be_supplied_together"):
        ValueOuterSet.interval_box(
            **common,
            statistical_lower=(1.0, 2.0),
        )

    with pytest.raises(ValueError, match="statistical_bounds_must_align_with_coordinates"):
        ValueOuterSet.interval_box(
            **common,
            statistical_lower=(1.0,),
            statistical_upper=(10.0,),
        )


def test_value_outer_set_rejects_reversed_statistical_bounds() -> None:
    with pytest.raises(ValueError, match="statistical_interval_lower_must_be_lte_upper"):
        ValueOuterSet.interval_box(
            coordinates=("source_reported_value",),
            lower=(4.0,),
            upper=(4.0,),
            statistical_lower=(10.0,),
            statistical_upper=(1.0,),
            identification_mode="point_identified",
            assumptions=("source_reported_estimator",),
            assumption_status="externally_supported",
            calibration_scope={"measurement": "source_reported"},
            data_trust=_trust(),
            world_model_record_ref="world_model_record_test",
            epoch="source_reported_epoch",
            representation_status="certified",
        )


def test_value_outer_set_proxy_mode_requires_nonzero_interval() -> None:
    """Proxy identification cannot masquerade as a point estimate."""

    with pytest.raises(
        ValueError,
        match="bounded_identification_requires_nonzero_interval",
    ):
        ValueOuterSet.interval_box(
            coordinates=("disposable_income",),
            lower=(42.0,),
            upper=(42.0,),
            identification_mode="proxy_identified",
            assumptions=("proxy_width_must_remain_visible",),
            assumption_status="declared",
            calibration_scope={"measurement": "household_distribution"},
            data_trust=_trust(),
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
                "repo://l5/measurement_registry.json#/trust_tiers/synthetic_below_min_coverage"
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
