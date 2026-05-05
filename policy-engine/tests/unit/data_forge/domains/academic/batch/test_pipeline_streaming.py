from __future__ import annotations

import asyncio
import json

from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
from polisyos.data_forge.domains.academic.batch.pipeline import run_academic_pipeline


def test_pipeline_streams_doc_normalize_into_resolve_extract(monkeypatch, tmp_path) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"doc_normalize", "resolve_extract"}),
    )
    seen: dict[str, bool] = {"streaming": False}

    async def _fake_doc_normalize(cfg):  # type: ignore[no-untyped-def]
        await asyncio.sleep(0.01)
        cfg.doc_ready_queue_path.parent.mkdir(parents=True, exist_ok=True)
        cfg.doc_ready_queue_path.write_text(
            json.dumps({"work_id": "W1", "fulltext": {"work_id": "W1", "text": "results"}}) + "\n",
            encoding="utf-8",
        )
        cfg.manifests_dir.mkdir(parents=True, exist_ok=True)
        (cfg.manifests_dir / "doc_normalize.json").write_text("{}", encoding="utf-8")
        return {"docs_total": 1, "usable_docs": 1}

    async def _fake_resolve_extract(cfg):  # type: ignore[no-untyped-def]
        seen["streaming"] = bool(cfg.stream_doc_normalize_to_resolve_extract)
        for _ in range(20):
            if cfg.doc_ready_queue_path.exists():
                break
            await asyncio.sleep(0.01)
        assert cfg.doc_ready_queue_path.exists()
        return {"records": 1, "successful_llm_extractions_per_topic": 1}

    monkeypatch.setattr(
        "polisyos.data_forge.domains.academic.batch.doc_normalize.run_doc_normalize",
        _fake_doc_normalize,
    )
    monkeypatch.setattr(
        "polisyos.data_forge.domains.academic.batch.resolve_extract.run_resolve_extract",
        _fake_resolve_extract,
    )

    stats = asyncio.run(run_academic_pipeline(config))

    assert seen["streaming"] is True
    assert stats.metrics["doc_normalize_docs_total"] == 1
    assert stats.metrics["resolve_extract_successful_llm_extractions_per_topic"] == 1
    assert "doc_normalize" in stats.stage_times
    assert "resolve_extract" in stats.stage_times
