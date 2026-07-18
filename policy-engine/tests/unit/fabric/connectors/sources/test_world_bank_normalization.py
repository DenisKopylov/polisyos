"""Exact behavioral contract for the canonical World Bank row projection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd
import pytest

from polisyos.fabric import connectors
from polisyos.fabric.connectors.sources import (
    normalize_worldbank_records as sources_normalize_worldbank_records,
)
from polisyos.fabric.connectors.sources import world_bank
from polisyos.fabric.connectors.sources.world_bank import (
    WorldBankConnector,
    normalize_worldbank_records,
)

_INDICATOR_ID = "GC.BAL.CASH.GD.ZS"


def _record() -> dict[str, Any]:
    return {
        "countryiso3code": "UKR",
        "country": {"id": "UA", "value": "Ukraine"},
        "indicator": {
            "id": _INDICATOR_ID,
            "value": "Cash surplus/deficit (% of GDP)",
        },
        "date": "2024",
        "value": "-17.1",
        "unit": "% of GDP",
        "decimal": "1",
    }


def _project(record: Mapping[str, Any]) -> dict[str, object]:
    frame = normalize_worldbank_records([record], _INDICATOR_ID)
    assert list(frame.columns) == [
        "country_code",
        "country_name",
        "indicator_id",
        "indicator_name",
        "year",
        "value",
        "unit",
        "decimal",
    ]
    assert len(frame) == 1
    return frame.iloc[0].to_dict()


def test_worldbank_projection_owns_the_exact_eight_field_mapping() -> None:
    assert _project(_record()) == {
        "country_code": "UKR",
        "country_name": "Ukraine",
        "indicator_id": _INDICATOR_ID,
        "indicator_name": "Cash surplus/deficit (% of GDP)",
        "year": 2024,
        "value": -17.1,
        "unit": "% of GDP",
        "decimal": 1,
    }


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ({"value": "-18.25"}, {"value": -18.25}),
        ({"unit": "percentage points"}, {"unit": "percentage points"}),
        ({"decimal": "3"}, {"decimal": 3}),
        (
            {
                "country": {"id": "UA", "value": "Україна"},
                "indicator": {"id": _INDICATOR_ID, "value": "Government balance"},
            },
            {"country_name": "Україна", "indicator_name": "Government balance"},
        ),
    ],
)
def test_worldbank_projection_preserves_decisive_value_unit_decimal_and_names(
    mutation: dict[str, object],
    expected: dict[str, object],
) -> None:
    projected = _project({**_record(), **mutation})
    assert {key: projected[key] for key in expected} == expected


def test_worldbank_projection_preserves_nulls_without_response_repair() -> None:
    projected = _project(
        {
            "countryiso3code": None,
            "country": {"id": "UA", "value": None},
            "indicator": None,
            "date": "not-a-year",
            "value": None,
            "unit": None,
            "decimal": None,
        }
    )

    assert projected == {
        "country_code": "UA",
        "country_name": None,
        "indicator_id": _INDICATOR_ID,
        "indicator_name": None,
        "year": None,
        "value": None,
        "unit": None,
        "decimal": None,
    }


def test_worldbank_projection_returns_the_declared_schema_for_no_rows() -> None:
    frame = normalize_worldbank_records([], _INDICATOR_ID)

    assert frame.empty
    assert list(frame.columns) == [
        "country_code",
        "country_name",
        "indicator_id",
        "indicator_name",
        "year",
        "value",
        "unit",
        "decimal",
    ]


def test_worldbank_connector_calls_the_shared_projection_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[Mapping[str, Any]], str]] = []
    expected = pd.DataFrame([{"sentinel": "owner-result"}])

    def _owner(
        records: list[Mapping[str, Any]],
        indicator_id: str,
    ) -> pd.DataFrame:
        calls.append((records, indicator_id))
        return expected

    monkeypatch.setattr(world_bank, "normalize_worldbank_records", _owner)

    actual = WorldBankConnector._normalize_records([_record()], _INDICATOR_ID)

    assert actual is expected
    assert calls == [([_record()], _INDICATOR_ID)]


def test_worldbank_projection_is_exported_through_stable_facades() -> None:
    assert connectors.normalize_worldbank_records is normalize_worldbank_records
    assert sources_normalize_worldbank_records is normalize_worldbank_records
