from __future__ import annotations

import asyncio

from polisyos.data_forge.domains.catalog.batch import harvester as harvester_module
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.harvester import harvest_sources
from polisyos.data_forge.domains.catalog.batch.source_registry import SourceRegistry, SourceSpec


def test_harvest_sources_runs_independent_sources_in_parallel(monkeypatch, tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")
    registry = SourceRegistry(
        version=1,
        sources=(
            SourceSpec(
                name="worldbank", family="worldbank", wave="A", endpoint="https://example.com/wb"
            ),
            SourceSpec(name="who", family="who", wave="A", endpoint="https://example.com/who"),
        ),
    )
    monkeypatch.setattr(DatasetBatchConfig, "load_registry", lambda self: registry)
    monkeypatch.setattr(harvester_module, "load_metrics_map", lambda _path: {})

    state = {"active": 0, "max_active": 0}
    gate = asyncio.Lock()

    async def _fake_fetch(source_name: str, rows: list[dict]) -> list[dict]:
        async with gate:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
        await asyncio.sleep(0.05)
        async with gate:
            state["active"] -= 1
        return rows

    async def _fake_worldbank(_endpoint: str, _limit: int, _timeout_s: int) -> list[dict]:
        return await _fake_fetch("worldbank", [{"id": "worldbank"}])

    async def _fake_who(_endpoint: str, _limit: int, _timeout_s: int) -> list[dict]:
        return await _fake_fetch("who", [{"id": "who"}])

    # Replace only network I/O. The real harvest_one_source still writes each JSONL payload
    # and raw manifest, and harvest_sources validates that binding before reporting success.
    monkeypatch.setattr(harvester_module, "_harvest_worldbank", _fake_worldbank)
    monkeypatch.setattr(harvester_module, "_harvest_who_indicators", _fake_who)

    out = asyncio.run(harvest_sources(config))

    assert set(out) == {"worldbank", "who"}
    assert out["worldbank"] == [{"id": "worldbank"}]
    assert out["who"][0] == {"id": "who"}
    checkpoint = harvester_module.load_json(config.harvest_checkpoint_path, default={})
    assert all(checkpoint[name]["status"] == "complete" for name in ("worldbank", "who"))
    assert state["max_active"] >= 2


def test_harvest_sources_respects_seed_dependencies_and_keeps_broad_ckan_serial(
    monkeypatch, tmp_path
) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")
    registry = SourceRegistry(
        version=1,
        sources=(
            SourceSpec(
                name="data_gov_ua_broad", family="ckan", wave="C", endpoint="https://example.com/ua"
            ),
            SourceSpec(
                name="data_gov_ro_broad", family="ckan", wave="C", endpoint="https://example.com/ro"
            ),
            SourceSpec(
                name="data_gov_ua_exec",
                family="ckan",
                wave="C",
                endpoint="https://example.com/ua-exec",
                seed_from="data_gov_ua_broad",
            ),
            SourceSpec(
                name="worldbank", family="worldbank", wave="A", endpoint="https://example.com/wb"
            ),
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

    source_names_by_endpoint = {spec.endpoint: spec.name for spec in registry.sources}

    async def _fake_fetch(source_name: str, rows: list[dict], delay: float) -> list[dict]:
        async with gate:
            state["active_total"] += 1
            state["max_active_total"] = max(state["max_active_total"], state["active_total"])
            if source_name in {"data_gov_ua_broad", "data_gov_ro_broad"}:
                state["active_broad_ckan"] += 1
                state["max_active_broad_ckan"] = max(
                    state["max_active_broad_ckan"],
                    state["active_broad_ckan"],
                )
        await asyncio.sleep(delay)
        async with gate:
            if source_name == "data_gov_ua_broad":
                state["ua_broad_finished"] = True
            if source_name in {"data_gov_ua_broad", "data_gov_ro_broad"}:
                state["active_broad_ckan"] -= 1
            state["active_total"] -= 1
        return rows

    async def _fake_ckan(endpoint: str, _limit: int, _timeout_s: int) -> list[dict]:
        source_name = source_names_by_endpoint[endpoint]
        delay = 0.05 if source_name in {"data_gov_ua_broad", "data_gov_ro_broad"} else 0.01
        return await _fake_fetch(source_name, [{"id": source_name}], delay)

    async def _fake_worldbank(_endpoint: str, _limit: int, _timeout_s: int) -> list[dict]:
        return await _fake_fetch("worldbank", [{"id": "worldbank"}], 0.01)

    original_seed_source = harvester_module._harvest_from_seed_source

    def _observe_seed_source(spec, config, *, harvested=None):
        assert state["ua_broad_finished"] is True
        assert harvested is not None and spec.seed_from in harvested
        state["seed_source_observed"] = spec.seed_from
        return original_seed_source(spec, config, harvested=harvested)

    # Patch network boundaries only; seed curation, payload/manifest writing, and success
    # validation remain the production implementations exercised by this test.
    monkeypatch.setattr(harvester_module, "_harvest_ckan", _fake_ckan)
    monkeypatch.setattr(harvester_module, "_harvest_worldbank", _fake_worldbank)
    monkeypatch.setattr(harvester_module, "_harvest_from_seed_source", _observe_seed_source)

    out = asyncio.run(harvest_sources(config))

    assert set(out) == {
        "data_gov_ua_broad",
        "data_gov_ro_broad",
        "data_gov_ua_exec",
        "worldbank",
    }
    assert [row["id"] for row in out["data_gov_ua_exec"]] == ["data_gov_ua_broad"]
    assert state["seed_source_observed"] == "data_gov_ua_broad"
    checkpoint = harvester_module.load_json(config.harvest_checkpoint_path, default={})
    assert all(checkpoint[name]["status"] == "complete" for name in out)
    assert state["max_active_broad_ckan"] == 1
    assert state["max_active_total"] >= 2
