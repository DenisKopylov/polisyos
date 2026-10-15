from __future__ import annotations

import asyncio
from typing import cast

from polisyos.common.async_tools import run_coro_sync
from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CoreSourcesCompatibilityContext,
    bind_core_sources_compatibility_context,
    resolve_core_sources_compatibility_binding,
)
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.core_sources import api


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
