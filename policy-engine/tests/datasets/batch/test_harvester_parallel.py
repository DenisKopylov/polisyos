from __future__ import annotations

import asyncio

from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.batch.harvester import harvest_sources
from polisyos.datasets.batch import harvester as harvester_module
from polisyos.datasets.batch.source_registry import SourceRegistry, SourceSpec


def test_harvest_sources_runs_independent_sources_in_parallel(monkeypatch, tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")
    registry = SourceRegistry(
        version=1,
        sources=(
            SourceSpec(name="worldbank", family="worldbank", wave="A", endpoint="https://example.com/wb"),
            SourceSpec(name="who", family="who", wave="A", endpoint="https://example.com/who"),
        ),
    )
    monkeypatch.setattr(DatasetBatchConfig, "load_registry", lambda self: registry)
    monkeypatch.setattr(harvester_module, "load_metrics_map", lambda _path: {})

    state = {"active": 0, "max_active": 0}
    gate = asyncio.Lock()

    async def _fake_harvest_one_source(spec, config, *, harvested=None, metrics_map=None, checkpoint=None):  # noqa: ARG001
        async with gate:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
        await asyncio.sleep(0.05)
        async with gate:
            state["active"] -= 1
        return [{"id": spec.name}]

    monkeypatch.setattr(harvester_module, "harvest_one_source", _fake_harvest_one_source)

    out = asyncio.run(harvest_sources(config))

    assert set(out) == {"worldbank", "who"}
    assert state["max_active"] >= 2


def test_harvest_sources_respects_seed_dependencies_and_keeps_broad_ckan_serial(monkeypatch, tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")
    registry = SourceRegistry(
        version=1,
        sources=(
            SourceSpec(name="data_gov_ua_broad", family="ckan", wave="C", endpoint="https://example.com/ua"),
            SourceSpec(name="data_gov_ro_broad", family="ckan", wave="C", endpoint="https://example.com/ro"),
            SourceSpec(
                name="data_gov_ua_exec",
                family="ckan",
                wave="C",
                endpoint="https://example.com/ua-exec",
                seed_from="data_gov_ua_broad",
            ),
            SourceSpec(name="worldbank", family="worldbank", wave="A", endpoint="https://example.com/wb"),
        ),
    )
    monkeypatch.setattr(DatasetBatchConfig, "load_registry", lambda self: registry)
    monkeypatch.setattr(harvester_module, "load_metrics_map", lambda _path: {})

    state = {
        "active_total": 0,
        "max_active_total": 0,
        "active_broad_ckan": 0,
        "max_active_broad_ckan": 0,
        "ua_broad_finished": False,
    }
    gate = asyncio.Lock()

    async def _fake_harvest_one_source(spec, config, *, harvested=None, metrics_map=None, checkpoint=None):  # noqa: ARG001
        async with gate:
            state["active_total"] += 1
            state["max_active_total"] = max(state["max_active_total"], state["active_total"])
            if spec.name in {"data_gov_ua_broad", "data_gov_ro_broad"}:
                state["active_broad_ckan"] += 1
                state["max_active_broad_ckan"] = max(
                    state["max_active_broad_ckan"],
                    state["active_broad_ckan"],
                )
            if spec.name == "data_gov_ua_exec":
                assert state["ua_broad_finished"] is True
        await asyncio.sleep(0.05 if spec.name in {"data_gov_ua_broad", "data_gov_ro_broad"} else 0.01)
        async with gate:
            if spec.name == "data_gov_ua_broad":
                state["ua_broad_finished"] = True
            if spec.name in {"data_gov_ua_broad", "data_gov_ro_broad"}:
                state["active_broad_ckan"] -= 1
            state["active_total"] -= 1
        return [{"id": spec.name}]

    monkeypatch.setattr(harvester_module, "harvest_one_source", _fake_harvest_one_source)

    out = asyncio.run(harvest_sources(config))

    assert set(out) == {
        "data_gov_ua_broad",
        "data_gov_ro_broad",
        "data_gov_ua_exec",
        "worldbank",
    }
    assert state["max_active_broad_ckan"] == 1
    assert state["max_active_total"] >= 2
