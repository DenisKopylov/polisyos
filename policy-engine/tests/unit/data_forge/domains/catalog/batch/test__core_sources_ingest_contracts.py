from __future__ import annotations

from typing import Any, cast

from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as runtime
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CoreSourcesIngestStats,
    ObservationFetchPayload,
    ObservationInsertStats,
    ObservationPlan,
    ObservationShard,
    ObservationWriteItem,
)


def test_core_sources_ingest_contracts_are_reexported_from_runtime_module() -> None:
    assert runtime.CoreSourcesIngestStats is CoreSourcesIngestStats
    assert runtime.ObservationPlan is ObservationPlan
    assert runtime.ObservationWriteItem is ObservationWriteItem


def test_core_sources_ingest_contract_behaviors_are_characterized() -> None:
    stats = CoreSourcesIngestStats()
    stats.record_source_observations("who", 2)
    stats.record_source_observations("who", 3)
    assert stats.observations_by_source == {"who": 5}

    written = sum(
        [
            ObservationInsertStats(attempted=2, inserted=1, replaced=1),
            ObservationInsertStats(attempted=1, inserted=1, replaced=0),
        ],
        ObservationInsertStats(),
    )
    assert written == ObservationInsertStats(attempted=3, inserted=2, replaced=1)
    assert written.written == 3

    plan = ObservationPlan(
        dataset_id="dataset",
        source="who",
        raw_variable="raw",
        canonical_var="canonical",
        connector_id="who",
        profile_id="profile",
        request_dataset_id="request",
        default_filters={},
        update_frequency="annual",
    )
    shard = ObservationShard(
        shard_id="shard",
        plan=plan,
        country_code="USA",
        start_year=2020,
        end_year=2021,
        filters={},
    )
    item = ObservationWriteItem(
        shard=shard,
        payload=ObservationFetchPayload(rows=[{"value": 1}]),
        ack=cast("Any", object()),
    )

    assert item.row_count == 1
    assert item.estimated_bytes == len(b'[{"value":1}]')
