"""Behavioral witnesses for the DFI-02 core-sources API cutover."""

from __future__ import annotations

import asyncio
import json

from polisyos.data_forge.domains.catalog.batch import pipeline
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CoreSourcesIngestStats,
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

    def replacement(_country):
        return "BOUND"

    monkeypatch.setattr(facade, "_to_iso3", replacement)

    assert facade._bulk_country_values("ilo", ("UA",)) == ["BOUND"]

    assert transformers._to_iso3 is original


def test_concurrent_facade_ingests_keep_their_captured_overrides(monkeypatch, tmp_path) -> None:
    """A later facade override cannot change an ingest already in flight."""
    from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade
    from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
        current_core_sources_compatibility_context,
    )

    original = transformers._to_iso3
    entered_a = asyncio.Event()
    entered_b = asyncio.Event()
    sampled_a = asyncio.Event()
    sampled_b = asyncio.Event()
    release_a = asyncio.Event()
    release_b = asyncio.Event()
    observed: dict[str, list[str]] = {}
    configs = {
        label: DatasetBatchConfig(
            snapshot_root=tmp_path / label,
            stages=frozenset({"core_sources_ingest"}),
        )
        for label in ("a", "b")
    }

    async def controlled_ingest(config: DatasetBatchConfig) -> CoreSourcesIngestStats:
        label = config.snapshot_root.name
        if label == "a":
            entered_a.set()
            await asyncio.wait_for(entered_b.wait(), timeout=5)
        else:
            entered_b.set()
            await asyncio.wait_for(sampled_a.wait(), timeout=5)

        observed[label] = loaders._bulk_country_values("ilo", ("UA",))
        if label == "a":
            sampled_a.set()
            await asyncio.wait_for(release_a.wait(), timeout=5)
        else:
            sampled_b.set()
            await asyncio.wait_for(release_b.wait(), timeout=5)
        return CoreSourcesIngestStats(observations=1 if label == "a" else 2)

    async def exercise() -> tuple[CoreSourcesIngestStats, CoreSourcesIngestStats]:
        monkeypatch.setattr(facade, "_run_core_sources_ingest_async", controlled_ingest)
        monkeypatch.setattr(facade, "_to_iso3", lambda _country: "A")
        task_a = asyncio.create_task(facade.run_core_sources_ingest_async(configs["a"]))
        await asyncio.wait_for(entered_a.wait(), timeout=5)

        monkeypatch.setattr(facade, "_to_iso3", lambda _country: "B")
        task_b = asyncio.create_task(facade.run_core_sources_ingest_async(configs["b"]))
        await asyncio.wait_for(sampled_b.wait(), timeout=5)

        assert transformers._to_iso3 is original
        release_a.set()
        stats_a = await task_a
        assert not task_b.done()
        release_b.set()
        stats_b = await task_b
        assert current_core_sources_compatibility_context() is None
        return stats_a, stats_b

    stats_a, stats_b = asyncio.run(exercise())

    assert observed == {"a": ["A"], "b": ["B"]}
    assert (stats_a.observations, stats_b.observations) == (1, 2)
    for label, expected in (("a", 1), ("b", 2)):
        manifest = configs[label].manifests_dir / "core_sources_ingest.json"
        assert (
            json.loads(manifest.read_text(encoding="utf-8"))["metrics"]["observations"] == expected
        )
    assert transformers._to_iso3 is original
