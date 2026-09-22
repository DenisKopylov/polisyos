from __future__ import annotations

import json

from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.pipeline import (
    _record_stage_completion,
    _should_skip_stage,
    run_dataset_pipeline_sync,
)
from polisyos.data_forge.kernel.embeddings import build_embedding_generation


def test_pipeline_writes_telemetry_when_qc_fails(monkeypatch, tmp_path) -> None:
    def _boom(*args, **kwargs):
        raise RuntimeError("qc exploded")

    monkeypatch.setattr("polisyos.data_forge.domains.catalog.batch.qc.run_qc", _boom)
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"qc"}),
    )

    try:
        run_dataset_pipeline_sync(config)
    except RuntimeError as exc:
        assert "qc exploded" in str(exc)
    else:
        raise AssertionError("Expected pipeline to propagate QC failure")

    assert config.telemetry_path.exists()
    with open(config.telemetry_path, encoding="utf-8") as fh:
        payload = json.load(fh)

    assert payload["pipeline_status"] == "failed"
    assert payload["current_stage"] == "qc"
    assert "qc exploded" in payload["error"]


def test_embed_resume_does_not_skip_when_selected_member_is_missing(tmp_path) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"embed"}),
        resume=True,
    )
    build_embedding_generation(
        rows=[],
        index_dir=config.index_dir,
        embedding_model=config.embedding_model,
        embedding_device="cpu",
        embedding_dimension=config.embedding_dimension,
        legacy_embeddings_path=config.index_dir / "ds_dataset_embeddings.npz",
        legacy_index_path=config.index_dir / "ds_dataset_index.hnsw",
    )
    _record_stage_completion(config, "embed")
    assert _should_skip_stage(config, "embed")

    selector = json.loads(
        (config.index_dir / "embedding_generation.json").read_text(encoding="utf-8")
    )
    generation_dir = config.index_dir / "embedding_generations" / selector["generation_id"]
    (generation_dir / "embeddings.npz").unlink()

    assert not _should_skip_stage(config, "embed")
