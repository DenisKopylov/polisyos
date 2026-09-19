from __future__ import annotations

from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    ObservationPlan,
    ObservationShard,
)
from polisyos.data_forge.domains.catalog.batch.core_sources import transformers, validators
from polisyos.fabric.connectors.base import DatasetCapabilitySnapshot


def test_core_sources_validators_keep_year_window_behavior() -> None:
    assert validators._year_windows(2020, 2022, 2) == [(2020, 2021), (2022, 2022)]


def test_validator_resolves_transformer_dependency_without_facade_bootstrap(monkeypatch) -> None:
    monkeypatch.delattr(validators, "_to_iso3", raising=False)
    monkeypatch.setattr(transformers, "_to_iso3", lambda _country_code: "CANONICAL")
    shard = ObservationShard(
        shard_id="ilo-shard",
        plan=ObservationPlan(
            dataset_id="ilo-dataset",
            source="ilo",
            raw_variable="value",
            canonical_var="employment",
            connector_id="sdmx.source",
            profile_id="ilo_sdmx",
            request_dataset_id="DF_TEST",
            default_filters={},
            update_frequency="annual",
        ),
        country_code="UA",
        country_codes=("UA",),
        start_year=2022,
        end_year=2022,
        filters={"geo": ["UA"]},
    )
    snapshot = DatasetCapabilitySnapshot(
        source="ilo",
        dataset_id="DF_TEST",
        resolved_dataset_id="DF_TEST",
        allowed_positions={"geo": ("CANONICAL",)},
    )

    assert validators._shard_supported_by_capability(shard, snapshot=snapshot)


def test_core_sources_validators_keep_facade_compatibility() -> None:
    from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade

    assert facade._year_windows(2020, 2020, 2) == [(2020, 2020)]
