"""Behavioral witnesses for the DFI-02 core-sources API cutover."""

from __future__ import annotations

import asyncio

from polisyos.data_forge.domains.catalog.batch import pipeline
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CoreSourcesCompatibilityContext,
    CoreSourcesIngestStats,
    bind_core_sources_compatibility_context,
)
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.core_sources import api, loaders, transformers
from polisyos.fabric.connectors.base import DatasetCapabilitySnapshot


def test_pipeline_consumes_canonical_api_and_preserves_ingest_counters(
    monkeypatch, tmp_path
) -> None:
    observed: list[DatasetBatchConfig] = []

    async def _fake_ingest(config: DatasetBatchConfig) -> CoreSourcesIngestStats:
        observed.append(config)
        return CoreSourcesIngestStats(
            registry_datasets=4,
            variable_alignments=5,
            observations=6,
            observations_attempted=7,
            observations_inserted=6,
            observations_replaced=1,
            failures=2,
            completed_shards=3,
            deferred_shards=4,
            failed_shards=5,
        )

    monkeypatch.setattr(api, "run_core_sources_ingest_async", _fake_ingest)
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"core_sources_ingest"}),
    )

    stats = asyncio.run(pipeline.run_dataset_pipeline(config))

    assert observed == [config]
    assert stats.metrics["core_registry_datasets"] == 4
    assert stats.metrics["core_variable_alignments"] == 5
    assert stats.metrics["core_observations"] == 6
    assert stats.metrics["core_observations_attempted"] == 7
    assert stats.metrics["core_observations_inserted"] == 6
    assert stats.metrics["core_observations_replaced"] == 1
    assert stats.metrics["core_failures"] == 2


def test_leaf_dependencies_are_owner_bound_across_sequential_calls(monkeypatch) -> None:
    monkeypatch.delattr(loaders, "_to_iso3", raising=False)
    monkeypatch.setattr(transformers, "_to_iso3", lambda _country: "FIRST")
    assert loaders._bulk_country_values("ilo", ("UA",)) == ["FIRST"]

    monkeypatch.setattr(transformers, "_to_iso3", lambda _country: "SECOND")
    assert loaders._bulk_country_values("ilo", ("UA",)) == ["SECOND"]


def test_source_selection_filters_survive_canonical_transformer() -> None:
    snapshot = DatasetCapabilitySnapshot(
        source="ilo",
        dataset_id="DF_TEST",
        resolved_dataset_id="DF_TEST",
        dimension_order=("REF_AREA", "FREQ", "SEX"),
    )

    filters = transformers._canonicalize_observation_request_filters(
        source="ilo",
        filters={"geo": ["UA"], "sex": ["T"]},
        capability_snapshot=snapshot,
    )

    assert filters == {"sex": ["T"], "REF_AREA": ["UKR"]}


def test_facade_compatibility_probe_does_not_broadcast_to_leaves(monkeypatch) -> None:
    from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade

    marker = object()
    monkeypatch.setattr(facade, "_dfi02_probe_only", marker, raising=False)

    facade._sync_implementation_globals()

    assert "_dfi02_probe_only" not in api.__dict__
    assert "_dfi02_probe_only" not in loaders.__dict__
    assert "_dfi02_probe_only" not in transformers.__dict__


def test_facade_override_is_scoped_to_supported_loader_binding(monkeypatch) -> None:
    from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade

    original = transformers._to_iso3

    def replacement(_country: str) -> str:
        return "BOUND"

    monkeypatch.setattr(facade, "_to_iso3", replacement)

    assert facade._bulk_country_values("ilo", ("UA",)) == ["BOUND"]

    assert transformers._to_iso3 is original


def test_facade_override_does_not_mutate_owner_module_during_call(monkeypatch) -> None:
    from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade

    original = transformers._to_iso3

    def _replacement(_country: str) -> str:
        assert transformers._to_iso3 is original
        return "REQUEST"

    monkeypatch.setattr(facade, "_to_iso3", _replacement)

    assert facade._bulk_country_values("ilo", ("UA",)) == ["REQUEST"]


def test_overlapping_compatibility_contexts_keep_sibling_dependencies_isolated() -> None:
    original = transformers._to_iso3
    contexts = [
        CoreSourcesCompatibilityContext(
            bindings={
                (transformers.__name__, "_to_iso3"): lambda _country, label=label: label
            }
        )
        for label in ("REQUEST_A", "REQUEST_B")
    ]

    async def _run_siblings() -> list[list[str]]:
        ready = asyncio.Event()
        waiting = 0

        async def _load(context: CoreSourcesCompatibilityContext) -> list[str]:
            nonlocal waiting
            with bind_core_sources_compatibility_context(context):
                waiting += 1
                if waiting == 2:
                    ready.set()
                await ready.wait()
                return loaders._bulk_country_values("ilo", ("UA", "PL"))

        return await asyncio.gather(*(_load(context) for context in contexts))

    assert asyncio.run(_run_siblings()) == [
        ["REQUEST_A", "REQUEST_A"],
        ["REQUEST_B", "REQUEST_B"],
    ]
    assert transformers._to_iso3 is original
