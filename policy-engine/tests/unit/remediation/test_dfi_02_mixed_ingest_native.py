"""Native mixed-result and persisted-lease witnesses for canonical core ingest.

Connector boundaries supply finite typed candidate inputs. The planner, source
budgets, checkpoint/receipt writers, DuckDB persistence and fresh catalog reader
remain real. Full published Fabric admission is qualified by the companion DFK
raw-to-serving witness; a current partial core receipt is not publication.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd
import pytest
import yaml

from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    ObservationPlan,
)
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.core_sources import registry, validators, writers
from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
from polisyos.data_forge.domains.catalog.batch.pipeline import run_dataset_pipeline_sync
from polisyos.data_forge.domains.catalog.knowledge.search import DatasetCatalogGraph
from polisyos.data_forge.domains.catalog.knowledge.types import DatasetRecord, DistributionRecord
from polisyos.data_forge.domains.catalog.registry import default_catalog_source_registry_path
from polisyos.fabric.connectors.base import AsyncFetchLease, DatasetCapabilitySnapshot
from polisyos.fabric.connectors.profiles.models import SourceProfile
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
from polisyos.fabric.connectors.sources.eurostat import EurostatConnector
from polisyos.fabric.connectors.sources.who import WHOConnector
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
from polisyos.ir.connectors import QualityTier

_WATERMARK = "2026-11-01T00:00:00Z"
_INPUTS = (
    ("worldbank", "WB_FIXTURE", "gdp_per_capita", "worldbank.wdi", "worldbank_wdi"),
    ("who", "WHO_FIXTURE", "health_outcomes", "who.indicators", "who_gho"),
    ("eurostat", "EU_FIXTURE", "unemployment_rate", "eurostat.data", "eurostat_public"),
)
_PIPELINE_COUNTERS = (
    "registry_datasets",
    "variable_alignments",
    "observations",
    "observations_attempted",
    "observations_inserted",
    "observations_replaced",
    "failures",
)


def _events(root: Path) -> list[dict[str, object]]:
    path = root / "connector-events.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def _event(root: Path, kind: str, source: str, **values: object) -> None:
    payload = {"kind": kind, "source": source, "pid": os.getpid(), **values}
    with (root / "connector-events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _config(root: Path) -> DatasetBatchConfig:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "registry.yaml"
    if not path.exists():
        registry = yaml.safe_load(default_catalog_source_registry_path().read_text())
        selected = [
            row for row in registry["sources"] if row["name"] in {"worldbank", "who", "eurostat"}
        ]
        for row in selected:
            row["endpoint"] = f"https://fixture.invalid/{row['name']}"
        path.write_text(yaml.safe_dump({"version": registry["version"], "sources": selected}))
    return DatasetBatchConfig(
        snapshot_root=root / "snapshot",
        registry_path=path,
        stages=frozenset({"core_sources_ingest"}),
        run_profile="prod_full",
        preflight_sources=tuple(row[0] for row in _INPUTS),
        active_countries=("UA",),
        active_year_window=(2020, 2020),
        observation_mode="core",
        embedding_device="cpu",
        max_datasets_per_source=100_000,
        resume=True,
    )


def _prepare_database(config: DatasetBatchConfig) -> None:
    if config.db_path.exists():
        return
    records = []
    for index, (source, identifier, metric, connector, profile) in enumerate(_INPUTS):
        distribution_id = f"distribution-{source}"
        records.append(
            DatasetRecord(
                id=f"mixed-{source}",
                source=source,
                source_portal=source,
                dataset_id=identifier,
                source_dataset_id=identifier,
                title=f"Controlled source {index + 1}",
                description="Finite candidate observations for the declared native ingest test.",
                variables=[identifier],
                polisyos_metrics=[metric],
                execution_tier="transport_ready",
                update_frequency="annual",
                last_updated=_WATERMARK,
                preferred_distribution_id=distribution_id,
                distributions=[
                    DistributionRecord(
                        id=distribution_id,
                        connector_type=connector,
                        profile_id=profile,
                        source_locator=identifier,
                        parser_supported=True,
                        machine_readable=True,
                        default_filters={"sex": ["T"], "unit": ["PC"]}
                        if source == "eurostat"
                        else {},
                    )
                ],
            )
        )
    build_graph(records=records, db_path=config.db_path)
    plan = ObservationPlan(
        dataset_id="mixed-worldbank",
        source="worldbank",
        raw_variable="WB_FIXTURE",
        canonical_var="gdp_per_capita",
        connector_id="worldbank.wdi",
        profile_id="worldbank_wdi",
        request_dataset_id="WB_FIXTURE",
        default_filters={},
        update_frequency="annual",
        source_watermark=_WATERMARK,
        dataset_version="WB_FIXTURE",
    )
    with duckdb.connect(str(config.db_path)) as connection:
        registry._ensure_registry_tables(connection)
        writers._insert_generic_observations(
            con=connection,
            plan=plan,
            rows=[{"country_code": "UKR", "year": 2020, "sex": "T", "value": -11.0}],
            acquisition_method="api_sync",
        )


def _install_profiles(patch: pytest.MonkeyPatch, *, asynchronous: bool) -> None:
    profiles = SourceProfileRegistry()
    for source, _identifier, _metric, _connector, profile in _INPUTS:
        profiles.register(
            SourceProfile(
                profile_id=profile,
                display_name=f"Finite {source} candidate provider",
                connector_family={"worldbank": "worldbank", "who": "who", "eurostat": "eurostat"}[
                    source
                ],
                base_url=f"https://fixture.invalid/{source}",
                max_retries=0,
                max_concurrency=1,
                requests_per_hour=64,
                preferred_core_transport="api_async"
                if asynchronous and source == "eurostat"
                else "api_sync",
                supports_async_fetch=asynchronous and source == "eurostat",
                max_sync_cells=1 if asynchronous and source == "eurostat" else None,
                max_async_cells=100 if asynchronous and source == "eurostat" else None,
            )
        )
    patch.setattr(SourceProfileRegistry, "_instance", profiles)


def _install_provider(patch: pytest.MonkeyPatch, root: Path, *, mode: str) -> None:
    by_connector = {row[3]: row for row in _INPUTS}

    async def describe(connector, handle, dataset_id):
        source, identifier, _metric, _connector, _profile = by_connector[connector.connector_id]
        assert dataset_id == identifier
        _event(root, "describe", source, dataset_id=dataset_id)
        return DatasetCapabilitySnapshot(
            source=source,
            dataset_id=identifier,
            resolved_dataset_id=identifier,
            dimension_order=("geo", "time", "sex", "unit")
            if source == "eurostat"
            else ("country", "year", "sex"),
            allowed_positions={
                "geo" if source == "eurostat" else "country": ("UA",),
                "sex": ("T", "M"),
                "unit": ("PC",),
            },
            estimated_cardinality=2,
            version_hint=identifier,
            last_checked_at=datetime.now(UTC),
        )

    def check_request(connector, request):
        source, identifier, _metric, _connector, _profile = by_connector[connector.connector_id]
        assert request.dataset_id == identifier
        assert request.date_start == datetime(2020, 1, 1, tzinfo=UTC)
        assert request.date_end == datetime(2020, 12, 31, tzinfo=UTC)
        filters = dict(request.filters)
        assert filters["geo" if source == "eurostat" else "country"] == ("UA",)
        if source == "eurostat":
            assert filters["sex"] == ("T",) and filters["unit"] == ("PC",)
        return source

    def result(connector, source: str):
        rows = (
            [
                {"country_code": "UKR", "year": 2020, "sex": "T", "value": 11.0},
                {"country_code": "UKR", "year": 2020, "sex": "M", "value": 12.0},
            ]
            if source == "worldbank"
            else []
            if source == "who"
            else [{"geo": "UA", "time_period": "2020", "sex": "T", "unit": "PC", "value": 33.0}]
        )
        raw = json.dumps(rows, sort_keys=True).encode()
        return connector._build_fetch_result(
            data=pd.DataFrame(rows),
            row_count=len(rows),
            schema_id=f"{source}.controlled",
            schema_version="1.0.0",
            quality_tier=QualityTier.UNVERIFIED,
            bytes_transferred=len(raw),
            completeness=1.0,
            fetched_at=datetime.now(UTC),
            fetch_duration_ms=0.001,
            content_hash="sha256:" + hashlib.sha256(raw).hexdigest(),
        )

    async def fetch(connector, handle, request):
        source = check_request(connector, request)
        _event(root, "fetch", source, dataset_id=request.dataset_id)
        if source == "eurostat" and mode == "mixed":
            raise RuntimeError("controlled provider authorization refusal")
        return result(connector, source)

    async def submit(connector, handle, request):
        source = check_request(connector, request)
        token = f"controlled-{uuid4().hex}"
        _event(
            root,
            "submit",
            source,
            dataset_id=request.dataset_id,
            token=token,
            source_profile_fingerprint=handle.config.source_profile_fingerprint,
        )
        return AsyncFetchLease(
            lease_id=token,
            connector_id=connector.connector_id,
            dataset_id=request.dataset_id,
            request_key=request.dataset_id,
            status="submitted",
            poll_after_seconds=0.0,
            status_url="https://fixture.invalid/eurostat/status",
            download_url="https://fixture.invalid/eurostat/data",
        )

    async def poll(connector, handle, lease):
        _event(
            root,
            "poll",
            "eurostat",
            token=lease.lease_id,
            dataset_id=lease.dataset_id,
            source_profile_fingerprint=handle.config.source_profile_fingerprint,
        )
        if mode == "lease_wait":
            import asyncio

            await asyncio.Event().wait()
        return result(connector, "eurostat")

    for connector_type in (WorldBankConnector, WHOConnector, EurostatConnector):
        patch.setattr(connector_type, "describe_dataset", describe)
        patch.setattr(connector_type, "fetch", fetch)
    patch.setattr(EurostatConnector, "fetch_async", submit)
    patch.setattr(EurostatConnector, "poll_async_fetch", poll)


def _manifest(config: DatasetBatchConfig) -> dict:
    return json.loads((config.manifests_dir / "core_sources_ingest.json").read_text())


def _assert_pipeline_counters(stats, manifest: dict, expected: dict[str, int]) -> None:
    assert set(expected) == set(_PIPELINE_COUNTERS)
    assert {name: stats.metrics[f"core_{name}"] for name in _PIPELINE_COUNTERS} == expected
    assert {name: manifest["metrics"][name] for name in _PIPELINE_COUNTERS} == expected


def _worker_main(root: Path, mode: str) -> None:
    if mode == "mixed_counter":
        with pytest.MonkeyPatch.context() as patch:
            _exercise_native_counter_case(patch, root)
        return
    with pytest.MonkeyPatch.context() as patch:
        config = _config(root)
        _prepare_database(config)
        _install_profiles(patch, asynchronous=True)
        _install_provider(patch, root, mode=mode)
        stats = run_dataset_pipeline_sync(config)
        current = validators._current_core_output_receipt_state(config)
        (root / "worker-result.json").write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "metrics": stats.metrics,
                    "manifest": _manifest(config),
                    "receipt_is_current": current.is_current,
                    "receipt": current.current_receipt,
                },
                sort_keys=True,
            )
        )


def _exercise_native_counter_case(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = _config(tmp_path)
    _prepare_database(config)
    _install_profiles(monkeypatch, asynchronous=False)
    _install_provider(monkeypatch, tmp_path, mode="mixed")
    facade_name = "polisyos.data_forge.domains.catalog.batch.core_sources_ingest"
    assert facade_name not in sys.modules
    leaf_calls = {
        name: set()
        for name in ("api", "registry", "transformers", "loaders", "validators", "writers")
    }
    prefix = "polisyos.data_forge.domains.catalog.batch.core_sources."
    previous_profiler = sys.getprofile()

    def observe_leaf(frame, event, argument):
        if event == "call":
            module = frame.f_globals.get("__name__", "")
            leaf = module.removeprefix(prefix)
            if module.startswith(prefix) and leaf in leaf_calls:
                leaf_calls[leaf].add(frame.f_code.co_name)
        if previous_profiler is not None:
            previous_profiler(frame, event, argument)

    sys.setprofile(observe_leaf)
    try:
        stats = run_dataset_pipeline_sync(config)
    finally:
        sys.setprofile(previous_profiler)
    assert facade_name not in sys.modules
    for leaf, function in {
        "api": "_run_core_sources_ingest_async",
        "registry": "_build_catalog_alignments",
        "transformers": "_normalize_observation_row",
        "loaders": "_records_from_payload",
        "validators": "_build_core_output_receipt",
        "writers": "_insert_generic_observations",
    }.items():
        assert function in leaf_calls[leaf], (leaf, leaf_calls[leaf])
    print(
        json.dumps(
            {
                "facade_imported": False,
                "native_leaf_calls": {name: sorted(calls) for name, calls in leaf_calls.items()},
            },
            sort_keys=True,
        )
    )
    manifest = _manifest(config)
    _assert_pipeline_counters(
        stats,
        manifest,
        {
            "registry_datasets": 3,
            "variable_alignments": 3,
            "observations": 1,
            "observations_attempted": 2,
            "observations_inserted": 1,
            "observations_replaced": 1,
            "failures": 1,
        },
    )
    assert {
        name: manifest["metrics"][name]
        for name in ("completed_shards", "empty_shards", "failed_shards", "deferred_shards")
    } == {"completed_shards": 2, "empty_shards": 1, "failed_shards": 1, "deferred_shards": 0}
    assert manifest["status"] == "warning"
    receipt = validators._current_core_output_receipt_state(config)
    assert receipt.is_current
    assert receipt.current_receipt["selected_pending"] == 1
    assert receipt.current_receipt["publishable_core_complete"] is False
    checkpoint = json.loads(config.observation_ingest_checkpoint_path.read_text())
    events = _events(tmp_path)
    for source, *_rest in _INPUTS:
        observed = sum(
            event["source"] == source and event["kind"] in {"describe", "fetch"} for event in events
        )
        assert observed >= 2
        assert checkpoint["source_budgets"][source]["requests_used"] == observed
    with duckdb.connect(str(config.db_path), read_only=True) as connection:
        rows = connection.execute(
            "SELECT observation_id,dataset_id,raw_variable,canonical_var,country_code,year,"
            "survey_year,wave,value,condition_json,acquisition_method,source_watermark,"
            "dataset_version FROM ds_observations ORDER BY value"
        ).fetchall()
    assert len(rows) == 2
    for row, sex, value in zip(rows, ("T", "M"), (11.0, 12.0), strict=True):
        condition = json.dumps({"sex": sex}, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(condition.encode()).hexdigest()[:12]
        identity = f"mixed-worldbank|WB_FIXTURE|gdp_per_capita|UA|2020|None|None|{digest}"
        assert row == (
            hashlib.sha256(identity.encode()).hexdigest()[:24],
            "mixed-worldbank",
            "WB_FIXTURE",
            "gdp_per_capita",
            "UA",
            2020,
            None,
            None,
            value,
            condition,
            "api_sync",
            _WATERMARK,
            "WB_FIXTURE",
        )

    _install_provider(monkeypatch, tmp_path, mode="recover")
    recovered = run_dataset_pipeline_sync(replace(config, resume=False))
    _assert_pipeline_counters(
        recovered,
        _manifest(config),
        {
            "registry_datasets": 3,
            "variable_alignments": 3,
            "observations": 1,
            "observations_attempted": 3,
            "observations_inserted": 1,
            "observations_replaced": 2,
            "failures": 0,
        },
    )
    current = validators._current_core_output_receipt_state(config)
    assert current.is_current and current.current_receipt["selected_work_complete"] is True
    graph = DatasetCatalogGraph(config.db_path, config.index_dir)
    try:
        assert {
            binding.catalog_dataset_id
            for binding in graph.search_metric_bindings("gdp_per_capita", modes=("exact",))
        } == {"mixed-worldbank"}
        assert {
            binding.catalog_dataset_id
            for binding in graph.search_metric_bindings("unemployment_rate", modes=("exact",))
        } == {"mixed-eurostat"}
    finally:
        graph.close()

    filtered = replace(config, preflight_sources=("ukons",))
    run_dataset_pipeline_sync(filtered)
    missing = _manifest(filtered)
    assert missing["status"] == "warning"
    assert missing["metrics"]["core_output_receipt_digest"] is None
    assert not validators._current_core_output_receipt_state(filtered).is_current
    with duckdb.connect(str(config.db_path), read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM ds_observations").fetchone() == (3,)


def _child_command(root: Path) -> tuple[list[str], Path, dict[str, str]]:
    project = Path(__file__).resolve().parents[3]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join((str(project / "src"), str(project / "tests")))
    return (
        [
            sys.executable,
            "-c",
            "import runpy,sys; from pathlib import Path; namespace=runpy.run_path(sys.argv[1]); namespace['_worker_main'](Path(sys.argv[2]),sys.argv[3])",
            str(Path(__file__).resolve()),
            str(root),
        ],
        project,
        environment,
    )


def test_native_canonical_pipeline_reconciles_mixed_counters_budget_and_receipt(
    tmp_path: Path,
) -> None:
    # A deliberately preloaded parent facade must not contaminate the fresh proof.
    from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade

    assert sys.modules[facade.__name__] is facade
    command, project, environment = _child_command(tmp_path)
    completed = subprocess.run(
        [*command, "mixed_counter"],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        timeout=40,
        check=False,
    )
    (tmp_path / "mixed-child.log").write_text(completed.stdout + completed.stderr)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert '"facade_imported": false' in completed.stdout
    print(completed.stdout, end="")


def test_native_canonical_pipeline_resumes_produced_async_lease_after_owned_child_kill(
    tmp_path: Path,
) -> None:
    root = tmp_path / "owned-producer"
    root.mkdir()
    command, project, environment = _child_command(root)
    # Resolve the existing owner path rather than assuming the checkpoint spelling.
    checkpoint_path = _config(root).observation_ingest_checkpoint_path
    with (root / "first-child.log").open("w") as output:
        child = subprocess.Popen(
            [*command, "lease_wait"],
            cwd=project,
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 25.0
            while time.monotonic() < deadline:
                assert child.poll() is None, (root / "first-child.log").read_text()
                if checkpoint_path.exists():
                    before = json.loads(checkpoint_path.read_text())
                    if before.get("async_fetch_leases"):
                        break
                time.sleep(0.05)
            else:
                raise AssertionError("producer did not persist its native async lease")
            before_events = _events(root)
            submits = [event for event in before_events if event["kind"] == "submit"]
            assert len(submits) == 1
            shard_id, lease = next(iter(before["async_fetch_leases"].items()))
            assert lease["lease_id"] == submits[0]["token"]
            assert lease["dataset_id"] == "EU_FIXTURE"
            assert lease["connector_id"] == "eurostat.data"
            assert before["work_packages"][shard_id]["plan"]["source"] == "eurostat"
            before_pid = child.pid
            child.kill()
            assert child.wait(timeout=5) != 0
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
    crash_cut = checkpoint_path.read_bytes()
    (root / "native-lease-crash-cut.json").write_bytes(crash_cut)
    assert json.loads(crash_cut)["async_fetch_leases"][shard_id] == lease
    resumed = subprocess.run(
        [*command, "lease_resume"],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        timeout=35,
        check=False,
    )
    (root / "resumed-child.log").write_text(resumed.stdout + resumed.stderr)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    result = json.loads((root / "worker-result.json").read_text())
    after_events = _events(root)
    assert sum(event["kind"] == "submit" for event in after_events) == 1
    polls = [
        event for event in after_events if event["kind"] == "poll" and event["pid"] == result["pid"]
    ]
    assert polls and result["pid"] != before_pid
    assert {event["token"] for event in polls} == {lease["lease_id"]}
    assert {event["dataset_id"] for event in polls} == {"EU_FIXTURE"}
    assert {event["source_profile_fingerprint"] for event in polls} == {
        submits[0]["source_profile_fingerprint"]
    }
    assert result["receipt_is_current"] is True
    assert result["receipt"]["selected_work_complete"] is True
    assert result["manifest"]["status"] == "ok"
    for name in _PIPELINE_COUNTERS:
        assert result["metrics"][f"core_{name}"] == result["manifest"]["metrics"][name]
    after = json.loads(checkpoint_path.read_text())
    assert after["async_fetch_leases"] == {}
    assert (
        after["source_budgets"]["eurostat"]["requests_used"]
        > before["source_budgets"]["eurostat"]["requests_used"]
    )
    config = _config(root)
    with duckdb.connect(str(config.db_path), read_only=True) as connection:
        assert connection.execute(
            "SELECT value,acquisition_method,country_code,year FROM ds_observations "
            "WHERE dataset_id='mixed-eurostat'"
        ).fetchall() == [(33.0, "api_async", "UA", 2020)]
