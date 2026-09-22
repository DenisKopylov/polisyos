"""Behavioral witnesses for the DFI-03 batch-resume contract."""

from __future__ import annotations

import json
import os
from pathlib import Path

from polisyos.data_forge.domains.catalog.batch import embedder as catalog_embedder
from polisyos.data_forge.domains.catalog.batch.checkpoints import save_stage_state
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.pipeline import (
    _record_stage_completion,
    _should_skip_stage,
    _stage_input_fingerprint,
    run_dataset_pipeline_sync,
)
from polisyos.data_forge.kernel.embeddings import build_embedding_generation


def _restore_stat(path: Path, stat_result: os.stat_result) -> None:
    os.utime(path, ns=(stat_result.st_atime_ns, stat_result.st_mtime_ns))


def _save_state(config: DatasetBatchConfig, stage: str, outputs: list[Path]) -> None:
    del outputs
    _record_stage_completion(config, stage)


def test_same_stat_changed_manifest_bytes_do_not_reuse_normalize_stage(tmp_path) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"normalize"}),
        resume=True,
    )
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


def test_mtime_only_manifest_change_keeps_normalize_stage_reusable(tmp_path) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"normalize"}),
        resume=True,
    )
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
