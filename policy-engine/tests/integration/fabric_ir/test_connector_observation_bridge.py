from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from polisyos.fabric.api import fabric_get_data
from polisyos.fabric.connectors.contracts import DataSchema, FieldSpec, SchemaType
from polisyos.ir.connectors import DataVersion, FetchResult, VersionStrategy
from polisyos.ir.model_layer.types import TimeFrequency
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    ObservationFamily,
    ObservationPanel,
    ObservationRecord,
    SourceConfidenceTier,
)

pytestmark = pytest.mark.integration

TESTS_ROOT = Path(__file__).resolve().parents[2]
REPLAY_FIXTURE = (
    TESTS_ROOT / "_data" / "fabric" / "shared" / "source_contracts" / "worldbank.wdi.generic.replay.json"
)


class _ReplayEntry:
    def __init__(self, *, source_contract_id: str) -> None:
        self.short_id = "worldbank.wdi"
        self.known_datasets = frozenset({source_contract_id})
        self.dataset_descriptors = ()
        self.default_config = {"mode": "replay"}


class _ReplayConnector:
    def __init__(self, replay: dict[str, Any]) -> None:
        self._replay = replay
        self.requests = []

    async def list_datasets(self, handle: object):
        del handle
        if False:
            yield None

    async def fetch(self, handle: object, request: object) -> FetchResult[object]:
        del handle
        self.requests.append(request)
        fetched_at = datetime(2026, 4, 27, tzinfo=UTC)
        return FetchResult(
            data=self._replay["normalized_sample_rows"],
            row_count=len(self._replay["normalized_sample_rows"]),
            schema_id=self._replay["source_contract_id"],
            schema_version="1.0.0",
            version=DataVersion(
                strategy=VersionStrategy.CONTENT_HASH,
                value=self._replay["replay_checksum"],
                timestamp=fetched_at,
                content_hash=self._replay["replay_checksum"],
            ),
            fetched_at=fetched_at,
            completeness=1.0,
            quality_flags=frozenset(),
        )


class _ReplayRegistry:
    def __init__(self, replay: dict[str, Any]) -> None:
        self.connector = _ReplayConnector(replay)
        self.entry = _ReplayEntry(source_contract_id=replay["source_contract_id"])

    def get(self, connector_id: str) -> _ReplayConnector:
        assert connector_id == self.entry.short_id
        return self.connector

    def get_entry(self, connector_id: str) -> _ReplayEntry:
        assert connector_id == self.entry.short_id
        return self.entry

    async def get_connection(self, connector_id: str, config: object) -> object:
        assert connector_id == self.entry.short_id
        assert config == self.entry.default_config
        return object()

    async def release_connection(self, connector_id: str, handle: object) -> None:
        del handle
        assert connector_id == self.entry.short_id

    def query_entries(self, *, capabilities: object | None = None) -> list[_ReplayEntry]:
        del capabilities
        return [self.entry]


def _schema_from_fetch_result(result: FetchResult[Any]) -> DataSchema:
    return DataSchema(
        schema_id=result.schema_id,
        version=result.schema_version,
        fields=(
            FieldSpec(name="country_code", data_type=SchemaType.STRING, nullable=False),
            FieldSpec(name="indicator_id", data_type=SchemaType.STRING, nullable=False),
            FieldSpec(name="year", data_type=SchemaType.INT64, nullable=False),
            FieldSpec(name="value", data_type=SchemaType.FLOAT64, nullable=False, unit="usd"),
        ),
        primary_key=("country_code", "indicator_id", "year"),
        grain_dims=("country_code", "indicator_id"),
        time_dimension="year",
        description="Integration replay schema projected from Fabric into IR.",
        source="worldbank.wdi",
        tags=frozenset({"phase5_2", "fabric_ir"}),
    )


def _observation_from_row(row: dict[str, Any], *, result: FetchResult[Any]) -> ObservationRecord:
    year = int(row["year"])
    return ObservationRecord(
        observation_id=f"obs.worldbank_wdi.{year}",
        family=ObservationFamily.MACRO_STATE,
        time_grain=TimeFrequency.YEAR,
        period_start=date(year, 1, 1),
        period_end=date(year, 12, 31),
        entity_scope=EntityScope.REGION,
        region_code=str(row["country_code"]),
        metric_id=str(row["indicator_id"]),
        observed_value=float(row["value"]),
        unit=str(row["unit"]),
        coverage_estimate=1.0,
        trust_weight=1.0,
        source_id=result.schema_id,
        source_version=result.schema_version,
        regime_id="fabric.replay.v1",
        schema_regime_id=result.schema_id,
        identification_mode=IdentificationMode.POINT_IDENTIFIED,
        source_confidence_tier=SourceConfidenceTier.VALIDATED,
        notes_json={"fabric_version": result.version.value},
    )


def test_fabric_connector_fetch_projects_to_ir_observation_and_schema_surface() -> None:
    replay = json.loads(REPLAY_FIXTURE.read_text())
    registry = _ReplayRegistry(replay)

    result = fabric_get_data(
        dataset_id=replay["source_contract_id"],
        connector_id=replay["connector_id"],
        constraints={"filters": {"country_code": [replay["normalized_sample_rows"][0]["country_code"]]}},
        registry=registry,
    )
    schema = _schema_from_fetch_result(result)
    panel = ObservationPanel(
        panel_id="panel.worldbank_wdi.generic",
        family=ObservationFamily.MACRO_STATE,
        time_grain=TimeFrequency.YEAR,
        records=[_observation_from_row(row, result=result) for row in result.data],
    )

    assert result.row_count == len(panel.records) == 1
    assert result.schema_id == "worldbank.wdi.generic"
    assert schema.field_names() == ["country_code", "indicator_id", "year", "value"]
    assert "value" in schema.to_jax_dtypes()
    assert panel.records[0].source_id == schema.schema_id
    assert panel.records[0].notes_json["fabric_version"] == replay["replay_checksum"]
    assert registry.connector.requests[0].include_schema is True
