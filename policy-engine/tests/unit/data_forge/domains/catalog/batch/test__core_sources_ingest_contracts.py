from __future__ import annotations

import asyncio
import contextlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any, cast

from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as runtime
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CoreSourcesCompatibilityContext,
    CoreSourcesIngestStats,
    ObservationFetchPayload,
    ObservationInsertStats,
    ObservationPlan,
    ObservationShard,
    ObservationWriteItem,
    bind_core_sources_compatibility_context,
    resolve_core_sources_compatibility_binding,
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


def test_compatibility_context_snapshots_and_scopes_nested_bindings() -> None:
    key = ("polisyos.data_forge.domains.catalog.batch.core_sources.api", "sample")
    source = {key: "outer"}
    context = CoreSourcesCompatibilityContext(source)
    source[key] = "mutated-after-snapshot"

    with bind_core_sources_compatibility_context(context):
        assert resolve_core_sources_compatibility_binding(*key) == (True, "outer")
        with bind_core_sources_compatibility_context(
            CoreSourcesCompatibilityContext({key: "inner"})
        ):
            assert resolve_core_sources_compatibility_binding(*key) == (True, "inner")
        assert resolve_core_sources_compatibility_binding(*key) == (True, "outer")

    assert resolve_core_sources_compatibility_binding(*key) == (False, None)


def test_compatibility_contexts_are_isolated_across_async_tasks_and_threads() -> None:
    key = ("polisyos.data_forge.domains.catalog.batch.core_sources.writers", "sample")

    async def _async_value(value: str, started: asyncio.Event, release: asyncio.Event) -> str:
        context = CoreSourcesCompatibilityContext({key: value})
        with bind_core_sources_compatibility_context(context):
            started.set()
            await release.wait()
            found, resolved = resolve_core_sources_compatibility_binding(*key)
            assert found
            return cast("str", resolved)

    async def _run_async_tasks() -> list[str]:
        first_started = asyncio.Event()
        second_started = asyncio.Event()
        release = asyncio.Event()
        first = asyncio.create_task(_async_value("first", first_started, release))
        second = asyncio.create_task(_async_value("second", second_started, release))
        await asyncio.gather(first_started.wait(), second_started.wait())
        release.set()
        return await asyncio.gather(first, second)

    assert asyncio.run(_run_async_tasks()) == ["first", "second"]

    rendezvous = Barrier(2)

    def _thread_value(value: str) -> str:
        context = CoreSourcesCompatibilityContext({key: value})
        with bind_core_sources_compatibility_context(context):
            rendezvous.wait(timeout=5)
            found, resolved = resolve_core_sources_compatibility_binding(*key)
            assert found
            return cast("str", resolved)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(_thread_value, "thread-first")
        second = executor.submit(_thread_value, "thread-second")
        assert {first.result(timeout=5), second.result(timeout=5)} == {
            "thread-first",
            "thread-second",
        }


def test_cancelled_compatibility_scope_resets_without_changing_live_sibling() -> None:
    key = ("polisyos.data_forge.domains.catalog.batch.core_sources.api", "sample")

    async def _run() -> None:
        cancelled_entered = asyncio.Event()
        sibling_entered = asyncio.Event()
        release_sibling = asyncio.Event()

        async def _wait_in_scope(value: str, entered: asyncio.Event) -> str:
            with bind_core_sources_compatibility_context(
                CoreSourcesCompatibilityContext({key: value})
            ):
                entered.set()
                await release_sibling.wait()
                found, resolved = resolve_core_sources_compatibility_binding(*key)
                assert found
                return cast("str", resolved)

        cancelled = asyncio.create_task(_wait_in_scope("cancelled", cancelled_entered))
        sibling = asyncio.create_task(_wait_in_scope("sibling", sibling_entered))
        await asyncio.gather(cancelled_entered.wait(), sibling_entered.wait())
        cancelled.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cancelled
        release_sibling.set()
        assert await sibling == "sibling"
        assert resolve_core_sources_compatibility_binding(*key) == (False, None)

    asyncio.run(_run())
