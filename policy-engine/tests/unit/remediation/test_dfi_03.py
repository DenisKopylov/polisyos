"""Behavioral witnesses for the DFI-03 batch-resume contract."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import duckdb
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
    _stage_input_fingerprint,
    current_content_stage_receipt,
    run_content_stage_with_receipt,
    run_dataset_pipeline_sync,
)
from polisyos.data_forge.domains.catalog.batch.source_registry import SourceRegistry, SourceSpec
from polisyos.data_forge.kernel.embeddings import build_embedding_generation
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
