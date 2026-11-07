from __future__ import annotations

import asyncio
import json
from typing import cast

from polisyos.common.async_tools import run_coro_sync
from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CatalogTransportDataset,
    CoreSourcesCompatibilityContext,
    CoreSourcesIngestStats,
    bind_core_sources_compatibility_context,
    resolve_core_sources_compatibility_binding,
)
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.core_sources import api


def test_outer_api_preserves_every_inner_counter_in_persisted_manifest(
    monkeypatch, tmp_path
) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path)
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    dataset = CatalogTransportDataset(
        catalog_dataset_id="wb-gdp",
        source="worldbank",
        title="GDP",
        description="Gross domestic product",
        source_dataset_id="WDI",
        update_frequency="annual",
        last_updated="2025-01-01",
        coverage_json='{"countries":["UA"]}',
        access_json='{"access_type":"open"}',
        execution_tier="transport_ready",
        variables=("NY.GDP.MKTP.CD",),
        keywords=("gdp",),
        themes=("economy",),
        polisyos_metrics=("gdp",),
        connector_id="worldbank.wdi",
        profile_id="worldbank_wdi",
        request_dataset_id="NY.GDP.MKTP.CD",
        default_filters={},
    )
    monkeypatch.setattr(api, "_load_catalog_transport_datasets", lambda *_args: [dataset])
    monkeypatch.setattr(api, "_build_catalog_alignments", lambda *_args: [])
    expected = {
        "observations": 6,
        "observations_attempted": 9,
        "observations_inserted": 4,
        "observations_replaced": 2,
        "failures": 3,
        "completed_shards": 5,
        "deferred_shards": 2,
        "failed_shards": 3,
        "empty_shards": 4,
    }

    async def inner_result(*_args, **_kwargs):
        return CoreSourcesIngestStats(**expected)

    monkeypatch.setattr(api, "_ingest_catalog_observations", inner_result)

    stats = asyncio.run(api.run_core_sources_ingest_async(config))

    assert {name: getattr(stats, name) for name in expected} == expected
    manifest = json.loads(
        (config.manifests_dir / "core_sources_ingest.json").read_text(encoding="utf-8")
    )
    assert {name: manifest["metrics"][name] for name in expected} == expected
    assert manifest["status"] == "warning"
    assert manifest["metrics"]["core_output_receipt_digest"] is None
    assert manifest["metrics"]["publishable_core_complete"] is False


def test_core_sources_api_module_keeps_facade_entrypoints() -> None:
    assert callable(api.run_core_sources_ingest_async)
    assert callable(facade.run_core_sources_ingest_async)
    assert callable(facade._run_core_sources_ingest_async)


def test_sync_api_resolves_runner_from_request_context_across_worker_thread(monkeypatch) -> None:
    runner_calls: list[bool] = []
    key = (api.__name__, "run_coro_sync")

    def _scoped_runner(coroutine):
        runner_calls.append(True)
        return run_coro_sync(coroutine)

    async def _stub_async_entrypoint(_config):
        found, selected_runner = resolve_core_sources_compatibility_binding(*key)
        assert found
        return selected_runner

    monkeypatch.setattr(api, "run_core_sources_ingest_async", _stub_async_entrypoint)
    context = CoreSourcesCompatibilityContext({key: _scoped_runner})

    async def _invoke_sync_entrypoint():
        with bind_core_sources_compatibility_context(context):
            return api.run_core_sources_ingest(cast("DatasetBatchConfig", object()))

    selected_runner = asyncio.run(_invoke_sync_entrypoint())

    assert selected_runner is _scoped_runner
    assert runner_calls == [True]
