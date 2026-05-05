from __future__ import annotations

import os

import pytest
from polisyos.data_forge.domains.legal.batch.config import BatchConfig


def _cfg(tmp_path, *, shard_count: int, shard_index: int, stages: frozenset[str]) -> BatchConfig:
    return BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=tmp_path / "out",
        shard_count=shard_count,
        shard_index=shard_index,
        stages=stages,
    )


def test_shard_state_paths_are_isolated(tmp_path) -> None:
    cfg = _cfg(
        tmp_path,
        shard_count=5,
        shard_index=2,
        stages=frozenset({"parse", "structure", "spo"}),
    )
    assert cfg.sharded is True
    assert cfg.shard_slug == "shard_02_of_05"

    # Shared stage outputs.
    assert str(cfg.provisions_dir).endswith("/out/provisions")
    assert str(cfg.spo_results_dir).endswith("/out/spo_results")

    # Shard-local state.
    assert str(cfg.progress_path).endswith("/out/_shards/shard_02_of_05/progress.jsonl")
    assert str(cfg.db_path).endswith("/out/_shards/shard_02_of_05/lex_knowledge_graph.duckdb")
    assert str(cfg.openai_batches_dir).endswith("/out/_shards/shard_02_of_05/openai_batches")


def test_doc_assignment_is_unique_across_shards(tmp_path) -> None:
    configs = [
        _cfg(
            tmp_path,
            shard_count=5,
            shard_index=i,
            stages=frozenset({"parse", "structure", "spo"}),
        )
        for i in range(5)
    ]
    doc_ids = [
        "d50ecd49c7651689",
        "ec234c69f92fd5ff",
        "c859d7c276595bed",
        "19f89d204898f31b",
        "64da45922f0fe840",
        "63bf81f2863e0a3d",
        "7eb52caff7c7d4aa",
    ]
    for doc_id in doc_ids:
        owners = [cfg.shard_index for cfg in configs if cfg.is_doc_in_shard(doc_id)]
        assert len(owners) == 1


def test_pre_sharded_manifest_bypasses_hash_assignment(tmp_path) -> None:
    configs = [
        BatchConfig(
            cards_path=tmp_path / "cards.xml",
            texts_path=tmp_path / "texts.xml",
            output_dir=tmp_path / f"out-{i}",
            shard_count=6,
            shard_index=i,
            stages=frozenset({"parse", "structure", "spo"}),
            manifest_is_pre_sharded=True,
        )
        for i in range(6)
    ]
    for doc_id in (
        "d50ecd49c7651689",
        "ec234c69f92fd5ff",
        "c859d7c276595bed",
    ):
        owners = [cfg.shard_index for cfg in configs if cfg.is_doc_in_shard(doc_id)]
        assert owners == [0, 1, 2, 3, 4, 5]


def test_invalid_shard_index_raises(tmp_path) -> None:
    with pytest.raises(ValueError):
        _cfg(
            tmp_path,
            shard_count=3,
            shard_index=3,
            stages=frozenset({"parse", "structure", "spo"}),
        )


def test_sharded_graph_stage_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError):
        _cfg(
            tmp_path,
            shard_count=2,
            shard_index=0,
            stages=frozenset({"parse", "graph"}),
        )


def test_invalid_spo_verify_mode_raises(tmp_path) -> None:
    with pytest.raises(ValueError):
        BatchConfig(
            cards_path=tmp_path / "cards.xml",
            texts_path=tmp_path / "texts.xml",
            output_dir=tmp_path / "out",
            shard_count=1,
            shard_index=0,
            stages=frozenset({"parse", "structure", "spo"}),
            spo_verify_mode="broken_mode",
        )


def test_invalid_spo_request_batch_size_raises(tmp_path) -> None:
    with pytest.raises(ValueError):
        BatchConfig(
            cards_path=tmp_path / "cards.xml",
            texts_path=tmp_path / "texts.xml",
            output_dir=tmp_path / "out",
            shard_count=1,
            shard_index=0,
            stages=frozenset({"parse", "structure", "spo"}),
            spo_request_batch_size=0,
        )


def test_invalid_spo_request_batch_chars_raises(tmp_path) -> None:
    with pytest.raises(ValueError):
        BatchConfig(
            cards_path=tmp_path / "cards.xml",
            texts_path=tmp_path / "texts.xml",
            output_dir=tmp_path / "out",
            shard_count=1,
            shard_index=0,
            stages=frozenset({"parse", "structure", "spo"}),
            spo_request_batch_chars=200,
        )


def test_gonka_api_keys_default_from_env(monkeypatch, tmp_path) -> None:
    for key in list(os.environ):
        if key == "GONKA_API_KEY" or key.startswith("GONKA_API_KEY_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GONKA_API_KEY", "primary-key")
    monkeypatch.setenv("GONKA_API_KEY_2", "secondary-key")
    monkeypatch.setenv("GONKA_API_KEY_1", "first-extra-key")

    cfg = BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=tmp_path / "out",
        stages=frozenset({"parse", "structure", "spo"}),
    )

    assert cfg.gonka_api_key == "primary-key"
    assert cfg.gonka_api_keys == ["primary-key", "first-extra-key", "secondary-key"]


def test_explicit_gonka_api_key_is_promoted_to_front(monkeypatch, tmp_path) -> None:
    for key in list(os.environ):
        if key == "GONKA_API_KEY" or key.startswith("GONKA_API_KEY_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GONKA_API_KEY_1", "key-a")
    monkeypatch.setenv("GONKA_API_KEY_2", "key-b")

    cfg = BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=tmp_path / "out",
        stages=frozenset({"parse", "structure", "spo"}),
        gonka_api_key="priority-key",
    )

    assert cfg.gonka_api_key == "priority-key"
    assert cfg.gonka_api_keys == ["priority-key", "key-a", "key-b"]
