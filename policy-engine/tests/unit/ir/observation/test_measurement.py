from __future__ import annotations

from datetime import date

import pytest
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    ObservationFamily,
    ObservationRecord,
    SourceConfidenceTier,
)
from polisyos.ir.observation.measurement import (
    IdentificationModeRouter,
    MeasurementRegistry,
    MeasurementTrustTier,
    RegimeCalendar,
    RegimeCalendarEntry,
    SchemaChangepoint,
    SchemaRegimeRegistry,
    SchemaRegimeSpec,
    ShockCalendar,
    ShockCalendarEntry,
)
from polisyos.ir.types import TimeFrequency


def _record(**overrides) -> ObservationRecord:
    payload = {
        "observation_id": "obs_measurement_2024_01",
        "family": ObservationFamily.LABOR_MARKET,
        "time_grain": TimeFrequency.MONTH,
        "period_start": date(2024, 1, 1),
        "period_end": date(2024, 1, 31),
        "entity_scope": EntityScope.CELL,
        "cell_id": "cell_kyiv_a",
        "metric_id": "employment_rate",
        "observed_value": 0.72,
        "unit": "share",
        "coverage_estimate": 0.82,
        "measurement_bias_flag": False,
        "censoring_mask": False,
        "trust_weight": 0.9,
        "lag_days_estimate": 5,
        "source_id": "admin_employment",
        "source_version": "2024.01",
        "regime_id": "wartime_2024",
        "shock_mask": False,
        "schema_regime_id": "employment_schema_v1",
        "identification_mode": IdentificationMode.PROXY_IDENTIFIED,
        "proxy_source_id": "administrative_employment",
        "source_confidence_tier": SourceConfidenceTier.VALIDATED,
    }
    payload.update(overrides)
    return ObservationRecord(**payload)


def test_measurement_registry_resolves_tiers_and_normalizes_extreme_trust() -> None:
    registry = MeasurementRegistry.default()

    authoritative = _record(
        observation_id="obs_authoritative",
        family=ObservationFamily.BUDGET_FLOWS,
        source_confidence_tier=SourceConfidenceTier.CORE,
        identification_mode=IdentificationMode.POINT_IDENTIFIED,
        proxy_source_id=None,
        coverage_estimate=0.95,
        trust_weight=5.0,
        metric_id="budget_flow",
    )
    proxy_record = _record()
    exploratory = _record(
        observation_id="obs_exploratory",
        identification_mode=IdentificationMode.POINT_IDENTIFIED,
        proxy_source_id=None,
        source_confidence_tier=SourceConfidenceTier.EXPLORATORY,
        trust_weight=0.5,
    )

    assert (
        registry.tier_for_record(authoritative) == MeasurementTrustTier.AUTHORITATIVE_HIGH_COVERAGE
    )
    assert registry.tier_for_record(proxy_record) == MeasurementTrustTier.DERIVED_PROXY
    assert registry.tier_for_record(exploratory) == MeasurementTrustTier.WEAK_ANCHOR
    assert registry.normalize_record_trust(authoritative) == pytest.approx(1.0)
    assert registry.proxy_mapping_for_family(ObservationFamily.LABOR_MARKET) is not None


def test_identification_mode_router_covers_all_families_and_falls_back_on_low_coverage() -> None:
    router = IdentificationModeRouter()
    routes = [
        router.route_family(family, coverage_estimate=1.0, explicit_mode=None)
        for family in ObservationFamily
    ]
    assert {route.family for route in routes} == set(ObservationFamily)

    fallback_route = router.route_record(
        _record(
            observation_id="obs_low_cov",
            coverage_estimate=0.2,
            censoring_mask=True,
            identification_mode=IdentificationMode.PROXY_IDENTIFIED,
        )
    )
    assert fallback_route.selected_mode == IdentificationMode.BOUNDS_ONLY
    assert fallback_route.fallback_triggered is True


def test_schema_regime_registry_and_calendars_detect_boundaries() -> None:
    registry = SchemaRegimeRegistry(
        regimes={
            "employment_schema_v1": SchemaRegimeSpec(
                schema_regime_id="employment_schema_v1",
                source_version="1.0",
                effective_start=date(2023, 1, 1),
                effective_end=date(2024, 1, 31),
            ),
            "employment_schema_v2": SchemaRegimeSpec(
                schema_regime_id="employment_schema_v2",
                source_version="2.0",
                effective_start=date(2024, 2, 1),
            ),
        },
        changepoints=[
            SchemaChangepoint(
                changepoint_id="employment_cp_2024_02",
                effective_date=date(2024, 2, 1),
                from_schema_regime_id="employment_schema_v1",
                to_schema_regime_id="employment_schema_v2",
            )
        ],
    )
    regime_calendar = RegimeCalendar(
        entries=[
            RegimeCalendarEntry(
                regime_id="wartime_2024", start_date=date(2024, 1, 1), end_date=date(2024, 12, 31)
            )
        ]
    )
    shock_calendar = ShockCalendar(
        entries=[
            ShockCalendarEntry(
                shock_id="shock_blackout", start_date=date(2024, 2, 1), end_date=date(2024, 2, 29)
            )
        ]
    )

    assert registry.is_boundary(
        schema_regime_id="employment_schema_v1",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
        time_grain=TimeFrequency.MONTH,
    )
    assert regime_calendar.is_boundary(
        regime_id="wartime_2024",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
        time_grain=TimeFrequency.MONTH,
    )
    assert shock_calendar.is_boundary(
        period_start=date(2024, 2, 1),
        period_end=date(2024, 2, 29),
        time_grain=TimeFrequency.MONTH,
    )
