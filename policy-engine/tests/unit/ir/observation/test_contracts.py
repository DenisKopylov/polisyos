from __future__ import annotations

from datetime import date

import pytest
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    MultiplexGraphLayerId,
    ObservationFamily,
    ObservationPanel,
    ObservationRecord,
    SourceConfidenceTier,
    StrategicResponseChannel,
)
from polisyos.ir.types import TimeFrequency
from pydantic import ValidationError


def _record(**overrides) -> ObservationRecord:
    payload = {
        "observation_id": "obs_budget_2024_01",
        "family": ObservationFamily.BUDGET_FLOWS,
        "time_grain": TimeFrequency.MONTH,
        "period_start": date(2024, 1, 1),
        "period_end": date(2024, 1, 31),
        "entity_scope": EntityScope.CELL,
        "cell_id": "cell_kyiv_it",
        "region_code": "UA-30",
        "sector_id": "it",
        "metric_id": "budget_outflow",
        "observed_value": 125.0,
        "unit": "uah_million",
        "coverage_estimate": 0.9,
        "measurement_bias_flag": False,
        "censoring_mask": False,
        "trust_weight": 0.8,
        "lag_days_estimate": 7,
        "source_id": "spending_gov",
        "source_version": "2024.01",
        "regime_id": "wartime_2024",
        "shock_mask": False,
        "schema_regime_id": "spending_schema_v3",
        "identification_mode": IdentificationMode.POINT_IDENTIFIED,
        "source_confidence_tier": SourceConfidenceTier.CORE,
        "notes_json": {"currency": "UAH"},
    }
    payload.update(overrides)
    return ObservationRecord(**payload)


def test_observation_record_validates_proxy_source_requirement() -> None:
    with pytest.raises(ValidationError):
        _record(
            observation_id="obs_proxy",
            identification_mode=IdentificationMode.PROXY_IDENTIFIED,
            proxy_source_id=None,
        )

    record = _record(
        observation_id="obs_proxy_ok",
        identification_mode=IdentificationMode.PROXY_IDENTIFIED,
        proxy_source_id="tax_debt_proxy",
    )
    assert record.proxy_source_id == "tax_debt_proxy"


def test_observation_record_rejects_non_finite_numeric_values() -> None:
    with pytest.raises(ValidationError):
        _record(observation_id="obs_nan", observed_value=float("nan"))
    with pytest.raises(ValidationError):
        _record(observation_id="obs_inf", trust_weight=float("inf"))


def test_observation_panel_enforces_family_consistency() -> None:
    first = _record(observation_id="obs_a")
    second = _record(
        observation_id="obs_b",
        family=ObservationFamily.PROCUREMENT_FLOWS,
        metric_id="proc_contracts",
    )

    with pytest.raises(ValidationError):
        ObservationPanel(
            panel_id="panel_budget",
            family=ObservationFamily.BUDGET_FLOWS,
            time_grain=TimeFrequency.MONTH,
            records=[first, second],
        )


def test_observation_contracts_serialize_lowercase_enum_values() -> None:
    record = _record(
        observation_id="obs_json",
        identification_mode=IdentificationMode.PROXY_IDENTIFIED,
        proxy_source_id="tax_debt_proxy",
        source_confidence_tier=SourceConfidenceTier.EXPLORATORY,
    )
    payload = record.model_dump(mode="json")
    assert payload["identification_mode"] == "proxy_identified"
    assert payload["source_confidence_tier"] == "exploratory"


def test_supporting_enums_match_blueprint_vocabularies() -> None:
    assert [member.value for member in MultiplexGraphLayerId] == [
        "budget",
        "procurement",
        "trade",
        "distress",
        "public_service",
    ]
    assert [member.value for member in StrategicResponseChannel] == [
        "budget_channel",
        "procurement_channel",
        "labor_channel",
        "trade_channel",
        "household_income_channel",
        "compliance_channel",
    ]
