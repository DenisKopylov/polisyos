"""Behavioral witnesses for the DFI-03 batch-resume contract."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import types
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
        return {
            "encoder.weight": np.asarray([type(self).asset_revision, 1.0], dtype=np.float32)
        }

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
    input_path = (
        config.merged_records_path if stage == "graph_load" else config.db_path
    )
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


def test_benchmark_resume_rejects_core_ingest_state_change(monkeypatch, tmp_path) -> None:
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
    assert _should_skip_stage(config, "benchmark")

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


def test_qc_resume_rejects_selected_previous_snapshot_payload_change(
    monkeypatch, tmp_path
) -> None:
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


def test_selected_empty_generation_is_reused_without_reencoding(
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

    monkeypatch.setitem(
        pipeline_module._STAGE_RULE_VERSIONS, "embed", "policyos.catalog.embed.v2"
    )
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
