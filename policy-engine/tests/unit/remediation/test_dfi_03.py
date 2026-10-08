"""Behavioral witnesses for the DFI-03 batch-resume contract."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import types
from dataclasses import replace
from pathlib import Path

import duckdb
import numpy as np
import pytest

from polisyos.data_forge.domains.catalog.batch import (
    embedder as catalog_embedder,
)
from polisyos.data_forge.domains.catalog.batch import (
    harvester as catalog_harvester,
)
from polisyos.data_forge.domains.catalog.batch import (
    normalizer as catalog_normalizer,
)
from polisyos.data_forge.domains.catalog.batch import (
    pipeline as catalog_pipeline,
)
from polisyos.data_forge.domains.catalog.batch import qc as catalog_qc
from polisyos.data_forge.domains.catalog.batch.checkpoints import (
    save_stage_state,
    stage_can_skip,
)
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.pipeline import (
    _record_stage_completion,
    _should_skip_stage,
    _stage_input_basis,
    _stage_input_fingerprint,
    current_content_stage_receipt,
    run_content_stage_with_receipt,
    run_dataset_pipeline_sync,
)
from polisyos.data_forge.domains.catalog.batch.source_registry import SourceRegistry, SourceSpec
from polisyos.data_forge.kernel.embeddings import (
    build_embedding_generation,
    derive_encoder_identity,
)
from polisyos.data_forge.kernel.pipeline.manifests import write_raw_manifest


def _restore_stat(path: Path, stat_result: os.stat_result) -> None:
    os.utime(path, ns=(stat_result.st_atime_ns, stat_result.st_mtime_ns))


def _save_state(config: DatasetBatchConfig, stage: str, outputs: list[Path]) -> None:
    del outputs
    _record_stage_completion(config, stage)


def _stub_complete_harvest_receipt(
    monkeypatch: pytest.MonkeyPatch, config: DatasetBatchConfig
) -> None:
    selected = config.load_registry().enabled_sources(
        wave=config.wave,
        run_profile=config.run_profile,
    )
    names = [spec.name for spec in selected]
    outcomes = {name: {"status": "ok"} for name in names}
    monkeypatch.setattr(
        catalog_pipeline,
        "_harvest_stage_receipt",
        lambda _config: (names, outcomes, []),
    )


def _create_empty_embedding_database(config: DatasetBatchConfig) -> None:
    with duckdb.connect(str(config.db_path)) as con:
        con.execute(
            "CREATE TABLE ds_datasets (id VARCHAR, title VARCHAR, description VARCHAR, "
            "keywords VARCHAR[], variables VARCHAR[])"
        )
        con.execute("CHECKPOINT")


class _MutableEncoderTokenizer:
    revision = 0

    def get_vocab(self) -> dict[str, int]:
        return {"<unk>": 0, f"revision-{self.revision}": 1}

    @property
    def special_tokens_map(self) -> dict[str, str]:
        return {"unk_token": "<unk>"}

    def get_added_vocab(self) -> dict[str, int]:
        return {}


class _MutableSentenceTransformer:
    asset_revision = 0

    def __init__(self, model_name: str, device: str | None = None) -> None:
        self.config = {"model_name": model_name, "revision": type(self).asset_revision}
        self.tokenizer = _MutableEncoderTokenizer()
        self.tokenizer.revision = type(self).asset_revision
        self.device = device

    def state_dict(self) -> dict[str, np.ndarray]:
        return {"encoder.weight": np.asarray([type(self).asset_revision, 1.0], dtype=np.float32)}

    def modules(self) -> list[_MutableSentenceTransformer]:
        return [self]

    def encode(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        del batch_size, show_progress_bar, normalize_embeddings
        return np.tile(np.asarray([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32), (len(texts), 1))


def test_same_stat_changed_manifest_bytes_do_not_reuse_normalize_stage(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"normalize"}),
        resume=True,
    )
    _stub_complete_harvest_receipt(monkeypatch, config)
    manifest = config.raw_dir / "source" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(b'{"row": 1}\n')
    config.normalized_dir.mkdir(parents=True, exist_ok=True)
    (config.normalized_dir / "records.jsonl").write_text("record\n", encoding="utf-8")
    _save_state(config, "normalize", [config.normalized_dir])

    assert _should_skip_stage(config, "normalize")
    previous_stat = manifest.stat()
    manifest.write_bytes(b'{"row": 2}\n')
    _restore_stat(manifest, previous_stat)

    assert not _should_skip_stage(config, "normalize")


def test_mtime_only_manifest_change_keeps_normalize_stage_reusable(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"normalize"}),
        resume=True,
    )
    _stub_complete_harvest_receipt(monkeypatch, config)
    manifest = config.raw_dir / "source" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(b'{"row": 1}\n')
    config.normalized_dir.mkdir(parents=True, exist_ok=True)
    (config.normalized_dir / "records.jsonl").write_text("record\n", encoding="utf-8")
    _save_state(config, "normalize", [config.normalized_dir])

    original = manifest.stat()
    os.utime(manifest, ns=(original.st_atime_ns, original.st_mtime_ns + 1_000_000))

    assert _should_skip_stage(config, "normalize")


def test_harvest_resume_rejects_preflight_limit_change(monkeypatch, tmp_path) -> None:
    registry = SourceRegistry(
        version=1,
        sources=(
            SourceSpec(
                name="worldbank_fixture",
                family="worldbank",
                wave="A",
                endpoint="https://example.test/worldbank",
                execution_tier="transport_ready",
                run_lane="empirical",
                publish_blocking=True,
            ),
        ),
    )
    monkeypatch.setattr(DatasetBatchConfig, "load_registry", lambda _self: registry)
    monkeypatch.setattr(catalog_harvester, "load_metrics_map", lambda _path: {})
    limits: list[int] = []

    async def fake_worldbank(_endpoint: str, limit: int, _timeout: int) -> list[dict]:
        limits.append(limit)
        return []

    monkeypatch.setattr(catalog_harvester, "_harvest_worldbank", fake_worldbank)
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"harvest"}),
        run_profile="prod_full",
        max_datasets_per_source=100_000,
    )

    asyncio.run(catalog_harvester.harvest_sources(config))
    _record_stage_completion(config, "harvest")
    config.resume = True
    assert _should_skip_stage(config, "harvest")

    config.preflight_only = True
    assert not _should_skip_stage(config, "harvest")
    config.resume = False
    asyncio.run(catalog_harvester.harvest_sources(config))

    assert limits == [100_000, 300]


def test_embed_resume_rejects_changed_loaded_encoder_assets(monkeypatch, tmp_path) -> None:
    _MutableSentenceTransformer.asset_revision = 0
    _MutableEncoderTokenizer.revision = 0
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=_MutableSentenceTransformer),
    )
    local_model = tmp_path / "cached-model"
    local_model.mkdir()
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"embed"}),
        resume=True,
        embedding_model=str(local_model),
        embedding_device="cpu",
        embedding_dimension=4,
    )
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(config.db_path)) as con:
        con.execute(
            "CREATE TABLE ds_datasets (id VARCHAR, title VARCHAR, description VARCHAR, "
            "keywords VARCHAR[], variables VARCHAR[])"
        )
        con.execute("INSERT INTO ds_datasets VALUES ('ds-1', 'Title', 'Description', [], [])")
        con.execute("CHECKPOINT")

    catalog_embedder.run_embed(config)
    _record_stage_completion(config, "embed")
    saved_identity = derive_encoder_identity(_MutableSentenceTransformer(str(local_model)))
    assert _should_skip_stage(config, "embed")

    _MutableSentenceTransformer.asset_revision = 1
    _MutableEncoderTokenizer.revision = 1
    current_identity = derive_encoder_identity(_MutableSentenceTransformer(str(local_model)))
    assert current_identity.content_identity != saved_identity.content_identity
    assert not _should_skip_stage(config, "embed")


@pytest.mark.parametrize("stage", ["graph_load", "graph_index"])
def test_graph_resume_rejects_same_stat_changed_input(stage: str, tmp_path) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({stage}),
        resume=True,
    )
    input_path = config.merged_records_path if stage == "graph_load" else config.db_path
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_bytes(b"before\n")
    if stage == "graph_load":
        config.db_path.parent.mkdir(parents=True, exist_ok=True)
        config.db_path.write_bytes(b"graph\n")
    _record_stage_completion(config, stage)
    assert _should_skip_stage(config, stage)

    previous_stat = input_path.stat()
    input_path.write_bytes(b"after!\n")
    _restore_stat(input_path, previous_stat)

    assert not _should_skip_stage(config, stage)


def test_graph_receipts_bind_database_after_selected_downstream_writers(
    monkeypatch, tmp_path
) -> None:
    from polisyos.data_forge.domains.catalog.batch import graph_builder
    from polisyos.data_forge.domains.catalog.batch.core_sources import api as core_api

    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"graph_load", "graph_index", "core_sources_ingest"}),
    )
    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    config.merged_records_path.write_text("input\n", encoding="utf-8")

    def load_graph(stage_config):
        stage_config.db_path.write_bytes(b"graph-load")
        return types.SimpleNamespace(datasets=1, distributions=0)

    def index_graph(stage_config):
        stage_config.db_path.write_bytes(b"graph-index")

    async def ingest_core(stage_config):
        stage_config.db_path.write_bytes(b"core-ingest")
        return types.SimpleNamespace(
            registry_datasets=0,
            variable_alignments=0,
            observations=0,
            observations_attempted=0,
            observations_inserted=0,
            observations_replaced=0,
            failures=0,
        )

    monkeypatch.setattr(graph_builder, "run_graph_load", load_graph)
    monkeypatch.setattr(graph_builder, "run_graph_index", index_graph)
    monkeypatch.setattr(core_api, "run_core_sources_ingest_async", ingest_core)

    run_dataset_pipeline_sync(config)
    assert config.db_path.read_bytes() == b"core-ingest"
    config.resume = True
    assert _should_skip_stage(config, "graph_load")
    assert _should_skip_stage(config, "graph_index")

    previous_stat = config.db_path.stat()
    config.db_path.write_bytes(b"CORE-INGEST")
    _restore_stat(config.db_path, previous_stat)

    assert not _should_skip_stage(config, "graph_load")
    assert not _should_skip_stage(config, "graph_index")


def test_pipeline_preserves_current_core_producer_progress_for_benchmark(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from datetime import UTC, datetime

    import pandas as pd

    from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        DatasetRecord,
        DistributionRecord,
    )
    from polisyos.fabric.connectors.base import DatasetCapabilitySnapshot
    from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector

    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        "\n".join(
            [
                "version: 1",
                "sources:",
                "  - name: worldbank",
                "    family: worldbank",
                "    wave: A",
                "    endpoint: https://example.test/worldbank",
                "    connector_id: worldbank.wdi",
                "    profile_id: worldbank_wdi",
                "    enabled: true",
                "    execution_tier: transport_ready",
                "    run_lane: empirical",
                "    publish_blocking: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        registry_path=registry_path,
        stages=frozenset({"core_sources_ingest", "benchmark"}),
        run_profile="preflight_core",
        promoted_sources=("worldbank",),
        preflight_sources=("worldbank",),
        active_countries=("UA",),
        active_year_window=(2020, 2020),
        observation_mode="core",
        max_datasets_per_source=1,
    )
    record = DatasetRecord(
        id="wb-gdp",
        title="GDP per capita",
        description="GDP per capita",
        source="worldbank",
        source_portal="worldbank",
        dataset_id="NY.GDP.PCAP.PP.CD",
        source_dataset_id="NY.GDP.PCAP.PP.CD",
        execution_tier="transport_ready",
        update_frequency="annual",
        polisyos_metrics=["gdp_per_capita"],
        variables=["NY.GDP.PCAP.PP.CD"],
        preferred_distribution_id="dist-wb",
        distributions=[
            DistributionRecord(
                id="dist-wb",
                connector_type="worldbank.wdi",
                profile_id="worldbank_wdi",
                source_locator="NY.GDP.PCAP.PP.CD",
                parser_supported=True,
                machine_readable=True,
            )
        ],
    )
    build_graph(records=[record], db_path=config.db_path)

    async def _describe_dataset(
        _connector: WorldBankConnector, _handle: object, dataset_id: str
    ) -> DatasetCapabilitySnapshot:
        return DatasetCapabilitySnapshot(
            source="worldbank",
            dataset_id=dataset_id,
            resolved_dataset_id=dataset_id,
            last_checked_at=datetime.now(UTC),
        )

    fetch_state = {"fail": False, "calls": 0}

    async def _fetch_dataset(
        _connector: WorldBankConnector, _handle: object, _request: object
    ) -> object:
        fetch_state["calls"] += 1
        if fetch_state["fail"]:
            raise RuntimeError("fixture World Bank fetch failure")
        return type(
            "WorldBankFixtureResult",
            (),
            {"data": pd.DataFrame([{"country_code": "UA", "year": 2020, "value": 1.1}])},
        )()

    monkeypatch.setattr(WorldBankConnector, "describe_dataset", _describe_dataset)
    monkeypatch.setattr(WorldBankConnector, "fetch", _fetch_dataset)

    stats = run_dataset_pipeline_sync(config)

    assert stats.metrics["core_observations"] == 1
    state = json.loads(config.stage_state_path.read_text(encoding="utf-8"))["core_sources_ingest"]
    producer_manifest = json.loads(
        (config.manifests_dir / "core_sources_ingest.json").read_text(encoding="utf-8")
    )
    benchmark = json.loads(config.benchmark_report_path.read_text(encoding="utf-8"))

    assert producer_manifest["status"] == "ok"
    assert producer_manifest["metrics"]["completed_shards"] == 1
    assert state["metadata"]["publishable_core_complete"] is True
    assert state["metadata"]["publishable_core_pending"] == 0
    assert state["metadata"]["source_core_completion_pct"] == {"worldbank": 100.0}
    assert state["status"] == "complete"
    assert state.get("input_basis") is None
    assert state.get("output_inventory") is None
    assert benchmark["evaluation_mode"] == "full-ready"

    retry_config = DatasetBatchConfig(
        snapshot_root=tmp_path / "retry-snapshot",
        registry_path=registry_path,
        stages=frozenset({"core_sources_ingest", "benchmark"}),
        run_profile="preflight_core",
        promoted_sources=("worldbank",),
        preflight_sources=("worldbank",),
        active_countries=("UA",),
        active_year_window=(2020, 2020),
        observation_mode="core",
        max_datasets_per_source=1,
        resume=True,
        resume_mode="force",
    )
    build_graph(records=[record], db_path=retry_config.db_path)
    retry_config.stage_state_path.parent.mkdir(parents=True, exist_ok=True)
    retry_config.stage_state_path.write_text(
        json.dumps({"core_sources_ingest": state}), encoding="utf-8"
    )

    fetch_state["fail"] = True
    failed_stats = run_dataset_pipeline_sync(retry_config)
    failed_state = json.loads(retry_config.stage_state_path.read_text(encoding="utf-8"))[
        "core_sources_ingest"
    ]
    failed_manifest = json.loads(
        (retry_config.manifests_dir / "core_sources_ingest.json").read_text(encoding="utf-8")
    )
    deferred_shards = json.loads(
        (retry_config.manifests_dir / "deferred_observation_plans.json").read_text(encoding="utf-8")
    )
    failed_benchmark = json.loads(retry_config.benchmark_report_path.read_text(encoding="utf-8"))
    failed_checkpoint = json.loads(
        retry_config.observation_ingest_checkpoint_path.read_text(encoding="utf-8")
    )
    with duckdb.connect(str(retry_config.db_path), read_only=True) as con:
        failed_observation_count = con.execute(
            "SELECT count(*) FROM ds_observations WHERE dataset_id = 'wb-gdp'"
        ).fetchone()[0]

    successful_shards = json.loads(
        (config.manifests_dir / "completed_observation_shards.json").read_text(encoding="utf-8")
    )
    assert failed_stats.metrics["core_failures"] == 1
    assert failed_manifest["status"] == "warning"
    assert failed_state["status"] == "warning"
    assert failed_state["metadata"]["publishable_core_complete"] is False
    assert failed_state["metadata"]["publishable_core_pending"] == 1
    assert failed_state["metadata"]["source_core_completion_pct"] == {"worldbank": 0.0}
    assert failed_state["metadata"]["subphases"]["publishable_core"] == {
        "status": "running",
        "remaining": 1,
    }
    assert deferred_shards[0]["shard_id"] == successful_shards[0]["shard_id"]
    assert failed_checkpoint["deferred"][deferred_shards[0]["shard_id"]]["status"] == "deferred"
    assert deferred_shards[0]["shard_id"] not in failed_checkpoint["completed"]
    assert failed_observation_count == 0
    assert failed_benchmark["evaluation_mode"] == "partial-eval"

    fetch_state["fail"] = False
    retried_stats = run_dataset_pipeline_sync(retry_config)
    retried_state = json.loads(retry_config.stage_state_path.read_text(encoding="utf-8"))[
        "core_sources_ingest"
    ]
    retried_shards = json.loads(
        (retry_config.manifests_dir / "completed_observation_shards.json").read_text(
            encoding="utf-8"
        )
    )
    retried_benchmark = json.loads(retry_config.benchmark_report_path.read_text(encoding="utf-8"))
    retried_checkpoint = json.loads(
        retry_config.observation_ingest_checkpoint_path.read_text(encoding="utf-8")
    )
    with duckdb.connect(str(retry_config.db_path), read_only=True) as con:
        persisted_observations = con.execute(
            "SELECT dataset_id, raw_variable, country_code, year, value "
            "FROM ds_observations WHERE dataset_id = 'wb-gdp'"
        ).fetchall()

    assert retried_stats.metrics["core_failures"] == 0
    assert retried_state["status"] == "complete"
    assert retried_state["metadata"]["publishable_core_complete"] is True
    assert retried_state["metadata"]["publishable_core_pending"] == 0
    assert retried_shards[0]["shard_id"] == deferred_shards[0]["shard_id"]
    assert (
        retried_checkpoint["completed"][retried_shards[0]["shard_id"]]["status"]
        == "complete_with_rows"
    )
    assert retried_shards[0]["shard_id"] not in retried_checkpoint["deferred"]
    assert persisted_observations == [("wb-gdp", "NY.GDP.PCAP.PP.CD", "UA", 2020, 1.1)]
    assert retried_benchmark["evaluation_mode"] == "full-ready"

    calls_before_valid_resume = fetch_state["calls"]
    valid_resume_stats = run_dataset_pipeline_sync(retry_config)
    valid_resume_benchmark = json.loads(
        retry_config.benchmark_report_path.read_text(encoding="utf-8")
    )
    assert fetch_state["calls"] == calls_before_valid_resume
    assert valid_resume_stats.metrics["core_failures"] == 0
    assert valid_resume_benchmark["evaluation_mode"] == "full-ready"

    completed_checkpoint = json.loads(
        retry_config.observation_ingest_checkpoint_path.read_text(encoding="utf-8")
    )
    completed_shard_id = retried_shards[0]["shard_id"]
    stale_checkpoint = json.loads(json.dumps(completed_checkpoint))
    stale_result = stale_checkpoint["completed"].pop(completed_shard_id)
    stale_checkpoint["deferred"][completed_shard_id] = {
        **stale_result,
        "status": "deferred",
    }
    retry_config.observation_ingest_checkpoint_path.write_text(
        json.dumps(stale_checkpoint), encoding="utf-8"
    )

    from polisyos.data_forge.domains.catalog.batch.benchmark import run_benchmark

    run_benchmark(retry_config)
    marker_only_report = json.loads(retry_config.benchmark_report_path.read_text(encoding="utf-8"))
    assert marker_only_report["evaluation_mode"] == "partial-eval"
    assert marker_only_report["metrics"]["benchmark_partial_eval"] == 1

    retry_config.observation_ingest_checkpoint_path.write_text(
        json.dumps(completed_checkpoint), encoding="utf-8"
    )
    with duckdb.connect(str(retry_config.db_path)) as con:
        con.execute("DELETE FROM ds_observations WHERE dataset_id = 'wb-gdp'")
        con.execute("CHECKPOINT")

    prior_green_stage = json.loads(retry_config.stage_state_path.read_text(encoding="utf-8"))[
        "core_sources_ingest"
    ]
    assert prior_green_stage["status"] == "complete"
    assert prior_green_stage["metadata"]["core_output_receipt"] is not None
    removed_output_benchmark = run_benchmark(retry_config)
    removed_output_report = json.loads(
        retry_config.benchmark_report_path.read_text(encoding="utf-8")
    )
    assert removed_output_benchmark.metrics["benchmark_partial_eval"] == 1
    assert removed_output_report["evaluation_mode"] == "partial-eval"

    before_missing_output_retry = fetch_state["calls"]
    fetch_state["fail"] = True
    missing_output_stats = run_dataset_pipeline_sync(retry_config)
    missing_output_state = json.loads(retry_config.stage_state_path.read_text(encoding="utf-8"))[
        "core_sources_ingest"
    ]
    missing_output_benchmark = json.loads(
        retry_config.benchmark_report_path.read_text(encoding="utf-8")
    )
    with duckdb.connect(str(retry_config.db_path), read_only=True) as con:
        missing_output_rows = con.execute(
            "SELECT count(*) FROM ds_observations WHERE dataset_id = 'wb-gdp'"
        ).fetchone()[0]

    assert fetch_state["calls"] == before_missing_output_retry + 1
    assert missing_output_stats.metrics["core_failures"] == 1
    assert missing_output_state["status"] == "warning"
    assert missing_output_state["metadata"]["publishable_core_complete"] is False
    assert missing_output_rows == 0
    assert missing_output_benchmark["evaluation_mode"] == "partial-eval"

    fetch_state["fail"] = False
    repaired_stats = run_dataset_pipeline_sync(retry_config)
    repaired_benchmark = json.loads(retry_config.benchmark_report_path.read_text(encoding="utf-8"))
    with duckdb.connect(str(retry_config.db_path), read_only=True) as con:
        repaired_rows = con.execute(
            "SELECT dataset_id, raw_variable, country_code, year, value "
            "FROM ds_observations WHERE dataset_id = 'wb-gdp'"
        ).fetchall()

    assert repaired_stats.metrics["core_failures"] == 0
    assert fetch_state["calls"] == before_missing_output_retry + 2
    assert repaired_rows == [("wb-gdp", "NY.GDP.PCAP.PP.CD", "UA", 2020, 1.1)]
    assert repaired_benchmark["evaluation_mode"] == "full-ready"

    with duckdb.connect(str(retry_config.db_path)) as con:
        con.execute(
            "UPDATE ds_variable_alignments SET confidence = confidence + 0.01 "
            "WHERE dataset_id = 'wb-gdp'"
        )
        con.execute("CHECKPOINT")

    altered_alignment_benchmark = run_benchmark(retry_config)
    altered_alignment_report = json.loads(
        retry_config.benchmark_report_path.read_text(encoding="utf-8")
    )
    assert altered_alignment_benchmark.metrics["benchmark_partial_eval"] == 1
    assert altered_alignment_report["evaluation_mode"] == "partial-eval"

    before_alignment_retry = fetch_state["calls"]
    fetch_state["fail"] = True
    altered_alignment_retry = run_dataset_pipeline_sync(retry_config)
    assert fetch_state["calls"] == before_alignment_retry + 1
    assert altered_alignment_retry.metrics["core_failures"] == 1

    calls_before_changed_plan = fetch_state["calls"]
    fetch_state["fail"] = False
    with duckdb.connect(str(retry_config.db_path)) as con:
        con.execute("UPDATE ds_datasets SET title = 'Changed plan input' WHERE id = 'wb-gdp'")
        con.execute("CHECKPOINT")
    changed_plan_stats = run_dataset_pipeline_sync(retry_config)
    changed_plan_benchmark = json.loads(
        retry_config.benchmark_report_path.read_text(encoding="utf-8")
    )
    assert fetch_state["calls"] == calls_before_changed_plan + 1
    assert changed_plan_stats.metrics["core_failures"] == 0
    assert changed_plan_benchmark["evaluation_mode"] == "full-ready"

    checkpoint_for_cache = json.loads(
        retry_config.observation_ingest_checkpoint_path.read_text(encoding="utf-8")
    )
    complete_for_cache = next(iter(checkpoint_for_cache["completed"]))
    deferred_for_cache = json.loads(json.dumps(checkpoint_for_cache))
    deferred_result = deferred_for_cache["completed"].pop(complete_for_cache)
    deferred_for_cache["deferred"][complete_for_cache] = {
        **deferred_result,
        "status": "deferred",
    }
    stage_state_before_cache_probe = retry_config.stage_state_path.read_bytes()
    benchmark_before_cache_probe = retry_config.benchmark_report_path.read_bytes()
    calls_before_cache_probe = fetch_state["calls"]
    retry_config.observation_ingest_checkpoint_path.write_text(
        json.dumps(deferred_for_cache), encoding="utf-8"
    )
    assert retry_config.stage_state_path.read_bytes() == stage_state_before_cache_probe
    assert retry_config.benchmark_report_path.read_bytes() == benchmark_before_cache_probe

    benchmark_only = replace(retry_config, stages=frozenset({"benchmark"}))
    cached_benchmark_stats = run_dataset_pipeline_sync(benchmark_only)
    cached_benchmark_report = json.loads(
        retry_config.benchmark_report_path.read_text(encoding="utf-8")
    )
    assert "benchmark" not in cached_benchmark_stats.skipped_stages
    assert cached_benchmark_stats.metrics["benchmark_partial_eval"] == 1
    assert cached_benchmark_report["evaluation_mode"] == "partial-eval"
    assert fetch_state["calls"] == calls_before_cache_probe
    partial_benchmark_receipt = current_content_stage_receipt(benchmark_only, "benchmark")
    assert partial_benchmark_receipt is not None
    benchmark_basis_config = partial_benchmark_receipt["input_basis"]["config"]
    core_receipt_basis_state = benchmark_basis_config["core_output_receipt_state"]
    assert core_receipt_basis_state["expected"] is True
    assert core_receipt_basis_state["matches_checkpoint_and_stage"] is False
    assert isinstance(core_receipt_basis_state["recomputed_receipt_digest"], str)

    repeated_benchmark_stats = run_dataset_pipeline_sync(benchmark_only)
    assert "benchmark" not in repeated_benchmark_stats.skipped_stages
    assert repeated_benchmark_stats.metrics["benchmark_partial_eval"] == 1


def test_core_sources_ingest_is_not_resumed_without_bound_fetch_receipt(tmp_path) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"core_sources_ingest"}),
        resume=True,
    )
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    config.db_path.write_bytes(b"existing catalog database")
    config.manifests_dir.mkdir(parents=True, exist_ok=True)
    (config.manifests_dir / "core_sources_ingest.json").write_text("{}", encoding="utf-8")
    _record_stage_completion(config, "core_sources_ingest")

    assert not _should_skip_stage(config, "core_sources_ingest")


def test_core_sources_run_signature_changes_with_producer_limit(tmp_path) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        max_datasets_per_source=100_000,
    )
    full_signature = config.run_signature

    config.max_datasets_per_source = 50

    assert config.run_signature != full_signature


def test_core_sources_run_signature_changes_with_registry_content(tmp_path) -> None:
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text("version: 1\nsources: []\n", encoding="utf-8")
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        registry_path=registry_path,
    )
    original_signature = config.run_signature

    registry_path.write_text("version: 2\nsources: []\n", encoding="utf-8")

    assert config.run_signature != original_signature


def test_benchmark_resume_requires_current_core_ingest_receipt(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        DatasetBatchConfig,
        "load_registry",
        lambda _self: SourceRegistry(version=1, sources=()),
    )
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"benchmark"}),
        resume=True,
    )
    config.benchmark_report_path.parent.mkdir(parents=True, exist_ok=True)
    config.benchmark_report_path.write_text("{}", encoding="utf-8")
    catalog_pipeline.write_json(
        config.stage_state_path,
        {
            "core_sources_ingest": {
                "status": "running",
                "metadata": {"publishable_core_pending": 1},
            }
        },
    )
    _record_stage_completion(config, "benchmark")
    assert not _should_skip_stage(config, "benchmark")

    catalog_pipeline.write_json(
        config.stage_state_path,
        {
            "core_sources_ingest": {
                "status": "complete",
                "metadata": {"publishable_core_pending": 0},
            },
            "benchmark": json.loads(config.stage_state_path.read_text(encoding="utf-8"))[
                "benchmark"
            ],
        },
    )
    _record_stage_completion(config, "benchmark")

    assert not _should_skip_stage(config, "benchmark")


def test_benchmark_resume_rejects_bulk_equivalence_manifest_change(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        DatasetBatchConfig,
        "load_registry",
        lambda _self: SourceRegistry(version=1, sources=()),
    )
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"benchmark"}),
        resume=True,
    )
    config.benchmark_report_path.parent.mkdir(parents=True, exist_ok=True)
    config.benchmark_report_path.write_text("{}", encoding="utf-8")
    manifest = config.manifests_dir / "observations" / "bulk_equivalence" / "fixture.json"
    catalog_pipeline.write_json(manifest, {"source": "fixture", "mismatches": 0})
    _record_stage_completion(config, "benchmark")
    assert _should_skip_stage(config, "benchmark")

    catalog_pipeline.write_json(manifest, {"source": "fixture", "mismatches": 1})

    assert not _should_skip_stage(config, "benchmark")


def test_benchmark_resume_rejects_unselected_raw_source_change(monkeypatch, tmp_path) -> None:
    registry = SourceRegistry(
        version=1,
        sources=(
            SourceSpec(
                name="blocking_source",
                family="worldbank",
                wave="A",
                endpoint="https://example.test/source",
                execution_tier="transport_ready",
                run_lane="empirical",
                publish_blocking=True,
            ),
        ),
    )
    monkeypatch.setattr(DatasetBatchConfig, "load_registry", lambda _self: registry)
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"benchmark"}),
        resume=True,
    )
    config.benchmark_report_path.parent.mkdir(parents=True, exist_ok=True)
    config.benchmark_report_path.write_text("{}", encoding="utf-8")
    payload = config.raw_dir / "blocking_source" / "snapshot" / "payload.jsonl"
    manifest = payload.with_name("manifest.json")
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_text('{"id":"a"}\n', encoding="utf-8")
    catalog_pipeline.write_json(manifest, {"source": "blocking_source", "count": 1})
    _record_stage_completion(config, "benchmark")
    assert _should_skip_stage(config, "benchmark")

    previous_stat = payload.stat()
    payload.write_text('{"id":"b"}\n', encoding="utf-8")
    _restore_stat(payload, previous_stat)

    assert not _should_skip_stage(config, "benchmark")


def test_qc_resume_rejects_selected_previous_snapshot_payload_change(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        DatasetBatchConfig,
        "load_registry",
        lambda _self: SourceRegistry(version=1, sources=()),
    )
    previous_root = tmp_path / "2026-10-01"
    current_root = tmp_path / "2026-10-06"
    config = DatasetBatchConfig(
        snapshot_root=current_root,
        stages=frozenset({"qc"}),
        resume=True,
    )
    config.qc_report_path.parent.mkdir(parents=True, exist_ok=True)
    config.qc_report_path.write_text("{}", encoding="utf-8")
    previous_payload = (
        previous_root / "datasets" / "raw" / "source" / "2026-10-01" / "payload.jsonl"
    )
    previous_manifest = previous_payload.with_name("manifest.json")
    previous_payload.parent.mkdir(parents=True, exist_ok=True)
    previous_payload.write_bytes(b"a\nb\n")
    catalog_pipeline.write_json(
        previous_manifest,
        {"source": "source", "payload": str(previous_payload), "count": 2},
    )
    _record_stage_completion(config, "qc")
    before = _stage_input_basis(config, "qc")
    assert not _should_skip_stage(config, "qc")

    previous_stat = previous_payload.stat()
    previous_payload.write_bytes(b"abcd")
    _restore_stat(previous_payload, previous_stat)

    after = _stage_input_basis(config, "qc")
    assert before["basis_digest"] != after["basis_digest"]
    assert not _should_skip_stage(config, "qc")


def test_changed_output_bytes_do_not_reuse_merge_stage(tmp_path) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"merge_dedup"}),
        resume=True,
    )
    normalized = config.normalized_dir / "records.jsonl"
    normalized.parent.mkdir(parents=True, exist_ok=True)
    normalized.write_text("input\n", encoding="utf-8")
    output = config.merged_records_path
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("output\n", encoding="utf-8")
    config.duplicates_report_path.write_text("dedup_key,kept_id,dropped_id\n", encoding="utf-8")
    _save_state(config, "merge_dedup", [output])

    assert _should_skip_stage(config, "merge_dedup")
    previous_stat = output.stat()
    output.write_text("mutput\n", encoding="utf-8")
    _restore_stat(output, previous_stat)

    assert not _should_skip_stage(config, "merge_dedup")


def test_legacy_directory_state_without_output_inventory_is_cache_miss(tmp_path) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"normalize"}),
        resume=True,
    )
    manifest = config.raw_dir / "source" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}\n", encoding="utf-8")
    config.normalized_dir.mkdir(parents=True, exist_ok=True)
    config.stage_state_path.parent.mkdir(parents=True, exist_ok=True)
    config.stage_state_path.write_text(
        json.dumps(
            {
                "normalize": {
                    "status": "complete",
                    "input_fingerprint": _stage_input_fingerprint(config, "normalize"),
                    "outputs": [str(config.normalized_dir)],
                    "metadata": {},
                }
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    assert not _should_skip_stage(config, "normalize")


def test_empty_normalize_output_directory_is_not_reusable(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"normalize"}),
        resume=True,
    )
    _stub_complete_harvest_receipt(monkeypatch, config)
    manifest = config.raw_dir / "source" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}\n", encoding="utf-8")
    _record_stage_completion(config, "normalize")

    assert not _should_skip_stage(config, "normalize")


def test_explicit_empty_required_outputs_do_not_fallback_to_recorded_outputs(tmp_path) -> None:
    state_path = tmp_path / "state.json"
    output = tmp_path / "output.txt"
    output.write_text("published\n", encoding="utf-8")
    save_stage_state(
        state_path,
        stage="fixture",
        status="complete",
        input_fingerprint="fixture-input",
        outputs=[output],
    )

    assert not stage_can_skip(
        state_path,
        stage="fixture",
        input_fingerprint="fixture-input",
        required_outputs=[],
    )


def test_content_stage_recompute_disables_inner_resume_checkpoint(monkeypatch, tmp_path) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"normalize"}),
        resume=True,
    )
    _stub_complete_harvest_receipt(monkeypatch, config)
    observed_resume: list[bool] = []

    def fake_normalize(stage_config) -> dict[str, int]:
        observed_resume.append(stage_config.resume)
        return {}

    monkeypatch.setattr(catalog_normalizer, "normalize_raw_sources", fake_normalize)
    run_dataset_pipeline_sync(config)

    assert observed_resume == [False]


def test_publish_receipt_binds_full_registry_bytes_and_selected_source_contract(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.yaml"

    def _write_registry(endpoint: str) -> None:
        registry_path.write_text(
            "\n".join(
                [
                    "version: 1",
                    "sources:",
                    "  - name: source_a",
                    "    family: worldbank",
                    "    wave: A",
                    f"    endpoint: {endpoint}",
                    "    enabled: true",
                    "    execution_tier: transport_ready",
                    "    run_lane: empirical",
                    "    publish_blocking: true",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    _write_registry("https://example.test/a")
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"publish"}),
        registry_path=registry_path,
        run_profile="prod_core_blocking",
    )
    for path in (
        config.db_path,
        config.merged_records_path,
        config.duplicates_report_path,
        config.benchmark_report_path,
        config.qc_report_path,
        config.publish_manifest_path,
        config.consumer_readiness_path,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")
    _record_stage_completion(config, "publish")
    receipt = current_content_stage_receipt(config, "publish")
    assert receipt is not None
    basis = receipt["input_basis"]
    assert isinstance(basis, dict)
    assert "source_registry" in basis["inputs"]
    assert basis["config"]["selected_sources"][0]["name"] == "source_a"

    prior_stat = registry_path.stat()
    _write_registry("https://example.test/changed")
    os.utime(registry_path, ns=(prior_stat.st_atime_ns, prior_stat.st_mtime_ns))
    assert current_content_stage_receipt(config, "publish") is None
    assert not _should_skip_stage(config, "publish")


def test_publish_receipt_requires_all_published_outputs(tmp_path: Path) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"publish"}),
    )
    for path in (
        config.db_path,
        config.merged_records_path,
        config.duplicates_report_path,
        config.benchmark_report_path,
        config.qc_report_path,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")

    _record_stage_completion(config, "publish")

    assert current_content_stage_receipt(config, "publish") is None


def test_standalone_content_receipt_requires_stable_inputs_and_real_outputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry_path = tmp_path / "registry.yaml"

    def write_registry(endpoint: str) -> None:
        registry_path.write_text(
            "\n".join(
                [
                    "version: 1",
                    "sources:",
                    "  - name: source_a",
                    "    family: worldbank",
                    "    wave: A",
                    f"    endpoint: {endpoint}",
                    "    enabled: true",
                    "    execution_tier: transport_ready",
                    "    run_lane: empirical",
                    "    publish_blocking: true",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    write_registry("https://example.test/a")
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"qc"}),
        registry_path=registry_path,
        run_profile="prod_core_blocking",
    )
    raw_dir = config.raw_dir / "source_a" / "20261006T000000Z"
    raw_dir.mkdir(parents=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"fixture"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="source_a",
        endpoint="https://example.test/a",
        payload_path=payload,
        count=1,
    )
    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    config.merged_records_path.write_text(
        '{"title":"Dataset","description":"Description"}\n', encoding="utf-8"
    )
    connection = duckdb.connect(str(config.db_path))
    connection.execute("CREATE TABLE ds_distributions (url VARCHAR)")
    connection.execute("CHECKPOINT")
    connection.close()

    result = run_content_stage_with_receipt(config, "qc")
    assert result.passed is True
    assert config.qc_report_path.exists()
    assert current_content_stage_receipt(config, "qc") is not None

    config.stage_state_path.unlink()

    def mutate_registry_during_real_qc(_config: DatasetBatchConfig) -> bool:
        write_registry("https://example.test/changed")
        return True

    monkeypatch.setattr(catalog_qc, "_is_smoke_like_run", mutate_registry_during_real_qc)
    with pytest.raises(RuntimeError, match="inputs changed while its producer was running"):
        run_content_stage_with_receipt(config, "qc")
    assert current_content_stage_receipt(config, "qc") is None


@pytest.mark.parametrize(
    ("artifact_name", "changed_bytes"),
    [
        (
            "merged_records_path",
            b'{"source":"source_a","title":"Changed","description":"Description"}\n',
        ),
        (
            "duplicates_report_path",
            b"source,kept_id,dropped_id\nsource_a,1,2\n",
        ),
    ],
)
def test_real_qc_receipt_binds_shared_merged_and_duplicate_inputs(
    tmp_path: Path,
    artifact_name: str,
    changed_bytes: bytes,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        "\n".join(
            [
                "version: 1",
                "sources:",
                "  - name: source_a",
                "    family: worldbank",
                "    wave: A",
                "    endpoint: https://example.test/a",
                "    enabled: true",
                "    execution_tier: transport_ready",
                "    run_lane: empirical",
                "    publish_blocking: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"qc"}),
        registry_path=registry_path,
        run_profile="prod_core_blocking",
    )
    raw_dir = config.raw_dir / "source_a" / "20261006T000000Z"
    raw_dir.mkdir(parents=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"fixture"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="source_a",
        endpoint="https://example.test/a",
        payload_path=payload,
        count=1,
    )
    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    config.merged_records_path.write_bytes(
        b'{"source":"source_a","title":"Dataset","description":"Description"}\n'
    )
    config.duplicates_report_path.write_bytes(b"source,kept_id,dropped_id\n")
    with duckdb.connect(str(config.db_path)) as connection:
        connection.execute("CREATE TABLE ds_distributions (url VARCHAR)")
        connection.execute("CHECKPOINT")

    for stage in ("benchmark", "qc", "publish"):
        basis = _stage_input_basis(config, stage)
        for input_name, path in (
            ("merged_records", config.merged_records_path),
            ("duplicates_report", config.duplicates_report_path),
        ):
            input_spec = basis["inputs"][input_name]
            assert isinstance(input_spec, dict)
            records = input_spec["records"]
            assert isinstance(records, list)
            assert any(
                isinstance(record, dict) and record.get("path") == str(path.resolve())
                for record in records
            )

    result = run_content_stage_with_receipt(config, "qc")
    assert result.passed is True
    receipt = current_content_stage_receipt(config, "qc")
    assert receipt is not None

    artifact = getattr(config, artifact_name)
    previous_stat = artifact.stat()
    artifact.write_bytes(changed_bytes)
    _restore_stat(artifact, previous_stat)

    assert current_content_stage_receipt(config, "qc") is None


def test_selected_empty_generation_is_reused_without_reencoding(monkeypatch, tmp_path) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"embed"}),
        resume=True,
        embedding_model="fixture-model",
        embedding_dimension=4,
    )
    _create_empty_embedding_database(config)
    assert build_embedding_generation(
        rows=[],
        index_dir=config.index_dir,
        embedding_model="fixture-model",
        embedding_device="cpu",
        embedding_dimension=4,
    ) == (0, 4)
    _record_stage_completion(config, "embed")

    def fail_if_reembedded(*_args, **_kwargs):
        raise AssertionError("selected generation was unnecessarily re-encoded")

    monkeypatch.setattr(catalog_embedder, "run_embed", fail_if_reembedded)
    stats = run_dataset_pipeline_sync(config)

    assert stats.skipped_stages == ["embed"]


def test_embed_resume_rejects_config_rule_and_selected_output_changes(
    monkeypatch, tmp_path
) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"embed"}),
        resume=True,
        embedding_model="fixture-model",
        embedding_dimension=4,
    )
    _create_empty_embedding_database(config)
    assert build_embedding_generation(
        rows=[],
        index_dir=config.index_dir,
        embedding_model="fixture-model",
        embedding_device="cpu",
        embedding_dimension=4,
    ) == (0, 4)
    _record_stage_completion(config, "embed")
    assert _should_skip_stage(config, "embed")

    config.embedding_model = "changed-model"
    assert not _should_skip_stage(config, "embed")
    config.embedding_model = "fixture-model"

    from polisyos.data_forge.domains.catalog.batch import pipeline as pipeline_module

    monkeypatch.setitem(
        pipeline_module._STAGE_RULE_VERSIONS, "embed", "policyos.catalog.embed.changed"
    )
    assert not _should_skip_stage(config, "embed")

    monkeypatch.setitem(pipeline_module._STAGE_RULE_VERSIONS, "embed", "policyos.catalog.embed.v2")
    selector = json.loads(
        (config.index_dir / "embedding_generation.json").read_text(encoding="utf-8")
    )
    generation_dir = config.index_dir / "embedding_generations" / str(selector["generation_id"])
    (generation_dir / "embeddings.npz").unlink()
    assert not _should_skip_stage(config, "embed")
    _record_stage_completion(config, "embed")
    assert not _should_skip_stage(config, "embed")


def test_interrupted_embed_state_is_never_reusable(tmp_path) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"embed"}),
        resume=True,
    )
    save_stage_state(
        config.stage_state_path,
        stage="embed",
        status="running",
        input_fingerprint=_stage_input_fingerprint(config, "embed"),
        outputs=[config.index_dir / "embedding_generation.json"],
        input_basis={},
        output_inventory={},
    )

    assert not _should_skip_stage(config, "embed")


def test_incomplete_selected_harvest_cannot_resume_and_failed_source_retries(
    monkeypatch, tmp_path
) -> None:
    registry = SourceRegistry(
        version=1,
        sources=(
            SourceSpec(
                name="source_a",
                family="worldbank",
                wave="A",
                endpoint="https://example.test/a",
                execution_tier="transport_ready",
                run_lane="empirical",
                publish_blocking=True,
            ),
            SourceSpec(
                name="source_b",
                family="worldbank",
                wave="A",
                endpoint="https://example.test/b",
                execution_tier="transport_ready",
                run_lane="empirical",
                publish_blocking=True,
            ),
        ),
    )
    monkeypatch.setattr(DatasetBatchConfig, "load_registry", lambda _self: registry)
    monkeypatch.setattr(catalog_harvester, "load_metrics_map", lambda _path: {})
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"harvest"}),
        run_profile="prod_core_blocking",
    )
    fail_source_b = False
    calls: dict[str, int] = {}

    async def _harvest_worldbank(endpoint: str, _limit: int, _timeout: int) -> list[dict]:
        calls[endpoint] = calls.get(endpoint, 0) + 1
        if fail_source_b and endpoint.endswith("/b"):
            raise RuntimeError("temporary source failure")
        return [{"id": endpoint.rsplit("/", maxsplit=1)[-1], "name": "fixture"}]

    monkeypatch.setattr(catalog_harvester, "_harvest_worldbank", _harvest_worldbank)

    asyncio.run(catalog_harvester.harvest_sources(config))
    _record_stage_completion(config, "harvest")
    config.resume = True
    assert _should_skip_stage(config, "harvest")

    fail_source_b = True
    config.resume = False
    with pytest.raises(RuntimeError, match=r"harvest incomplete.*source_b"):
        asyncio.run(catalog_harvester.harvest_sources(config))
    failed_manifest = json.loads(
        (config.manifests_dir / "harvest.json").read_text(encoding="utf-8")
    )
    assert failed_manifest["status"] == "partial"
    assert failed_manifest["metrics"]["selected_sources"] == ["source_a", "source_b"]
    assert failed_manifest["metrics"]["failed_sources"] == ["source_b"]
    config.resume = True
    assert not _should_skip_stage(config, "harvest")

    config.stages = frozenset({"normalize"})
    with pytest.raises(RuntimeError, match="normalize requires a complete receipt"):
        run_dataset_pipeline_sync(config)
    config.stages = frozenset({"harvest"})

    fail_source_b = False
    asyncio.run(catalog_harvester.harvest_sources(config))
    _record_stage_completion(config, "harvest")
    assert calls == {"https://example.test/a": 2, "https://example.test/b": 3}
    assert _should_skip_stage(config, "harvest")

    successful_manifest = json.loads(
        (config.manifests_dir / "harvest.json").read_text(encoding="utf-8")
    )
    payload_path = Path(
        successful_manifest["metrics"]["source_outcomes"]["source_b"]["payload_path"]
    )
    original_stat = payload_path.stat()
    payload_path.write_bytes(payload_path.read_bytes().replace(b'"id": "b"', b'"id": "c"'))
    _restore_stat(payload_path, original_stat)
    assert not _should_skip_stage(config, "harvest")


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("max_sync_cells", 2),
        ("base_url", "https://example.test/changed"),
        ("description", "same-ID profile byte change"),
        ("dataset_discovery_hints", ["changed_dataset", "second_dataset"]),
        ("preferred_core_transport", "changed_transport"),
    ],
)
def test_same_id_live_source_profile_change_invalidates_stage_receipts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
    replacement: object,
) -> None:
    from polisyos.data_forge.domains.catalog.batch.core_sources.api import (
        _resolve_profile_config,
        _resolve_source_execution_policy,
    )
    from polisyos.fabric.connectors.profiles.models import SourceProfile
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    profiles = SourceProfileRegistry()
    profile = SourceProfile(
        profile_id="fixture_profile",
        display_name="Fixture",
        description="All non-default profile fields",
        connector_family="sdmx",
        base_url="https://example.test/source",
        auth_policy="api_key",
        timeout_seconds=17,
        max_retries=5,
        rate_limit_rps=2.5,
        max_concurrency=8,
        requests_per_hour=400,
        supports_async_large_responses=True,
        schema_preflight=True,
        preferred_transport="fixture",
        preferred_core_transport="fixture_core",
        preferred_backfill_transport="fixture_backfill",
        bulk_download_url="https://example.test/bulk",
        bulk_format="CSV",
        supports_content_constraints=True,
        supports_availability_constraints=True,
        supports_async_fetch=True,
        fallback_on_capability_failure="fixture_fallback",
        core_group_limit=2,
        backfill_group_limit=3,
        max_sync_cells=1,
        max_async_cells=900,
        capability_cache_ttl_hours=7,
        negative_cache_ttl_hours=5,
        soft_negative_cache_ttl_hours=3,
        dataset_discovery_hints=["fixture_dataset", "second_dataset"],
        tags=["fixture_tag", "second_tag"],
        source_organization="Fixture organization",
        source_url="https://example.test/about",
        estimated_datasets=12,
    )
    profiles.register(profile)
    monkeypatch.setattr(SourceProfileRegistry, "_instance", profiles)
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text("version: 1\nsources: []\n", encoding="utf-8")
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        registry_path=registry_path,
        stages=frozenset({"benchmark", "publish"}),
        resume=True,
    )
    for output in (
        config.benchmark_report_path,
        config.publish_manifest_path,
        config.consumer_readiness_path,
    ):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("{}", encoding="utf-8")
    for stage in ("benchmark", "publish"):
        _record_stage_completion(config, stage)
        assert _should_skip_stage(config, stage)
        assert current_content_stage_receipt(config, stage) is not None
    initial_signature = config.run_signature
    marker_bytes = config.stage_state_path.read_bytes()
    registry_bytes = registry_path.read_bytes()
    assert (
        _resolve_source_execution_policy(
            source="fixture", profile_id="fixture_profile"
        ).max_sync_cells
        == 1
    )
    assert _resolve_profile_config("fixture_profile").url == "https://example.test/source"

    # New object, identical bytes and only YAML write-time drift retain reuse.
    profiles.register(profile.model_copy(deep=True), override=True)
    previous_stat = registry_path.stat()
    os.utime(
        registry_path,
        ns=(previous_stat.st_atime_ns, previous_stat.st_mtime_ns + 1_000_000),
    )
    assert config.run_signature == initial_signature
    assert all(_should_skip_stage(config, stage) for stage in ("benchmark", "publish"))
    profiles.register(profile.model_copy(update={field: replacement}, deep=True), override=True)

    assert registry_path.read_bytes() == registry_bytes
    assert config.stage_state_path.read_bytes() == marker_bytes
    assert config.run_signature != initial_signature
    if field == "max_sync_cells":
        assert (
            _resolve_source_execution_policy(
                source="fixture", profile_id="fixture_profile"
            ).max_sync_cells
            == 2
        )
    if field == "base_url":
        assert _resolve_profile_config("fixture_profile").url == replacement
    if field == "preferred_core_transport":
        assert (
            _resolve_source_execution_policy(
                source="fixture", profile_id="fixture_profile"
            ).preferred_core_transport
            == replacement
        )
    for stage in ("benchmark", "publish"):
        assert not _should_skip_stage(config, stage)
        assert current_content_stage_receipt(config, stage) is None


def test_real_qc_receipt_rejects_same_id_live_source_profile_change(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from polisyos.fabric.connectors.profiles.models import SourceProfile
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    profiles = SourceProfileRegistry()
    profile = SourceProfile(
        profile_id="fixture_profile",
        display_name="Fixture",
        connector_family="worldbank",
        base_url="https://example.test/source",
        max_sync_cells=1,
    )
    profiles.register(profile)
    monkeypatch.setattr(SourceProfileRegistry, "_instance", profiles)
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        "version: 1\nsources:\n"
        "  - name: source_a\n"
        "    family: worldbank\n"
        "    wave: A\n"
        "    endpoint: https://example.test/source\n"
        "    profile_id: fixture_profile\n"
        "    enabled: true\n"
        "    execution_tier: transport_ready\n"
        "    run_lane: empirical\n"
        "    publish_blocking: true\n",
        encoding="utf-8",
    )
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"qc"}),
        registry_path=registry_path,
        run_profile="prod_core_blocking",
    )
    raw_dir = config.raw_dir / "source_a" / "fixture-snapshot"
    raw_dir.mkdir(parents=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"fixture"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="source_a",
        endpoint="https://example.test/source",
        payload_path=payload,
        count=1,
    )
    config.merged_records_path.write_text(
        '{"source":"source_a","title":"Dataset","description":"Description"}\n',
        encoding="utf-8",
    )
    config.duplicates_report_path.write_text("source,kept_id,dropped_id\n", encoding="utf-8")
    with duckdb.connect(str(config.db_path)) as connection:
        connection.execute("CREATE TABLE ds_distributions (url VARCHAR)")
        connection.execute("CHECKPOINT")

    result = run_content_stage_with_receipt(config, "qc")
    assert result.passed is True
    assert current_content_stage_receipt(config, "qc") is not None
    report_bytes = config.qc_report_path.read_bytes()
    marker_bytes = config.stage_state_path.read_bytes()

    profiles.register(profile.model_copy(update={"max_sync_cells": 2}, deep=True), override=True)

    assert config.qc_report_path.read_bytes() == report_bytes
    assert config.stage_state_path.read_bytes() == marker_bytes
    assert current_content_stage_receipt(config, "qc") is None


def test_all_header_policy_is_a_declared_profile_currentness_residual(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from polisyos.data_forge.domains.catalog.batch.core_sources.api import _resolve_profile_config
    from polisyos.fabric.connectors.profiles.models import SourceProfile
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    profiles = SourceProfileRegistry()
    profile = SourceProfile(
        profile_id="fixture_profile",
        display_name="Fixture",
        connector_family="sdmx",
        base_url="https://example.test/source",
        headers={"Accept": "application/json"},
    )
    profiles.register(profile)
    monkeypatch.setattr(SourceProfileRegistry, "_instance", profiles)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snapshot")
    initial_signature = config.run_signature
    assert _resolve_profile_config("fixture_profile").headers["Accept"] == "application/json"

    profiles.register(
        profile.model_copy(update={"headers": {"Accept": "text/csv"}}, deep=True),
        override=True,
    )

    assert _resolve_profile_config("fixture_profile").headers["Accept"] == "text/csv"
    # This is an exposed limitation, never evidence of complete effective-policy currentness.
    assert config.run_signature == initial_signature


@pytest.mark.parametrize("material_change", ["profile_url", "seed_evidence"])
def test_material_input_change_recomputes_real_producer_and_benchmark(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, material_change: str
) -> None:
    from datetime import UTC, datetime

    import pandas as pd

    from polisyos.data_forge.domains.catalog.batch.core_sources import api as core_api
    from polisyos.data_forge.domains.catalog.batch.core_sources.validators import (
        _current_core_output_receipt_state,
    )
    from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        DatasetRecord,
        DistributionRecord,
    )
    from polisyos.fabric.connectors.base import ConnectionHandle, DatasetCapabilitySnapshot
    from polisyos.fabric.connectors.profiles.models import SourceProfile
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
    from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector

    profiles = SourceProfileRegistry()
    profile = SourceProfile(
        profile_id="worldbank_wdi",
        display_name="Fixture World Bank",
        connector_family="worldbank",
        base_url="https://example.test/original",
    )
    profiles.register(profile)
    monkeypatch.setattr(SourceProfileRegistry, "_instance", profiles)
    seed_path = tmp_path / "seed_variable_alignments.yaml"
    seed_path.write_text(
        "alignments:\n"
        "  - canonical_var: economic.gdp\n"
        "    dataset_var: NY.GDP.MKTP.CD\n"
        "    dataset_id: WB_WDI\n"
        "    method: exact\n"
        "    confidence: 1.0\n"
        "    evidence: seed_worldbank_wdi\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(core_api, "_seed_alignments_path", lambda: seed_path)
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        "version: 1\nsources:\n"
        "  - name: worldbank\n"
        "    family: worldbank\n"
        "    wave: A\n"
        "    endpoint: https://example.test/worldbank\n"
        "    connector_id: worldbank.wdi\n"
        "    profile_id: worldbank_wdi\n"
        "    enabled: true\n"
        "    execution_tier: transport_ready\n"
        "    run_lane: empirical\n"
        "    publish_blocking: true\n",
        encoding="utf-8",
    )
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        registry_path=registry_path,
        stages=frozenset({"core_sources_ingest", "benchmark"}),
        run_profile="preflight_core",
        promoted_sources=("worldbank",),
        preflight_sources=("worldbank",),
        active_countries=("UA",),
        active_year_window=(2020, 2020),
        observation_mode="core",
        max_datasets_per_source=1,
        resume=True,
        resume_mode="force",
    )
    build_graph(
        records=[
            DatasetRecord(
                id="wb-gdp",
                title="Fixture indicator",
                description="Fixture indicator",
                source="worldbank",
                source_portal="worldbank",
                dataset_id="NY.GDP.MKTP.CD",
                source_dataset_id="NY.GDP.MKTP.CD",
                execution_tier="transport_ready",
                update_frequency="annual",
                polisyos_metrics=[],
                variables=["NY.GDP.MKTP.CD"],
                preferred_distribution_id="dist-wb",
                distributions=[
                    DistributionRecord(
                        id="dist-wb",
                        connector_type="worldbank.wdi",
                        profile_id="worldbank_wdi",
                        source_locator="NY.GDP.MKTP.CD",
                        parser_supported=True,
                        machine_readable=True,
                    )
                ],
            )
        ],
        db_path=config.db_path,
    )
    fetch_urls: list[str] = []

    async def describe_dataset(
        _connector: WorldBankConnector, _handle: ConnectionHandle, dataset_id: str
    ) -> DatasetCapabilitySnapshot:
        return DatasetCapabilitySnapshot(
            source="worldbank",
            dataset_id=dataset_id,
            resolved_dataset_id=dataset_id,
            last_checked_at=datetime.now(UTC),
        )

    async def fetch_dataset(
        connector: WorldBankConnector, handle: ConnectionHandle, _request: object
    ) -> object:
        url = handle.config.url
        assert connector._base_url(handle) == url
        assert url in {"https://example.test/original", "https://example.test/changed"}
        fetch_urls.append(url)
        value = 1.1 if url == "https://example.test/original" else 2.2
        return type(
            "WorldBankFixtureResult",
            (),
            {"data": pd.DataFrame([{"country_code": "UA", "year": 2020, "value": value}])},
        )()

    monkeypatch.setattr(WorldBankConnector, "describe_dataset", describe_dataset)
    monkeypatch.setattr(WorldBankConnector, "fetch", fetch_dataset)

    initial = run_dataset_pipeline_sync(config)
    assert initial.metrics["core_observations"] == 1
    assert fetch_urls == ["https://example.test/original"]
    with duckdb.connect(str(config.db_path), read_only=True) as connection:
        initial_rows = connection.execute(
            "SELECT dataset_id, raw_variable, country_code, year, value "
            "FROM ds_observations WHERE dataset_id = 'wb-gdp'"
        ).fetchall()
    initial_report = json.loads(config.benchmark_report_path.read_text(encoding="utf-8"))
    assert initial_rows == [("wb-gdp", "NY.GDP.MKTP.CD", "UA", 2020, 1.1)]
    assert initial_report["evaluation_mode"] == "full-ready"
    assert initial_report["diagnostic_context"]["core_output_receipt_current"] is True
    assert _current_core_output_receipt_state(config).is_current
    assert _should_skip_stage(config, "benchmark")
    with duckdb.connect(str(config.db_path), read_only=True) as connection:
        initial_evidence = connection.execute(
            "SELECT evidence FROM ds_variable_alignments WHERE dataset_id = 'wb-gdp' "
            "AND raw_variable = 'NY.GDP.MKTP.CD'"
        ).fetchall()
    assert initial_evidence == [("seed_worldbank_wdi;source=worldbank",)]
    initial_signature = config.run_signature
    profiles.register(profile.model_copy(deep=True), override=True)
    registry_stat = registry_path.stat()
    os.utime(
        registry_path,
        ns=(registry_stat.st_atime_ns, registry_stat.st_mtime_ns + 1_000_000),
    )
    seed_stat = seed_path.stat()
    os.utime(
        seed_path,
        ns=(seed_stat.st_atime_ns, seed_stat.st_mtime_ns + 1_000_000),
    )
    assert config.run_signature == initial_signature
    run_dataset_pipeline_sync(config)
    assert fetch_urls == ["https://example.test/original"]

    marker_bytes = config.stage_state_path.read_bytes()
    checkpoint_bytes = config.observation_ingest_checkpoint_path.read_bytes()
    report_bytes = config.benchmark_report_path.read_bytes()
    registry_bytes = registry_path.read_bytes()
    if material_change == "profile_url":
        profiles.register(
            profile.model_copy(update={"base_url": "https://example.test/changed"}, deep=True),
            override=True,
        )
        expected_url = "https://example.test/changed"
        expected_value = 2.2
        expected_evidence = "seed_worldbank_wdi;source=worldbank"
    else:
        previous_seed_stat = seed_path.stat()
        original_seed_bytes = seed_path.read_bytes()
        seed_path.write_bytes(
            original_seed_bytes.replace(b"seed_worldbank_wdi", b"seed_worldbank_alt")
        )
        assert seed_path.stat().st_size == previous_seed_stat.st_size
        _restore_stat(seed_path, previous_seed_stat)
        assert seed_path.stat().st_mtime_ns == previous_seed_stat.st_mtime_ns
        expected_url = "https://example.test/original"
        expected_value = 1.1
        expected_evidence = "seed_worldbank_alt;source=worldbank"
    assert registry_path.read_bytes() == registry_bytes
    assert config.stage_state_path.read_bytes() == marker_bytes
    assert config.observation_ingest_checkpoint_path.read_bytes() == checkpoint_bytes
    assert config.benchmark_report_path.read_bytes() == report_bytes
    assert config.run_signature != initial_signature
    with duckdb.connect(str(config.db_path), read_only=True) as connection:
        held_evidence = connection.execute(
            "SELECT evidence FROM ds_variable_alignments WHERE dataset_id = 'wb-gdp' "
            "AND raw_variable = 'NY.GDP.MKTP.CD'"
        ).fetchall()
    assert held_evidence == initial_evidence
    assert not _current_core_output_receipt_state(config).is_current
    assert not _should_skip_stage(config, "benchmark")
    assert current_content_stage_receipt(config, "benchmark") is None

    benchmark_only = replace(config, stages=frozenset({"benchmark"}))
    stale = run_dataset_pipeline_sync(benchmark_only)
    partial = json.loads(config.benchmark_report_path.read_text(encoding="utf-8"))
    assert "benchmark" not in stale.skipped_stages
    assert fetch_urls == ["https://example.test/original"]
    assert partial["evaluation_mode"] == "partial-eval"
    assert partial["metrics"]["benchmark_partial_eval"] == 1
    assert partial["diagnostic_context"]["core_output_receipt_current"] is False
    assert not _should_skip_stage(benchmark_only, "benchmark")

    repaired = run_dataset_pipeline_sync(config)
    checkpoint = json.loads(config.observation_ingest_checkpoint_path.read_text(encoding="utf-8"))
    metadata = json.loads(config.stage_state_path.read_text(encoding="utf-8"))[
        "core_sources_ingest"
    ]["metadata"]
    current = _current_core_output_receipt_state(config)
    report = json.loads(config.benchmark_report_path.read_text(encoding="utf-8"))
    with duckdb.connect(str(config.db_path), read_only=True) as connection:
        rows = connection.execute(
            "SELECT dataset_id, raw_variable, country_code, year, value "
            "FROM ds_observations WHERE dataset_id = 'wb-gdp'"
        ).fetchall()
        evidence = connection.execute(
            "SELECT evidence FROM ds_variable_alignments WHERE dataset_id = 'wb-gdp' "
            "AND raw_variable = 'NY.GDP.MKTP.CD'"
        ).fetchall()

    assert repaired.metrics["core_failures"] == 0
    assert fetch_urls == ["https://example.test/original", expected_url]
    assert rows == [("wb-gdp", "NY.GDP.MKTP.CD", "UA", 2020, expected_value)]
    assert evidence == [(expected_evidence,)]
    assert checkpoint["planner_signature"] == config.run_signature
    assert {item["status"] for item in checkpoint["completed"].values()} == {"complete_with_rows"}
    assert current.is_current
    assert current.current_receipt is not None
    assert checkpoint["core_output_receipt"] == metadata["core_output_receipt"]
    assert metadata["core_output_receipt"] == current.current_receipt
    assert report["evaluation_mode"] == "full-ready"
    assert report["metrics"]["benchmark_partial_eval"] == 0
    assert report["diagnostic_context"]["core_output_receipt_current"] is True
    assert (
        report["diagnostic_context"]["core_output_receipt_digest"]
        == current.current_receipt["basis_digest"]
    )
    assert report["diagnostic_context"]["publishable_core_complete"] is True
    assert report["diagnostic_context"]["publishable_core_pending"] == 0
    assert current_content_stage_receipt(config, "benchmark") is not None
    fresh_benchmark = replace(config, stages=frozenset({"benchmark"}))
    fresh_stats = run_dataset_pipeline_sync(fresh_benchmark)
    assert "benchmark" in fresh_stats.skipped_stages
    assert fetch_urls == ["https://example.test/original", expected_url]
    assert _current_core_output_receipt_state(fresh_benchmark).is_current
    assert current_content_stage_receipt(fresh_benchmark, "benchmark") is not None


def test_warm_proxy_policy_change_updates_actual_catalog_alignment(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
        CatalogTransportDataset,
    )
    from polisyos.data_forge.domains.catalog.batch.core_sources import registry as core_registry
    from polisyos.data_forge.domains.catalog.knowledge import proxy_penalties

    proxy_path = tmp_path / "proxy.yaml"
    proxy_path.write_text(
        "mappings:\n  fixture_metric:\n"
        "    - canonical_var: economic.gdp\n"
        "      confidence: 0.8\n      proxy_penalty: 0.2\n",
        encoding="utf-8",
    )
    seed_path = tmp_path / "seed.yaml"
    seed_path.write_text("alignments: []\n", encoding="utf-8")
    monkeypatch.setattr(proxy_penalties, "default_proxy_metric_alignments_path", lambda: proxy_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snapshot")
    dataset = CatalogTransportDataset(
        catalog_dataset_id="fixture",
        source="worldbank",
        title="Fixture indicator",
        description="",
        source_dataset_id="FIXTURE",
        update_frequency="annual",
        last_updated="",
        coverage_json="{}",
        access_json="{}",
        execution_tier="transport_ready",
        variables=("FIXTURE",),
        keywords=(),
        themes=(),
        polisyos_metrics=("fixture_metric",),
        connector_id="worldbank.wdi",
        profile_id="worldbank_wdi",
        request_dataset_id="FIXTURE",
        default_filters={},
    )

    def persisted_alignment() -> tuple:
        alignments = core_registry._build_catalog_alignments([dataset], seed_path)
        with duckdb.connect(":memory:") as connection:
            connection.execute(
                "CREATE TABLE ds_variable_alignments (dataset_id VARCHAR, raw_variable VARCHAR, "
                "canonical_var VARCHAR, method VARCHAR, confidence DOUBLE, evidence VARCHAR, "
                "is_proxy BOOLEAN, proxy_penalty DOUBLE, "
                "PRIMARY KEY (dataset_id, raw_variable, canonical_var))"
            )
            assert core_registry._upsert_catalog_alignments(connection, alignments) == 1
            return connection.execute(
                "SELECT canonical_var, confidence, proxy_penalty, evidence, is_proxy "
                "FROM ds_variable_alignments"
            ).fetchone()

    assert persisted_alignment() == (
        "economic.gdp",
        0.8,
        0.2,
        "metric_binding_proxy:fixture_metric",
        True,
    )
    signature = config.run_signature
    previous_stat = proxy_path.stat()
    os.utime(proxy_path, ns=(previous_stat.st_atime_ns, previous_stat.st_mtime_ns + 1_000_000))
    assert config.run_signature == signature
    assert proxy_penalties.metric_proxy_alignments("fixture_metric")[0].proxy_penalty == 0.2
    previous_stat = proxy_path.stat()
    proxy_path.write_bytes(
        proxy_path.read_bytes().replace(b"proxy_penalty: 0.2", b"proxy_penalty: 0.4")
    )
    _restore_stat(proxy_path, previous_stat)
    assert proxy_path.stat().st_mtime_ns == previous_stat.st_mtime_ns
    changed = persisted_alignment()
    assert changed == ("economic.gdp", 0.8, 0.4, "metric_binding_proxy:fixture_metric", True)
    assert config.run_signature != signature
    changed_signature = config.run_signature
    proxy_path.unlink()
    assert proxy_penalties.metric_proxy_alignments("fixture_metric") == ()
    absent_signature = config.run_signature
    assert absent_signature != changed_signature
    proxy_path.write_bytes(b"")
    assert proxy_penalties.metric_proxy_alignments("fixture_metric") == ()
    assert config.run_signature != absent_signature


def test_warm_wvs_policy_change_updates_selected_bulk_rows_and_harvest_catalog(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from polisyos.data_forge.domains.catalog.batch.core_sources import loaders, transformers

    registry_path = tmp_path / "wvs.yaml"
    registry_path.write_text(
        "indicators:\n  A165:\n    title: Fixture first\n"
        "    aggregation: weighted_mean\n    response_type: binary\n"
        "    canonical_candidates: [social.trust]\n",
        encoding="utf-8",
    )
    csv_path = tmp_path / "wvs.csv"
    csv_path.write_text(
        "COUNTRY_ALPHA,S020,S002VS,S017,S018,A165\nUKR,2020,7,1,1,1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(loaders, "_wvs_registry_path", lambda: registry_path)
    monkeypatch.setattr(catalog_harvester, "_wvs_registry_path", lambda: registry_path)
    monkeypatch.setattr(loaders, "_wvs_bulk_csv_path", lambda: csv_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snapshot")
    initial_rows = loaders._load_wvs_bulk_rows("A165", year_window=(2020, 2020))
    assert len(initial_rows) == 1
    assert initial_rows[0]["country_code"] == "UA"
    assert initial_rows[0]["value"] == 1.0
    assert initial_rows[0]["aggregation_method"] == "weighted_mean"
    normalized = transformers._normalize_observation_row(initial_rows[0])
    assert normalized is not None
    assert json.loads(normalized[-1])["aggregation_method"] == "weighted_mean"
    assert (
        catalog_harvester._load_wvs_indicator_catalog_from_local_file()[0]["name"]
        == "Fixture first"
    )
    signature = config.run_signature
    previous_stat = registry_path.stat()
    os.utime(registry_path, ns=(previous_stat.st_atime_ns, previous_stat.st_mtime_ns + 1_000_000))
    assert config.run_signature == signature
    previous_stat = registry_path.stat()
    original = registry_path.read_bytes()
    changed = original.replace(b"Fixture first", b"Fixture later").replace(
        b"weighted_mean", b"weighted_mode"
    )
    assert len(changed) == len(original)
    registry_path.write_bytes(changed)
    _restore_stat(registry_path, previous_stat)
    assert registry_path.stat().st_mtime_ns == previous_stat.st_mtime_ns
    changed_rows = loaders._load_wvs_bulk_rows("A165", year_window=(2020, 2020))
    assert changed_rows[0]["aggregation_method"] == "weighted_mode"
    assert changed_rows[0]["value"] == initial_rows[0]["value"]
    normalized = transformers._normalize_observation_row(changed_rows[0])
    assert normalized is not None
    assert json.loads(normalized[-1])["aggregation_method"] == "weighted_mode"
    assert (
        catalog_harvester._load_wvs_indicator_catalog_from_local_file()[0]["name"]
        == "Fixture later"
    )
    assert config.run_signature != signature


def test_wvs_metadata_fallback_tracks_actual_branch_and_optional_asset(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from openpyxl import Workbook

    from polisyos.data_forge.domains.catalog.batch.core_sources import loaders

    registry_path = tmp_path / "wvs.yaml"
    variable_path = tmp_path / "wvs.xlsx"
    monkeypatch.setattr(loaders, "_wvs_registry_path", lambda: registry_path)
    monkeypatch.setattr(catalog_harvester, "_wvs_registry_path", lambda: registry_path)
    monkeypatch.setattr(catalog_harvester, "_wvs_variable_catalog_path", lambda: variable_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snapshot")
    absent_signature = config.run_signature
    assert catalog_harvester._load_wvs_indicator_catalog_from_local_file() == (
        catalog_harvester._WVS_STATIC_INDICATORS
    )

    def write_codebook(title: str) -> None:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["Variable", "Title"])
        worksheet.append(["FIXTURE", title])
        workbook.save(variable_path)
        workbook.close()

    write_codebook("Fixture first")
    assert (
        catalog_harvester._load_wvs_indicator_catalog_from_local_file()[0]["name"]
        == "Fixture first"
    )
    present_signature = config.run_signature
    assert present_signature != absent_signature
    previous_stat = variable_path.stat()
    os.utime(variable_path, ns=(previous_stat.st_atime_ns, previous_stat.st_mtime_ns + 1_000_000))
    assert config.run_signature == present_signature
    previous_stat = variable_path.stat()
    write_codebook("Fixture later")
    _restore_stat(variable_path, previous_stat)
    assert variable_path.stat().st_mtime_ns == previous_stat.st_mtime_ns
    assert (
        catalog_harvester._load_wvs_indicator_catalog_from_local_file()[0]["name"]
        == "Fixture later"
    )
    assert config.run_signature != present_signature

    registry_path.write_text("indicators:\n  A165:\n    title: Primary YAML\n", encoding="utf-8")
    primary_signature = config.run_signature
    assert (
        catalog_harvester._load_wvs_indicator_catalog_from_local_file()[0]["name"] == "Primary YAML"
    )
    variable_path.unlink()
    variable_path.mkdir()
    assert config.run_signature == primary_signature
    assert (
        catalog_harvester._load_wvs_indicator_catalog_from_local_file()[0]["name"] == "Primary YAML"
    )
    registry_path.write_text("indicators: {}\n", encoding="utf-8")
    with pytest.raises(IsADirectoryError):
        _ = config.run_signature
    with pytest.raises(IsADirectoryError):
        catalog_harvester._load_wvs_indicator_catalog_from_local_file()
    variable_path.rmdir()
    assert catalog_harvester._load_wvs_indicator_catalog_from_local_file() == (
        catalog_harvester._WVS_STATIC_INDICATORS
    )
    registry_path.write_text("indicators: [malformed\n", encoding="utf-8")
    assert catalog_harvester._load_wvs_indicator_catalog_from_local_file() == (
        catalog_harvester._WVS_STATIC_INDICATORS
    )
    assert config.run_signature != absent_signature


def test_resolved_legacy_mode_binds_signature_and_actual_dispatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from polisyos.data_forge.domains.catalog.batch.core_sources import api as core_api

    config = DatasetBatchConfig(snapshot_root=tmp_path / "snapshot")
    branches: list[str] = []
    parallel = core_api._ingest_catalog_observations_parallel
    legacy = core_api._ingest_catalog_observations_legacy

    async def observed_parallel(*args, **kwargs):
        branches.append("parallel")
        return await parallel(*args, **kwargs)

    async def observed_legacy(*args, **kwargs):
        branches.append("legacy")
        return await legacy(*args, **kwargs)

    monkeypatch.setattr(core_api, "_ingest_catalog_observations_parallel", observed_parallel)
    monkeypatch.setattr(core_api, "_ingest_catalog_observations_legacy", observed_legacy)
    monkeypatch.delenv("POLISYOS_DATASET_LEGACY_SERIAL", raising=False)
    false_signature = config.run_signature
    asyncio.run(core_api._ingest_catalog_observations(config.db_path, [], config=config))
    assert branches[-1] == "parallel"
    for spelling in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("POLISYOS_DATASET_LEGACY_SERIAL", spelling)
        assert config.run_signature == false_signature
        assert core_api._legacy_serial_mode_enabled() is False
    true_signature = None
    for spelling in ("1", "true", "yes", "on"):
        monkeypatch.setenv("POLISYOS_DATASET_LEGACY_SERIAL", spelling)
        signature = config.run_signature
        assert signature != false_signature
        if true_signature is None:
            true_signature = signature
        assert signature == true_signature
        assert core_api._legacy_serial_mode_enabled() is True
    asyncio.run(core_api._ingest_catalog_observations(config.db_path, [], config=config))
    assert branches[-1] == "legacy"
    monkeypatch.setenv("POLISYOS_DATASET_LEGACY_SERIAL", "off")
    assert config.run_signature == false_signature


def test_wvs_bulk_resolves_current_policy_once_per_operation(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from polisyos.data_forge.domains.catalog.batch.core_sources import loaders

    registry_path = tmp_path / "wvs.yaml"
    registry_path.write_text(
        "indicators:\n  A165:\n    response_type: binary_12\n    aggregation: weighted_mean\n",
        encoding="utf-8",
    )
    csv_path = tmp_path / "wvs.csv"
    csv_path.write_text(
        "COUNTRY_ALPHA,S020,S002VS,S017,S018,A165\n"
        "UKR,2020,7,1,1,2\nUKR,2020,7,1,1,2\nUKR,2020,7,1,1,2\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(loaders, "_wvs_registry_path", lambda: registry_path)
    monkeypatch.setattr(loaders, "_wvs_bulk_csv_path", lambda: csv_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snapshot")
    signature = config.run_signature
    snapshot = loaders._material_file_snapshot
    reads: list[Path] = []

    def observed_snapshot(path: Path, **kwargs):
        if path == registry_path:
            reads.append(path)
        return snapshot(path, **kwargs)

    monkeypatch.setattr(loaders, "_material_file_snapshot", observed_snapshot)
    initial = loaders._load_wvs_bulk_duckdb(["A165"], year_window=(2020, 2020))
    assert reads == [registry_path]
    assert initial["A165"][0]["sample_size"] == 3
    assert initial["A165"][0]["value"] == 0.0
    previous_stat = registry_path.stat()
    registry_path.write_bytes(registry_path.read_bytes().replace(b"binary_12", b"continuous"))
    _restore_stat(registry_path, previous_stat)
    reads.clear()
    changed = loaders._load_wvs_bulk_duckdb(["A165"], year_window=(2020, 2020))
    assert reads == [registry_path]
    assert changed["A165"][0]["sample_size"] == 3
    assert changed["A165"][0]["value"] == 2.0
    assert config.run_signature != signature
